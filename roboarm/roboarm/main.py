import threading, time
import util
import arm_cont
from keyboard_cont import KeyboardController
from camera_capture import CameraCapture
from config import CONTROL_LOOP_SLEEP


# 이미지 저장 폴더 없으면 폴더 생성
util.makeImgDir()

# 키보드 입력 컨트롤러 인스턴스 생성
key = KeyboardController()

# 카메라 캡처 인스턴스 생성
camera = CameraCapture(key)

# PCA9685 서보 모터 초기화
arm_cont.init_servos()


# 메인 루프
def arm_control_loop():
    """로봇팔 제어 메인 루프: 키 입력에 따라 서보 이동"""
    while True:
        time.sleep(CONTROL_LOOP_SLEEP)

        # ESC 입력 시 종료
        if key.exit_flag == 1:
            break

        # 서보 동작 수행
        if key.servo_channel >= 0:
            arm_cont.move_servo(key.servo_channel, key.servo_direction)


if __name__ == "__main__":

    # 키보드 입력 활성화
    getkey_thread = threading.Thread(target=key.getkeyboard)
    getkey_thread.start()
    print('keyboard on!')

    # 로봇팔 제어 루프 활성화
    arm_thread = threading.Thread(target=arm_control_loop)
    arm_thread.start()
    print('Arm on!')

    # 카메라 활성화
    main_thread = threading.Thread(target=camera.capture_img)
    main_thread.start()
    print('main on!')
