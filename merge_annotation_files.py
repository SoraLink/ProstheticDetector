import json
import os


def merge_and_reassign_ids(base_json_path, new_json_path, output_path):
    print(f"📖 读取文件 A (主文件): {base_json_path}")
    with open(base_json_path, "r", encoding="utf-8") as f:
        base_data = json.load(f)

    print(f"📖 读取文件 B (追加文件): {new_json_path}")
    with open(new_json_path, "r", encoding="utf-8") as f:
        new_data = json.load(f)

    # 1. 初始化合并数据
    merged_data = {
        "info": base_data.get("info", {}),
        "licenses": base_data.get("licenses", []),
        "categories": base_data.get("categories", []),
        "images": list(base_data.get("images", [])),
        "annotations": list(base_data.get("annotations", []))
    }

    # 2. 获取 A 的最大 ID 作为起始点
    # 如果 A 为空，则从 0 开始
    max_img_id = max([img['id'] for img in merged_data['images']], default=0)
    max_ann_id = max([ann['id'] for ann in merged_data['annotations']], default=0)

    existing_filenames = set(img['file_name'] for img in merged_data['images'])

    # 映射表：记录 FILE B 的旧 image_id 到新 image_id 的对应关系
    img_id_map = {}

    # =========================================================================
    # 3. 处理文件 B 的图片
    # =========================================================================
    print("⚙️ 正在重新分配图片 ID 并去重...")
    for img in new_data.get("images", []):
        old_id = img['id']

        # 去重：如果文件名在 A 中已存在，跳过，并记录映射为 A 中已有的 ID
        if img['file_name'] in existing_filenames:
            # 找到 A 中同名图片的 ID，以便标注重定向
            matching_img = next(i for i in merged_data['images'] if i['file_name'] == img['file_name'])
            img_id_map[old_id] = matching_img['id']
            continue

        # 新图片：分配新 ID
        max_img_id += 1
        new_id = max_img_id
        img_id_map[old_id] = new_id

        # 拷贝图片对象并更新 ID
        new_img_obj = img.copy()
        new_img_obj['id'] = new_id
        merged_data['images'].append(new_img_obj)
        existing_filenames.add(img['file_name'])

    # =========================================================================
    # 4. 处理文件 B 的标注
    # =========================================================================
    print("⚙️ 正在重新分配标注 ID...")
    skipped_ann_count = 0

    for ann in new_data.get("annotations", []):
        old_img_id = ann['image_id']

        # 如果标注对应的图片在 A 和 B 中都被去重掉了，或者不存在
        if old_img_id not in img_id_map:
            skipped_ann_count += 1
            continue

        # 分配新标注 ID
        max_ann_id += 1

        new_ann_obj = ann.copy()
        new_ann_obj['id'] = max_ann_id  # 绝对唯一的标注 ID
        new_ann_obj['image_id'] = img_id_map[old_img_id]  # 指向正确的新图片 ID

        merged_data['annotations'].append(new_ann_obj)

    # =========================================================================
    # 5. 保存与报告
    # =========================================================================
    print("-" * 50)
    print(f"✅ 合并完成！FILE B 的数据已自动追加至 FILE A 之后。")
    print(f"📊 统计报告:")
    print(f"   - 最终总图片数: {len(merged_data['images'])}")
    print(f"   - 最终总标注数: {len(merged_data['annotations'])}")
    print(f"   - 忽略重复标注: {skipped_ann_count} (由于图片缺失)")
    print("-" * 50)

    print(f"💾 正在保存到: {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, ensure_ascii=False)


if __name__ == "__main__":
    FILE_B = "E:/DATA/pros_final/train_2nd/train_2nd_final.json"
    FILE_A = "E:/DATA/pros_final/train/train_final.json"
    OUTPUT_FILE = "E:/DATA/pros_final/train_final/train_final.json"

    if os.path.exists(FILE_A) and os.path.exists(FILE_B):
        merge_and_reassign_ids(FILE_A, FILE_B, OUTPUT_FILE)
    else:
        print("❌ 错误：路径不存在")