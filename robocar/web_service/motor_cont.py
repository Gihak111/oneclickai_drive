import os
import RPi.GPIO as GPIO
import numpy as np
from time import sleep
from config import GO_OUTPUT

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

go_output = GO_OUTPUT

# 외부에서 파라미터를 동적으로 변경할 수 있도록 함수 추가
def set_params(go):
    global go_output
    go_output = go


# LEFT Forward motor 설정
LEFT_FORWARD_PIN1 = 27
LEFT_FORWARD_PIN2 = 17
LEFT_FORWARD_PWM = 22

# LEFT Backward motor 설정
LEFT_BACKWARD_PIN1 = 6
LEFT_BACKWARD_PIN2 = 5
LEFT_BACKWARD_PWM = 13

# RIGHT Forward motor 설정
RIGHT_FORWARD_PIN1 = 20
RIGHT_FORWARD_PIN2 = 21
RIGHT_FORWARD_PWM = 16

# RIGHT Backward motor 설정
RIGHT_BACKWARD_PIN1 = 8
RIGHT_BACKWARD_PIN2 = 7
RIGHT_BACKWARD_PWM = 25


# LEFT Forward motor GPIO 설정
GPIO.setup(LEFT_FORWARD_PIN1, GPIO.OUT)
GPIO.setup(LEFT_FORWARD_PIN2, GPIO.OUT)
GPIO.setup(LEFT_FORWARD_PWM, GPIO.OUT)
LEFT_FORWARD_MOTOR = GPIO.PWM(LEFT_FORWARD_PWM, 100)
LEFT_FORWARD_MOTOR.start(0)

# LEFT Backward motor GPIO 설정
GPIO.setup(LEFT_BACKWARD_PIN1, GPIO.OUT)
GPIO.setup(LEFT_BACKWARD_PIN2, GPIO.OUT)
GPIO.setup(LEFT_BACKWARD_PWM, GPIO.OUT)
LEFT_BACKWARD_MOTOR = GPIO.PWM(LEFT_BACKWARD_PWM, 100)
LEFT_BACKWARD_MOTOR.start(0)

# RIGHT Forward motor GPIO 설정
GPIO.setup(RIGHT_FORWARD_PIN1, GPIO.OUT)
GPIO.setup(RIGHT_FORWARD_PIN2, GPIO.OUT)
GPIO.setup(RIGHT_FORWARD_PWM, GPIO.OUT)
RIGHT_FORWARD_MOTOR = GPIO.PWM(RIGHT_FORWARD_PWM, 100)
RIGHT_FORWARD_MOTOR.start(0)

# RIGHT Backward motor GPIO 설정
GPIO.setup(RIGHT_BACKWARD_PIN1, GPIO.OUT)
GPIO.setup(RIGHT_BACKWARD_PIN2, GPIO.OUT)
GPIO.setup(RIGHT_BACKWARD_PWM, GPIO.OUT)
RIGHT_BACKWARD_MOTOR = GPIO.PWM(RIGHT_BACKWARD_PWM, 100)
RIGHT_BACKWARD_MOTOR.start(0)

# 왼쪽 전방 모터 제어
def leftForwardMotor(pin1, pin2, pwm):
    LEFT_FORWARD_MOTOR.ChangeDutyCycle(pwm)
    GPIO.output(LEFT_FORWARD_PIN1, pin1)
    GPIO.output(LEFT_FORWARD_PIN2, pin2)

# 왼쪽 후방 모터 제어
def leftBackwardMotor(pin1, pin2, pwm):
    LEFT_BACKWARD_MOTOR.ChangeDutyCycle(pwm)
    GPIO.output(LEFT_BACKWARD_PIN1, pin1)
    GPIO.output(LEFT_BACKWARD_PIN2, pin2)

# 오른쪽 전방 모터 제어
def rightForwardMotor(pin1, pin2, pwm):
    RIGHT_FORWARD_MOTOR.ChangeDutyCycle(pwm)
    GPIO.output(RIGHT_FORWARD_PIN1, pin1)
    GPIO.output(RIGHT_FORWARD_PIN2, pin2)

# 오른쪽 후방 모터 제어
def rightBackwardMotor(pin1, pin2, pwm):
    RIGHT_BACKWARD_MOTOR.ChangeDutyCycle(pwm)
    GPIO.output(RIGHT_BACKWARD_PIN1, pin1)
    GPIO.output(RIGHT_BACKWARD_PIN2, pin2)

def motor_stop():
    GPIO.output(LEFT_FORWARD_PIN1, False)
    GPIO.output(LEFT_FORWARD_PIN2, False)
    LEFT_FORWARD_MOTOR.ChangeDutyCycle(0)

    GPIO.output(LEFT_BACKWARD_PIN1, False)
    GPIO.output(LEFT_BACKWARD_PIN2, False)
    LEFT_BACKWARD_MOTOR.ChangeDutyCycle(0)

    GPIO.output(RIGHT_FORWARD_PIN1, False)
    GPIO.output(RIGHT_FORWARD_PIN2, False)
    RIGHT_FORWARD_MOTOR.ChangeDutyCycle(0)

    GPIO.output(RIGHT_BACKWARD_PIN1, False)
    GPIO.output(RIGHT_BACKWARD_PIN2, False)
    RIGHT_BACKWARD_MOTOR.ChangeDutyCycle(0)







def drive(go_flag, left_flag, right_flag, brake_flag, back_flag):
    # 브레이크 입력 시
    if brake_flag == 1:
        motor_stop()

    # 직진, 후진 동시 입력 시
    elif (go_flag == 1) and (back_flag == 1):
        motor_stop()
    # 직진 입력 시
    elif go_flag == 1:
        if left_flag==right_flag: # left right together
            leftForwardMotor(1, 0, go_output)
            leftBackwardMotor(1, 0, go_output)
            rightForwardMotor(1, 0, go_output)
            rightBackwardMotor(1, 0, go_output)
        elif left_flag == 1: #left
            leftForwardMotor(0, 1, go_output)
            leftBackwardMotor(0, 1, go_output)
            rightForwardMotor(1, 0, go_output)
            rightBackwardMotor(1, 0, go_output)
        elif right_flag == 1: #right
            leftForwardMotor(1, 0, go_output)
            leftBackwardMotor(1, 0, go_output)
            rightForwardMotor(0, 1, go_output)
            rightBackwardMotor(0, 1, go_output)

    # 후진 입력 시
    elif back_flag == 1 :
        if left_flag==right_flag:
            leftForwardMotor(0, 1, go_output)
            leftBackwardMotor(0, 1, go_output)
            rightForwardMotor(0, 1, go_output)
            rightBackwardMotor(0, 1, go_output)
        elif left_flag == 1:
            leftForwardMotor(1, 0, go_output)
            leftBackwardMotor(1, 0, go_output)
            rightForwardMotor(0, 1, go_output)
            rightBackwardMotor(0, 1, go_output)
        elif right_flag == 1:
            leftForwardMotor(0, 1, go_output)
            leftBackwardMotor(0, 1, go_output)
            rightForwardMotor(1, 0, go_output)
            rightBackwardMotor(1, 0, go_output)


    elif left_flag ==1:
            leftForwardMotor(0, 1, go_output)
            leftBackwardMotor(1, 0, go_output)
            rightForwardMotor(1, 0, go_output)
            rightBackwardMotor(0, 1, go_output)

    elif right_flag ==1:
            leftForwardMotor(1, 0, go_output)
            leftBackwardMotor(0, 1, go_output)
            rightForwardMotor(0, 1, go_output)
            rightBackwardMotor(1, 0, go_output)
            
    else :
        leftForwardMotor(1, 0, 0)
        leftBackwardMotor(1, 0, 0)
        rightForwardMotor(1, 0, 0)
        rightBackwardMotor(1, 0, 0)

if __name__ == '__main__':
    # 직진 5초
    sleep(5)

    # 후진 5초 작성


    # 좌회전 5초 작성


    # 우회전 5초 작성
