"""
자율주행 모드 패키지 — autonomous_examples 를 로봇개에 맞게 옮긴 것.

폴더 구성 (예제와 동일한 파이프라인):
  camera_capture.py   프레임 전처리(실습 포인트) + 라벨별 학습 이미지 저장
  auto_cont.py        제어 루프: 모델 예측 -> 이동 명령, 저장, 안전장치
  model/model.py      학습 스크립트 (image/ 폴더의 이미지로 CNN 학습 -> keras_model.tflite)
  model/labels.txt    모델 출력 인덱스 -> 라벨 이름
  model/keras_model.tflite  학습된 모델 (처음엔 예제 모델이 들어 있음 — 직접 학습해서 교체)
  image/              저장된 학습 이미지 (go/left/right/brake), 실행 시 자동 생성

사용 흐름:
  1. 웹 /autonomous 페이지에서 저장 ON -> 방향키/브레이크를 누르고 있는 동안 그 라벨로 저장됨
  2. PC에서 python model/model.py 실행 -> keras_model.tflite 생성
  3. 페이지에서 "모델 다시 불러오기" -> 자율주행 시작
"""
