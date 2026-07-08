import json
import os
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
import matplotlib.patches as mpatches


# ==========================================
# 1. 核心解析逻辑：严格保留 4 类残肢点统计与控制台打印，增加图片文件夹过滤
# ==========================================
def analyze_dataset_stats(file_list, image_dir=None, label="Dataset"):
    kp_stats = defaultdict(lambda: {"bio": 0, "pros": 0, "abs": 0})
    res_stats = {"arm_above": 0, "arm_below": 0, "leg_above": 0, "leg_below": 0}

    found_data = False
    limb_mapping = {
        'Elbow': [7, 8], 'Wrist': [9, 10], 'Fingertip': [17, 18],
        'Knee': [13, 14], 'Ankle': [15, 16], 'Heel': [19, 20], 'Toe': [21, 22]
    }

    # --- 新增：获取文件夹内真实存在的图片名称集合 ---
    valid_images = set()
    if image_dir:
        if os.path.exists(image_dir):
            valid_images = set(os.listdir(image_dir))
            print(f"📁 [{label}] 图片过滤已开启，共加载 {len(valid_images)} 张有效图片名称自: {image_dir}")
        else:
            print(f"❌ [{label}] 找不到图片文件夹: {image_dir}，将跳过过滤或报错。")

    for json_path in file_list:
        if not os.path.exists(json_path):
            print(f"❌ [{label}] 找不到文件: {json_path}")
            continue

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # --- 新增：建立 image_id -> file_name 的映射字典 ---
        images_info = data.get('images', [])
        # 使用 os.path.basename 防止 json 里的 file_name 带有路径前缀
        img_id_to_name = {img.get('id'): os.path.basename(img.get('file_name', '')) for img in images_info}

        annotations = data.get('annotations', [])
        for ann in annotations:
            # --- 新增：核心过滤逻辑 ---
            if image_dir:
                img_id = ann.get('image_id')
                img_name = img_id_to_name.get(img_id)
                # 如果图片名在 json 里找不到，或者不在实际的文件夹集合中，直接跳过
                if not img_name or img_name not in valid_images:
                    continue

            kps = ann.get('keypoints', [])
            types = ann.get('keypoint_types', [])
            if not kps or not types or len(types) != 31: continue

            found_data = True
            for i in range(31):
                v = kps[i * 3 + 2] if (i * 3 + 2) < len(kps) else 0
                if v > 0:
                    k_type = types[i]
                    if i <= 22:
                        if k_type == 0:
                            kp_stats[i]['bio'] += 1
                        elif k_type == 1:
                            kp_stats[i]['pros'] += 1
                        elif k_type == 2:
                            kp_stats[i]['abs'] += 1
                    elif 23 <= i <= 30:
                        if k_type == 0:
                            if i in [23, 24]:
                                res_stats["arm_above"] += 1
                            elif i in [25, 26]:
                                res_stats["arm_below"] += 1
                            elif i in [27, 28]:
                                res_stats["leg_above"] += 1
                            elif i in [29, 30]:
                                res_stats["leg_below"] += 1

    print(f"\n📊 [{label}] 详细统计结果:")
    if not found_data: print("   ！！！错误：未发现有效标注数据！！！")

    aggregated = {}
    for name, indices in limb_mapping.items():
        bio = sum(kp_stats[idx]['bio'] for idx in indices)
        pros = sum(kp_stats[idx]['pros'] for idx in indices)
        abs_val = sum(kp_stats[idx]['abs'] for idx in indices)
        total = bio + pros + abs_val
        print(f"   {name:<10}: Bio={bio}, Pros={pros}, Abs={abs_val} (Total={total})")
        aggregated[name] = {
            'pros_pct': (pros / total * 100) if total > 0 else 0,
            'bio_pct': (bio / total * 100) if total > 0 else 0,
            'abs_pct': (abs_val / total * 100) if total > 0 else 0
        }
    print(f"   Residuals : Arm Above={res_stats['arm_above']}, Arm Below={res_stats['arm_below']}, "
          f"Leg Above={res_stats['leg_above']}, Leg Below={res_stats['leg_below']}\n")
    return aggregated, res_stats


# ==========================================
# 2. 绘图逻辑：保持不变
# ==========================================
def draw_and_save_separately(ld_agg, ld_res, pr_agg, pr_res):
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "Liberation Sans"],
        "font.size": 10, "pdf.fonttype": 42
    })

    C_LD, C_PR = '#5B84B1', '#FC766A'
    C_BIO, C_PROS, C_ABS = '#55A868', '#EDC948', '#BAB0AC'
    cats = ['Elbow', 'Wrist', 'Fingertip', 'Knee', 'Ankle', 'Heel', 'Toe']

    # --- (A) 环形对比图 ---
    fig_a, ax1 = plt.subplots(figsize=(8, 8), subplot_kw={'projection': 'polar'})
    ld_p = [ld_agg[c]['pros_pct'] for c in cats]
    pr_p = [pr_agg[c]['pros_pct'] for c in cats]

    N = len(cats)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False)
    bar_width = (2 * np.pi) / N * 0.40
    inner_r = 25
    ax1.set_ylim(0, inner_r + 35)

    ax1.set_axisbelow(True)
    theta_fill = np.linspace(0, 2 * np.pi, 100)
    ax1.fill_between(theta_fill, 0, inner_r, color='white', zorder=2)
    ax1.grid(True, axis='x', color='#D0D0D0', linestyle='--', alpha=0.5, zorder=1)
    ax1.set_rgrids([inner_r + 10, inner_r + 20, inner_r + 30], labels=[])
    ax1.grid(True, axis='y', color='#D0D0D0', linestyle='--', alpha=0.5, zorder=1)

    ax1.bar(angles - bar_width / 2, ld_p, width=bar_width, bottom=inner_r, color=C_LD,
            edgecolor='none', linewidth=0, label='LDPose', alpha=0.9, zorder=3)
    ax1.bar(angles + bar_width / 2, pr_p, width=bar_width, bottom=inner_r, color=C_PR,
            edgecolor='none', linewidth=0, label='ProPose (Ours)', zorder=3)

    def add_labels(data, offset_angle):
        for angle, val in zip(angles, data):
            if val < 0.1: continue
            bar_angle_rad = angle + offset_angle
            visual_deg = 90 - np.rad2deg(bar_angle_rad)
            visual_deg = visual_deg % 360

            if 90 < visual_deg <= 270:
                text_rotation = visual_deg + 180
                ha = 'right'
            else:
                text_rotation = visual_deg
                ha = 'left'

            r_pos = inner_r + val + 1.0
            ax1.text(bar_angle_rad, r_pos, f'{val:.1f}%',
                     va='center', ha=ha, rotation=text_rotation,
                     rotation_mode='anchor', fontsize=9, fontweight='bold', color='#111111', zorder=4)

    add_labels(ld_p, -bar_width / 2)
    add_labels(pr_p, bar_width / 2)

    ax1.set_theta_zero_location("N")
    ax1.set_theta_direction(-1)
    ax1.set_xticks(angles)
    ax1.tick_params(pad=45)
    ax1.set_xticklabels(cats, fontweight='bold', fontsize=12, zorder=4)
    ax1.set_yticklabels([])

    ax1.spines['polar'].set_visible(True)
    ax1.spines['polar'].set_edgecolor('black')
    ax1.spines['polar'].set_linewidth(1.5)
    ax1.spines['polar'].set_zorder(5)

    legend_patches = [
        mpatches.Patch(facecolor=C_LD, edgecolor='none', label='LDPose'),
        mpatches.Patch(facecolor=C_PR, edgecolor='none', label='ProPose (Ours)')
    ]
    ax1.legend(handles=legend_patches, loc='center', title=r'$\mathbf{Datasets}$',
               title_fontsize=12, fontsize=10, frameon=False).set_zorder(6)

    plt.savefig('fig_a_circular_final.pdf', bbox_inches='tight', dpi=300)

    # --- (B) 残肢对比图 ---
    fig_b, ax2 = plt.subplots(figsize=(7, 5))
    res_labels = ['Arm Above', 'Arm Below', 'Leg Above', 'Leg Below']
    x = np.arange(4)
    bw = 0.35
    ld_v = [ld_res['arm_above'], ld_res['arm_below'], ld_res['leg_above'], ld_res['leg_below']]
    pr_v = [pr_res['arm_above'], pr_res['arm_below'], pr_res['leg_above'], pr_res['leg_below']]

    ax2.bar(x - bw / 2, ld_v, width=bw, label='LDPose', color=C_LD, edgecolor='none', linewidth=0, alpha=0.9)
    ax2.bar(x + bw / 2, pr_v, width=bw, label='ProPose (Ours)', color=C_PR, edgecolor='none', linewidth=0)

    ax2.set_xticks(x)
    ax2.set_xticklabels(res_labels, rotation=15, ha='right')
    ax2.set_ylabel('Instance Count', fontweight='bold')

    handles_b, labels_b = ax2.get_legend_handles_labels()
    ax2.legend(handles_b, labels_b, frameon=False)

    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.yaxis.grid(True, linestyle='--', alpha=0.5)
    plt.savefig('fig_b_residual_final.pdf', bbox_inches='tight')

    # --- (C) 类型占比图 ---
    fig_c, ax3 = plt.subplots(figsize=(7, 5))
    b_v = np.array([pr_agg[c]['bio_pct'] for c in cats])
    p_v = np.array([pr_agg[c]['pros_pct'] for c in cats])
    a_v = np.array([pr_agg[c]['abs_pct'] for c in cats])

    ax3.bar(cats, b_v, label='Biological', color=C_BIO, width=0.6, edgecolor='none', linewidth=0)
    ax3.bar(cats, p_v, bottom=b_v, label='Prosthetic', color=C_PROS, width=0.6, edgecolor='none', linewidth=0)
    ax3.bar(cats, a_v, bottom=b_v + p_v, label='Absent', color=C_ABS, width=0.6, edgecolor='none', linewidth=0)

    ax3.set_ylim(0, 100)
    ax3.set_ylabel('Percentage (%)', fontweight='bold')
    plt.xticks(rotation=45, ha='right')

    handles_c, labels_c = ax3.get_legend_handles_labels()
    ax3.legend(handles_c, labels_c, loc='lower center', bbox_to_anchor=(0.5, 1.02), ncol=3, frameon=False)

    ax3.spines['top'].set_visible(False)
    ax3.spines['right'].set_visible(False)
    plt.savefig('fig_c_type_final.pdf', bbox_inches='tight')

    print("✅ 执行完毕：图表生成成功。")


# ==========================================
# 3. 运行环境配置
# ==========================================
if __name__ == "__main__":
    LDP_FILES = [
        "./ldpose_annotation/train_final.json",
        "./ldpose_annotation/test_final.json"
    ]
    PRP_FILES = [
        "./propose_annotation/train_final.json",
        "./propose_annotation/test_final.json"
    ]

    # ！！！请在这里修改你的图片文件夹路径！！！
    # 如果传 None，就会退回到以前的逻辑（全部统计）
    LDP_IMAGE_DIR = "/DATA/dataset_raw"  # 替换为你实际的 LDPose 图片文件夹路径
    PRP_IMAGE_DIR = "/DATA/dataset_raw"  # 替换为你实际的 ProPose 图片文件夹路径

    print("--- 正在处理 LDPose 数据 ---")
    ld_agg, ld_res = analyze_dataset_stats(LDP_FILES, image_dir=LDP_IMAGE_DIR, label="LDPose")

    print("--- 正在处理 ProPose 数据 ---")
    pr_agg, pr_res = analyze_dataset_stats(PRP_FILES, image_dir=PRP_IMAGE_DIR, label="ProPose")

    if ld_agg or pr_agg:
        draw_and_save_separately(ld_agg, ld_res, pr_agg, pr_res)
    else:
        print("❌ 数据为空，请检查 JSON 路径。")