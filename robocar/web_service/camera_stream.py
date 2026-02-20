# camera_stream.py
import time, threading, atexit
import cv2
from picamera2 import Picamera2

HEADERS_NO_CACHE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

class CameraStream:
    """
    라즈베리파이 카메라 스트림을 관리하는 클래스
    - 프레임 캡처, JPEG 변환, MJPEG 스트림 제공
    """
    def __init__(self, size=(480,360), fps=24, quality=80, flip=0):
        """카메라 스트림 객체 초기화 (해상도, FPS, 화질, flip 설정)"""
        self.size = size
        self.fps = max(1, int(fps))
        self.quality = int(quality)
        self.flip = flip
        self.picam2 = None
        self._thread = None
        self._running = False
        self._latest = None
        self._lock = threading.Lock()
        self._event = threading.Event()

    def start(self):
        """카메라 스트림 시작 (스레드로 프레임 캡처)"""
        if self._running:
            return
        print("[camera] start()", flush=True)
        self.picam2 = Picamera2()
        cfg = self.picam2.create_video_configuration(main={"size": self.size})
        self.picam2.configure(cfg)
        self.picam2.start()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        atexit.register(self.close)

    def _loop(self):
        """카메라 프레임을 주기적으로 캡처하여 JPEG으로 변환 (백그라운드 스레드)"""
        period = 1.0 / self.fps
        frames = 0
        while self._running:
            try:
                frame = self.picam2.capture_array() 
                frame = cv2.flip(frame, self.flip)
                frame = cv2.flip(frame, 1)
                # convert to JPEG
                ok, jpeg = cv2.imencode(
                    ".jpg",
                    cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
                    [int(cv2.IMWRITE_JPEG_QUALITY), self.quality],
                )
                if ok:
                    with self._lock:
                        self._latest = jpeg.tobytes()
                    self._event.set()
                    frames += 1
                    if frames <= 3:
                        print(f"[camera] frame #{frames} ready ({len(self._latest)} bytes)", flush=True)
                else:
                    print("[camera] imencode failed", flush=True)
            except Exception as e:
                print("[camera] capture error:", e, flush=True)
                time.sleep(0.2)
            time.sleep(period)

    def get_jpeg(self, wait_ms=800):
        """최신 JPEG 프레임 반환 (없으면 wait_ms 동안 대기)"""
        if not self._running:
            print("[camera] get_jpeg(): not running → start()", flush=True)
            self.start()
        if not self._event.wait(timeout=wait_ms/1000.0):
            print("[camera] get_jpeg(): timeout waiting frame", flush=True)
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
        self.picam2 = None

camera = CameraStream()  # CameraStream 인스턴스 (전역, 외부에서 사용)
