"""
모터 동작 테스트 (하드웨어 생존 테스트)
J 커맨드(직접 각도 지정)로 연결된 모든 모터를 90도 -> 120도 -> 90도로 움직인다.
※ J 커맨드는 IK 계산 없이 서보에 실제 각도를 그대로 쓰므로, 표시되는 각도가 실제 각도다.
"""
import os
import sys
import time

# robot_dog 앱의 공용 모듈(util, config) 사용
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, 'robot_dog'))
from util import connect_esp32

ser = connect_esp32()
if ser is None:
    sys.exit(1)


def move_all(angle, duration_ms=800):
    """모든 모터를 duration_ms 동안 부드럽게 angle(실제 각도)로 이동"""
    angles_str = " ".join([str(angle)] * 12)
    ser.write(f"J {duration_ms} {angles_str}\n".encode('ascii'))
    ser.flush()
    print(f"[TEST] 모든 모터에게 {duration_ms}ms 동안 {angle}도로 이동 명령을 보냈습니다.")
    time.sleep(duration_ms / 1000.0 + 0.3)


print("--------------------------------------------------")
print("🚨 궁극의 하드웨어 생존 테스트를 시작합니다 🚨")
print("--------------------------------------------------")
print("3초 뒤, 연결된 '모든' 모터가 90도(물리적 중앙) 위치로 동시에 움직입니다!")
time.sleep(3)

move_all(90)
time.sleep(1)

print("\n이제 모터가 살짝 꺾입니다! (120도)")
move_all(120)
time.sleep(1)

print("\n다시 중앙으로 돌아옵니다! (90도)")
move_all(90)
time.sleep(1)

print("\n테스트 종료! 만약 모터가 이 테스트에서도 안 움직였다면 선/전원 불량입니다.")
ser.close()
