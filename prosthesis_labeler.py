import os
import csv
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 800


def load_existing_labels(label_path: Path):
    """读取已有 labels.csv，返回 {filename: label}"""
    labels = {}
    if label_path.exists():
        with open(label_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) >= 2:
                    labels[row[0]] = row[1]
    return labels


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
        self.master = master
        self.master.title("LD-Prosthesis Labeler (3-Class with Resume)")
        self.master.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        # ------------------ 用户选择 ------------------
        self.image_dir = self.ask_image_directory()
        if not self.image_dir:
            self.master.destroy()
            return

        self.label_file = self.ask_label_file()
        if not self.label_file:
            self.master.destroy()
            return

        # ------------------ 载入数据 ------------------
        self.all_images = list_images(self.image_dir)
        if not self.all_images:
            messagebox.showerror("错误", "目录中没有图片: " + str(self.image_dir))
            self.master.destroy()
            return

        # 加载已有标签 → 实现 resume
        self.labels = load_existing_labels(self.label_file)

        # 统计数量（自动恢复）
        self.count_2 = sum(1 for v in self.labels.values() if v == "2")
        self.count_1 = sum(1 for v in self.labels.values() if v == "1")
        self.count_0 = sum(1 for v in self.labels.values() if v == "0")

        # 找到第一张未标注的位置 → resume
        self.index = 0
        self.skip_labeled()

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

        # 按钮区域
        btn_frame = tk.Frame(self.master)
        btn_frame.pack(pady=10)

        tk.Button(
            btn_frame,
            text="连接点可见 (2)",
            width=18,
            command=lambda: self.save_label("2")
        ).grid(row=0, column=0, padx=5)

        tk.Button(
            btn_frame,
            text="衣物遮挡 (1)",
            width=18,
            command=lambda: self.save_label("1")
        ).grid(row=0, column=1, padx=5)

        tk.Button(
            btn_frame,
            text="无假肢 (0)",
            width=18,
            command=lambda: self.save_label("0")
        ).grid(row=0, column=2, padx=5)

        tk.Button(
            btn_frame,
            text="跳过",
            width=10,
            command=self.skip_image
        ).grid(row=0, column=3, padx=5)

        tk.Button(
            btn_frame,
            text="结束",
            width=12,
            command=self.stop_labeling
        ).grid(row=0, column=4, padx=5)

        # 键盘绑定
        self.master.bind("2", lambda event: self.save_label("2"))
        self.master.bind("1", lambda event: self.save_label("1"))
        self.master.bind("0", lambda event: self.save_label("0"))
        self.master.bind("<Right>", lambda event: self.skip_image())
        self.master.bind("<Escape>", lambda event: self.stop_labeling())

        # 打开 label 文件（追加）
        init_new_file = not self.label_file.exists()
        self.label_f = open(self.label_file, "a", newline="", encoding="utf-8")
        self.writer = csv.writer(self.label_f)
        if init_new_file:
            self.writer.writerow(["filename", "label"])

        # 显示图片（resume 到正确位置）
        self.show_image()

    # ==========================================
    # 选择文件夹 / 文件
    # ==========================================
    def ask_image_directory(self):
        dirname = filedialog.askdirectory(title="请选择图片目录")
        return Path(dirname) if dirname else None

    def ask_label_file(self):
        filename = filedialog.asksaveasfilename(
            title="请选择 labels.csv 保存位置",
            initialfile="labels.csv",
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")]
        )
        return Path(filename) if filename else None

    # ==========================================
    # 自动跳过已标注的图片（resume）
    # ==========================================
    def skip_labeled(self):
        while self.index < len(self.all_images):
            rel = self.all_images[self.index].relative_to(self.image_dir).as_posix()
            if rel not in self.labels:
                break
            self.index += 1

    # ==========================================
    # UI 更新
    # ==========================================
    def update_counter_text(self):
        total = self.count_2 + self.count_1 + self.count_0
        self.counter_var.set(
            f"已标注：{total}   |   连接点可见(2)：{self.count_2}   |   衣物遮挡(1)：{self.count_1}   |   无假肢(0)：{self.count_0}"
        )

    def show_image(self):
        if self.index >= len(self.all_images):
            messagebox.showinfo("完成", "所有图片已标注完毕！")
            self.stop_labeling()
            return

        img_path = self.all_images[self.index]
        rel_path = img_path.relative_to(self.image_dir).as_posix()

        self.info_var.set(f"{self.index + 1}/{len(self.all_images)} : {rel_path}")

        img = Image.open(img_path).convert("RGB")
        w, h = img.size
        scale = min((WINDOW_WIDTH - 40) / w, (WINDOW_HEIGHT - 150) / h, 1.0)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        self.tk_img = ImageTk.PhotoImage(img)
        self.image_label.config(image=self.tk_img)

    # ==========================================
    # 保存标签
    # ==========================================
    def save_label(self, label: str):
        img_path = self.all_images[self.index]
        rel_path = img_path.relative_to(self.image_dir).as_posix()

        # 写 CSV
        self.writer.writerow([rel_path, label])
        self.label_f.flush()

        # 内存更新
        self.labels[rel_path] = label
        if label == "2":
            self.count_2 += 1
        elif label == "1":
            self.count_1 += 1
        else:
            self.count_0 += 1

        self.update_counter_text()

        # 下一张
        self.index += 1
        self.skip_labeled()
        self.show_image()

    # ==========================================
    # 跳过
    # ==========================================
    def skip_image(self):
        self.index += 1
        self.skip_labeled()
        self.show_image()

    # ==========================================
    # 结束标注
    # ==========================================
    def stop_labeling(self):
        try:
            self.label_f.close()
        except:
            pass
        messagebox.showinfo("退出", "标注结束，数据已保存。")
        self.master.destroy()


def main():
    root = tk.Tk()
    app = ProsthesisLabelerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
