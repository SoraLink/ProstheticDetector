import argparse
import csv
import json


def load_annotations(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 既兼容 COCO 格式（data["annotations"]），也兼容“纯列表”格式
    if isinstance(data, dict) and "annotations" in data:
        return data["annotations"], data.get("images", None)
    elif isinstance(data, list):
        return data, None
    else:
        raise ValueError("不认识的 JSON 格式，请检查标注文件。")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--anno_path", type=str)

    args = parser.parse_args()
    annotation_path = args.anno_path
    annotations, image_infos = load_annotations(annotation_path)
    pros_ids = range(30, 54)
    out_csv = "prosthetic_images.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["image_id", "image_name"])
        for image_info in image_infos:
            id = image_info["id"]
            annos_for_id = [a for a in annotations if a.get("image_id") == id]
            category_ids = [a["category_id"] for a in annos_for_id]
            intersection = list(set(category_ids) & set(pros_ids))
            if len(intersection) == 0:
                image_name = image_info["file_name"]
                writer.writerow([id, image_name])
                print(f"{id} {image_name}")
if __name__ == '__main__':
    main()