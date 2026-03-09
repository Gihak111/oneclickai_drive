import arm_cont

def handle_key(keys):
    """
    keys: 리스트 형태의 입력 키 (예: ['q'], ['q', 'w'])
    Q/A: Base(0), W/S: Shoulder(1), E/D: Elbow(2), R/F: Gripper(3)
    """
    keys = [k.lower() for k in keys]

    if 'q' in keys: arm_cont.move_servo(0,  1)
    if 'a' in keys: arm_cont.move_servo(0, -1)
    if 'w' in keys: arm_cont.move_servo(1,  1)
    if 's' in keys: arm_cont.move_servo(1, -1)
    if 'e' in keys: arm_cont.move_servo(2,  1)
    if 'd' in keys: arm_cont.move_servo(2, -1)
    if 'r' in keys: arm_cont.move_servo(3,  1)
    if 'f' in keys: arm_cont.move_servo(3, -1)