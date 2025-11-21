import json
import os
import csv
from collections import defaultdict
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 800

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


def load_existing_label_infos(label_path: Path):
    _, image_info_list = load_annotations(label_path)
    return image_info_list

def load_LD_labels(label_path: Path):
    annotations, image_info_list = load_annotations(label_path)
    return annotations, image_info_list

def list_images(image_dir: Path):
    """递归列出目录下所有图片"""
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
    return sorted([p for p in image_dir.rglob("*") if p.suffix.lower() in exts])


class ProsthesisLabelerApp:
    """
    三分类标注：
    2 = 带假肢，连接点可见
    1 = 带假肢，衣物遮挡
    0 = 无假肢
    """
    def __init__(self, master):
        self.selected_keypoint_id = None
        self.current_label = None
        self.master = master
        self.master.title("LD-Prosthesis Labeler (3-Class with Resume)")
        self.master.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        # ------------------ 用户选择 ------------------
        self.LD_label_file = self.ask_LD_label_directory()
        if not self.LD_label_file:
            self.master.destroy()
            return

        self.label_file = self.ask_label_file()
        if not self.label_file:
            self.master.destroy()
            return

        self.image_dir = self.ask_image_directory()
        if not self.image_dir:
            self.master.destroy()
            return

        # 加载已经标注的标签
        if self.label_file.exists():
            self.labels = load_existing_label_infos(self.label_file)
            self.labels = { label['id']: label for label in self.labels }
        else:
            self.labels = {}
        # 加载LDpose的标签
        self.LD_annotations, self.LD_image_infos = load_LD_labels(self.LD_label_file)
        self.LD_labels = {}
        for LD_image_info in self.LD_image_infos:
            LD_id = LD_image_info['id']
            annotations = [annotation for annotation in self.LD_annotations if annotation.get("image_id") == LD_id]
            if len(annotations) == 0:
                continue
            self.LD_labels[LD_id] = [LD_image_info, annotations]

        # 统计数量（自动恢复）
        self.count_pro = sum(1 for info in self.labels.values() if info.get('has_pro') is True)
        self.count_no_pro = len(self.labels) - self.count_pro

        # 找到第一张未标注的位置
        self.todo_ids = self.get_todo_ids()

        # ------------------ UI ------------------
        self.image_label = tk.Label(self.master)
        self.image_label.pack(expand=True)

        # 当前文件信息
        self.info_var = tk.StringVar()
        tk.Label(self.master, textvariable=self.info_var).pack(pady=5)

        # 计数信息
        self.counter_var = tk.StringVar()
        self.update_counter_text()
        tk.Label(self.master, textvariable=self.counter_var, font=("Arial", 12)).pack()

        self.keypoints = {
            1: 'Above right elbow residual limb end',
            2: 'Below right elbow residual limb end',
            3: 'Above left elbow residual limb end',
            4: 'Below left elbow residual limb end',
            5: 'Above right knee residual limb end',
            6: 'Below right knee residual limb end',
            7: 'Above left knee residual limb end',
            8: 'Below left knee residual limb end',
            9: 'Left prosthetic elbow',
            10: 'Right prosthetic elbow',
            11: 'Left prosthetic knee',
            12: 'Right prosthetic knee',
            13: 'Left prosthetic wrist',
            14: 'Right prosthetic wrist',
            15: 'Left prosthetic ankle',
            16: 'Right prosthetic ankle',
        }

        self.reset()

        # 点击坐标
        self.image_label.bind("<Button-1>", self.on_image_click)

        # 按钮区域
        btn_frame = tk.Frame(self.master)
        btn_frame.pack(pady=10)
        for i in range(0, 4):
            for j in range(0, 4):
                keypoint_id = i * 4 + j + 1
                tk.Button(
                    btn_frame,
                    text=self.keypoints[keypoint_id],
                    width=18,
                    command=lambda k=keypoint_id: self.set_target_keypoint(k)
                ).grid(row=i, column=j, padx=5)

        for i in range(1, 4):
            tk.Button(
                btn_frame,
                text=f"Vis {i}",
                width=18,
                command=lambda v=i: self.set_vis(v)
            ).grid(row=5, column=i, padx=5)

        tk.Button(
            btn_frame,
            text="Clear selected keypoint",
            width=18,
            command=self.clear_selected_keypoint
        ).grid(row=6, column=0, padx=5)

        tk.Button(
            btn_frame,
            text="Next",
            width=18,
            command=lambda: self.next_image()
        ).grid(row=6, column=1, padx=5)


        # 打开 label 文件（追加）
        if not self.label_file.exists():
            with open(self.label_file, "w", encoding="utf-8") as f:
                data = {
                    "images": [],
                    "annotations": []
                }
                json.dump(data, f, ensure_ascii=False, indent=4)

        self.show_image()

    def clear_selected_keypoint(self):
        if self.selected_keypoint_id in self.current_label:
            self.current_label[self.selected_keypoint_id] = [-1, -1, -1]

    def ask_image_directory(self):
        dirname = filedialog.askdirectory(title="请选择图片目录")
        return Path(dirname) if dirname else None

    def reset(self):
        self.selected_keypoint_id = -1
        self.current_label = defaultdict(lambda: [-1, -1, -1])

    def set_vis(self, vis):
        self.current_label[self.selected_keypoint_id][2] = vis

    # ==========================================
    # 选择文件夹 / 文件
    # ==========================================
    def ask_LD_label_directory(self):
        dirname = filedialog.askopenfilename(
            title="请选择LDPose的annotation的位置",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json")]
        )
        return Path(dirname) if dirname else None

    def ask_label_file(self):
        filename = filedialog.asksaveasfilename(
            title="请选择 labels.json 保存位置",
            initialfile="labels.json",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json")]
        )
        return Path(filename) if filename else None


    def get_todo_ids(self):
        todo_ids = set(self.LD_labels.keys())
        for label_id in self.labels.keys():
            todo_ids.discard(label_id)
        return sorted(list(todo_ids))

    # ==========================================
    # UI 更新
    # ==========================================
    def update_counter_text(self):
        total = len(self.labels)
        self.counter_var.set(
            f"已标注：{total}  |  有假肢：{self.count_pro}   |   无假肢：{self.count_no_pro}"
        )

    def next_image(self):
        self.save_result()
        if self.todo_ids:
            self.todo_ids.pop(0)
        self.reset()
        self.show_image()

    def save_result(self):
        if not self.todo_ids:
            return

        current_id = self.todo_ids[0]

        # 只要有任意 keypoint != [-1, -1, -1] 就认为有假肢
        has_pro = any(v != [-1, -1, -1] for v in self.current_label.values())

        with open(self.label_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        images = data.get("images", [])
        annotations = data.get("annotations", [])
        existing_ids = {img["id"] for img in images}

        if current_id not in existing_ids:
            img_info, anns = self.LD_labels[current_id]  # 👈 不动你的 annotations
            out_img_info = img_info.copy()  # 复制一份 image_info
            out_img_info["has_pro"] = has_pro  # 只在输出里加字段
            images.append(out_img_info)

            out_anns = anns.copy()

            #### TODO 完成kepoint存储逻辑。
            out_anns["new_keypoints"] = self.current_label.values()

            self.labels[current_id] = out_img_info

        data["images"] = images

        with open(self.label_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        if has_pro:
            self.count_pro += 1
        else:
            self.count_no_pro += 1
        self.update_counter_text()



    def show_image(self):
        if len(self.todo_ids) == 0:
            messagebox.showinfo("完成", "所有图片已标注完毕！")
            self.stop_labeling()
            return

        current_id = self.todo_ids[0]

        img_file_name = self.LD_labels[current_id][0]['file_name']
        img_path = self.image_dir / img_file_name
        rel_path = img_path.relative_to(self.image_dir).as_posix()

        self.info_var.set(f"{len(self.labels)}/{len(self.LD_labels)} : {rel_path}")

        img = Image.open(img_path).convert("RGB")
        self.tk_img = ImageTk.PhotoImage(img)
        self.image_label.config(image=self.tk_img)

    def set_target_keypoint(self, keypoint_id):
        self.selected_keypoint_id = keypoint_id

    # ==========================================
    # 结束标注
    # ==========================================
    def stop_labeling(self):
        messagebox.showinfo("退出", "标注结束，数据已保存。")
        self.master.destroy()

    def on_image_click(self, event):
        if self.selected_keypoint_id is None or self.selected_keypoint_id < 0:
            messagebox.showwarning("提示", "请先选择一个关键点按钮，再在图片上点击。")
            return

        x, y = event.x, event.y
        print("clicked:", x, y)
        self.current_label[self.selected_keypoint_id][0] = x
        self.current_label[self.selected_keypoint_id][1] = y


def main():
    root = tk.Tk()
    app = ProsthesisLabelerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
