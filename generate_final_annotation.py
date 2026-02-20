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


def extract_delta_annotations(source_path, delta_path, output_path):
    print(f"📖 正在加载底库: {source_path}")
    with open(source_path, 'r', encoding='utf-8') as f:
        source_data = json.load(f)

    print(f"📖 正在加载增量: {delta_path}")
    with open(delta_path, 'r', encoding='utf-8') as f:
        delta_data = json.load(f)

    changes_map = delta_data.get("changes", {})

    new_annotations = []
    valid_image_ids = set() # 用来记录最终保留下来的有效图片ID

    stats = {
        "processed": 0,             # 在 delta 中且被保留/更新的
        "deleted_by_user": 0,       # 在 delta 中但被标记为 __DELETED__ 的
        "ignored_not_in_delta": 0,  # 根本不在 delta 中的（被直接丢弃）
        "missing_zeroed": 0         # 统计有多少个点被强制归零
    }

    # =========================================================================
    # 1. 遍历并过滤 annotations
    # =========================================================================
    for ann in source_data.get('annotations', []):
        key = f"{ann['image_id']}_{ann['id']}"

        # 【核心修改 1】：如果这个标注根本不在 delta 文件里，直接丢弃！
        if key not in changes_map:
            stats["ignored_not_in_delta"] += 1
            continue

        # 【核心修改 2】：如果在 delta 里，但是被你手动标记为删除了，也丢弃！
        if changes_map[key].get("__DELETED__") is True:
            stats["deleted_by_user"] += 1
            continue

        # 到这里，说明它在 delta 文件里，且是有效标注
        new_ann = deepcopy(ann)
        patch = changes_map[key]

        # 补全字段以防报错
        num_kps = len(KEYPOINT_NAMES)
        if 'keypoints' not in new_ann: new_ann['keypoints'] = [0] * (num_kps * 3)
        if 'keypoint_types' not in new_ann: new_ann['keypoint_types'] = [0] * num_kps

        for idx, kp_name in enumerate(KEYPOINT_NAMES):
            if kp_name in patch:
                # 获取新值: [x, y, v, type]
                new_vals = patch[kp_name]
                x, y, v, t = new_vals[0], new_vals[1], new_vals[2], new_vals[3]

                # 如果是 Missing (Type=2)，坐标强制为 0
                if t == 2:
                    x, y = 0.0, 0.0
                    stats["missing_zeroed"] += 1

                # 更新 keypoints 和 keypoint_types 列表
                base_idx = idx * 3
                new_ann['keypoints'][base_idx] = x
                new_ann['keypoints'][base_idx + 1] = y
                new_ann['keypoints'][base_idx + 2] = v
                new_ann['keypoint_types'][idx] = t

        # 将更新后的标注加入新列表，并记录这张图片的 ID
        new_annotations.append(new_ann)
        valid_image_ids.add(new_ann['image_id'])
        stats["processed"] += 1

    # =========================================================================
    # 2. 清理多余的 images (丢弃没有标注的空图片)
    # =========================================================================
    original_images_count = len(source_data.get('images', []))
    new_images = [img for img in source_data.get('images', []) if img['id'] in valid_image_ids]

    # 替换旧数据
    source_data['annotations'] = new_annotations
    source_data['images'] = new_images

    # =========================================================================
    # 3. 打印报告与保存
    # =========================================================================
    print("-" * 45)
    print(f"🎉 提取融合完成！")
    print(f"✅ 成功保留 (来自 Delta) : {stats['processed']} 个标注")
    print(f"🗑️ 被手动删除 (__DELETED__): {stats['deleted_by_user']} 个标注")
    print(f"👻 未在 Delta 中 (已丢弃) : {stats['ignored_not_in_delta']} 个标注")
    print(f"🔧 Missing 点强制归零次数 : {stats['missing_zeroed']}")
    print(f"🖼️ 图片数量变化           : {original_images_count} 张 -> {len(new_images)} 张")
    print("-" * 45)

    print(f"💾 正在保存到: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(source_data, f, ensure_ascii=False)


if __name__ == "__main__":
    # === 请在这里修改文件名 ===
    SOURCE_FILE = "./train/labels_train_fix_residual_kpts.json"  # 你的原始 JSON
    DELTA_FILE = "./train/train_0-19000.json"                           # 你的标注工具生成的 JSON
    OUTPUT_FILE = "./train/train_0-19000_coco_annotation.json"           # 输出的新文件名

    if not os.path.exists(SOURCE_FILE) or not os.path.exists(DELTA_FILE):
        print("❌ 错误：找不到输入文件，请检查文件名。")
    else:
        extract_delta_annotations(SOURCE_FILE, DELTA_FILE, OUTPUT_FILE)