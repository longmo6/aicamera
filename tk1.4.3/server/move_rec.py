from action_components.tflite_infer import TfliteRun
from action_components.utils import _keypoints_and_edges_for_display,\
    drawKeypoints, drawLine, humanAction
from action_components.config import ai_cfg
import numpy as np
import cv2
import time

MOVE_MODEL_PATH = "action_resources/model_zoo/movenet_float16.tflite"

class MoveRec(object):
    def __init__(self, model_path=MOVE_MODEL_PATH):
        self.tflite_run = TfliteRun(model_path=model_path)
        self.predictions = []

    def imgPreprocessing(self, img):
        input_data = cv2.resize(img, ai_cfg.INPUT_SIZE)
        input_data = cv2.cvtColor(input_data, cv2.COLOR_BGR2RGB)
        # 使用np.expand_dims来增加一个维度，以符合模型对输入数据形状的要求。
        input_data = np.expand_dims(input_data, axis=0)
        return input_data

    def inference(self, img):
        input_data = self.imgPreprocessing(img)
        output = self.tflite_run.inference(input_data)
        self.predictions = [output, ]
        return self.predictions


def recImgDis(img, predictions):
    human_action = 0
    if predictions:
        # 解析模型输出结果
        keypoints_xy, edges_xy, edge_colors = _keypoints_and_edges_for_display(predictions[0],
                                                                               ai_cfg.CAM_HEIGHT,
                                                                               ai_cfg.CAM_WIDTH)

        # 绘制关键点连线
        drawLine(edges_xy, img, edge_colors)

        # 绘制关键点
        drawKeypoints(keypoints_xy, img)
        # 返回动作解析结果：
        # 1左转：左胳膊抬起；2右转：右胳膊抬起；3直行：左胳膊举过头顶；4后退：右胳膊举过头顶；
        img, human_action = humanAction(img, keypoints_xy)

    return img, human_action


