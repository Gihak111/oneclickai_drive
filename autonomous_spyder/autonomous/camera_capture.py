import cv2
from picamera2 import Picamera2
import numpy as np
import os
import time
import util
from datetime import datetime
from config import CAPTURE_FREQ


class CameraCapture:
    def __init__(self, keyboard_controller):
        self.key = keyboard_controller
        self.pred_image = None
        self.show_image = None
        self.save_cnt = 0
        self.frame_cnt = 0
        self.t0 = 0
        self.capture_freq = CAPTURE_FREQ

    def get_pred_image(self):
        """학습에 사용할 전처리된 이미지 반환"""
        return self.pred_image

    def get_show_image(self):
        """화면에 표시할 이미지 반환"""
        return self.show_image

    def capture_img(self):
        """카메라 이미지 캡처 및 저장"""
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
                frame = frame[200:,:]  # 위쪽 200 픽셀 제거

                # 화면에 띄울 이미지 선정 (show_image)
                frame = cv2.resize(frame, (512, 512))

                # 상태 정보를 표시할 이미지 복사본 생성
                display_frame = frame.copy()

                # 자율주행 모드 상태 표시
                mode_text = "AUTO" if self.key.manual == 0 else "MANUAL"
                mode_color = (0, 255, 0) if self.key.manual == 0 else (255, 255, 255)
                cv2.putText(display_frame, mode_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, mode_color, 2)

                # 저장 모드 상태 표시
                save_text = "SAVING" if self.key.save_flag == 1 else "NOT SAVING"
                save_color = (0, 0, 255) if self.key.save_flag == 1 else (128, 128, 128)
                cv2.putText(display_frame, save_text, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, save_color, 2)

                self.show_image = display_frame
                cv2.imshow('Frame', self.show_image)
                cv2.waitKey(40)

                # 모델에 맞게 이미지 크기 조절
                frame = cv2.resize(frame, (64, 64))

                # 저장할 이미지 선정 (pred_image)
                save_image = frame

                # 학습 전 이미지 전처리
                frame = np.asarray(frame, dtype=np.float32).reshape(1, 64, 64, 3)
                frame = (frame / 127.5) - 1

                # 학습에 사용할 이미지, 저장되는 이미지 선정 (pred_image)
                self.pred_image = frame

                # 프레임 카운트
                self.frame_cnt += 1

                # 이미지 저장 간격 조절
                if self.frame_cnt % self.capture_freq == 0 and self.key.save_flag == 1:
                    formatted_time = datetime.now().strftime("%M%S%f")[:-3]

                    # 이미지 저장위치: flag에 따라 다르게 저장
                    if self.key.brake_flag == 1:
                        directory = 'image' + os.sep + 'brake'
                    elif (self.key.go_flag == 1) and (self.key.left_flag == 1) and (self.key.right_flag == 0):
                        directory = 'image' + os.sep + 'left'
                    elif (self.key.go_flag == 1) and (self.key.left_flag == 0) and (self.key.right_flag == 1):
                        directory = 'image' + os.sep + 'right'
                    elif (self.key.go_flag == 1) and (self.key.left_flag == 0) and (self.key.right_flag == 0):
                        directory = 'image' + os.sep + 'go'
                    elif self.key.parking_flag == 1:
                        directory = 'image' + os.sep + 'parking'
                    else:
                        directory = 'image' + os.sep + 'other'

                    # 이미지 파일 이름
                    file_name = f"{directory}/{self.key.go_flag}{self.key.left_flag}{self.key.right_flag}{self.key.brake_flag}{self.key.back_flag}_{self.frame_cnt}_{formatted_time}.jpg"

                    # 저장
                    cv2.imwrite(file_name, save_image)
                    self.save_cnt += 1

                    # fps 계산
                    fps = util.calc_fps(self.t0)
                    self.t0 = time.time()
                    print(f"Image saved as {file_name}, fps: {fps},  cnt : {self.save_cnt}")

        except Exception as error:
            print('camera_capture 함수에 문제가 발생했습니다!')
            print(error)
