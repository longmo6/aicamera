import cv2
import numpy as np
from PIL import ImageFont, ImageDraw, Image
from components.config import ai_cfg
from action_tools.config import config
import random
import math

def putText(img, text, org=(0, 0), font_path=ai_cfg.FONT_PATH,
            color=(0, 0, 255), font_size=ai_cfg.FONT_SIZE):
    """
    在图片上显示文字
    :param img: 输入的img, 通过cv2读取
    :param text: 要显示的文字
    :param org: 文字左上角坐标
    :param font_path: 字体路径
    :param color: 字体颜色, (B,G,R)
    :return:
    """
    img_pil = Image.fromarray(img)
    draw = ImageDraw.Draw(img_pil)
    b, g, r = color
    a = 0
    draw.text(org, text, font=ImageFont.truetype(font_path, font_size), fill=(b, g, r, a))
    img = np.array(img_pil)
    return img


# Dictionary that maps from joint names to keypoint indices.
KEYPOINT_DICT = {
    'nose': 0,
    'left_eye': 1,
    'right_eye': 2,
    'left_ear': 3,
    'right_ear': 4,
    'left_shoulder': 5,
    'right_shoulder': 6,
    'left_elbow': 7,
    'right_elbow': 8,
    'left_wrist': 9,
    'right_wrist': 10,
    'left_hip': 11,
    'right_hip': 12,
    'left_knee': 13,
    'right_knee': 14,
    'left_ankle': 15,
    'right_ankle': 16
}

# Maps bones to a matplotlib color name.
KEYPOINT_EDGE_INDS_TO_COLOR = {
    (0, 1): (0, 0, 255),
    (0, 2): (255, 0, 0), (1, 3): (0, 255, 0),
    (2, 4): (255, 0, 0), (0, 5): (0, 255, 0),
    (0, 6): (255, 0, 0), (5, 7): (0, 255, 0),
    (7, 9): (255, 0, 0), (6, 8): (0, 255, 0),
    (8, 10): (255, 0, 0), (5, 6): (0, 255, 0),
    (5, 11): (255, 0, 0), (6, 12): (0, 255, 0),
    (11, 12): (255, 0, 0), (11, 13): (0, 255, 0),
    (13, 15): (255, 0, 0), (12, 14): (0, 255, 0),
    (14, 16): (0, 255, 0)
}

def _keypoints_and_edges_for_display(keypoints_with_scores,
                                     height,
                                     width,
                                     keypoint_threshold=0.11):
  """Returns high confidence keypoints and edges for visualization.

  Args:
    keypoints_with_scores: A numpy array with shape [1, 1, 17, 3] representing
      the keypoint coordinates and scores returned from the MoveNet model.
    height: height of the image in pixels.
    width: width of the image in pixels.
    keypoint_threshold: minimum confidence score for a keypoint to be
      visualized.

  Returns:
    A (keypoints_xy, edges_xy, edge_colors) containing:
      * the coordinates of all keypoints of all detected entities;
      * the coordinates of all skeleton edges of all detected entities;
      * the colors in which the edges should be plotted.
  """
  keypoints_all = []
  keypoint_edges_all = []
  edge_colors = []
  num_instances, _, _, _ = keypoints_with_scores.shape
  for idx in range(num_instances):
    kpts_x = keypoints_with_scores[0, idx, :, 1]
    kpts_y = keypoints_with_scores[0, idx, :, 0]
    kpts_scores = keypoints_with_scores[0, idx, :, 2]
    kpts_absolute_xy = np.stack(
        [width * np.array(kpts_x), height * np.array(kpts_y)], axis=-1)
    kpts_above_thresh_absolute = kpts_absolute_xy[
        kpts_scores > keypoint_threshold, :]
    keypoints_all.append(kpts_above_thresh_absolute)

    for edge_pair, color in KEYPOINT_EDGE_INDS_TO_COLOR.items():
      if (kpts_scores[edge_pair[0]] > keypoint_threshold and
          kpts_scores[edge_pair[1]] > keypoint_threshold):
        x_start = kpts_absolute_xy[edge_pair[0], 0]
        y_start = kpts_absolute_xy[edge_pair[0], 1]
        x_end = kpts_absolute_xy[edge_pair[1], 0]
        y_end = kpts_absolute_xy[edge_pair[1], 1]
        line_seg = np.array([[x_start, y_start], [x_end, y_end]])
        keypoint_edges_all.append(line_seg)
        edge_colors.append(color)

  if keypoints_all:
    keypoints_xy = np.concatenate(keypoints_all, axis=0)
  else:
    keypoints_xy = np.zeros((0, 17, 2))

  if keypoint_edges_all:
    edges_xy = np.stack(keypoint_edges_all, axis=0)
  else:
    edges_xy = np.zeros((0, 2, 2))
  return keypoints_xy, edges_xy, edge_colors

def drawKeypoints(body, img, color=(0, 0, 255)):
    for keypoint in body:
            center = (int(keypoint[0]), int(keypoint[1]))
            radius = 6
            cv2.circle(img, center, radius, color, -1, 8)
    return None

def drawLine(edges_xy, img, color=None):
    thickness = 5

    for i, edges in enumerate(edges_xy):
        cv2.line(img, (int(edges[0][0]), int(edges[0][1])),
                       (int(edges[1][0]), int(edges[1][1])),
                        (0, 255, 0), thickness)


def humanAction(img, keypoints_xy):
    action_index = 0
    try:
        # 左胳膊抬起-左手拿东西
        if (math.fabs((keypoints_xy[5][1] - keypoints_xy[7][1]) / (keypoints_xy[5][0] - keypoints_xy[7][0])) < 0.5
                and math.fabs(
                    (keypoints_xy[7][1] - keypoints_xy[9][1]) / (keypoints_xy[7][0] - keypoints_xy[9][0])) < 0.5):
            if action_index == 0:
                action_index = 1
                img = putText(img, "左手拿东西", (0, 20), font_path=ai_cfg.FONT_PATH,
            color=(255, 255, 0), font_size=ai_cfg.FONT_SIZE)


        # 右胳膊抬起---右手拿东西
        elif (math.fabs((keypoints_xy[6][1] - keypoints_xy[8][1]) / (keypoints_xy[6][0] - keypoints_xy[8][0])) < 0.5
              and math.fabs(
                    (keypoints_xy[8][1] - keypoints_xy[10][1]) / (keypoints_xy[8][0] - keypoints_xy[10][0])) < 0.5):
            if action_index == 0:
                action_index = 2
                img = putText(img, "右手拿东西", (0, 20), font_path=ai_cfg.FONT_PATH,
                              color=(255, 255, 0), font_size=ai_cfg.FONT_SIZE)

        # 左胳膊举过头顶-左手拿东西
        elif (keypoints_xy[1][1] > keypoints_xy[9][1]):
            if action_index == 0:
                action_index = 3
                img = putText(img, "左手拿东西", (0, 20), font_path=ai_cfg.FONT_PATH,
                              color=(255, 255, 0), font_size=ai_cfg.FONT_SIZE)

        # 右胳膊举过头顶--右手拿东西
        elif (keypoints_xy[10][1] < keypoints_xy[2][1]):
            if action_index == 0:
                action_index = 4
                img = putText(img, "左手拿东西", (0, 20), font_path=ai_cfg.FONT_PATH,
                              color=(255, 255, 0), font_size=ai_cfg.FONT_SIZE)

        # 胳膊交叉胸前--偷东西
        elif (math.fabs((keypoints_xy[7][0] - keypoints_xy[9][0]) / (keypoints_xy[7][1] - keypoints_xy[9][1])) > 1
              and math.fabs((keypoints_xy[8][0] - keypoints_xy[10][0]) / (keypoints_xy[8][1] - keypoints_xy[9][1])) > 1 \
              and keypoints_xy[7][1] > keypoints_xy[9][1] > keypoints_xy[1][1] \
              and keypoints_xy[8][1] > keypoints_xy[10][1] > keypoints_xy[1][1]):
            if action_index == 0:
                action_index = 6
                img = putText(img, "警告:有人偷东西！！", (0, 110))

        # 摔倒
        elif (math.fabs((keypoints_xy[11][1] - keypoints_xy[15][1]) / (keypoints_xy[11][0] - keypoints_xy[15][0])) < 0.5
              or math.fabs(
                    (keypoints_xy[12][1] - keypoints_xy[16][1]) / (keypoints_xy[12][0] - keypoints_xy[16][0])) < 0.5):
            if action_index == 0:
                action_index = 5
                img = putText(img, "警告：有人摔倒！！", (0, 110))

        # 蹲
        elif (0.5 < math.fabs(
                (keypoints_xy[11][1] - keypoints_xy[15][1]) / (keypoints_xy[11][0] - keypoints_xy[15][0])) < 2
              or 0.5 < math.fabs(
                    (keypoints_xy[12][1] - keypoints_xy[16][1]) / (keypoints_xy[12][0] - keypoints_xy[16][0])) < 2):
            if action_index == 0:
                action_index = 8
                img = putText(img, "蹲下", (0, 20), font_path=ai_cfg.FONT_PATH,
                              color=(255, 255, 0), font_size=ai_cfg.FONT_SIZE)

        # 走
        elif (math.fabs((keypoints_xy[13][0] - keypoints_xy[15][0]) / (keypoints_xy[13][1] - keypoints_xy[15][1])) > 0.3
              or math.fabs(
                    (keypoints_xy[14][0] - keypoints_xy[16][0]) / (keypoints_xy[14][1] - keypoints_xy[16][1])) > 0.3):
            if action_index == 0:
                action_index = 9
                img = putText(img, "行走", (0, 20), font_path=ai_cfg.FONT_PATH,
                              color=(255, 255, 0), font_size=ai_cfg.FONT_SIZE)

        else:
            action_index = 0
            img = putText(img, "自然状态", (0, 20), font_path=ai_cfg.FONT_PATH,
                          color=(255, 255, 0), font_size=ai_cfg.FONT_SIZE)
    except:
        pass

    return img, action_index

