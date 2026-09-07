"""
동작(모션) 만들기 모듈 — 유니티 애니메이터 방식의 키프레임 동작 시스템

동작(motion)은 키프레임의 리스트다. 각 키프레임은 "시간(초) + 12개 서보 각도"로,
재생 시 키프레임 사이를 ESP32가 보간(J 커맨드)으로 이어서 움직인다.

파일 포맷 (motions/<이름>.json):
{
    "name": "인사하기",
    "loop": false,
    "keyframes": [
        {"time": 0.0, "angles": [90, 90, ... 12개]},
        {"time": 0.5, "angles": [95, 80, ... 12개]},
        ...
    ]
}

재생 흐름:
  1. 현재 자세 -> 첫 키프레임 진입 (코사인 보간, 양끝 정지).
     진입 시간 = max(MOTION_DEFAULT_ENTRY_MS, 첫 키프레임 time). 바닥에 누운 자세처럼
     첫 키프레임과 멀리 떨어진 자세에서 출발해도 튀지 않도록 최소 시간을 보장한다.
  2. 키프레임 구간마다 J <구간시간ms> <각도12개> <보간모드> 전송 후 구간시간만큼 대기
     (보간은 ESP32 5ms 루프가 수행 -> 파이썬 타이밍 지터의 영향 없음)
  3. 보간 모드: 반복 동작은 전 구간 선형(등속)으로 이어 붙여 걷기처럼 주기적인
     동작이 멈칫거리지 않게 한다. 일반 동작은 첫 구간 ease-in, 중간 선형,
     마지막 ease-out (구간이 하나면 코사인).
  4. loop=true면 마지막 키프레임에서 첫 키프레임으로 되돌아가 반복.
     복귀 시간 = 첫 키프레임 time (0보다 크면) / 0이면 마지막 구간의 시간.
     (편집기가 첫 키프레임을 0초로 만들기 때문에, 학생이 만든 걷기 동작도 별도 설정
      없이 키프레임 간격과 같은 시간으로 자연스럽게 순환한다)

재생/정지는 하나의 락으로 직렬화된다. 화살표 키를 빠르게 눌렀다 떼면 재생과 정지
요청이 Flask 스레드 두 개에서 동시에 처리될 수 있는데, 락이 없으면 "정지 상태인데
재생 스레드가 살아서 J를 계속 보내는" 꼬임이 생긴다.
"""
import os
import re
import json
import math
import threading

import dog_cont
from dog_cont import EASE_INOUT, EASE_LINEAR, EASE_IN, EASE_OUT
from config import (MOTIONS_DIR, NUM_SERVOS, MOTION_MIN_SEGMENT_MS,
                    MOTION_MAX_SEGMENT_MS, MOTION_DEFAULT_ENTRY_MS,
                    MOTION_SEND_LEAD_MS)

MOTION_NAME_MAX_LEN = 40   # 파일명 길이 제한

_ctrl_lock = threading.RLock()     # play/stop 직렬화
_state_lock = threading.Lock()     # _status 보호
_play_thread = None                # (Thread, 그 스레드 전용 stop Event)
_play_gen = 0                      # 재생 세대: 늦게 끝난 옛 스레드가 새 상태를 덮지 않게
_status = {"playing": False, "motion": None, "loop": False, "hold": False, "gen": 0}


# ==================== 저장 / 불러오기 (CRUD) ====================

def _safe_name(name):
    """파일명으로 쓸 수 있게 동작 이름을 정리 (한글/영문/숫자/공백/-/_ 허용, 40자 이내)"""
    name = str(name).strip()
    name = re.sub(r'[^\w\s\-가-힣]', '', name, flags=re.UNICODE)
    name = " ".join(name.split())[:MOTION_NAME_MAX_LEN].strip()
    if not name:
        raise ValueError("동작 이름이 비어 있습니다. (한글/영문/숫자/공백/-/_ 만 사용)")
    return name


def _motion_path(name):
    return os.path.join(MOTIONS_DIR, _safe_name(name) + ".json")


def _ensure_dir():
    os.makedirs(MOTIONS_DIR, exist_ok=True)


def motion_exists(name):
    try:
        return os.path.exists(_motion_path(name))
    except ValueError:
        return False


def _check_loop(loop, n_keyframes):
    if loop and n_keyframes < 2:
        raise ValueError("반복 재생은 키프레임이 2개 이상 필요합니다. (1개면 반복 체크를 끄세요)")


def validate_motion(data):
    """동작 데이터 검증 + 정규화 (시간순 정렬, 각도 클램프). 검증된 dict 반환."""
    if not isinstance(data, dict):
        raise ValueError("동작 데이터 형식이 잘못되었습니다.")
    keyframes = data.get("keyframes", [])
    if not isinstance(keyframes, list) or len(keyframes) == 0:
        raise ValueError("키프레임이 1개 이상 있어야 합니다.")

    normalized = []
    for i, kf in enumerate(keyframes):
        try:
            t = float(kf["time"])
            angles = kf["angles"]
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"키프레임 #{i + 1}의 형식이 잘못되었습니다. (time, angles 필요)")
        if t != t or t < 0:
            raise ValueError(f"키프레임 #{i + 1}의 시간이 잘못되었습니다.")
        if not isinstance(angles, list) or len(angles) != NUM_SERVOS:
            raise ValueError(f"키프레임 #{i + 1}의 angles는 {NUM_SERVOS}개여야 합니다.")
        try:
            clamped = [max(0.0, min(180.0, float(a))) for a in angles]
        except (TypeError, ValueError):
            raise ValueError(f"키프레임 #{i + 1}의 angles에 숫자가 아닌 값이 있습니다.")
        if any(a != a for a in clamped):
            raise ValueError(f"키프레임 #{i + 1}의 angles에 잘못된 값(NaN)이 있습니다.")
        normalized.append({"time": round(t, 3), "angles": clamped})

    normalized.sort(key=lambda kf: kf["time"])

    # 키프레임 시간 간격 검사: 같거나 너무 가까우면 재생이 뚝뚝 끊기므로 명확히 거부
    min_gap = MOTION_MIN_SEGMENT_MS / 1000.0
    for i in range(len(normalized) - 1):
        gap = normalized[i + 1]["time"] - normalized[i]["time"]
        if gap < min_gap - 1e-9:
            raise ValueError(
                f"키프레임 #{i + 1}({normalized[i]['time']}초)과 #{i + 2}({normalized[i + 1]['time']}초)의 "
                f"시간 간격이 너무 짧습니다. 최소 {min_gap}초 이상 차이가 나야 합니다.")

    loop = bool(data.get("loop", False))
    _check_loop(loop, len(normalized))
    return {
        "name": _safe_name(data.get("name", "이름없는 동작")),
        "loop": loop,
        "keyframes": normalized,
    }


def list_motions():
    """저장된 동작 목록: [{name, keyframes, duration, loop}]. name은 파일명 기준."""
    _ensure_dir()
    motions = []
    for fname in sorted(os.listdir(MOTIONS_DIR)):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(MOTIONS_DIR, fname), 'r', encoding='utf-8') as f:
                data = json.load(f)
            kfs = data.get("keyframes", [])
            motions.append({
                "name": fname[:-5],  # 불러올 때 쓰는 이름 = 파일명
                "keyframes": len(kfs),
                "duration": max((float(kf.get("time", 0)) for kf in kfs), default=0),
                "loop": bool(data.get("loop", False)),
            })
        except Exception as e:
            print(f"[motion_cont] {fname} 읽기 실패: {e}")
    return motions


def load_motion(name):
    """동작 파일 로드. 없으면 None, 파일이 손상됐으면 ValueError."""
    path = _motion_path(name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise ValueError(f"동작 파일을 읽을 수 없습니다 ({name}): {e}")


def save_motion(name, data):
    """동작 저장 (검증 후). 검증된 데이터 반환."""
    _ensure_dir()
    if not isinstance(data, dict):
        raise ValueError("동작 데이터 형식이 잘못되었습니다.")
    data = dict(data)
    data["name"] = name
    validated = validate_motion(data)
    with open(_motion_path(name), 'w', encoding='utf-8') as f:
        json.dump(validated, f, ensure_ascii=False, indent=2)
    print(f"[motion_cont] 동작 저장됨: {validated['name']} ({len(validated['keyframes'])} 키프레임)")
    return validated


def delete_motion(name):
    path = _motion_path(name)
    if os.path.exists(path):
        os.remove(path)
        print(f"[motion_cont] 동작 삭제됨: {name}")
        return True
    return False


# ==================== 재생 ====================

def get_status():
    with _state_lock:
        return {k: v for k, v in _status.items() if k != "gen"}


def is_playing():
    with _state_lock:
        return _status["playing"]


def is_hold_playing():
    """키를 누르고 있는 동안만 재생되는(hold) 동작이 재생 중인지 (keep-alive 워치독용)"""
    with _state_lock:
        return _status["playing"] and _status["hold"]


def entry_ms_for(motion):
    """현재 자세 -> 첫 키프레임 진입 시간(ms)"""
    kf0 = motion["keyframes"][0]
    ms = _segment_ms(0, kf0["time"]) if kf0["time"] > 0 else 0
    return max(MOTION_DEFAULT_ENTRY_MS, ms)


def loop_back_ms_for(motion):
    """반복 시 마지막 -> 첫 키프레임 복귀 시간(ms)"""
    kfs = motion["keyframes"]
    if kfs[0]["time"] > 0:
        return _segment_ms(0, kfs[0]["time"])
    if len(kfs) >= 2:
        return _segment_ms(kfs[-2]["time"], kfs[-1]["time"])
    return MOTION_DEFAULT_ENTRY_MS


def play(name, loop=None, hold=False):
    """
    저장된 동작 재생 시작 (백그라운드 스레드). 검증된 동작 dict 반환.
    loop가 None이면 파일에 저장된 loop 설정을 따른다.
    hold=True면 "키를 누르고 있는 동안" 재생되는 동작으로 표시된다
    (반복 동작에만 적용, keep-alive가 끊기면 서버가 알아서 정지시킨다).
    """
    motion = load_motion(name)
    if motion is None:
        raise ValueError(f"동작을 찾을 수 없습니다: {name}")
    return play_data(motion, loop=loop, hold=hold)


def play_data(data, loop=None, hold=False):
    """
    동작 데이터(dict)를 바로 재생 (저장하지 않은 편집 중인 동작 미리보기용).
    검증된 동작 dict 반환. 잘못된 데이터면 ValueError.
    """
    global _play_thread, _play_gen

    motion = validate_motion(data)
    if loop is not None:
        motion["loop"] = bool(loop)
        _check_loop(motion["loop"], len(motion["keyframes"]))
    # hold(누르는 동안 재생)는 반복 동작에만 의미가 있다. 일반 동작은 끝까지 재생.
    hold = bool(hold) and motion["loop"]

    with _ctrl_lock:
        _stop_locked()  # 재생 중이던 동작이 있으면 먼저 중단 (join까지)
        _play_gen += 1
        gen = _play_gen
        stop_event = threading.Event()
        with _state_lock:
            _status.update(playing=True, motion=motion["name"], loop=motion["loop"],
                           hold=hold, gen=gen)
        t = threading.Thread(target=_play_loop, args=(motion, stop_event, gen), daemon=True)
        _play_thread = (t, stop_event)
        t.start()
    print(f"[motion_cont] 재생 시작: {motion['name']} (loop={motion['loop']}, hold={hold})")
    return motion


def _segment_ms(t_prev, t_next):
    ms = int(round((t_next - t_prev) * 1000))
    return max(MOTION_MIN_SEGMENT_MS, min(MOTION_MAX_SEGMENT_MS, ms))


def _segment_ease(i, nseg, loop):
    """구간 i(0부터)의 보간 모드"""
    if loop:
        return EASE_LINEAR          # 반복: 전 구간 등속 -> 이음새 없이 순환
    if nseg == 1:
        return EASE_INOUT           # 구간 하나: 양끝 감속
    if i == 0:
        return EASE_IN              # 첫 구간: 시작만 감속
    if i == nseg - 1:
        return EASE_OUT             # 마지막 구간: 끝만 감속
    return EASE_LINEAR


def _play_loop(motion, stop_event, gen):
    def wait_segment(ms, is_last):
        """
        구간 시간만큼 대기. 마지막 구간이 아니면 MOTION_SEND_LEAD_MS만큼 일찍 깨어나
        다음 J를 먼저 보낸다 (시리얼 전송/스케줄링 지연 상쇄 -> 구간 사이 멈칫 방지).
        정지 요청이 오면 True.
        """
        if is_last:
            w = ms
        else:
            w = max(MOTION_MIN_SEGMENT_MS // 2, ms - MOTION_SEND_LEAD_MS)
        return stop_event.wait(w / 1000.0)

    try:
        kfs = motion["keyframes"]
        loop = motion["loop"]
        nseg = len(kfs) - 1

        # 1) 현재 자세 -> 첫 키프레임 진입 (코사인, 최소 MOTION_DEFAULT_ENTRY_MS)
        entry_ms = entry_ms_for(motion)
        dog_cont.pose(entry_ms, kfs[0]["angles"], EASE_INOUT)
        if wait_segment(entry_ms, nseg == 0 and not loop):
            return

        back_ms = loop_back_ms_for(motion)
        while True:
            # 2) 키프레임 구간 순차 재생
            for i, (prev, nxt) in enumerate(zip(kfs, kfs[1:])):
                ms = _segment_ms(prev["time"], nxt["time"])
                dog_cont.pose(ms, nxt["angles"], _segment_ease(i, nseg, loop))
                is_last = (not loop) and (i == nseg - 1)
                if wait_segment(ms, is_last):
                    return

            # 3) 루프 처리: 마지막 -> 첫 키프레임으로 복귀 후 반복
            if not loop:
                break
            dog_cont.pose(back_ms, kfs[0]["angles"], EASE_LINEAR if nseg > 0 else EASE_INOUT)
            if wait_segment(back_ms, False):
                return
    except Exception as e:
        print(f"[motion_cont] 재생 에러: {e}")
    finally:
        with _state_lock:
            if _status.get("gen") == gen:  # 내가 최신 재생일 때만 상태를 정리
                _status.update(playing=False, motion=None, loop=False, hold=False)
        print(f"[motion_cont] 재생 종료: {motion.get('name')}")


def _stop_locked():
    """(_ctrl_lock 보유 상태에서) 재생 스레드를 멈추고 상태를 정리한다"""
    global _play_thread
    if _play_thread is not None:
        t, ev = _play_thread
        if t.is_alive():
            ev.set()
            t.join(timeout=2.0)
            if t.is_alive():
                print("[motion_cont] 경고: 재생 스레드가 2초 안에 끝나지 않았습니다.")
        _play_thread = None
    with _state_lock:
        _status.update(playing=False, motion=None, loop=False, hold=False)


def stop(to_stand=False, only_motion=None):
    """
    재생 중단. to_stand=True면 중단 후 기립 자세로 복귀(F 4, ESP32가 부드럽게 처리).
    only_motion이 주어지면 그 이름의 동작이 재생 중일 때만 중단한다
    (화살표 키를 뗐을 때 다른 동작/조작을 방해하지 않기 위함).
    중단(또는 기립)을 수행했으면 True.
    """
    with _ctrl_lock:
        if only_motion is not None:
            with _state_lock:
                if not _status["playing"] or _status["motion"] != only_motion:
                    return False
        _stop_locked()
        if to_stand:
            dog_cont.function_stand()
    return True


# ============================================================================
# 기본 예제 동작 생성 ("예제 걷기")
#
# 기존 펌웨어 보행(gait) 코드는 그대로 두고, 하드웨어에 따라 조정할 수 있는
# "대안 걷기"를 키프레임 동작으로 자동 생성한다. 펌웨어의 역기구학(IK)을 그대로
# 파이썬으로 포팅해서, 서버 시작 시점의 캘리브레이션(중간각)을 반영해 각도를 계산한다.
# 기본 보행보다 느리고(사이클 1.8초), 발을 더 높이 들고(14mm), 보폭은 짧다(30mm).
# 편집 페이지에서 시간/각도를 수정하거나, 화살표 키에 할당해 사용할 수 있다.
# ============================================================================

# WAVEGO 기구 치수 (펌웨어와 동일)
_LINK_W, _LINK_S = 19.15, 12.2
_LINK_A, _LINK_B = 40.0, 40.0
_LINK_C, _LINK_D, _LINK_E = 39.8153, 31.7750, 30.8076
_SERVO_DIR = [1, -1, -1, 1, 1, -1, -1, 1, 1, -1, -1, 1]
# 다리 번호 -> (Hip/FORE, Knee/BACK, Wave) 서보 인덱스
_LEG_SERVOS = {1: (0, 1, 2), 2: (4, 5, 3), 3: (6, 7, 8), 4: (10, 11, 9)}

# 예제 걷기 파라미터 (사용자가 편집기에서 조정 가능하도록 키프레임에 구워짐)
WALK_EXAMPLE_NAME = "예제 걷기"
_EX_CYCLE_SEC = 1.8      # 1보행 사이클 시간 (기본 보행 1.0초보다 느리게)
_EX_KEYFRAMES = 12       # 사이클당 키프레임 수 (150ms 간격)
_EX_RANGE = 30.0         # 보폭 (기본 40 -> 짧게: 서보 부하 감소)
_EX_LIFT = 14.0          # 스윙 시 발 들어올리는 높이 (기본 9 -> 높게: 발끌림 방지)
_EX_HEIGHT = 95.0        # 지지 높이 (기본 보행과 동일)
_EX_ACC = 5.0
_EX_LIFT_PROP = 0.25
_EX_EXT_Z = 25.0


def _c1(v):
    return max(-1.0, min(1.0, v))


def _wiggle_plane_ik(a_in, b_in):
    """정면 평면 IK: (z, y) -> (Wave 서보 각도, 유효 다리 길이)"""
    la = _LINK_W
    l2c = a_in * a_in + b_in * b_in
    lc = math.sqrt(l2c)
    lam = math.degrees(math.atan(a_in / b_in))
    psi = math.degrees(math.acos(_c1(la / lc)))
    lb = math.sqrt(max(0.0, l2c - la * la))
    return psi + lam - 90.0, lb


def _single_leg_plane_ik(x_in, y_in):
    """측면 평면 5절 링크 IK: (x, y) -> (Hip 각도 beta, 무릎 링크 좌표)"""
    ls2 = _LINK_S / 2.0
    l_cd = (_LINK_C + _LINK_D) ** 2
    le2 = _LINK_E ** 2
    la2 = _LINK_A ** 2
    bs_sq = (x_in + ls2) ** 2 + y_in ** 2
    bs = math.sqrt(bs_sq)
    lam = math.acos(_c1((bs_sq + la2 - l_cd - le2) / (2.0 * bs * _LINK_A)))
    delta = math.atan((x_in + ls2) / y_in)
    beta = lam - delta
    theta = math.atan((_LINK_C + _LINK_D) / _LINK_E)
    sledc = math.sqrt(le2 + l_cd)
    omega = math.asin(_c1((y_in - math.cos(beta) * _LINK_A) / sledc))
    nu = math.pi - theta - omega
    dfx, dfy = math.cos(nu) * _LINK_E, math.sin(nu) * _LINK_E
    mu = math.pi / 2.0 - nu
    dex, dey = math.cos(mu) * _LINK_D, math.sin(mu) * _LINK_D
    return math.degrees(beta), x_in + dfx - dex, y_in - dfy - dey


def _simple_linkage_ik(a_in, b_in):
    """2링크 IK: 무릎(BACK) 서보 각도 alpha"""
    la, lb = _LINK_A, _LINK_B
    l2c = a_in * a_in + b_in * b_in
    lc = math.sqrt(l2c)
    lam = math.degrees(math.atan(b_in / a_in)) if a_in != 0 else 0.0
    psi = math.degrees(math.acos(_c1((la * la - lb * lb + l2c) / (2.0 * la * lc))))
    return 90.0 - lam - psi


def _leg_angles(leg, x, y, z, middles):
    """다리 1개의 발 좌표 -> 서보 3개 각도 (펌웨어 single_leg_ctrl과 동일)"""
    nf, nb, nw = _LEG_SERVOS[leg]
    w_alpha, w_len = _wiggle_plane_ik(z, y)
    beta, px, py = _single_leg_plane_ik(x, w_len)
    alpha = _simple_linkage_ik(py, px - _LINK_S / 2.0)
    return {
        nw: max(0.0, min(180.0, middles[nw] + w_alpha * _SERVO_DIR[nw])),
        nf: max(0.0, min(180.0, middles[nf] + (90.0 - beta) * _SERVO_DIR[nf])),
        nb: max(0.0, min(180.0, middles[nb] + alpha * _SERVO_DIR[nb])),
    }


def _gait_foot(phase):
    """보행 위상(0~1) -> 발의 (전후 오프셋, 다리 길이). 펌웨어의 수정된 궤적과 동일"""
    if phase < 1.0 - _EX_LIFT_PROP:
        # 지지구간: 발을 지면에 붙인 채 뒤로
        cp = phase / (1.0 - _EX_LIFT_PROP)
        r = (_EX_RANGE / 2.0 + _EX_ACC) * (1.0 - 2.0 * cp)
        y = _EX_HEIGHT
    else:
        # 스윙구간: 발을 들어올려 앞으로 복귀
        cp = (phase - (1.0 - _EX_LIFT_PROP)) / _EX_LIFT_PROP
        y = _EX_HEIGHT - _EX_LIFT * math.sin(cp * math.pi)
        r = -(_EX_RANGE / 2.0 + _EX_ACC) + (_EX_RANGE + 2.0 * _EX_ACC) * cp
    return r, y


def _walk_pose(global_phase, middles):
    """전체 위상 -> 12개 서보 각도 (트로트: 대각선 쌍이 0.5 위상차, 전진 방향)"""
    angles = [90.0] * NUM_SERVOS
    for leg, phase_off, ext_x in ((1, 0.0, 16.0), (4, 0.0, -16.0),
                                  (2, 0.5, -16.0), (3, 0.5, 16.0)):
        r, y = _gait_foot((global_phase + phase_off) % 1.0)
        for idx, val in _leg_angles(leg, r + ext_x, y, _EX_EXT_Z, middles).items():
            angles[idx] = round(val, 1)
    return angles


def generate_walk_motion(name=WALK_EXAMPLE_NAME):
    """현재 캘리브레이션(중간각) 기준으로 예제 걷기 동작 데이터를 생성"""
    middles = [float(a) for a in dog_cont.ServoMiddleAngle]
    keyframes = []
    for i in range(1, _EX_KEYFRAMES + 1):
        # 마지막 키프레임(i=N)은 위상 0 -> 루프 복귀(첫 키프레임 시간 간격)와 이어져
        # 걷기가 이음새 없이 반복된다
        phase = (i % _EX_KEYFRAMES) / _EX_KEYFRAMES
        t = round(_EX_CYCLE_SEC * i / _EX_KEYFRAMES, 2)
        keyframes.append({"time": t, "angles": _walk_pose(phase, middles)})
    return {"name": name, "loop": True, "keyframes": keyframes}


def ensure_default_motions():
    """예제 걷기 동작이 없으면 생성 (삭제 후 서버 재시작 시 현재 캘리브레이션으로 재생성)"""
    _ensure_dir()
    if os.path.exists(_motion_path(WALK_EXAMPLE_NAME)):
        return
    try:
        save_motion(WALK_EXAMPLE_NAME, generate_walk_motion())
        print(f"[motion_cont] 기본 예제 동작 생성됨: {WALK_EXAMPLE_NAME} "
              f"(사이클 {_EX_CYCLE_SEC}초, 보폭 {_EX_RANGE}mm, 발들기 {_EX_LIFT}mm)")
    except Exception as e:
        print(f"[motion_cont] 예제 동작 생성 실패: {e}")


if __name__ == '__main__':
    print("저장된 동작 목록:", list_motions())
