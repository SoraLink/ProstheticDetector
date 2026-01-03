import json
import os


def check_keypoints_bounds(json_path):
    print(f"\n{'=' * 20} 正在扫描: {os.path.basename(json_path)} {'=' * 20}")

    if not os.path.exists(json_path):
        print(f"❌ 文件不存在: {json_path}")
        return

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ JSON 读取失败: {e}")
        return

    # 1. 建立图片尺寸索引 (ID -> [w, h])
    # 因为 annotation 里只有 image_id，没有宽高，必须先查 images 列表
    img_dims = {}
    for img in data.get('images', []):
        img_dims[img['id']] = (img.get('width', 0), img.get('height', 0))

    print(f"ℹ️  已加载 {len(img_dims)} 张图片信息的尺寸。")

    # 统计数据
    total_anns = len(data.get('annotations', []))
    total_kps = 0
    out_of_bound_count = 0
    affected_anns = set()

    print(f"ℹ️  开始检查 {total_anns} 条标注...\n")

    # 2. 遍历标注
    for ann in data.get('annotations', []):
        img_id = ann['image_id']
        ann_id = ann['id']

        if img_id not in img_dims:
            continue

        img_w, img_h = img_dims[img_id]
        keypoints = ann.get('keypoints', [])

        # 3. 遍历关键点 (x, y, v)
        for i in range(0, len(keypoints), 3):
            # 防止列表越界
            if i + 2 >= len(keypoints): break

            x = keypoints[i]
            y = keypoints[i + 1]
            v = keypoints[i + 2]

            # 只检查可见点 (v > 0)
            # 如果 v=0，通常 x,y 也是 0，但不管它
            if v > 0:
                total_kps += 1
                is_out = False
                reason = []

                # === 核心检查逻辑 ===
                # 检查是否小于 0
                if x < 0:
                    reason.append(f"x={x:.2f} < 0")
                    is_out = True
                if y < 0:
                    reason.append(f"y={y:.2f} < 0")
                    is_out = True

                # 检查是否超出宽高
                if x > img_w:
                    reason.append(f"x={x:.2f} > w({img_w})")
                    is_out = True
                if y > img_h:
                    reason.append(f"y={y:.2f} > h({img_h})")
                    is_out = True

                if is_out:
                    out_of_bound_count += 1
                    affected_anns.add(ann_id)
                    # 打印详细报错
                    # index i//3 是第几个关键点
                    print(
                        f"⚠️ [越界] ImgID: {img_id:<6} | AnnID: {ann_id:<6} | KP_Idx: {i // 3:<2} | {', '.join(reason)}")

    # 4. 总结报告
    print("-" * 50)
    print(f"扫描完成。")
    print(f"📉 总关键点数: {total_kps}")
    if out_of_bound_count > 0:
        print(f"❌ 发现越界关键点: {out_of_bound_count} 个")
        print(f"❌ 涉及标注条目数: {len(affected_anns)} 条")
        print("\n💡 结论: 这些越界点如果位于图片右侧 (x > w)，")
        print("   就会导致旧版逻辑算出 new_width = img_w - x = 负数。")
    else:
        print(f"✅ 完美: 所有可见关键点都在图片范围内 (0 ~ w, 0 ~ h)。")


if __name__ == "__main__":
    # 填入你的文件路径，建议检查这一轮生成的 final 文件
    files = [
        "ldpose_test.json",
        "labels_test_final.json",
        "ldpose_train.json",
        "labels_train_final.json",
        "ldpose_val.json",
        "labels_val_final.json",
    ]

    for f in files:
        check_keypoints_bounds(f)