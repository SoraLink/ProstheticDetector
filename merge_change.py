import json
import os
import glob
from pathlib import Path


def merge_with_priority(source_json_path, input_dir, output_file, master_filename="change.json"):
    # =========================================================================
    # 第一步：加载原始 Source JSON (获取 Task ID)
    # =========================================================================
    print(f"📖 读取 Source JSON: {source_json_path}")
    try:
        with open(source_json_path, "r", encoding="utf-8") as f:
            source_data = json.load(f)
    except Exception as e:
        print(f"❌ 无法读取 Source JSON: {e}")
        return

    anns = source_data.get('annotations', [])
    print("⚙️ 重建任务索引 (Sorting)...")
    anns.sort(key=lambda x: (x['image_id'], x['id']), reverse=True)

    key_to_task_id = {}
    for idx, ann in enumerate(anns):
        k = f"{ann['image_id']}_{ann['id']}"
        key_to_task_id[k] = idx + 1

    print(f"✅ 索引建立完成。准备扫描合并...\n")

    # =========================================================================
    # 第二步：准备文件列表 (调整顺序)
    # =========================================================================
    input_path = Path(input_dir)
    all_files = list(input_path.glob("*.json"))

    # 排除输出文件本身
    all_files = [f for f in all_files if f.name != Path(output_file).name]

    if not all_files:
        print("❌ 未找到 JSON 文件。")
        return

    # 【关键修改】将 master_filename (change.json) 移到列表最前面
    master_file = None
    other_files = []

    for f in all_files:
        if f.name == master_filename:
            master_file = f
        else:
            other_files.append(f)

    # 重新组合：主文件排第一，其他文件排后面
    if master_file:
        print(f"⭐ 发现主文件 [{master_filename}]，将优先处理并锁定其数据。")
        sorted_files = [master_file] + other_files
    else:
        print(f"⚠️ 未找到主文件 [{master_filename}]，将按默认顺序处理。")
        sorted_files = other_files

    # =========================================================================
    # 第三步：扫描并合并
    # =========================================================================
    merged_data = {"info": {"last_index": 0}, "changes": {}}
    ownership_map = {}  # { unique_id: filename }

    conflict_count = 0
    ignored_count = 0  # 记录因为主文件存在而被忽略的次数

    print(f"📂 开始处理 {len(sorted_files)} 个文件...\n")

    for f_path in sorted_files:
        current_filename = f_path.name
        is_master = (current_filename == master_filename)

        try:
            with open(f_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            print(f"⚠️ 跳过损坏文件: {current_filename}")
            continue

        changes = data.get("changes", {})
        print(f"📄 正在读取: {current_filename} ({len(changes)} 条记录)")

        for unique_id, new_content in changes.items():

            # --- 冲突检测逻辑 ---
            if unique_id in ownership_map:
                prev_filename = ownership_map[unique_id]
                old_content = merged_data["changes"][unique_id]
                task_idx = key_to_task_id.get(unique_id, "???")
                is_diff = (old_content != new_content)

                # 情况 A: 之前的拥有者是 Master 文件
                # 策略: 坚决不覆盖，直接跳过
                if prev_filename == master_filename:
                    if is_diff:
                        print(f"    🔒 [主文件保护] Task {task_idx} | ID: {unique_id}")
                        print(f"       Ignoring: {current_filename} (试图修改主文件数据)")
                        ignored_count += 1
                    # 如果数据一样，我们也可以直接跳过，无需打印
                    continue

                    # 情况 B: 普通文件冲突 (Previous 不是 Master)
                # 策略: 覆盖 (新文件 覆盖 旧文件)
                conflict_count += 1
                if is_diff:
                    print(f"    ⚠️  [普通冲突] Task {task_idx} | ID: {unique_id}")
                    print(f"       覆盖: {prev_filename} -> 被 {current_filename} 覆盖")

            # --- 写入数据 ---
            # 只有当 ID 不存在，或者 ID 存在但不是被 Master 锁定时，才写入
            merged_data["changes"][unique_id] = new_content
            ownership_map[unique_id] = current_filename

    # =========================================================================
    # 第四步：保存
    # =========================================================================
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 50)
        print(f"✅ 合并完成")
        print(f"💾 输出文件: {output_file}")
        print(f"🔒 主文件保护: 忽略了 {ignored_count} 次外部修改")
        print(f"🔄 普通覆盖:   发生了 {conflict_count} 次普通文件间的覆盖")
        print(f"📊 最终有效记录数: {len(merged_data['changes'])}")
        print("=" * 50)

    except Exception as e:
        print(f"❌ 保存失败: {e}")


# ================= 配置区域 =================
if __name__ == "__main__":
    SOURCE_JSON_PATH = "./labels_residual_fix/labels_test_fix_residual_kpts.json"
    INPUT_DIR = "./test"
    OUTPUT_FILE = "./test/merged_final.json"

    # 指定哪个文件是“老大”，它的数据绝对不会被覆盖
    MASTER_FILE_NAME = "change.json"

    merge_with_priority(SOURCE_JSON_PATH, INPUT_DIR, OUTPUT_FILE, MASTER_FILE_NAME)