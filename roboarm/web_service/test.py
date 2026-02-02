import time
import threading
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

# --- 1. 하드웨어 설정 ---
i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = 50

# 서보 객체 (Pin 0~15)
servos = [servo.Servo(pca.channels[i], min_pulse=500, max_pulse=2500) for i in range(16)]
