import os
import RPi.GPIO as GPIO
import numpy as np
import rpi_servo
from time import sleep
from config import NEUTRAL_DEG, LEFT_DEG, RIGHT_DEG, GO_OUTPUT, TURN_OUTPUT

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

rpi_servo.init()

RIGHT_FORWARD = 7
RIGHT_BACKWARD = 8
RIGHT_PWM = 25
LEFT_FORWARD = 20
LEFT_BACKWARD = 21
LEFT_PWM = 16

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







def drive(go_flag, left_flag, right_flag, brake_flag, back_flag):
    # 브레이크 입력 시
    if brake_flag == 1:
        motor_stop()

    # 직진, 후진 동시 입력 시
    elif go_flag == back_flag:
        motor_stop()
        if left_flag==right_flag:
            rpi_servo.set_deg(NEUTRAL_DEG)
        elif left_flag == 1:
            rpi_servo.set_deg(LEFT_DEG)
        elif right_flag == 1:
            rpi_servo.set_deg(RIGHT_DEG)
    # 직진 입력 시
    elif go_flag == 1:
        if left_flag==right_flag: # left right together
            rpi_servo.set_deg(NEUTRAL_DEG)
            rightMotor(1 ,0, GO_OUTPUT)
            leftMotor(1 ,0, GO_OUTPUT)
        elif left_flag == 1: #left
            rpi_servo.set_deg(LEFT_DEG)
            rightMotor(1 ,0, GO_OUTPUT)
            leftMotor(1 ,0, TURN_OUTPUT)
        elif right_flag == 1: #right
            rpi_servo.set_deg(RIGHT_DEG)
            rightMotor(1 ,0, TURN_OUTPUT)
            leftMotor(1 ,0, GO_OUTPUT)

    # 후진 입력 시
    elif back_flag == 1 :
        if left_flag==right_flag:
            rpi_servo.set_deg(NEUTRAL_DEG)
            rightMotor(0 ,1, GO_OUTPUT)
            leftMotor(0 ,1, GO_OUTPUT)
        elif left_flag == 1:
            rpi_servo.set_deg(LEFT_DEG)
            rightMotor(0 ,1, GO_OUTPUT)
            leftMotor(0 ,1, TURN_OUTPUT)
        elif right_flag == 1:
            rpi_servo.set_deg(RIGHT_DEG)
            rightMotor(0 ,1, TURN_OUTPUT)
            leftMotor(0 ,1, GO_OUTPUT)


if __name__ == '__main__':
    # 직진 5초
    # ~ rpi_servo.set_deg(neutral_deg)
    # ~ rightMotor(1 ,0, go_output)
    # ~ leftMotor(1 ,0, go_output)
    sleep(5)
    
    # 후진 5초 작성
    
    
    # 좌회전 5초 작성
    
    
    # 우회전 5초 작성
