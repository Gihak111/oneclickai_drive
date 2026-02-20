import os
import rpi_servo
import numpy as np
from time import sleep

# 서보모터 시작
rpi_servo.init()


# 서보모터 각도 변경
rpi_servo.set_deg(90)
sleep(1)
rpi_servo.set_deg(95)
sleep(1)
rpi_servo.set_deg(100)
sleep(1)
rpi_servo.set_deg(105)
sleep(1)
rpi_servo.set_deg(110)
sleep(1)
rpi_servo.set_deg(90)
