import json
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

    SHORT_NAMES = {
        1: 'L-Elbow\nRes(Above)', 2: 'R-Elbow\nRes(Above)',
        3: 'L-Elbow\nRes(Below)', 4: 'R-Elbow\nRes(Below)',
        5: 'L-Knee\nRes(Above)', 6: 'R-Knee\nRes(Above)',
        7: 'L-Knee\nRes(Below)', 8: 'R-Knee\nRes(Below)',
        9: 'L-Pros\nElbow', 10: 'R-Pros\nElbow',
        11: 'L-Pros\nWrist', 12: 'R-Pros\nWrist',
        13: 'L-Pros\nKnee', 14: 'R-Pros\nKnee',
        15: 'L-Pros\nAnkle', 16: 'R-Pros\nAnkle',
    }

    # Prosthetic points set (requires Flexibility setting)
    PROSTHETIC_IDS = {9, 10, 11, 12, 13, 14, 15, 16}

    # Upper residual limb points (allow Skip Knee/Elbow attribute setting)
    UPPER_RESIDUAL_IDS = {1, 2, 5, 6}

    COLORS = {
        1: '#FF0000', 2: '#00FF00', 3: '#FF00FF', 4: '#00FFFF',
        5: '#A52A2A', 6: '#FFC0CB', 7: '#000080', 8: '#8B4513',
        9: '#0000FF', 10: '#B8860B', 11: '#FFA500', 12: '#800080',
        13: '#808000', 14: '#008080', 15: '#DC143C', 16: '#4B0082',
    }

    BUTTON_LAYOUT = [
        [1, 2, 9, 10], [3, 4, 11, 12], [5, 6, 13, 14], [7, 8, 15, 16]
    ]

    COCO_SKELETON = [
        (0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
        (11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (5, 11), (6, 12)
    ]
    COCO_LEFT_SIDE = {5, 7, 9, 11, 13, 15}
    COCO_RIGHT_SIDE = {6, 8, 10, 12, 14, 16}

    PROSTHETIC_CONNECTIONS = [
        (1, 9), (9, 11), (3, 11),
        (2, 10), (10, 12), (4, 12),
        (5, 13), (13, 15), (7, 15),
        (6, 14), (14, 16), (8, 16),
    ]


class DataManager:
    def __init__(self):
        self.ld_label_path = None
        self.output_label_path = None
        self.image_dir = None
        self.all_image_ids = []
        self.ld_data_map = {}
        self.saved_anns_map = defaultdict(list)
        self.finished_ids = set()

    def set_paths(self, ld_path, out_path, img_dir):
        self.ld_label_path = ld_path
        self.output_label_path = out_path
        self.image_dir = img_dir

    def load_data(self):
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
        saved_anns_list, saved_imgs_list = self._load_json(self.output_label_path)
        self.saved_anns_map = defaultdict(list)
        for ann in saved_anns_list:
            self.saved_anns_map[ann['image_id']].append(ann)
        self.finished_ids = {img['id'] for img in (saved_imgs_list or [])}
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
        try:
            with open(self.output_label_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = {"images": [], "annotations": []}

        images = data.get("images", [])
        annotations = data.get("annotations", [])
        images = [img for img in images if img['id'] != current_id]
        annotations = [ann for ann in annotations if ann['image_id'] != current_id]

        img_info, ld_anns = self.ld_data_map[current_id]

        has_valid_data = False
        for person_labels in current_labels_map.values():
            if person_labels:
                has_valid_data = True
                break

        out_img_info = img_info.copy()
        out_img_info["has_pro"] = has_valid_data
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

        data["images"] = images
        data["annotations"] = annotations

        with open(self.output_label_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        self.finished_ids.add(current_id)
        self.saved_anns_map[current_id] = new_saved_cache
        return len(self.finished_ids)


class ImageVisualizer:
    def render(self, img_path, ld_anns, selected_ann_index, current_labels_map, show_coco_kps=True,
               show_extra_kps=False, show_bbox=True, show_connections=True):
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"Unable to open image: {img_path}, Error: {e}")
            return None

        draw = ImageDraw.Draw(img)

        if ld_anns and 0 <= selected_ann_index < len(ld_anns):
            target_ann = ld_anns[selected_ann_index]
            if show_coco_kps: self._draw_coco_keypoints(draw, target_ann)
            if show_extra_kps: self._draw_extra_keypoints(draw, target_ann)
            if show_bbox and "bbox" in target_ann:
                x, y, w, h = target_ann["bbox"]
                draw.rectangle([x, y, x + w, y + h], outline="red", width=3)
                draw.text((x, y - 15), f"ID: {target_ann.get('id')}", fill="red")

        current_person_labels = current_labels_map.get(selected_ann_index, {})

        if show_connections:
            self._draw_prosthetic_connections(draw, current_person_labels)

        r = 4
        for key_id, val in current_person_labels.items():
            if not isinstance(val, (list, tuple)) or len(val) < 2: continue
            if val[0] == -1: continue

            kx, ky = val[0], val[1]
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

    def _draw_prosthetic_connections(self, draw, labels_map):
        connection_color = '#00FFFF'
        line_width = 3

        for start_id, end_id in Config.PROSTHETIC_CONNECTIONS:
            if start_id not in labels_map or end_id not in labels_map:
                continue

            pt1_data = labels_map[start_id]
            pt2_data = labels_map[end_id]

            if not isinstance(pt1_data, (list, tuple)) or len(pt1_data) < 2 or pt1_data[0] == -1: continue
            if not isinstance(pt2_data, (list, tuple)) or len(pt2_data) < 2 or pt2_data[0] == -1: continue

            x1, y1 = pt1_data[0], pt1_data[1]
            x2, y2 = pt2_data[0], pt2_data[1]

            draw.line([(x1, y1), (x2, y2)], fill=connection_color, width=line_width)

    def _draw_coco_keypoints(self, draw, ann):
        kps = ann.get("keypoints", [])
        if not kps: return

        def get_kp(index):
            idx = index * 3
            if idx + 2 < len(kps): return kps[idx], kps[idx + 1], kps[idx + 2]
            return 0, 0, 0

        for i_start, i_end in Config.COCO_SKELETON:
            x1, y1, v1 = get_kp(i_start)
            x2, y2, v2 = get_kp(i_end)
            if v1 > 0 and v2 > 0: draw.line([(x1, y1), (x2, y2)], fill='black', width=2)
        r = 3
        for i in range(17):
            x, y, v = get_kp(i)
            if v > 0:
                draw.ellipse([x - r, y - r, x + r, y + r], fill='black', outline=None)
                if i in Config.COCO_LEFT_SIDE:
                    draw.text((x + 5, y - 5), "L", fill="black")
                elif i in Config.COCO_RIGHT_SIDE:
                    draw.text((x + 5, y - 5), "R", fill="black")

    def _draw_extra_keypoints(self, draw, ann):
        kps = ann.get("keypoints", [])
        if not kps: return

        def get_kp(index):
            idx = index * 3
            if idx + 2 < len(kps): return kps[idx], kps[idx + 1], kps[idx + 2]
            return 0, 0, 0

        r = 4
        for i in range(17, 25):
            x, y, v = get_kp(i)
            if v > 0:
                draw.ellipse([x - r, y - r, x + r, y + r], fill='#00BFFF', outline='white')
                draw.text((x + 5, y - 5), f"E{i}", fill="#00BFFF")


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

        # View States
        self.show_coco_var = tk.BooleanVar(value=False)
        self.show_extra_var = tk.BooleanVar(value=False)
        self.show_bbox_var = tk.BooleanVar(value=True)
        self.show_connection_var = tk.BooleanVar(value=True)

        if not self._init_paths():
            self.master.destroy()
            return
        if not self.data_manager.load_data():
            messagebox.showerror("Error", "Unable to load data files.")
            self.master.destroy()
            return
        self.current_img_index = self.data_manager.get_next_todo_index()
        self._setup_ui()
        self.master.bind("w", lambda event: self._move_list_selection(-1))
        self.master.bind("s", lambda event: self._move_list_selection(1))
        self._load_current_image()

    def _init_paths(self):
        ld_path = filedialog.askopenfilename(title="Select LDPose annotation (.json)", filetypes=[("JSON", "*.json")],
                                             initialdir='./ldpose_final/annotations')
        if not ld_path: return False
        out_path = filedialog.asksaveasfilename(title="Save labels.json location", initialfile="labels.json",
                                                defaultextension=".json", initialdir='./')
        if not out_path: return False
        img_dir = filedialog.askdirectory(title="Select Image Directory", initialdir='./ldpose_final')
        if not img_dir: return False

        if not Path(out_path).exists():
            with open(out_path, "w", encoding="utf-8") as f: json.dump({"images": [], "annotations": []}, f)
        self.data_manager.set_paths(Path(ld_path), Path(out_path), Path(img_dir))
        return True

    def _move_list_selection(self, step):
        size = self.ann_listbox.size()
        if size == 0: return
        current_sel = self.ann_listbox.curselection()
        if not current_sel:
            target_idx = 0
        else:
            target_idx = current_sel[0] + step
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
        self.image_label.bind("<Configure>", self._on_image_resize)
        self.image_label.bind("<Button-1>", self._on_canvas_click)
        self.image_label.bind('<Enter>', self._bound_to_mousewheel)
        self.canvas.bind('<Enter>', self._bound_to_mousewheel)
        self.image_label.bind('<Leave>', self._unbound_to_mousewheel)
        self.canvas.bind('<Leave>', self._unbound_to_mousewheel)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

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
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            delta = int(-1 * (event.delta / 120))
            self.canvas.yview_scroll(delta, "units")

    def _on_image_resize(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _setup_control_buttons(self, parent):
        kp_panel = tk.Frame(parent, bd=1, relief=tk.SUNKEN)
        kp_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        for i in range(4): kp_panel.columnconfigure(i, weight=1)
        for i in range(4): kp_panel.rowconfigure(i, weight=1)
        for r, row_ids in enumerate(Config.BUTTON_LAYOUT):
            for c, kp_id in enumerate(row_ids):
                name = Config.SHORT_NAMES.get(kp_id, Config.KEYPOINTS[kp_id])
                color = Config.COLORS.get(kp_id, 'black')
                tk.Button(kp_panel, text=name, fg=color, font=("Arial", 9, "bold"), width=15, height=3, bg="#f9f9f9",
                          wraplength=100, command=lambda k=kp_id: self._set_tool_keypoint(k)).grid(row=r, column=c,
                                                                                                   padx=2, pady=2,
                                                                                                   sticky="nsew")

        tools_panel = tk.Frame(parent)
        tools_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        info_frame = tk.Frame(tools_panel)
        info_frame.pack(fill=tk.X, pady=5)
        tk.Label(info_frame, textvariable=self.info_var, font=("Arial", 10)).pack(side=tk.LEFT)
        tk.Label(info_frame, textvariable=self.counter_var, font=("Arial", 11, "bold"), fg="blue").pack(side=tk.RIGHT)
        tk.Frame(tools_panel, height=2, bd=1, relief=tk.GROOVE).pack(fill=tk.X, pady=5)

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
            attr_frame,
            text="Skip Knee/Elbow",
            variable=self.skip_joint_var,
            command=self._on_skip_toggle,
            fg="red", font=("Arial", 9, "bold")
        )
        tk.Button(attr_frame, text="Clear", bg="#ffcccc", command=self._clear_current_point).pack(side=tk.RIGHT, padx=5)

        toggle_frame = tk.Frame(tools_panel)
        toggle_frame.pack(fill=tk.X, pady=5)

        # Row 1 of toggles
        row1 = tk.Frame(toggle_frame)
        row1.pack(fill=tk.X, expand=True)
        self.btn_toggle_coco = tk.Button(row1, text="显示原始 COCO", command=self._toggle_coco_display)
        self.btn_toggle_coco.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        self.btn_toggle_extra = tk.Button(row1, text="显示残肢点(旧)", command=self._toggle_extra_display)
        self.btn_toggle_extra.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        # Row 2 of toggles
        row2 = tk.Frame(toggle_frame)
        row2.pack(fill=tk.X, expand=True, pady=2)
        self.btn_toggle_bbox = tk.Button(row2, text="隐藏 BBox", relief="sunken", bg="#FFCCCB",
                                         command=self._toggle_bbox_display)
        self.btn_toggle_bbox.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        self.btn_toggle_conn = tk.Button(row2, text="隐藏假肢连线", relief="sunken", bg="#E0FFFF",
                                         command=self._toggle_connection_display)
        self.btn_toggle_conn.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        self.default_btn_bg = self.btn_toggle_coco.cget("bg")

        # [NEW] Index Search Bar
        search_frame = tk.Frame(tools_panel)
        search_frame.pack(fill=tk.X, pady=10)
        tk.Label(search_frame, text="跳转 Index:", font=("Arial", 10)).pack(side=tk.LEFT)
        self.entry_search = tk.Entry(search_frame, width=8, font=("Arial", 10))
        self.entry_search.pack(side=tk.LEFT, padx=5)
        self.entry_search.bind("<Return>", self._on_search_index)
        tk.Button(search_frame, text="Go", command=self._on_search_index, height=1).pack(side=tk.LEFT)

        nav_frame = tk.Frame(tools_panel)
        nav_frame.pack(fill=tk.X, pady=2)
        tk.Button(nav_frame, text="< Previous", height=2, command=self._prev_image).pack(side=tk.LEFT, fill=tk.X,
                                                                                         expand=True, padx=20)
        tk.Button(nav_frame, text="Next >", height=2, bg="#ddffdd", command=self._next_image).pack(side=tk.LEFT,
                                                                                                   fill=tk.X,
                                                                                                   expand=True, padx=20)

    # [NEW] Search handler
    def _on_search_index(self, event=None):
        val = self.entry_search.get().strip()
        if not val: return
        try:
            target_idx = int(val) - 1
        except ValueError:
            messagebox.showerror("Error", "请输入有效的数字 (Index)")
            return
        total_imgs = len(self.data_manager.all_image_ids)
        if target_idx < 0 or target_idx >= total_imgs:
            messagebox.showerror("Error", f"索引超出范围。\n有效范围: 1 - {total_imgs}")
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

    def _toggle_extra_display(self):
        new_val = not self.show_extra_var.get()
        self.show_extra_var.set(new_val)
        self.btn_toggle_extra.config(text="隐藏残肢点(旧)" if new_val else "显示残肢点(旧)",
                                     relief="sunken" if new_val else "raised",
                                     bg="#ADD8E6" if new_val else self.default_btn_bg)
        self._refresh_canvas()

    def _toggle_coco_display(self):
        new_val = not self.show_coco_var.get()
        self.show_coco_var.set(new_val)
        self.btn_toggle_coco.config(text="隐藏 COCO" if new_val else "显示 COCO",
                                    relief="sunken" if new_val else "raised",
                                    bg="#ddd" if new_val else self.default_btn_bg)
        self._refresh_canvas()

    def _set_attr_flex(self, val):
        if self.selected_keypoint_id < 0: return
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
            messagebox.showinfo("Done", "No more images or index out of bounds.")
            return
        self.runtime_labels = {}
        self.selected_keypoint_id = -1
        self.selected_ann_index = 0
        self._reconstruct_runtime_state(ctx)
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
        self._refresh_canvas()

    def _reconstruct_runtime_state(self, ctx):
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
                recovered_data = defaultdict(lambda: [-1, -1, -1, -1, False])
                for k, v in s_ann["new_keypoints"].items():
                    val_list = list(v)
                    if not val_list or val_list[0] == -1: continue
                    while len(val_list) < 5: val_list.append(False if len(val_list) == 4 else -1)
                    recovered_data[int(k)] = val_list
                self.runtime_labels[target_idx] = recovered_data
        if self.selected_ann_index not in self.runtime_labels:
            self.runtime_labels[self.selected_ann_index] = defaultdict(lambda: [-1, -1, -1, -1, False])

    def _refresh_canvas(self):
        ctx = self.data_manager.get_image_context(self.current_img_index)
        if not ctx: return
        tk_img = self.visualizer.render(
            ctx['full_path'], ctx['ld_anns'], self.selected_ann_index, self.runtime_labels,
            show_coco_kps=self.show_coco_var.get(),
            show_extra_kps=self.show_extra_var.get(),
            show_bbox=self.show_bbox_var.get(),
            show_connections=self.show_connection_var.get()
        )
        if tk_img:
            self.tk_img_ref = tk_img
            self.image_label.config(image=tk_img)

    def _prune_garbage(self):
        for ann_idx in list(self.runtime_labels.keys()):
            person_labels = self.runtime_labels[ann_idx]
            keys_to_delete = [
                k for k, v in person_labels.items()
                if isinstance(v, list) and len(v) > 0 and v[0] == -1
            ]
            for k in keys_to_delete:
                del person_labels[k]

    def _validate_before_save(self):
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
                        messagebox.showerror("Validation Error",
                                             f"#{ann_idx} {kp_name}: It's a prosthetic point, please set 'Flex'.")
                        return False
        return True

    def _save_current(self):
        if not self._validate_before_save(): return False
        ctx = self.data_manager.get_image_context(self.current_img_index)
        if not ctx: return True
        count = self.data_manager.save_annotation_result(ctx['id'], self.runtime_labels)
        self._update_counter(saved_count=count)
        return True

    def _update_counter(self, saved_count=None):
        if saved_count is None: saved_count = len(self.data_manager.finished_ids)
        self.counter_var.set(f"Saved: {saved_count}")

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
            messagebox.showwarning("Tip", "Please select a keypoint button first.")
            return
        if self.selected_ann_index not in self.runtime_labels:
            self.runtime_labels[self.selected_ann_index] = defaultdict(lambda: [-1, -1, -1, -1, False])

        current_points = self.runtime_labels[self.selected_ann_index]
        if self.selected_keypoint_id not in current_points:
            current_points[self.selected_keypoint_id] = [-1, -1, -1, -1, False]

        current_points[self.selected_keypoint_id][0] = event.x
        current_points[self.selected_keypoint_id][1] = event.y
        self._refresh_canvas()

    def _set_tool_keypoint(self, kp_id):
        self.selected_keypoint_id = kp_id
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