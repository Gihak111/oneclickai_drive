# autonomous/ — 자율주행 모드

`autonomous_examples`(RC카용)를 로봇개에 맞게 옮긴 것입니다. 파이프라인은 같습니다:

```
1. 데이터 모으기   웹 /autonomous → 저장 ON → 방향키로 코스를 수동 주행
                    → 버튼을 누르고 있는 동안만 image/go, left, right, brake 에 64x64 이미지 저장
                      (누르는 순간 1장 바로, 계속 누르면 실시간으로 계속. 손을 떼면 저장 안 함)
2. 학습하기        PC: python model/model.py  →  model/keras_model.tflite, labels.txt
3. 자율주행        웹 /autonomous → 모델 다시 불러오기 → 자율주행 시작 (Z)
```

## 예제와 달라진 점

| 예제 (RC카, 별도 프로그램) | 로봇개 (웹 서버 안의 세 번째 모드) |
|---|---|
| `main.py` 가 카메라·키보드·모터를 직접 잡음 | 카메라는 `camera_stream`, 시리얼은 `dog_cont` 가 이미 갖고 있어 웹 서버 안에서 동작 |
| `keyboard_cont.py` (pynput 로컬 키보드) | 브라우저 키 입력 → 기존 `key_cont` / `dog_cont` |
| `motor_cont.drive(go, left, right, ...)` | `auto_cont.ACTION_TO_MOVE` → `dog_cont.input_cmd(fb, lr)` |
| `camera_capture.py` 가 카메라를 열고 전처리·저장 | `camera_capture.py` 는 전처리·저장만 (실습 TODO 는 그대로) |
| `cv2.imshow` 로 로컬 화면 표시 | 웹 페이지의 "모델 입력 미리보기" |
| 웹서비스를 끄고 실행 | 끌 필요 없음 |

키는 예제와 같습니다 (이 페이지에서는 WASD 가 아니라 **방향키**로 운전합니다):

| 키 | 동작 |
|---|---|
| ↑ ← → ↓ | 수동 주행 (누르는 동안) |
| S / A | 저장 ON / OFF |
| Z / X | 자율주행 시작 / 정지 |
| B (누르는 동안) | 브레이크 — 저장 라벨이 `brake` 가 되고, 자율주행 중이면 로봇을 세움 |

## 안전장치

- 자율주행 페이지가 1초마다 keep-alive 를 보냅니다. 탭을 닫거나 WiFi 가 끊겨
  `HOLD_TIMEOUT`(기본 3초) 동안 안 오면 자율주행과 저장이 스스로 멈춥니다.
- 자율주행 중 방향키를 누르거나, 동작을 재생하거나, 캘리브레이션 페이지로 가면
  자율주행이 먼저 정지됩니다 (수동 개입 우선).
- 제어 루프가 죽어도 기존 keep-alive 워치독이 로봇을 세웁니다.

## 설정

`robot_dog/config.py` 의 `자율주행 설정` 섹션:
`AUTO_CONTROL_LOOP_SLEEP`, `AUTO_CAPTURE_FREQ`, `AUTO_CROP_TOP`(위쪽 잘라내기), `AUTO_MODEL_INPUT` 등.

## 라즈베리파이 준비

```
sudo apt install -y python3-tflite-runtime      # 예측용 (가벼움)
# 또는  pip install tflite-runtime --break-system-packages
```

학습(`model/model.py`)은 tensorflow 가 필요하므로 보통 PC 에서 합니다.
`image/` 폴더를 PC 로 복사해 학습한 뒤, 생성된 `keras_model.tflite` 와 `labels.txt` 를
라즈베리파이의 이 폴더(`model/`)에 다시 복사하세요.

처음에는 예제(RC카)로 학습된 `keras_model.tflite` 가 들어 있습니다. 파이프라인 확인용이며,
로봇개의 카메라 높이·코스와 맞지 않으므로 반드시 직접 데이터를 모아 다시 학습하세요.
