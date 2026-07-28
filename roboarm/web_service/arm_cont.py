"""
PCA9685 서보 모터 제어 모듈
서보 4개 (채널 0: Base, 1: Shoulder, 2: Elbow, 3: Gripper)

하드웨어에 각도가 반영되는 경로는 슬루 필터 스레드(_filter_loop) 하나뿐이다.
외부(키보드/웹)는 목표 각도(target_angles)만 바꾸고, 필터가 매 틱 현재 각도를
목표 방향으로 최대 속도(max_speed_dps) 이하의 스텝으로만 이동시키며 서보에 쓴다.
"""
import time
import threading

try:
    from adafruit_servokit import ServoKit
    kit = ServoKit(channels=16)
    PCA9685_AVAILABLE = True
except Exception as e:
    print(f"[arm_cont] PCA9685 초기화 실패: {e}")
    print("[arm_cont] 서보 제어 비활성화 상태로 실행합니다.")
    kit = None
    PCA9685_AVAILABLE = False

# 서보 설정
NUM_SERVOS = 4
ANGLE_STEP = 5        # 키 입력 한 번당 목표 각도 변화량
MIN_ANGLE = 0         # 최소 각도
MAX_ANGLE = 180       # 최대 각도
INITIAL_ANGLES = [90, 180, 180, 180]  # 초기 자세: Base 90°, 나머지 180°

JOINTS = ['base', 'shoulder', 'elbow', 'gripper']

# 슬루 필터 설정 — 서보에 걸리는 유일한 속도 제한
FILTER_TICK = 0.02    # 필터 주기 (초, 50Hz)
max_speed_dps = 90.0  # 최대 회전 속도 (도/초). set_max_speed()로 변경

# 각도 상태: target은 외부에서 설정, current는 필터가 서보에 반영한 값
target_angles = [float(a) for a in INITIAL_ANGLES]
current_angles = [float(a) for a in INITIAL_ANGLES]

_lock = threading.Lock()
_filter_thread = None


def _clamp(angle):
    return max(MIN_ANGLE, min(MAX_ANGLE, float(angle)))


def _apply(channel):
    """실제 서보 하드웨어에 현재 각도를 쓴다 (_filter_loop / init_servos 전용)"""
    if PCA9685_AVAILABLE:
        kit.servo[channel].angle = current_angles[channel]


def set_max_speed(dps):
    """슬루 필터의 최대 회전 속도(도/초) 설정"""
    global max_speed_dps
    try:
        max_speed_dps = max(10.0, min(600.0, float(dps)))
    except (TypeError, ValueError):
        return
    print(f"[arm_cont] 최대 회전 속도 = {max_speed_dps}°/s")


def _filter_loop():
    """슬루 필터: 매 틱 current를 target 방향으로 속도 제한 스텝만큼만 이동"""
    while True:
        time.sleep(FILTER_TICK)
        max_step = max_speed_dps * FILTER_TICK
        with _lock:
            for ch in range(NUM_SERVOS):
                diff = target_angles[ch] - current_angles[ch]
                if diff == 0:
                    continue
                if abs(diff) <= max_step:
                    current_angles[ch] = target_angles[ch]
                else:
                    current_angles[ch] += max_step if diff > 0 else -max_step
                _apply(ch)


def init_servos():
    """서보를 초기 자세로 이동하고 슬루 필터 스레드 시작"""
    global _filter_thread
    with _lock:
        for ch in range(NUM_SERVOS):
            target_angles[ch] = float(INITIAL_ANGLES[ch])
            current_angles[ch] = float(INITIAL_ANGLES[ch])
            # 전원 인가 직후에는 서보의 실제 위치를 알 수 없으므로
            # 초기 자세 1회만 직접 쓴다. 이후 모든 반영은 _filter_loop 경유.
            _apply(ch)
    if _filter_thread is None:
        _filter_thread = threading.Thread(target=_filter_loop, daemon=True)
        _filter_thread.start()
    print(f"[arm_cont] 서보 초기화 완료: {INITIAL_ANGLES}, 최대 속도 {max_speed_dps}°/s")


def move_servo(channel, direction):
    """
    목표 각도를 ANGLE_STEP만큼 이동 (실제 이동 속도는 슬루 필터가 제한)
    channel: 서보 채널 (0~3)
    direction: 1(올리기) 또는 -1(내리기)
    """
    if channel < 0 or channel >= NUM_SERVOS:
        return
    with _lock:
        target_angles[channel] = _clamp(target_angles[channel] + ANGLE_STEP * direction)
        new_target = target_angles[channel]
    print(f"[arm_cont] servo[{channel}] ({JOINTS[channel]}) 목표 = {new_target}°")


def set_angle(channel, angle):
    """목표 각도를 절대값으로 설정 (실제 이동 속도는 슬루 필터가 제한)"""
    if channel < 0 or channel >= NUM_SERVOS:
        return
    try:
        clamped = _clamp(angle)
    except (TypeError, ValueError):
        return
    with _lock:
        target_angles[channel] = clamped


def get_angles():
    """현재(서보에 실제 반영된) 각도 반환"""
    with _lock:
        return list(current_angles)


def get_targets():
    """현재 목표 각도 반환"""
    with _lock:
        return list(target_angles)


if __name__ == '__main__':
    init_servos()
    print("서보 테스트: 각 서보를 초기 자세에서 -60° 이동 후 복귀 (슬루 필터 적용)")
    for ch in range(NUM_SERVOS):
        set_angle(ch, INITIAL_ANGLES[ch] - 60)
        time.sleep(1.5)
        set_angle(ch, INITIAL_ANGLES[ch])
        time.sleep(1.5)
    print("테스트 완료")
