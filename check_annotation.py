import json
import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
import numpy as np

# ================= 配置区域 =================
# 1. 填入你的训练集 JSON 路径
JSON_PATH = '/home/sora/workspace/dataset/ldpose_final/pros_annotations/labels_train_final.json'

# 2. 填入你的图片根目录 (就是 ldpose_train 文件夹)
IMG_ROOT = '/home/sora/workspace/dataset/ldpose_final/ldpose_train/'

# 3. 想看第几张图？(换几个数字多测测，比如 10, 50, 100)
SAMPLE_IDX = 10


# ===========================================

def check_bbox():
    print(f"🚀 正在读取 JSON: {JSON_PATH} ...")
    with open(JSON_PATH, 'r') as f:
        data = json.load(f)

    # 获取标注和对应图片信息
    ann = data['annotations'][SAMPLE_IDX]
    img_id = ann['image_id']
    bbox = ann['bbox']  # [x, y, w, h]

    # 找到对应的图片文件名
    img_info = next((item for item in data['images'] if item['id'] == img_id), None)
    if not img_info:
        print(f"❌ 找不到 Image ID {img_id} 的图片信息")
        return

    img_filename = img_info['file_name']
    img_path = os.path.join(IMG_ROOT, img_filename)
    img_w, img_h = img_info['width'], img_info['height']

    print("-" * 40)
    print(f"🔍 检查样本 ID: {SAMPLE_IDX}")
    print(f"🖼️ 图片尺寸 (W x H): {img_w} x {img_h}")
    print(f"📦 JSON BBox 数据: {bbox}")

    # === 核心侦探逻辑 ===
    x, y, w, h = bbox

    # 1. 数值检查
    is_xyxy_suspect = False
    if x + w > img_w * 1.1:  # 如果 x+w 远超图片宽度
        print(f"⚠️ [高能预警] x + w ({x + w}) > 图片宽度 ({img_w})！")
        print("👉 极大可能是 XYXY 格式误写成了 XYWH！")
        is_xyxy_suspect = True
    elif w > img_w or h > img_h:
        print(f"⚠️ [警告] 框的宽高 ({w}, {h}) 比图片本身还大！")

    # 2. 可视化绘制
    if not os.path.exists(img_path):
        print(f"❌ 图片文件不存在: {img_path}")
        return

    try:
        im = Image.open(img_path)
    except Exception as e:
        print(f"❌ 无法打开图片: {e}")
        return

    fig, ax = plt.subplots(figsize=(10, 10))
    ax.imshow(im)

    # 画框：Matplotlib 的 Rectangle 接收 (x,y), width, height
    # 如果数据是 xyxy，这里的 w 其实是 x2，框会超级宽，画到姥姥家去
    rect = patches.Rectangle((x, y), w, h, linewidth=3, edgecolor='r', facecolor='none')
    ax.add_patch(rect)

    # 加个标题
    status = "SUSPECTED XYXY (WRONG)" if is_xyxy_suspect else "LOOKS LIKE XYWH (OK)"
    ax.set_title(f"BBox Check: {status}\nBlue=Image Edge, Red=BBox", color='r' if is_xyxy_suspect else 'g')

    save_name = 'bbox_verification.png'
    plt.savefig(save_name)
    print("-" * 40)
    print(f"✅ 验证图已生成: {os.path.abspath(save_name)}")
    print("👉 请打开图片：如果红框飞出去了，或者大得离谱，那就是格式错了！")


if __name__ == "__main__":
    check_bbox()