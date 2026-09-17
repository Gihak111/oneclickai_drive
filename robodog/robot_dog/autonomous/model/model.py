"""
자율주행 모델 학습 스크립트 (autonomous_examples/model/model.py 에 해당)

image/<라벨>/ 에 저장된 64x64 이미지로 작은 CNN 을 학습하고 keras_model.tflite 로 내보낸다.
보통 라즈베리파이가 아니라 PC 에서 돌린다 (image/ 폴더를 복사해 오거나 공유해서).

  실행:  python model.py            (이 폴더에서)
  필요:  pip install tensorflow scikit-learn matplotlib opencv-python numpy
         (tflite 변환이 실패하면: pip install flatbuffers==2.0)

결과:  keras_model.tflite, labels.txt, training_result.png  (이 폴더에 생성)
       -> 라즈베리파이의 robot_dog/autonomous/model/ 에 복사한 뒤
          웹 /autonomous 페이지에서 "모델 다시 불러오기"
"""
import os
import sys

import cv2
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow.keras import layers
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import util  # noqa: E402  (이 폴더의 util.py)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "..", "image")
MODEL_OUT = os.path.join(BASE_DIR, "keras_model.tflite")
LABELS_OUT = os.path.join(BASE_DIR, "labels.txt")
PLOT_OUT = os.path.join(BASE_DIR, "training_result.png")

# 라벨 순서 = 모델 출력 인덱스. image/ 의 폴더 이름과 같아야 하고,
# 학습이 끝나면 같은 순서로 labels.txt 를 써서 로봇 쪽(auto_cont)이 읽게 한다.
LABELS = ["go", "left", "right", "brake"]
INPUT_SHAPE = (64, 64, 3)   # config.AUTO_MODEL_INPUT 과 같아야 한다

util.deleteImg(IMAGE_DIR)  # 1KB 미만의 깨진 파일 삭제

# ==================== 데이터 읽기 ====================
data = []
labels = []
for idx, name in enumerate(LABELS):
    folder = os.path.join(IMAGE_DIR, name)
    if not os.path.isdir(folder):
        print(f"[경고] 폴더 없음: {folder}")
        continue
    count = 0
    for fname in os.listdir(folder):
        image = cv2.imread(os.path.join(folder, fname))
        if image is None or image.shape != INPUT_SHAPE:
            continue
        data.append(image)
        labels.append(idx)
        count += 1
    print(f"  {name:6s} ({idx}): {count}장")

print("Total image data =", len(data))
if len(data) < 20:
    sys.exit("학습 이미지가 너무 적습니다. 웹 /autonomous 페이지에서 저장 ON 으로 주행해 이미지를 모으세요.")

data = (np.array(data, dtype="float32") / 127.5) - 1
data = data[:, :, :, ::-1]  # BGR -> RGB (auto_cont._predict 와 같은 순서)
labels = np.array(labels)

X_train, X_valid, Y_train, Y_valid = train_test_split(data, labels, test_size=0.2, random_state=42)

# ==================== CNN 모델 ====================
model = tf.keras.Sequential()
model.add(layers.Conv2D(64, (3, 3), activation='relu', input_shape=INPUT_SHAPE))
model.add(layers.MaxPooling2D((2, 2)))
model.add(layers.Conv2D(128, (3, 3), activation='relu'))
model.add(layers.MaxPooling2D((2, 2)))
model.add(layers.Conv2D(64, (3, 3), activation='relu'))
model.add(layers.MaxPooling2D((2, 2)))
model.add(layers.Conv2D(32, (3, 3), activation='relu'))
model.add(layers.Flatten())
model.add(layers.Dense(64, activation='relu'))
model.add(layers.Dropout(0.5))
model.add(layers.Dense(len(LABELS), activation='softmax'))

model.compile(loss='sparse_categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
history = model.fit(X_train, Y_train, validation_data=(X_valid, Y_valid), epochs=10, batch_size=128)

# ==================== 저장 (tflite + labels.txt) ====================
converter = tf.lite.TFLiteConverter.from_keras_model(model)
with open(MODEL_OUT, 'wb') as f:
    f.write(converter.convert())
with open(LABELS_OUT, 'w', encoding='utf-8') as f:
    for idx, name in enumerate(LABELS):
        f.write(f"{idx} {name}\n")
print(f"저장: {MODEL_OUT}\n저장: {LABELS_OUT}")

valid_loss, valid_accuracy = model.evaluate(X_valid, Y_valid)
print(f"Valid Accuracy: {valid_accuracy}")
print(f"Valid Loss: {valid_loss}")

# ==================== 학습 그래프 ====================
plt.figure(figsize=(12, 4))
plt.subplot(1, 2, 1)
plt.plot(history.history['loss'])
plt.plot(history.history['val_loss'])
plt.title('Model Loss')
plt.ylabel('Loss')
plt.xlabel('Epoch')
plt.legend(['Train', 'Validation'], loc='upper right')

plt.subplot(1, 2, 2)
plt.plot(history.history['accuracy'])
plt.plot(history.history['val_accuracy'])
plt.title('Model Accuracy')
plt.ylabel('Accuracy')
plt.xlabel('Epoch')
plt.legend(['Train', 'Validation'], loc='lower right')

plt.tight_layout()
plt.savefig(PLOT_OUT)   # 화면이 없는 환경(SSH)에서도 결과를 볼 수 있게 파일로도 저장
print(f"저장: {PLOT_OUT}")
plt.show()
