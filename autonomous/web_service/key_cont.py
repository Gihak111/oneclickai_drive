import motor_cont

key = None

def handle_key(keys):

    # 모든 키가 눌리거나, 아무 키도 눌리지 않거나, 3개의 키가 눌리거나, w,s 또는 a,d가 눌리면
    if (len(keys) == 3) or (len(keys) == 4) or ('w' in keys and 's' in keys) or ('a' in keys and 'd' in keys):
        motor_cont.drive(go_flag=0, left_flag=0, right_flag=0, brake_flag=1, back_flag=0)

    # 아무 키도 눌리지 않을 때
    elif (len(keys) == 0):
        print("Stop")
        motor_cont.drive(go_flag=0, left_flag=0, right_flag=0, brake_flag=0, back_flag=0)

    # W 키가 눌렸을 때
    elif 'w' in keys:
        if 'a' in keys:
            print("Left Turn")
            motor_cont.drive(go_flag=1, left_flag=1, right_flag=0, brake_flag=0, back_flag=0)
        elif 'd' in keys:
            print("Right Turn")
            motor_cont.drive(go_flag=1, left_flag=0, right_flag=1, brake_flag=0, back_flag=0)
        else:
            print("Straight")
            motor_cont.drive(go_flag=1, left_flag=0, right_flag=0, brake_flag=0, back_flag=0)

    # S 키가 눌렸을 때
    elif 's' in keys:
        if 'a' in keys:
            print("Left Back")
            motor_cont.drive(go_flag=0, left_flag=1, right_flag=0, brake_flag=0, back_flag=1)
        elif 'd' in keys:
            print("Right Back")
            motor_cont.drive(go_flag=0, left_flag=0, right_flag=1, brake_flag=0, back_flag=1)
        else:
            print("Back")
            motor_cont.drive(go_flag=0, left_flag=0, right_flag=0, brake_flag=0, back_flag=1)

    # A 키가 눌렸을 때
    elif 'a' in keys:
        print("Left")
        motor_cont.drive(go_flag=0, left_flag=1, right_flag=0, brake_flag=0, back_flag=0)

    # D 키가 눌렸을 때
    elif 'd' in keys:
        print("Right")
        motor_cont.drive(go_flag=0, left_flag=0, right_flag=1, brake_flag=0, back_flag=0)
        
        
        