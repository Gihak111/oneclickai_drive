"""
서보 1개 지정 테스트 유틸리티
인덱스(0~11)와 목표 각도를 입력하면, 그 서보 하나만 90도에서 그 각도로 움직였다가
Enter를 누르면 다시 90도로 복귀한다. K 커맨드(부분 포즈)로 지정한 서보 1개만
움직이므로 다른 다리는 건드리지 않는다. 원하는 인덱스를 계속 바꿔가며 반복 테스트할 수 있다.

사용법: flask_web.py를 끄고(시리얼 포트를 하나만 잡을 수 있음) 실행한다.
모든 서보가 align_90 상태(물리적 90도)라고 가정한다.

- 관절 방향(ServoDirection) 확인: 인덱스와 그 좌우 짝을 같은 각도로 움직여보고
  실제 움직임이 거울 대칭인지 비교한다.
- 캘리브레이션 트림 확인: 계산된 기립/보행 목표각(예: 25.3도)을 직접 입력해서
  그 서보가 실제로 그 각도까지 무리 없이 도달하는지 확인한다.
"""
import os
import sys
import time

# robot_dog 앱의 공용 모듈(util, config) 사용
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, 'robot_dog'))
from util import connect_esp32
from config import SERVO_NAMES

DEFAULT_ANGLE = 105.0  # Enter만 누르면 쓰는 기본 목표각 (90+15)

print("==================================================")
print("🔍 서보 1개 지정 테스트 유틸리티")
print("==================================================")
print("인덱스(0~11)를 입력하면 그 서보의 이름을 보여주고,")
print("목표 각도를 입력하면 그 서보 하나만 그 각도로 움직였다가 Enter로 90도 복귀합니다.")
print("q 입력 시 종료합니다.\n")
for i, name in enumerate(SERVO_NAMES):
    print(f"  {i:2d}: {name}")
print()

ser = connect_esp32()
if ser is None:
    sys.exit(1)


def move_one(idx, angle, ms=600):
    ser.write(f"K {ms} {idx} {angle}\n".encode('ascii'))
    ser.flush()
    time.sleep(ms / 1000.0 + 0.15)


try:
    while True:
        raw = input("인덱스(0-11, q=종료): ").strip().lower()
        if raw == '':
            continue
        if raw in ('q', 'quit', 'exit'):
            break
        try:
            idx = int(raw)
        except ValueError:
            print("  숫자를 입력하세요.")
            continue
        if not (0 <= idx <= 11):
            print("  0~11 사이여야 합니다.")
            continue

        name = SERVO_NAMES[idx]
        raw_angle = input(f"  [{idx}: {name}] 목표 각도 (Enter={DEFAULT_ANGLE:g}): ").strip()
        try:
            angle = float(raw_angle) if raw_angle else DEFAULT_ANGLE
        except ValueError:
            print("  숫자를 입력하세요.")
            continue
        angle = max(0.0, min(180.0, angle))

        print(f"  -> {name}: 90 -> {angle:g}도")
        move_one(idx, angle)
        input("  확인했으면 Enter (90도로 복귀)...")
        move_one(idx, 90)
        print("  -> 90도로 복귀했습니다.\n")

except KeyboardInterrupt:
    print("\n중단합니다. 마지막으로 움직인 서보는 90도로 복귀되어 있어야 합니다.")
finally:
    ser.close()
