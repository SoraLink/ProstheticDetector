import json
import tkinter as tk
from tkinter import filedialog
import os
from collections import defaultdict

# === 配置区域 ===
RESIDUAL_NAMES = {
    1: '左上臂残肢 (Above Left Elbow)',
    2: '右上臂残肢 (Above Right Elbow)',
    3: '左前臂残肢 (Below Left Elbow)',
    4: '右前臂残肢 (Below Right Elbow)',
    5: '左大腿残肢 (Above Left Knee)',
    6: '右大腿残肢 (Above Right Knee)',
    7: '左小腿残肢 (Below Left Knee)',
    8: '右小腿残肢 (Below Right Knee)'
}


def analyze_single_file(file_path):
    """
    分析单个 JSON 文件
    返回: (文件名, 原始图片总数, 有效图片数, 残肢统计字典)
    """
    filename = os.path.basename(file_path)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return filename, 0, 0, defaultdict(int)

    # 1. 获取原始图片总数
    images_list = data.get("images", [])
    total_raw_images = len(images_list)

    # 2. 统计有效标注
    annotations = data.get("annotations", [])
    valid_image_ids = set()
    stats = defaultdict(int)

    for ann in annotations:
        if "new_keypoints" not in ann:
            continue

        new_kps = ann["new_keypoints"]
        has_valid_point = False

        for kp_id_str, val in new_kps.items():
            kp_id = int(kp_id_str)

            # 检查点是否有效 (val[0] != -1)
            if isinstance(val, list) and len(val) >= 2 and val[0] != -1:
                has_valid_point = True

                # 统计残肢 (ID 1-8)
                if kp_id in RESIDUAL_NAMES:
                    stats[kp_id] += 1

        if has_valid_point:
            valid_image_ids.add(ann["image_id"])

    return filename, total_raw_images, len(valid_image_ids), stats


def print_stats(title, raw_count, valid_count, stats):
    """
    格式化打印统计结果
    """
    print("=" * 60)
    print(f" 📂 {title}")
    print("=" * 60)

    # 计算占比
    ratio = (valid_count / raw_count * 100) if raw_count > 0 else 0.0

    print(f"原始图片总数 (Total Images):     {raw_count}")
    print(f"含假肢/残肢图 (Annotated):       {valid_count}")
    print(f"数据集占比 (Ratio):              {ratio:.2f}%")
    print("-" * 60)

    sorted_ids = sorted(RESIDUAL_NAMES.keys())
    upper_count = 0
    lower_count = 0

    print(f"{'ID':<4} | {'部位名称':<30} | {'数量':<5}")
    print("-" * 60)

    for kp_id in sorted_ids:
        count = stats[kp_id]
        name = RESIDUAL_NAMES[kp_id]
        print(f"{kp_id:<4} | {name:<30} | {count:<5}")

        if 1 <= kp_id <= 4:
            upper_count += count
        elif 5 <= kp_id <= 8:
            lower_count += count

    print("-" * 60)
    print(f"  上肢残肢点总计 (Upper): {upper_count}")
    print(f"  下肢残肢点总计 (Lower): {lower_count}")
    print(f"  所有残肢点总计 (Total): {upper_count + lower_count}")
    print("\n")


def main():
    root = tk.Tk()
    root.withdraw()

    print("请选择文件 (支持多选，例如同时选择 train.json, val.json, test.json)...")
    file_paths = filedialog.askopenfilenames(
        title="选择要统计的 JSON 文件 (可多选)",
        filetypes=[("JSON Files", "*.json")]
    )

    if not file_paths:
        print("未选择文件。")
        return

    # 汇总变量
    total_raw_sum = 0
    total_valid_sum = 0
    total_stats = defaultdict(int)

    # 1. 分别统计
    print("\n" + "#" * 25 + " 分别统计结果 " + "#" * 25 + "\n")

    for path in file_paths:
        fname, raw_cnt, valid_cnt, f_stats = analyze_single_file(path)
        print_stats(fname, raw_cnt, valid_cnt, f_stats)

        # 累加到汇总
        total_raw_sum += raw_cnt
        total_valid_sum += valid_cnt
        for k, v in f_stats.items():
            total_stats[k] += v

    # 2. 汇总统计
    print("\n" + "#" * 25 + "   汇总结果   " + "#" * 25 + "\n")
    print_stats("TOTAL (所有文件汇总)", total_raw_sum, total_valid_sum, total_stats)

    input("统计完成，按回车键退出...")


if __name__ == "__main__":
    main()