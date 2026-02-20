import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow.keras import layers
from sklearn.model_selection import train_test_split
import util # 상대 경로로 util 모듈 import

util.deleteImg()  # 이미지 폴더 내 1KB 미만의 파일 삭제

# 이미지 경로와 라벨을 저장할 리스트 생성
data = []
labels = []
test = []

# 이미지 데이터를 읽어오고 라벨을 저장: 직진
data_path = ".." + os.sep + "image" + os.sep + "go"
for img in os.listdir(data_path):
    image = cv2.imread(os.path.join(data_path, img))
    data.append(image)
    test.append(img)
    labels.append(0)  # 라벨 0

# 이미지 데이터를 읽어오고 라벨을 저장: 좌회전
data_path = ".." + os.sep + "image" + os.sep + "left"
for img in os.listdir(data_path):
    image = cv2.imread(os.path.join(data_path, img))
    data.append(image)
    test.append(img)    
    labels.append(1)  # 라벨 1

# 이미지 데이터를 읽어오고 라벨을 저장: 우회전
data_path = ".." + os.sep + "image" + os.sep + "right"
for img in os.listdir(data_path):
    image = cv2.imread(os.path.join(data_path, img))
    data.append(image)
    test.append(img)    
    labels.append(2)  # 라벨 2
    
# 이미지 데이터를 읽어오고 라벨을 저장:     브레이크
data_path = ".." + os.sep + "image" + os.sep + "brake"
for img in os.listdir(data_path):
    image = cv2.imread(os.path.join(data_path, img))
    data.append(image)
    test.append(img)    
    labels.append(3)  # 라벨 3
    
    
    
    
# 데이터와 라벨을 넘파이 배열로 변환
print("Total image data = ", len(data))
data = (np.array(data, dtype='float32')/127.5) -1
data = data[:,:,:,::-1]
labels = np.array(labels)

#X_train, X_val, Y_train, Y_val = train_test_split(data, labels, test_size=0.2, random_state=42)
X_train, X_valid, Y_train, Y_valid = train_test_split(data, labels, test_size=0.2, random_state=42 )

# Convolutional Neural Network Model
model = tf.keras.Sequential()
model.add(layers.Conv2D(64, (3, 3), activation='relu', input_shape=(64, 64, 3)))
model.add(layers.MaxPooling2D((2, 2)))
model.add(layers.Conv2D(128, (3, 3), activation='relu'))
model.add(layers.MaxPooling2D((2, 2)))
model.add(layers.Conv2D(64, (3, 3), activation='relu'))
model.add(layers.MaxPooling2D((2, 2)))
model.add(layers.Conv2D(32, (3, 3), activation='relu'))
model.add(layers.Flatten())
model.add(layers.Dense(64, activation='relu'))
model.add(layers.Dropout(0.5))
model.add(layers.Dense(4, activation='softmax'))

# 모델 학습
model.compile(loss='sparse_categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
history = model.fit(X_train, Y_train, validation_data=(X_valid, Y_valid), epochs=10, batch_size = 128)

# 모델 저장 (h5 포맷)
# model.save('.//keras_model.h5')

# 모델 저장 (tflite)
# 이 방식을 사용하려면 커맨드창에 아래 커맨드 입력
# pip install flatbuffers==2.0 --break-system-packages
converter = tf.lite.TFLiteConverter.from_keras_model(model)
tflite_model = converter.convert()
with open('keras_model.tflite', 'wb') as f:
  f.write(tflite_model)

# x_test, y_test를 사용하여 모델 평가
valid_loss, valid_accuracy = model.evaluate(X_valid, Y_valid)

print(f"Valid Accuracy: {valid_accuracy}")
print(f"Valid Loss: {valid_loss}")
print(history.history.keys())

# 2개의 subplot 생성
plt.figure(figsize=(12, 4))

# Loss 그래프
plt.subplot(1, 2, 1)
plt.plot(history.history['loss'])
plt.plot(history.history['val_loss'])
plt.title('Model Loss')
plt.ylabel('Loss')
plt.xlabel('Epoch')
plt.legend(['Train', 'Validation'], loc='upper right')

# Accuracy 그래프
plt.subplot(1, 2, 2)
plt.plot(history.history['accuracy'])
plt.plot(history.history['val_accuracy'])
plt.title('Model Accuracy')
plt.ylabel('Accuracy')
plt.xlabel('Epoch')
plt.legend(['Train', 'Validation'], loc='lower right')

plt.tight_layout()
plt.show()
