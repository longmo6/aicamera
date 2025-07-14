import threading
from flask import Flask, Response
from flask_socketio import SocketIO, emit
import cv2
import time
import os

# 状态标志
shared_flags = {
    'face': False,
    'track': False,
    'pose': False
}

latest_frame = None
frame_lock = threading.Lock()
pyqt_server = {'server': None}

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8" />
    <title>智能摄像头控制面板</title>
    <style>
        body {
            max-width: 1100px;
            margin: 0 auto;
            padding: 20px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-image: url('/bg_img');
            background-size: cover;
            background-position: center center;
            background-repeat: no-repeat;
            background-attachment: fixed;
            color: #333;
        }

        h1 {
    display: block;
    margin: 0 auto 20px auto;
    text-align: center;
    /* 其他样式保持 */
    font-weight: 700;
    color: white;
    background-color: rgba(0, 0, 0, 0.5);
    padding: 10px 20px;
    border-radius: 10px;
    max-width: fit-content;  /* 让宽度自适应内容 */
}

        .main-container {
            display: flex;
            gap: 40px;
            height: 520px;
        }

        /* 视频区域 */
        .video-panel {
            flex: 1;
            background: #ffffff;
            border-radius: 30px;
            border: 2px solid #a3c4f3;
            padding: 12px;
            box-shadow: 0 8px 16px rgba(200, 200, 200, 0.3);
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }

        /* 视频框 */
        .video-container {
            width: 640px;
            height: 480px;
            background: #000;
            border-radius: 22px;
            overflow: hidden;
            box-shadow: inset 0 0 30px rgba(0,0,0,0.6);
        }

        .video-container img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        /* 右侧区域 */
        .right-panel {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 40px;
            height: 100%;
        }

        /* 状态信息 */
        .info-panel {
            flex: 1;
            background: #f0f4f8;
            border-radius: 30px;
            border: 2px solid #a3c4f3;
            box-shadow: 0 8px 16px rgba(160, 160, 160, 0.25);
            padding: 24px 20px;
            font-family: 'Courier New', Courier, monospace;
            font-size: 20px;
            color: #4a4a4a;
            text-align: center;
            display: flex;
            justify-content: center;
            align-items: center;
            user-select: none;
        }

        /* 控制区域 */
        .control-panel {
            flex: 1;
            background: #f9fafc;
            border-radius: 30px;
            border: 2px solid #a3c4f3;
            box-shadow: 0 8px 16px rgba(160, 160, 160, 0.25);
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 30px;
            color: #4a4a4a;
        }

        /* 方向按钮 */
        .direction-radial button {
            border-radius: 50%;
            width: 60px;
            height: 60px;
            font-size: 20px;
            font-weight: bold;
            background: linear-gradient(45deg, #d9e4ff, #a9c1ff);
            border: none;
            color: #3a4a64;
            box-shadow: 0 4px 8px rgba(120, 140, 180, 0.3);
            transition: 0.2s;
            cursor: pointer;
        }

        .direction-radial button:hover {
            background: linear-gradient(45deg, #a9c1ff, #7b95ff);
        }

        /* 功能按钮 */
        .buttons button {
            background: linear-gradient(45deg, #cce0ff, #9bbaff);
            border: none;
            padding: 10px 20px;
            border-radius: 12px;
            font-size: 16px;
            cursor: pointer;
            color: #2f3b53;
            box-shadow: 0 4px 8px rgba(120, 140, 180, 0.3);
            transition: all 0.3s ease;
            min-width: 130px;
        }

        .buttons button:hover {
            background: linear-gradient(45deg, #9bbaff, #7b95ff);
            transform: translateY(-2px);
        }

        .buttons button.active {
            background: linear-gradient(45deg, #8fb3ff, #5478e3);
            box-shadow: 0 6px 12px rgba(70, 100, 170, 0.35);
        }

        /* 方向按钮定位 */
        .direction-radial {
            position: relative;
            width: 200px;
            height: 200px;
        }

        .direction-radial .btn-up {
            position: absolute; top: 0; left: 50%; transform: translateX(-50%);
        }

        .direction-radial .btn-down {
            position: absolute; bottom: 0; left: 50%; transform: translateX(-50%);
        }

        .direction-radial .btn-left {
            position: absolute; top: 50%; left: 0; transform: translateY(-50%);
        }

        .direction-radial .btn-right {
            position: absolute; top: 50%; right: 0; transform: translateY(-50%);
        }

        .direction-radial .center-btn {
            position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
        }

        /* 响应式 */
        @media (max-width: 1000px) {
            .main-container {
                flex-direction: column;
                height: auto;
            }
            .video-panel, .right-panel {
                flex: none;
                width: 100%;
                height: auto;
            }
            .info-panel, .control-panel {
                border-radius: 20px;
            }
            .video-container {
                width: 100%;
                height: auto;
            }
        }
    </style>
</head>
<body>
    <h1>智能摄像头控制面板</h1>
    <div class="main-container">
        <div class="video-panel">
            <div class="video-container">
                <img id="video" src="/video_feed" alt="视频流" />
            </div>
        </div>
        <div class="right-panel">
            <div class="info-panel" id="info-panel">等待设备信息...</div>
            <div class="control-panel">
                <div class="direction-radial">
                    <div class="btn-up"><button id="btn-up">↑</button></div>
                    <div class="btn-down"><button id="btn-down">↓</button></div>
                    <div class="btn-left"><button id="btn-left">←</button></div>
                    <div class="btn-right"><button id="btn-right">→</button></div>
                    <div class="center-btn"><button id="btn-stop">■</button></div>
                </div>
                <div class="buttons">
                    <button id="face-btn">人脸识别</button>
                    <button id="track-btn">人脸追踪</button>
                    <button id="pose-btn">姿态识别</button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <script>
        const socket = io();

        const buttons = {
            'face': document.getElementById('face-btn'),
            'track': document.getElementById('track-btn'),
            'pose': document.getElementById('pose-btn')
        };

        for (let flag in buttons) {
            buttons[flag].addEventListener('click', () => {
                socket.emit('toggle_flag', { flag });
            });
        }

        socket.on('flag_update', (data) => {
            for (let flag in data) {
                if (buttons[flag]) {
                    buttons[flag].classList.toggle('active', data[flag]);
                }
            }
        });

        socket.on('status_update', (data) => {
            const infoPanel = document.getElementById('info-panel');
            if (data) {
                infoPanel.textContent = `时间: ${data.time}  温度: ${data.temperature.toFixed(2)}°C  湿度: ${data.humidity.toFixed(2)}%  CPU: ${data.cpu.toFixed(1)}%`;
            } else {
                infoPanel.textContent = '等待设备信息...';
            }
        });

        socket.emit('request_flags');

        function sendCommand(cmd) {
            socket.emit('send_command', { cmd });
        }

        let pressTimers = {};

        function onButtonPress(cmd) {
            if (pressTimers[cmd]) return;
            sendCommand(cmd);
            pressTimers[cmd] = setInterval(() => {
                sendCommand(cmd);
            }, 100);
        }

        function onButtonRelease(cmd) {
            if (pressTimers[cmd]) {
                clearInterval(pressTimers[cmd]);
                pressTimers[cmd] = null;
            }
            sendCommand('stop');
        }

        const dirButtons = {
            'btn-up': 'Up',
            'btn-down': 'Down',
            'btn-left': 'Left',
            'btn-right': 'Right'
        };

        Object.entries(dirButtons).forEach(([btnId, cmd]) => {
            const btn = document.getElementById(btnId);
            btn.addEventListener('mousedown', () => onButtonPress(cmd));
            btn.addEventListener('touchstart', () => onButtonPress(cmd));
            btn.addEventListener('mouseup', () => onButtonRelease(cmd));
            btn.addEventListener('mouseleave', () => onButtonRelease(cmd));
            btn.addEventListener('touchend', () => onButtonRelease(cmd));
            btn.addEventListener('touchcancel', () => onButtonRelease(cmd));
        });

        document.getElementById('btn-stop').addEventListener('click', () => {
            Object.values(pressTimers).forEach(timer => {
                if (timer) clearInterval(timer);
            });
            pressTimers = {};
            sendCommand('stop');
        });
    </script>
</body>
</html>

    """

@app.route('/bg_img')
def bg_img():
    img_path = os.path.join(os.path.dirname(__file__), 'bj.jpg')
    if not os.path.exists(img_path):
        return '背景图片未找到', 404
    with open(img_path, 'rb') as f:
        img_data = f.read()
    return Response(img_data, mimetype='image/jpeg')

@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            with frame_lock:
                if latest_frame is not None:
                    bgr_frame = cv2.cvtColor(latest_frame, cv2.COLOR_RGB2BGR)
                    ret, jpeg = cv2.imencode('.jpg', bgr_frame)
                    if not ret:
                        continue
                    frame = jpeg.tobytes()
                else:
                    continue
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.03)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@socketio.on('toggle_flag')
def toggle_flag(data):
    flag = data.get('flag')
    if flag in shared_flags:
        shared_flags[flag] = not shared_flags[flag]
        emit('flag_update', {flag: shared_flags[flag]}, broadcast=True)
        print(f"[Web] 状态切换: {flag} => {shared_flags[flag]}")

        if pyqt_server['server']:
            state = 2 if shared_flags[flag] else 0
            if flag == 'face':
                pyqt_server['server'].toggle_face_detection(state)
            elif flag == 'track':
                pyqt_server['server'].toggle_face_tracking(state)
            elif flag == 'pose':
                pyqt_server['server'].toggle_pose_detection(state)

@socketio.on('send_command')
def send_command(data):
    print("[Web] 控制命令:", data)
    if pyqt_server['server']:
        pyqt_server['server'].handle_web_command(data)

@socketio.on('request_flags')
def send_current_flags():
    emit('flag_update', shared_flags)

def update_flag_from_pyqt(flag, state_bool):
    if flag in shared_flags:
        shared_flags[flag] = state_bool
        socketio.emit('flag_update', {flag: state_bool}, broadcast=True)

def update_status_to_web(info_dict):
    def send():
        socketio.emit('status_update', info_dict)
    socketio.start_background_task(send)

def update_frame_from_pyqt(frame):
    global latest_frame
    with frame_lock:
        latest_frame = frame

def register_pyqt_server(server):
    pyqt_server['server'] = server

def start_flask_server():
    print("[Web] Flask + Socket.IO 启动中...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
