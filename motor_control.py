import wiringpi
import time
import threading
from multiprocessing.connection import Listener

# 电机引脚和序列定义
IN1, IN2, IN3, IN4 = 3, 4, 6, 9
IN5, IN6, IN7, IN8 = 10, 13, 15, 16
motor1_pins = [IN1, IN2, IN3, IN4]
motor2_pins = [IN5, IN6, IN7, IN8]

sequence = [
    [1, 0, 0, 0], [1, 1, 0, 0], [0, 1, 0, 0], [0, 1, 1, 0],
    [0, 0, 1, 0], [0, 0, 1, 1], [0, 0, 0, 1], [1, 0, 0, 1]
]

wiringpi.wiringPiSetup()
for pin in motor1_pins + motor2_pins:
    wiringpi.pinMode(pin, 1)

STEP_DELAY = 0.003

# 电机位置状态
step_index1 = 0
step_index2 = 0
step_motor1 = 0
step_motor2 = 0

# 运行控制标志
motor1_running_dir = 0  # -1:反转, 1:正转, 0:停止
motor2_running_dir = 0

def degree_to_step(deg):
    return int(deg / 360 * 4096)

def rotate_one_step(motor_pins, direction, motor_id):
    global step_index1, step_index2, step_motor1, step_motor2
    if motor_id == 1:
        step_index1 = (step_index1 + direction) % 8
        step = sequence[step_index1]
        for pin, val in zip(motor_pins, step):
            wiringpi.digitalWrite(pin, val)
        step_motor1 += direction
        step_motor1 = max(0, min(degree_to_step(350), step_motor1))
    else:
        step_index2 = (step_index2 + direction) % 8
        step = sequence[step_index2]
        for pin, val in zip(motor_pins, step):
            wiringpi.digitalWrite(pin, val)
        step_motor2 += direction
        step_motor2 = max(0, min(degree_to_step(130), step_motor2))
    time.sleep(STEP_DELAY)

def rotate_motor(motor_id, target_angle):
    if motor_id == 1:
        current_step = step_motor1
        max_deg = 350
        motor_pins = motor1_pins
    else:
        current_step = step_motor2
        max_deg = 130
        motor_pins = motor2_pins

    target_step = degree_to_step(target_angle)
    target_step = max(0, min(degree_to_step(max_deg), target_step))
    diff = target_step - current_step
    direction = 1 if diff > 0 else -1

    for _ in range(abs(diff)):
        rotate_one_step(motor_pins, direction, motor_id)

def stop_all():
    global motor1_running_dir, motor2_running_dir
    motor1_running_dir = 0
    motor2_running_dir = 0
    for pin in motor1_pins + motor2_pins:
        wiringpi.digitalWrite(pin, 0)

# 后台线程，控制持续旋转
def motor_thread(motor_id):
    global motor1_running_dir, motor2_running_dir
    while True:
        if motor_id == 1 and motor1_running_dir != 0:
            rotate_one_step(motor1_pins, motor1_running_dir, 1)
        elif motor_id == 2 and motor2_running_dir != 0:
            rotate_one_step(motor2_pins, motor2_running_dir, 2)
        else:
            time.sleep(0.01)  # 空闲状态

# 启动两个电机线程
threading.Thread(target=motor_thread, args=(1,), daemon=True).start()
threading.Thread(target=motor_thread, args=(2,), daemon=True).start()

def main():
    address = ('localhost', 6000)
    listener = Listener(address, authkey=b'secret password')
    print("电机控制进程已启动，等待连接...")

    conn = listener.accept()
    print("主程序连接成功！")

    try:
        while True:
            if conn.poll(0.1):
                msg = conn.recv()
                cmd = msg.get('cmd')

                if cmd == 'rotate':
                    angle1 = msg.get('angle1')
                    angle2 = msg.get('angle2')
                    rotate_motor(1, angle1)
                    rotate_motor(2, angle2)
                    conn.send({'status': 'done', 'angle1': angle1, 'angle2': angle2})

                elif cmd == 'key':
                    key = msg.get('key')
                    print("接收到方向键：", key)
                    global motor1_running_dir, motor2_running_dir
                    if key == 'Right':
                        motor1_running_dir = 1
                    elif key == 'Left':
                        motor1_running_dir = -1
                    elif key == 'Up':
                        motor2_running_dir = 1
                    elif key == 'Down':
                        motor2_running_dir = -1
                    elif key == 'stop':
                        stop_all()

                elif cmd == 'stop':
                    stop_all()
                    conn.send({'status': 'stopped'})

                elif cmd == 'exit':
                    stop_all()
                    conn.close()
                    break
    except Exception as e:
        print("异常:", e)
    finally:
        stop_all()
        listener.close()
        print("电机控制进程退出")

if __name__ == "__main__":
    main()
