"""
로봇개 관절 서보모터 ID 설정 유틸리티
모터를 딱 1개씩만 연결한 상태로 실행하여 ID 1~12번을 순서대로 부여한다.
"""
import os
import sys
import time

# robot_dog 앱의 공용 모듈(util, config) 사용
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, 'robot_dog'))
from util import connect_esp32

print("\n=========================================")
print("🤖 [Robot Dog 관절 서보모터 ID 설정 유틸리티] 🤖")
print("=========================================")
print("!!! 아주 중요한 주의사항 !!!")
print("시리얼 버스 서보모터는 같은 통신선을 공유하는 병렬 구조입니다.")
print("만약 모터 여러 개를 한 번에 연결해둔 상태에서 실행하면,")
print("모든 모터가 동시에 똑같은 ID로 덮어씌워지는 대참사가 발생합니다.")
print("반드시 **할당하려는 모터 딱 1개만** 연결한 상태에서 진행하세요!")
print("=========================================\n")

ser = connect_esp32()
if ser is None:
    sys.exit(1)


def send_and_read(cmd, wait_time=0.2):
    try:
        if ser.in_waiting > 0:
            ser.read(ser.in_waiting)
        ser.write(cmd.encode('ascii'))
        ser.flush()
        time.sleep(wait_time)
    except Exception as e:
        print(f"데이터 전송 에러: {e}")


def set_servo_id(old_id, new_id):
    send_and_read(f"I {old_id} {new_id}\n", 0.2)  # ESP32가 패킷 3번 쏘는 시간 대기


def verify_id(servo_id):
    """PING 명령을 보내 방금 바꾼 ID가 정상 응답하는지 확인합니다."""
    send_and_read(f"Q {servo_id}\n", 0.1)
    try:
        reply = ""
        start = time.time()
        while time.time() - start < 0.5:
            if ser.in_waiting > 0:
                reply += ser.read(ser.in_waiting).decode('ascii', errors='ignore')
                if "OK" in reply:
                    return True
                if "ERR" in reply:
                    return False
            time.sleep(0.02)
    except Exception:
        pass
    return False


target_ids = [
    (1, "앞쪽 왼쪽 골반 (FL Hip)"),
    (2, "앞쪽 왼쪽 무릎 (FL Knee)"),
    (3, "앞쪽 왼쪽 무릎아래 (FL Wave)"),
    (4, "앞쪽 오른쪽 무릎아래 (FR Wave)"),
    (5, "앞쪽 오른쪽 골반 (FR Hip)"),
    (6, "앞쪽 오른쪽 무릎 (FR Knee)"),
    (7, "뒤쪽 왼쪽 골반 (BL Hip)"),
    (8, "뒤쪽 왼쪽 무릎 (BL Knee)"),
    (9, "뒤쪽 왼쪽 무릎아래 (BL Wave)"),
    (10, "뒤쪽 오른쪽 무릎아래 (BR Wave)"),
    (11, "뒤쪽 오른쪽 골반 (BR Hip)"),
    (12, "뒤쪽 오른쪽 무릎 (BR Knee)"),
]

for new_id, desc in target_ids:
    input(f"\n👉 [{desc} - 부위 ID: {new_id} 할당]\n   부착하실 모터 **딱 1개만** 연결하고 엔터(Enter)를 누르세요...")

    # 254(0xFE)는 브로드캐스트 ID입니다.
    set_servo_id(254, new_id)

    if verify_id(new_id):
        print(f"   ✅ 대성공! ID {new_id}번 ({desc}) 설정 및 검증 완료!")
        print("   (이제 선을 뽑으시고, 다음 모터를 꽂아주세요.)")
    else:
        print(f"   ❌ 실패: ID {new_id}번으로 설정 명령을 보냈으나 응답이 없습니다. 전원과 연결을 확인하세요.")

print("\n🎉 모든 모터의 ID 설정이 안전하게 완료되었습니다.")
print("이제 1번부터 12번 모터까지 데이지 체인 방식으로 모두 연결하세요!")

ser.close()
