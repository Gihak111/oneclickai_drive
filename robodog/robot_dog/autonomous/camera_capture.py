"""
자율주행용 이미지 전처리 + 학습 데이터 저장 (autonomous_examples/camera_capture.py에 해당)

예제는 이 파일이 카메라를 직접 열었지만, 로봇개는 camera_stream이 카메라를 갖고 있고
웹 스트리밍과 공유하므로 여기서는 "받은 프레임을 전처리하고 저장"만 한다.

  preprocess()       카메라 프레임 -> (화면용 프레임, 모델 입력용 64x64)   <- 실습 포인트
  label_for_move()   지금 누르고 있는 이동 명령 -> 학습 라벨(go/left/right/brake) 또는 None
  save_image()       image/<라벨>/ 에 저장
"""
import os
from datetime import datetime

import cv2

from config import AUTO_IMAGE_DIR, AUTO_VIEW_SIZE, AUTO_CROP_TOP, AUTO_MODEL_INPUT

# 저장 폴더 이름 = 학습 라벨. model/model.py 의 LABELS 와 같은 이름/순서다.
TRAIN_LABELS = ("go", "left", "right", "brake")


def make_image_dirs():
    for name in TRAIN_LABELS:
        os.makedirs(os.path.join(AUTO_IMAGE_DIR, name), exist_ok=True)


def count_images():
    """
    라벨별로 지금까지 모인 이미지 장수 (이전에 저장해 둔 것 포함).
    학습 전에 "어느 라벨이 부족한지" 보려고 쓴다 — 한쪽만 많으면 그쪽으로 치우쳐 학습된다.
    """
    counts = {}
    for name in TRAIN_LABELS:
        folder = os.path.join(AUTO_IMAGE_DIR, name)
        try:
            counts[name] = sum(1 for f in os.listdir(folder) if f.endswith(".jpg"))
        except OSError:
            counts[name] = 0   # 폴더가 아직 없음
    return counts


def preprocess(frame):
    """
    카메라 프레임(BGR) -> (화면용 프레임, 모델 입력용 프레임 BGR uint8)
    저장하는 이미지와 예측에 쓰는 이미지가 반드시 같은 전처리를 거치도록 한 곳에 둔다.

    TODO: 이미지를 어떻게 바꿔서 처리할까? (예제와 같은 실습 포인트)
      - 위쪽을 얼마나 잘라낼지 (config.AUTO_CROP_TOP): 천장/하늘처럼 주행과 무관한 부분 제거
      - 색/밝기 보정, 흑백 변환 등
    ※ 여기를 바꾸면 기존에 저장한 이미지와 달라지므로 다시 저장하고 다시 학습해야 한다.
    ※ 상하/좌우 뒤집기는 config.CAMERA_FLIP 이 이미 처리하므로 여기서 또 하지 않는다.
    """
    frame = cv2.resize(frame, (AUTO_VIEW_SIZE, AUTO_VIEW_SIZE))
    frame = frame[AUTO_CROP_TOP:, :]
    frame = cv2.resize(frame, (AUTO_VIEW_SIZE, AUTO_VIEW_SIZE))
    display = frame
    model_input = cv2.resize(frame, AUTO_MODEL_INPUT)
    return display, model_input


def label_for_move(fb, lr, brake=False):
    """
    누르고 있는 이동 명령 -> 학습 라벨. 우선순위는 예제와 같다 (brake > left > right > go).
    학습 라벨이 아닌 입력(아무것도 안 누름/후진/제자리 회전)은 None — 저장하지 않는다.
    """
    if brake:
        return "brake"
    if fb == 1 and lr == -1:
        return "left"
    if fb == 1 and lr == 1:
        return "right"
    if fb == 1 and lr == 0:
        return "go"
    return None


def save_image(model_input, label, fb, lr, brake, frame_cnt):
    """
    64x64 이미지를 image/<label>/ 에 저장하고 파일 경로를 돌려준다.
    파일 이름은 예제와 같은 규칙: <go><left><right><brake><back>_<프레임번호>_<분초밀리초>.jpg
    """
    go = 1 if fb == 1 else 0
    back = 1 if fb == -1 else 0
    left = 1 if lr == -1 else 0
    right = 1 if lr == 1 else 0
    stamp = datetime.now().strftime("%M%S%f")[:-3]
    name = f"{go}{left}{right}{1 if brake else 0}{back}_{frame_cnt}_{stamp}.jpg"
    path = os.path.join(AUTO_IMAGE_DIR, label, name)
    cv2.imwrite(path, model_input)
    return path
