import json
import os

# ================= 映射配置 =================

# 1. 最终输出的关键点总数
# 0-16: COCO 标准点 (包含真人和假肢)
# 17-24: 残肢端点 (Residual Ends)
TOTAL_KPS = 25

# 2. 你的工具 ID (1-20) 到 COCO Index (0-16) 的映射
# 只有假肢点需要映射进 COCO 骨架，残肢点追加在后面
# 格式: { 工具ID: COCO索引 }
PROSTHETIC_TO_COCO_MAP = {
    # 假肢肘 -> COCO Elbow
    9: 7,  # L-Elbow
    10: 8,  # R-Elbow

    # 假肢手腕 -> COCO Wrist
    11: 9,  # L-Wrist
    12: 10,  # R-Wrist
    17: 9,  # L-Wrist End (归并到左手腕)
    18: 10,  # R-Wrist End (归并到右手腕)

    # 假肢膝 -> COCO Knee
    13: 13,  # L-Knee
    14: 14,  # R-Knee

    # 假肢踝 -> COCO Ankle
    15: 15,  # L-Ankle
    16: 16,  # R-Ankle
    19: 15,  # L-Ankle End (归并到左脚踝)
    20: 16  # R-Ankle End (归并到右脚踝)
}

# 3. 残肢点映射 (工具ID -> 新的数组索引 17-24)
RESIDUAL_TO_INDEX_MAP = {
    1: 17, 2: 18,  # Elbow Above
    3: 19, 4: 20,  # Elbow Below
    5: 21, 6: 22,  # Knee Above
    7: 23, 8: 24  # Knee Below
}


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

    # --- 1. 构建 Categories (25个点) ---
    # COCO 原名
    coco_kps = [
        "nose", "left_eye", "right_eye", "left_ear", "right_ear",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
        "left_wrist", "right_wrist", "left_hip", "right_hip",
        "left_knee", "right_knee", "left_ankle", "right_ankle"
    ]

    # 残肢名 (追加在后面)
    res_kps = [
        "L-Elbow-Res-Above", "R-Elbow-Res-Above",
        "L-Elbow-Res-Below", "R-Elbow-Res-Below",
        "L-Knee-Res-Above", "R-Knee-Res-Above",
        "L-Knee-Res-Below", "R-Knee-Res-Below"
    ]

    new_cat = {
        "id": 1,
        "name": "person_prosthesis_merged",
        "supercategory": "person",
        "keypoints": coco_kps + res_kps,
        "num_keypoints": TOTAL_KPS
    }
    new_data["categories"].append(new_cat)

    # --- 2. 过滤图片 ---
    valid_image_ids = set()
    for img in data.get("images", []):
        new_data["images"].append(img)
        valid_image_ids.add(img['id'])

    # --- 3. 处理标注 ---
    for ann in data.get("annotations", []):

        # 初始化 25 个点的数组: [x, y, v, type]
        # 默认全部初始化为 0,0,0,2 (不存在)
        final_kps_list = [[0, 0, 0, 2] for _ in range(TOTAL_KPS)]

        # Step A: 填入原始 COCO 数据 (0-16)
        # 默认认为这些是 Type 0 (Human)
        old_kps = ann.get("keypoints", [])
        for i in range(17):
            if i * 3 + 2 < len(old_kps):
                x = old_kps[i * 3]
                y = old_kps[i * 3 + 1]
                v = old_kps[i * 3 + 2]
                if v > 0:
                    # 有效的 COCO 点，填入，标记为 Type 0
                    final_kps_list[i] = [x, y, v, 0]
                else:
                    # 无效点，保持 Type 2
                    final_kps_list[i] = [0, 0, 0, 2]

        # Step B: 使用工具的新标注 (New Keypoints) 进行 覆盖 或 追加
        new_kps_dict = ann.get("new_keypoints", {})

        # 遍历工具里的所有 ID (1-20)
        # 注意：这里我们遍历 dict 的 keys，因为没标的我们就不动
        for tid_str, val in new_kps_dict.items():
            tid = int(tid_str)

            # 数据校验
            if not isinstance(val, list) or len(val) < 3: continue
            raw_x, raw_y, raw_vis = val[0], val[1], val[2]
            is_skip = val[4] if len(val) > 4 else False

            # 确定这个点应该填在 final_kps_list 的哪个 index
            target_idx = -1
            point_type = 2

            # 1. 判断是否是残肢 (Type 0)
            if tid in RESIDUAL_TO_INDEX_MAP:
                target_idx = RESIDUAL_TO_INDEX_MAP[tid]
                point_type = 0  # 残肢也是肉体

            # 2. 判断是否是假肢 (Type 1) -> 覆盖 COCO 槽位
            elif tid in PROSTHETIC_TO_COCO_MAP:
                target_idx = PROSTHETIC_TO_COCO_MAP[tid]
                point_type = 1  # 假肢

            if target_idx == -1: continue  # 未知 ID，跳过

            # 3. 填入数据
            if is_skip:
                # 显式 Skip：设为 0,0,0,2 (不存在)
                final_kps_list[target_idx] = [0, 0, 0, 2]
            elif raw_x == -1:
                # 无效数据：不操作，保留 Step A 的 COCO 值 (如果是非覆盖位则保留空)
                # 或者如果你希望工具里的 "未标注" 意味着 "删除 COCO 的标注"，则这里要设为 [0,0,0,2]
                # 通常：如果工具里没标，说明没修过，保留原值比较安全。除非显式 -1 意味着擦除。
                pass
            else:
                # 有效的新标注 -> 强制覆盖
                final_kps_list[target_idx] = [raw_x, raw_y, raw_vis, point_type]

        # Step C: 展平数组
        flat_kps = []
        num_valid = 0
        for item in final_kps_list:
            flat_kps.extend(item)
            if item[2] > 0: num_valid += 1

        new_ann = ann.copy()
        new_ann["keypoints"] = flat_kps
        new_ann["num_keypoints"] = num_valid
        if "new_keypoints" in new_ann: del new_ann["new_keypoints"]

        new_data["annotations"].append(new_ann)

    # --- 4. 保存 ---
    print(f"Output: {output_path}")
    print(f"Keypoints per person: {TOTAL_KPS} (x4 dims)")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False)


if __name__ == "__main__":
    convert_json("labels_round2.json", "train_annotations_merged.json")