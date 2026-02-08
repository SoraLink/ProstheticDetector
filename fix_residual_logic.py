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
    "L-Elbow-Res-Above": "left_elbow",
    "R-Elbow-Res-Above": "right_elbow",
    "L-Elbow-Res-Below": "left_wrist",
    "R-Elbow-Res-Below": "right_wrist",
    "L-Knee-Res-Above": "left_knee",
    "R-Knee-Res-Above": "right_knee",
    "L-Knee-Res-Below": "left_ankle",
    "R-Knee-Res-Below": "right_ankle"
}


def fix_residual_strict(json_path, output_path):
    print(f"📖 读取文件: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    kp_map = {name: i for i, name in enumerate(KEYPOINT_NAMES)}

    stats = {
        "total_checked": 0,
        "fixed_type_error": 0,  # 以前 Type 就错了 (最严重的)
        "fixed_vis_error": 0,  # Type 对了，但 Vis 没设为 2
        "fixed_coord_error": 0,  # Type/Vis 对了，但坐标没归零 (强迫症修正)
        "perfect": 0  # 本来就是完美的
    }

    print(f"⚙️ 正在执行严格清洗 (目标: Type=2, Vis=2, Pos=0,0)...")

    for ann in data.get("annotations", []):
        kps = ann.get("keypoints", [])
        types = ann.get("keypoint_types", [])

        if not kps or not types: continue
        is_modified = False
        stats["total_checked"] += 1

        for res_name, check_name in LOGIC_MAP.items():
            res_idx = kp_map[res_name]
            check_idx = kp_map[check_name]

            # 正常点信息
            check_v = kps[check_idx * 3 + 2]
            check_type = types[check_idx]

            # 残肢点当前信息
            res_type = types[res_idx]
            res_x = kps[res_idx * 3]
            res_y = kps[res_idx * 3 + 1]
            res_v = kps[res_idx * 3 + 2]

            # === 触发条件：正常点存在 (Type=0 且 v>0) ===
            if check_type == 0 and check_v > 0:

                # 检查当前残肢点是否"完美"
                is_perfect = (res_type == 2 and res_v == 2 and res_x == 0 and res_y == 0)

                if not is_perfect:
                    # 统计错误类型 (为了让你知道发生了什么)
                    if res_type != 2:
                        stats["fixed_type_error"] += 1
                    elif res_v != 2:
                        stats["fixed_vis_error"] += 1
                    else:
                        stats["fixed_coord_error"] += 1

                    # === 强制修正 (无论之前是哪里不对，统统覆盖) ===
                    types[res_idx] = 2  # Type -> 2
                    kps[res_idx * 3] = 0  # X -> 0
                    kps[res_idx * 3 + 1] = 0  # Y -> 0
                    kps[res_idx * 3 + 2] = 2  # Vis -> 2

                    is_modified = True
                else:
                    stats["perfect"] += 1

        if is_modified:
            ann["keypoints"] = kps
            ann["keypoint_types"] = types

    print("-" * 50)
    print("📊 严格修复报告")
    print(f"   总扫描: {stats['total_checked']}")
    print("-" * 20)
    print(f"🔧 修复 Type 错误 (原 Type!=2): {stats['fixed_type_error']}")
    print(f"👁️ 修复 Vis 错误  (原 Vis!=2) : {stats['fixed_vis_error']}  <-- 重点关注这个")
    print(f"📍 修复 坐标 错误 (原 x,y!=0) : {stats['fixed_coord_error']}")
    print("-" * 20)
    print(f"✅ 完美通过 (无需修改): {stats['perfect']}")
    print("-" * 50)

    print(f"💾 保存到: {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


if __name__ == "__main__":
    INPUT_FILE = "./test/test_fix_logic.json"
    OUTPUT_FILE = "./test/FULL_DATASET_STRICT_FIXED.json"

    if os.path.exists(INPUT_FILE):
        fix_residual_strict(INPUT_FILE, OUTPUT_FILE)
    else:
        print("❌ 找不到输入文件")