import json
import os
import shutil
import cv2
from collections import Counter


def process_prosthetic_images(json_path, source_img_dir, save_dir, expand_ratio=0.2):
    """
    expand_ratio: 0.2 表示 BBox 的长宽分别扩大 20% (即上下左右各往外扩 10% 左右)
    """

    if not os.path.exists(json_path):
        print(f"JSON文件不存在: {json_path}")
        return

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        print(f"创建保存目录: {save_dir}")

    print(f"正在读取: {json_path} ...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    img_map = {img['id']: img['file_name'] for img in data['images']}

    # 统计每张图的人数
    print("正在统计每张图片的人数...")
    img_person_count = Counter([ann['image_id'] for ann in data['annotations']])

    processed_count = 0

    for ann in data['annotations']:
        types = ann.get('keypoint_types', [])
        kps = ann.get('keypoints', [])
        img_id = ann['image_id']
        ann_id = ann['id']

        if not types or len(types) < 9:
            continue

        # 检查是否含有假肢肘部
        has_prosthetic_elbow = False
        if types[7] == 1 and kps[7 * 3 + 2] > 0:
            has_prosthetic_elbow = True
        if not has_prosthetic_elbow and types[8] == 1 and kps[8 * 3 + 2] > 0:
            has_prosthetic_elbow = True

        if not has_prosthetic_elbow:
            continue

        file_name = img_map.get(img_id)
        if not file_name:
            continue

        src_path = os.path.join(source_img_dir, file_name)

        if not os.path.exists(src_path):
            print(f"[警告] 原图不存在，跳过: {src_path}")
            continue

        person_count = img_person_count[img_id]

        # === 情况 A: 单人 -> 复制整图 ===
        if person_count == 1:
            save_name = f"full_{os.path.basename(file_name)}"
            dst_path = os.path.join(save_dir, save_name)
            shutil.copy2(src_path, dst_path)
            print(f"[单人-复制] {file_name} -> {save_name}")

        # === 情况 B: 多人 -> 扩大 BBox 后裁剪 ===
        else:
            bbox = ann.get('bbox', [])  # [x, y, w, h]
            if not bbox or len(bbox) != 4:
                continue

            img = cv2.imread(src_path)
            if img is None:
                continue

            img_h, img_w = img.shape[:2]
            x, y, w, h = bbox

            # --- 核心修改：扩大 BBox ---
            # 计算需要增加的宽和高 (expand_ratio)
            pad_w = w * expand_ratio / 2  # 左右各分一半
            pad_h = h * expand_ratio / 2  # 上下各分一半

            # 计算新的坐标，并进行边界检查 (Clamp)，防止越界
            # int() 确保坐标是整数
            x1 = int(max(0, x - pad_w))
            y1 = int(max(0, y - pad_h))
            x2 = int(min(img_w, x + w + pad_w))
            y2 = int(min(img_h, y + h + pad_h))

            # 裁剪
            if x2 > x1 and y2 > y1:
                crop_img = img[y1:y2, x1:x2]

                save_name = f"crop_ann{ann_id}_{os.path.basename(file_name)}"
                dst_path = os.path.join(save_dir, save_name)

                cv2.imwrite(dst_path, crop_img)
                print(f"[多人-裁剪] {file_name} (AnnID:{ann_id}) -> {save_name} (扩大 {(x2 - x1) / (w):.2f}x)")
            else:
                print(f"[警告] BBox无效: {file_name}")

        processed_count += 1

    print("\n" + "=" * 50)
    print(f"处理完成。")
    print("=" * 50)


if __name__ == "__main__":
    json_file = "labels_test_final.json"
    source_images = "./ldpose_final/ldpose_test"
    output_folder = "prosthetic_elbow_dataset"

    # 在这里调整 expand_ratio，0.3 意味着框会更大一些
    process_prosthetic_images(json_file, source_images, output_folder, expand_ratio=0.3)