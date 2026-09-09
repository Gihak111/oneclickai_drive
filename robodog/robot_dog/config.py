"""
하드웨어 및 소프트웨어 설정 파일
자주 조정하는 파라미터들을 관리
"""
import os

THIS_DIR = os.path.dirname(os.path.realpath(__file__))

# ==================== 웹 서버 설정 ====================
WEB_PORT = 8080

# ==================== 시리얼(ESP32) 설정 ====================
SERIAL_BAUD = 115200
SERIAL_TIMEOUT = 1            # 시리얼 read 타임아웃 (초)
SERIAL_BOOT_WAIT = 1.5        # 포트 open 후 ESP32 부팅 대기 (초)
QUERY_TIMEOUT = 1.0           # 질의(핑/자세 읽기) 응답 대기 (초)
HEARTBEAT_INTERVAL = 0.5      # ESP32 워치독용 하트비트 주기 (초)

# ==================== 조종 안전 설정 ====================
# 브라우저(또는 외부 조종 클라이언트)는 키를 누르고 있는 동안 keep-alive
# (POST /api/hold, 또는 이동 명령 재전송)를 주기적으로 보낸다. 이것이 아래 시간(초)
# 이상 끊기면 서버가 스스로 정지 명령을 보낸다. keyup을 못 받는 상황(WiFi 끊김,
# 브라우저 강제 종료)에서 로봇이 계속 걷거나 반복 동작을 계속하는 사고 방지.
# 0이면 비활성화. (브라우저는 1초마다 보냄)
HOLD_TIMEOUT = 3.0

# ==================== 보행 설정 ====================
DEFAULT_STEP_SPEED = 0.005    # 보행 속도 (ESP32 STEP_ITERATE 기본값, 1사이클=1초)
MIN_STEP_SPEED = 0.001
MAX_STEP_SPEED = 0.02         # 서보 보호 상한 (펌웨어에서도 동일하게 제한)

# ==================== 서보 설정 ====================
NUM_SERVOS = 12
# 서보 인덱스(0~11) → 부위 이름 (README의 ID 맵핑표와 동일한 순서)
SERVO_NAMES = [
    "FL Hip",  "FL Knee",  "FL Wave",   # 0, 1, 2  앞왼쪽
    "FR Wave", "FR Hip",   "FR Knee",   # 3, 4, 5  앞오른쪽
    "BL Hip",  "BL Knee",  "BL Wave",   # 6, 7, 8  뒤왼쪽
    "BR Wave", "BR Hip",   "BR Knee",   # 9, 10, 11 뒤오른쪽
]
CALIBRATION_FILE = os.path.join(THIS_DIR, "calibration.json")

# ==================== 기준 자세 설정 ====================
# 로봇의 "기준 자세"는 캘리브레이션 각도(ServoMiddleAngle) 그대로다.
# unit_test/servo/align_90.py로 조립할 때 맞춘 기준과 같은 자세이며,
# 부팅 / 캘리브레이션 진입 / 동작 재생 종료 후 복귀에 모두 이 자세를 쓴다.
HOME_POSE_MS = 600            # 기준 자세로 이동하는 시간 (ms)
CALIBRATION_ADJUST_MS = 200   # 캘리브레이션 슬라이더 조작 시 그 서보만 이동하는 시간 (ms)

# ==================== 동작(모션) 편집 설정 ====================
MOTIONS_DIR = os.path.join(THIS_DIR, "motions")
KEY_BINDINGS_FILE = os.path.join(THIS_DIR, "key_bindings.json")  # 화살표 키 -> 동작 할당
MOTION_MIN_SEGMENT_MS = 50        # 키프레임 간 최소 이동 시간 (ms)
MOTION_MAX_SEGMENT_MS = 10000     # 키프레임 간 최대 이동 시간 (ms)
MOTION_DEFAULT_ENTRY_MS = 600     # 현재 자세 → 첫 키프레임 진입 시간 (ms)
MOTION_PREVIEW_MS = 250           # 편집 중 슬라이더 미리보기 이동 시간 (ms)
# 다음 키프레임 명령을 현재 구간이 끝나기 이만큼(ms) 전에 미리 보낸다.
# 시리얼 전송(J 한 줄 약 7ms)과 파이썬 스케줄링 지연을 상쇄해 키프레임 사이에
# 로봇이 멈칫하는 틈을 없앤다. 너무 크면 궤적 모서리가 잘리므로 5~10 권장.
MOTION_SEND_LEAD_MS = 8

# ==================== 카메라 설정 ====================
CAMERA_SIZE = (640, 480)
CAMERA_FPS = 24
CAMERA_QUALITY = 80           # JPEG 품질 (1~100)
CAMERA_FLIP = None            # None=안뒤집음, 0=상하, 1=좌우, -1=상하좌우

# ==================== 시스템 정보 설정 ====================
INFO_UPDATE_INTERVAL = 5      # 웹 UI 상태 정보 갱신 주기 (초)
