import ctypes
import time

# initialize
lib = None

def init():
    global lib
    # Load the shared library into ctypes
    lib = ctypes.CDLL('./servo.so')
    lib.initializePWM(18)

# Set duty
def set_deg(new_deg):
    global lib
    duty = calc_duty_from_deg(new_deg)
    lib.setPWMDuty(int(duty))

# calc duty
def calc_duty_from_deg(deg):
        deg = min(175, deg)
        deg = max(5, deg)

        min_duty = 480 # 바꾸면 안됨
        max_duty = 2600 # 바꾸면 안됨

        min_deg = 0 # 바꾸면 안됨
        max_deg = 180 # 바꾸면 안됨

        duty = (deg - min_deg) / (max_deg - min_deg) * (max_duty-min_duty) + min_duty
        return duty

if __name__ == '__main__':
    init()
    print(lib)
    set_deg(45)
    time.sleep(1)
    set_deg(60)
    time.sleep(1)
    set_deg(75)
    time.sleep(1)
    set_deg(90)
    time.sleep(1)    
