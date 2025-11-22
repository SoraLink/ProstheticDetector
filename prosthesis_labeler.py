import json
import os
import csv
from collections import defaultdict
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk, ImageDraw  # 引入 ImageDraw 用于画框

WINDOW_WIDTH = 1400  # 稍微加宽一点以容纳更宽的按钮和左侧列表
WINDOW_HEIGHT = 900  # 稍微加高一点


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

        # === 核心数据结构更改 ===
        # self.all_current_labels: 存储当前图片中所有人的标注
        # 结构: { annotation_index: defaultdict(lambda: [-1, -1, -1]) }
        self.all_current_labels = {}

        # self.current_label: 仅仅是一个引用，指向当前选中的那个人的 defaultdict
        self.current_label = None

        self.current_ann_index = 0  # 记录当前选中的是第几个 annotation
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
            self.labels = {label['id']: label for label in self.labels}
        else:
            self.labels = {}
        # 加载LDpose的标签
        self.LD_annotations, self.LD_image_infos = load_LD_labels(self.LD_label_file)
        self.LD_labels = {}
        for LD_image_info in self.LD_image_infos:
            LD_id = LD_image_info['id']
            annotations = [annotation for annotation in self.LD_annotations if annotation.get("image_id") == LD_id]
            # 注意：这里存的是 annotations 列表，而不是单个对象
            if len(annotations) == 0:
                continue
            self.LD_labels[LD_id] = [LD_image_info, annotations]

        # 统计数量（自动恢复）
        self.count_pro = sum(1 for info in self.labels.values() if info.get('has_pro') is True)
        self.count_no_pro = len(self.labels) - self.count_pro

        # 找到第一张未标注的位置
        self.todo_ids = self.get_todo_ids()

        # ------------------ UI ------------------
        # 使用 PanedWindow 分隔左右区域
        self.paned_window = tk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # === 左侧：Annotation 列表 ===
        self.left_frame = tk.Frame(self.paned_window, width=200, bg="#f0f0f0")
        self.paned_window.add(self.left_frame)

        tk.Label(self.left_frame, text="Annotations List", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(pady=5)

        list_frame = tk.Frame(self.left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.ann_listbox = tk.Listbox(list_frame, font=("Arial", 10), selectmode=tk.SINGLE)
        self.ann_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.ann_listbox.bind("<<ListboxSelect>>", self.on_annotation_select)  # 绑定选择事件

        scrollbar = tk.Scrollbar(list_frame, command=self.ann_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ann_listbox.config(yscrollcommand=scrollbar.set)

        # === 右侧：原本的图片和控制区 ===
        self.right_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.right_frame)

        # 设置 bd=0 消除边框误差
        self.image_label = tk.Label(self.right_frame, bd=0, highlightthickness=0)
        self.image_label.pack(expand=True)

        # 当前文件信息
        self.info_var = tk.StringVar()
        tk.Label(self.right_frame, textvariable=self.info_var).pack(pady=5)

        # 计数信息
        self.counter_var = tk.StringVar()
        self.update_counter_text()
        tk.Label(self.right_frame, textvariable=self.counter_var, font=("Arial", 12)).pack()

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

        # === 定义每个关键点的颜色 ===
        self.keypoint_colors = {
            1: '#FF0000',  # Red
            2: '#00FF00',  # Lime
            3: '#0000FF',  # Blue
            4: '#FFFF00',  # Yellow
            5: '#FF00FF',  # Magenta
            6: '#00FFFF',  # Cyan
            7: '#FFA500',  # Orange
            8: '#800080',  # Purple
            9: '#A52A2A',  # Brown
            10: '#FFC0CB',  # Pink
            11: '#808000',  # Olive
            12: '#008080',  # Teal
            13: '#000080',  # Navy
            14: '#FFD700',  # Gold
            15: '#DC143C',  # Crimson
            16: '#4B0082',  # Indigo
        }

        self.reset()

        # 点击坐标
        self.image_label.bind("<Button-1>", self.on_image_click)

        # 按钮区域
        btn_frame = tk.Frame(self.right_frame)
        btn_frame.pack(pady=10)
        for i in range(0, 4):
            for j in range(0, 4):
                keypoint_id = i * 4 + j + 1
                # 获取颜色并设置按钮前景或背景色，方便用户对应
                color = self.keypoint_colors.get(keypoint_id, 'black')
                tk.Button(
                    btn_frame,
                    text=self.keypoints[keypoint_id],
                    width=35,  # Changed width to 35 to fit text
                    fg=color if keypoint_id not in [4, 6, 10] else 'black',  # 浅色背景用黑字，深色用彩字，简单处理
                    # 或者可以在文字旁加个色块，这里简单起见直接设置文字颜色（除了太浅的黄色等）
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
            # 清除后刷新界面
            self.render_image_with_bbox()

    def ask_image_directory(self):
        dirname = filedialog.askdirectory(title="请选择图片目录")
        return Path(dirname) if dirname else None

    def reset(self):
        self.selected_keypoint_id = -1
        self.current_ann_index = 0

        # 重置所有人的标注容器
        self.all_current_labels = {}

        # 初始化第一个人的标注容器，并指向它
        self._switch_current_label_pointer(0)

    def _switch_current_label_pointer(self, index):
        """
        切换当前操作的 label 指针。
        如果该 index 的 label 还不存在，则创建一个新的 defaultdict。
        """
        self.current_ann_index = index
        if index not in self.all_current_labels:
            self.all_current_labels[index] = defaultdict(lambda: [-1, -1, -1])

        # 关键：改变引用指向
        self.current_label = self.all_current_labels[index]

    def set_vis(self, vis):
        if self.selected_keypoint_id is None or self.selected_keypoint_id < 0:
            messagebox.showwarning("提示", "请先选择一个关键点按钮，再设置 Vis。")
            return

        # 只有当该点已经有坐标时（不为全 -1），我们才允许改 Vis，或者你可以允许先设 Vis
        # 这里假设: 用户通常是先点坐标，默认 Vis=0/1/2，或者可以改 Vis。
        # 如果目前是 [-1, -1, -1]，改 Vis 变成 [-1, -1, vis]
        self.current_label[self.selected_keypoint_id][2] = vis

        # === 立即刷新显示 ===
        self.render_image_with_bbox()

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
        # 如果 save_result 返回 False (校验失败)，则不进行任何操作
        if not self.save_result():
            return

        if self.todo_ids:
            self.todo_ids.pop(0)
        self.reset()
        self.show_image()

    def save_result(self):
        if not self.todo_ids:
            return True

        current_id = self.todo_ids[0]

        # === 校验逻辑：在保存前检查完整性 ===
        # 遍历所有已编辑的人
        for ann_idx, person_labels in self.all_current_labels.items():
            # 遍历该人所有的关键点
            for key_id, val in person_labels.items():
                x, y, v = val

                # 状态判定：
                # 全空：[-1, -1, -1] -> 合法（未标注）
                # 全满：[>=0, >=0, >=0] -> 合法（已标注）
                # 其他：不合法（半成品）
                is_empty = (x == -1 and y == -1 and v == -1)
                is_full = (x != -1 and y != -1 and v != -1)

                if not is_empty and not is_full:
                    kp_name = self.keypoints.get(key_id, f"ID {key_id}")
                    msg = f"保存失败：\n检测到不完整的标注！\n\n" \
                          f"人物索引 (List Index): {ann_idx}\n" \
                          f"关键点: {kp_name}\n" \
                          f"当前值: {val}\n\n" \
                          f"请确保坐标 (xy) 和 可见性 (Vis) 都已设置，或者清除该点。"
                    messagebox.showerror("校验错误", msg)
                    return False

        # === 修正：检查所有人是否有标记 ===
        # 遍历 self.all_current_labels 中的每一个人的标注 dict
        has_pro = False
        for person_labels in self.all_current_labels.values():
            if any(v != [-1, -1, -1] for v in person_labels.values()):
                has_pro = True
                break

        with open(self.label_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        images = data.get("images", [])
        annotations = data.get("annotations", [])
        existing_ids = {img["id"] for img in images}

        if current_id not in existing_ids:
            img_info, anns_list = self.LD_labels[current_id]  # 获取的是一个 list

            # 1. 保存 image_info
            out_img_info = img_info.copy()
            out_img_info["has_pro"] = has_pro
            images.append(out_img_info)

            # 2. 保存 annotations
            if anns_list and len(anns_list) > 0:
                # === 修正逻辑：遍历该图所有 Annotation，并分别保存它们的标注 ===
                for idx, ann in enumerate(anns_list):
                    out_ann = ann.copy()

                    # 检查这个 index 是否在我们的标注记录里
                    if idx in self.all_current_labels:
                        person_labels = self.all_current_labels[idx]
                        # 只有当这个 dict 不为空（或者包含了修改）时才保存
                        # 这里直接转换成 dict 保存
                        print(f"Saving for annotation index {idx}: {person_labels}")
                        out_ann["new_keypoints"] = dict(person_labels)

                    # 将处理好的（或未修改的）annotation 加入列表
                    annotations.append(out_ann)

            else:
                # 如果原数据里完全没有 annotation，但我们却标注了（比如 index 0），则创建一个新的
                # 通常这种情况 index 肯定是 0
                if 0 in self.all_current_labels:
                    out_ann = {
                        "image_id": current_id,
                        "id": len(annotations) + 1,
                        "new_keypoints": dict(self.all_current_labels[0])
                    }
                    annotations.append(out_ann)

            self.labels[current_id] = out_img_info

        data["images"] = images
        data["annotations"] = annotations

        with open(self.label_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        if has_pro:
            self.count_pro += 1
        else:
            self.count_no_pro += 1
        self.update_counter_text()
        return True  # 保存成功

    def show_image(self):
        if len(self.todo_ids) == 0:
            messagebox.showinfo("完成", "所有图片已标注完毕！")
            self.stop_labeling()
            return

        current_id = self.todo_ids[0]

        # === 1. 加载并填充 Annotation 列表 ===
        self.ann_listbox.delete(0, tk.END)  # 清空旧列表
        _, anns_list = self.LD_labels[current_id]

        if anns_list:
            for idx, ann in enumerate(anns_list):
                # 显示格式: "Index: ID (Category)" 或其他有用信息
                cat_id = ann.get('category_id', '?')
                ann_id = ann.get('id', '?')
                self.ann_listbox.insert(tk.END, f"#{idx} - ID:{ann_id} (Cat:{cat_id})")

            # 默认选中第0个或者上次选中的（如果范围允许）
            target_idx = 0
            if self.current_ann_index < len(anns_list):
                target_idx = self.current_ann_index

            self.ann_listbox.selection_set(target_idx)
            # 确保指针和UI同步
            self._switch_current_label_pointer(target_idx)

        else:
            self.ann_listbox.insert(tk.END, "No Annotations")
            self._switch_current_label_pointer(0)  # 即使没有 annotation，也允许在 index 0 上标注

        # === 2. 绘制图片 (包含 bbox 和 keypoints) ===
        self.render_image_with_bbox()

    def on_annotation_select(self, event):
        """处理列表选择事件"""
        selection = self.ann_listbox.curselection()
        if selection:
            idx = selection[0]
            if idx != self.current_ann_index:
                # 切换到新人，指针指向新人的 label dict
                self._switch_current_label_pointer(idx)
                self.render_image_with_bbox()

    def render_image_with_bbox(self):
        """辅助函数：读取原图，画上当前选中ann的bbox和关键点，并显示"""
        current_id = self.todo_ids[0]
        img_file_name = self.LD_labels[current_id][0]['file_name']
        img_path = self.image_dir / img_file_name

        # 显示路径信息
        rel_path = img_path.relative_to(self.image_dir).as_posix()
        self.info_var.set(f"{len(self.labels)}/{len(self.LD_labels)} : {rel_path}")

        # 打开图片
        img = Image.open(img_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        # === 1. 画 BBox ===
        _, anns_list = self.LD_labels[current_id]
        if anns_list and 0 <= self.current_ann_index < len(anns_list):
            target_ann = anns_list[self.current_ann_index]
            if "bbox" in target_ann:
                # COCO bbox 格式: [x_min, y_min, width, height]
                x, y, w, h = target_ann["bbox"]
                # PIL rectangle 需要: [x_min, y_min, x_max, y_max]
                draw.rectangle([x, y, x + w, y + h], outline="red", width=3)

                # 可选：画个标签文字
                draw.text((x, y - 15), f"ID: {target_ann.get('id')}", fill="red")

        # === 2. 画 Keypoints (新功能) ===
        # self.current_label 包含当前选中人物的所有标注点
        r = 4  # 点的半径
        for key_id, (kx, ky, kv) in self.current_label.items():
            # 检查坐标是否有效 (不为 -1)
            if kx != -1 and ky != -1:
                # 获取对应的颜色
                color = self.keypoint_colors.get(key_id, 'white')

                # 画实心圆
                # 坐标: [x0, y0, x1, y1]
                draw.ellipse([kx - r, ky - r, kx + r, ky + r], fill=color, outline='black')

                # === 新增: 显示 Vis ===
                # 在点旁边显示可见性
                # 稍微偏移一点坐标 (x+r+2, y-r)，使用描边效果让文字更清晰
                draw.text((kx + r + 2, ky - r), str(kv), fill=color, stroke_fill="black", stroke_width=1)

        # 显示图片
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

        # === 点击后立即刷新显示，以便看到刚才点的点 ===
        self.render_image_with_bbox()


def main():
    root = tk.Tk()
    app = ProsthesisLabelerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()