import tensorflow as tf
import cv2
from pynput import keyboard
from picamera2 import Picamera2
import numpy as np
import os
import threading
import time
import motor_cont
import util
from datetime import datetime
from keyboard_cont import KeyboardController
# import parking

# 학습된 모델 불러오기
model = tf.lite.Interpreter(model_path=".//model//keras_model.tflite")
model.allocate_tensors()
input_details = model.get_input_details()
output_details = model.get_output_details()

# 폴더 없으면 폴더 생성
util.makeImgDir()

# 키보드 입력 받는 함수
key = KeyboardController()

# 글로벌 파라미터2: 저장 할 이미지
pred_image = None

# 카메라 이미지 캡처 및 저장
def capture_img():
    global pred_image, show_image
    save_cnt = 0
    frame_cnt = 0
    t0 = 0



    try:
        picam2 = Picamera2()
        picam2.configure(picam2.create_preview_configuration(main={"format": 'RGB888', "size": (1332, 990)}))
        picam2.start()

        while True:             
            # 카메라 이미지 캡쳐
            frame = picam2.capture_array()
            frame = cv2.flip(frame, -1)
            frame = cv2.resize(frame, (512, 512))

            # TODO: 이미지를 어떻게 바꿔서 처리할까?
            frame = frame[200:,:]
            # frame = ....
            #

            # 화면에 띄울 이미지 선정 (show_image)
            frame = cv2.resize(frame, (512, 512))
            show_image = frame
            cv2.imshow('Frame', show_image)
            cv2.waitKey(40)

            # 모델에 맞게 이미지 크기 조절
            frame = cv2.resize(frame, (64, 64))
            
            # 저장할 이미지 선정 (pred_image)
            save_image = frame

            # # 학습 전 이미지 전처리
            frame = np.asarray(frame, dtype=np.float32).reshape(1, 64, 64, 3) #(1,224,224,3)
            frame = (frame / 127.5) - 1

            # 학습에 사용할 이미지, 저장되는 이미지 선정 (pred_image)
            pred_image = frame

            # 이미지 저장 간격 조절 : 최대 frame_cnt % 10 == 0 의 의미는 10장중에 1장만 저장하겠다는 뜻
            frame_cnt+=1
            capture_freq = 4

            # 이미지 저장
            if frame_cnt%capture_freq==0 and key.save_flag == 1:
                formatted_time = datetime.now().strftime("%M%S%f")[:-3]  # Remove the last 3 digits to get milliseconds

                # 이미지 저장위치 
                if key.brake_flag == 1:
                    directory = 'image' + os.sep + 'brake'
                elif (key.go_flag == 1) and (key.left_flag == 1) and (key.right_flag == 0):
                    directory = 'image' + os.sep + 'left'
                elif (key.go_flag == 1) and (key.left_flag == 0) and (key.right_flag == 1):
                    directory = 'image' + os.sep + 'right'
                elif (key.go_flag == 1) and (key.left_flag == 0) and (key.right_flag == 0):
                    directory = 'image' + os.sep + 'go'
                elif key.parking_flag == 1:
                    directory = 'image' + os.sep + 'parking'
                else:
                    directory = 'image' + os.sep + 'other'

                # 이미지 파일 이름
                file_name = f"{directory}/{key.go_flag}{key.left_flag}{key.right_flag}{key.brake_flag}{key.back_flag}_{frame_cnt}_{formatted_time}.jpg"
                
                # 저장
                cv2.imwrite(file_name, save_image)
                save_cnt += 1
                
                # fps 계산 
                fps = util.calc_fps(t0)
                t0 = time.time() # fps 계산용
                print(f"Image saved as {file_name}, fps: {fps},  cnt : {save_cnt}")
            else :
                pass

    except Exception as error:
        print('camera_capture 함수에 문제가 발생했습니다!')
        print(error)
        pass






def drive_mode():
    global pred_image
    t0 = 0

    while True:
        time.sleep(0.08)
        if pred_image is None:
            pass
        else:
            pred_image = pred_image[:,:,:,::-1]
            model.set_tensor(input_details[0]['index'], pred_image)
            model.invoke()
            prediction = model.get_tensor(output_details[0]['index'])
            
            print('go: ', str(round(prediction[0][0],2)), '  left:', str(round(prediction[0][1],2)), '   right:', str(round(prediction[0][2],2)))
            #print('go: ', str(round(prediction[0][0],2)), '  left:', str(round(prediction[0][1],2)), '   right:', str(round(prediction[0][2],2)), '   brk:',str(round(prediction[0][3],2)))
            prediction = np.argmax((prediction),axis=1)
            #prediction = 0
            pass

        # 자율주행 모드
        if key.manual == 0 :
            if prediction == 0 :  # 직진
                key.go_flag = 1
                key.left_flag = 0
                key.right_flag = 0
                key.back_flag = 0
            elif prediction == 1 :  # 좌회전
                key.go_flag = 1
                key.left_flag = 1
                key.right_flag = 0
                key.back_flag = 0
            elif prediction == 2 :  # 우회전
                key.go_flag = 1
                key.left_flag = 0
                key.right_flag = 1
                key.back_flag = 0
            elif prediction == 3 :  # 정지
                key.go_flag = 0
                key.left_flag = 0
                key.right_flag = 0
                key.back_flag = 0
            elif prediction == 4: # 주차
                # 주차 모드에 진입하면 따로 주차파일 만들어서 실행
                # parking.parking()
                break
                
        else :
            None

        # 모터 동작 수행
        motor_cont.drive(key.go_flag, key.left_flag, key.right_flag, key.brake_flag, key.back_flag)

        fps = util.calc_fps(t0)
        t0 = time.time() # fps 계산용
        print(f"fps: {fps}")





if __name__ == "__main__":
    getkey_thread = threading.Thread(target=key.getkeyboard)
    getkey_thread.start()
    print('keyboard on!')

    drive_thread = threading.Thread(target=drive_mode)
    drive_thread.start()
    print('Motor on!')

    main_thread = threading.Thread(target=capture_img)
    main_thread.start()
    print('main on!')
