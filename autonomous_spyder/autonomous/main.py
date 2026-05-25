import tensorflow as tf
import numpy as np
import threading, time
import subprocess
import util
import motor_cont
from keyboard_cont import KeyboardController
from camera_capture import CameraCapture
from config import MODEL_PATH, CONTROL_LOOP_SLEEP
# import parking



# 학습된 모델 불러오기 (tflite 모델)
model = tf.lite.Interpreter(model_path=MODEL_PATH)
model.allocate_tensors()
input_details = model.get_input_details()
output_details = model.get_output_details()

# 이미지 저장 폴더 없으면 폴더 생성
util.makeImgDir()

# 키보드 입력 컨트롤러 인스턴스 생성
key = KeyboardController()

# 카메라 캡처 인스턴스 생성
camera = CameraCapture(key)

# 메인 루프
def autonomous_control_loop():
    """자율주행 제어 메인 루프: 이미지 예측 및 모터 제어"""
    t0 = 0
    predicted_action = None


    while True:
        time.sleep(CONTROL_LOOP_SLEEP)

        # 자율주행 모드
        if key.manual == 0:

            # 카메라에서 전처리된 이미지 가져오기
            image = camera.get_pred_image()
            if image is None:
                continue

            # RGB를 BGR로 변환 (OpenCV 형식)
            image_bgr = image[:,:,:,::-1]

            # 모델 예측
            model.set_tensor(input_details[0]['index'], image_bgr)
            model.invoke()
            prediction_probs = model.get_tensor(output_details[0]['index'])

            # 예측 확률 출력: 모델이 0을 출력하면 직진, 1은 좌회전, 2는 우회전, 3은 정지
            ACTION_LABELS = ['go', 'left', 'right', 'brake']
            prob_str = '  '.join([f'{ACTION_LABELS[i]}: {round(prediction_probs[0][i], 2)}'
                                   for i in range(len(prediction_probs[0]))])
            print(prob_str)

            # 가장 높은 확률의 행동 선택
            predicted_action = np.argmax(prediction_probs, axis=1)[0]

            # 예측된 행동에 따라 키보드 플래그 설정
            if predicted_action == 0:  # 직진
                key.go_flag = 1
                key.left_flag = 0
                key.right_flag = 0
                key.back_flag = 0
            elif predicted_action == 1:  # 좌회전
                key.go_flag = 1
                key.left_flag = 1
                key.right_flag = 0
                key.back_flag = 0
            elif predicted_action == 2:  # 우회전
                key.go_flag = 1
                key.left_flag = 0
                key.right_flag = 1
                key.back_flag = 0
            elif predicted_action == 3:  # 정지
                key.go_flag = 0
                key.left_flag = 0
                key.right_flag = 0
                key.back_flag = 0
            elif predicted_action == 4: # 주차
                # 주차 모드에 진입하면 따로 주차파일 만들어서 실행
                # parking.parking()
                break

        # 모터 동작 수행
        motor_cont.drive(shot_flag=key.shot_flag, go_flag=key.go_flag, left_flag=key.left_flag, right_flag=key.right_flag, brake_flag=key.brake_flag, back_flag=key.back_flag)

        # FPS 계산 및 출력
        fps = util.calc_fps(t0)
        t0 = time.time()
        print(f"fps: {fps}")




if __name__ == "__main__":
    # 키보드 입력 활성화
    getkey_thread = threading.Thread(target=key.getkeyboard)
    getkey_thread.start()
    print('keyboard on!')

    # 자율주행 메인 루프 활성화
    drive_thread = threading.Thread(target=autonomous_control_loop)
    drive_thread.start()
    print('Motor on!')

    # 카메라 활성화
    main_thread = threading.Thread(target=camera.capture_img)
    main_thread.start()
    print('main on!')

