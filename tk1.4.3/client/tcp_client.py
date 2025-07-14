import socket
import struct
import json
import threading
import time
import cv2
import queue

class VideoCommandClient:
    def __init__(self, get_frame_func, server_ip, server_port=9999):
        self.get_frame = get_frame_func
        self.server_ip = server_ip
        self.server_port = server_port
        self.sock = None
        self.running = False
        self.send_thread = None
        self.recv_thread = None
        self.callback = None
        self.lock = threading.Lock()
        self.cmd_queue = queue.Queue()  # 新增命令队列

    def start(self, callback=None):
        self.running = True
        self.callback = callback
        threading.Thread(target=self.connect_loop, daemon=True).start()

    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.sock.close()
            self.sock = None

    def connect_loop(self):
        while self.running:
            try:
                print(f"[通信] 正在连接 {self.server_ip}:{self.server_port} ...")
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.server_ip, self.server_port))
                print("[通信] 已连接")
                self.send_thread = threading.Thread(target=self.send_loop, daemon=True)
                self.recv_thread = threading.Thread(target=self.recv_loop, daemon=True)
                self.send_thread.start()
                self.recv_thread.start()
                self.send_thread.join()
                self.recv_thread.join()
            except Exception as e:
                print("[通信] 错误，3秒后重连：", e)
                time.sleep(3)

    def send_loop(self):
        frame_interval = 1.0 / 60.0  # 60 FPS
        while self.running:
            start_time = time.time()
            # 先发送所有队列里的命令
            while not self.cmd_queue.empty():
                cmd = self.cmd_queue.get()
                try:
                    with self.lock:
                        data_str = json.dumps(cmd)
                        data_bytes = data_str.encode('utf-8')
                        self.sock.sendall(struct.pack('!I', len(data_bytes)) + data_bytes)
                except Exception as e:
                    print("[通信] 命令发送失败:", e)
                    self.running = False
                    return

            # 发送视频帧
            frame = self.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            _, buf = cv2.imencode('.jpg', frame)
            data = buf.tobytes()
            try:
                with self.lock:
                    self.sock.sendall(struct.pack('!I', len(data)) + data)
            except Exception as e:
                print("[通信] 视频帧发送失败:", e)
                self.running = False
                return

            elapsed = time.time() - start_time
            time.sleep(max(0, frame_interval - elapsed))

    def recv_loop(self):
        while self.running:
            try:
                header = self.recvall(4)
                if not header:
                    break
                resp_size = struct.unpack('!I', header)[0]
                resp_data = self.recvall(resp_size)
                if resp_data:
                    result = json.loads(resp_data.decode())
                    if self.callback:
                        self.callback(result)
            except Exception as e:
                print("[通信] 接收失败:", e)
                break

    def recvall(self, n):
        data = b''
        while len(data) < n:
            packet = self.sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    def send_command(self, cmd_dict):
        """将控制命令放入队列，由发送线程异步发送"""
        if not self.running:
            print("[通信] 发送失败：连接未启动")
            return
        self.cmd_queue.put(cmd_dict)


# ===== 以下为测试代码，仅在本文件单独执行时触发 =====
if __name__ == '__main__':
    def get_test_frame():
        ret, frame = cap.read()
        return frame if ret else None

    def test_callback(cmd):
        print("[测试指令接收]", cmd)

    cap = cv2.VideoCapture(0)
    client = VideoCommandClient(get_test_frame, server_ip='192.168.4.54', server_port=9999)
    client.start(callback=test_callback)

    # 模拟每5秒发送一次测试命令
    def send_test_commands():
        while True:
            client.send_command({'cmd': 'test_status', 'value': 123})
            time.sleep(5)

    threading.Thread(target=send_test_commands, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[退出] 手动终止")
    finally:
        client.stop()
        cap.release()
