import json
import os

# ================= 配置区域 =================
KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist",
    "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle",
    "L_Middle_Tip", "R_Middle_Tip", "L_Heel", "R_Heel", "L_Toe_Tip", "R_Toe_Tip",
    "L-Elbow-Res-Above", "R-Elbow-Res-Above", "L-Elbow-Res-Below", "R-Elbow-Res-Below",
    "L-Knee-Res-Above", "R-Knee-Res-Above", "L-Knee-Res-Below", "R-Knee-Res-Below"
]

LOGIC_MAP = {
    "L-Elbow-Res-Above": "left_elbow", "R-Elbow-Res-Above": "right_elbow",
    "L-Elbow-Res-Below": "left_wrist", "R-Elbow-Res-Below": "right_wrist",
    "L-Knee-Res-Above": "left_knee", "R-Knee-Res-Above": "right_knee",
    "L-Knee-Res-Below": "left_ankle", "R-Knee-Res-Below": "right_ankle"
}

UPPER_MAP = {
    "L-Elbow-Res-Below": "left_elbow", "R-Elbow-Res-Below": "right_elbow",
    "L-Knee-Res-Below": "left_knee", "R-Knee-Res-Below": "right_knee"
}




def fix_and_resize_bbox(json_path, output_path):
    print(f"📖 读取文件: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    img_map = {img['id']: (img['width'], img['height']) for img in data.get('images', [])}
    kp_map = {name: i for i, name in enumerate(KEYPOINT_NAMES)}

    stats = {"total_ann": 0, "fixed_res": 0, "fixed_out_of_bounds": 0, "bbox_updated": 0}

    for ann in data.get("annotations", []):
        img_id = ann.get('image_id')
        if img_id not in img_map: continue

        img_w, img_h = img_map[img_id]
        kps = ann.get("keypoints", [])
        types = ann.get("keypoint_types", [])
        if not kps: continue

        stats["total_ann"] += 1
        is_modified = False

        # --- 1. 过滤越界关键点 ---
        for i in range(len(kps) // 3):
            x, y, v = kps[i * 3], kps[i * 3 + 1], kps[i * 3 + 2]
            if v > 0:
                # 检查是否超出图片边界
                if x < 0 or x >= img_w or y < 0 or y >= img_h:
                    kps[i * 3], kps[i * 3 + 1], kps[i * 3 + 2] = 0, 0, 0
                    if types: types[i] = 0
                    is_modified = True
                    stats["fixed_out_of_bounds"] += 1

        # --- 2. 残肢点逻辑 ---
        for res_name, check_name in LOGIC_MAP.items():
            res_idx, check_idx = kp_map[res_name], kp_map[check_name]
            check_v = kps[check_idx * 3 + 2]
            check_type = types[check_idx] if types else 0
            res_type = types[res_idx] if types else 2
            res_vis = kps[res_idx * 3 + 2]
            if res_type == 0 and res_vis > 0:
                continue

            # 情况 A: 健全 (v > 0) -> 抹除残肢点
            if check_type == 0 and check_v > 0:
                if not (types[res_idx] == 2 and kps[res_idx * 3 + 2] == 2):
                    kps[res_idx * 3:res_idx * 3 + 3] = [0, 0, 2]
                    if types: types[res_idx] = 2
                    is_modified = True
                    stats["fixed_res"] += 1
            # 情况 B: 不确定 (v == 0) -> 重置残肢点
            elif check_v == 0:
                if not (types[res_idx] == 0 and kps[res_idx * 3 + 2] == 0):
                    kps[res_idx * 3:res_idx * 3 + 3] = [0, 0, 0]
                    if types: types[res_idx] = 0
                    is_modified = True
                    stats["fixed_res"] += 1

            if res_name in UPPER_MAP.keys():
                upper_name = UPPER_MAP[res_name]
                upper_idx = kp_map[upper_name]
                upper_type = types[upper_idx] if types else 0
                if upper_type == check_type:
                    if not (types[res_idx] == 2 and kps[res_idx * 3 + 2] == 2):
                        kps[res_idx * 3:res_idx * 3 + 3] = [0, 0, 2]
                        if types: types[res_idx] = 2
                        is_modified = True
                        stats["fixed_res"] += 1

        # --- 3. 重新计算并缩放 BBox ---
        # 无论前面是否修改，我们都根据最新的有效点重算 BBox
        valid_coords = [(kps[i * 3], kps[i * 3 + 1]) for i in range(len(kps) // 3) if kps[i * 3 + 2] > 0 and types[i] != 2]

        if valid_coords:
            xs, ys = zip(*valid_coords)
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)

            w, h = x_max - x_min, y_max - y_min
            cx, cy = x_min + w / 2, y_min + h / 2

            # 1.25 倍扩大
            new_w, new_h = w * 1.25, h * 1.25

            # 边界截断
            nx1 = max(0, cx - new_w / 2)
            ny1 = max(0, cy - new_h / 2)
            nx2 = min(img_w, cx + new_w / 2)
            ny2 = min(img_h, cy + new_h / 2)

            new_bbox = [nx1, ny1, nx2 - nx1, ny2 - ny1]

            # 检查 BBox 是否真的变了 (防止浮点数微小差异导致错误标记，这里简单比较)
            if "bbox" not in ann or abs(ann["bbox"][0] - nx1) > 0.1:
                ann["bbox"] = new_bbox
                ann["area"] = new_bbox[2] * new_bbox[3]
                is_modified = True
                stats["bbox_updated"] += 1

        if is_modified:
            ann["keypoints"] = kps
            if types: ann["keypoint_types"] = types

    print(f"📊 处理完成!")
    print(f"✅ 越界清理: {stats['fixed_out_of_bounds']} 点")
    print(f"🦾 残肢逻辑修复: {stats['fixed_res']} 点")
    print(f"📦 BBox 重新适配: {stats['bbox_updated']} 处")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


if __name__ == "__main__":
    INPUT = "E:/DATA/pros_final/test/test_final.json"
    OUTPUT = "E:/DATA/pros_final/test/test_final_resize.json"
    if os.path.exists(INPUT):
        fix_and_resize_bbox(INPUT, OUTPUT)