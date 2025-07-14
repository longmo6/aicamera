
class AI_Config:
    # 基本设置
    window_name = "posenet"

    CAM_HEIGHT = 480
    CAM_WIDTH = 640

    INPUT_SIZE = (192, 192)  # (h, w)

    # 模型路径
    MOVE_MODEL_PATH = "./resources/model_zoo/movenet_float16.tflite"
    FONT_PATH = "./resources/font/simsun.ttc"
    FONT_SIZE = 45

ai_cfg = AI_Config()