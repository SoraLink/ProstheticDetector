import json
import os
import tkinter as tk
from tkinter import messagebox, filedialog
from collections import defaultdict
from pathlib import Path
from typing import List, Tuple, Dict

from PIL import Image, ImageTk, ImageDraw


class Config:
    """
    Config class. Set window size, keypoint name and colors for anaotation display
    """
    WINDOW_WIDTH = 1400
    WINDOW_HEIGHT = 900

    KEYPOINTS = {
        # === Upper Body Residuals ===
        1: 'Above left elbow residual limb end',
        2: 'Above right elbow residual limb end',
        3: 'Below left elbow residual limb end',
        4: 'Below right elbow residual limb end',

        # === Lower Body Residuals ===
        5: 'Above left knee residual limb end',
        6: 'Above right knee residual limb end',
        7: 'Below left knee residual limb end',
        8: 'Below right knee residual limb end',

        # === Upper Body Prosthetics ===
        9: 'Left prosthetic elbow',
        10: 'Right prosthetic elbow',
        11: 'Left prosthetic wrist',
        12: 'Right prosthetic wrist',

        # === Lower Body Prosthetics ===
        13: 'Left prosthetic knee',
        14: 'Right prosthetic knee',
        15: 'Left prosthetic ankle',
        16: 'Right prosthetic ankle',
    }

    PROSTHETIC_IDS = {9, 10, 11, 12, 13, 14, 15, 16}

    COLORS = {
        1: '#FF0000', 2: '#00FF00', 3: '#FF00FF', 4: '#00FFFF',
        5: '#A52A2A', 6: '#FFC0CB', 7: '#000080', 8: '#8B4513',
        9: '#0000FF', 10: '#B8860B', 11: '#FFA500', 12: '#800080',
        13: '#808000', 14: '#008080', 15: '#DC143C', 16: '#4B0082',
    }

    BUTTON_LAYOUT = [
        [1, 2, 9, 10],  # Row 1: Above Elbow Res (L/R) | Pros Elbow (L/R)
        [3, 4, 11, 12],  # Row 2: Below Elbow Res (L/R) | Pros Wrist (L/R)
        [5, 6, 13, 14],  # Row 3: Above Knee Res (L/R)  | Pros Knee (L/R)
        [7, 8, 15, 16]  # Row 4: Below Knee Res (L/R)  | Pros Ankle (L/R)
    ]


class DataManager:
    """
    DataManager class to manage any data which will be used in the annotation process or generated during annotation
    processes.
    """

    def __init__(self):
        self.ld_label_path = None
        self.output_label_path = None
        self.image_dir = None

        # core data
        self.all_image_ids = []  # sorted id list to be processed
        self.ld_data_map = {}  # {image_id: (img_info, ld_annotations_list)}
        self.saved_anns_map = defaultdict(list)  # {image_id: [saved_annotations]}
        self.finished_ids = set()

    def set_paths(self, ld_path, out_path, img_dir):
        """
        Setting paths for annotation process.

        Args:
            ld_path: LDpose's annotation path
            out_path: The path to save the new annotation file
            img_dir: The path to read images

        Returns:
            None
        """
        self.ld_label_path = ld_path
        self.output_label_path = out_path
        self.image_dir = img_dir

    def load_data(self):
        """
        Retrieve data from the saved path

        Returns:
            None
        """
        # Load original annotation
        ld_anns, ld_imgs = self._load_json(self.ld_label_path)
        if not ld_imgs:
            return False

        # LD data by id
        self.ld_data_map = {}

        temp_ld_anns = defaultdict(list)
        for ann in ld_anns:
            temp_ld_anns[ann.get("image_id")].append(ann)

        for img in ld_imgs:
            img_id = img['id']
            if img_id in temp_ld_anns:
                self.ld_data_map[img_id] = (img, temp_ld_anns[img_id])

        self.all_image_ids = sorted(list(self.ld_data_map.keys()))

        # Load the saved new annotation to resume
        saved_anns_list, saved_imgs_list = self._load_json(self.output_label_path)
        self.saved_anns_map = defaultdict(list)
        for ann in saved_anns_list:
            self.saved_anns_map[ann['image_id']].append(ann)

        self.finished_ids = {img['id'] for img in (saved_imgs_list or [])}
        return True

    def _load_json(self, path) -> Tuple[List, List]:
        """
        Load annotation from JSON file
        Args:
            path: path to the JSON file

        Returns:
            List of images Infos
            List of Annotations
        """
        if not path or not path.exists():
            return [], []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "annotations" in data:
                return data["annotations"], data.get("images", [])
            return [], []
        except Exception:
            return [], []

    def get_next_todo_index(self) -> int:
        """
        Return the index of the next id

        Returns:
            ID number
        """
        for i, img_id in enumerate(self.all_image_ids):
            if img_id not in self.finished_ids:
                return i
        return len(self.all_image_ids) - 1 if self.all_image_ids else 0

    def get_image_context(self, index: int) -> Dict | None:
        """
        Retrieve all context for an image
        Args:
            index: The ID of an image.

        Returns:
            A dict including id, name, path, LD annotations, previous saved annotations and index string.
        """
        if index < 0 or index >= len(self.all_image_ids):
            return None

        current_id = self.all_image_ids[index]
        img_info, ld_anns = self.ld_data_map[current_id]

        saved_anns = self.saved_anns_map.get(current_id, [])

        return {
            "id": current_id,
            "file_name": img_info['file_name'],
            "full_path": self.image_dir / img_info['file_name'],
            "ld_anns": ld_anns,
            "saved_anns": saved_anns,
            "index_str": f"{index + 1}/{len(self.all_image_ids)}"
        }

    def save_annotation_result(self, current_id, current_labels_map):
        """
        Save the annotation result to the disk
        Args:
            current_id: Image ID
            current_labels_map: The content of Annotation {ann_index: {keypoint_id: [x, y, vis]}}

        Returns:
            The total number of finished annotations
        """
        # 1. Read exist annotation
        try:
            with open(self.output_label_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = {"images": [], "annotations": []}

        images = data.get("images", [])
        annotations = data.get("annotations", [])

        # 2. Filter out the current id's corresponding data
        images = [img for img in images if img['id'] != current_id]
        annotations = [ann for ann in annotations if ann['image_id'] != current_id]

        # 3. Retrieve the LD pose annotation of the id.
        img_info, ld_anns = self.ld_data_map[current_id]

        has_pro = False
        for person_labels in current_labels_map.values():
            if any(v[2] != -1 for v in person_labels.values()):
                has_pro = True
                break

        out_img_info = img_info.copy()
        out_img_info["has_pro"] = has_pro
        images.append(out_img_info)

        # 4. Merge annotation
        new_saved_cache = []

        if ld_anns:
            for idx, ann in enumerate(ld_anns):
                out_ann = ann.copy()
                if idx in current_labels_map:
                    person_labels = current_labels_map[idx]
                    out_ann["new_keypoints"] = dict(person_labels)

                annotations.append(out_ann)
                new_saved_cache.append(out_ann)
        else:
            if 0 in current_labels_map:
                out_ann = {
                    "image_id": current_id,
                    "id": 9000000 + current_id,
                    "new_keypoints": dict(current_labels_map[0])
                }
                annotations.append(out_ann)
                new_saved_cache.append(out_ann)

        # 5. Write to the file
        data["images"] = images
        data["annotations"] = annotations

        with open(self.output_label_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        # 6. Update memory data
        self.finished_ids.add(current_id)
        self.saved_anns_map[current_id] = new_saved_cache

        return len(self.finished_ids)


class ImageVisualizer:
    """
    The ImageVisualizer class response for the
    """

    def render(self, img_path, ld_anns, selected_ann_index, current_labels_map):
        """
        img_path: Image path
        ld_anns: LDpose annotations
        selected_ann_index: The index of the selected annotations
        current_labels_map: The current image's annotation {ann_idx: {kp_id: [x,y,v,conn,flex]}}
        """
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"无法打开图片: {img_path}, Error: {e}")
            return None

        draw = ImageDraw.Draw(img)

        # 1. Draw bbox based on the LDpose annotation
        if ld_anns:
            if 0 <= selected_ann_index < len(ld_anns):
                target_ann = ld_anns[selected_ann_index]
                if "bbox" in target_ann:
                    x, y, w, h = target_ann["bbox"]
                    draw.rectangle([x, y, x + w, y + h], outline="red", width=3)
                    draw.text((x, y - 15), f"ID: {target_ann.get('id')}", fill="red")

        # Drawing the keypoints
        current_person_labels = current_labels_map.get(selected_ann_index, {})

        r = 4
        for key_id, val in current_person_labels.items():
            if not isinstance(val, (list, tuple)) or len(val) < 2:
                continue

            kx, ky = val[0], val[1]

            if kx != -1 and ky != -1:
                kv = val[2] if len(val) > 2 else -1
                conn = val[3] if len(val) > 3 else -1
                flex = val[4] if len(val) > 4 else -1

                color = Config.COLORS.get(key_id, 'white')
                draw.ellipse([kx - r, ky - r, kx + r, ky + r], fill=color, outline='black')

                label_text = str(kv)

                if key_id in Config.PROSTHETIC_IDS:
                    c_str = "H" if conn == 0 else "P" if conn == 1 else "?"
                    f_str = "Fix" if flex == 0 else "Free" if flex == 1 else "?"

                    if conn != -1 or flex != -1:
                        label_text += f"\n{c_str}|{f_str}"

                draw.text((kx + r + 2, ky - r), label_text, fill=color, stroke_fill="black", stroke_width=1)

        return ImageTk.PhotoImage(img)

class ProsthesisLabelerApp:
    def __init__(self, master):
        self.master = master
        self.master.title("LD-Prosthesis Labeler")
        self.master.geometry(f"{Config.WINDOW_WIDTH}x{Config.WINDOW_HEIGHT}")

        self.data_manager = DataManager()
        self.visualizer = ImageVisualizer()

        self.current_img_index = 0
        self.selected_ann_index = 0
        self.selected_keypoint_id = -1

        self.runtime_labels = {}

        if not self._init_paths():
            self.master.destroy()
            return

        if not self.data_manager.load_data():
            messagebox.showerror("错误", "无法加载数据文件。")
            self.master.destroy()
            return

        self.current_img_index = self.data_manager.get_next_todo_index()

        self._setup_ui()

        self._load_current_image()

    def _init_paths(self):
        ld_path = filedialog.askopenfilename(
            title="选择 LDPose annotation (.json)",
            filetypes=[("JSON", "*.json")],
            initialdir='./ldpose_final/annotations'
        )
        if not ld_path: return False

        out_path = filedialog.asksaveasfilename(
            title="保存 labels.json 位置",
            initialfile="labels.json",
            defaultextension=".json",
            initialdir='./'
        )
        if not out_path: return False

        img_dir = filedialog.askdirectory(
            title="选择图片目录",
            initialdir='./ldpose_final'
        )
        if not img_dir: return False

        if not Path(out_path).exists():
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"images": [], "annotations": []}, f)

        self.data_manager.set_paths(Path(ld_path), Path(out_path), Path(img_dir))
        return True

    def _setup_ui(self):
        """
        Set up the UI
        Returns:
            None
        """
        paned = tk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # The left window contain a list of annotations of an image
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

        # The right window contains image and button
        right_frame = tk.Frame(paned)
        paned.add(right_frame)

        self.image_label = tk.Label(right_frame, bd=0, highlightthickness=0)
        self.image_label.pack(expand=True)
        self.image_label.bind("<Button-1>", self._on_canvas_click)

        self.info_var = tk.StringVar()
        tk.Label(right_frame, textvariable=self.info_var).pack(pady=5)

        self.counter_var = tk.StringVar()
        tk.Label(right_frame, textvariable=self.counter_var, font=("Arial", 12)).pack()

        self._setup_control_buttons(right_frame)

    def _setup_control_buttons(self, parent):
        btn_frame = tk.Frame(parent)
        btn_frame.pack(pady=10)

        # 1. Keypoint buttons
        for r, row_ids in enumerate(Config.BUTTON_LAYOUT):
            for c, kp_id in enumerate(row_ids):
                name = Config.KEYPOINTS[kp_id]
                color = Config.COLORS.get(kp_id, 'black')

                tk.Button(
                    btn_frame,
                    text=name,
                    width=35,
                    fg=color,
                    command=lambda k=kp_id: self._set_tool_keypoint(k)
                ).grid(row=r, column=c, padx=5, pady=2)

        # 2. Visibility buttons
        for i in range(3):
            tk.Button(
                btn_frame, text=f"Vis {i}", width=18,
                command=lambda v=i: self._set_tool_vis(v)
            ).grid(row=5, column=i, padx=5, pady=5)

        tk.Label(btn_frame, text="Prev Node:").grid(row=6, column=0, sticky='e')
        conn_frame = tk.Frame(btn_frame)
        conn_frame.grid(row=6, column=1, columnspan=3, sticky='w')
        tk.Button(conn_frame, text="Human (0)", command=lambda: self._set_attr_conn(0)).pack(side=tk.LEFT)
        tk.Button(conn_frame, text="Prosthetic (1)", command=lambda: self._set_attr_conn(1)).pack(side=tk.LEFT)

        tk.Label(btn_frame, text="Flexibility:").grid(row=7, column=0, sticky='e')
        flex_frame = tk.Frame(btn_frame)
        flex_frame.grid(row=7, column=1, columnspan=3, sticky='w')
        tk.Button(flex_frame, text="Fixed (0)", command=lambda: self._set_attr_flex(0)).pack(side=tk.LEFT)
        tk.Button(flex_frame, text="Free (1)", command=lambda: self._set_attr_flex(1)).pack(side=tk.LEFT)

        tk.Button(
            btn_frame,
            text="Clear selected point",
            width=18,
            command=self._clear_current_point
        ).grid(
            row=7,
            column=2,
            pady=10
        )

        nav_frame = tk.Frame(btn_frame)
        nav_frame.grid(row=6, column=2, columnspan=2)
        tk.Button(nav_frame, text="< Previous", width=15, command=self._prev_image).pack(side=tk.LEFT, padx=5)
        tk.Button(nav_frame, text="Next >", width=15, command=self._next_image).pack(side=tk.LEFT, padx=5)

        # 插入在 _set_tool_vis 下面
    def _set_attr_conn(self, val):
        if self.selected_keypoint_id < 0: return
        if self.selected_keypoint_id <= 8:
            messagebox.showwarning("提示", "人体残肢点不需要设置连接属性")
            return

        if self.selected_ann_index not in self.runtime_labels:
            self.runtime_labels[self.selected_ann_index] = defaultdict(lambda: [-1, -1, -1, -1, -1])  # 注意这里维度变长了

        data = self.runtime_labels[self.selected_ann_index][self.selected_keypoint_id]
        while len(data) < 5: data.append(-1)

        data[3] = val
        self._refresh_canvas()

    def _set_attr_flex(self, val):
        if self.selected_keypoint_id < 0: return
        if self.selected_keypoint_id <= 8:
            messagebox.showwarning("提示", "人体残肢点不需要设置自由度")
            return

        if self.selected_ann_index not in self.runtime_labels:
            self.runtime_labels[self.selected_ann_index] = defaultdict(lambda: [-1, -1, -1, -1, -1])

        data = self.runtime_labels[self.selected_ann_index][self.selected_keypoint_id]
        while len(data) < 5: data.append(-1)

        data[4] = val  # 第5位存自由度
        self._refresh_canvas()

    def _load_current_image(self):
        """
        Load the current image
        Returns:
            None
        """
        ctx = self.data_manager.get_image_context(self.current_img_index)
        if not ctx:
            messagebox.showinfo("完成", "没有更多图片或索引越界。")
            return

        # 1. Reset params
        self.runtime_labels = {}
        self.selected_keypoint_id = -1
        self.selected_ann_index = 0

        # 2. Restore the annotation
        self._reconstruct_runtime_state(ctx)

        # 3. Refresh the list
        self.ann_listbox.delete(0, tk.END)
        ld_anns = ctx['ld_anns']

        if ld_anns:
            for idx, ann in enumerate(ld_anns):
                self.ann_listbox.insert(tk.END, f"#{idx} - ID:{ann.get('id')} (Cat:{ann.get('category_id')})")
            self.ann_listbox.selection_set(0)
        else:
            self.ann_listbox.insert(tk.END, "No Annotations (New)")
            if 0 not in self.runtime_labels:
                self.runtime_labels[0] = defaultdict(lambda: [-1, -1, -1])

        rel_path = ctx['full_path'].relative_to(self.data_manager.image_dir).as_posix()
        self.info_var.set(f"{ctx['index_str']} : {rel_path}")
        self._update_counter()

        self._refresh_canvas()

    def _reconstruct_runtime_state(self, ctx):
        """
        Reconstruct the state using saved annotation
        """
        saved_anns = ctx['saved_anns']
        ld_anns = ctx['ld_anns']

        id_to_idx = {ann['id']: i for i, ann in enumerate(ld_anns)}

        for s_ann in saved_anns:
            if "new_keypoints" not in s_ann: continue

            target_idx = None
            if s_ann.get('id') in id_to_idx:
                target_idx = id_to_idx[s_ann['id']]
            elif not ld_anns:
                target_idx = 0

            if target_idx is not None:
                recovered_data = defaultdict(lambda: [-1, -1, -1])
                for k, v in s_ann["new_keypoints"].items():
                    recovered_data[int(k)] = v
                self.runtime_labels[target_idx] = recovered_data

        if self.selected_ann_index not in self.runtime_labels:
            self.runtime_labels[self.selected_ann_index] = defaultdict(lambda: [-1, -1, -1])

    def _refresh_canvas(self):
        """
        Refresh the canvas to draw the current image and annotation
        Returns:
            None
        """
        ctx = self.data_manager.get_image_context(self.current_img_index)
        if not ctx: return

        tk_img = self.visualizer.render(
            ctx['full_path'],
            ctx['ld_anns'],
            self.selected_ann_index,
            self.runtime_labels
        )

        if tk_img:
            self.tk_img_ref = tk_img
            self.image_label.config(image=tk_img)

    def _validate_before_save(self):

        for ann_idx, kps in self.runtime_labels.items():
            for kp_id, val in kps.items():
                if not isinstance(val, list) or len(val) < 2:
                    continue

                x, y = val[0], val[1]

                if x == -1 or y == -1:
                    continue

                kp_name = Config.KEYPOINTS.get(kp_id, f"ID {kp_id}")

                vis = val[2] if len(val) > 2 else -1
                if vis == -1:
                    msg = f"保存失败：标注不完整\n人物#{ann_idx}, 点: {kp_name}\n请设置可见性 (Vis)。"
                    messagebox.showerror("校验错误", msg)
                    return False

                if kp_id in Config.PROSTHETIC_IDS:
                    conn = val[3] if len(val) > 3 else -1
                    if conn == -1:
                        msg = f"保存失败：标注不完整\n人物#{ann_idx}, 点: {kp_name}\n是假肢点，请设置 'Prev Node' (Human/Prosthetic)。"
                        messagebox.showerror("校验错误", msg)
                        return False

                    flex = val[4] if len(val) > 4 else -1
                    if flex == -1:
                        msg = f"保存失败：标注不完整\n人物#{ann_idx}, 点: {kp_name}\n是假肢点，请设置 'Flexibility' (Fixed/Free)。"
                        messagebox.showerror("校验错误", msg)
                        return False

        return True

    def _save_current(self):
        """
        Save the current image's annotation
        Returns:
            Boolean: True if the annotation is saved, False otherwise
        """
        if not self._validate_before_save():
            return False

        ctx = self.data_manager.get_image_context(self.current_img_index)
        if not ctx: return True

        count = self.data_manager.save_annotation_result(ctx['id'], self.runtime_labels)
        self._update_counter(saved_count=count)
        return True

    def _update_counter(self, saved_count=None):
        if saved_count is None:
            saved_count = len(self.data_manager.finished_ids)
        self.counter_var.set(f"已保存: {saved_count}")


    def _on_ann_list_select(self, event):
        sel = self.ann_listbox.curselection()
        if sel:
            idx = sel[0]
            if idx != self.selected_ann_index:
                self.selected_ann_index = idx
                if idx not in self.runtime_labels:
                    self.runtime_labels[idx] = defaultdict(lambda: [-1, -1, -1])
                self._refresh_canvas()

    def _on_canvas_click(self, event):
        if self.selected_keypoint_id < 0:
            messagebox.showwarning("提示", "请先选择一个关键点按钮。")
            return

        if self.selected_ann_index not in self.runtime_labels:
            self.runtime_labels[self.selected_ann_index] = defaultdict(lambda: [-1, -1, -1])

        current_points = self.runtime_labels[self.selected_ann_index]
        current_points[self.selected_keypoint_id][0] = event.x
        current_points[self.selected_keypoint_id][1] = event.y

        self._refresh_canvas()

    def _set_tool_keypoint(self, kp_id):
        self.selected_keypoint_id = kp_id

    def _set_tool_vis(self, vis):
        if self.selected_keypoint_id < 0:
            messagebox.showwarning("提示", "请先选择关键点。")
            return

        if self.selected_ann_index not in self.runtime_labels:
            self.runtime_labels[self.selected_ann_index] = defaultdict(lambda: [-1, -1, -1])

        self.runtime_labels[self.selected_ann_index][self.selected_keypoint_id][2] = vis
        self._refresh_canvas()

    def _clear_current_point(self):
        if self.selected_ann_index in self.runtime_labels:
            if self.selected_keypoint_id in self.runtime_labels[self.selected_ann_index]:
                self.runtime_labels[self.selected_ann_index][self.selected_keypoint_id] = [-1, -1, -1]
                self._refresh_canvas()

    def _prev_image(self):
        if not self._save_current():
            return
        if self.current_img_index > 0:
            self.current_img_index -= 1
            self._load_current_image()
        else:
            messagebox.showinfo("提示", "已经是第一张。")

    def _next_image(self):
        if not self._save_current(): return
        if self.current_img_index < len(self.data_manager.all_image_ids) - 1:
            self.current_img_index += 1
            self._load_current_image()
        else:
            messagebox.showinfo("提示", "已经是最后一张。")


def main():
    root = tk.Tk()
    app = ProsthesisLabelerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
