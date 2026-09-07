"""
모든 서보모터 정자세(90도) 정렬 유틸리티 (조립용)
J 커맨드로 12개 모터 전부를 "실제 90도"에 고정(Torque On)시킨다.
이 상태를 유지한 채로 다리가 지면과 수직/수평 90도가 되도록 부품을 조립한다.

※ 기존 버전은 캘리브레이션 모드(스탠드 자세 IK)를 사용해서 실제로는 90도가
   아니었으나, 이제 J 커맨드로 IK를 거치지 않은 진짜 90도에 고정된다.
"""
import os
import sys
import time

# robot_dog 앱의 공용 모듈(util, config) 사용
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, 'robot_dog'))
from util import connect_esp32

print("==================================================")
print("🤖 모든 서보모터 정자세(90도) 정렬 유틸리티 🤖")
print("==================================================")

ser = connect_esp32()
if ser is None:
    sys.exit(1)

print(">>> 모든 모터를 실제 90도 위치로 이동시킵니다 (1초 동안 부드럽게)...")
angles = " ".join(["90"] * 12)
ser.write(f"J 1000 {angles}\n".encode('ascii'))
ser.flush()
time.sleep(1.5)

print("[완료] 모든 모터가 90도로 정렬되어 고정(Torque On)되었습니다.")
print("이 상태에서 다리를 직각으로 조립하세요.")
print("(조립이 끝나면 Ctrl+C로 종료하세요. 모터는 계속 90도를 유지합니다.)")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n종료합니다. (모터는 마지막 자세를 유지합니다)")
    ser.close()
