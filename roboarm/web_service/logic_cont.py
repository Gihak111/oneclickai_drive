import arm_cont

def handle_key(keys):
    """
    keys: 리스트 형태의 입력 키 (예: ['w'], ['a', 'w'])
    AI나 웹에서 보낸 키를 해석해 관절을 움직임
    """
    step = arm_cont.move_step # 현재 설정된 속도 가져오기

    # --- Shoulder (어깨) ---
    if 'w' in keys: # 아래로 (각도 감소라 가정, 방향 반대면 수정)
        arm_cont.update_target('shoulder', -step)
    elif 's' in keys: # 위로
        arm_cont.update_target('shoulder', step)

    # --- Base (좌우 회전) ---
    if 'a' in keys: # 오른쪽
        arm_cont.update_target('base', -step)
    elif 'd' in keys: # 왼쪽
        arm_cont.update_target('base', step)

    # --- Elbow (팔꿈치) ---
    if 'f' in keys: # 굽히기
        arm_cont.update_target('elbow', -step)
    elif 'r' in keys: # 펴기
        arm_cont.update_target('elbow', step)

    # --- Gripper (집게) ---
    if 'h' in keys: # 열기
        arm_cont.set_target_absolute('gripper', 50)
    elif 'g' in keys: # 잡기
        arm_cont.set_target_absolute('gripper', 130)