import subprocess
import time
import sys
import os

def run_script(script_name):
    return subprocess.Popen([sys.executable, script_name], cwd=os.getcwd())

if __name__ == "__main__":
    print("启动电机控制程序...")
    motor_proc = run_script("motor_control.py")

    # 等待一秒让电机控制程序先启动监听
    time.sleep(1)

    print("启动主程序界面...")
    gui_proc = run_script("main_program.py")

    try:
        # 等待主程序结束
        gui_proc.wait()
    except KeyboardInterrupt:
        print("收到退出信号，关闭程序...")

    # 关闭电机控制程序
    motor_proc.terminate()
    motor_proc.wait()
    print("所有程序已退出。")
