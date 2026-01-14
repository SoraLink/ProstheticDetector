import json
import os
import cv2
import numpy as np
from tqdm import tqdm

# ================= 配置区域 =================
JSON_PATH = "./coco/annotations_trainval2017/annotations/person_keypoints_train2017.json"
OUTPUT_DIR = "./output_openpose_centered"  # 新的输出目录
MAX_IMAGES = 100
REQUIRE_UPPER_BODY = True

# 画布设置 (SDXL 推荐尺寸)
CANVAS_SIZE = (1024, 1024)  # 宽, 高
PADDING = 200  # 在人周围留多少空白像素
# ===========================================

# OpenPose 连线定义
COCO_PAIRS = [
    (0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)
]
COLORS = [
    (0, 255, 255), (0, 0, 255), (0, 255, 255), (0, 0, 255),
    (255, 0, 0), (255, 170, 0), (255, 255, 0), (255, 85, 0), (170, 255, 0),
    (255, 0, 85), (0, 255, 170), (0, 85, 255), (0, 255, 85), (0, 170, 255),
    (85, 255, 0), (255, 0, 170)
]


def process_coco_json():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print(f"正在加载 JSON...")
    with open(JSON_PATH, 'r') as f:
        data = json.load(f)

    print("正在处理...")

    count = 0
    pbar = tqdm(total=MAX_IMAGES if MAX_IMAGES else len(data['annotations']))

    # 这里的逻辑稍微变一下，我们直接遍历 annotations，因为我们不关心原图背景了
    # 我们要把每个人单独提取出来变成一张新图

    images_info = {img['id']: img for img in data['images']}

    for ann in data['annotations']:
        if MAX_IMAGES and count >= MAX_IMAGES:
            break

        # 1. 基础过滤
        if ann['num_keypoints'] < 5 or ann['area'] < 1000:  # 过滤掉点太少或太小的人
            continue

        keypoints = ann['keypoints']

        # 2. 上半身完整性检查
        if REQUIRE_UPPER_BODY:
            # 必须包含肩膀(5,6) 和 至少一个手肘(7,8) 或 手腕(9,10)
            has_shoulders = (keypoints[5 * 3 + 2] > 0 and keypoints[6 * 3 + 2] > 0)
            has_arms = (keypoints[7 * 3 + 2] > 0 or keypoints[8 * 3 + 2] > 0)
            if not (has_shoulders and has_arms):
                continue

        # 3. 计算这个人的 Bounding Box (为了居中)
        xs = [keypoints[i * 3] for i in range(17) if keypoints[i * 3 + 2] > 0]
        ys = [keypoints[i * 3 + 1] for i in range(17) if keypoints[i * 3 + 2] > 0]

        if not xs or not ys:
            continue

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        person_w = max_x - min_x
        person_h = max_y - min_y

        # 4. 计算缩放比例，让这个人填满 1024x1024 但保留边距
        scale_x = (CANVAS_SIZE[0] - PADDING) / person_w
        scale_y = (CANVAS_SIZE[1] - PADDING) / person_h
        scale = min(scale_x, scale_y)  # 保持纵横比

        # 5. 坐标变换：把原图坐标 -> 新画布中心坐标
        # 新坐标 = (原坐标 - 原中心) * 缩放 + 新中心
        center_x_old = min_x + person_w / 2
        center_y_old = min_y + person_h / 2

        center_x_new = CANVAS_SIZE[0] / 2
        center_y_new = CANVAS_SIZE[1] / 2

        # 创建新画布
        canvas = np.zeros((CANVAS_SIZE[1], CANVAS_SIZE[0], 3), dtype=np.uint8)

        points_new = []
        for i in range(17):
            v = keypoints[i * 3 + 2]
            if v > 0:
                x = keypoints[i * 3]
                y = keypoints[i * 3 + 1]

                # 变换公式
                new_x = int((x - center_x_old) * scale + center_x_new)
                new_y = int((y - center_y_old) * scale + center_y_new)
                points_new.append((new_x, new_y, v))
            else:
                points_new.append((0, 0, 0))

        # 6. 绘图
        for pair_idx, (start_idx, end_idx) in enumerate(COCO_PAIRS):
            p1 = points_new[start_idx]
            p2 = points_new[end_idx]
            if p1[2] > 0 and p2[2] > 0:
                color = COLORS[pair_idx % len(COLORS)]

                # 【改这里】去掉 scale，直接固定为 4 或 5
                thickness = 5
                cv2.line(canvas, (p1[0], p1[1]), (p2[0], p2[1]), color, thickness)

        for i, p in enumerate(points_new):
            if p[2] > 0:
                # 【改这里】去掉 scale，直接固定为 5 或 6
                radius = 6
                cv2.circle(canvas, (p[0], p[1]), radius, (0, 0, 255), -1)

        # 保存
        file_name = f"pose_{ann['id']}.png"  # 使用 annotation ID 作为文件名，避免同一张图多个人重名
        cv2.imwrite(os.path.join(OUTPUT_DIR, file_name), canvas)
        count += 1
        pbar.update(1)

    pbar.close()
    print(f"完成！生成了 {count} 张居中校正的骨架图。")


if __name__ == "__main__":
    process_coco_json()