import cv2
from picamera2 import Picamera2
import time
import util
from datetime import datetime
from config import CAPTURE_FREQ


class CameraCapture:
    def __init__(self, keyboard_controller):
        self.key = keyboard_controller
        self.show_image = None
        self.save_cnt = 0
        self.frame_cnt = 0
        self.t0 = 0
        self.capture_freq = CAPTURE_FREQ

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

                # 상태 정보를 표시할 이미지 복사본 생성
                display_frame = frame.copy()

                # 저장 모드 상태 표시
                save_text = "SAVING" if self.key.save_flag == 1 else "NOT SAVING"
                save_color = (0, 0, 255) if self.key.save_flag == 1 else (128, 128, 128)  # 빨간색(SAVING) 또는 회색(NOT SAVING)
                cv2.putText(display_frame, save_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, save_color, 2)

                self.show_image = display_frame
                cv2.imshow('Frame', self.show_image)
                cv2.waitKey(40)

                # 프레임 카운트: 몇번의 프레임이 지나갔는지 카운트
                self.frame_cnt += 1

                # 이미지 저장 간격 조절 : capture_freq 프레임 중 1장만 저장
                if self.frame_cnt % self.capture_freq == 0 and self.key.save_flag == 1:
                    formatted_time = datetime.now().strftime("%M%S%f")[:-3]  # Remove the last 3 digits to get milliseconds

                    # 이미지 파일 이름 (상태 글자가 없는 원본 프레임 저장)
                    file_name = f"image/{self.frame_cnt}_{formatted_time}.jpg"

                    # 저장
                    cv2.imwrite(file_name, frame)
                    self.save_cnt += 1

                    # fps 계산
                    fps = util.calc_fps(self.t0)
                    self.t0 = time.time() # fps 계산용
                    print(f"Image saved as {file_name}, fps: {fps},  cnt : {self.save_cnt}")

        except Exception as error:
            print('camera_capture 함수에 문제가 발생했습니다!')
            print(error)
