import os
import RPi.GPIO as GPIO
import numpy as np
import rpi_servo
from time import sleep

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

rpi_servo.init()

RIGHT_FORWARD = 7
RIGHT_BACKWARD = 8
RIGHT_PWM = 25
LEFT_FORWARD = 20
LEFT_BACKWARD = 21
LEFT_PWM = 16


go_output = 70 # 직진속도
turn_output = go_output # 회전속도

GPIO.setup(RIGHT_FORWARD,GPIO.OUT)
GPIO.setup(RIGHT_BACKWARD,GPIO.OUT)
GPIO.setup(RIGHT_PWM,GPIO.OUT)
RIGHT_MOTOR = GPIO.PWM(RIGHT_PWM,100)
RIGHT_MOTOR.start(0)

GPIO.setup(LEFT_FORWARD,GPIO.OUT)
GPIO.setup(LEFT_BACKWARD,GPIO.OUT)
GPIO.setup(LEFT_PWM,GPIO.OUT)
LEFT_MOTOR = GPIO.PWM(LEFT_PWM,100)
LEFT_MOTOR.start(0)

#RIGHT Motor control
def rightMotor(forward, backward, pwm):
    RIGHT_MOTOR.ChangeDutyCycle(pwm)
    GPIO.output(RIGHT_FORWARD,forward)
    GPIO.output(RIGHT_BACKWARD,backward)

#Left Motor control
def leftMotor(forward, backward, pwm):
    LEFT_MOTOR.ChangeDutyCycle(pwm)
    GPIO.output(LEFT_FORWARD,forward)
    GPIO.output(LEFT_BACKWARD,backward)

def motor_stop():
    GPIO.output(RIGHT_FORWARD,False)
    GPIO.output(RIGHT_BACKWARD,False)
    RIGHT_MOTOR.ChangeDutyCycle(0)
    GPIO.output(LEFT_FORWARD,False)
    GPIO.output(LEFT_BACKWARD,False)
    LEFT_MOTOR.ChangeDutyCycle(0)







def drive(go_flag, left_flag, right_flag, brake_flag, back_flag, shot_flag=0):
    # 브레이크 입력 시 
    if brake_flag == 1:
        motor_stop()

    # 직진, 후진 동시 입력 시
    elif go_flag == back_flag:
        motor_stop()

    # 직진 입력 시
    elif go_flag == 1:
        if left_flag==right_flag: # left right together
            rightMotor(1 ,0, go_output)
            leftMotor(1 ,0, go_output)
        elif left_flag == 1: #left
            rightMotor(1 ,0, go_output)
            leftMotor(0 ,1, turn_output)
        elif right_flag == 1: #right
            rightMotor(0 ,1, turn_output)
            leftMotor(1 ,0, go_output)

    # 후진 입력 시 
    elif back_flag == 1 :
        if left_flag==right_flag:
            rightMotor(0 ,1, go_output)
            leftMotor(0 ,1, go_output)
        elif left_flag == 1:
            rightMotor(0 ,1, go_output)
            leftMotor(1 ,0, turn_output)
        elif right_flag == 1:
            rightMotor(1 ,0, turn_output)
            leftMotor(0 ,1, go_output)

    # 발사 로직
    if shot_flag == 1:
        print("shot_flag_on")
        rpi_servo.set_deg(130)
        sleep(0.2)


if __name__ == '__main__':
    # 직진 5초
    sleep(5)
    
    # 후진 5초 작성
    
    
    # 좌회전 5초 작성
    
    
    # 우회전 5초 작성
