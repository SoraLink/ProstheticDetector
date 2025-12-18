import json
import tkinter as tk
import threading
import shutil
import copy
from tkinter import messagebox, filedialog
from collections import defaultdict
from pathlib import Path
from typing import List, Tuple, Dict

from PIL import Image, ImageTk, ImageDraw, ImageOps

# ==========================================
#              GLOBAL SETTINGS
# ==========================================
# [开关] 设置为 False 将彻底隐藏按钮、禁用启动/退出时的弹窗和上传功能
ENABLE_CLOUD_SYNC = True
# ==========================================

try:
    from huggingface_hub import upload_file, hf_hub_download

    HF_AVAILABLE = True if ENABLE_CLOUD_SYNC else False
except ImportError:
    HF_AVAILABLE = False
    if ENABLE_CLOUD_SYNC:
        print("Warning: huggingface_hub library not installed. Cloud features disabled.")


class Config:
    """
    Config class.
    """
    HF_REPO_ID = "Soralink/LDPoseP"  # 你的仓库ID

    WINDOW_WIDTH = 1400
    WINDOW_HEIGHT = 900

    KEYPOINTS = {
        1: 'Above left elbow residual limb end',
        2: 'Above right elbow residual limb end',
        3: 'Below left elbow residual limb end',
        4: 'Below right elbow residual limb end',
        5: 'Above left knee residual limb end',
        6: 'Above right knee residual limb end',
        7: 'Below left knee residual limb end',
        8: 'Below right knee residual limb end',
        9: 'Left prosthetic elbow',
        10: 'Right prosthetic elbow',
        11: 'Left prosthetic wrist',
        12: 'Right prosthetic wrist',
        13: 'Left prosthetic knee',
        14: 'Right prosthetic knee',
        15: 'Left prosthetic ankle',
        16: 'Right prosthetic ankle',
        17: 'Left Prosthetic Wrist End',
        18: 'Right Prosthetic Wrist End',
        19: 'Left Prosthetic Ankle End',
        20: 'Right Prosthetic Ankle End',
    }

    SHORT_NAMES = {
        1: 'L-Elbow\nRes(Above)', 2: 'R-Elbow\nRes(Above)',
        3: 'L-Elbow\nRes(Below)', 4: 'R-Elbow\nRes(Below)',
        5: 'L-Knee\nRes(Above)', 6: 'R-Knee\nRes(Above)',
        7: 'L-Knee\nRes(Below)', 8: 'R-Knee\nRes(Below)',
        9: 'L-Pros\nElbow', 10: 'R-Pros\nElbow',
        11: 'L-Pros\nWrist', 12: 'R-Pros\nWrist',
        13: 'L-Pros\nKnee', 14: 'R-Pros\nKnee',
        15: 'L-Pros\nAnkle', 16: 'R-Pros\nAnkle',
        17: 'L-Wrist\nEnd', 18: 'R-Wrist\nEnd',
        19: 'L-Ankle\nEnd', 20: 'R-Ankle\nEnd',
    }

    MUTUAL_EXCLUSIVE_PAIRS = {
        17: 11,
        18: 12,
        19: 15,
        20: 16,
    }

    REVERSE_MUTUAL_PAIRS = {v: k for k, v in MUTUAL_EXCLUSIVE_PAIRS.items()}

    PROSTHETIC_IDS = {9, 10, 11, 12, 13, 14, 15, 16}
    END_POINT_IDS = {17, 18, 19, 20}
    UPPER_RESIDUAL_IDS = {1, 2, 5, 6}
    COLORS = {
        1: '#FF0000', 2: '#00FF00', 3: '#FF00FF', 4: '#00FFFF',
        5: '#A52A2A', 6: '#FFC0CB', 7: '#000080', 8: '#8B4513',
        9: '#0000FF', 10: '#B8860B', 11: '#FFA500', 12: '#800080',
        13: '#808000', 14: '#008080', 15: '#DC143C', 16: '#4B0082',
        17: '#FF4500', 18: '#FF4500', 19: '#FFD700', 20: '#FFD700',
    }

    # R1 参考点的颜色 (灰色)
    R1_COLOR = '#A0A0A0'

    BUTTON_LAYOUT = [
        [1, 2, None, 9, 10, None],
        [3, 4, 17, 11, 12, 18],  # 手腕及端点
        [5, 6, None, 13, 14, None],
        [7, 8, 19, 15, 16, 20]  # 脚踝及端点
    ]

    COCO_SKELETON = [
        (0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
        (11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (5, 11), (6, 12)
    ]
    COCO_LEFT_SIDE = {5, 7, 9, 11, 13, 15}
    COCO_RIGHT_SIDE = {6, 8, 10, 12, 14, 16}
    PROSTHETIC_CONNECTIONS = [
        (1, 9), (9, 11), (9, 17), (3, 11), (3, 17),
        (2, 10), (10, 12), (10, 18), (4, 12), (4, 18),
        (5, 13), (13, 15), (13, 19), (7, 15), (7, 19),
        (6, 14), (14, 16), (14, 20), (8, 16), (8, 20),
    ]


class DataManager:
    def __init__(self):
        self.ld_label_path = None  # 原始 COCO/LD 标注
        self.round1_label_path = None  # [NEW] Round 1 标注 (只读参考 & 初始值来源)
        self.output_label_path = None  # Round 2 输出
        self.image_dir = None

        self.all_image_ids = []
        self.ld_data_map = {}
        self.r1_anns_map = defaultdict(list)  # [NEW] Round 1 数据缓存
        self.saved_anns_map = defaultdict(list)  # Round 2 数据缓存
        self.saved_images_map = {}  # [NEW] Round 2 图片信息缓存 (用于存储 is_discarded)
        self.finished_ids = set()

        self.output_cache = {"images": [], "annotations": []}
        self.write_lock = threading.Lock()
        self.save_thread = None

    def set_paths(self, ld_path, r1_path, out_path, img_dir):
        self.ld_label_path = ld_path
        self.round1_label_path = r1_path
        self.output_label_path = out_path
        self.image_dir = img_dir

    def load_data(self):
        # 1. 加载原始标注 (Base Data)
        ld_anns, ld_imgs = self._load_json(self.ld_label_path)
        if not ld_imgs: return False

        self.ld_data_map = {}
        temp_ld_anns = defaultdict(list)
        for ann in ld_anns:
            temp_ld_anns[ann.get("image_id")].append(ann)
        for img in ld_imgs:
            img_id = img['id']
            if img_id in temp_ld_anns:
                self.ld_data_map[img_id] = (img, temp_ld_anns[img_id])
        self.all_image_ids = sorted(list(self.ld_data_map.keys()))

        # 2. [NEW] 加载 Round 1 数据 (只读)
        r1_anns, _ = self._load_json(self.round1_label_path)
        self.r1_anns_map = defaultdict(list)
        for ann in r1_anns:
            self.r1_anns_map[ann['image_id']].append(ann)

        # 3. 加载 Round 2 输出文件 (可读写)
        if self.output_label_path and self.output_label_path.exists():
            try:
                with open(self.output_label_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, dict): data = {"images": [], "annotations": []}
                    self.output_cache = data
            except Exception:
                self.output_cache = {"images": [], "annotations": []}
        else:
            self.output_cache = {"images": [], "annotations": []}

        # 4. 构建 Round 2 快速查找表
        self.saved_anns_map = defaultdict(list)
        self.saved_images_map = {}  # [NEW]

        for ann in self.output_cache.get("annotations", []):
            self.saved_anns_map[ann['image_id']].append(ann)

        for img in self.output_cache.get("images", []):
            self.saved_images_map[img['id']] = img

        self.finished_ids = {img['id'] for img in self.output_cache.get("images", [])}
        return True

    def _load_json(self, path) -> Tuple[List, List]:
        if not path or not path.exists(): return [], []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "annotations" in data:
                return data["annotations"], data.get("images", [])
            return [], []
        except Exception:
            return [], []

    def get_next_todo_index(self) -> int:
        for i, img_id in enumerate(self.all_image_ids):
            if img_id not in self.finished_ids: return i
        return len(self.all_image_ids) - 1 if self.all_image_ids else 0

    def get_image_context(self, index: int) -> Dict | None:
        if index < 0 or index >= len(self.all_image_ids): return None
        current_id = self.all_image_ids[index]
        img_info, ld_anns = self.ld_data_map[current_id]

        # 获取该图对应的 Round 1 数据
        r1_anns = self.r1_anns_map.get(current_id, [])
        # 获取该图对应的 Round 2 (已保存) 数据
        saved_anns = self.saved_anns_map.get(current_id, [])
        # [NEW] 获取图片状态 (是否废弃)
        saved_img_info = self.saved_images_map.get(current_id, {})
        is_discarded = saved_img_info.get("is_discarded", False)

        return {
            "id": current_id,
            "file_name": img_info['file_name'],
            "full_path": self.image_dir / img_info['file_name'],
            "ld_anns": ld_anns,  # Base COCO
            "r1_anns": r1_anns,  # Round 1 Data
            "saved_anns": saved_anns,  # Round 2 Data
            "is_discarded": is_discarded,  # [NEW]
            "index_str": f"{index + 1}/{len(self.all_image_ids)}"
        }

    def save_annotation_result(self, current_id, current_labels_map, is_marked_deleted=False, sync=False):
        """保存到 Round 2 的缓存和文件"""
        images = self.output_cache.get("images", [])
        annotations = self.output_cache.get("annotations", [])

        # 移除旧数据
        images = [img for img in images if img['id'] != current_id]
        annotations = [ann for ann in annotations if ann['image_id'] != current_id]

        # 准备新数据
        img_info, ld_anns = self.ld_data_map[current_id]
        has_valid_data = False
        for person_labels in current_labels_map.values():
            if person_labels:
                has_valid_data = True
                break

        out_img_info = img_info.copy()
        out_img_info["has_pro"] = has_valid_data
        out_img_info["is_discarded"] = is_marked_deleted  # [NEW] 记录废弃状态
        images.append(out_img_info)

        new_saved_cache = []
        if ld_anns:
            for idx, ann in enumerate(ld_anns):
                out_ann = ann.copy()
                if idx in current_labels_map:
                    person_labels = current_labels_map[idx]
                    if person_labels:
                        out_ann["new_keypoints"] = dict(person_labels)
                annotations.append(out_ann)
                new_saved_cache.append(out_ann)
        else:
            if 0 in current_labels_map and current_labels_map[0]:
                out_ann = {
                    "image_id": current_id,
                    "id": 9000000 + current_id,
                    "new_keypoints": dict(current_labels_map[0])
                }
                annotations.append(out_ann)
                new_saved_cache.append(out_ann)

        self.output_cache["images"] = images
        self.output_cache["annotations"] = annotations

        # 更新快速查找表
        self.finished_ids.add(current_id)
        self.saved_anns_map[current_id] = new_saved_cache
        self.saved_images_map[current_id] = out_img_info  # [NEW]

        if sync:
            if self.save_thread and self.save_thread.is_alive():
                self.save_thread.join()
            self._write_to_disk()
        else:
            if self.save_thread and self.save_thread.is_alive():
                return len(self.finished_ids)
            self.save_thread = threading.Thread(target=self._write_to_disk)
            self.save_thread.daemon = True
            self.save_thread.start()

        return len(self.finished_ids)

    def _write_to_disk(self):
        with self.write_lock:
            try:
                with open(self.output_label_path, "w", encoding="utf-8") as f:
                    json.dump(self.output_cache, f, ensure_ascii=False, indent=None)
            except Exception as e:
                print(f"Error saving to disk: {e}")


class ImageVisualizer:
    def render(self, base_img, ld_anns, selected_ann_index, current_labels_map,
               r1_anns_map,
               show_coco_kps=True, show_extra_kps=False,
               show_bbox=True, show_connections=True,
               show_r1_res=False, show_r1_pro=False,
               is_discarded=False,  # [NEW]
               scale=1.0):

        if base_img is None: return None
        img = base_img.copy()
        draw = ImageDraw.Draw(img)

        def to_screen(v):
            return v * scale

        # [NEW] 如果被标记废弃，画一个巨大的红叉
        if is_discarded:
            w, h = img.size
            draw.line([(0, 0), (w, h)], fill="red", width=5)
            draw.line([(0, h), (w, 0)], fill="red", width=5)
            # 可选：左上角再写个字，防止被遮挡
            draw.text((10, 10), "!!! DISCARDED !!!", fill="red")

        # 1. 绘制 COCO 基础点
        if ld_anns and 0 <= selected_ann_index < len(ld_anns):
            target_ann = ld_anns[selected_ann_index]
            if show_coco_kps:
                self._draw_coco_keypoints(draw, target_ann, to_screen)
            if show_extra_kps:
                self._draw_extra_keypoints(draw, target_ann, to_screen)
            if show_bbox and "bbox" in target_ann:
                x, y, w, h = target_ann["bbox"]
                sx, sy, sw, sh = to_screen(x), to_screen(y), to_screen(w), to_screen(h)
                draw.rectangle([sx, sy, sx + sw, sy + sh], outline="red", width=2)
                draw.text((sx, sy - 15), f"ID: {target_ann.get('id')}", fill="red")

        # 2. 绘制 Round 1 参考点 (只读，灰色)
        r1_person_data = {}
        if r1_anns_map:
            if 0 <= selected_ann_index < len(r1_anns_map):
                r1_ann = r1_anns_map[selected_ann_index]
                if "new_keypoints" in r1_ann:
                    r1_person_data = r1_ann["new_keypoints"]

        if show_r1_res or show_r1_pro:
            self._draw_static_points(draw, r1_person_data, to_screen, show_r1_res, show_r1_pro)

        # 3. 绘制 Round 2 当前编辑点
        current_person_labels = current_labels_map.get(selected_ann_index, {})

        if show_connections:
            self._draw_prosthetic_connections(draw, current_person_labels, to_screen)

        r = 4
        for key_id, val in current_person_labels.items():
            if not isinstance(val, (list, tuple)) or len(val) < 2: continue
            if val[0] == -1: continue

            raw_x, raw_y = val[0], val[1]
            kx = to_screen(raw_x)
            ky = to_screen(raw_y)

            kv = val[2] if len(val) > 2 else -1
            flex = val[3] if len(val) > 3 else -1
            is_skip = val[4] if len(val) > 4 else False

            color = Config.COLORS.get(key_id, 'white')
            draw.ellipse([kx - r, ky - r, kx + r, ky + r], fill=color, outline='black', width=1)

            label_text = str(kv)
            if key_id in Config.PROSTHETIC_IDS:
                f_str = "Fix" if flex == 0 else "Free" if flex == 1 else "?"
                if flex != -1: label_text += f"\n{f_str}"
            if is_skip:
                label_text += "\n[S]"

            draw.text((kx + r + 2, ky - r), label_text, fill=color, stroke_fill="black", stroke_width=1)

        return ImageTk.PhotoImage(img)

    def _draw_static_points(self, draw, kps_dict, to_screen_func, show_res, show_pro):
        r = 3
        for kid_str, val in kps_dict.items():
            kid = int(kid_str)
            is_res = kid in Config.UPPER_RESIDUAL_IDS or (1 <= kid <= 8)
            is_pro = kid in Config.PROSTHETIC_IDS

            if is_res and not show_res: continue
            if is_pro and not show_pro: continue

            if not isinstance(val, (list, tuple)) or len(val) < 2: continue
            if val[0] == -1: continue

            x, y = to_screen_func(val[0]), to_screen_func(val[1])
            draw.ellipse([x - r, y - r, x + r, y + r], fill=Config.R1_COLOR, outline='white')

    def _draw_prosthetic_connections(self, draw, labels_map, to_screen_func):
        connection_color = '#00FFFF'
        line_width = 2
        for start_id, end_id in Config.PROSTHETIC_CONNECTIONS:
            if start_id not in labels_map or end_id not in labels_map: continue
            pt1_data = labels_map[start_id]
            pt2_data = labels_map[end_id]
            if not isinstance(pt1_data, (list, tuple)) or len(pt1_data) < 2 or pt1_data[0] == -1: continue
            if not isinstance(pt2_data, (list, tuple)) or len(pt2_data) < 2 or pt2_data[0] == -1: continue
            x1, y1 = to_screen_func(pt1_data[0]), to_screen_func(pt1_data[1])
            x2, y2 = to_screen_func(pt2_data[0]), to_screen_func(pt2_data[1])
            draw.line([(x1, y1), (x2, y2)], fill=connection_color, width=line_width)

    def _draw_coco_keypoints(self, draw, ann, to_screen_func):
        kps = ann.get("keypoints", [])
        if not kps: return

        def get_kp(index):
            idx = index * 3
            if idx + 2 < len(kps): return kps[idx], kps[idx + 1], kps[idx + 2]
            return 0, 0, 0

        for i_start, i_end in Config.COCO_SKELETON:
            rx1, ry1, v1 = get_kp(i_start)
            rx2, ry2, v2 = get_kp(i_end)
            x1, y1 = to_screen_func(rx1), to_screen_func(ry1)
            x2, y2 = to_screen_func(rx2), to_screen_func(ry2)
            if v1 > 0 and v2 > 0: draw.line([(x1, y1), (x2, y2)], fill='black', width=2)
        r = 3
        for i in range(17):
            rx, ry, v = get_kp(i)
            if v > 0:
                x, y = to_screen_func(rx), to_screen_func(ry)
                draw.ellipse([x - r, y - r, x + r, y + r], fill='black', outline=None)
                if i in Config.COCO_LEFT_SIDE:
                    draw.text((x + 5, y - 5), "L", fill="black")
                elif i in Config.COCO_RIGHT_SIDE:
                    draw.text((x + 5, y - 5), "R", fill="black")

    def _draw_extra_keypoints(self, draw, ann, to_screen_func):
        kps = ann.get("keypoints", [])
        if not kps: return

        def get_kp(index):
            idx = index * 3
            if idx + 2 < len(kps): return kps[idx], kps[idx + 1], kps[idx + 2]
            return 0, 0, 0

        r = 4
        for i in range(17, 25):
            rx, ry, v = get_kp(i)
            if v > 0:
                x, y = to_screen_func(rx), to_screen_func(ry)
                draw.ellipse([x - r, y - r, x + r, y + r], fill='#00BFFF', outline='white')
                draw.text((x + 5, y - 5), f"E{i}", fill="#00BFFF")


class ProsthesisLabelerApp:
    def __init__(self, master):
        self.master = master
        self.master.title("LD-Prosthesis Labeler - Round 2 Mode")
        self.master.geometry(f"{Config.WINDOW_WIDTH}x{Config.WINDOW_HEIGHT}")
        self.data_manager = DataManager()
        self.visualizer = ImageVisualizer()
        self.current_img_index = 0
        self.selected_ann_index = 0
        self.selected_keypoint_id = -1
        self.runtime_labels = {}
        self.scale = 1.0

        self.raw_image = None
        self.display_image = None

        # View States
        self.show_coco_var = tk.BooleanVar(value=False)
        self.show_extra_var = tk.BooleanVar(value=False)
        self.show_bbox_var = tk.BooleanVar(value=True)
        self.show_connection_var = tk.BooleanVar(value=True)

        # [NEW] Round 1 显示开关
        self.show_r1_res_var = tk.BooleanVar(value=False)
        self.show_r1_pro_var = tk.BooleanVar(value=False)

        # [NEW] 废弃标记开关
        self.is_discarded_var = tk.BooleanVar(value=False)

        # 1. 初始化路径 (现在包含 Round 1 文件)
        if not self._init_paths():
            self.master.destroy()
            return

        if HF_AVAILABLE:
            self._sync_from_cloud_on_startup()

        if not self.data_manager.load_data():
            messagebox.showerror("Error", "Unable to load data files.")
            self.master.destroy()
            return

        self.current_img_index = self.data_manager.get_next_todo_index()
        self._setup_ui()

        # Shortcuts
        self.master.bind("w", lambda event: self._move_list_selection(-1))
        self.master.bind("s", lambda event: self._move_list_selection(1))
        self.master.bind("a", lambda event: self._prev_image())
        self.master.bind("d", lambda event: self._next_image())
        self.master.protocol("WM_DELETE_WINDOW", self._on_close_window)
        self.master.after(100, self._load_current_image)

    def _sync_from_cloud_on_startup(self):
        if not HF_AVAILABLE: return
        target_filename = self.data_manager.output_label_path.name
        msg = f"Download latest '{target_filename}' from Cloud?\n(Repo: {Config.HF_REPO_ID})\nWARNING: Overwrites local {target_filename}"
        if not messagebox.askyesno("Cloud Sync Check", msg): return
        try:
            loading_win = tk.Toplevel(self.master)
            loading_win.title("Downloading...")
            tk.Label(loading_win, text=f"Downloading {target_filename}...", pady=20).pack()
            self.master.update()
            cached_file_path = hf_hub_download(repo_id=Config.HF_REPO_ID, filename=target_filename, repo_type="dataset")
            shutil.copy(cached_file_path, self.data_manager.output_label_path)
            loading_win.destroy()
            messagebox.showinfo("Success", f"Synced {target_filename} successfully!")
        except Exception as e:
            messagebox.showerror("Sync Error", f"Failed to download: {e}")

    def _upload_to_hf(self):
        if not HF_AVAILABLE: return
        if not self.data_manager.output_label_path: return
        try:
            self.master.after(0, lambda: self.info_var.set("Syncing to Cloud..."))
            target_filename = self.data_manager.output_label_path.name
            print(f"Uploading {target_filename}...")
            upload_file(
                path_or_fileobj=str(self.data_manager.output_label_path),
                path_in_repo=target_filename,
                repo_id=Config.HF_REPO_ID,
                repo_type="dataset",
                commit_message=f"R2 Sync {target_filename}: {self.counter_var.get()}"
            )
            self.master.after(0, lambda: messagebox.showinfo("Success", f"Upload {target_filename} Completed!"))
            self.master.after(0, lambda: self.info_var.set(f"Sync Complete (Last saved: {self.counter_var.get()})"))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Error", f"Upload Failed: {e}"))
            self.master.after(0, lambda: self.info_var.set("Sync Failed"))

    def _start_upload_thread(self):
        if not self._save_current(sync=True): return
        t = threading.Thread(target=self._upload_to_hf)
        t.daemon = True
        t.start()

    def _on_close_window(self):
        self._save_current(sync=True)
        if HF_AVAILABLE:
            if messagebox.askyesno("Exit", "Upload to Hugging Face before exiting?"):
                try:
                    self.info_var.set("Uploading...")
                    self.master.update()
                    upload_file(
                        path_or_fileobj=str(self.data_manager.output_label_path),
                        path_in_repo=self.data_manager.output_label_path.name,
                        repo_id=Config.HF_REPO_ID,
                        repo_type="dataset",
                        commit_message="Final sync on exit"
                    )
                except Exception as e:
                    messagebox.showerror("Error", f"Upload failed: {e}")
        self.master.destroy()

    def _init_paths(self):
        # 1. Base JSON
        ld_path = filedialog.askopenfilename(title="1. Select Base LDPose Annotation (.json)",
                                             filetypes=[("JSON", "*.json")], initialdir='./ldpose_final/annotations')
        if not ld_path: return False

        # 2. [NEW] Round 1 JSON
        r1_path = filedialog.askopenfilename(title="2. Select ROUND 1 Result (.json)",
                                             filetypes=[("JSON", "*.json")], initialdir='./')
        if not r1_path:
            if not messagebox.askyesno("Warning", "No Round 1 file selected. Start without Round 1 data copy?"):
                return False
            # 允许为空，但功能受限
            r1_path = None

        # 3. Output JSON
        out_path = filedialog.asksaveasfilename(title="3. Save ROUND 2 Label File", initialfile="labels_round2.json",
                                                defaultextension=".json", initialdir='./')
        if not out_path: return False

        # 4. Images
        img_dir = filedialog.askdirectory(title="4. Select Image Directory", initialdir='./ldpose_final')
        if not img_dir: return False

        if not Path(out_path).exists():
            with open(out_path, "w", encoding="utf-8") as f: json.dump({"images": [], "annotations": []}, f)

        self.data_manager.set_paths(Path(ld_path), Path(r1_path) if r1_path else None, Path(out_path), Path(img_dir))
        return True

    def _move_list_selection(self, step):
        size = self.ann_listbox.size()
        if size == 0: return
        current_sel = self.ann_listbox.curselection()
        target_idx = 0 if not current_sel else current_sel[0] + step
        if target_idx < 0: target_idx = 0
        if target_idx >= size: target_idx = size - 1
        if not current_sel or target_idx != current_sel[0]:
            self.ann_listbox.selection_clear(0, tk.END)
            self.ann_listbox.selection_set(target_idx)
            self.ann_listbox.see(target_idx)
            self._on_ann_list_select(None)

    def _setup_ui(self):
        paned = tk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        left_frame = tk.Frame(paned, width=250, bg="#f0f0f0")
        paned.add(left_frame)
        tk.Label(left_frame, text="Annotations List", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(pady=5)
        list_frame = tk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.ann_listbox = tk.Listbox(list_frame, font=("Arial", 10), selectmode=tk.SINGLE)
        self.ann_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.ann_listbox.bind("<<ListboxSelect>>", self._on_ann_list_select)
        sb = tk.Scrollbar(list_frame, command=self.ann_listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.ann_listbox.config(yscrollcommand=sb.set)

        right_frame = tk.Frame(paned)
        paned.add(right_frame)
        controls_frame = tk.Frame(right_frame, bd=1, relief=tk.RAISED)
        controls_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.info_var = tk.StringVar()
        self.counter_var = tk.StringVar()
        self._setup_control_buttons(controls_frame)

        image_container = tk.Frame(right_frame, bg="gray")
        image_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(image_container, bg="#404040")
        v_scroll = tk.Scrollbar(image_container, orient=tk.VERTICAL, command=self.canvas.yview)
        h_scroll = tk.Scrollbar(image_container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.image_label = tk.Label(self.canvas, bd=0, highlightthickness=0)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.image_label, anchor="nw")

        self.image_label.bind("<Button-1>", self._on_canvas_click)
        self.image_label.bind('<Enter>', self._bound_to_mousewheel)
        self.canvas.bind('<Enter>', self._bound_to_mousewheel)
        self.image_label.bind('<Leave>', self._unbound_to_mousewheel)
        self.canvas.bind('<Leave>', self._unbound_to_mousewheel)
        self.image_label.bind("<Configure>", self._on_image_resize)

    def _bound_to_mousewheel(self, event):
        self.canvas.focus_set()
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbound_to_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        state = event.state
        alt_pressed = (state & 8) or (state & 0x20000)
        ctrl_pressed = (state & 4)
        if alt_pressed or ctrl_pressed:
            if event.num == 4 or event.delta > 0:
                self._zoom_image(1.1)
            elif event.num == 5 or event.delta < 0:
                self._zoom_image(0.9)
        else:
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")
            else:
                delta = int(-1 * (event.delta / 120))
                self.canvas.yview_scroll(delta, "units")

    def _zoom_image(self, factor):
        new_scale = self.scale * factor
        if new_scale < 0.1: new_scale = 0.1
        if new_scale > 5.0: new_scale = 5.0
        self.scale = new_scale
        self._update_display_image_cache()
        self._refresh_canvas()

    def _on_image_resize(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _setup_control_buttons(self, parent):
        kp_panel = tk.Frame(parent, bd=1, relief=tk.SUNKEN)
        kp_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        for i in range(6):
            kp_panel.columnconfigure(i, weight=1)
        for i in range(4):
            kp_panel.rowconfigure(i, weight=1)
        for r, row_ids in enumerate(Config.BUTTON_LAYOUT):
            for c, kp_id in enumerate(row_ids):
                if kp_id is None:
                    tk.Label(kp_panel, text="", width=10).grid(row=r, column=c)
                    continue
                name = Config.SHORT_NAMES.get(kp_id, Config.KEYPOINTS.get(kp_id, "UNK"))
                color = Config.COLORS.get(kp_id, 'black')
                btn_bg = "#e1f5fe" if kp_id >= 17 else "#f9f9f9"

                tk.Button(kp_panel, text=name, fg=color, font=("Arial", 8, "bold"),
                          width=10, height=3, bg=btn_bg,
                          wraplength=80, command=lambda k=kp_id: self._set_tool_keypoint(k)).grid(
                    row=r, column=c, padx=2, pady=2, sticky="nsew")

        tools_panel = tk.Frame(parent)
        tools_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        info_frame = tk.Frame(tools_panel)
        info_frame.pack(fill=tk.X, pady=5)
        tk.Label(info_frame, textvariable=self.info_var, font=("Arial", 10)).pack(side=tk.LEFT)
        tk.Label(info_frame, textvariable=self.counter_var, font=("Arial", 11, "bold"), fg="blue").pack(side=tk.RIGHT)
        tk.Frame(tools_panel, height=2, bd=1, relief=tk.GROOVE).pack(fill=tk.X, pady=5)

        status_frame = tk.Frame(tools_panel)
        status_frame.pack(fill=tk.X, pady=2)
        self.btn_discard = tk.Button(status_frame, text="标记废弃 (Mark as Bad)", command=self._toggle_discard,
                                     bg="#fff0f0")
        self.btn_discard.pack(side=tk.LEFT, fill=tk.X, expand=True)

        attr_frame = tk.Frame(tools_panel)
        attr_frame.pack(fill=tk.X, pady=5)
        tk.Label(attr_frame, text="Vis:").pack(side=tk.LEFT)
        tk.Button(attr_frame, text="Occ(1)", width=5, command=lambda: self._set_tool_vis(1)).pack(side=tk.LEFT, padx=2)
        tk.Button(attr_frame, text="Vis(2)", width=5, command=lambda: self._set_tool_vis(2)).pack(side=tk.LEFT, padx=2)
        tk.Label(attr_frame, text="| Flex:").pack(side=tk.LEFT, padx=5)
        tk.Button(attr_frame, text="Fix(0)", width=5, command=lambda: self._set_attr_flex(0)).pack(side=tk.LEFT, padx=2)
        tk.Button(attr_frame, text="Free(1)", width=5, command=lambda: self._set_attr_flex(1)).pack(side=tk.LEFT,
                                                                                                    padx=2)

        self.skip_joint_var = tk.BooleanVar(value=False)
        self.chk_skip_joint = tk.Checkbutton(
            attr_frame, text="Skip Knee/Elbow", variable=self.skip_joint_var,
            command=self._on_skip_toggle, fg="red", font=("Arial", 9, "bold")
        )

        tk.Button(attr_frame, text="Clear", bg="#ffcccc", command=self._clear_current_point).pack(side=tk.RIGHT, padx=5)

        # Toggle Frame
        toggle_frame = tk.Frame(tools_panel)
        toggle_frame.pack(fill=tk.X, pady=5)

        # Row 1 (Original)
        row1 = tk.Frame(toggle_frame)
        row1.pack(fill=tk.X, expand=True)
        self.btn_toggle_coco = tk.Button(row1, text="显示原始 COCO", command=self._toggle_coco_display)
        self.btn_toggle_coco.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.btn_toggle_extra = tk.Button(row1, text="显示 R2 残肢/假肢 (当前)", state=tk.DISABLED, relief="sunken",
                                          bg="#ddffdd")
        self.btn_toggle_extra.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)  # 占位或提示

        # Row 2 (BBox / Conn)
        row2 = tk.Frame(toggle_frame)
        row2.pack(fill=tk.X, expand=True, pady=2)
        self.btn_toggle_bbox = tk.Button(row2, text="隐藏 BBox", relief="sunken", bg="#FFCCCB",
                                         command=self._toggle_bbox_display)
        self.btn_toggle_bbox.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.btn_toggle_conn = tk.Button(row2, text="隐藏假肢连线", relief="sunken", bg="#E0FFFF",
                                         command=self._toggle_connection_display)
        self.btn_toggle_conn.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        # [NEW] Row 3 (Round 1 Toggles)
        row3 = tk.Frame(toggle_frame)
        row3.pack(fill=tk.X, expand=True, pady=2)
        self.btn_r1_res = tk.Button(row3, text="显示 R1 残肢 (旧)", command=lambda: self._toggle_r1_display('res'))
        self.btn_r1_res.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.btn_r1_pro = tk.Button(row3, text="显示 R1 假肢 (旧)", command=lambda: self._toggle_r1_display('pro'))
        self.btn_r1_pro.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        self.default_btn_bg = self.btn_toggle_coco.cget("bg")

        search_frame = tk.Frame(tools_panel)
        search_frame.pack(fill=tk.X, pady=5)
        tk.Label(search_frame, text="跳转 Index:", font=("Arial", 10)).pack(side=tk.LEFT)
        self.entry_search = tk.Entry(search_frame, width=8, font=("Arial", 10))
        self.entry_search.pack(side=tk.LEFT, padx=5)
        self.entry_search.bind("<Return>", self._on_search_index)
        tk.Button(search_frame, text="Go", command=self._on_search_index, height=1).pack(side=tk.LEFT)

        nav_frame = tk.Frame(tools_panel)
        nav_frame.pack(fill=tk.X, pady=5)
        tk.Button(nav_frame, text="< Previous", height=2, command=self._prev_image).pack(side=tk.LEFT, fill=tk.X,
                                                                                         expand=True, padx=20)
        tk.Button(nav_frame, text="Next >", height=2, bg="#ddffdd", command=self._next_image).pack(side=tk.LEFT,
                                                                                                   fill=tk.X,
                                                                                                   expand=True, padx=20)

        if HF_AVAILABLE:
            sync_frame = tk.Frame(tools_panel)
            sync_frame.pack(fill=tk.X, pady=10)
            self.btn_upload = tk.Button(
                sync_frame, text="☁️ Sync Round 2 to HuggingFace",
                bg="#007bff", fg="white", font=("Arial", 10, "bold"),
                command=self._start_upload_thread
            )
            self.btn_upload.pack(fill=tk.X, ipady=5)


    def _toggle_discard(self):
        new_val = not self.is_discarded_var.get()
        self.is_discarded_var.set(new_val)
        self._update_discard_btn_visual()
        self._refresh_canvas()

    def _update_discard_btn_visual(self):
        if self.is_discarded_var.get():
            self.btn_discard.config(text="[已废弃] 恢复正常", bg="red", fg="white", relief="sunken")
        else:
            self.btn_discard.config(text="标记废弃 (Mark as Bad)", bg="#fff0f0", fg="black", relief="raised")

    def _on_search_index(self, event=None):
        val = self.entry_search.get().strip()
        if not val: return
        try:
            target_idx = int(val) - 1
        except ValueError:
            messagebox.showerror("Error", "请输入有效的数字")
            return
        if target_idx < 0 or target_idx >= len(self.data_manager.all_image_ids):
            messagebox.showerror("Error", f"索引超出范围。")
            return
        if not self._save_current(): return
        self.current_img_index = target_idx
        self._load_current_image()

    def _on_skip_toggle(self):
        if self.selected_keypoint_id not in Config.UPPER_RESIDUAL_IDS: return
        if self.selected_ann_index not in self.runtime_labels:
            self.runtime_labels[self.selected_ann_index] = defaultdict(lambda: [-1, -1, -1, -1, False])
        point_data = self.runtime_labels[self.selected_ann_index][self.selected_keypoint_id]
        while len(point_data) < 5: point_data.append(False)
        point_data[4] = self.skip_joint_var.get()
        self._refresh_canvas()

    def _toggle_bbox_display(self):
        new_val = not self.show_bbox_var.get()
        self.show_bbox_var.set(new_val)
        self.btn_toggle_bbox.config(text="隐藏 BBox" if new_val else "显示 BBox",
                                    relief="sunken" if new_val else "raised",
                                    bg="#FFCCCB" if new_val else self.default_btn_bg)
        self._refresh_canvas()

    def _toggle_connection_display(self):
        new_val = not self.show_connection_var.get()
        self.show_connection_var.set(new_val)
        self.btn_toggle_conn.config(text="隐藏假肢连线" if new_val else "显示假肢连线",
                                    relief="sunken" if new_val else "raised",
                                    bg="#E0FFFF" if new_val else self.default_btn_bg)
        self._refresh_canvas()

    def _toggle_coco_display(self):
        new_val = not self.show_coco_var.get()
        self.show_coco_var.set(new_val)
        self.btn_toggle_coco.config(text="隐藏 COCO" if new_val else "显示 COCO",
                                    relief="sunken" if new_val else "raised",
                                    bg="#ddd" if new_val else self.default_btn_bg)
        self._refresh_canvas()

    # [NEW] Round 1 显示切换
    def _toggle_r1_display(self, mode):
        if mode == 'res':
            new_val = not self.show_r1_res_var.get()
            self.show_r1_res_var.set(new_val)
            self.btn_r1_res.config(relief="sunken" if new_val else "raised",
                                   bg="#D3D3D3" if new_val else self.default_btn_bg)
        elif mode == 'pro':
            new_val = not self.show_r1_pro_var.get()
            self.show_r1_pro_var.set(new_val)
            self.btn_r1_pro.config(relief="sunken" if new_val else "raised",
                                   bg="#D3D3D3" if new_val else self.default_btn_bg)
        self._refresh_canvas()

    def _set_attr_flex(self, val):
        if self.selected_keypoint_id < 0: return
        if self.selected_keypoint_id >= 17:
            messagebox.showinfo("提示", f"端点 (End) 不需要设置活动性属性。")
            return
        if self.selected_keypoint_id <= 8:
            messagebox.showwarning("Warning", "Flexibility setting not needed for residual limbs")
            return
        if self.selected_ann_index not in self.runtime_labels:
            self.runtime_labels[self.selected_ann_index] = defaultdict(lambda: [-1, -1, -1, -1])
        data = self.runtime_labels[self.selected_ann_index][self.selected_keypoint_id]
        while len(data) < 4: data.append(-1)
        data[3] = val
        self._refresh_canvas()

    def _load_current_image(self):
        ctx = self.data_manager.get_image_context(self.current_img_index)
        if not ctx:
            messagebox.showinfo("Done", "No more images.")
            return

        self.runtime_labels = {}
        self.selected_keypoint_id = -1
        self.selected_ann_index = 0

        # [NEW] 初始化逻辑：Round 2 保存过 > Round 1 备份 > 新建
        self._reconstruct_runtime_state(ctx)

        # [NEW] 恢复废弃状态
        is_disc = ctx.get("is_discarded", False)
        self.is_discarded_var.set(is_disc)
        self._update_discard_btn_visual()

        # Update Listbox
        self.ann_listbox.delete(0, tk.END)
        ld_anns = ctx['ld_anns']
        if ld_anns:
            for idx, ann in enumerate(ld_anns):
                self.ann_listbox.insert(tk.END, f"#{idx} - ID:{ann.get('id')} (Cat:{ann.get('category_id')})")
            self.ann_listbox.selection_set(0)
        else:
            self.ann_listbox.insert(tk.END, "No Annotations (New)")
            if 0 not in self.runtime_labels: self.runtime_labels[0] = defaultdict(lambda: [-1, -1, -1, -1, False])

        rel_path = ctx['full_path'].relative_to(self.data_manager.image_dir).as_posix()
        self.info_var.set(f"{ctx['index_str']} : {rel_path}")
        self._update_counter()

        try:
            self.raw_image = Image.open(ctx['full_path']).convert("RGB")
            self.raw_image = ImageOps.exif_transpose(self.raw_image)

            img_w, img_h = self.raw_image.size
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            if canvas_w < 50: canvas_w = 800
            if canvas_h < 50: canvas_h = 600
            scale_w = canvas_w / img_w
            scale_h = canvas_h / img_h
            self.scale = min(scale_w, scale_h, 1.0)

            self._update_display_image_cache()

        except Exception as e:
            print(f"Error loading image: {e}")
            self.raw_image = None
            self.display_image = None

        self._refresh_canvas()

    def _update_display_image_cache(self):
        if self.raw_image is None: return
        new_w = int(self.raw_image.width * self.scale)
        new_h = int(self.raw_image.height * self.scale)
        self.display_image = self.raw_image.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # [IMPORTANT] 重构状态的核心逻辑
    def _reconstruct_runtime_state(self, ctx):
        saved_anns = ctx['saved_anns']  # Round 2
        r1_anns = ctx['r1_anns']  # Round 1
        ld_anns = ctx['ld_anns']

        # 1. 优先检查是否有已经保存的 Round 2 数据
        source_anns = []
        is_from_round2 = False

        if saved_anns:
            source_anns = saved_anns
            is_from_round2 = True
        elif r1_anns:
            # 2. 如果没有 Round 2 数据，自动复制 Round 1 数据作为起点
            source_anns = r1_anns
            is_from_round2 = False

        # 建立映射辅助
        id_to_idx = {ann['id']: i for i, ann in enumerate(ld_anns)}

        for s_ann in source_anns:
            if "new_keypoints" not in s_ann: continue

            # 找到对应的 person index
            target_idx = None
            if s_ann.get('id') in id_to_idx:
                target_idx = id_to_idx[s_ann['id']]
            elif not ld_anns:
                target_idx = 0

            if target_idx is not None:
                # 深度复制数据，因为接下来我们要修改它
                recovered_data = defaultdict(lambda: [-1, -1, -1, -1, False])
                source_kps = s_ann["new_keypoints"]

                for k, v in source_kps.items():
                    kp_id = int(k)

                    # [MODIFIED] 如果是从 Round 1 复制而来，过滤掉非假肢点（即不复制残肢点）
                    if not is_from_round2:
                        if kp_id not in Config.PROSTHETIC_IDS:
                            continue

                    # 确保是列表且深度拷贝，避免引用同一个对象
                    val_list = list(copy.deepcopy(v))
                    if not val_list or val_list[0] == -1: continue
                    while len(val_list) < 5: val_list.append(False if len(val_list) == 4 else -1)
                    recovered_data[kp_id] = val_list

                self.runtime_labels[target_idx] = recovered_data

        # 确保选中项初始化
        if self.selected_ann_index not in self.runtime_labels:
            self.runtime_labels[self.selected_ann_index] = defaultdict(lambda: [-1, -1, -1, -1, False])

    def _refresh_canvas(self):
        ctx = self.data_manager.get_image_context(self.current_img_index)
        if not ctx: return

        # 获取当前图的 Round 1 原始数据，传给 visualizer 做 Ghost 显示
        r1_anns_list = ctx['r1_anns']

        tk_img = self.visualizer.render(
            self.display_image,
            ctx['ld_anns'], self.selected_ann_index, self.runtime_labels,
            r1_anns_map=r1_anns_list,
            show_coco_kps=self.show_coco_var.get(),
            show_extra_kps=self.show_extra_var.get(),
            show_bbox=self.show_bbox_var.get(),
            show_connections=self.show_connection_var.get(),
            show_r1_res=self.show_r1_res_var.get(),
            show_r1_pro=self.show_r1_pro_var.get(),
            is_discarded=self.is_discarded_var.get(),  # [NEW]
            scale=self.scale
        )
        if tk_img:
            self.tk_img_ref = tk_img
            self.image_label.config(image=tk_img)

    def _prune_garbage(self):
        for ann_idx in list(self.runtime_labels.keys()):
            person_labels = self.runtime_labels[ann_idx]
            keys_to_delete = [k for k, v in person_labels.items() if isinstance(v, list) and len(v) > 0 and v[0] == -1]
            for k in keys_to_delete: del person_labels[k]

    def _validate_before_save(self):
        # [NEW] 如果被标记为废弃，跳过校验，允许直接保存
        if self.is_discarded_var.get():
            return True

        self._prune_garbage()

        for ann_idx, kps in self.runtime_labels.items():
            for kp_id, val in kps.items():
                kp_name = Config.KEYPOINTS.get(kp_id, f"ID {kp_id}")
                vis = val[2] if len(val) > 2 else -1
                if vis == -1:
                    messagebox.showerror("Validation Error", f"#{ann_idx} {kp_name}: Please set Visibility (Vis).")
                    return False
                if kp_id in Config.PROSTHETIC_IDS:
                    flex = val[3] if len(val) > 3 else -1
                    if flex == -1:
                        messagebox.showerror("Validation Error", f"#{ann_idx} {kp_name}: Set 'Flex' for prosthetic.")
                        return False

        return True

    def _save_current(self, sync=False):
        if not self._validate_before_save(): return False
        ctx = self.data_manager.get_image_context(self.current_img_index)
        if not ctx: return True
        count = self.data_manager.save_annotation_result(
            ctx['id'],
            self.runtime_labels,
            is_marked_deleted=self.is_discarded_var.get(),  # [NEW]
            sync=sync
        )
        self._update_counter(saved_count=count)
        return True

    def _update_counter(self, saved_count=None):
        if saved_count is None: saved_count = len(self.data_manager.finished_ids)
        self.counter_var.set(f"Saved (R2): {saved_count}")

    def _on_ann_list_select(self, event):
        sel = self.ann_listbox.curselection()
        if sel:
            idx = sel[0]
            if idx != self.selected_ann_index:
                self.selected_ann_index = idx
                if idx not in self.runtime_labels: self.runtime_labels[idx] = defaultdict(
                    lambda: [-1, -1, -1, -1, False])
                self._refresh_canvas()

    def _on_canvas_click(self, event):
        if self.selected_keypoint_id < 0:
            messagebox.showwarning("Tip", "Select a keypoint button first.")
            return

        if self.selected_ann_index not in self.runtime_labels:
            self.runtime_labels[self.selected_ann_index] = defaultdict(lambda: [-1, -1, -1, -1, False])

        current_points = self.runtime_labels[self.selected_ann_index]

        real_x = int(event.x / self.scale)
        real_y = int(event.y / self.scale)

        # 正常赋值或更新
        if self.selected_keypoint_id not in current_points:
            default_flex = 0 if self.selected_keypoint_id >= 17 else -1
            current_points[self.selected_keypoint_id] = [real_x, real_y, -1, default_flex, False]
        else:
            current_points[self.selected_keypoint_id][0] = real_x
            current_points[self.selected_keypoint_id][1] = real_y

        self._refresh_canvas()

    def _set_tool_keypoint(self, kp_id):
        # 1. 设置当前选中的工具 ID
        self.selected_keypoint_id = kp_id

        # 2. 检查当前标注中是否有与之互斥的点 (11<->17, 12<->18, 15<->19, 16<->20)
        exclusive_id = None
        if kp_id in Config.MUTUAL_EXCLUSIVE_PAIRS:
            exclusive_id = Config.MUTUAL_EXCLUSIVE_PAIRS[kp_id]
        elif kp_id in Config.REVERSE_MUTUAL_PAIRS:
            exclusive_id = Config.REVERSE_MUTUAL_PAIRS[kp_id]

        # 3. 如果互斥点存在，立即执行“静默转换”
        if exclusive_id and self.selected_ann_index in self.runtime_labels:
            current_points = self.runtime_labels[self.selected_ann_index]

            # 只有当旧点确实存在坐标时才转换
            if exclusive_id in current_points and current_points[exclusive_id][0] != -1:
                old_data = list(copy.deepcopy(current_points[exclusive_id]))

                # 转换属性适配
                if kp_id >= 17:  # 如果切到端点
                    if old_data[3] == -1: old_data[3] = 0
                else:  # 如果切回关节
                    old_data[3] = -1

                # 偷梁换柱
                del current_points[exclusive_id]
                current_points[kp_id] = old_data

                # 转换完直接刷新画布，此时你会看到点变色了
                self._refresh_canvas()

        # 4. 原有的控制逻辑 (处理残肢 Skip 按钮的显示/隐藏)
        if kp_id in Config.UPPER_RESIDUAL_IDS:
            self.chk_skip_joint.pack(side=tk.LEFT, padx=10)
            is_skip = False
            if self.selected_ann_index in self.runtime_labels:
                data = self.runtime_labels[self.selected_ann_index].get(kp_id, [])
                if len(data) > 4: is_skip = data[4]
            self.skip_joint_var.set(is_skip)
        else:
            self.chk_skip_joint.pack_forget()

    def _set_tool_vis(self, vis):
        if self.selected_keypoint_id < 0:
            messagebox.showwarning("Tip", "Please select a keypoint.")
            return
        if self.selected_ann_index not in self.runtime_labels:
            self.runtime_labels[self.selected_ann_index] = defaultdict(lambda: [-1, -1, -1, -1, False])
        self.runtime_labels[self.selected_ann_index][self.selected_keypoint_id][2] = vis
        self._refresh_canvas()

    def _clear_current_point(self):
        if self.selected_ann_index in self.runtime_labels:
            if self.selected_keypoint_id in self.runtime_labels[self.selected_ann_index]:
                del self.runtime_labels[self.selected_ann_index][self.selected_keypoint_id]
                self._refresh_canvas()

    def _prev_image(self):
        if not self._save_current(): return
        if self.current_img_index > 0:
            self.current_img_index -= 1
            self._load_current_image()
        else:
            messagebox.showinfo("Tip", "Already the first image.")

    def _next_image(self):
        if not self._save_current(): return
        if self.current_img_index < len(self.data_manager.all_image_ids) - 1:
            self.current_img_index += 1
            self._load_current_image()
        else:
            messagebox.showinfo("Tip", "Already the last image.")


def main():
    root = tk.Tk()
    app = ProsthesisLabelerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()