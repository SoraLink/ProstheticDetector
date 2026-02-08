import json
import os


def merge_residual_points_by_id(ldpose_path, new_ann_path, output_path):
    print(f"正在加载 LDPose 源文件: {ldpose_path}")
    with open(ldpose_path, 'r', encoding='utf-8') as f:
        ld_data = json.load(f)

    print(f"正在加载 你的新标注文件: {new_ann_path}")
    with open(new_ann_path, 'r', encoding='utf-8') as f:
        new_data = json.load(f)

    # 构建 ID 索引
    print("正在构建 ID 索引...")
    ld_map = {ann['id']: ann for ann in ld_data['annotations']}

    update_count = 0

    # ==========================================
    # 定义肢体组 (Limb Groups)
    # 假设 8 个残肢点是按顺序每 2 个对应一个肢体
    # New Indices: 23-30
    # Group 0: 23, 24 (例如: 左臂的上、下残肢位)
    # Group 1: 25, 26 (例如: 右臂的上、下残肢位)
    # Group 2: 27, 28 (例如: 左腿的上、下残肢位)
    # Group 3: 29, 30 (例如: 右腿的上、下残肢位)
    # ==========================================
    limb_groups = [
        [23, 24],
        [25, 26],
        [27, 28],
        [29, 30]
    ]
    # 注意：偏移量 offset = -6 (New 23 -> Old 17)

    print("开始比对并修复残肢点...")

    for user_ann in new_data['annotations']:
        ann_id = user_ann['id']

        if ann_id not in ld_map:
            # 如果找不到对应ID，可以选择跳过或报错，这里保持你原有的报错逻辑
            print(f"ID Warning: {ann_id}")
            raise ValueError('ann_id not in ld_map')

        src_ann = ld_map[ann_id]
        src_kps = src_ann['keypoints']

        # 你的新标注数据
        dst_kps = user_ann['keypoints']

        # 补齐长度检查
        if len(dst_kps) < 93:  # 31 * 3
            raise ValueError(f'dst_kps not enough length for ID {ann_id}')

        # ==========================================
        # 核心修改: 按肢体组 (Limb) 进行遍历
        # ==========================================
        for group in limb_groups:
            # 1. 检查 New 文件中，这个肢体是否已经有了残肢点？
            # 只要组内有一个点是可见的 (v > 0)，就视为该肢体已有标注
            limb_has_new_annotation = False
            for new_idx in group:
                v_index = new_idx * 3 + 2
                if dst_kps[v_index] > 0:
                    limb_has_new_annotation = True
                    break

            # 2. 如果新文件里这个肢体已经有点了，绝对不碰它（尊重你的修改）
            if limb_has_new_annotation:
                continue

            # 3. 如果新文件里这个肢体是空的，才去查旧文件
            for new_idx in group:
                old_idx = new_idx - 6  # 23 -> 17

                src_base = old_idx * 3
                dst_base = new_idx * 3

                s_v = src_kps[src_base + 2]

                # 如果旧文件里这个点存在
                if s_v > 0:
                    # 复制坐标和可见性
                    dst_kps[dst_base] = src_kps[src_base]  # x
                    dst_kps[dst_base + 1] = src_kps[src_base + 1]  # y
                    dst_kps[dst_base + 2] = src_kps[src_base + 2]  # v
                    update_count += 1
                    # 一个肢体通常只有一个残肢点，找到一个复制完其实就可以 break group 了
                    # 但为了保险（万一旧数据有两个点这种脏数据），让它跑完这个 group 也可以

        # 保存回对象
        user_ann['keypoints'] = dst_kps

        # 重新计算 num_keypoints
        visible_kps = sum(1 for j in range(0, len(dst_kps), 3) if dst_kps[j + 2] > 0)
        user_ann['num_keypoints'] = visible_kps

    print(f"修复完成！基于 ID 和 肢体互斥原则，共从旧文件恢复了 {update_count} 个残肢点。")
    print(f"正在保存到: {output_path}")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False)


# ==========================================
# 路径配置
# ==========================================
LDP_FILE = "./ldpose_final/annotations/ldpose_test.json"
NEW_FILE = "./labels_test31.json"
OUT_FILE = "labels_residual_fix/labels_test_fix_residual_kpts.json"

if __name__ == "__main__":
    # 确保输出目录存在
    out_dir = os.path.dirname(OUT_FILE)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)

    if os.path.exists(LDP_FILE) and os.path.exists(NEW_FILE):
        merge_residual_points_by_id(LDP_FILE, NEW_FILE, OUT_FILE)
    else:
        print("错误：找不到输入文件。")