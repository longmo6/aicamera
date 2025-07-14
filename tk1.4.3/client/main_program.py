import tkinter as tk
from tkinter import messagebox
import threading
import time
import cv2
import psutil
from PIL import Image, ImageTk
from multiprocessing.connection import Client
import os
import wiringpi
import struct
import json
from streaming_server import StreamingServer
from tcp_client import VideoCommandClient
import mediapipe as mp
import queue

# ========== wiringpi 初始化传感器 ==========
wiringpi.wiringPiSetup()
BASE = 64
wiringpi.htu21dSetup(BASE)

# ========== 初始化 ==========
pcip = '192.168.4.54'

os.makedirs("images", exist_ok=True)
os.makedirs("videos", exist_ok=True)

cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
recording = False
video_writer = None
address = ('localhost', 6000)
conn = Client(address, authkey=b'secret password')

# ======= Mediapipe 人脸检测器初始化 =======
mp_face = mp.solutions.face_detection
face_detector = mp_face.FaceDetection(model_selection=0, min_detection_confidence=0.6)

video_display_enabled = True
face_detection_enabled = False
streaming_enabled = False
tcp_enabled = False
face_tracking_enabled = False

stream_server = StreamingServer(lambda: get_stream_frame())
video_comm = VideoCommandClient(lambda: get_stream_frame(), server_ip=pcip)

# ========== 电机控制 ==========
def send_motor_command(angle1, angle2):
    try:
        conn.send({'cmd': 'rotate', 'angle1': angle1, 'angle2': angle2})
        if conn.recv().get('status') == 'done':
            print(f"电机旋转完成：{angle1}, {angle2}")
    except Exception as e:
        print("电机控制失败:", e)

# ========== 远程控制指令处理 ==========
def handle_remote_command(cmd):
    print("[收到远程指令]", cmd)
    if cmd.get("cmd") == "key":
        key = cmd.get("key")
        if key in ['Up', 'Down', 'Left', 'Right']:
            conn.send({'cmd': 'key', 'key': key})
        elif key == 'stop':
            conn.send({'cmd': 'key', 'key': 'stop'})

# ========== 异步人脸检测线程 ==========
face_detection_queue = queue.Queue(maxsize=1)
face_detection_results = None

def face_detection_worker():
    global face_detection_results
    while True:
        frame = face_detection_queue.get()
        if frame is None:
            break
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_detector.process(rgb_frame)
        face_detection_results = results

# ========== 摄像头显示 ==========
def get_stream_frame():
    ret, frame = cap.read()
    if not ret:
        return None
    frame = cv2.flip(frame, 0)
    return frame

def update_frame():
    global face_detection_results
    if video_display_enabled:
        frame = get_stream_frame()
        if frame is not None:
            h, w, _ = frame.shape
            if face_detection_enabled and face_detection_queue.empty():
                face_detection_queue.put(frame.copy())

            if face_detection_enabled and face_detection_results and face_detection_results.detections:
                face_centers = []
                for detection in face_detection_results.detections:
                    box = detection.location_data.relative_bounding_box
                    x1 = int(box.xmin * w)
                    y1 = int(box.ymin * h)
                    x2 = int((box.xmin + box.width) * w)
                    y2 = int((box.ymin + box.height) * h)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, 'Face', (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (36, 255, 12), 1)
                    cx = (x1 + x2) // 2
                    cy = (y1 + y2) // 2
                    face_centers.append((cx, cy))

                if face_tracking_enabled and face_centers:
                    face_cx, face_cy = face_centers[0]
                    offset_x = face_cx - w // 2
                    offset_y = face_cy - h // 2
                    threshold_x = w * 0.1
                    threshold_y = h * 0.1

                    direction = ""

                    if abs(offset_y) > threshold_y:
                        direction += "Down" if offset_y > 0 else "Up"
                    if abs(offset_x) > threshold_x:
                        direction += "Right" if offset_x > 0 else "Left"

                    if direction == "":
                        direction = "stop"
                        conn.send({'cmd': 'key', 'key': 'stop'})
                        print("追踪: stop")

                    if direction == "stop":
                        conn.send({'cmd': 'key', 'key': 'stop'})
                        print("追踪: stop")
                        pass
                    elif direction == "Up":
                        conn.send({'cmd': 'key', 'key': 'Up'})
                        print("追踪: Up")
                    elif direction == "Down":
                        conn.send({'cmd': 'key', 'key': 'Down'})
                        print("追踪: Down")
                    elif direction == "Left":
                        conn.send({'cmd': 'key', 'key': 'Left'})
                        print("追踪: Left")
                    elif direction == "Right":
                        conn.send({'cmd': 'key', 'key': 'Right'})
                        print("追踪: Right")
                    elif direction == "UpLeft":
                        conn.send({'cmd': 'key', 'key': 'Up'})
                        conn.send({'cmd': 'key', 'key': 'Left'})
                        print("追踪: Up + Left")
                    elif direction == "UpRight":
                        conn.send({'cmd': 'key', 'key': 'Up'})
                        conn.send({'cmd': 'key', 'key': 'Right'})
                        print("追踪: Up + Right")
                    elif direction == "DownLeft":
                        conn.send({'cmd': 'key', 'key': 'Down'})
                        conn.send({'cmd': 'key', 'key': 'Left'})
                        print("追踪: Down + Left")
                    elif direction == "DownRight":
                        conn.send({'cmd': 'key', 'key': 'Down'})
                        conn.send({'cmd': 'key', 'key': 'Right'})
                        print("追踪: Down + Right")

            if recording and video_writer:
                video_writer.write(frame)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            video_label.imgtk = imgtk
            video_label.configure(image=imgtk)
    else:
        video_label.config(image='')

    root.after(16, update_frame)


# ========== 实时信息 ==========
def update_info():
    try:
        temp_raw = wiringpi.analogRead(BASE + 0)
        humi_raw = wiringpi.analogRead(BASE + 1)
        temp = temp_raw / 10.0
        humi = humi_raw / 10.0
    except Exception as e:
        print("读取温湿度失败:", e)
        temp = 0
        humi = 0
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    cpu = psutil.cpu_percent(interval=None)
    info_text.set(f"时间: {now}   温度: {temp:.1f}°C   湿度: {humi:.1f}%   CPU: {cpu}%")

    # 如果启用了 TCP，顺带发送温湿度和 CPU 信息给远端
    if tcp_enabled and video_comm and video_comm.sock:
        try:
            data = {
                "cmd": "status_update",
                "time": now,
                "temperature": temp,
                "humidity": humi,
                "cpu": cpu
            }
            with video_comm.lock:
                video_comm.sock.sendall(
                    struct.pack('!I', len(json.dumps(data).encode())) + json.dumps(data).encode()
                )
        except Exception as e:
            print("发送状态数据失败:", e)

    root.after(1000, update_info)


# ========== 拍照与录像 ==========
def take_photo():
    if not video_display_enabled:
        messagebox.showwarning("提示", "开启视频后才能拍照")
        return
    frame = get_stream_frame()
    if frame is not None:
        filename = time.strftime("images/photo_%Y%m%d_%H%M%S.jpg")
        cv2.imwrite(filename, frame)
        messagebox.showinfo("拍照", f"已保存：{filename}")


def toggle_record():
    global recording, video_writer
    if not video_display_enabled:
        messagebox.showwarning("提示", "开启视频后才能录像")
        return
    if not recording:
        filename = time.strftime("videos/video_%Y%m%d_%H%M%S.avi")
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        video_writer = cv2.VideoWriter(filename, fourcc, 20.0, (640, 480))
        recording = True
        record_btn.config(text="停止录像")
        status_label.config(text="录像中")
    else:
        recording = False
        video_writer.release()
        video_writer = None
        record_btn.config(text="开始录像")
        status_label.config(text="录像停止")


# ========== 控制按钮 ==========
def toggle_video_display():
    global video_display_enabled
    video_display_enabled = not video_display_enabled
    video_toggle_btn.config(text="关闭视频显示" if video_display_enabled else "开启视频显示")
    photo_btn.config(state=tk.NORMAL if video_display_enabled else tk.DISABLED)
    record_btn.config(state=tk.NORMAL if video_display_enabled else tk.DISABLED)


def toggle_face_detection():
    global face_detection_enabled
    face_detection_enabled = not face_detection_enabled
    face_detect_btn.config(text="关闭人脸检测（本地）" if face_detection_enabled else "开启人脸检测（本地）")


def toggle_streaming():
    global streaming_enabled
    streaming_enabled = not streaming_enabled
    if streaming_enabled:
        stream_server.start()
        stream_toggle_btn.config(text="关闭Web推流")
    else:
        stream_server.stop()
        stream_toggle_btn.config(text="开启Web推流")


def toggle_tcp():
    global tcp_enabled
    tcp_enabled = not tcp_enabled
    if tcp_enabled:
        video_comm.start(callback=handle_remote_command)
        tcp_toggle_btn.config(text="断开服务器连接")
    else:
        video_comm.stop()
        tcp_toggle_btn.config(text="连接服务器")


def toggle_face_tracking():
    global face_tracking_enabled
    face_tracking_enabled = not face_tracking_enabled
    face_tracking_btn.config(text="关闭人脸追踪（本地）" if face_tracking_enabled else "开启人脸追踪（本地）")

    # 根据状态发送电机延迟指令
    delay_value = 0.01 if face_tracking_enabled else 0.003
    try:
        conn.send({'cmd': 'set_speed', 'delay': delay_value})
        print(f"电机延迟设置为 {delay_value}")
    except Exception as e:
        print("设置电机延迟失败:", e)



# ========== 键盘事件 ==========
def on_key_press(event):
    if event.keysym in ['Up', 'Down', 'Left', 'Right']:
        conn.send({'cmd': 'key', 'key': event.keysym})


def on_key_release(event):
    if event.keysym in ['Up', 'Down', 'Left', 'Right']:
        conn.send({'cmd': 'key', 'key': 'stop'})


# ========== GUI ==========
root = tk.Tk()
root.title("智能摄像头控制系统")
root.geometry("700x720")
root.bind("<KeyPress>", on_key_press)
root.bind("<KeyRelease>", on_key_release)

info_text = tk.StringVar()
tk.Label(root, textvariable=info_text, font=("Arial", 11), fg="blue").pack(pady=5)
status_label = tk.Label(root, text="系统状态：初始化中...")
status_label.pack()

video_label = tk.Label(root)
video_label.pack(pady=10)

action_frame = tk.Frame(root)
action_frame.pack()

photo_btn = tk.Button(action_frame, text="拍照", command=take_photo)
record_btn = tk.Button(action_frame, text="开始录像", command=toggle_record)
video_toggle_btn = tk.Button(action_frame, text="关闭视频显示", command=toggle_video_display)
face_detect_btn = tk.Button(action_frame, text="开启人脸检测（本地）", command=toggle_face_detection)
stream_toggle_btn = tk.Button(action_frame, text="开启Web推流", command=toggle_streaming)
tcp_toggle_btn = tk.Button(action_frame, text="连接服务器", command=toggle_tcp)
face_tracking_btn = tk.Button(action_frame, text="开启人脸追踪（本地）", command=toggle_face_tracking)
face_tracking_btn.pack(side=tk.LEFT, padx=10)

for btn in [photo_btn, record_btn, video_toggle_btn, face_detect_btn, stream_toggle_btn, tcp_toggle_btn]:
    btn.pack(side=tk.LEFT, padx=10)


# ========== 初始姿态 ==========
def initialize_position():
    def init():
        conn.send({'cmd': 'set_speed', 'delay': 0.001})
        time.sleep(0.1)
        send_motor_command(350, 110)
        time.sleep(0.5)
        send_motor_command(168, 60)
        time.sleep(0.5)
        conn.send({'cmd': 'set_speed', 'delay': 0.003})
        status_label.config(text="初始化完成")
    threading.Thread(target=init, daemon=True).start()


# ========== 资源清理 ==========
def cleanup():
    face_detection_queue.put(None)
    cap.release()
    try:
        conn.send({'cmd': 'exit'})
    except Exception:
        pass
    conn.close()
    if recording and video_writer:
        video_writer.release()
    stream_server.stop()
    video_comm.stop()


# ========== 启动程序 ==========
# 启动异步人脸检测线程
threading.Thread(target=face_detection_worker, daemon=True).start()

root.after(100, initialize_position)
root.after(0, update_frame)
root.after(0, update_info)

try:
    root.mainloop()
finally:
    cleanup()
