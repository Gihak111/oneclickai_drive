# stream_pi.py

from flask import Flask, Response, render_template_string, request, jsonify
from flask_cors import CORS
from key_cont import handle_key
from camera_stream import camera, HEADERS_NO_CACHE
import motor_cont
import servo_cont

servo_cont.init_servos()

app = Flask(__name__)
CORS(app)


HTML_PAGE = """
<!doctype html>
<title>Raspberry Pi Camera</title>
<meta name="viewport" content="width=device-width,initial-scale=1" />
<h2>Raspberry Pi Camera (MJPEG)</h2>
<img src="/stream.mjpg" style="max-width:100%;border:1px solid #ccc" />

<div style="margin-top:12px;font-family:sans-serif">
  <div style="margin-top:12px;display:flex;gap:10px;justify-content:center">
    <button id="btnUp" onmousedown="press('ArrowUp')" onmouseup="release('ArrowUp')" ontouchstart="press('ArrowUp')" ontouchend="release('ArrowUp')">↑</button>
  </div>
  <div style="display:flex;gap:10px;justify-content:center">
    <button id="btnLeft" onmousedown="press('ArrowLeft')" onmouseup="release('ArrowLeft')" ontouchstart="press('ArrowLeft')" ontouchend="release('ArrowLeft')">←</button>
    <button id="btnDown" onmousedown="press('ArrowDown')" onmouseup="release('ArrowDown')" ontouchstart="press('ArrowDown')" ontouchend="release('ArrowDown')">↓</button>
    <button id="btnRight" onmousedown="press('ArrowRight')" onmouseup="release('ArrowRight')" ontouchstart="press('ArrowRight')" ontouchend="release('ArrowRight')">→</button>
  </div>

  <hr style="margin:16px 0">
  <div style="font-weight:bold;margin-bottom:8px">서보 제어 (키보드: Q/A, W/S, E/D)</div>
  <div style="display:flex;gap:16px;align-items:center">
    <div>
      <div style="text-align:center;font-size:12px">Servo 0</div>
      <div style="display:flex;flex-direction:column;gap:4px">
        <button onclick="moveServo(0,1)">▲</button>
        <button onclick="moveServo(0,-1)">▼</button>
      </div>
    </div>
    <div>
      <div style="text-align:center;font-size:12px">Servo 1</div>
      <div style="display:flex;flex-direction:column;gap:4px">
        <button onclick="moveServo(1,1)">▲</button>
        <button onclick="moveServo(1,-1)">▼</button>
      </div>
    </div>
    <div>
      <div style="text-align:center;font-size:12px">Servo 2</div>
      <div style="display:flex;flex-direction:column;gap:4px">
        <button onclick="moveServo(2,1)">▲</button>
        <button onclick="moveServo(2,-1)">▼</button>
      </div>
    </div>
    <div id="servoAngles" style="font-size:12px;color:#555"></div>
  </div>
</div>

<script>
let pressed = new Set();
function postKeys(){
  fetch('/keys', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ keys: Array.from(pressed) })
  });
}
document.addEventListener("keydown", (e) => {
  if (e.repeat) return;
  const k = e.key;
  if (["ArrowUp","ArrowLeft","ArrowDown","ArrowRight"].includes(k)) {
    e.preventDefault(); pressed.add(k); postKeys();
  }
  if (["q","a","w","s","e","d"].includes(k.toLowerCase())) {
    pressed.add(k); postKeys();
  }
});
document.addEventListener("keyup", (e) => {
  const k = e.key;
  if (["ArrowUp","ArrowLeft","ArrowDown","ArrowRight"].includes(k)) {
    pressed.delete(k); postKeys();
  }
  if (["q","a","w","s","e","d"].includes(k.toLowerCase())) {
    pressed.delete(k); postKeys();
  }
});
window.addEventListener("blur", () => { if (pressed.size){ pressed.clear(); postKeys(); }});
function press(k){
  if (!pressed.has(k)) { pressed.add(k); postKeys(); }
}
function release(k){
  if (pressed.has(k)) { pressed.delete(k); postKeys(); }
}
function moveServo(channel, direction) {
  fetch('/servo', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel: channel, direction: direction })
  }).then(r => r.json()).then(data => {
    if (data.angles) {
      document.getElementById('servoAngles').textContent =
        'S0:' + data.angles[0] + '° S1:' + data.angles[1] + '° S2:' + data.angles[2] + '°';
    }
  });
}
</script>
"""

# Flask 라우트
@app.route("/")
def index():
  return render_template_string(HTML_PAGE)

@app.route("/ping", methods=["GET", "HEAD"])
def ping():
    return 'auto', 200

@app.route("/servo", methods=["POST"])
def servo():
  data = request.get_json(silent=True) or {}
  channel = data.get("channel", 0)
  direction = data.get("direction", 0)
  servo_cont.move_servo(channel, direction)
  return jsonify({"ok": 1, "angles": servo_cont.get_angles()})

@app.route("/set_params", methods=["POST"])
def set_params():
  data = request.get_json(silent=True) or {}
  go = data.get("go_output", motor_cont.go_output)
  motor_cont.set_params(go)
  return jsonify({"ok": 1})

@app.route("/stream.mjpg")
def stream():
  return Response(
    camera.mjpeg_generator(),
    mimetype="multipart/x-mixed-replace; boundary=frame",
    headers=HEADERS_NO_CACHE
  )

@app.route("/keys", methods=["POST"])
def keys():
  data = request.get_json(silent=True) or {}
  keys = data.get("keys", [])
  handle_key(keys)
  return jsonify({"ok": 1})

if __name__ == "__main__":
  camera.start()
  app.run(host="0.0.0.0", port=8080, threaded=True, use_reloader=False)
