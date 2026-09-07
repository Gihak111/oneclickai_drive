"""
공용 유틸리티 모듈
- ESP32 시리얼 포트 탐색/연결 (dog_cont와 for_test 스크립트들이 공유)
- 시스템 정보(CPU 온도, RAM, IP, WiFi 신호) 수집
"""
import os
import re
import time
import threading
import subprocess

import serial
import serial.tools.list_ports

from config import SERIAL_BAUD, SERIAL_TIMEOUT, SERIAL_BOOT_WAIT


# ==================== ESP32 시리얼 연결 ====================

def find_serial_candidates():
    """블루투스를 제외하고 USB/UART 장치를 우선순위로 후보 포트 목록을 만든다"""
    ports = serial.tools.list_ports.comports()
    candidates = []

    if os.path.exists('/dev/ttyAMA2'):
        candidates.append('/dev/ttyAMA2')

    for p in ports:
        if 'Bluetooth' in p.description or 'BTHENUM' in p.hwid:
            continue
        if ('USB' in p.description or 'CH340' in p.description or
                'CP210' in p.description or 'UART' in p.description or
                'ACM' in p.device):
            if p.device not in candidates:
                candidates.append(p.device)

    for p in ports:
        if 'Bluetooth' not in p.description and 'BTHENUM' not in p.hwid:
            if p.device not in candidates:
                candidates.append(p.device)

    return candidates


def connect_esp32(verbose=True):
    """
    후보 포트를 순회하며 ESP32를 찾아 연결한다.
    각 포트에 "Q 1"(서보 1번 핑)을 보내 "OK"/"ERR" 응답이 오면 ESP32로 판정.
    성공 시 열린 serial.Serial 객체, 실패 시 None 반환.
    """
    def log(msg):
        if verbose:
            print(msg)

    log("ESP32 시리얼 포트를 찾는 중입니다...")
    for port in find_serial_candidates():
        ser = None
        try:
            log(f"Testing port {port}...")
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = SERIAL_BAUD
            ser.timeout = SERIAL_TIMEOUT
            # 아두이노류 보드의 DTR 자동 리셋 방지 (open 전후 모두 눌러둔다)
            ser.setDTR(False)
            ser.setRTS(False)
            ser.open()
            ser.setDTR(False)
            ser.setRTS(False)

            time.sleep(SERIAL_BOOT_WAIT)
            ser.reset_input_buffer()

            ser.write(b"Q 1\n")
            ser.flush()

            start_time = time.time()
            reply = ""
            while time.time() - start_time < 1.0:
                if ser.in_waiting > 0:
                    reply += ser.read(ser.in_waiting).decode('ascii', errors='ignore')
                    if "OK" in reply or "ERR" in reply or "FIRMWARE" in reply:
                        log(f"[성공] {port} 포트에 {SERIAL_BAUD} baudrate로 연결 성공!")
                        return ser
                time.sleep(0.05)

            log(f"Warning: {port} 포트는 ESP32가 아닙니다 (응답 없음).")
            ser.close()
        except Exception as e:
            log(f"Warning: {port} 열기 실패 - {e}")
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass

    log("❌ 연결 가능한 ESP32 시리얼 포트가 없습니다. USB를 확인하세요.")
    return None


# ==================== 시스템 정보 ====================

# 백그라운드 스레드가 갱신하는 시스템 정보 (웹 UI 상태 패널용)
system_info = {
    'cpu_temp': 0,
    'ram_usage': 0,
    'wifi_rssi': 0,
    'ip_address': 'N/A',
}

_info_thread = None


def get_cpu_temperature():
    """라즈베리파이 CPU 온도 (실패 시 psutil, 그것도 없으면 0)"""
    try:
        temperature_str = os.popen('vcgencmd measure_temp').readline()
        return float(temperature_str.replace("temp=", "").replace("'C\n", ""))
    except Exception:
        pass
    try:
        import psutil
        temps = psutil.sensors_temperatures()
        for entries in temps.values():
            if entries:
                return round(entries[0].current, 1)
    except Exception:
        pass
    return 0


def get_ram_usage():
    try:
        import psutil
        return psutil.virtual_memory().percent
    except Exception:
        return 0


def get_ip_address(interface='wlan0'):
    try:
        import netifaces
        info = netifaces.ifaddresses(interface)
        return info.get(netifaces.AF_INET, [{}])[0].get('addr')
    except Exception:
        return None


def get_wifi_rssi(interface='wlan0'):
    try:
        output = subprocess.check_output(["/sbin/iwconfig", interface]).decode("utf-8")
        match = re.search(r"Signal level=(-\d+)", output)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return 0


def _info_loop(interval):
    while True:
        try:
            system_info['cpu_temp'] = get_cpu_temperature()
            system_info['ram_usage'] = get_ram_usage()
            system_info['wifi_rssi'] = get_wifi_rssi()
            ip = get_ip_address('wlan0') or get_ip_address('eth0')
            system_info['ip_address'] = ip if ip else 'N/A'
        except Exception as e:
            print(f"[util] 시스템 정보 갱신 에러: {e}")
        time.sleep(interval)


def start_system_info(interval=5):
    """시스템 정보 수집 스레드 시작 (중복 호출해도 1개만 돈다)"""
    global _info_thread
    if _info_thread is None:
        _info_thread = threading.Thread(target=_info_loop, args=(interval,), daemon=True)
        _info_thread.start()


if __name__ == '__main__':
    start_system_info(2)
    time.sleep(3)
    print(system_info)
    ser = connect_esp32()
    if ser:
        print("ESP32 연결 확인 완료.")
        ser.close()
