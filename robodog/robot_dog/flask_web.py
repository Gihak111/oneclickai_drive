"""
로봇개 웹 서버 (메인 진입점)  —  실행: python3 robot_dog/flask_web.py

- 순수 Flask(REST + 폴링)만 사용 — 가상환경 없이 라즈베리파이 시스템 패키지로 동작
- 실제 하드웨어 제어는 dog_cont(시리얼 브릿지)가, 동작 재생은 motion_cont가 담당
- 카메라는 camera_stream이 MJPEG으로 스트리밍
- 웹 UI는 모든 명령을 POST /api/command 로, 상태는 GET /api/status 폴링으로 주고받는다
- 웹에서 들어온 값은 전부 타입/범위를 검증한 뒤에만 시리얼로 보낸다
  (문자열이 그대로 f-string에 들어가 다른 커맨드가 끼어들던 문제 방지)
"""
import time

from flask import Flask, render_template, Response, request, jsonify

import util
import dog_cont
import key_cont
import motion_cont
from camera_stream import camera, HEADERS_NO_CACHE
from config import (WEB_PORT, INFO_UPDATE_INTERVAL, SERVO_NAMES, MOTION_PREVIEW_MS,
                    MOTION_MIN_SEGMENT_MS, MOTION_MAX_SEGMENT_MS,
                    MIN_STEP_SPEED, MAX_STEP_SPEED, DEFAULT_STEP_SPEED, HOLD_TIMEOUT)

app = Flask(__name__)


# CORS 처리: flask-cors 패키지 없이 after_request로 직접 헤더를 붙인다.
# 외부 PC의 조종 프로그램(/keys)이 브라우저에서 접근할 수 있도록 모든 origin을 허용한다.
# 로봇 자체 AP(인터넷 없음)에서 쓰는 전제이며, 입력은 아래 검증 헬퍼로 전부 걸러진다.
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin')
    response.headers['Access-Control-Allow-Origin'] = origin if origin else '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PUT, DELETE'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


# ==================== 입력 검증 헬퍼 ====================

def _as_int(v, lo, hi, default=None):
    """정수로 변환 후 [lo, hi]로 클램프. 변환 불가면 default."""
    try:
        v = int(float(v))
    except (TypeError, ValueError, OverflowError):
        return default
    return max(lo, min(hi, v))


def _as_index(v, lo, hi):
    """
    정수 식별자(서보 번호, 프리셋 번호, 특수기능 번호 등).
    범위 밖이거나 정수가 아니면 None — 크기값과 달리 클램프하면 엉뚱한 대상에 명령이 간다.
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or not f.is_integer():
        return None
    i = int(f)
    return i if lo <= i <= hi else None


def _as_float(v, lo, hi, default=None):
    """실수로 변환 후 [lo, hi]로 클램프. 변환 불가/NaN이면 default."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    if v != v:
        return default
    return max(lo, min(hi, v))


def _as_bool(v, default=False):
    if v is None:
        return default
    if isinstance(v, str):
        return v.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(v)


def _json_dict():
    """요청 본문 JSON을 dict로. dict가 아니거나 없으면 빈 dict."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


# ==================== 페이지 라우팅 ====================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/calibration')
def calibration():
    return render_template('calibration.html',
                           angles=dog_cont.ServoMiddleAngle,
                           pins=dog_cont.pin_mapping,
                           active_preset=dog_cont.calibration_data.get("active_preset", 1))


@app.route('/motion')
def motion_page():
    return render_template('motion.html', servo_names=SERVO_NAMES)


@app.route('/video_feed')
@app.route('/stream.mjpg')
def video_feed():
    return Response(camera.mjpeg_generator(),
                    mimetype='multipart/x-mixed-replace; boundary=frame',
                    headers=HEADERS_NO_CACHE)


@app.route('/ping', methods=['GET', 'HEAD', 'OPTIONS'])
def ping():
    return jsonify({"status": "ok", "message": "pong"})


# ==================== 상태 폴링 (기존 SocketIO 브로드캐스트 대체) ====================

@app.route('/api/status', methods=['GET'])
def api_status():
    """웹 UI가 주기적으로 폴링하는 시스템/로봇 상태"""
    status = dict(util.system_info)
    status.update(motion_cont.get_status())
    status["hardware"] = dog_cont.HARDWARE_AVAILABLE
    status["moving"] = dog_cont.is_moving()
    return jsonify(status)


# ==================== 조종 (REST) ====================

@app.route('/keys', methods=['POST', 'OPTIONS'])
def keys():
    """
    외부 PC 조종용: {"keys": ["w", "d"]}. 이동 중에는 HOLD_TIMEOUT(기본 3초) 안에
    같은 요청을 다시 보내야 계속 움직인다 (keep-alive 워치독).
    """
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = request.form.to_dict() or {}
    keys_in = data.get('keys', [])
    if isinstance(keys_in, str):
        keys_in = [keys_in]
    if not isinstance(keys_in, list):
        keys_in = []
    keys_in = [str(k)[:16] for k in keys_in[:16]]
    key_cont.handle_key(keys_in)
    return jsonify({"status": "success", "received": {"keys": keys_in}})


@app.route('/api/hold', methods=['POST'])
def api_hold():
    """
    keep-alive. body(선택): {"move": true, "motion": true} — 어느 종류를 갱신할지.
    본문이 없으면 둘 다 갱신한다.
      move:   이동(보행) 중 — 브라우저가 이동 키를 누르고 있는 동안 1초마다
      motion: hold 동작 재생 중 — 화살표 키를 누르고 있는 동안 / 편집기가 열려 있는 동안
    HOLD_TIMEOUT 동안 끊기면 서버가 해당 동작을 스스로 정지시킨다.
    """
    data = _json_dict()
    if not data:
        key_cont.refresh_hold()
    else:
        if _as_bool(data.get("move")):
            key_cont.refresh_hold('move')
        if _as_bool(data.get("motion")):
            key_cont.refresh_hold('motion')
    return jsonify({"status": "success", "timeout": HOLD_TIMEOUT})


@app.route('/api/command', methods=['POST', 'OPTIONS'])
def api_command():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})
    handle_command(_json_dict())
    return jsonify({"status": "success", "message": "Command received"})


def handle_command(data):
    """웹 UI 공통 명령 처리 (payload: {A: 명령코드, B/C/D/E: 인자}). 값은 전부 검증."""
    cmd_type = _as_int(data.get("A"), 0, 9999, 0)

    # 이동
    if cmd_type == 1000:
        fb = _as_int(data.get("B"), -1, 1, 0)
        lr = _as_int(data.get("C"), -1, 1, 0)
        if fb != 0 or lr != 0:
            if motion_cont.is_playing():
                motion_cont.stop(to_home=False)  # 조종 개입 시 동작 재생 중단
            key_cont.refresh_hold('move')
        dog_cont.input_cmd(fb, lr)

    # 특수 기능 (1=엎드리기, 2=악수, 3=점프, 4=기립)
    elif cmd_type == 1004:
        func_num = _as_index(data.get("B"), 1, 4)
        funcs = {1: dog_cont.function_stay_low, 2: dog_cont.function_handshake,
                 3: dog_cont.function_jump, 4: dog_cont.function_stand}
        if func_num in funcs:
            if motion_cont.is_playing():
                motion_cont.stop(to_home=False)
            funcs[func_num]()

    # 캘리브레이션
    elif cmd_type == 2000:
        if motion_cont.is_playing():
            motion_cont.stop(to_home=False)  # 재생 중인 J가 캘리브레이션 자세를 덮지 않게
        dog_cont.enter_calibration_mode()
    elif cmd_type == 2001:
        dog_cont.exit_calibration_mode()
    elif cmd_type == 2002:
        servo_id = _as_index(data.get("B"), 0, len(SERVO_NAMES) - 1)
        angle = _as_float(data.get("C"), 0.0, 180.0, None)
        if servo_id is not None and angle is not None:
            dog_cont.update_calibration_angle(servo_id, angle)
    elif cmd_type == 2003:
        preset = _as_index(data.get("B"), 1, 3)
        if preset:
            dog_cont.set_calibration_preset(preset)
    elif cmd_type == 2004:
        preset = _as_index(data.get("B"), 1, 3)
        if preset:
            dog_cont.save_to_preset(preset)
    elif cmd_type == 2005:
        joint = _as_index(data.get("B"), 0, len(SERVO_NAMES) - 1)
        pin = _as_index(data.get("C"), 1, 253)
        if joint is not None and pin:
            dog_cont.update_pin_mapping(joint, pin)

    # 속도
    elif cmd_type == 3000:
        speed = _as_float(data.get("B"), MIN_STEP_SPEED, MAX_STEP_SPEED, DEFAULT_STEP_SPEED)
        dog_cont.set_speed(speed)

    # 조명 / RGB / OLED
    elif cmd_type == 4000:
        dog_cont.lights_ctrl(_as_int(data.get("B"), 0, 255, 0), _as_int(data.get("C"), 0, 255, 0))
    elif cmd_type == 4001:
        dog_cont.rgb_light(_as_int(data.get("B"), 0, 255, 0), _as_int(data.get("C"), 0, 255, 0),
                           _as_int(data.get("D"), 0, 255, 0), _as_int(data.get("E"), 0, 255, 0))
    elif cmd_type == 4002:
        dog_cont.base_oled(_as_int(data.get("B"), 1, 3, 1), data.get("C", ""))


# ==================== 동작(모션) API ====================

@app.route('/api/motions', methods=['GET'])
def api_motion_list():
    return jsonify({"motions": motion_cont.list_motions()})


@app.route('/api/motions/<name>', methods=['GET'])
def api_motion_get(name):
    try:
        motion = motion_cont.load_motion(name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    if motion is None:
        return jsonify({"error": "동작을 찾을 수 없습니다."}), 404
    return jsonify(motion)


@app.route('/api/motions/<name>', methods=['POST'])
def api_motion_save(name):
    data = _json_dict()
    if not data:
        return jsonify({"error": "동작 데이터(JSON)가 필요합니다."}), 400
    try:
        saved = motion_cont.save_motion(name, data)
        return jsonify({"status": "success", "motion": saved})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/motions/<name>', methods=['DELETE'])
def api_motion_delete(name):
    try:
        if motion_cont.delete_motion(name):
            unbound = key_cont.unbind_motion(name)  # 이 동작을 가리키던 화살표 할당 해제
            return jsonify({"status": "success", "unbound": unbound})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"error": "동작을 찾을 수 없습니다."}), 404


def _play_response():
    st = motion_cont.get_status()
    return jsonify({"status": "success", "loop": st["loop"], "hold": st["hold"],
                    "motion": st["motion"]})


@app.route('/api/motions/<name>/play', methods=['POST'])
def api_motion_play(name):
    """
    저장된 동작 재생. body: {"loop": bool(선택), "hold": bool(선택)}
    hold=true는 "키를 누르고 있는 동안" 재생하는 경우(화살표 키)에 쓴다. 반복 동작에만
    적용되며, 브라우저는 /api/hold {motion:true} keep-alive를 계속 보내야 한다.
    응답에 loop/hold 를 돌려주므로 브라우저는 그 값으로 "뗄 때 멈출지"를 판단한다.
    """
    data = _json_dict()
    loop = _as_bool(data.get("loop")) if data.get("loop") is not None else None
    hold = _as_bool(data.get("hold"))
    try:
        motion_cont.play(name, loop=loop, hold=hold)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404 if not motion_cont.motion_exists(name) else 400
    if motion_cont.is_hold_playing():
        key_cont.refresh_hold('motion')
    return _play_response()


@app.route('/api/motion/play', methods=['POST'])
def api_motion_play_data():
    """
    편집 중인(저장하지 않은) 동작 데이터를 바로 재생.
    body: {"motion": {name, loop, keyframes}, "loop": bool(선택), "hold": bool(선택)}
    """
    data = _json_dict()
    motion = data.get("motion")
    if not isinstance(motion, dict):
        return jsonify({"error": "motion(동작 데이터)이 필요합니다."}), 400
    loop = _as_bool(data.get("loop")) if data.get("loop") is not None else None
    hold = _as_bool(data.get("hold"))
    try:
        motion_cont.play_data(motion, loop=loop, hold=hold)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if motion_cont.is_hold_playing():
        key_cont.refresh_hold('motion')
    return _play_response()


@app.route('/api/motion/stop', methods=['POST'])
def api_motion_stop():
    """
    재생 중단 후 기준 자세(캘리브레이션 각도)로 복귀. body(선택):
      only_if_playing: 재생 중이 아니면 복귀 명령을 보내지 않음 (다른 조작 방해 방지)
      motion: 이 이름의 동작이 재생 중일 때만 중단 (화살표 키를 뗐을 때 사용)
    """
    data = _json_dict()
    only_motion = data.get("motion") if isinstance(data.get("motion"), str) else None
    if _as_bool(data.get("only_if_playing")) and not motion_cont.is_playing():
        return jsonify({"status": "success", "skipped": True})
    stopped = motion_cont.stop(to_home=True, only_motion=only_motion)
    return jsonify({"status": "success", "skipped": not stopped})


@app.route('/api/motion/status', methods=['GET'])
def api_motion_status():
    status = motion_cont.get_status()
    status["hardware"] = dog_cont.HARDWARE_AVAILABLE
    return jsonify(status)


@app.route('/api/motion/pose', methods=['POST'])
def api_motion_pose():
    """
    편집 중 미리보기.
    - {"servos": {인덱스: 각도, ...}}: 지정한 서보만 이동 (나머지는 현재 위치 유지)
      -> 슬라이더 조작 시 사용: 바꾼 서보 딱 하나만 움직인다
    - {"angles": [12개]}: 전체 자세 이동 (키프레임 미리보기 버튼)
    """
    data = _json_dict()
    duration = _as_int(data.get("duration_ms", MOTION_PREVIEW_MS),
                       20, MOTION_MAX_SEGMENT_MS, None)
    if duration is None:
        return jsonify({"error": "duration_ms는 숫자여야 합니다."}), 400

    if motion_cont.is_playing():
        motion_cont.stop(to_home=False)

    # 부분 포즈: 지정 서보만 이동
    servos = data.get("servos")
    if isinstance(servos, dict) and servos:
        clean = {}
        for k, v in servos.items():
            idx = _as_index(k, 0, len(SERVO_NAMES) - 1)
            angle = _as_float(v, 0.0, 180.0, None)
            if idx is None or angle is None:
                return jsonify({"error": f"servos 항목이 잘못되었습니다: {k}: {v}"}), 400
            clean[idx] = angle
        dog_cont.pose_servos(duration, clean)
        return jsonify({"status": "success"})

    # 전체 포즈
    angles = data.get("angles")
    if not isinstance(angles, list) or len(angles) != len(SERVO_NAMES):
        return jsonify({"error": f"angles는 {len(SERVO_NAMES)}개여야 합니다."}), 400
    clean = [_as_float(a, 0.0, 180.0, None) for a in angles]
    if any(a is None for a in clean):
        return jsonify({"error": "angles에 숫자가 아닌 값이 있습니다."}), 400
    dog_cont.pose(duration, clean)
    return jsonify({"status": "success"})


@app.route('/api/motion/current_pose', methods=['GET'])
def api_motion_current_pose():
    """
    현재 자세 캡처. source=present(기본): 서보 실측값 (토크 끄고 손으로 잡은 자세도 읽힘)
    source=goal: ESP32의 마지막 목표 각도
    응답 없는 서보가 있으면 503 + reason="servo" + failed=[인덱스...] (틀린 값을 주지 않음)
    """
    source = 'goal' if request.args.get('source') == 'goal' else 'present'
    if motion_cont.is_playing():
        motion_cont.stop(to_home=False)  # 움직이는 중에는 자세를 읽을 수 없다
    try:
        angles = dog_cont.read_pose(source)
    except dog_cont.ServoReadError as e:
        return jsonify({"error": str(e), "reason": "servo", "failed": e.failed}), 503
    if angles is None:
        return jsonify({"error": "로봇에서 자세를 읽지 못했습니다. (ESP32 연결 확인)",
                        "reason": "no_reply"}), 503
    return jsonify({"angles": angles})


@app.route('/api/motion/torque', methods=['POST'])
def api_motion_torque():
    """토크 켜기/끄기 (끄면 손으로 자세를 잡을 수 있다). 재생 중이면 먼저 멈춘다."""
    data = _json_dict()
    on = _as_bool(data.get("on"))
    if motion_cont.is_playing():
        motion_cont.stop(to_home=False)
    if on:
        dog_cont.enable_torque()
    else:
        dog_cont.release_torque()
    return jsonify({"status": "success", "torque_on": on})


# ==================== 화살표 키 바인딩 API ====================

@app.route('/api/keybindings', methods=['GET'])
def api_keybindings_get():
    return jsonify(key_cont.get_bindings())


@app.route('/api/keybindings', methods=['POST'])
def api_keybindings_set():
    data = _json_dict()
    try:
        key_cont.set_bindings(data)
        return jsonify({"status": "success", "bindings": key_cont.get_bindings()})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ==================== 메인 실행 ====================

if __name__ == "__main__":
    print("로봇 시스템 초기화를 시작합니다...")

    dog_cont.init()                                # ESP32 시리얼 연결
    camera.start()                                 # 카메라 스트림
    util.start_system_info(INFO_UPDATE_INTERVAL)   # 시스템 정보 수집
    motion_cont.ensure_default_motions()           # "예제 걷기" 기본 동작 생성/캘리브레이션 변경 시 갱신
    key_cont.start_hold_watchdog()                 # 조종 keep-alive 워치독

    # 부팅 시 기준 자세(캘리브레이션 각도)로 맞추고 토크를 켠다.
    # align_90.py 등 조립 유틸리티는 종료 시 토크를 해제해 손으로 자세를 만질 수
    # 있게 두므로, 여기서 다시 기준 자세로 부드럽게 이동하며 토크를 켠다.
    if dog_cont.HARDWARE_AVAILABLE:
        time.sleep(0.5)
        print("기준 자세(캘리브레이션 각도)로 정렬하고 토크를 켭니다...")
        dog_cont.pose_home()

    print(f"웹 서버를 시작합니다. http://<라즈베리파이_IP>:{WEB_PORT}")
    print(f"  - 조종:        http://<IP>:{WEB_PORT}/")
    print(f"  - 캘리브레이션: http://<IP>:{WEB_PORT}/calibration")
    print(f"  - 동작 편집:    http://<IP>:{WEB_PORT}/motion")

    try:
        app.run(host='0.0.0.0', port=WEB_PORT, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("프로그램 종료 중...")
    finally:
        motion_cont.stop(to_home=False)
        dog_cont.release_torque()
        print("모든 장치가 비활성화되었습니다. 종료.")
