"""
키 입력 처리 모듈
- 웹/REST로 전달된 키 리스트를 로봇개 이동 명령(fb, lr)으로 변환
  (W/↑: 전진, S/↓: 후진, A/←: 좌회전, D/→: 우회전)
- 화살표 키 바인딩 관리: 화살표 4개 각각에 "default"(기본 보행) 또는
  저장된 동작 이름을 할당한다. 할당 정보는 key_bindings.json에 저장되고,
  메인 조종 화면(index.html)이 이를 읽어 동작 재생/보행을 분기한다.
- 조종 keep-alive 워치독: 클라이언트는 키를 누르고 있는 동안(또는 편집기에서
  동작을 재생하는 동안) 1초마다 POST /api/hold 를 보낸다. 종류는 두 가지:
    "move"   이동(보행) 중임을 알림 — 끊기면 이동을 정지
    "motion" 누르는 동안 재생(hold) 동작이 재생 중임을 알림 — 끊기면 동작 정지 후 기준 자세 복귀
  HOLD_TIMEOUT(기본 3초) 이상 끊기면(WiFi 끊김, 브라우저/탭 종료) 서버가 스스로 멈춘다.
  ※ /keys 로 조종하는 외부 프로그램도 이동 중에는 HOLD_TIMEOUT 안에 명령을
    다시 보내야 한다 (같은 키를 반복 전송하면 된다).
"""
import os
import json
import time
import threading

import dog_cont
import motion_cont
from config import KEY_BINDINGS_FILE, HOLD_TIMEOUT

ARROW_KEYS = ['arrowup', 'arrowdown', 'arrowleft', 'arrowright']
HOLD_KINDS = ('move', 'motion')

# 화살표 키 바인딩: 'default' = 기본 보행, 그 외 = 동작(모션) 이름
_bindings = {k: 'default' for k in ARROW_KEYS}

_last_hold = {'move': 0.0, 'motion': 0.0}
_hold_thread = None


# ==================== 화살표 키 바인딩 ====================

def load_bindings():
    global _bindings
    if os.path.exists(KEY_BINDINGS_FILE):
        try:
            with open(KEY_BINDINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for k in ARROW_KEYS:
                if isinstance(data.get(k), str) and data[k].strip():
                    _bindings[k] = data[k].strip()
            print(f"[key_cont] 키 바인딩 로드됨: {_bindings}")
        except Exception as e:
            print(f"[key_cont] 키 바인딩 로드 실패: {e}")


def save_bindings():
    try:
        with open(KEY_BINDINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(_bindings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[key_cont] 키 바인딩 저장 실패: {e}")


def get_bindings():
    return dict(_bindings)


def set_bindings(new_bindings):
    """화살표 키 바인딩 갱신 (부분 갱신 허용). 잘못된 키/없는 동작은 거부."""
    if not isinstance(new_bindings, dict):
        raise ValueError("바인딩 데이터 형식이 잘못되었습니다.")
    cleaned = {}
    for k, v in new_bindings.items():
        if k not in ARROW_KEYS:
            raise ValueError(f"바인딩 가능한 키가 아닙니다: {k}")
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{k}의 할당 값이 잘못되었습니다.")
        v = v.strip()
        if v != 'default' and not motion_cont.motion_exists(v):
            raise ValueError(f"저장된 동작이 아닙니다: {v} (먼저 저장하세요)")
        cleaned[k] = v
    _bindings.update(cleaned)
    save_bindings()
    print(f"[key_cont] 키 바인딩 저장됨: {_bindings}")


def unbind_motion(name):
    """동작이 삭제되었을 때 그 동작을 가리키는 화살표 할당을 기본 보행으로 되돌린다"""
    changed = [k for k, v in _bindings.items() if v == name]
    for k in changed:
        _bindings[k] = 'default'
    if changed:
        save_bindings()
        print(f"[key_cont] 삭제된 동작 '{name}'의 할당 해제: {changed}")
    return changed


# ==================== 키 -> 이동 변환 ====================

def keys_to_move(keys):
    """키 리스트 -> (fb, lr) 변환"""
    if isinstance(keys, str):
        keys = [keys]
    if not isinstance(keys, (list, tuple)):
        keys = []
    keys = [str(k).lower() for k in keys[:16]]
    fb = 0
    lr = 0
    if 'w' in keys or 'arrowup' in keys:
        fb = 1
    elif 's' in keys or 'arrowdown' in keys:
        fb = -1
    if 'a' in keys or 'arrowleft' in keys:
        lr = -1
    elif 'd' in keys or 'arrowright' in keys:
        lr = 1
    return fb, lr


def handle_key(keys):
    """
    keys: 리스트 형태의 입력 키 (예: ['w'], ['w', 'd'])
    이동 명령이 있으면 재생 중인 동작을 먼저 중단한다 (안전).
    ※ 화살표 바인딩 분기는 웹 UI(index.html)에서 처리하며,
      이 REST 경로(/keys, 외부 PC 조종용)는 항상 기본 보행으로 동작한다.
    """
    fb, lr = keys_to_move(keys)
    if fb != 0 or lr != 0:
        if motion_cont.is_playing():
            motion_cont.stop(to_home=False)
        refresh_hold('move')
    dog_cont.input_cmd(fb, lr)


# ==================== 조종 keep-alive 워치독 ====================

def refresh_hold(kind=None):
    """
    클라이언트가 아직 키를 누르고 있음(또는 편집기가 재생 중임)을 기록.
    kind: 'move' / 'motion' / None(둘 다)
    """
    now = time.monotonic()
    kinds = HOLD_KINDS if kind is None else (kind,)
    for k in kinds:
        if k in _last_hold:
            _last_hold[k] = now


def _hold_stale(kind):
    return time.monotonic() - _last_hold[kind] > HOLD_TIMEOUT


def _hold_watchdog_loop():
    while True:
        time.sleep(0.5)
        try:
            if HOLD_TIMEOUT <= 0:
                continue
            if dog_cont.is_moving() and _hold_stale('move'):
                print("[key_cont] 조종 keep-alive 끊김 -> 이동 정지")
                dog_cont.input_cmd(0, 0)
            if motion_cont.is_hold_playing() and _hold_stale('motion'):
                print("[key_cont] 동작 keep-alive 끊김 -> 동작 정지 후 기준 자세 복귀")
                motion_cont.stop(to_home=True)
        except Exception as e:
            print(f"[key_cont] 워치독 에러: {e}")


def start_hold_watchdog():
    """keep-alive 워치독 스레드 시작 (중복 호출해도 1개만 돈다)"""
    global _hold_thread
    if _hold_thread is None:
        refresh_hold()
        _hold_thread = threading.Thread(target=_hold_watchdog_loop, daemon=True)
        _hold_thread.start()


# 모듈 import 시점에 저장된 바인딩을 로드
load_bindings()
