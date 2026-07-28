from flask import Flask, Response, render_template_string, request, jsonify
from flask_cors import CORS
from camera_stream import camera, HEADERS_NO_CACHE
import key_cont # 키 입력 처리
import arm_cont   # 하드웨어 제어

arm_cont.init_servos()

app = Flask(__name__)
CORS(app, max_age=300)

# =================================================================
# --- 0. 대시보드 UI (A/D, W/S, G/H 반전 적용됨) ---
# =================================================================
HTML_DASHBOARD = """
<!doctype html>
<title>RoboArm Controller</title>
<meta name="viewport" content="width=device-width,initial-scale=1" />
<h2>RoboArm Controller</h2>
<img src="/stream.mjpg" style="max-width:100%;border:1px solid #ccc" />

<div style="margin-top:12px;font-family:sans-serif">
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

// 키보드 제어
const KEYS = ['q','a','w','s','e','d','r','f'];
let pressed = new Set();
let keyTimer = null;
document.addEventListener('keydown', (e) => {
  const k = e.key.toLowerCase();
  if (!KEYS.includes(k) || pressed.has(k)) return;
  pressed.add(k);
  sendKeys();
  if (!keyTimer) keyTimer = setInterval(sendKeys, 100);
});
document.addEventListener('keyup', (e) => {
  pressed.delete(e.key.toLowerCase());
  if (pressed.size === 0) { clearInterval(keyTimer); keyTimer = null; }
});
window.addEventListener('blur', () => { pressed.clear(); clearInterval(keyTimer); keyTimer = null; });
function sendKeys() {
  if (!pressed.size) return;
  fetch('/keys', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({keys: [...pressed]})});
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

# =================================================================
# --- 라우팅 정의 ---
# =================================================================

@app.route("/")
def index():
    return render_template_string(HTML_DASHBOARD)

@app.route("/ping", methods=["GET"])
def ping():
    return "roboarm", 200

@app.route("/set_params", methods=["POST"])
def set_params():
    data = request.get_json(silent=True) or {}
    if "step" in data:
        try:
            arm_cont.ANGLE_STEP = int(data["step"])
        except (TypeError, ValueError):
            pass
    # 슬루 필터 최대 회전 속도(도/초) — 프론트엔드 speed 슬라이더가 여기로 반영된다
    if "speed_dps" in data:
        arm_cont.set_max_speed(data["speed_dps"])
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
    keys_list = data.get("keys", [])
    key_cont.handle_key(keys_list)
    return jsonify({"ok": 1, "processed": keys_list})


@app.route("/get_servo", methods=["GET"])
def get_servo():
    angles = arm_cont.get_angles()
    return jsonify(dict(zip(arm_cont.JOINTS, angles)))


@app.route("/set_servo", methods=["POST"])
def set_servo():
    """프론트엔드에서 전달된 각도를 절대값으로 설정"""
    data = request.get_json(silent=True) or {}

    for joint in arm_cont.JOINTS:
        if joint in data and data[joint] is not None:
            try:
                arm_cont.set_angle(arm_cont.JOINTS.index(joint), float(data[joint]))
            except (ValueError, TypeError):
                return jsonify({"error": f"Invalid angle for {joint}"}), 400

    return jsonify({"ok": 1})


if __name__ == "__main__":
    camera.start()
    print(">>> RPi Server Started at port 8080")
    app.run(host="0.0.0.0", port=8080, threaded=True, use_reloader=False)
