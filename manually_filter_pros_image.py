import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from send2trash import send2trash  # 用于安全删除到回收站


class ImageViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("图片筛选工具 (A/D 翻页, Delete 删除)")
        self.root.geometry("900x700")

        # 状态变量
        self.image_list = []
        self.current_idx = 0
        self.current_image_path = None
        self.folder_path = ""

        # === UI 布局 ===

        # 1. 图片显示区域
        self.img_label = tk.Label(root, text="请点击下方按钮选择文件夹", bg="gray")
        self.img_label.pack(expand=True, fill="both", padx=10, pady=10)

        # 2. 信息显示区域 (文件名)
        self.info_label = tk.Label(root, text="等待加载...", font=("Arial", 12))
        self.info_label.pack(pady=5)

        # 3. 按钮控制区域
        btn_frame = tk.Frame(root)
        btn_frame.pack(fill="x", pady=10, padx=20)

        # 按钮样式配置
        btn_opts = {'font': ("Arial", 12), 'width': 12, 'height': 2}

        self.btn_select = tk.Button(btn_frame, text="选择文件夹", command=self.select_folder, **btn_opts)
        self.btn_select.pack(side="left", padx=5)

        self.btn_prev = tk.Button(btn_frame, text="< 上一张 (A)", command=self.prev_image, state="disabled", **btn_opts)
        self.btn_prev.pack(side="left", padx=5)

        self.btn_next = tk.Button(btn_frame, text="下一张 (D) >", command=self.next_image, state="disabled", **btn_opts)
        self.btn_next.pack(side="left", padx=5)

        # 删除按钮用红色强调
        self.btn_del = tk.Button(btn_frame, text="删除 (Del)", command=self.delete_image, bg="#ffcccc", fg="red",
                                 state="disabled", **btn_opts)
        self.btn_del.pack(side="right", padx=5)

        # === 键盘绑定 ===
        # 绑定 a/d 和 左右方向键
        root.bind('<a>', lambda event: self.prev_image())
        root.bind('<Left>', lambda event: self.prev_image())
        root.bind('<d>', lambda event: self.next_image())
        root.bind('<Right>', lambda event: self.next_image())
        # 绑定 Delete 键
        root.bind('<Delete>', lambda event: self.delete_image())

    def select_folder(self):
        """选择文件夹并加载图片"""
        path = filedialog.askdirectory()
        if not path:
            return

        self.folder_path = path
        # 支持的图片格式
        valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')

        # 获取所有图片并排序
        self.image_list = [
            f for f in os.listdir(path)
            if f.lower().endswith(valid_extensions)
        ]
        self.image_list.sort()  # 按文件名排序

        if not self.image_list:
            messagebox.showinfo("提示", "该文件夹下没有找到图片。")
            return

        self.current_idx = 0
        self.load_image()
        self.update_buttons()

    def load_image(self):
        """读取并显示当前索引的图片"""
        if not self.image_list:
            self.img_label.config(image='', text="文件夹为空")
            self.info_label.config(text="")
            return

        filename = self.image_list[self.current_idx]
        self.current_image_path = os.path.join(self.folder_path, filename)

        try:
            # 使用 PIL 读取
            pil_image = Image.open(self.current_image_path)

            # --- 智能缩放逻辑 ---
            # 获取显示区域的大小 (如果窗口刚启动还没大小，就给个默认值)
            win_w = self.root.winfo_width()
            win_h = self.root.winfo_height()
            if win_w < 100: win_w = 800
            if win_h < 100: win_h = 600

            # 留出按钮区域的高度
            display_h = win_h - 150
            display_w = win_w - 50

            # 保持比例缩放 (thumbnail 修改原对象，copy防止修改原图对象虽非必须但更安全)
            img_copy = pil_image.copy()
            img_copy.thumbnail((display_w, display_h), Image.Resampling.LANCZOS)

            self.tk_image = ImageTk.PhotoImage(img_copy)

            # 更新界面
            self.img_label.config(image=self.tk_image, text="")
            self.info_label.config(
                text=f"[{self.current_idx + 1}/{len(self.image_list)}] {filename}"
            )

        except Exception as e:
            print(f"无法加载图片: {e}")
            self.img_label.config(text=f"无法加载: {filename}")

    def next_image(self):
        """下一张"""
        if not self.image_list: return

        # 循环浏览：如果到了最后一张，回到第一张
        self.current_idx += 1
        if self.current_idx >= len(self.image_list):
            self.current_idx = 0  # 循环
            # self.current_idx = len(self.image_list) - 1 # 如果不想循环，用这行

        self.load_image()

    def prev_image(self):
        """上一张"""
        if not self.image_list: return

        self.current_idx -= 1
        if self.current_idx < 0:
            self.current_idx = len(self.image_list) - 1  # 循环到最后一张

        self.load_image()

    def delete_image(self):
        """删除当前图片到回收站"""
        if not self.image_list: return

        filename = self.image_list[self.current_idx]
        full_path = os.path.join(self.folder_path, filename)

        # 二次确认（如果需要快速删除，可以把下面这三行注释掉）
        # confirm = messagebox.askyesno("确认删除", f"确定要把 {filename} 移入回收站吗？")
        # if not confirm:
        #     return

        try:
            # 核心：移动到回收站
            send2trash(full_path)
            print(f"已删除: {filename}")

            # 从列表中移除
            del self.image_list[self.current_idx]

            # 索引调整：如果删的是最后一张，索引前移
            if self.current_idx >= len(self.image_list):
                self.current_idx = len(self.image_list) - 1

            # 如果删完没图了
            if not self.image_list:
                self.img_label.config(image='', text="文件夹已空")
                self.info_label.config(text="无图片")
                self.update_buttons()
            else:
                self.load_image()

        except Exception as e:
            messagebox.showerror("错误", f"删除失败: {e}")

    def update_buttons(self):
        """根据是否有图片启用/禁用按钮"""
        state = "normal" if self.image_list else "disabled"
        self.btn_prev.config(state=state)
        self.btn_next.config(state=state)
        self.btn_del.config(state=state)


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageViewer(root)
    root.mainloop()