import time
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QCheckBox, QHBoxLayout
from PyQt6.QtGui import QImage, QPixmap, QKeyEvent
from PyQt6.QtCore import Qt
import sys
import socket
import struct
import json
import threading
import cv2
import numpy as np
import web_server  # 导入web_server，访问socketio和注册接口
from face_detect_rec import FaceDetectRec, faceDetecImgDis
from move_rec import MoveRec, recImgDis

class VideoServer(QWidget):
    def __init__(self, host='0.0.0.0', port=9999):
        super().__init__()
        self.setWindowTitle("视频流服务端")
        self.resize(640, 640)

        # 状态显示标签
        self.status_label = QLabel("等待客户端连接...")
        self.status_label.setFixedHeight(30)
        self.status_label.setStyleSheet("font-size: 14px; color: blue;")

        # 显示视频画面
        self.label = QLabel(self)
        self.label.setFixedSize(640, 480)

        # 复选框 - 人脸识别
        self.face_checkbox = QCheckBox("开启人脸识别")
        self.face_checkbox.setChecked(False)
        self.face_checkbox.stateChanged.connect(self.toggle_face_detection)

        # 复选框 - 人脸追踪（受限于人脸识别开启）
        self.track_checkbox = QCheckBox("开启人脸追踪")
        self.track_checkbox.setChecked(False)
        self.track_checkbox.setEnabled(False)
        self.track_checkbox.stateChanged.connect(self.toggle_face_tracking)

        # 复选框 - 姿态识别
        self.pose_checkbox = QCheckBox("开启姿态识别")
        self.pose_checkbox.setChecked(False)
        self.pose_checkbox.stateChanged.connect(self.toggle_pose_detection)

        # UI布局
        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.label)
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addWidget(self.face_checkbox)
        checkbox_layout.addWidget(self.track_checkbox)
        checkbox_layout.addWidget(self.pose_checkbox)
        layout.addLayout(checkbox_layout)
        self.setLayout(layout)

        # TCP监听套接字
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((host, port))
        self.sock.listen(1)
        print(f"等待客户端连接 {host}:{port} ...")

        self.conn = None
        self.addr = None
        self.running = True
        self.recv_thread = threading.Thread(target=self.accept_client, daemon=True)
        self.recv_thread.start()

        # 控制状态变量
        self.iffacedetector = 0
        self.iftrackface = 0
        self.ifposerec = 0
        self.last_track_time = 0
        self.last_direction = None

        # 加载模型
        self.face_detector = FaceDetectRec()
        print("人脸识别模型加载完成")
        self.pose_detector = MoveRec()
        print("姿态识别模型加载完成")

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

        # 注册PyQt实例到web_server
        web_server.register_pyqt_server(self)
        # 启动Web服务线程
        threading.Thread(target=web_server.start_flask_server, daemon=True).start()

        # 绑定web_server的socketio事件回调，实现命令接收
        web_server.socketio.on_event('send_command', self.handle_web_command)

    # 人脸识别开关切换，带同步Web端
    def toggle_face_detection(self, state):
        self.iffacedetector = 1 if state == Qt.CheckState.Checked.value else 0
        self.track_checkbox.setEnabled(self.iffacedetector == 1)
        if self.iffacedetector == 0:
            self.track_checkbox.setChecked(False)
        web_server.update_flag_from_pyqt('face', self.iffacedetector == 1)

    # 人脸追踪开关切换，带同步Web端
    def toggle_face_tracking(self, state):
        self.iftrackface = 1 if state == Qt.CheckState.Checked.value else 0
        web_server.update_flag_from_pyqt('track', self.iftrackface == 1)

    # 姿态识别开关切换，带同步Web端
    def toggle_pose_detection(self, state):
        self.ifposerec = 1 if state == Qt.CheckState.Checked.value else 0
        web_server.update_flag_from_pyqt('pose', self.ifposerec == 1)

    def accept_client(self):
        self.conn, self.addr = self.sock.accept()
        self.status_label.setText(f"客户端已连接: {self.addr}")
        try:
            while self.running:
                length_bytes = self.recvall(4)
                if not length_bytes:
                    break
                packet_length = struct.unpack('!I', length_bytes)[0]
                packet_data = self.recvall(packet_length)
                if not packet_data:
                    break

                # 处理可能是JSON状态信息
                try:
                    text = packet_data.decode('utf-8')
                    info = json.loads(text)
                    if info.get("cmd") == "status_update":
                        self.update_status(info)
                        continue
                except:
                    pass

                # 解码图像数据
                np_arr = np.frombuffer(packet_data, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                if frame is None:
                    continue

                # 人脸识别及追踪
                if self.iffacedetector == 1:
                    face_mask_pricet = self.face_detector.inference(frame)
                    frame, _ = faceDetecImgDis(frame, face_mask_pricet)
                    if self.iftrackface == 1:
                        now = time.time()
                        if now - self.last_track_time > 0.25:
                            direction = self.get_face_direction(frame, face_mask_pricet)
                            if direction != self.last_direction:
                                self.send_command({'cmd': 'key', 'key': 'stop'})
                                if direction != 'stop':
                                    keys = direction.replace('Up', 'Up ').replace('Down', 'Down ').split()
                                    for k in keys:
                                        self.send_command({'cmd': 'key', 'key': k})
                                self.last_direction = direction
                                self.last_track_time = now

                # 姿态识别
                if self.ifposerec == 1:
                    pose_predict = self.pose_detector.inference(frame)
                    frame, _ = recImgDis(frame, pose_predict)

                # 推送图像给Web端
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                web_server.update_frame_from_pyqt(rgb_image)

                # Qt显示
                h, w, ch = rgb_image.shape
                qt_image = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
                self.label.setPixmap(QPixmap.fromImage(qt_image))

        except Exception as e:
            print("Exception:", e)
        finally:
            if self.conn:
                self.conn.close()
                self.status_label.setText("客户端断开")

    def update_status(self, info):
        self.status_label.setText(
            f"时间: {info['time']}  温度: {info['temperature']:.2f}°C  湿度: {info['humidity']:.2f}%  CPU: {info['cpu']:.1f}%"
        )
        web_server.update_status_to_web(info)

    def get_face_direction(self, frame, predictions):
        if not predictions or len(predictions[0]) == 0:
            return "stop"
        height, width = frame.shape[:2]
        tracked_boxes = predictions[0]
        x1, y1, x2, y2, _ = max(tracked_boxes, key=lambda b: (b[2]-b[0])*(b[3]-b[1]))
        dx, dy = (x1+x2)//2 - width//2, (y1+y2)//2 - height//2
        dir_x = "Left" if dx < -width * 0.1 else "Right" if dx > width * 0.1 else ""
        dir_y = "Up" if dy < -height * 0.2 else "Down" if dy > height * 0.2 else ""
        return dir_y + dir_x if dir_x or dir_y else "stop"

    def recvall(self, n):
        data = b''
        while len(data) < n:
            packet = self.conn.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    def keyPressEvent(self, event: QKeyEvent):
        key_map = {
            Qt.Key.Key_Up: 'Up', Qt.Key.Key_Down: 'Down',
            Qt.Key.Key_Left: 'Left', Qt.Key.Key_Right: 'Right'
        }
        if event.key() in key_map and not event.isAutoRepeat():
            self.send_command({'cmd': 'key', 'key': key_map[event.key()]})

    def keyReleaseEvent(self, event: QKeyEvent):
        if not event.isAutoRepeat():
            self.send_command({'cmd': 'key', 'key': 'stop'})

    def send_command(self, cmd_dict):
        try:
            msg = json.dumps(cmd_dict).encode('utf-8')
            self.conn.sendall(struct.pack('!I', len(msg)) + msg)
        except:
            pass

    def handle_web_command(self, data):
        # Web端发来的控制命令
        cmd = data.get('key') or data.get('cmd')
        if cmd is None:
            return
        print(f"[Web->PyQt] 收到控制命令: {cmd}")
        if cmd.lower() == 'stop':
            self.send_command({'cmd': 'key', 'key': 'stop'})
        elif cmd in ['Up', 'Down', 'Left', 'Right']:
            self.send_command({'cmd': 'key', 'key': cmd})
        else:
            print(f"未知命令: {cmd}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    server = VideoServer()
    server.show()
    sys.exit(app.exec())
