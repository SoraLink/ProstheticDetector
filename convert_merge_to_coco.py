import json
import os

# ================= 1. 映射配置 =================

TOTAL_KPS = 25

# 假肢点映射 (工具ID -> COCO索引)
PROSTHETIC_TO_COCO_MAP = {
    9: 7, 10: 8, 11: 9, 12: 10,
    17: 9, 18: 10, 13: 13, 14: 14,
    15: 15, 16: 16, 19: 15, 20: 16
}

# 残肢点映射 (工具ID -> 新索引 17-24)
RESIDUAL_TO_INDEX_MAP = {
    1: 17, 2: 18, 3: 19, 4: 20,
    5: 21, 6: 22, 7: 23, 8: 24
}

# Skip 逻辑 (工具ID -> 强制Missing的COCO索引)
SKIP_CONTROL_MAP = {
    1: 7, 2: 8, 5: 13, 6: 14
}

# 解剖抑制映射 (核心逻辑)
# 格式: { 触发者残肢ID: [要被消灭的下游关节ID列表] }
ANATOMICAL_SUPPRESSION_MAP = {
    17: [7, 9], 18: [8, 10],  # 上臂残肢 -> 肘、腕没了
    19: [9], 20: [10],  # 前臂残肢 -> 腕没了
    21: [13, 15], 22: [14, 16],  # 大腿残肢 -> 膝、踝没了
    23: [15], 24: [16]  # 小腿残肢 -> 踝没了
}

CHAIN_DEPENDENCY = {
    7: 9,   # 左肘 看 左腕
    8: 10,  # 右肘 看 右腕
    13: 15, # 左膝 看 左踝
    14: 16  # 右膝 看 右踝
}

def recalculate_bbox(keypoints_list_3d, img_w, img_h, padding_ratio=1.25):
    """根据 3D keypoints (x,y,v) 重算 bbox"""
    valid_x = []
    valid_y = []
    # 步长为 3
    for i in range(0, len(keypoints_list_3d), 3):
        x = keypoints_list_3d[i]
        y = keypoints_list_3d[i + 1]
        v = keypoints_list_3d[i + 2]
        if v > 0 and x > 1 and y > 1:
            valid_x.append(x)
            valid_y.append(y)

    if not valid_x or not valid_y:
        return None, 0.0

    min_x, max_x = min(valid_x), max(valid_x)
    min_y, max_y = min(valid_y), max(valid_y)

    raw_w = max_x - min_x
    raw_h = max_y - min_y
    tight_area = raw_w * raw_h

    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    new_width = raw_w * padding_ratio
    new_height = raw_h * padding_ratio

    x1 = cx - new_width / 2.0
    y1 = cy - new_height / 2.0
    x2 = cx + new_width / 2.0
    y2 = cy + new_height / 2.0

    x1 = max(0, min(x1, img_w))
    y1 = max(0, min(y1, img_h))
    x2 = max(0, min(x2, img_w))
    y2 = max(0, min(y2, img_h))

    final_w = x2 - x1
    final_h = y2 - y1

    if final_w <= 1 or final_h <= 1:
        return None, 0.0

    return [x1, y1, final_w, final_h], tight_area


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
    # 仅用于可视化连线
    coco_skeleton = [[16, 14], [14, 12], [17, 15], [15, 13], [12, 13], [6, 12], [7, 13], [6, 7], [6, 8], [7, 9],
                     [8, 10], [9, 11], [2, 3], [1, 2], [1, 3], [2, 4], [3, 5], [4, 6], [5, 7]]
    ld_skeleton = [[6, 18], [7, 19], [8, 20], [9, 21], [12, 22], [13, 23], [14, 24], [15, 25]]

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

        img_w, img_h = img_dims.get(ann['image_id'], (0, 0))
        if img_w <= 0 or img_h <= 0: continue

        # =======================================================
        # Step A: 分段初始化 (核心修正)
        # =======================================================
        final_kps_list = []
        # 0-16 (标准人体点): 默认 Normal (0) -> 兼容普通人的遮挡情况
        for _ in range(17):
            final_kps_list.append([0, 0, 0, 0])
            # 17-24 (残肢点): 默认 Missing (2) -> 兼容普通人没有残肢
        for _ in range(TOTAL_KPS - 17):
            final_kps_list.append([0, 0, 0, 2])

        # =======================================================
        # Step B: 填入数据
        # =======================================================

        # 1. 填入原始 COCO 数据
        old_kps = ann.get("keypoints", [])
        for i in range(17):
            if i * 3 + 2 < len(old_kps):
                x, y, v = old_kps[i * 3], old_kps[i * 3 + 1], old_kps[i * 3 + 2]
                if v > 0:
                    x = max(0, min(x, img_w - 1))
                    y = max(0, min(y, img_h - 1))

                    final_kps_list[i] = [x, y, v, 0]  # Normal

        new_kps_dict = ann.get("new_keypoints", {})

        # 2. 填入工具标注的点 (假肢/残肢)
        for tid_str, val in new_kps_dict.items():
            tid = int(tid_str)
            if not isinstance(val, list) or len(val) < 3: continue

            raw_x, raw_y, raw_vis = val[0], val[1], val[2]
            target_idx = -1
            point_type = 2

            if tid in RESIDUAL_TO_INDEX_MAP:
                target_idx = RESIDUAL_TO_INDEX_MAP[tid]
                point_type = 0  # 残肢 (Normal/Exist)
            elif tid in PROSTHETIC_TO_COCO_MAP:
                target_idx = PROSTHETIC_TO_COCO_MAP[tid]
                point_type = 1  # 假肢 (Prosthetic)

            if target_idx != -1 and raw_x != -1:

                safe_x = max(0, min(raw_x, img_w - 1))
                safe_y = max(0, min(raw_y, img_h - 1))
                final_kps_list[target_idx] = [safe_x, safe_y, raw_vis, point_type]

        # 3. 处理 Skip 逻辑 (显式 Missing)
        for ctrl_id, target_coco_idx in SKIP_CONTROL_MAP.items():
            ctrl_id_str = str(ctrl_id)
            if ctrl_id_str in new_kps_dict:
                val = new_kps_dict[ctrl_id_str]
                if len(val) > 4 and val[4] is True:
                    final_kps_list[target_coco_idx] = [0, 0, 0, 2]  # 强制 Missing

        # =======================================================
        # Step C: 解剖抑制 (安全版) - 解决图外假肢问题
        # =======================================================
        for res_idx, target_joints in ANATOMICAL_SUPPRESSION_MAP.items():
            if res_idx >= len(final_kps_list): continue

            res_node = final_kps_list[res_idx]
            res_vis = res_node[2]
            res_type = res_node[3]

            # 只有当残肢确实存在且可见时
            if res_vis > 0 and res_type != 2:
                for joint_idx in target_joints:
                    current_joint = final_kps_list[joint_idx]
                    current_type = current_joint[3]
                    if current_type != 0:
                        continue

                    is_saved_by_downstream = False
                    if joint_idx in CHAIN_DEPENDENCY:
                        distal_idx = CHAIN_DEPENDENCY[joint_idx]
                        distal_node = final_kps_list[distal_idx]
                        distal_type = distal_node[3]

                        if distal_type == 1:
                            is_saved_by_downstream = True
                    if is_saved_by_downstream:
                        final_kps_list[joint_idx] = [0, 0, 0, 1]
                    else:
                        final_kps_list[joint_idx] = [0, 0, 0, 2]

        # =======================================================
        # Step D: 拆分展平 (适配 MMPose)
        # =======================================================
        flat_kps_3d = []
        final_types = []
        num_valid_coco = 0

        for item in final_kps_list:
            x, y, vis, point_type = item

            flat_kps_3d.extend([x, y, vis])
            final_types.append(point_type)  # 【必须有这行】

            if vis > 0:
                num_valid_coco += 1

        new_ann = ann.copy()
        new_ann["keypoints"] = flat_kps_3d
        new_ann["keypoint_types"] = final_types
        new_ann["num_keypoints"] = num_valid_coco

        # BBox 重算
        img_w, img_h = img_dims.get(ann['image_id'], (0, 0))

        valid_annotation = False

        if img_w > 0:
            result = recalculate_bbox(flat_kps_3d, img_w, img_h, padding_ratio=1.25)
            if result[0] is not None:
                new_bbox, tight_area = result

                if tight_area > 0 and new_bbox[2] > 0 and new_bbox[3] > 0:
                    new_ann['bbox'] = new_bbox
                    new_ann['area'] = float(tight_area)
                    valid_annotation = True

        if valid_annotation:
            if "new_keypoints" in new_ann: del new_ann["new_keypoints"]
            new_data["annotations"].append(new_ann)

        else:
            print(f"丢弃无效数据 (Area=0): ImgID {ann['image_id']} | AnnID {ann['id']}")

    print(f"Output: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False)


if __name__ == "__main__":
    # 替换为你实际的文件名
    convert_json("labels_train_round2.json", "labels_train_final.json")
    convert_json("labels_val_round2.json", "labels_val_final.json")
    convert_json("labels_test_round2.json", "labels_test_final.json")