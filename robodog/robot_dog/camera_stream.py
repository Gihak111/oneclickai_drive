"""
카메라 스트림 모듈 (example/web_service/camera_stream.py 기반)
- 라즈베리파이: picamera2, 그 외(윈도우 PC 등): OpenCV 웹캠 자동 선택
- 카메라가 없으면 안내 문구가 담긴 플레이스홀더 프레임을 스트리밍
"""
import time
import threading
import atexit

import cv2
import numpy as np

from config import CAMERA_SIZE, CAMERA_FPS, CAMERA_QUALITY, CAMERA_FLIP

try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    PICAMERA_AVAILABLE = False
    print("[camera] picamera2 없음 -> OpenCV 웹캠을 사용합니다.")

HEADERS_NO_CACHE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


class CameraStream:
    """카메라 프레임 캡처 + JPEG 변환 + MJPEG 스트림 제공"""

    def __init__(self, size=CAMERA_SIZE, fps=CAMERA_FPS, quality=CAMERA_QUALITY, flip=CAMERA_FLIP):
        self.size = size
        self.fps = max(1, int(fps))
        self.quality = int(quality)
        self.flip = flip
        self.picam2 = None
        self.cap = None
        self._thread = None
        self._running = False
        self._latest = None
        self._lock = threading.Lock()
        self._event = threading.Event()

    def start(self):
        """카메라 스트림 시작 (백그라운드 스레드로 프레임 캡처)"""
        if self._running:
            return
        print("[camera] start()", flush=True)

        if PICAMERA_AVAILABLE:
            try:
                self.picam2 = Picamera2()
                cfg = self.picam2.create_video_configuration(
                    main={"format": 'XRGB8888', "size": self.size})
                self.picam2.configure(cfg)
                self.picam2.start()
                print("[camera] picamera2 초기화 완료.")
            except Exception as e:
                print(f"[camera] picamera2 초기화 실패: {e}")
                self.picam2 = None

        if self.picam2 is None:
            try:
                self.cap = cv2.VideoCapture(0)
                if self.cap.isOpened():
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.size[0])
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.size[1])
                    print("[camera] OpenCV 웹캠 초기화 완료.")
                else:
                    self.cap = None
                    print("[camera] 사용 가능한 카메라가 없습니다. 플레이스홀더를 스트리밍합니다.")
            except Exception as e:
                self.cap = None
                print(f"[camera] 웹캠 초기화 실패: {e}")

        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        atexit.register(self.close)

    def _placeholder(self, text):
        frame = np.full((self.size[1], self.size[0], 3), 255, dtype=np.uint8)
        cv2.putText(frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        return frame

    def _capture(self):
        if self.picam2 is not None:
            frame = self.picam2.capture_array()
            return cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
        if self.cap is not None:
            ret, frame = self.cap.read()
            if ret:
                return frame
            return self._placeholder("Webcam read error")
        # 카메라 없음: CPU 과부하 방지를 위해 잠깐 대기 후 안내 프레임
        time.sleep(0.5)
        return self._placeholder("Camera not available")

    def _loop(self):
        """프레임을 주기적으로 캡처하여 JPEG으로 변환 (백그라운드 스레드)"""
        period = 1.0 / self.fps
        while self._running:
            try:
                frame = self._capture()
                if self.flip is not None:
                    frame = cv2.flip(frame, self.flip)
                ok, jpeg = cv2.imencode(
                    ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
                if ok:
                    with self._lock:
                        self._latest = jpeg.tobytes()
                    self._event.set()
            except Exception as e:
                print("[camera] capture error:", e, flush=True)
                time.sleep(0.2)
            time.sleep(period)

    def get_jpeg(self, wait_ms=800):
        """최신 JPEG 프레임 반환 (없으면 wait_ms 동안 대기)"""
        if not self._running:
            self.start()
        if not self._event.wait(timeout=wait_ms / 1000.0):
            return None
        self._event.clear()
        with self._lock:
            return self._latest

    def mjpeg_generator(self):
        """MJPEG 스트림(HTTP용) 생성 제너레이터"""
        while True:
            buf = self.get_jpeg(wait_ms=1000)
            if not buf:
                continue
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n"
                   b"Content-Length: " + str(len(buf)).encode() + b"\r\n\r\n" +
                   buf + b"\r\n")

    def close(self):
        """카메라 스트림 안전 종료"""
        if not self._running:
            return
        print("[camera] close()", flush=True)
        self._running = False
        try:
            if self.picam2:
                self.picam2.stop()
        except Exception:
            pass
        try:
            if self.cap:
                self.cap.release()
        except Exception:
            pass
        self.picam2 = None
        self.cap = None


camera = CameraStream()  # CameraStream 인스턴스 (전역, 외부에서 사용)
