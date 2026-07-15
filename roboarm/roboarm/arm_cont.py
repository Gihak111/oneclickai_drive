"""
PCA9685 서보 모터 제어 모듈
서보 4개 (채널 0: Base, 1: Shoulder, 2: Elbow, 3: Gripper)
"""
import time

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
ANGLE_STEP = 5        # 한 번 누를 때 변화할 각도
MIN_ANGLE = 0         # 최소 각도
MAX_ANGLE = 180       # 최대 각도
INITIAL_ANGLE = 90    # 초기 각도

JOINTS = ['base', 'shoulder', 'elbow', 'gripper']

# 각 서보의 현재 각도 저장
servo_angles = [INITIAL_ANGLE] * NUM_SERVOS


def init_servos():
    """서보를 초기 위치(90도)로 이동"""
    if not PCA9685_AVAILABLE:
        return
    for i in range(NUM_SERVOS):
        servo_angles[i] = INITIAL_ANGLE
        kit.servo[i].angle = INITIAL_ANGLE
    print(f"[arm_cont] 서보 초기화 완료: {servo_angles}")


def move_servo(channel, direction):
    """
    서보를 지정 방향으로 ANGLE_STEP만큼 이동
    channel: 서보 채널 (0~3)
    direction: 1(올리기) 또는 -1(내리기)
    """
    if channel < 0 or channel >= NUM_SERVOS:
        return

    new_angle = servo_angles[channel] + (ANGLE_STEP * direction)
    new_angle = max(MIN_ANGLE, min(MAX_ANGLE, new_angle))
    servo_angles[channel] = new_angle
    if PCA9685_AVAILABLE:
        kit.servo[channel].angle = new_angle
    print(f"[arm_cont] servo[{channel}] ({JOINTS[channel]}) = {new_angle}°")


def set_angle(channel, angle):
    """서보를 절대 각도로 설정"""
    if channel < 0 or channel >= NUM_SERVOS:
        return

    new_angle = max(MIN_ANGLE, min(MAX_ANGLE, float(angle)))
    servo_angles[channel] = new_angle
    if PCA9685_AVAILABLE:
        kit.servo[channel].angle = new_angle
    print(f"[arm_cont] servo[{channel}] ({JOINTS[channel]}) = {new_angle}°")


def get_angles():
    """현재 모든 서보 각도 반환"""
    return list(servo_angles)


if __name__ == '__main__':
    init_servos()
    print("서보 테스트: 각 서보를 0° → 90° → 180° → 90° 로 이동")
    for ch in range(NUM_SERVOS):
        for angle in [0, 90, 180, 90]:
            set_angle(ch, angle)
            print(f"  servo[{ch}] ({JOINTS[ch]}) = {angle}°")
            time.sleep(0.5)
    print("테스트 완료")
