import time
import os


# fps 계산용
def calc_fps(last_time):
    t_current = time.time()
    fps = round(1/(t_current-last_time + 10e-8),1)
    return fps


# 이미지 저장 폴더 생성
def makeImgDir():
    if not os.path.exists('image'):
        os.makedirs('image')


if __name__ == '__main__':
    makeImgDir()
