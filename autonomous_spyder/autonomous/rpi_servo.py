from pathlib import Path
import time

PWM_PATH_FILE = Path("/run/pwm18_path")
PERIOD_NS = 20_000_000

def _pwm():
    if not PWM_PATH_FILE.exists():
        raise RuntimeError("Run: sudo systemctl restart pwm18.service")
    return Path(PWM_PATH_FILE.read_text().strip())

def _write(name, value):
    (_pwm() / name).write_text(str(value))

def init():
    _write("period", PERIOD_NS)
    _write("duty_cycle", 1_500_000)
    _write("enable", 1)

def set_deg(angle):
    angle = max(0, min(180, angle))
    pulse_us = 500 + (angle / 180) * 2000
    _write("duty_cycle", int(pulse_us * 1000))

def stop():
    _write("enable", 0)

if __name__ == "__main__":
    init()
    for a in [0, 90, 180, 90]:
        set_deg(a)
        time.sleep(1)
    stop()
