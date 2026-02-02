import time
import threading
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

# --- 1. 하드웨어 설정 ---
i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = 50

# 서보 객체 (Pin 0~15)
servos = [servo.Servo(pca.channels[i], min_pulse=500, max_pulse=2500) for i in range(16)]

# --- 2. 상태 변수 ---
# 핀 매핑: Base=0, Shoulder=1, Elbow=2, Gripper=3
JOINT_MAP = {'base': 0, 'shoulder': 1, 'elbow': 2, 'gripper': 3}

current_angles = {'base': 90.0, 'shoulder': 90.0, 'elbow': 90.0, 'gripper': 90.0}
target_angles = current_angles.copy()

# 파라미터 (외부 제어용)
move_step = 2.0  # 한 번 키를 눌렀을 때(또는 루프당) 이동할 각도 크기


def set_params(step_size=2.0):
    """외부(API)에서 감도 조절"""
    global move_step
    move_step = float(step_size)
    print(f"[Arm] Speed set to: {move_step}")


def get_servo(joint=None):
    """현재 각도 조회 (전체 또는 특정 조인트)"""
    if joint is None:
        return current_angles.copy()
    return current_angles.get(joint)


def update_target(joint, delta):
    """목표 각도 업데이트 (delta만큼 증감)"""
    if joint in target_angles:
        new_angle = target_angles[joint] + delta
        # 안전 범위 (0~180)
        target_angles[joint] = max(0, min(180, new_angle))
        print(f"[Arm] delta update {joint}: {current_angles[joint]:.1f} -> {target_angles[joint]:.1f}")


def set_target_absolute(joint, angle):
    """목표 각도 절대값 설정 (그리퍼 등)"""
    if joint in target_angles:
        target_angles[joint] = max(0, min(180, angle))
        print(f"[Arm] absolute set {joint}: {current_angles[joint]:.1f} -> {target_angles[joint]:.1f}")


# --- 3. 백그라운드 스무딩 스레드 ---
def _servo_loop():
    while True:
        for name, pin in JOINT_MAP.items():
            target = target_angles[name]
            current = current_angles[name]

            diff = target - current

            # 스무딩: 차이가 크면 조금씩 이동
            if abs(diff) > 0.5:
                # move_step보다는 작게, 부드럽게 따라가도록 고정 step 사용
                step = 1.0 if diff > 0 else -1.0
                current_angles[name] += step
            else:
                current_angles[name] = target

            # 하드웨어 명령
            servos[pin].angle = current_angles[name]

        time.sleep(0.01)  # 100Hz


# 모듈 로드 시 스레드 자동 시작
threading.Thread(target=_servo_loop, daemon=True).start()
