from flask import Flask, Response, render_template_string
from werkzeug.serving import make_server
import threading
import time
import cv2

class StreamingServer:
    def __init__(self, get_frame_func, host='0.0.0.0', port=8080):
        self.app = Flask(__name__)
        self.host = host
        self.port = port
        self.get_frame = get_frame_func
        self.server = None
        self.server_thread = None
        self.running = False

        @self.app.route('/')
        def index():
            return render_template_string("""
                <html>
                <head><title>摄像头推流</title></head>
                <body>
                    <h2>摄像头视频流</h2>
                    <img src="/video_feed" width="640" height="480">
                </body>
                </html>
            """)

        @self.app.route('/video_feed')
        def video_feed():
            return Response(self.gen_frames(),
                            mimetype='multipart/x-mixed-replace; boundary=frame')

    def gen_frames(self):
        while self.running:
            frame = self.get_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.03)

    def start(self):
        if self.running:
            print("推流服务已运行")
            return
        self.running = True
        self.server = make_server(self.host, self.port, self.app)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        print("推流服务已启动")

    def stop(self):
        if not self.running:
            print("推流服务未运行")
            return
        self.running = False
        if self.server:
            self.server.shutdown()
            self.server_thread.join()
            self.server = None
            self.server_thread = None
        print("推流服务已停止")
