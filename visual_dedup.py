import os
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import imagehash
import threading

# ================= 配置区域 =================
# 请替换为你实际的文件夹路径
DIR_CRAWLER = "/DATA/knee_round1"  # 待清洗的爬虫数据
DIR_TRAIN = "/DATA/knee"  # 训练集
DIR_VAL = "/DATA/knee"  # 验证集
DIR_TEST = "/DATA/knee"  # 测试集

# 相似度阈值 (越小越严格，5是推荐值)
THRESHOLD = 5
# 图片在界面上的显示大小
IMG_SIZE = (250, 250)


# ===========================================

class DeduplicateApp:
    def __init__(self, root):
        self.root = root
        self.root.title("全能数据集去重工具 (支持双向删除)")
        self.root.geometry("1200x700")

        # 数据存储
        # protected_hashes = { path: {'hash': h, 'type': 'train'/'val'/'test', 'path': path} }
        self.protected_hashes = {}
        self.crawler_files = []
        self.current_match = None
        self.stop_thread = False

        self.setup_ui()

        # 启动后台线程加载数据
        threading.Thread(target=self.load_data_thread, daemon=True).start()

    def setup_ui(self):
        # --- 1. 顶部状态与进度 ---
        self.top_frame = tk.Frame(self.root, pady=10)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        self.status_label = tk.Label(self.top_frame, text="正在初始化...", font=("微软雅黑", 10))
        self.status_label.pack()

        self.progress = ttk.Progressbar(self.top_frame, orient="horizontal", length=1000, mode="determinate")
        self.progress.pack(pady=5)

        # --- 2. 中间图片展示区 (Grid布局) ---
        self.img_frame = tk.Frame(self.root)
        self.img_frame.pack(expand=True, fill=tk.BOTH, padx=10)

        headers = ["【爬虫 (新数据)】", "【Train (训练集)】", "【Val (验证集)】", "【Test (测试集)】"]
        # 对应列的标识符
        self.col_tags = ["crawler", "train", "val", "test"]
        colors = ["red", "blue", "green", "orange"]

        self.image_labels = {}  # 图片控件
        self.text_labels = {}  # 文件名控件
        self.del_buttons = {}  # 删除按钮控件

        for idx, tag in enumerate(self.col_tags):
            # 每个列一个Frame
            frame = tk.Frame(self.img_frame, borderwidth=2, relief="groove")
            frame.grid(row=0, column=idx, padx=5, pady=5, sticky="nsew")
            self.img_frame.columnconfigure(idx, weight=1)

            # 2.1 标题
            tk.Label(frame, text=headers[idx], fg=colors[idx], font=("Arial", 11, "bold")).pack(side=tk.TOP, pady=5)

            # 2.2 图片区域
            lbl_img = tk.Label(frame, text="等待扫描...", bg="#f0f0f0")
            lbl_img.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
            self.image_labels[tag] = lbl_img

            # 2.3 底部操作区 (文件名 + 删除按钮)
            bottom_box = tk.Frame(frame)
            bottom_box.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

            # 文件名
            lbl_text = tk.Label(bottom_box, text="", wraplength=200, fg="gray", font=("Arial", 9))
            lbl_text.pack(side=tk.TOP, pady=5)
            self.text_labels[tag] = lbl_text

            # 删除按钮 (每个列都有！)
            # 使用 lambda 绑定当前的 tag
            btn = tk.Button(bottom_box, text=f"删除此图", bg="#ffdddd", fg="red",
                            font=("Arial", 10, "bold"),
                            command=lambda t=tag: self.delete_file_action(t),
                            state=tk.DISABLED)
            btn.pack(side=tk.TOP)
            self.del_buttons[tag] = btn

        # --- 3. 底部总控区 ---
        self.btn_frame = tk.Frame(self.root, pady=15, bg="#eeeeee")
        self.btn_frame.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Label(self.btn_frame, text="操作提示: 删除爬虫图会自动跳下一个；删除资料库图会停留在当前页面。",
                 bg="#eeeeee", fg="#555").pack(side=tk.TOP, pady=5)

        self.btn_skip = tk.Button(self.btn_frame, text="全部保留并跳过 (Next/Skip)",
                                  font=("Arial", 12, "bold"), bg="white", height=2, width=30,
                                  command=self.next_match, state=tk.DISABLED)
        self.btn_skip.pack()

    def load_data_thread(self):
        """后台加载哈希和文件列表"""
        datasets = [
            (DIR_TRAIN, 'train'),
            (DIR_VAL, 'val'),
            (DIR_TEST, 'test')
        ]

        # 1. 统计文件总数
        self.update_status("正在扫描文件列表...")
        all_dataset_files = []
        for dir_path, tag in datasets:
            if not os.path.exists(dir_path): continue
            for f in os.listdir(dir_path):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                    all_dataset_files.append((os.path.join(dir_path, f), tag))

        total_files = len(all_dataset_files)
        self.root.after(0, lambda: self.progress.configure(maximum=total_files, value=0))

        # 2. 计算资料库 Hash
        count = 0
        for path, tag in all_dataset_files:
            if self.stop_thread: return
            count += 1
            if count % 10 == 0:
                self.update_status(f"建立索引中 ({tag}): {count}/{total_files}")
                self.root.after(0, lambda v=count: self.progress.configure(value=v))

            try:
                with Image.open(path) as img:
                    h = imagehash.phash(img)
                    # key使用路径，方便查找和删除
                    self.protected_hashes[path] = {'hash': h, 'type': tag, 'path': path}
            except:
                continue

        # 3. 加载爬虫文件列表
        self.update_status("正在加载爬虫文件夹...")
        if os.path.exists(DIR_CRAWLER):
            files = sorted(os.listdir(DIR_CRAWLER))  # 排序一下，体验好点
            for f in files:
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                    self.crawler_files.append(os.path.join(DIR_CRAWLER, f))

        self.update_status(
            f"准备就绪！资料库: {len(self.protected_hashes)} 张, 爬虫待处理: {len(self.crawler_files)} 张")
        self.root.after(0, self.start_scanning)

    def update_status(self, text):
        self.root.after(0, lambda: self.status_label.config(text=text))

    def start_scanning(self):
        self.progress.pack_forget()  # 隐藏进度条
        self.crawler_iter = iter(self.crawler_files)
        self.next_match()

    def next_match(self):
        """查找下一个有重复的图片"""
        # 重置按钮状态
        self.reset_ui_state()

        found_conflict = False

        while not found_conflict:
            try:
                crawler_path = next(self.crawler_iter)
            except StopIteration:
                self.finish_all()
                return

            # 如果文件已经被删了（可能外部操作），跳过
            if not os.path.exists(crawler_path):
                continue

            try:
                with Image.open(crawler_path) as img:
                    c_hash = imagehash.phash(img)
            except:
                continue

            self.status_label.config(text=f"正在比对: {os.path.basename(crawler_path)}")
            self.root.update()

            matches = {'train': None, 'val': None, 'test': None}
            has_match = False

            # 在 protected_hashes 中查找匹配
            # 注意：这里简单的遍历在数据量巨大(10w+)时会慢，如果很慢需要换成 VP-Tree，但几千张图没事
            for p_path, p_info in self.protected_hashes.items():
                if c_hash - p_info['hash'] <= THRESHOLD:
                    matches[p_info['type']] = p_path
                    has_match = True
                    # 只要该类别找到一个匹配的就够了（防止显示太多），想看所有可以改逻辑
                    # 这里不break，因为train/val/test可能各有一个

            if has_match:
                self.current_match = {
                    'crawler': crawler_path,
                    'matches': matches,  # {'train': path, 'val': None, ...}
                    'crawler_hash': c_hash  # 存一下hash备用
                }
                found_conflict = True
                self.show_match_ui()

    def show_match_ui(self):
        """显示当前的匹配结果"""
        self.btn_skip.config(state=tk.NORMAL)

        # 1. 显示爬虫图
        c_path = self.current_match['crawler']
        self.display_image(c_path, 'crawler')
        self.del_buttons['crawler'].config(state=tk.NORMAL, text="删除爬虫图")

        # 2. 显示匹配图
        matches = self.current_match['matches']
        for tag in ['train', 'val', 'test']:
            path = matches[tag]
            if path and os.path.exists(path):
                self.display_image(path, tag)
                self.del_buttons[tag].config(state=tk.NORMAL, text="删除此库图")
            else:
                self.clear_slot(tag)

    def display_image(self, path, tag):
        try:
            img = Image.open(path)
            img.thumbnail(IMG_SIZE)
            tk_img = ImageTk.PhotoImage(img)

            self.image_labels[tag].config(image=tk_img, text="")
            self.image_labels[tag].image = tk_img
            self.text_labels[tag].config(text=os.path.basename(path))
        except Exception as e:
            self.image_labels[tag].config(text="图片损坏", image="")
            print(e)

    def clear_slot(self, tag):
        """清空某一列的显示"""
        self.image_labels[tag].config(image="", text="无匹配/已删除")
        self.text_labels[tag].config(text="")
        self.del_buttons[tag].config(state=tk.DISABLED)

    def reset_ui_state(self):
        for tag in self.col_tags:
            self.clear_slot(tag)
        self.btn_skip.config(state=tk.DISABLED)

    def delete_file_action(self, tag):
        """核心删除逻辑"""
        if not self.current_match: return

        file_path = ""
        is_crawler = (tag == 'crawler')

        if is_crawler:
            file_path = self.current_match['crawler']
        else:
            file_path = self.current_match['matches'][tag]

        if file_path and os.path.exists(file_path):
            try:
                # 1. 执行物理删除
                # 如果是windows有时可能需要先释放图片引用，这里Image.open后已关闭，ImageTk引用不影响删除
                os.remove(file_path)
                print(f"已删除: {file_path}")

                # 2. 界面反馈
                self.clear_slot(tag)

                # 3. 逻辑后续
                if is_crawler:
                    # 如果删的是爬虫图，说明冲突解决（源头没了），直接下一张
                    self.status_label.config(text="爬虫图已删，查找下一张...", fg="green")
                    self.root.after(500, self.next_match)
                else:
                    # 如果删的是资料库图 (Train/Val/Test)
                    # a. 从内存索引中移除，防止后面比对时又匹配到这个不存在的文件
                    if file_path in self.protected_hashes:
                        del self.protected_hashes[file_path]

                    # b. 更新 current_match 数据，避免再次点击出错
                    self.current_match['matches'][tag] = None

                    self.status_label.config(text=f"资料库图片({tag})已删。你可以继续删除爬虫图，或点击跳过。", fg="blue")
                    # c. 不自动跳过！因为用户可能还想把爬虫图也删了，或者检查其他列的匹配。

            except Exception as e:
                messagebox.showerror("删除失败", f"无法删除文件:\n{e}")
        else:
            messagebox.showwarning("提示", "文件不存在或已被删除")
            self.clear_slot(tag)

    def finish_all(self):
        self.reset_ui_state()
        self.status_label.config(text="全部扫描完成！", fg="green")
        messagebox.showinfo("完成", "爬虫文件夹扫描结束。")


if __name__ == "__main__":
    root = tk.Tk()
    # 捕获关闭事件
    app = DeduplicateApp(root)


    def on_closing():
        app.stop_thread = True
        root.destroy()


    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()