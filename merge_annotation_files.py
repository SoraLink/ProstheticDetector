import json
import os
import copy


def merge_keep_all_data(base_json_path, new_json_path, output_path):
    # =========================================================================
    # 1. 加载文件
    # =========================================================================
    print(f"📖 读取文件 A (主文件): {base_json_path}")
    with open(base_json_path, "r", encoding="utf-8") as f:
        base_data = json.load(f)

    print(f"📖 读取文件 B (副文件 - 将被追加): {new_json_path}")
    with open(new_json_path, "r", encoding="utf-8") as f:
        new_data = json.load(f)

    # 初始化合并数据，以文件 A 为基础
    merged_data = {
        "info": base_data.get("info", {}),
        "licenses": base_data.get("licenses", []),
        "categories": base_data.get("categories", []),
        "images": base_data.get("images", []),
        "annotations": base_data.get("annotations", [])
    }

    # =========================================================================
    # 2. 准备 ID 和 文件名 索引
    # =========================================================================
    existing_img_ids = [img['id'] for img in merged_data['images']]
    existing_ann_ids = [ann['id'] for ann in merged_data['annotations']]

    # 获取当前最大的 ID，作为基准线
    max_img_id = max(existing_img_ids) if existing_img_ids else 0
    max_ann_id = max(existing_ann_ids) if existing_ann_ids else 0

    print(f"✅ 文件 A 统计: 图片 {len(existing_img_ids)} 张 (Max ID: {max_img_id})")

    # 记录已存在的文件名集合，用于检测重名
    existing_filenames = set(img['file_name'] for img in merged_data['images'])

    # =========================================================================
    # 3. 处理文件 B 的图片 (自动重命名 + ID重映射)
    # =========================================================================
    img_id_map = {}  # 旧 ID -> 新 ID
    rename_log = []  # 记录哪些文件被改名了，方便你改物理文件名

    print("⚙️ 正在处理文件 B 的图片 (如有重名将自动修改)...")

    for img in new_data.get("images", []):
        old_fname = img['file_name']
        old_id = img['id']

        # --- 核心逻辑：文件名冲突检测 ---
        final_fname = old_fname

        # 如果文件名已存在，则循环尝试添加后缀，直到不重复
        if final_fname in existing_filenames:
            name_part, ext_part = os.path.splitext(final_fname)
            counter = 1
            while final_fname in existing_filenames:
                # 生成新名字：比如 001.jpg -> 001_v1.jpg -> 001_v2.jpg
                final_fname = f"{name_part}_v{counter}{ext_part}"
                counter += 1

            # 记录重命名操作
            rename_log.append(f"冲突: {old_fname} -> 改名为: {final_fname}")

        # --- ID 生成 ---
        max_img_id += 1
        new_id = max_img_id

        # 记录 ID 映射
        img_id_map[old_id] = new_id

        # 构造新对象
        new_img_entry = copy.deepcopy(img)
        new_img_entry['id'] = new_id
        new_img_entry['file_name'] = final_fname  # 使用（可能修改过的）新名字

        merged_data['images'].append(new_img_entry)
        existing_filenames.add(final_fname)  # 加入集合，防止后续再冲突

    # =========================================================================
    # 4. 处理文件 B 的标注 (迁移到新 ID)
    # =========================================================================
    print("⚙️ 正在处理文件 B 的标注...")

    for ann in new_data.get("annotations", []):
        old_img_id = ann['image_id']

        if old_img_id not in img_id_map:
            # 理论上不会发生，除非 json 数据本身不完整
            print(f"⚠️ 警告: 标注(id:{ann['id']}) 找不到对应的图片 ID {old_img_id}，已跳过。")
            continue

        # 生成新 Annotation ID
        max_ann_id += 1
        new_ann_id = max_ann_id

        # 构造新标注
        new_ann_entry = copy.deepcopy(ann)
        new_ann_entry['id'] = new_ann_id
        new_ann_entry['image_id'] = img_id_map[old_img_id]  # 链接到新的 Image ID

        merged_data['annotations'].append(new_ann_entry)

    # =========================================================================
    # 5. 保存与报告
    # =========================================================================
    print("-" * 50)
    print(f"🎉 合并完成！所有数据已保留。")
    print(f"🖼️  图片总数: {len(merged_data['images'])} (来自B的文件: {len(new_data.get('images', []))})")
    print(f"📝 标注总数: {len(merged_data['annotations'])} (来自B的标注: {len(new_data.get('annotations', []))})")

    if rename_log:
        print(f"\n⚠️  注意：有 {len(rename_log)} 个文件因重名在 JSON 中被重命名了！")
        print("   (你可能需要去修改硬盘上对应的真实文件名，以匹配这些更改)")
        print("   前5个示例:")
        for log in rename_log[:5]:
            print(f"   - {log}")
    else:
        print("\n✨ 完美：没有文件名冲突，无需重命名。")

    print("-" * 50)

    print(f"💾 正在保存到: {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, ensure_ascii=False)


if __name__ == "__main__":
    # 1. 之前生成的那个比较完美的文件
    FILE_A = "./test/test_annotation.json"

    # 2. 另外重新爬下来的新数据生成的 COCO 文件
    FILE_B = "./test_2nd/test_final.json"

    # 3. 最终的大一统文件
    OUTPUT_FILE = "./test/FULL_DATASET_ALL_IN.json"

    if os.path.exists(FILE_A) and os.path.exists(FILE_B):
        merge_keep_all_data(FILE_A, FILE_B, OUTPUT_FILE)
    else:
        print("❌ 错误：找不到输入文件，请检查路径。")