import cv2
from picamera2 import Picamera2
import numpy as np


def capture_img():
    # 카메라 이미지 캡처
    picam2 = Picamera2()
    main = {"format": 'RGB888', "size": (1332, 990)}
    picam2.configure(picam2.create_preview_configuration(main=main))
    picam2.start()


    while True:
        # 카메라 이미지 캡쳐
        frame = picam2.capture_array()

        # 이미지를 어떻게 바꿔서 처리할까?
        # TODO2: 상하반전
        
        # TODO3: 이미지 크기 변경 (512, 512)

        # TODO4: 이미지 자르기 이미지 상단(윗부분) 50% 삭제
        
        # TODO5: 이미지 저장

        # 화면에 띄울 이미지 선정 (show_image)
        cv2.imshow('Frame', frame)
        cv2.waitKey(200)


# TODO1: 함수 실행
if __name__ == '__main__':
    capture_img()