import os

# 获取前一级路径
# BASE_PATH = os.path.dirname(os.path.dirname(__file__))

# 获取当前路径
BASE_PATH = os.path.dirname(__file__)

class Config:
    UART_BAUDRATE = 115200
    UART_TIMEOUT = 3
    
    LOG_LEVEL_STDOUT = "info"
    LOG_LEVEL_FILE = "info"
    LOG_SAVE_FLODER = os.path.join(BASE_PATH, "bkrc_log")
    LOG_FLAGE = False

    IMG_DIS_FLAGE = True
    USB_CAMERA_INDEX = "1"
    THRESHOLD = 0.6

    POSEN_STATIC = "HUMAN_ACTION"
    IMU_DATA = "IMU_DATA"

    CLINET_MODE = "wifi"


config = Config()
