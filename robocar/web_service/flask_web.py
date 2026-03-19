# stream_pi.py

from flask import Flask, Response, render_template_string, request, jsonify
from flask_cors import CORS
from key_cont import handle_key
from camera_stream import camera, HEADERS_NO_CACHE
import motor_cont
import arm_cont as arm_cont

arm_cont.init_servos()

app = Flask(__name__)
CORS(app, max_age=300)


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
  <div style="font-weight:bold;margin-bottom:8px">서보 제어 (키보드: Q/A, W/S, E/D, R/F)</div>

  <div style="display:flex;flex-direction:column;gap:8px;max-width:480px">
    <div style="display:flex;align-items:center;gap:8px">
      <span style="width:60px;font-size:13px">Base</span>
      <input type="range" min="0" max="180" value="90" id="slider_base" oninput="onSlider('base',this.value)" style="flex:1">
      <input type="number" min="0" max="180" value="90" id="num_base" oninput="onNumber('base',this.value)" style="width:50px;text-align:center">°
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="width:60px;font-size:13px">Shoulder</span>
      <input type="range" min="0" max="180" value="90" id="slider_shoulder" oninput="onSlider('shoulder',this.value)" style="flex:1">
      <input type="number" min="0" max="180" value="90" id="num_shoulder" oninput="onNumber('shoulder',this.value)" style="width:50px;text-align:center">°
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="width:60px;font-size:13px">Elbow</span>
      <input type="range" min="0" max="180" value="90" id="slider_elbow" oninput="onSlider('elbow',this.value)" style="flex:1">
      <input type="number" min="0" max="180" value="90" id="num_elbow" oninput="onNumber('elbow',this.value)" style="width:50px;text-align:center">°
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="width:60px;font-size:13px">Gripper</span>
      <input type="range" min="0" max="180" value="90" id="slider_gripper" oninput="onSlider('gripper',this.value)" style="flex:1">
      <input type="number" min="0" max="180" value="90" id="num_gripper" oninput="onNumber('gripper',this.value)" style="width:50px;text-align:center">°
    </div>
  </div>

  <div id="servoAngles" style="font-size:12px;color:#555;margin-top:8px"></div>
</div>

<script>
const ARROW_KEYS = ["ArrowUp","ArrowLeft","ArrowDown","ArrowRight"];
const SERVO_KEYS = ["q","a","w","s","e","d","r","f"];
let pressed = new Set();
let keyTimer = null;
function sendKeys() {
  if (!pressed.size) return;
  fetch('/keys', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({keys: [...pressed]})});
}
document.addEventListener("keydown", (e) => {
  const k = e.key;
  if (ARROW_KEYS.includes(k)) { e.preventDefault(); }
  if (ARROW_KEYS.includes(k) || SERVO_KEYS.includes(k.toLowerCase())) {
    if (!pressed.has(k)) {
      pressed.add(k); sendKeys();
      if (!keyTimer) keyTimer = setInterval(sendKeys, 100);
    }
  }
});
document.addEventListener("keyup", (e) => {
  const k = e.key;
  pressed.delete(k);
  if (pressed.size === 0) { clearInterval(keyTimer); keyTimer = null; sendStop(); }
});
window.addEventListener("blur", () => { pressed.clear(); clearInterval(keyTimer); keyTimer = null; sendStop(); });
function press(k){
  if (!pressed.has(k)) { pressed.add(k); sendKeys(); if (!keyTimer) keyTimer = setInterval(sendKeys, 100); }
}
function release(k){
  pressed.delete(k);
  if (pressed.size === 0) { clearInterval(keyTimer); keyTimer = null; sendStop(); }
}
function sendStop() {
  fetch('/keys', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({keys: []})});
}
function setAbsolute(joint, angle) {
  angle = Math.max(0, Math.min(180, parseFloat(angle)));
  fetch('/set_servo', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ [joint]: angle })
  });
}
function onSlider(joint, val) {
  document.getElementById('num_' + joint).value = val;
  setAbsolute(joint, val);
}
function onNumber(joint, val) {
  const v = Math.max(0, Math.min(180, parseFloat(val) || 0));
  document.getElementById('slider_' + joint).value = v;
  setAbsolute(joint, v);
}

// 서보 상태 폴링
let dragging = null;
['base','shoulder','elbow','gripper'].forEach(j => {
  document.getElementById('slider_' + j).addEventListener('mousedown', () => dragging = j);
  document.getElementById('num_' + j).addEventListener('focus', () => dragging = j);
});
document.addEventListener('mouseup', () => dragging = null);
document.addEventListener('focusout', () => dragging = null);

setInterval(() => {
  fetch('/get_servo').then(r => r.json()).then(a => {
    document.getElementById('servoAngles').textContent =
      'Base:' + (a.base??'-') + '° Shoulder:' + (a.shoulder??'-') + '° Elbow:' + (a.elbow??'-') + '° Gripper:' + (a.gripper??'-') + '°';
    ['base','shoulder','elbow','gripper'].forEach(j => {
      if (dragging !== j && a[j] != null) {
        const v = Math.round(a[j]);
        document.getElementById('slider_' + j).value = v;
        document.getElementById('num_' + j).value = v;
      }
    });
  }).catch(() => {});
}, 500);
</script>
"""

# Flask 라우트
@app.route("/")
def index():
  return render_template_string(HTML_PAGE)

@app.route("/ping", methods=["GET", "HEAD"])
def ping():
    return 'auto', 200

@app.route("/get_servo", methods=["GET"])
def get_servo():
  angles = arm_cont.get_angles()
  return jsonify(dict(zip(arm_cont.JOINTS, angles)))

@app.route("/set_servo", methods=["POST"])
def set_servo():
  data = request.get_json(silent=True) or {}
  for joint in arm_cont.JOINTS:
    if joint in data and data[joint] is not None:
      arm_cont.set_angle(arm_cont.JOINTS.index(joint), float(data[joint]))
  return jsonify({"ok": 1})

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
