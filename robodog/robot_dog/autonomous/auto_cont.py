"""
자율주행 제어 모듈 — autonomous_examples 의 main.py(제어 루프) + keyboard_cont.py(플래그)
+ motor_cont.py(구동)에 해당한다.

예제는 카메라/키보드/모터를 직접 잡는 별도 프로그램이었지만, 로봇개는 카메라(camera_stream)와
시리얼 포트(dog_cont)를 웹 서버가 갖고 있으므로 웹 서버 안의 세 번째 모드로 동작한다.

  예제                        로봇개
  key.manual == 0             _state["auto"]              자율주행 ON
  (예제는 매 틱 drive() 호출)  명령이 바뀔 때만 input_cmd()  아래 "보행 명령" 참고
  key.save_flag               _state["saving"]            학습 이미지 저장 ON
  key.brake_flag              _state["brake"]             브레이크(정지 라벨)
  key.go/left/right_flag      dog_cont.current_move()     웹 조종이 이미 갖고 있는 이동 상태
  motor_cont.drive(...)       dog_cont.input_cmd(fb, lr)
  camera.get_pred_image()     camera.get_frame() + camera_capture.preprocess()

동작 흐름 (워커 스레드 1개, 예제의 제어 루프와 같은 주기):
  프레임 받기 -> 전처리 -> [자율주행이면] 모델 예측 -> 이동 명령
             -> [저장 ON + 버튼을 누르고 있으면] 그 버튼의 라벨로 64x64 이미지 저장
                (누르는 순간 1장 바로, 계속 누르면 AUTO_CAPTURE_FREQ 프레임마다. 떼면 중단)

보행 명령:
  예제(RC카)는 매 틱 motor_cont.drive() 로 모터 출력을 다시 써도 됐지만, 로봇개는 다르다.
  ESP32 는 M 커맨드를 받을 때마다 보행 진입 보간을 새로 시작하므로(begin_pose_to_gait),
  같은 명령을 매 틱 보내면 진입이 끝나지 않아 제자리에서 버둥거린다. 그래서 사람이
  키보드를 쓰듯 "명령이 바뀌는 순간에만" 보낸다. 걷는 상태 유지는 ESP32 가 알아서 하고,
  통신 두절 감시는 dog_cont 의 하트비트(H, 0.5초)가 맡는다.

안전장치:
  - 자율주행 중에는 매 틱 key_cont.refresh_hold('move') 를 호출한다. 이 루프가 죽으면
    기존 keep-alive 워치독(HOLD_TIMEOUT)이 로봇을 세운다.
  - 자율주행 페이지가 1초마다 touch() 를 보낸다. HOLD_TIMEOUT 동안 끊기면(탭 종료, WiFi
    끊김) 자율주행과 저장을 스스로 멈춘다.
  - 수동 조종/동작 재생/캘리브레이션 진입은 flask_web 이 stop_auto() 를 먼저 부른다.
"""
import os
import threading
import time

import cv2
import numpy as np

import dog_cont
import key_cont
from camera_stream import camera
from config import (AUTO_MODEL_PATH, AUTO_LABELS_PATH, AUTO_CONTROL_LOOP_SLEEP,
                    AUTO_CAPTURE_FREQ, HOLD_TIMEOUT)
from autonomous import camera_capture

# 라벨 이름 -> 이동 명령 (fb, lr). 예제 motor_cont.drive() 의 go/left/right/brake 에 해당.
# left/right 는 "전진하면서 그쪽으로 도는" 명령 (펌웨어 gait 방향각 ±30도).
ACTION_TO_MOVE = {"go": (1, 0), "left": (1, -1), "right": (1, 1), "brake": (0, 0)}

_lock = threading.Lock()
_thread = None
_model = None            # (interpreter, input_detail, output_detail, labels)
_last_page_alive = 0.0   # 페이지 keep-alive 마지막 시각 (monotonic)
_preview = None          # 최신 전처리 결과 (화면용 프레임)

_state = {
    "auto": False,
    "saving": False,
    "brake": False,
    "action": None,        # 마지막 예측 라벨
    "probs": {},           # 라벨별 확률
    "fps": 0.0,
    "counts": None,        # 라벨별 누적 이미지 장수 (None = 아직 폴더를 안 읽음)
    "saved_session": 0,    # 이번 실행에서 저장한 장수
    "label_now": None,     # 지금 저장 중인 라벨 (누르고 있는 버튼)
    "frame_ok": False,     # 카메라 프레임을 받고 있는지
    "model_loaded": False,
    "model_error": None,
}


# ==================== 상태 조회 / keep-alive ====================

def refresh_counts():
    """image/ 폴더를 읽어 라벨별 누적 장수를 갱신한다. 갱신된 dict 반환."""
    counts = camera_capture.count_images()
    with _lock:
        _state["counts"] = counts
    return counts


def get_status():
    if _state["counts"] is None:   # 페이지를 처음 열었을 때 한 번만 폴더를 읽는다
        refresh_counts()
    with _lock:
        st = dict(_state)
        st["counts"] = dict(_state["counts"] or {})
    st["model_path"] = AUTO_MODEL_PATH
    st["labels"] = list(_model[3]) if _model else []
    return st


def is_auto():
    return _state["auto"]


def touch():
    """자율주행 페이지 keep-alive. HOLD_TIMEOUT 동안 안 오면 워커가 스스로 멈춘다."""
    global _last_page_alive
    _last_page_alive = time.monotonic()


def get_preview_jpeg():
    """모델 입력 미리보기(전처리 결과)를 JPEG 으로. 프레임이 없으면 None."""
    with _lock:
        frame = _preview
    if frame is None:
        return None
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    return buf.tobytes() if ok else None


# ==================== 모델 ====================

def _interpreter_class():
    """가벼운 것부터: tflite_runtime -> ai_edge_litert(tf.lite 후속) -> tensorflow"""
    try:
        from tflite_runtime.interpreter import Interpreter
        return Interpreter
    except ImportError:
        pass
    try:
        from ai_edge_litert.interpreter import Interpreter
        return Interpreter
    except ImportError:
        pass
    try:
        import tensorflow as tf
        return tf.lite.Interpreter
    except ImportError:
        raise RuntimeError(
            "tflite 실행 라이브러리가 없습니다. 라즈베리파이: "
            "sudo apt install python3-tflite-runtime  (PC: pip install tensorflow)")


def _load_interpreter(path):
    """
    tflite 인터프리터 생성. 경로가 아니라 파일 내용을 넘긴다 — TFLite 의 C++ 로더는
    Windows 에서 한글 등 비ASCII 경로를 열지 못한다 ("Could not open ...").
    """
    with open(path, "rb") as f:
        content = f.read()
    itp = _interpreter_class()(model_content=content)
    itp.allocate_tensors()
    return itp


def _read_labels(n_outputs):
    """labels.txt('0 go' 형식) -> 출력 인덱스 순서의 라벨 이름 리스트"""
    names = {}
    if os.path.exists(AUTO_LABELS_PATH):
        with open(AUTO_LABELS_PATH, encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[0].isdigit():
                    names[int(parts[0])] = parts[1]
    return [names.get(i, f"class{i}") for i in range(n_outputs)]


def load_model():
    """모델 + 라벨 로드. 성공하면 True, 실패하면 model_error 에 이유를 남기고 False."""
    global _model
    with _lock:
        if _state["auto"]:
            _state["model_error"] = "자율주행 중에는 모델을 다시 불러올 수 없습니다. 먼저 정지하세요."
            return False
        try:
            if not os.path.exists(AUTO_MODEL_PATH):
                raise FileNotFoundError(
                    f"모델 파일이 없습니다: {AUTO_MODEL_PATH} (model/model.py 로 학습하세요)")
            itp = _load_interpreter(AUTO_MODEL_PATH)
            inp = itp.get_input_details()[0]
            out = itp.get_output_details()[0]
            labels = _read_labels(int(out["shape"][-1]))
            _model = (itp, inp, out, labels)
            _state.update(model_loaded=True, model_error=None)
            print(f"[auto_cont] 모델 로드: {AUTO_MODEL_PATH}  라벨={labels}")
            return True
        except Exception as e:
            _model = None
            _state.update(model_loaded=False, model_error=str(e))
            print(f"[auto_cont] 모델 로드 실패: {e}")
            return False


def _predict(model_input):
    """64x64 BGR uint8 -> (라벨, {라벨: 확률}). 전처리는 학습 스크립트(model.py)와 같은 순서."""
    itp, inp, out, labels = _model
    x = np.asarray(model_input, dtype=np.float32)[np.newaxis, ...]
    x = (x / 127.5) - 1.0
    x = x[:, :, :, ::-1]  # BGR -> RGB
    itp.set_tensor(inp["index"], x.astype(inp["dtype"]))
    itp.invoke()
    probs = itp.get_tensor(out["index"])[0]
    idx = int(np.argmax(probs))
    return labels[idx], {labels[i]: round(float(p), 3) for i, p in enumerate(probs)}


# ==================== 모드 전환 ====================

def start_auto():
    """자율주행 시작. (성공 여부, 메시지)"""
    if dog_cont.calibrationMode:
        return False, "캘리브레이션 모드 중에는 자율주행을 시작할 수 없습니다."
    if _model is None and not load_model():
        return False, _state["model_error"]
    touch()
    with _lock:
        _state["auto"] = True
        _ensure_worker_locked()
    print("[auto_cont] 자율주행 시작")
    return True, "자율주행 시작"


def stop_auto():
    """자율주행 정지 + 로봇 정지. 자율주행 중이 아니면 아무것도 하지 않는다."""
    with _lock:
        was_auto = _state["auto"]
        _state["auto"] = False
        _state["action"] = None
    if was_auto:
        dog_cont.input_cmd(0, 0)
        print("[auto_cont] 자율주행 정지")


def set_saving(on):
    on = bool(on)
    if on:
        camera_capture.make_image_dirs()
        touch()
    with _lock:
        _state["saving"] = on
        if on:
            _ensure_worker_locked()
    counts = refresh_counts()   # 시작/종료 시점에 폴더를 다시 읽어 실제 장수를 맞춘다
    total = sum(counts.values())
    detail = ", ".join(f"{k} {v}" for k, v in counts.items())
    print(f"[auto_cont] 이미지 저장 {'ON' if on else 'OFF'} — 누적 {total}장 ({detail})")


def set_brake(on):
    """브레이크: 저장 라벨을 brake 로 바꾸고, 자율주행 중이면 로봇을 세운다 (예제 'b' 키)."""
    _state["brake"] = bool(on)


def stop_all():
    """페이지 이탈 / 서버 종료용: 자율주행과 저장을 모두 끈다."""
    stop_auto()
    if _state["saving"]:
        set_saving(False)


# ==================== 워커 스레드 ====================

def _ensure_worker_locked():
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_worker, daemon=True)
        _thread.start()


def _active():
    return _state["auto"] or _state["saving"]


def _save_label():
    """
    저장에 쓸 라벨 = 사람이 지금 누르고 있는 버튼. 아무것도 안 누르면 None.
    자율주행 중에는 방향키를 누르는 순간 자율주행이 꺼지므로, 사람 입력은 브레이크뿐이다
    (모델이 스스로 낸 예측을 학습 데이터로 되저장하면 틀린 판단이 굳어지므로 저장하지 않는다).
    """
    brake = _state["brake"]
    if _state["auto"]:
        return "brake" if brake else None
    fb, lr = dog_cont.current_move()
    return camera_capture.label_for_move(fb, lr, brake)


def _worker():
    """예제의 autonomous_control_loop + capture_img 를 합친 루프. auto/saving 둘 다 꺼지면 끝난다."""
    global _preview
    seq = 0
    frame_cnt = 0
    t_prev = time.monotonic()
    driving = False
    held_label = None   # 지금 저장 중인 라벨(버튼). 바뀌는 순간 바로 1장 저장한다
    held_frames = 0
    try:
        while _active():
            time.sleep(AUTO_CONTROL_LOOP_SLEEP)

            if time.monotonic() - _last_page_alive > HOLD_TIMEOUT:
                print("[auto_cont] 페이지 keep-alive 끊김 -> 자율주행/저장 정지")
                with _lock:
                    _state["auto"] = False
                    _state["saving"] = False
                break

            seq, frame = camera.get_frame(seq, wait_ms=500)
            _state["frame_ok"] = frame is not None
            if frame is None:
                continue
            display, model_input = camera_capture.preprocess(frame)
            with _lock:
                _preview = display
            frame_cnt += 1

            if _state["auto"]:
                action, probs = _predict(model_input)
                fb, lr = ACTION_TO_MOVE.get(action, (0, 0))
                if _state["brake"]:
                    fb, lr = 0, 0
                # 키보드처럼 "명령이 바뀔 때만" 보낸다 (keydown/keyup 한 번씩).
                # 매 틱 같은 M 을 다시 보내면 펌웨어가 그때마다 begin_pose_to_gait()으로
                # 보행 진입 보간(150ms)을 처음부터 다시 시작해서, 제어 주기(80ms)가 더 짧은
                # 탓에 진입이 끝나지 않는다 -> 실제 보행에 못 들어가고 제자리에서 버둥거린다.
                # 비교 기준은 dog_cont 가 마지막으로 보낸 값이라, 재연결로 초기화되면
                # (_reconnect 가 0,0 으로 되돌림) 다음 틱에 자동으로 다시 보낸다.
                if (fb, lr) != dog_cont.current_move():
                    dog_cont.input_cmd(fb, lr)
                key_cont.refresh_hold('move')   # 워치독은 계속 갱신 (시리얼 전송 없음)
                driving = True
                _state["action"] = action
                _state["probs"] = probs

            label = _save_label()
            _state["label_now"] = label
            if _state["saving"] and label:
                if label != held_label:          # 방금 눌렀다(또는 다른 키로 바뀜) -> 즉시 1장
                    held_label, held_frames = label, 0
                if held_frames % AUTO_CAPTURE_FREQ == 0:
                    fb, lr = dog_cont.current_move()
                    camera_capture.save_image(model_input, label, fb, lr, _state["brake"], frame_cnt)
                    with _lock:
                        _state["saved_session"] += 1
                        if _state["counts"] is not None:
                            _state["counts"][label] = _state["counts"].get(label, 0) + 1
                held_frames += 1
            else:
                held_label = None                # 손을 뗐다 -> 저장 중단

            now = time.monotonic()
            _state["fps"] = round(1.0 / (now - t_prev + 1e-8), 1)
            t_prev = now
    except Exception as e:
        print(f"[auto_cont] 워커 에러: {e}")
        with _lock:
            _state["auto"] = False
            _state["saving"] = False
    finally:
        if driving:
            dog_cont.input_cmd(0, 0)  # 어떤 이유로 끝나든 로봇은 세운다
        _state["frame_ok"] = False
        _state["action"] = None
        print("[auto_cont] 워커 종료")
