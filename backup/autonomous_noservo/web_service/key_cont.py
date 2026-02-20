import motor_cont

key = None

def handle_key(keys):
    # 소문자로 변환하여 대소문자 구분 없이 처리
    keys = [k.lower() for k in keys]

    # 모든 키가 눌리거나, 아무 키도 눌리지 않거나, 3개의 키가 눌리거나, ↑↓ 또는 ←→가 눌리면
    if (len(keys) == 3) or (len(keys) == 4) or ('arrowup' in keys and 'arrowdown' in keys) or ('arrowleft' in keys and 'arrowright' in keys):
        motor_cont.drive(go_flag=0, left_flag=0, right_flag=0, brake_flag=1, back_flag=0)

    # 아무 키도 눌리지 않을 때
    elif (len(keys) == 0):
        print("Stop")
        motor_cont.drive(go_flag=0, left_flag=0, right_flag=0, brake_flag=0, back_flag=0)

    # ↑ 키가 눌렸을 때
    elif 'arrowup' in keys:
        if 'arrowleft' in keys:
            print("Left Turn")
            motor_cont.drive(go_flag=1, left_flag=1, right_flag=0, brake_flag=0, back_flag=0)
        elif 'arrowright' in keys:
            print("Right Turn")
            motor_cont.drive(go_flag=1, left_flag=0, right_flag=1, brake_flag=0, back_flag=0)
        else:
            print("Straight")
            motor_cont.drive(go_flag=1, left_flag=0, right_flag=0, brake_flag=0, back_flag=0)

    # ↓ 키가 눌렸을 때
    elif 'arrowdown' in keys:
        if 'arrowleft' in keys:
            print("Left Back")
            motor_cont.drive(go_flag=0, left_flag=1, right_flag=0, brake_flag=0, back_flag=1)
        elif 'arrowright' in keys:
            print("Right Back")
            motor_cont.drive(go_flag=0, left_flag=0, right_flag=1, brake_flag=0, back_flag=1)
        else:
            print("Back")
            motor_cont.drive(go_flag=0, left_flag=0, right_flag=0, brake_flag=0, back_flag=1)

    # ← 키가 눌렸을 때
    elif 'arrowleft' in keys:
        print("Left")
        motor_cont.drive(go_flag=0, left_flag=1, right_flag=0, brake_flag=0, back_flag=0)

    # → 키가 눌렸을 때
    elif 'arrowright' in keys:
        print("Right")
        motor_cont.drive(go_flag=0, left_flag=0, right_flag=1, brake_flag=0, back_flag=0)
        
        
        