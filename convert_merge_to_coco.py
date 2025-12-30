import json
import os

# ================= 映射配置 =================

# 1. 最终输出的关键点总数
TOTAL_KPS = 25

# 2. 假肢点映射 (工具ID -> COCO索引)
PROSTHETIC_TO_COCO_MAP = {
    9: 7, 10: 8,  # Elbows
    11: 9, 12: 10,  # Wrists
    17: 9, 18: 10,  # Wrist Ends
    13: 13, 14: 14,  # Knees
    15: 15, 16: 16,  # Ankles
    19: 15, 20: 16  # Ankle Ends
}

# 3. 残肢点映射 (工具ID -> 新索引 17-24)
RESIDUAL_TO_INDEX_MAP = {
    1: 17, 2: 18,
    3: 19, 4: 20,
    5: 21, 6: 22,
    7: 23, 8: 24
}

# 4. Skip 逻辑控制映射
# 格式: { 控制者ID(残肢点): 被控制的COCO索引(关节) }
SKIP_CONTROL_MAP = {
    1: 7,  # ID 1 (Left Elbow Res Above)  -> Controls COCO 7 (Left Elbow)
    2: 8,  # ID 2 (Right Elbow Res Above) -> Controls COCO 8 (Right Elbow)
    5: 13,  # ID 5 (Left Knee Res Above)   -> Controls COCO 13 (Left Knee)
    6: 14  # ID 6 (Right Knee Res Above)  -> Controls COCO 14 (Right Knee)
}


def recalculate_bbox(keypoints_list, img_w, img_h, padding_ratio=1.25):
    """
    根据关键点重新计算 BBox，并给予一定的扩充 (Padding)。
    """
    valid_x = []
    valid_y = []

    # 遍历所有点 (步长为4)
    for i in range(0, len(keypoints_list), 3):
        x = keypoints_list[i]
        y = keypoints_list[i + 1]
        v = keypoints_list[i + 2]

        # 过滤条件：
        # 1. v > 0: 必须是可见/有效点
        # 2. x > 1 and y > 1: 必须有有效坐标
        # 注意: Skip 点 [0, 0, 2, 2] 虽然 v=2，但 x=0，会被正确排除，不会拉偏 BBox
        if v > 0 and x > 1 and y > 1:
            valid_x.append(x)
            valid_y.append(y)

    # 如果没有有效点 (极少见)，返回 None
    if not valid_x or not valid_y:
        return None

    min_x, max_x = min(valid_x), max(valid_x)
    min_y, max_y = min(valid_y), max(valid_y)

    width = max_x - min_x
    height = max_y - min_y

    # 计算中心点
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    # 扩张
    new_width = width * padding_ratio
    new_height = height * padding_ratio

    # 计算新的左上角
    new_x = cx - new_width / 2.0
    new_y = cy - new_height / 2.0

    # 边界截断 (Clip to image boundaries)
    new_x = max(0, new_x)
    new_y = max(0, new_y)

    # 防止右下角越界
    if new_x + new_width > img_w:
        new_width = img_w - new_x
    if new_y + new_height > img_h:
        new_height = img_h - new_y

    return [new_x, new_y, new_width, new_height]


def convert_json(input_path, output_path):
    print(f"Reading: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    new_data = {
        "info": data.get("info", {}),
        "licenses": data.get("licenses", []),
        "categories": [],
        "images": [],
        "annotations": []
    }

    # --- 1. Categories ---
    coco_kps = [
        "nose", "left_eye", "right_eye", "left_ear", "right_ear",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
        "left_wrist", "right_wrist", "left_hip", "right_hip",
        "left_knee", "right_knee", "left_ankle", "right_ankle"
    ]
    res_kps = [
        "L-Elbow-Res-Above", "R-Elbow-Res-Above",
        "L-Elbow-Res-Below", "R-Elbow-Res-Below",
        "L-Knee-Res-Above", "R-Knee-Res-Above",
        "L-Knee-Res-Below", "R-Knee-Res-Below"
    ]

    # 【修复】完整填入骨架列表，防止可视化报错
    coco_skeleton = [
        [16, 14], [14, 12], [17, 15], [15, 13],
        [12, 13], [6, 12], [7, 13], [6, 7],
        [6, 8], [7, 9], [8, 10], [9, 11],
        [2, 3], [1, 2], [1, 3], [2, 4], [3, 5], [4, 6], [5, 7]
    ]
    ld_skeleton = [
        [6, 18], [7, 19], [8, 20], [9, 21],
        [12, 22], [13, 23], [14, 24], [15, 25]
    ]

    new_cat = {
        "id": 1,
        "name": "person_prosthesis_merged",
        "supercategory": "person",
        "keypoints": coco_kps + res_kps,
        "num_keypoints": TOTAL_KPS,
        "skeleton": coco_skeleton + ld_skeleton
    }
    new_data["categories"].append(new_cat)

    # --- 2. Images ---
    valid_image_ids = set()
    img_dims = {}
    for img in data.get("images", []):
        new_data["images"].append(img)
        valid_image_ids.add(img['id'])
        img_dims[img['id']] = (img.get('width', 0), img.get('height', 0))

    # --- 3. Annotations ---
    for ann in data.get("annotations", []):
        if ann["image_id"] not in valid_image_ids: continue

        final_kps_list = [[0, 0, 0, 0] for _ in range(TOTAL_KPS)]

        # Step A: 填入原始 COCO 数据
        old_kps = ann.get("keypoints", [])
        for i in range(17):
            if i * 3 + 2 < len(old_kps):
                x, y, v = old_kps[i * 3], old_kps[i * 3 + 1], old_kps[i * 3 + 2]
                if v > 0:
                    final_kps_list[i] = [x, y, v, 0]  # 默认为 Human (0)

        new_kps_dict = ann.get("new_keypoints", {})

        # Step B-1: 填入工具标注的点
        for tid_str, val in new_kps_dict.items():
            tid = int(tid_str)
            if not isinstance(val, list) or len(val) < 3:
                raise ValueError("invalid value of id: {}, {}".format(tid_str, val))

            raw_x, raw_y, raw_vis = val[0], val[1], val[2]

            target_idx = -1
            point_type = 2

            if tid in RESIDUAL_TO_INDEX_MAP:
                target_idx = RESIDUAL_TO_INDEX_MAP[tid]
                point_type = 0  # 残肢 (Exist)
            elif tid in PROSTHETIC_TO_COCO_MAP:
                target_idx = PROSTHETIC_TO_COCO_MAP[tid]
                point_type = 1  # 假肢 (Exist)

            if target_idx != -1 and raw_x != -1:
                final_kps_list[target_idx] = [raw_x, raw_y, raw_vis, point_type]

        # Step B-2: 处理 Skip 逻辑
        for ctrl_id, target_coco_idx in SKIP_CONTROL_MAP.items():
            ctrl_id_str = str(ctrl_id)
            if ctrl_id_str in new_kps_dict:
                val = new_kps_dict[ctrl_id_str]
                if len(val) > 4 and val[4] is True:
                    # Skip: 坐标归零，Vis=2 (Visible)，Type=2 (Not Exists)
                    final_kps_list[target_coco_idx] = [0, 0, 2, 2]

        # Step C: 展平
        flat_kps_3d = []
        final_types = []
        num_valid_coco = 0
        for item in final_kps_list:
            x, y, vis, point_type = item
            flat_kps_3d.extend([x, y, vis])
            final_types.append(point_type)
            if vis > 0:
                num_valid_coco += 1

        new_ann = ann.copy()
        new_ann["keypoints"] = flat_kps_3d
        new_ann["keypoint_types"] = final_types
        new_ann["num_keypoints"] = num_valid_coco

        # --- Step D: BBox 重算 ---
        # 【修复】直接获取，避免 .get() 返回 None 导致解包错误
        # 之前的逻辑保证了 valid_image_ids 存在，所以 img_dims 必有 key
        img_w, img_h = img_dims[ann['image_id']]

        if img_w <= 0 or img_h <= 0:
            raise ValueError(f"Invalid image dimensions for Image ID {ann['image_id']}: ({img_w}, {img_h})")

        new_bbox = recalculate_bbox(flat_kps_3d, img_w, img_h, padding_ratio=1.25)

        if new_bbox:
            new_ann['bbox'] = new_bbox
            new_ann['area'] = new_bbox[2] * new_bbox[3]

        if "new_keypoints" in new_ann: del new_ann["new_keypoints"]
        new_data["annotations"].append(new_ann)

    # --- 4. Save ---
    print(f"Output: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False)


if __name__ == "__main__":
    convert_json("labels_test_round2.json", "test_annotations_merged.json")