"""
로봇개(ESP32) 시리얼 제어 모듈

라즈베리파이는 연산을 하지 않는 통신 브릿지다. 이동/자세/보행의 실시간 연산은
전부 ESP32 펌웨어(esp32_controller.ino)가 5ms 루프에서 수행하고,
이 모듈은 한 줄짜리 텍스트 커맨드를 시리얼로 보내는 역할만 한다.

주요 커맨드 (RPi -> ESP32):
  M <fb> <lr>          이동 (-1/0/1)
  S <speed>            보행 속도 (STEP_ITERATE)
  F <n>                특수 기능 (1=엎드리기, 2=악수, 3=점프, 4=기립)
  J <ms> <a0..a11> <mode>
                       자세(포즈) 명령: 12개 서보를 ms 동안 보간 이동
                       mode 0=코사인 1=선형 2=ease-in 3=ease-out
  K <ms> <i> <a> ...   부분 포즈: 지정 서보만 이동 (슬라이더 미리보기)
  T                    토크 해제 / E: 토크 활성화
  U / V                현재 서보 실측 각도 / 목표 각도 읽기 ("POS ..."/"ANG ..." 응답,
                       실측 응답이 없는 서보는 "?")
  C 0/1                캘리브레이션 모드
  A <a0..a11>          캘리브레이션 중간각 12개
  O <p0..p11>          서보 ID(핀) 맵 12개 / P <joint> <pin>: 단건
  H                    하트비트 (ESP32 워치독 갱신용, 자동 전송)

모든 커맨드는 전송 전에 개행/제어문자를 제거한다 (한 줄 = 한 커맨드 보장).
"""
import os
import json
import time
import threading

import util
from config import (CALIBRATION_FILE, NUM_SERVOS, SERVO_NAMES, HEARTBEAT_INTERVAL,
                    QUERY_TIMEOUT, MIN_STEP_SPEED, MAX_STEP_SPEED,
                    HOME_POSE_MS, CALIBRATION_ADJUST_MS)

# 포즈(J) 보간 곡선 — 펌웨어의 PoseEase와 같은 값
EASE_INOUT = 0    # 코사인: 양끝 속도 0 (단발 자세 전환)
EASE_LINEAR = 1   # 등속 (키프레임이 연속되는 동작의 중간 구간)
EASE_IN = 2       # 시작만 감속 (연속 동작의 첫 구간)
EASE_OUT = 3      # 끝만 감속 (연속 동작의 마지막 구간)


class ServoReadError(Exception):
    """서보 실측 각도 읽기에서 일부 서보가 응답하지 않음 (failed = 서보 인덱스 목록)"""

    def __init__(self, failed):
        self.failed = list(failed)
        names = ", ".join(f"{i}번({SERVO_NAMES[i]})" for i in self.failed)
        super().__init__(f"응답 없는 서보: {names}. 서보 전원/배선을 확인하세요.")


# ==================== 모듈 상태 ====================

ser = None
HARDWARE_AVAILABLE = False

_uart_lock = threading.Lock()
_reconnect_lock = threading.Lock()
_heartbeat_thread = None

# 마지막으로 보낸 이동 명령 (keep-alive 워치독이 참조)
_move = {"fb": 0, "lr": 0}

calibration_data = {
    "pin_mapping": list(range(1, NUM_SERVOS + 1)),
    "active_preset": 1,
    "presets": {
        "1": [90] * NUM_SERVOS,
        "2": [90] * NUM_SERVOS,
        "3": [90] * NUM_SERVOS,
    }
}
pin_mapping = calibration_data["pin_mapping"]
# 프리셋 리스트를 그대로 참조하면 안 된다 — 별칭이 되면 현재 각도를 수정할 때
# 활성 프리셋이 아닌 다른 프리셋까지 같이 바뀐다. 항상 복사해서 쓴다.
ServoMiddleAngle = list(calibration_data["presets"]["1"])
calibrationMode = False


# ==================== 초기화 / 연결 ====================

def init():
    """시리얼 연결 + 캘리브레이션 로드/전송 + 하트비트 스레드 시작"""
    global ser, HARDWARE_AVAILABLE, _heartbeat_thread

    load_calibration()

    ser = util.connect_esp32()
    HARDWARE_AVAILABLE = ser is not None
    if HARDWARE_AVAILABLE:
        print("[dog_cont] ESP32 연결 완료.")
        send_initial_calibration()
    else:
        print("[dog_cont] Warning: ESP32 미연결. Mock 모드로 실행합니다.")

    if _heartbeat_thread is None:
        _heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
        _heartbeat_thread.start()


def _reconnect():
    """전송 실패 시 백그라운드 재연결 (uart_lock 밖에서 처리해 데드락 방지)"""
    global ser, HARDWARE_AVAILABLE
    # 여러 스레드(전송/질의/하트비트)가 동시에 실패해도 재연결은 1개만 수행
    if not _reconnect_lock.acquire(blocking=False):
        return
    try:
        print("⚠️ [dog_cont] 시리얼 연결 끊김 감지! 재연결을 시도합니다...")
        time.sleep(1)
        new_ser = util.connect_esp32()
        if new_ser:
            ser = new_ser
            HARDWARE_AVAILABLE = True
            time.sleep(0.5)
            send_initial_calibration()
            _move["fb"] = 0
            _move["lr"] = 0
            print("✅ [dog_cont] 재연결 성공! 캘리브레이션 데이터 재전송 완료.")
    finally:
        _reconnect_lock.release()


def _sanitize(cmd_str):
    """
    커맨드를 '출력 가능한 ASCII 한 줄'로 정리한다.
    개행(\\r, \\n)과 제어문자, 비ASCII 문자를 제거해 웹에서 들어온 값이
    다른 커맨드로 끼어들거나(인젝션) encode 에러로 연결이 끊기는 일을 막는다.
    """
    s = str(cmd_str)
    s = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in s)
    return " ".join(s.split())


def _on_serial_error(e, where):
    """전송/질의 실패 공통 처리: 포트를 닫고 백그라운드 재연결"""
    global HARDWARE_AVAILABLE
    print(f"[dog_cont] Serial {where} error: {e}")
    try:
        ser.close()
    except Exception:
        pass
    HARDWARE_AVAILABLE = False
    threading.Thread(target=_reconnect, daemon=True).start()


def send_cmd(cmd_str):
    """한 줄 커맨드 전송 (스레드 안전)"""
    line = _sanitize(cmd_str)
    if not line:
        return
    if not (HARDWARE_AVAILABLE and ser and ser.is_open):
        return
    with _uart_lock:
        try:
            ser.write((line + '\n').encode('ascii'))
            ser.flush()
        except Exception as e:
            _on_serial_error(e, "send")


def query(cmd_str, reply_prefix, timeout=QUERY_TIMEOUT):
    """
    커맨드를 보내고 reply_prefix로 시작하는 응답 한 줄을 기다린다.
    응답 문자열(prefix 제외 뒷부분) 또는 None 반환.
    """
    line = _sanitize(cmd_str)
    if not line:
        return None
    if not (HARDWARE_AVAILABLE and ser and ser.is_open):
        return None
    with _uart_lock:
        try:
            ser.reset_input_buffer()
            ser.write((line + '\n').encode('ascii'))
            ser.flush()
            buf = ""
            start = time.time()
            while time.time() - start < timeout:
                if ser.in_waiting > 0:
                    buf += ser.read(ser.in_waiting).decode('ascii', errors='ignore')
                    # 개행으로 끝난 "완성된 줄"만 검사한다.
                    # (수신 도중 잘린 줄을 응답으로 오인하면 각도 개수가 부족해짐)
                    complete, _, buf = buf.rpartition('\n')
                    for reply in complete.splitlines():
                        reply = reply.strip()
                        if reply.startswith(reply_prefix):
                            return reply[len(reply_prefix):].strip()
                time.sleep(0.01)
            return None
        except Exception as e:
            _on_serial_error(e, "query")
            return None


def _heartbeat_loop():
    """ESP32 워치독 갱신용 하트비트. 통신 두절 시 ESP32가 스스로 보행을 멈춘다."""
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        if HARDWARE_AVAILABLE:
            send_cmd("H")


# ==================== 이동 / 특수 기능 ====================

def _clamp_dir(v):
    """이동 방향값을 -1/0/1 정수로 강제 (문자열/범위 밖 값은 0 또는 클램프)"""
    try:
        v = int(float(v))
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(-1, min(1, v))


def input_cmd(fb, lr):
    """이동 명령: fb/lr 각각 -1, 0, 1"""
    fb = _clamp_dir(fb)
    lr = _clamp_dir(lr)
    _move["fb"] = fb
    _move["lr"] = lr
    send_cmd(f"M {fb} {lr}")


def is_moving():
    """마지막 이동 명령이 정지(0,0)가 아니면 True (keep-alive 워치독용)"""
    return _move["fb"] != 0 or _move["lr"] != 0


def set_speed(speed):
    """보행 속도(STEP_ITERATE) 변경. 범위 밖 값은 클램프."""
    try:
        speed = float(speed)
    except (TypeError, ValueError):
        return
    if speed != speed:  # NaN
        return
    speed = max(MIN_STEP_SPEED, min(MAX_STEP_SPEED, speed))
    send_cmd(f"S {speed:.4f}")


def function_stay_low():
    _move["fb"] = 0
    _move["lr"] = 0
    send_cmd("F 1")


def function_handshake():
    _move["fb"] = 0
    _move["lr"] = 0
    send_cmd("F 2")


def function_jump():
    _move["fb"] = 0
    _move["lr"] = 0
    send_cmd("F 3")


def function_stand():
    _move["fb"] = 0
    _move["lr"] = 0
    send_cmd("F 4")


# ==================== 자세(포즈) / 토크 — 동작(모션) 기능용 ====================

def pose(duration_ms, angles, ease=EASE_INOUT):
    """
    12개 서보를 duration_ms 동안 angles(0~180)로 보간 이동.
    ease: EASE_INOUT(코사인) / EASE_LINEAR / EASE_IN / EASE_OUT
    보간 자체는 ESP32의 5ms 루프가 수행하므로 파이썬 지연에 영향받지 않는다.
    """
    if len(angles) != NUM_SERVOS:
        raise ValueError(f"angles는 {NUM_SERVOS}개여야 합니다.")
    clamped = [max(0.0, min(180.0, float(a))) for a in angles]
    angle_str = " ".join(f"{a:.1f}" for a in clamped)
    ease = int(ease) if int(ease) in (EASE_INOUT, EASE_LINEAR, EASE_IN, EASE_OUT) else EASE_INOUT
    _move["fb"] = 0
    _move["lr"] = 0
    send_cmd(f"J {int(duration_ms)} {angle_str} {ease}")


def pose_servos(duration_ms, servo_angles):
    """
    일부 서보만 duration_ms 동안 부드럽게 이동. 나머지는 현재 위치를 유지한다.
    servo_angles: {서보 인덱스: 각도} (동작 편집 슬라이더 미리보기용 — K 커맨드)
    """
    pairs = []
    for idx, angle in servo_angles.items():
        idx = int(idx)
        if not 0 <= idx < NUM_SERVOS:
            raise ValueError(f"서보 인덱스는 0~{NUM_SERVOS - 1}이어야 합니다.")
        clamped = max(0.0, min(180.0, float(angle)))
        pairs.append(f"{idx} {clamped:.1f}")
    if not pairs:
        return
    _move["fb"] = 0
    _move["lr"] = 0
    send_cmd(f"K {int(duration_ms)} " + " ".join(pairs))


def pose_home(duration_ms=HOME_POSE_MS):
    """
    기준 자세(= 캘리브레이션 각도 ServoMiddleAngle)로 이동해 고정한다.
    IK로 계산하는 기립 자세(F 4)가 아니라 align_90.py와 같은 방식으로 각도를 그대로
    적용하므로, 캘리브레이션에 저장된 값이 곧 로봇이 취하는 자세가 된다.
    """
    pose(duration_ms, ServoMiddleAngle)


def read_pose(source="present"):
    """
    현재 자세 각도 12개를 읽는다.
    source="present": 서보에서 실측 위치 읽기 (토크 꺼서 손으로 잡은 자세 캡처 가능)
    source="goal":    ESP32가 마지막으로 명령한 목표 각도
    반환: 각도 리스트. ESP32 응답이 없으면 None.
    실측 읽기에서 일부 서보가 응답하지 않으면(펌웨어가 "?"로 표시) ServoReadError.
    (기존에는 펌웨어가 목표각으로 조용히 대체해 틀린 값이 키프레임에 섞였다)
    """
    if source == "present":
        reply = query("U", "POS")
    else:
        reply = query("V", "ANG")
    if reply is None:
        return None
    tokens = reply.split()
    if len(tokens) != NUM_SERVOS:
        return None
    angles = []
    failed = []
    for i, tok in enumerate(tokens):
        try:
            angles.append(max(0.0, min(180.0, float(tok))))
        except ValueError:
            angles.append(None)
            failed.append(i)
    if failed:
        raise ServoReadError(failed)
    return angles


def release_torque():
    """토크 해제 — 손으로 로봇 자세를 잡을 수 있게 된다"""
    _move["fb"] = 0
    _move["lr"] = 0
    send_cmd("T")
    print("[dog_cont] Torque release command sent.")


def enable_torque():
    """토크 재활성화 — 현재 자세로 고정"""
    _move["fb"] = 0
    _move["lr"] = 0
    send_cmd("E")
    print("[dog_cont] Torque enable command sent.")


# ==================== 캘리브레이션 ====================

def _valid_preset(values):
    """프리셋 1개가 쓸 수 있는 형태인지 (0~180 사이 숫자 NUM_SERVOS개)"""
    if not isinstance(values, list) or len(values) != NUM_SERVOS:
        return False
    try:
        return all(0 <= float(v) <= 180 for v in values)
    except (TypeError, ValueError):
        return False


def load_calibration():
    """
    calibration.json 로드. 사람이 직접 편집하는 파일이고 이 함수는 import 시점에
    실행되므로, 내용이 깨져 있어도 예외를 던지지 않고 기본값(90도)으로 되돌려
    서버가 뜨는 것을 보장한다.
    """
    global pin_mapping, ServoMiddleAngle
    if os.path.exists(CALIBRATION_FILE):
        try:
            with open(CALIBRATION_FILE, 'r') as f:
                calibration_data.update(json.load(f))
        except Exception as e:
            print(f"[dog_cont] Failed to load calibration: {e}")

    presets = calibration_data.get("presets")
    if not isinstance(presets, dict):
        presets = {}
    for key in ("1", "2", "3"):
        if not _valid_preset(presets.get(key)):
            print(f"[dog_cont] 프리셋 {key} 값이 잘못되어 90도로 초기화합니다.")
            presets[key] = [90] * NUM_SERVOS
    calibration_data["presets"] = presets

    active = str(calibration_data.get("active_preset", 1))
    if active not in presets:
        print(f"[dog_cont] active_preset({active})에 해당하는 프리셋이 없어 1번을 사용합니다.")
        active = "1"
    calibration_data["active_preset"] = int(active)

    # 0은 '미설정'을 뜻하던 옛 값. 범위를 벗어나면 기본 순서(1~12)로 되돌린다.
    try:
        pins = [int(p) for p in calibration_data.get("pin_mapping", [])]
    except (TypeError, ValueError):
        pins = []
    if len(pins) != NUM_SERVOS or not all(1 <= p <= 253 for p in pins):
        pins = list(range(1, NUM_SERVOS + 1))
    pin_mapping = pins
    calibration_data["pin_mapping"] = pins

    # 프리셋 리스트를 그대로 참조하면 별칭이 되어 다른 프리셋까지 오염된다 (복사본 사용)
    ServoMiddleAngle = [float(a) for a in presets[active]]
    print(f"[dog_cont] Calibration loaded. Active preset: {calibration_data['active_preset']}")


def save_calibration():
    try:
        with open(CALIBRATION_FILE, 'w') as f:
            json.dump(calibration_data, f, indent=4)
        print("[dog_cont] Calibration saved successfully.")
    except Exception as e:
        print(f"[dog_cont] Failed to save calibration: {e}")


def _fmt_angles(angles):
    return " ".join(f"{float(a):g}" for a in angles)


def send_initial_calibration():
    """연결 직후 핀 맵과 중간각을 ESP32에 동기화"""
    send_cmd("O " + " ".join(str(int(p)) for p in pin_mapping))
    time.sleep(0.05)
    send_cmd("A " + _fmt_angles(ServoMiddleAngle))
    time.sleep(0.05)


# 캘리브레이션 모드는 로봇을 기준 자세(= 캘리브레이션 각도)로 세워 두고, 슬라이더로 바꾼
# 값이 그 서보에 즉시 그대로 반영되게 한다. 즉 화면의 숫자 = 실제 서보 각도.
# (기존에는 ESP32의 "C 1"이 IK로 계산한 기립 자세를 유지했기 때문에, 슬라이더에 90이
#  떠 있어도 실제 서보는 전혀 다른 각도(예: 25.3도)로 가 있었다. align_90.py로 맞춘
#  기준과도 어긋나서, 캘리브레이션 페이지에 들어가기만 해도 로봇이 틀어졌다.)


def enter_calibration_mode():
    """기준 자세(캘리브레이션 각도)로 이동해 고정한다"""
    global calibrationMode
    calibrationMode = True
    pose_home()
    print("[dog_cont] Entered calibration mode.")


def exit_calibration_mode():
    """값을 저장하고 모드만 해제한다. 자세는 캘리브레이션 각도 그대로 유지."""
    global calibrationMode
    save_calibration()
    calibrationMode = False
    print("[dog_cont] Exited calibration mode.")


def update_calibration_angle(servo_id, angle):
    """중간각 1개 변경 -> 그 서보만 새 각도로 즉시 이동 (나머지는 현재 자세 유지)"""
    try:
        servo_id = int(servo_id)
        angle = round(max(0.0, min(180.0, float(angle))), 1)
    except (TypeError, ValueError):
        return
    if 0 <= servo_id < NUM_SERVOS:
        ServoMiddleAngle[servo_id] = angle
        calibration_data["presets"][str(calibration_data["active_preset"])][servo_id] = angle
        send_cmd("A " + _fmt_angles(ServoMiddleAngle))  # 보행 IK가 쓰는 기준값도 갱신
        if calibrationMode:
            pose_servos(CALIBRATION_ADJUST_MS, {servo_id: angle})


def update_pin_mapping(joint_id, new_pin):
    try:
        joint_id = int(joint_id)
        new_pin = int(new_pin)
    except (TypeError, ValueError):
        return
    # 254는 브로드캐스트 ID이므로 개별 서보 ID로 쓸 수 없다
    if 0 <= joint_id < NUM_SERVOS and 1 <= new_pin <= 253:
        pin_mapping[joint_id] = new_pin
        calibration_data["pin_mapping"][joint_id] = new_pin
        send_cmd(f"P {joint_id} {new_pin}")
        save_calibration()
        print(f"[dog_cont] Updated PIN mapping: Joint {joint_id} -> UART ID {new_pin}")


def save_to_preset(preset_id):
    if preset_id in [1, 2, 3]:
        calibration_data["presets"][str(preset_id)] = list(ServoMiddleAngle)
        calibration_data["active_preset"] = preset_id
        save_calibration()
        print(f"[dog_cont] Saved current angles to Preset {preset_id}")


def set_calibration_preset(preset_id):
    global ServoMiddleAngle
    if preset_id in [1, 2, 3]:
        calibration_data["active_preset"] = preset_id
        ServoMiddleAngle = list(calibration_data["presets"][str(preset_id)])
        send_cmd("A " + _fmt_angles(ServoMiddleAngle))
        if calibrationMode:
            pose_home()  # 새 프리셋 각도로 실제로 이동
        save_calibration()
        print(f"[dog_cont] Loaded Preset {preset_id}")


# ==================== 조명 / OLED ====================

def _clamp_int(v, lo, hi):
    try:
        v = int(float(v))
    except (TypeError, ValueError, OverflowError):
        return lo
    return max(lo, min(hi, v))


def lights_ctrl(pwmA, pwmB):
    send_cmd(f"L {_clamp_int(pwmA, 0, 255)} {_clamp_int(pwmB, 0, 255)}")


def rgb_light(led_id, r, g, b):
    send_cmd(f"R {_clamp_int(led_id, 0, 255)} {_clamp_int(r, 0, 255)} "
             f"{_clamp_int(g, 0, 255)} {_clamp_int(b, 0, 255)}")


def base_oled(line, text):
    """OLED 한 줄 표시. 텍스트는 출력 가능한 ASCII 21자(128px/6px)까지만."""
    line = _clamp_int(line, 1, 3)
    text = "".join(ch for ch in str(text) if 32 <= ord(ch) < 127)[:21]
    send_cmd(f"D {line} {text}")


# 모듈 import 시점에 파일의 캘리브레이션을 즉시 로드한다.
# (init() 없이 save_calibration()이 호출되는 경로가 생겨도
#  기본값(전부 90도)으로 실제 캘리브레이션 파일을 덮어쓰지 않도록 방지)
load_calibration()


if __name__ == '__main__':
    init()
    print("dog_cont 단독 테스트: 기립 -> 앞으로 3초 -> 정지 -> 토크 해제")
    function_stand()
    time.sleep(2)
    input_cmd(1, 0)
    time.sleep(3)
    input_cmd(0, 0)
    time.sleep(1)
    release_torque()
