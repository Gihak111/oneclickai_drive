import RPi.GPIO as GPIO
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

# 초기 파라미터
go_output = 25 # 직진속도
neutral_deg = 90 # 중립
left_deg = 65  # 좌회전
right_deg = 115  # 우회전

go_output = 25 # 직진속도
turn_output = 20 # 회전속도

# 외부에서 파라미터를 동적으로 변경할 수 있도록 함수 추가
def set_params(neutral, left, right, go):
    global neutral_deg, left_deg, right_deg, go_output, turn_output
    neutral_deg = neutral
    left_deg = left
    right_deg = right
    go_output = go
    turn_output = int(go*0.5)

# 모터 셋업: 오른쪽
GPIO.setup(RIGHT_FORWARD,GPIO.OUT)
GPIO.setup(RIGHT_BACKWARD,GPIO.OUT)
GPIO.setup(RIGHT_PWM,GPIO.OUT)
RIGHT_MOTOR = GPIO.PWM(RIGHT_PWM,100)
RIGHT_MOTOR.start(0)

# 모터 셋업: 왼쪽
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
            rpi_servo.set_deg(neutral_deg)
        elif left_flag == 1:
            rpi_servo.set_deg(left_deg)
        elif right_flag == 1:
            rpi_servo.set_deg(right_deg)
    # 직진 입력 시
    elif go_flag == 1:
        if left_flag==right_flag: # left right together
            rpi_servo.set_deg(neutral_deg)
            rightMotor(1 ,0, go_output)
            leftMotor(1 ,0, go_output)
        elif left_flag == 1: #left
            rpi_servo.set_deg(left_deg)
            rightMotor(1 ,0, go_output)
            leftMotor(1 ,0, turn_output)
        elif right_flag == 1: #right
            rpi_servo.set_deg(right_deg)
            rightMotor(1 ,0, turn_output)
            leftMotor(1 ,0, go_output)

    # 후진 입력 시 
    elif back_flag == 1 :
        if left_flag==right_flag:
            rpi_servo.set_deg(neutral_deg)
            rightMotor(0 ,1, go_output)
            leftMotor(0 ,1, go_output)
        elif left_flag == 1:
            rpi_servo.set_deg(left_deg)
            rightMotor(0 ,1, go_output)
            leftMotor(0 ,1, turn_output)
        elif right_flag == 1:
            rpi_servo.set_deg(right_deg)
            rightMotor(0 ,1, turn_output)
            leftMotor(0 ,1, go_output)


if __name__ == '__main__':
    # 직진 5초
    # ~ rpi_servo.set_deg(neutral_deg)
    # ~ rightMotor(1 ,0, go_output)
    # ~ leftMotor(1 ,0, go_output)
    sleep(5)
    
    # 후진 5초 작성
    
    
    # 좌회전 5초 작성
    
    
    # 우회전 5초 작성
