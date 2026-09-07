"""
서보모터 스캔 테스트
1~12번 모터에 핑(Ping)을 보내 몇 번 모터가 살아있는지 확인한다.

실패한 ID는 ESP32가 실제로 받은 바이트(QDBG 진단 줄)를 같이 보여 준다:
  rx=[]                    아무 응답도 없음 -> 서보 전원, RX(18번) 배선, TX/RX 반대 연결 확인
  rx=[ff ff 05 02 00 f8]   정상 프레임인데 실패 -> 펌웨어 파서 문제 (보고 요망)
  echo=1                   드라이버 보드가 송신을 되돌려주는(에코) 구조 (펌웨어가 자동 처리)
"""
import os
import sys
import time

# robot_dog 앱의 공용 모듈(util, config) 사용
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, 'robot_dog'))
from util import connect_esp32


def ping(ser, servo_id, timeout=0.6):
    """Q <id> 전송 후 ("OK"|"ERR"|"NONE", 진단줄) 반환"""
    if ser.in_waiting > 0:
        ser.read(ser.in_waiting)
    ser.write(f"Q {servo_id}\n".encode('ascii'))
    ser.flush()

    buf = ""
    result = None
    start = time.time()
    while time.time() - start < timeout:
        if ser.in_waiting > 0:
            buf += ser.read(ser.in_waiting).decode('ascii', errors='ignore')
            complete, _, buf = buf.rpartition('\n')
            for line in complete.splitlines():
                line = line.strip()
                if result is None and line == "OK":
                    return "OK", ""
                if result is None and line == "ERR":
                    result = "ERR"
                    start = time.time()  # 진단 줄을 잠깐 더 기다린다
                elif result == "ERR" and line.startswith("QDBG"):
                    return "ERR", line
        time.sleep(0.01)
    return result or "NONE", ""


def scan_waveshare_servos():
    print("==================================================")
    print("🔍 [시리얼 스마트 스캐너] 유선으로 모든 모터를 스캔합니다!")

    ser = connect_esp32()
    if ser is None:
        return
    time.sleep(0.5)

    found = []
    no_reply = []
    weird = []

    print("\n[스캔 중] 1번부터 12번 모터까지 핑(Ping) 쏘는 중...")
    for servo_id in range(1, 13):
        result, dbg = ping(ser, servo_id)
        if result == "OK":
            print(f"   -> 🤩 [발견!!] ID {servo_id}번 모터가 응답했습니다!")
            found.append(servo_id)
        elif result == "ERR":
            print(f"   -> ❌ ID {servo_id}번 응답 없음   {dbg}")
            if "rx=[]" in dbg:
                no_reply.append(servo_id)
            else:
                weird.append((servo_id, dbg))
        else:
            print(f"   -> ⚠️ ID {servo_id}번: ESP32가 대답하지 않음 (USB 연결/펌웨어 확인)")
        time.sleep(0.05)

    print("\n==================================================")
    if not found:
        print("😭 [결과] 아무 모터도 대답하지 않았습니다.")
    else:
        print(f"💡 [결과] 응답한 모터: {found}")
    if no_reply:
        print(f"   응답이 전혀 없는 ID: {no_reply}")
        print("   -> 서보 전원, ESP32 RX(18번)에 서보 신호선이 연결됐는지, TX/RX가 반대는 아닌지 확인하세요.")
        print("      (송신만 되는 배선이면 로봇은 걷지만 자세 캡처/핑은 실패합니다)")
    if weird:
        print("   프레임은 받았지만 검증에 실패한 ID (ID/체크섬 불일치):")
        for sid, dbg in weird:
            print(f"      ID {sid}: {dbg}")
        print("   -> 이 출력을 그대로 보고해 주세요.")

    ser.close()


if __name__ == '__main__':
    scan_waveshare_servos()
