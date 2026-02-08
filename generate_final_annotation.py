import json
import os
from copy import deepcopy

# ================= 配置 =================
# 必须与你标注工具里的列表完全一致
KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist",
    "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle",
    "L_Middle_Tip", "R_Middle_Tip", "L_Heel", "R_Heel", "L_Toe_Tip", "R_Toe_Tip",
    "L-Elbow-Res-Above", "R-Elbow-Res-Above", "L-Elbow-Res-Below", "R-Elbow-Res-Below",
    "L-Knee-Res-Above", "R-Knee-Res-Above", "L-Knee-Res-Below", "R-Knee-Res-Below"
]


def merge_annotations(source_path, delta_path, output_path):
    print(f"正在加载底库: {source_path}")
    with open(source_path, 'r', encoding='utf-8') as f:
        source_data = json.load(f)

    print(f"正在加载增量: {delta_path}")
    with open(delta_path, 'r', encoding='utf-8') as f:
        delta_data = json.load(f)

    changes_map = delta_data.get("changes", {})

    new_annotations = []
    stats = {
        "kept": 0,
        "modified": 0,
        "deleted": 0,
        "missing_zeroed": 0  # 统计有多少个点被强制归零
    }

    # 遍历原始所有的 annotations
    for ann in source_data.get('annotations', []):
        key = f"{ann['image_id']}_{ann['id']}"

        # 1. 物理删除逻辑
        if key in changes_map and changes_map[key].get("__DELETED__") is True:
            stats["deleted"] += 1
            continue

        new_ann = deepcopy(ann)

        # 2. 修改更新逻辑
        if key in changes_map:
            patch = changes_map[key]
            is_modified = False

            # 补全字段以防报错
            num_kps = len(KEYPOINT_NAMES)
            if 'keypoints' not in new_ann: new_ann['keypoints'] = [0] * (num_kps * 3)
            if 'keypoint_types' not in new_ann: new_ann['keypoint_types'] = [0] * num_kps

            for idx, kp_name in enumerate(KEYPOINT_NAMES):
                if kp_name in patch:
                    # 获取新值: [x, y, v, type]
                    new_vals = patch[kp_name]
                    x, y, v, t = new_vals[0], new_vals[1], new_vals[2], new_vals[3]

                    # =========================================
                    # 【核心修改】 如果是 Missing (Type=2)，坐标强制为 0
                    # =========================================
                    if t == 2:
                        x, y = 0.0, 0.0
                        # v 和 t 保持原样 (正如你要求的)
                        stats["missing_zeroed"] += 1

                    # 更新 keypoints 列表
                    base_idx = idx * 3
                    new_ann['keypoints'][base_idx] = x
                    new_ann['keypoints'][base_idx + 1] = y
                    new_ann['keypoints'][base_idx + 2] = v

                    # 更新 keypoint_types 列表
                    new_ann['keypoint_types'][idx] = t

                    is_modified = True

            if is_modified:
                stats["modified"] += 1
            else:
                stats["kept"] += 1
        else:
            stats["kept"] += 1

        new_annotations.append(new_ann)

    # 替换旧数据
    source_data['annotations'] = new_annotations

    print("-" * 35)
    print(f"融合完成！")
    print(f"保留未动: {stats['kept']}")
    print(f"修改更新: {stats['modified']}")
    print(f"物理删除: {stats['deleted']}")
    print(f"Missing点归零次数: {stats['missing_zeroed']}")
    print("-" * 35)

    print(f"正在保存到: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(source_data, f, ensure_ascii=False)


if __name__ == "__main__":
    # === 请在这里修改文件名 ===
    SOURCE_FILE = "./labels_residual_fix/labels_test_fix_residual_kpts.json"  # 你的原始 JSON
    DELTA_FILE = "./test/merged_final.json"  # 你的标注工具生成的 JSON
    OUTPUT_FILE = "./test/test_annotation.json"  # 输出的新文件名

    if not os.path.exists(SOURCE_FILE) or not os.path.exists(DELTA_FILE):
        print("错误：找不到输入文件，请检查文件名。")
    else:
        merge_annotations(SOURCE_FILE, DELTA_FILE, OUTPUT_FILE)