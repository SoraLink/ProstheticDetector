import json
import os

# ================= 配置区域 =================
# 在这里修改你的 JSON 文件路径
JSON_PATH = "./train_2nd/train_2nd_final.json"


# ===========================================

def count_prosthesis_people(json_file):
    if not os.path.exists(json_file):
        print(f"错误: 找不到文件 {json_file}")
        return

    print(f"正在加载文件: {json_file} ...")
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    annotations = data.get('annotations', [])
    total_anns = len(annotations)

    prosthesis_count = 0
    prosthesis_ids = []

    print(f"开始扫描 {total_anns} 个标注对象...")

    for ann in annotations:
        # 获取 keypoint_types 列表，如果没有则默认为空
        kpt_types = ann.get('keypoint_types', [])

        # 核心逻辑：只要类型列表中包含 1 (Prosthesis)，就算作假肢人物
        if 1 in kpt_types:
            prosthesis_count += 1
            prosthesis_ids.append(ann['id'])

    # ================= 输出结果 =================
    print("-" * 30)
    print(f"统计完成！")
    print(f"总标注数量 (Annotations): {total_anns}")
    print(f"含假肢人物数量 (Prosthesis): {prosthesis_count}")

    if total_anns > 0:
        ratio = (prosthesis_count / total_anns) * 100
        print(f"占比: {ratio:.2f}%")
    print("-" * 30)

    # 如果你想看具体是哪些 ID 有假肢，可以取消下面这行的注释
    # print(f"包含假肢的 Annotation IDs: {prosthesis_ids}")


if __name__ == "__main__":
    count_prosthesis_people(JSON_PATH)