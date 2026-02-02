from flask import Flask, Response, render_template_string, request, jsonify
from flask_cors import CORS
from camera_stream import camera, HEADERS_NO_CACHE
import logic_cont # 키 입력 처리
import arm_cont   # 하드웨어 제어

app = Flask(__name__)
CORS(app)

# =================================================================
# --- 0. 대시보드 UI (A/D, W/S, G/H 반전 적용됨) ---
# =================================================================
HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RPi Robot Controller</title>
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; text-align: center; margin: 0; padding: 20px; }
        h1 { color: #4CAF50; margin-bottom: 5px; }
        .container { max-width: 900px; margin: 0 auto; }
        
        .top-section { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; margin-bottom: 20px; }
        .video-box { border: 2px solid #333; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.5); max-width: 480px; }
        img { width: 100%; display: block; }
        .status-box { flex: 1; background: #1e1e1e; padding: 20px; border-radius: 10px; min-width: 250px; text-align: left; }

        .control-panel { background: #222; padding: 20px; border-radius: 15px; border: 1px solid #444; margin-bottom: 20px; }
        .control-row { display: flex; align-items: center; justify-content: center; margin: 10px 0; gap: 10px; flex-wrap: wrap; }
        .label { width: 100px; font-weight: bold; color: #bbb; text-align: right; margin-right: 10px; }
        
        button { 
            padding: 10px 15px; font-size: 14px; border: none; border-radius: 5px; 
            cursor: pointer; color: white; transition: 0.2s; min-width: 60px; font-weight: bold;
        }
        button:active { transform: scale(0.95); opacity: 0.8; }
        .btn-move { background: #2196F3; } 
        .btn-grip { background: #E91E63; } 
        
        input[type=number] { width: 60px; padding: 8px; text-align: center; background: #333; border: 1px solid #555; color: white; border-radius: 5px; }
        
        .key-hint { font-size: 0.8em; color: #888; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Raspberry Pi Controller</h1>
        <p style="color:#aaa; margin-bottom: 20px;">Frontend Control & Dashboard</p>

        <div class="top-section">
            <div class="video-box">
                <img src="/stream.mjpg" alt="Camera Stream" />
            </div>
            <div class="status-box">
                <h3>System Status</h3>
                <p>⚡ <strong>Server:</strong> <span id="ping-badge" style="color:#4CAF50">Checking...</span></p>
                <p>🎮 <strong>Last Command:</strong> <span id="last-cmd">-</span></p>
                <p>🛰 <strong>Angles:</strong> <span id="angles">-</span></p>
                <div class="key-hint">
                    <h4>⌨️ Keyboard Shortcuts</h4>
                    <ul>
                        <li><strong>W / S</strong> : Shoulder (Up/Down)</li>
                        <li><strong>A / D</strong> : Base (Left/Right)</li>
                        <li><strong>R / F</strong> : Elbow (Up/Down)</li>
                        <li><strong>G / H</strong> : Gripper (Grab/Open)</li>
                    </ul>
                </div>
            </div>
        </div>

        <div class="control-panel">
            <h3>Manual Control</h3>
            
            <div class="control-row">
                <span class="label">Base (좌우)</span>
                <button class="btn-move" onclick="move('base', 30)">-30°</button>
                <button class="btn-move" onclick="move('base', 5)">-5°</button>
                <input type="number" id="val_base" value="10">
                <button class="btn-move" onclick="customMove('base', 1)">◀ Custom</button>
                <button class="btn-move" onclick="customMove('base', -1)">Custom ▶</button>
                <button class="btn-move" onclick="move('base', -5)">+5°</button>
                <button class="btn-move" onclick="move('base', -30)">+30°</button>
            </div>

            <div class="control-row">
                <span class="label">Shoulder (어깨)</span>
                <button class="btn-move" onclick="move('shoulder', 30)">-30°</button>
                <button class="btn-move" onclick="move('shoulder', 5)">-5°</button>
                <input type="number" id="val_shoulder" value="10">
                <button class="btn-move" onclick="customMove('shoulder', 1)">▼ Custom</button>
                <button class="btn-move" onclick="customMove('shoulder', -1)">Custom ▲</button>
                <button class="btn-move" onclick="move('shoulder', -5)">+5°</button>
                <button class="btn-move" onclick="move('shoulder', -30)">+30°</button>
            </div>

            <div class="control-row">
                <span class="label">Elbow (팔꿈치)</span>
                <button class="btn-move" onclick="move('elbow', -30)">-30°</button>
                <button class="btn-move" onclick="move('elbow', -5)">-5°</button>
                <input type="number" id="val_elbow" value="10">
                <button class="btn-move" onclick="customMove('elbow', -1)">▼ Custom</button>
                <button class="btn-move" onclick="customMove('elbow', 1)">Custom ▲</button>
                <button class="btn-move" onclick="move('elbow', 5)">+5°</button>
                <button class="btn-move" onclick="move('elbow', 30)">+30°</button>
            </div>

            <div class="control-row">
                <span class="label">Gripper (집게)</span>
                <button class="btn-grip" onclick="move('gripper', 20)">Open (H)</button>
                <button class="btn-grip" onclick="move('gripper', -20)">Grab (G)</button>
            </div>

            <div class="control-row" style="border-top: 1px solid #333; padding-top: 10px; margin-top: 15px;">
                <span class="label">Absolute Set</span>
                <input type="number" id="abs_base" placeholder="Base" min="0" max="180">
                <input type="number" id="abs_shoulder" placeholder="Shoulder" min="0" max="180">
                <input type="number" id="abs_elbow" placeholder="Elbow" min="0" max="180">
                <input type="number" id="abs_gripper" placeholder="Gripper" min="0" max="180">
                <button class="btn-move" onclick="setServo()">Set</button>
            </div>
        </div>

    </div>

    <script>
        function move(joint, angle) {
            fetch('/set_servo_relative', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ joint: joint, angle: parseFloat(angle) })
            }).then(r => {
                document.getElementById('last-cmd').textContent = `${joint} moved`;
            });
        }

        function customMove(joint, sign) {
            const val = document.getElementById('val_' + joint).value;
            if(val) move(joint, parseFloat(val) * sign);
        }

        const keyMap = {
            'w': 'shoulder_up', 's': 'shoulder_down',
            'a': 'base_left', 'd': 'base_right',
            'r': 'elbow_up', 'f': 'elbow_down',
            'g': 'grab', 'h': 'open'
        };
        
        let pressedKeys = new Set();
        let keyInterval = null;

        document.addEventListener('keydown', (e) => {
            const k = e.key.toLowerCase();
            if (keyMap[k] && !pressedKeys.has(k)) {
                pressedKeys.add(k);
                sendKeySignal();
                if (!keyInterval) keyInterval = setInterval(sendKeySignal, 100);
            }
        });

        document.addEventListener('keyup', (e) => {
            const k = e.key.toLowerCase();
            if (pressedKeys.has(k)) {
                pressedKeys.delete(k);
                if (pressedKeys.size === 0) {
                    clearInterval(keyInterval);
                    keyInterval = null;
                }
            }
        });

        function sendKeySignal() {
            if (pressedKeys.size === 0) return;
            const keys = Array.from(pressedKeys);
            fetch('/keys', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ keys: keys })
            }).then(() => {
                document.getElementById('last-cmd').textContent = "Keys: " + keys.join(',');
            });
        }

        setInterval(() => {
            fetch('/ping').then(r => {
                const badge = document.getElementById('ping-badge');
                if(r.ok) { badge.textContent = "ONLINE"; badge.style.color = "#4CAF50"; }
                else { badge.textContent = "ERROR"; badge.style.color = "red"; }
            }).catch(() => {
                const badge = document.getElementById('ping-badge');
                badge.textContent = "OFFLINE";
                badge.style.color = "red";
            });
        }, 2000);

        setInterval(() => {
            fetch('/get_servo')
                .then(r => r.json())
                .then(data => {
                    const a = data || {};
                    document.getElementById('angles').textContent = `base ${a.base ?? '-'} / shoulder ${a.shoulder ?? '-'} / elbow ${a.elbow ?? '-'} / gripper ${a.gripper ?? '-'}`;
                })
                .catch(() => {
                    document.getElementById('angles').textContent = '-';
                });
        }, 500);

        function setServo() {
            const entries = {
                base: parseFloat(document.getElementById('abs_base').value),
                shoulder: parseFloat(document.getElementById('abs_shoulder').value),
                elbow: parseFloat(document.getElementById('abs_elbow').value),
                gripper: parseFloat(document.getElementById('abs_gripper').value),
            };
            const payload = {};
            for (const [k, v] of Object.entries(entries)) {
                if (Number.isFinite(v)) payload[k] = v;
            }
            if (Object.keys(payload).length === 0) return;

            fetch('/set_servo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }).then(() => {
                document.getElementById('last-cmd').textContent = 'Set: ' + Object.entries(payload).map(([k,v]) => `${k}=${v}`).join(', ');
            });
        }
    </script>
</body>
</html>
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
    speed = data.get("speed", 2.0)
    arm_cont.set_params(step_size=speed)
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
    logic_cont.handle_key(keys_list)
    return jsonify({"ok": 1, "processed": keys_list})


@app.route("/get_servo", methods=["GET"])
def get_servo():
    return jsonify(arm_cont.get_servo())


@app.route("/set_servo", methods=["POST"])
def set_servo():
    """프론트엔드에서 전달된 각도를 절대값으로 설정"""
    data = request.get_json(silent=True) or {}

    for joint in ["base", "shoulder", "elbow", "gripper"]:
        if joint in data and data[joint] is not None:
            try:
                arm_cont.set_target_absolute(joint, float(data[joint]))
            except (ValueError, TypeError):
                return jsonify({"error": f"Invalid angle for {joint}"}), 400

    return jsonify({"ok": 1})


if __name__ == "__main__":
    camera.start()
    print(">>> RPi Server Started at port 8080")
    app.run(host="0.0.0.0", port=8080, threaded=True, use_reloader=False)
