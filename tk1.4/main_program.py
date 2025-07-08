import tkinter as tk
from tkinter import messagebox
import threading
import time
import cv2
import random
import psutil
from PIL import Image, ImageTk
from multiprocessing.connection import Client
import os

os.makedirs("images", exist_ok=True)
os.makedirs("videos", exist_ok=True)

# 摄像头控制 & 多进程通信连接
address = ('localhost', 6000)
conn = Client(address, authkey=b'secret password')

cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
recording = False
video_writer = None

# ---------- 控制电机 ----------
def send_motor_command(angle1, angle2):
    try:
        conn.send({'cmd': 'rotate', 'angle1': angle1, 'angle2': angle2})
        resp = conn.recv()
        if resp.get('status') == 'done':
            print(f"电机1旋转到{angle1}度完成\n电机2旋转到{angle2}度完成")
    except Exception as e:
        print("发送电机命令异常:", e)

def control_motors():
    try:
        target1 = int(angle1_entry.get())
        target2 = int(angle2_entry.get())
        if not (0 <= target1 <= 350) or not (0 <= target2 <= 130):
            status_label.config(text="输入角度超限")
            return
        status_label.config(text="电机旋转中...")
        threading.Thread(target=send_motor_command, args=(target1, target2), daemon=True).start()
        status_label.config(text="完成")
    except Exception as e:
        status_label.config(text=f"错误: {e}")

# ---------- 摄像头显示 ----------
def update_frame():
    ret, frame = cap.read()
    if ret:
        frame = cv2.flip(frame, 0)
        cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(cv2image)
        imgtk = ImageTk.PhotoImage(image=img)
        video_label.imgtk = imgtk
        video_label.configure(image=imgtk)
        if recording and video_writer:
            video_writer.write(frame)
    root.after(16, update_frame)

# ---------- 实时信息更新 ----------
def update_info_bar():
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    temp = round(random.uniform(25, 35), 1)
    humi = round(random.uniform(40, 60), 1)
    cpu = psutil.cpu_percent(interval=None)
    info_text.set(f"时间: {now}   温度: {temp}°C   湿度: {humi}%   CPU: {cpu}%")
    root.after(1000, update_info_bar)

# ---------- 拍照与录像 ----------
def take_photo():
    ret, frame = cap.read()
    if ret:
        filename = time.strftime("images/photo_%Y%m%d_%H%M%S.jpg")
        frame = cv2.flip(frame, 0)
        cv2.imwrite(filename, frame)
        messagebox.showinfo("拍照", f"照片已保存：{filename}")

def toggle_record():
    global recording, video_writer
    if not recording:
        filename = time.strftime("videos/video_%Y%m%d_%H%M%S.avi")
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        fps = 20.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        video_writer = cv2.VideoWriter(filename, fourcc, fps, (width, height))
        recording = True
        record_btn.config(text="停止录像")
        status_label.config(text="录像中...")
    else:
        recording = False
        record_btn.config(text="开始录像")
        status_label.config(text="录像停止")
        if video_writer:
            video_writer.release()
            video_writer = None

# ---------- 键盘控制 ----------
def on_key_press(event):
    key = event.keysym
    if key in ['Up', 'Down', 'Left', 'Right']:
        try:
            conn.send({'cmd': 'key', 'key': key})
            print(f"按下：{key}")
        except Exception as e:
            print("发送按键指令失败:", e)

def on_key_release(event):
    if event.keysym in ['Up', 'Down', 'Left', 'Right']:
        try:
            conn.send({'cmd': 'key', 'key': 'stop'})
            print("松开：发送stop")
        except Exception as e:
            print("发送stop失败:", e)

# ---------- 主界面 ----------
root = tk.Tk()
root.title("智能摄像头控制系统")
root.geometry("700x600")

root.bind("<KeyPress>", on_key_press)
root.bind("<KeyRelease>", on_key_release)

# ---------- 顶部信息栏 ----------
info_text = tk.StringVar()
info_label = tk.Label(root, textvariable=info_text, font=("Arial", 11), fg="blue")
info_label.pack(pady=5)

# ---------- 控制区域 ----------
control_frame = tk.Frame(root)
control_frame.pack(pady=5)

# tk.Label(control_frame, text="目标电机1角度(0~350):").grid(row=0, column=0, padx=5)
# angle1_entry = tk.Entry(control_frame, width=5)
# angle1_entry.insert(0, "175")
# angle1_entry.grid(row=0, column=1, padx=5)
#
# tk.Label(control_frame, text="目标电机2角度(0~130):").grid(row=0, column=2, padx=5)
# angle2_entry = tk.Entry(control_frame, width=5)
# angle2_entry.insert(0, "60")
# angle2_entry.grid(row=0, column=3, padx=5)
#
# control_btn = tk.Button(control_frame, text="执行旋转", command=control_motors)
# control_btn.grid(row=0, column=4, padx=10)

status_label = tk.Label(root, text="系统状态：相机初始化中...")
status_label.pack()

video_label = tk.Label(root)
video_label.pack(pady=10)

action_frame = tk.Frame(root)
action_frame.pack(pady=10)

photo_btn = tk.Button(action_frame, text="拍照", command=take_photo)
photo_btn.pack(side=tk.LEFT, padx=20)

record_btn = tk.Button(action_frame, text="开始录像", command=toggle_record)
record_btn.pack(side=tk.LEFT, padx=20)

# ---------- 电机初始定位 ----------
def initialize_camera_position():
    def init_sequence():
        send_motor_command(350, 110)
        time.sleep(0.5)
        send_motor_command(175, 60)
        status_label.config(text="镜头初始化完成")
    threading.Thread(target=init_sequence, daemon=True).start()

# ---------- 启动 ----------
root.after(100, initialize_camera_position)
root.after(0, update_frame)
root.after(0, update_info_bar)

try:
    root.mainloop()
finally:
    cap.release()
    try:
        conn.send({'cmd': 'exit'})
        conn.close()
    except:
        pass
