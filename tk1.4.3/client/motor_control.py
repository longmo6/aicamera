import wiringpi
import time
import threading
from multiprocessing.connection import Listener

class StepperMotorController:
    def __init__(self, step_delay=0.003):
        self.motor1_pins = [3, 4, 6, 9]
        self.motor2_pins = [10, 13, 15, 16]

        self.sequence = [
            [1, 0, 0, 0], [1, 1, 0, 0], [0, 1, 0, 0], [0, 1, 1, 0],
            [0, 0, 1, 0], [0, 0, 1, 1], [0, 0, 0, 1], [1, 0, 0, 1]
        ]

        wiringpi.wiringPiSetup()
        for pin in self.motor1_pins + self.motor2_pins:
            wiringpi.pinMode(pin, 1)

        self.step_index1 = 0
        self.step_index2 = 0
        self.step_motor1 = 0
        self.step_motor2 = 0

        self.motor1_running_dir = 0
        self.motor2_running_dir = 0

        self.step_delay = step_delay  # 步进延迟秒数控制速度

        threading.Thread(target=self._motor_thread, args=(1,), daemon=True).start()
        threading.Thread(target=self._motor_thread, args=(2,), daemon=True).start()

    def degree_to_step(self, deg):
        return int(deg / 360 * 4096)

    def clamp_step(self, step, max_deg):
        """限制步数在合理范围内"""
        return max(0, min(self.degree_to_step(max_deg), step))

    def _rotate_one_step(self, motor_pins, direction, motor_id):
        if motor_id == 1:
            self.step_index1 = (self.step_index1 + direction) % 8
            step = self.sequence[self.step_index1]
            for pin, val in zip(motor_pins, step):
                wiringpi.digitalWrite(pin, val)
            self.step_motor1 += direction
            self.step_motor1 = self.clamp_step(self.step_motor1, 350)
        else:
            self.step_index2 = (self.step_index2 + direction) % 8
            step = self.sequence[self.step_index2]
            for pin, val in zip(motor_pins, step):
                wiringpi.digitalWrite(pin, val)
            self.step_motor2 += direction
            self.step_motor2 = self.clamp_step(self.step_motor2, 130)

        time.sleep(self.step_delay)

    def rotate_motor(self, motor_id, target_angle):
        if motor_id == 1:
            current_step = self.step_motor1
            max_deg = 350
            motor_pins = self.motor1_pins
        else:
            current_step = self.step_motor2
            max_deg = 130
            motor_pins = self.motor2_pins

        target_step = self.clamp_step(self.degree_to_step(target_angle), max_deg)
        diff = target_step - current_step
        direction = 1 if diff > 0 else -1

        for _ in range(abs(diff)):
            self._rotate_one_step(motor_pins, direction, motor_id)

    def rotate_both_motors(self, angle1, angle2):
        t1 = threading.Thread(target=self.rotate_motor, args=(1, angle1))
        t2 = threading.Thread(target=self.rotate_motor, args=(2, angle2))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    def stop_all(self):
        self.motor1_running_dir = 0
        self.motor2_running_dir = 0
        for pin in self.motor1_pins + self.motor2_pins:
            wiringpi.digitalWrite(pin, 0)

    def _motor_thread(self, motor_id):
        while True:
            if motor_id == 1 and self.motor1_running_dir != 0:
                self._rotate_one_step(self.motor1_pins, self.motor1_running_dir, 1)
            elif motor_id == 2 and self.motor2_running_dir != 0:
                self._rotate_one_step(self.motor2_pins, self.motor2_running_dir, 2)
            else:
                time.sleep(0.01)

    def set_speed(self, step_delay):
        if step_delay > 0:
            self.step_delay = step_delay
            print(f"电机速度设置为 步进延迟 {self.step_delay} 秒")
        else:
            print("错误：延迟必须 > 0")

    def get_motor1_angle(self):
        return self.step_motor1 / 4096 * 360

    def get_motor2_angle(self):
        return self.step_motor2 / 4096 * 360


def main():
    address = ('localhost', 6000)
    listener = Listener(address, authkey=b'secret password')
    print("电机控制进程已启动，等待连接...")

    conn = listener.accept()
    print("主程序连接成功！")

    controller = StepperMotorController()

    try:
        while True:
            if conn.poll(0.1):
                msg = conn.recv()
                cmd = msg.get('cmd')

                if cmd == 'rotate':
                    angle1 = msg.get('angle1')
                    angle2 = msg.get('angle2')
                    controller.rotate_both_motors(angle1, angle2)
                    conn.send({'status': 'done', 'angle1': angle1, 'angle2': angle2})

                elif cmd == 'key':
                    key = msg.get('key')
                    print("接收到方向键：", key)
                    if key == 'Right':
                        controller.motor1_running_dir = 1
                    elif key == 'Left':
                        controller.motor1_running_dir = -1
                    elif key == 'Up':
                        controller.motor2_running_dir = 1
                    elif key == 'Down':
                        controller.motor2_running_dir = -1
                    elif key == 'stop':
                        controller.stop_all()

                elif cmd == 'set_speed':
                    new_delay = msg.get('delay')
                    if isinstance(new_delay, (float, int)) and 0 < new_delay < 1:
                        controller.set_speed(new_delay)
                        conn.send({'status': 'speed_set', 'delay': new_delay})
                    else:
                        conn.send({'status': 'error', 'message': 'invalid delay'})

                elif cmd == 'get_angle':
                    angle1 = controller.get_motor1_angle()
                    angle2 = controller.get_motor2_angle()
                    conn.send({'status': 'angle', 'angle1': angle1, 'angle2': angle2})

                elif cmd == 'exit':
                    controller.stop_all()
                    conn.close()
                    break

    except Exception as e:
        print("异常:", e)

    finally:
        controller.stop_all()
        listener.close()
        print("电机控制进程退出")


if __name__ == "__main__":
    main()
