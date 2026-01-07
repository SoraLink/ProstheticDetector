import json
import os
from collections import defaultdict

# 定义关键点名称，方便查看 (0-16)
COCO_NAMES = [
    "0: Nose", "1: L-Eye", "2: R-Eye", "3: L-Ear", "4: R-Ear",
    "5: L-Shoulder", "6: R-Shoulder", "7: L-Elbow", "8: R-Elbow",
    "9: L-Wrist", "10: R-Wrist", "11: L-Hip", "12: R-Hip",
    "13: L-Knee", "14: R-Knee", "15: L-Ankle", "16: R-Ankle"
]

# 残肢名称 (17-24) - 对应你的 RESIDUAL_TO_INDEX_MAP
RES_NAMES = [
    "17: L-Elbow-Res-Above (ID 1)",
    "18: R-Elbow-Res-Above (ID 2)",
    "19: L-Elbow-Res-Below (ID 3)",
    "20: R-Elbow-Res-Below (ID 4)",
    "21: L-Knee-Res-Above (ID 5)",
    "22: R-Knee-Res-Above (ID 6)",
    "23: L-Knee-Res-Below (ID 7)",
    "24: R-Knee-Res-Below (ID 8)"
]


def analyze_dataset(json_path):
    if not os.path.exists(json_path):
        print(f"文件不存在: {json_path}")
        return

    print(f"\n{'=' * 20} 正在分析: {json_path} {'=' * 20}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 计数器
    # 结构: stats[kpoint_index]['normal'/'prosthetic'/'residual'] = count
    stats = defaultdict(lambda: {"normal": 0, "prosthetic": 0, "residual": 0})

    total_anns = len(data['annotations'])
    print(f"总标注数 (Annotations): {total_anns}")

    for ann in data['annotations']:
        kps = ann.get('keypoints', [])  # flat list
        types = ann.get('keypoint_types', [])

        # 安全检查
        if not types or len(types) != 25:
            continue

        # 遍历所有 25 个点
        for i in range(25):
            k_type = types[i]
            # 获取可见性 v (x, y, v)
            # 索引 i 对应的 v 在 list 中的位置是 i*3 + 2
            v = kps[i * 3 + 2]

            # 只有当点是可见的 (v > 0) 我们才统计它的属性
            # 如果 v=0，即使 type=0，通常也是未标注点，不算入“有效样本”
            if v > 0:
                if i < 17:
                    # COCO 点 (0-16)
                    if k_type == 0:
                        stats[i]['normal'] += 1
                    elif k_type == 1:
                        stats[i]['prosthetic'] += 1
                else:
                    # 残肢点 (17-24)
                    # 你的逻辑中残肢点 type=0 代表存在 (Step B), type=2 代表 Missing
                    if k_type == 0:
                        stats[i]['residual'] += 1

    # ================= 输出报告 =================

    print(f"\n--- [1] COCO 关键点 (0-16) 假肢/肉身 分布 ---")
    print(f"{'ID':<4} {'Name':<15} | {'Normal (Type 0)':<15} | {'Prosthetic (Type 1)':<20} | {'P占比 (%)':<10}")
    print("-" * 80)

    total_p_count = 0

    for i in range(17):
        n_count = stats[i]['normal']
        p_count = stats[i]['prosthetic']
        total = n_count + p_count
        ratio = (p_count / total * 100) if total > 0 else 0.0
        total_p_count += p_count

        short_name = COCO_NAMES[i].split(":")[1].strip()
        print(f"{i:<4} {short_name:<15} | {n_count:<15} | {p_count:<20} | {ratio:.2f}%")

    print("-" * 80)
    print(f"总计检测到假肢关键点 (0-16范围): {total_p_count} 个")

    print(f"\n--- [2] 残肢关键点 (17-24) 存在数量统计 ---")
    print(f"注意：这里统计的是 type=0 且 visibility>0 的点")
    print(f"{'Idx':<4} {'Name (Tool ID)':<30} | {'Count (Exist)':<10}")
    print("-" * 60)

    for i in range(17, 25):
        r_count = stats[i]['residual']
        # 对应 output 里的 name
        r_name = RES_NAMES[i - 17]
        print(f"{i:<4} {r_name:<30} | {r_count:<10}")

    print("-" * 60)


if __name__ == "__main__":
    # 在这里填入你转换后的文件名
    analyze_dataset("labels_train_final.json")
    analyze_dataset("labels_val_final.json")
    analyze_dataset("labels_test_final.json")