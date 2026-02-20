import os
import RPi.GPIO as GPIO
import numpy as np
from time import sleep

GPIO.setwarnings(False) # GPIO 경고 메시지 끄기
GPIO.setmode(GPIO.BCM)  # 핀번호 설정을 BCM모드로 설정

# RIGHT MOTOR 설정
RIGHT_FORWARD = 7
RIGHT_BACKWARD = 8
RIGHT_PWM = 25

GPIO.setup(RIGHT_FORWARD,GPIO.OUT)    # 사용할 핀 정의
GPIO.setup(RIGHT_BACKWARD,GPIO.OUT)   # 사용할 핀 정의
GPIO.setup(RIGHT_PWM,GPIO.OUT)        # 사용할 핀 정의

RIGHT_MOTOR = GPIO.PWM(RIGHT_PWM,100) # PWM frequency 정의
RIGHT_MOTOR.start(0)                  # PWM 0으로 시작!

# LEFT MOTOR 설정
LEFT_FORWARD = 20
LEFT_BACKWARD = 21
LEFT_PWM = 16

GPIO.setup(LEFT_FORWARD,GPIO.OUT)    # 사용할 핀 정의
GPIO.setup(LEFT_BACKWARD,GPIO.OUT)   # 사용할 핀 정의
GPIO.setup(LEFT_PWM,GPIO.OUT)        # 사용할 핀 정의

LEFT_MOTOR = GPIO.PWM(LEFT_PWM,100) # PWM frequency 정의
LEFT_MOTOR.start(0)                  # PWM 0으로 시작!

# 오른쪽 모터 직진: 1, 0, 속도(0~100)
# 오른쪽 모터 후진: 0, -1, 속도(0~100)
def rightMotor(forward, backward, pwm):
    RIGHT_MOTOR.ChangeDutyCycle(pwm)
    GPIO.output(RIGHT_FORWARD,forward)
    GPIO.output(RIGHT_BACKWARD,backward)

# 왼쪽 모터 직진: 1, 0, 속도(0~100)
# 왼쪽 모터 후진: 0, -1, 속도(0~100)
def leftMotor(forward, backward, pwm):
    LEFT_MOTOR.ChangeDutyCycle(pwm)
    GPIO.output(LEFT_FORWARD,forward)
    GPIO.output(LEFT_BACKWARD,backward)

# 모든 모터 정지
def motor_stop():
    GPIO.output(RIGHT_FORWARD,False)
    GPIO.output(RIGHT_BACKWARD,False)
    RIGHT_MOTOR.ChangeDutyCycle(0)
    GPIO.output(LEFT_FORWARD,False)
    GPIO.output(LEFT_BACKWARD,False)
    LEFT_MOTOR.ChangeDutyCycle(0)


# 테스트 코드
if __name__ == '__main__':
    rightMotor(1,0,20) # 오른쪽 바퀴 전진
    sleep(3)
    rightMotor(0,-1,20) # 오른쪽 바퀴 후진
    sleep(3)
    motor_stop()
    
    sleep(3)
    leftMotor(1,0,20) # 왼쪽 바퀴 전진
    sleep(3)
    leftMotor(0,-1,20) # 왼쪽 바퀴 후진
    sleep(3)
    motor_stop()

    # TODO1
    # 양쪽 모터 모두 
    # 5초 직진, 
    # 5초 후진, 
    # 정지
