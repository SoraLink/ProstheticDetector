import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np


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


def find_image_file(images_dir: Path, image_info_list, target_image_id: int):
    """
    尝试根据 COCO 的 images 字段查出 filename 并在目录下找到图片。
    如果没有 images 列表，就简单在目录里猜：image_id.* (jpg/png/jpeg)
    """
    if image_info_list is not None:
        for img in image_info_list:
            if img.get("id") == target_image_id:
                filename = img.get("file_name")
                if filename is None:
                    break
                img_path = images_dir / filename
                if img_path.exists():
                    return img_path

    # fallback：如果没有 images 信息，就尝试 image_id.xxx
    for ext in [".jpg", ".jpeg", ".png", ".bmp"]:
        candidate = images_dir / f"{target_image_id}{ext}"
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"找不到 image_id={target_image_id} 对应的图片文件，"
        f"请检查 images 目录或在 JSON 里是否有 images->file_name 信息。"
    )


def visualize(ax, image_path: Path, annos_for_image):
    img = plt.imread(str(image_path))

    ax.clear()
    ax.imshow(img)
    ax.set_axis_off()

    for anno in annos_for_image:
        segs = anno.get("segmentation", [])
        # segmentation 可能是 [[x1,y1,...]] 这种
        for seg in segs:
            if len(seg) < 6:
                # 少于 3 个点就跳过
                continue
            # seg: [x1,y1,x2,y2,...] -> Nx2
            coords = np.array(seg, dtype=float).reshape(-1, 2)
            poly = Polygon(
                coords,
                closed=True,
                fill=False,
                linewidth=2,
            )
            ax.add_patch(poly)

            # 可选：在多边形中心写一个 category_id 或 track_id
            cx = coords[:, 0].mean()
            cy = coords[:, 1].mean()
            text = f"id={anno.get('id')}"
            if "category_id" in anno:
                text += f", c={anno['category_id']}"
            ax.text(cx, cy, text, fontsize=8, color="yellow")

    ax.figure.canvas.draw_idle()



def get_ids(image_info_list):
    image_ids = sorted(set(i["id"] for i in image_info_list))
    return image_ids


def on_click(total_images, images_dir, annotations, image_ids, image_info_list, ax):
    def on_click_listener(event):
        global idx
        if event.button == 1:
            idx = (idx + 1) % total_images
        elif event.button == 3:
            idx = (idx - 1) % total_images
        image_id = image_ids[idx]
        image_path = find_image_file(images_dir, image_info_list, image_id)
        annos_for_image = [a for a in annotations if a.get("image_id") == image_id]
        visualize(ax, image_path, annos_for_image)

    return on_click_listener


def main():
    if len(sys.argv) != 3:
        print("用法:")
        print("  python visualize_seg.py annotations.json /path/to/images IMAGE_ID")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    images_dir = Path(sys.argv[2])

    annotations, image_info_list = load_annotations(json_path)
    image_ids = get_ids(image_info_list)
    global idx
    idx = 1

    fig, ax = plt.subplots(figsize=(10, 8))

    curr_image_id = image_ids[idx]
    image_path = find_image_file(images_dir, image_info_list, curr_image_id)
    annos_for_image = [a for a in annotations if a.get("image_id") == curr_image_id]
    visualize(ax, image_path, annos_for_image)

    fig.canvas.mpl_connect(
        'button_press_event',
        on_click(len(image_ids), images_dir, annotations, image_ids, image_info_list, ax)
    )

    plt.show()


if __name__ == "__main__":
    main()
