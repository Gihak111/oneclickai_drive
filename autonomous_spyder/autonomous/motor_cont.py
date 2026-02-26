
import RPi.GPIO as GPIO
import rpi_servo
from time import sleep
import ctypes
import time
from config import GO_OUTPUT


GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# 서보 초기화
rpi_servo.init()

RIGHT_FORWARD = 7
RIGHT_BACKWARD = 8
RIGHT_PWM = 25
LEFT_FORWARD = 20
LEFT_BACKWARD = 21
LEFT_PWM = 16

# 초기 파라미터
go_output = GO_OUTPUT # 직진속도


# 외부에서 파라미터를 동적으로 변경할 수 있도록 함수 추가
def set_params(go):
    global go_output
    go_output = go


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
    
# RIGHT Motor control
def rightMotor(forward, backward, pwm):
    RIGHT_MOTOR.ChangeDutyCycle(pwm)
    GPIO.output(RIGHT_FORWARD,forward)
    GPIO.output(RIGHT_BACKWARD,backward)

# Left Motor control
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

# === 수정된 drive 함수 ===
def drive(shot_flag, go_flag, left_flag, right_flag, brake_flag, back_flag):
    # 1. 주행 로직 (우선순위: 브레이크 -> 직진 -> 후진)
    
    # 브레이크 입력 시 
    if brake_flag == 1:
        motor_stop()
    
    # 직진 입력 시
    elif go_flag == 1:
        if left_flag == right_flag: # 직진 (둘 다 0이거나 둘 다 1일 때)
            rightMotor(1 ,0, go_output)
            leftMotor(1 ,0, go_output)
        elif left_flag == 1: # 좌회전
            rightMotor(1 ,0, go_output)
            leftMotor(0 ,1, go_output)
        elif right_flag == 1: # 우회전
            rightMotor(0 ,1, go_output)
            leftMotor(1 ,0, go_output)
            
    # 후진 입력 시 
    elif back_flag == 1 :
        if left_flag == right_flag: # 후진 직진
            rightMotor(0 ,1, go_output)
            leftMotor(0 ,1, go_output)
        elif left_flag == 1: # 후진 좌회전
            rightMotor(0 ,1, go_output)
            leftMotor(1 ,0, go_output)
        elif right_flag == 1: # 후진 우회전
            rightMotor(1 ,0, go_output)
            leftMotor(0 ,1, go_output)
            
    elif right_flag==1 :
        rightMotor(0 ,1, go_output)
        leftMotor(1 ,0, go_output)
        
    elif left_flag==1 :
        rightMotor(1 ,0, go_output)
        leftMotor(0 ,1, go_output)
    # 아무 키도 안 눌렀을 때
    else:
         motor_stop()

    # 2. 발사 로직 (주행 로직과 별도로 마지막에 체크)
    if shot_flag == 1:
        print("shot_flag_on")
        # 기존: rpi_servo(rpi_servo.set_deg(130)) -> 문법 오류 가능성 있음
        # 수정: 함수를 직접 호출
        rpi_servo.set_deg(130)
        sleep(0.2) # 서보가 움직일 물리적 시간 부여 (필요시 조절)
        #rpi_servo.set_deg(60)

if __name__ == '__main__':
    # 테스트 코드
    pass
