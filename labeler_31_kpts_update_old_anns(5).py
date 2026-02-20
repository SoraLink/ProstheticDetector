import json
import os
import tkinter as tk
from tkinter import messagebox, filedialog
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw, ImageOps, ImageFont


# =================CONFIGURATION=================
class Config:
    WINDOW_WIDTH = 1600
    WINDOW_HEIGHT = 950

    KEYPOINT_NAMES = [
        "nose", "left_eye", "right_eye", "left_ear", "right_ear",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist",
        "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle",
        "L_Middle_Tip", "R_Middle_Tip", "L_Heel", "R_Heel", "L_Toe_Tip", "R_Toe_Tip",
        "L-Elbow-Res-Above", "R-Elbow-Res-Above", "L-Elbow-Res-Below", "R-Elbow-Res-Below",
        "L-Knee-Res-Above", "R-Knee-Res-Above", "L-Knee-Res-Below", "R-Knee-Res-Below"
    ]

    JOINTS_KPS = ["left_elbow", "right_elbow", "left_knee", "right_knee"]

    RES_KPS = [
        "L-Elbow-Res-Above", "R-Elbow-Res-Above", "L-Elbow-Res-Below", "R-Elbow-Res-Below",
        "L-Knee-Res-Above", "R-Knee-Res-Above", "L-Knee-Res-Below", "R-Knee-Res-Below"
    ]

    EDITABLE_KPS = [
                       "left_wrist", "right_wrist", "left_ankle", "right_ankle",
                       "L_Middle_Tip", "R_Middle_Tip", "L_Heel", "R_Heel", "L_Toe_Tip", "R_Toe_Tip",
                       "left_elbow", "right_elbow", "left_knee", "right_knee"
                   ] + RES_KPS

    BTN_L = ["left_wrist", "L_Middle_Tip", "left_ankle", "L_Heel", "L_Toe_Tip"]
    BTN_R = ["right_wrist", "R_Middle_Tip", "right_ankle", "R_Heel", "R_Toe_Tip"]
    BTN_JOINTS = ["left_elbow", "right_elbow", "left_knee", "right_knee"]
    BTN_RES_L = ["L-Elbow-Res-Above", "L-Elbow-Res-Below", "L-Knee-Res-Above", "L-Knee-Res-Below"]
    BTN_RES_R = ["R-Elbow-Res-Above", "R-Elbow-Res-Below", "R-Knee-Res-Above", "R-Knee-Res-Below"]

    BBOX_COLOR = "#FFFF00"
    SKELETON_COLOR = "#0000FF"
    JOINT_COLOR = "#0055FF"
    RES_COLOR = "#00FF00"
    RES_ACTIVE_COLOR = "red"
    OTHER_COLOR = "black"

    SKELETON_LINKS = [
        (0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12), (11, 12),
        (11, 13), (13, 15), (12, 14), (14, 16), (9, 17), (10, 18), (15, 19), (15, 21), (16, 20), (16, 22),
        (5, 23), (6, 24), (7, 25), (8, 26), (11, 27), (12, 28), (13, 29), (14, 30)
    ]
    TYPE_NAMES = {0: "Normal", 1: "Prosthesis", 2: "Missing", -1: "Unset"}
    VIS_NAMES = {0: "无(0)", 1: "遮挡(1)", 2: "可见(2)", -1: "Init(-1)"}

    # ---------------------------------------------------------
    # 核心逻辑冲突定义 (Logic Conflict Definitions)
    # ---------------------------------------------------------

    # 1. 层级压制 (Hierarchy Suppression)
    LOGIC_CONFLICT_MAP = {
        # === 上肢 ===
        "L-Elbow-Res-Above": ["left_elbow", "L-Elbow-Res-Below", "left_wrist", "L_Middle_Tip"],
        "R-Elbow-Res-Above": ["right_elbow", "R-Elbow-Res-Below", "right_wrist", "R_Middle_Tip"],
        "L-Elbow-Res-Below": ["left_wrist", "L_Middle_Tip"],
        "R-Elbow-Res-Below": ["right_wrist", "R_Middle_Tip"],

        # === 下肢 ===
        "L-Knee-Res-Above": ["left_knee", "L-Knee-Res-Below", "left_ankle", "L_Heel", "L_Toe_Tip"],
        "R-Knee-Res-Above": ["right_knee", "R-Knee-Res-Below", "right_ankle", "R_Heel", "R_Toe_Tip"],
        "L-Knee-Res-Below": ["left_ankle", "L_Heel", "L_Toe_Tip"],
        "R-Knee-Res-Below": ["right_ankle", "R_Heel", "R_Toe_Tip"]
    }

    # 2. 逆天生长 (Normal Parent Check)
    HIERARCHY_NORMAL = {
        "left_wrist": "left_elbow", "right_wrist": "right_elbow",
        "left_elbow": "left_shoulder", "right_elbow": "right_shoulder",
        "L_Middle_Tip": "left_wrist", "R_Middle_Tip": "right_wrist",
        "left_ankle": "left_knee", "right_ankle": "right_knee",
        "left_knee": "left_hip", "right_knee": "right_hip",
        "L_Heel": "left_ankle", "R_Heel": "right_ankle",
        "L_Toe_Tip": "L_Heel", "R_Toe_Tip": "R_Heel"
    }

    # 3. 悬空假肢 (Prosthesis Anchor Check)
    HIERARCHY_PROSTHESIS = {
        "left_wrist": ["L-Elbow-Res-Above", "L-Elbow-Res-Below"],
        "right_wrist": ["R-Elbow-Res-Above", "R-Elbow-Res-Below"],
        "L_Middle_Tip": ["L-Elbow-Res-Above", "L-Elbow-Res-Below"],
        "R_Middle_Tip": ["R-Elbow-Res-Above", "R-Elbow-Res-Below"],
        "left_ankle": ["L-Knee-Res-Above", "L-Knee-Res-Below"],
        "right_ankle": ["R-Knee-Res-Above", "R-Knee-Res-Below"],
        "L_Heel": ["L-Knee-Res-Above", "L-Knee-Res-Below"],
        "R_Heel": ["R-Knee-Res-Above", "R-Knee-Res-Below"],
        "L_Toe_Tip": ["L-Knee-Res-Above", "L-Knee-Res-Below"],
        "R_Toe_Tip": ["R-Knee-Res-Above", "R-Knee-Res-Below"]
    }

    # 级联关系 (保留原有的自动辅助功能)
    AUTO_PROSTHESIS_MAP = {
        "L-Elbow-Res-Above": ["left_elbow", "left_wrist", "L_Middle_Tip"],
        "L-Elbow-Res-Below": ["left_wrist", "L_Middle_Tip"],
        "R-Elbow-Res-Above": ["right_elbow", "right_wrist", "R_Middle_Tip"],
        "R-Elbow-Res-Below": ["right_wrist", "R_Middle_Tip"],
        "L-Knee-Res-Above": ["left_knee", "left_ankle", "L_Heel", "L_Toe_Tip"],
        "L-Knee-Res-Below": ["left_ankle", "L_Heel", "L_Toe_Tip"],
        "R-Knee-Res-Above": ["right_knee", "right_ankle", "R_Heel", "R_Toe_Tip"],
        "R-Knee-Res-Below": ["right_ankle", "R_Heel", "R_Toe_Tip"]
    }


# =================DATA MANAGER=================
class DataManager:
    def __init__(self):
        self.source_data, self.delta_data = {}, {}
        self.image_lookup, self.task_list = {}, []
        self.img_dir, self.output_path = None, None

    def load_data(self, src, dst, img_d):
        self.img_dir, self.output_path = Path(img_d), Path(dst)
        try:
            with open(src, "r", encoding="utf-8") as f:
                self.source_data = json.load(f)
        except Exception as e:
            return False, str(e)
        self.image_lookup = {img['id']: img for img in self.source_data.get('images', [])}
        anns = self.source_data.get('annotations', [])
        anns.sort(key=lambda x: (x['image_id'], x['id']), reverse=True)
        self.task_list = anns
        if self.output_path.exists():
            try:
                with open(self.output_path, "r", encoding="utf-8") as f:
                    self.delta_data = json.load(f)
            except:
                self.delta_data = {"info": {"last_index": 0}, "changes": {}}
        else:
            self.delta_data = {"info": {"last_index": 0}, "changes": {}}
        return True, "Success"

    def get_context(self, index):
        if index < 0 or index >= len(self.task_list): return None
        ann = self.task_list[index]
        img_info = self.image_lookup.get(ann['image_id'])
        if not img_info: return None
        key = f"{ann['image_id']}_{ann['id']}"
        changes = self.delta_data.get("changes", {}).get(key, None)

        is_deleted = False
        if changes and "__DELETED__" in changes and changes["__DELETED__"] == True:
            is_deleted = True

        return {
            "index": index, "total": len(self.task_list),
            "img_info": img_info, "original_ann": ann,
            "changes": changes, "full_path": self.img_dir / img_info['file_name'],
            "is_deleted": is_deleted
        }

    def save_current_state(self, index, kps_dict, is_deleted):
        ann = self.task_list[index]
        key = f"{ann['image_id']}_{ann['id']}"
        if is_deleted:
            changes = {"__DELETED__": True}
        else:
            changes = {n: [round(d['x'], 2), round(d['y'], 2), int(d['v']), int(d['type'])]
                       for n, d in kps_dict.items() if n in Config.EDITABLE_KPS}
        if "changes" not in self.delta_data: self.delta_data["changes"] = {}
        self.delta_data["changes"][key] = changes
        self.delta_data["info"]["last_index"] = index
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(self.delta_data, f, ensure_ascii=False)

    # ---------------------------------------------------------
    # 核心逻辑检测引擎 (The Logic Engine)
    # ---------------------------------------------------------
    def check_logic_conflict(self, kps_dict):
        conflicts = []
        # 定义严格的层级结构
        HIERARCHY = {
            "L-Elbow-Res-Above": ("left_elbow", "L-Elbow-Res-Below", ["left_wrist", "L_Middle_Tip"]),
            "R-Elbow-Res-Above": ("right_elbow", "R-Elbow-Res-Below", ["right_wrist", "R_Middle_Tip"]),
            "L-Knee-Res-Above": ("left_knee", "L-Knee-Res-Below", ["left_ankle", "L_Heel", "L_Toe_Tip"]),
            "R-Knee-Res-Above": ("right_knee", "R-Knee-Res-Below", ["right_ankle", "R_Heel", "R_Toe_Tip"])
        }

        for above_res, (joint, below_res, distal_parts) in HIERARCHY.items():
            above_data = kps_dict.get(above_res)
            is_above_active = (above_data and above_data['v'] > 0 and above_data['type'] != 2)

            if is_above_active:
                j_data = kps_dict.get(joint)
                if j_data and j_data['v'] > 0 and j_data['type'] == 0:
                    conflicts.append((above_res, f"逻辑冲突: {above_res}已截肢，关节 {joint} 不能是肉体"))
                b_data = kps_dict.get(below_res)
                if b_data and b_data['type'] != 2:
                    conflicts.append((above_res, f"物理冲突: {above_res}已截肢，下游残肢 {below_res} 必须是Missing"))
                for distal in distal_parts:
                    d_data = kps_dict.get(distal)
                    if d_data and d_data['v'] > 0 and d_data['type'] == 0:
                        conflicts.append((above_res, f"逻辑冲突: {above_res}已截肢，远端 {distal} 不能是肉体"))
                continue
            else:
                j_data = kps_dict.get(joint)
                if j_data and j_data['v'] > 0:
                    if j_data['type'] == 1:
                        conflicts.append((joint, f"逻辑冲突: {above_res}未截肢，关节 {joint} 却是假肢"))
                    elif j_data['type'] == 2:
                        conflicts.append((joint, f"数据残留: {above_res}未截肢，关节 {joint} 却是Missing"))

                below_data = kps_dict.get(below_res)
                is_below_active = (below_data and below_data['v'] > 0 and below_data['type'] != 2)

                for distal in distal_parts:
                    d_data = kps_dict.get(distal)
                    if not d_data or d_data['v'] == 0: continue
                    if is_below_active:
                        if d_data['type'] == 0:
                            conflicts.append((below_res, f"逻辑冲突: {below_res}已截肢，远端 {distal} 不能是肉体"))
                    else:
                        if d_data['type'] == 1:
                            conflicts.append((distal, f"逻辑冲突: {below_res}未截肢，远端 {distal} 却是假肢"))
                        elif d_data['type'] == 2:
                            conflicts.append((distal, f"数据残留: {below_res}未截肢，远端 {distal} 却是Missing"))
        return conflicts

# =================VISUALIZER=================
class ImageVisualizer:
    def __init__(self):
        self.title_font = self._load_font(20)

    def _load_font(self, size):
        try:
            return ImageFont.truetype("msyh.ttc", size)
        except:
            return ImageFont.load_default()

    def render(self, base_img, runtime_kps, active_kp, scale, show_bbox, show_skel, show_pts, bbox, is_deleted,
               conflicts):
        img = base_img.copy()
        draw = ImageDraw.Draw(img)
        s = lambda v: v * scale

        if is_deleted:
            w, h = img.size
            draw.line([(0, 0), (w, h)], fill="red", width=5)
            draw.line([(0, h), (w, 0)], fill="red", width=5)
            draw.text((20, 20), "OBJECT DELETED", fill="red", font=self.title_font)
            return ImageTk.PhotoImage(img)

        conflict_names = set(c[0] for c in conflicts)

        # BBox
        if show_bbox and bbox:
            draw.rectangle([s(bbox[0]), s(bbox[1]), s(bbox[0] + bbox[2]), s(bbox[1] + bbox[3])],
                           outline=Config.BBOX_COLOR, width=2)

        # Skeleton
        if show_skel:
            for i1, i2 in Config.SKELETON_LINKS:
                p1, p2 = runtime_kps.get(Config.KEYPOINT_NAMES[i1]), runtime_kps.get(Config.KEYPOINT_NAMES[i2])
                if (p1 and p2 and p1['x'] > 1 and p2['x'] > 1 and p1['v'] > 0 and p2['v'] > 0 and
                    p1['type'] != 2 and p2['type'] != 2):
                    draw.line([(s(p1['x']), s(p1['y'])), (s(p2['x']), s(p2['y']))], fill=Config.SKELETON_COLOR, width=2)

        # Points
        if show_pts:
            for name, d in runtime_kps.items():
                if d['v'] == 0 or d['x'] <= 1 or d['type'] == 2: continue

                is_ed = name in Config.EDITABLE_KPS
                is_conflict = name in conflict_names
                is_active = (name == active_kp)
                is_residual = (name in Config.RES_KPS)

                color = Config.OTHER_COLOR
                outline_color = None
                radius = 3

                if is_conflict:
                    color = "red"
                    outline_color = "yellow"
                    radius = 8
                elif is_residual:
                    if is_active:
                        color = Config.RES_ACTIVE_COLOR
                        outline_color = "white"
                        radius = 7
                    else:
                        color = Config.RES_COLOR
                        radius = 4
                elif is_ed:
                    color = "#00FFFF" if "left" in name or name.startswith("L") else "#FF00FF"
                    if is_active:
                        color = "#FFFF00"
                        radius = 7
                        outline_color = "white"
                    else:
                        radius = 4
                elif name in Config.JOINTS_KPS:
                    color = Config.JOINT_COLOR
                    radius = 3

                draw.ellipse([s(d['x']) - radius, s(d['y']) - radius, s(d['x']) + radius, s(d['y']) + radius],
                             fill=color, outline=outline_color)

                display_name = ""
                if is_residual:
                    display_name = name.replace("Elbow", "Elb").replace("Knee", "Kn").replace("-Res-", "-")

                text_color = "yellow"
                info_txt = f"T:{d['type']} V:{d['v']}"

                if is_conflict:
                    text_color = "red"
                    info_txt = f"ERR!\n{display_name}"
                elif is_residual:
                    info_txt += f"\n{display_name}"
                    if is_active:
                        text_color = "red"
                    else:
                        text_color = "#00FF00"

                text_x, text_y = s(d['x']) + 10, s(d['y']) - 10
                draw.text((text_x, text_y), info_txt, fill=text_color)

        return ImageTk.PhotoImage(img)


# =================APP=================
class LabelerApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Amputee Pose Labeler Pro (Auto-Fix Ghost Points)")
        self.master.geometry(f"{Config.WINDOW_WIDTH}x{Config.WINDOW_HEIGHT}")
        self.data_mgr, self.visualizer = DataManager(), ImageVisualizer()
        self.current_index, self.scale, self.runtime_kps = 0, 1.0, {}
        self.active_kp_name = Config.EDITABLE_KPS[0] if Config.EDITABLE_KPS else Config.KEYPOINT_NAMES[0]
        self.is_deleted = False

        self.show_bbox_var, self.show_skeleton_var, self.show_points_var = [tk.BooleanVar(value=True) for _ in range(3)]
        self.type_var, self.vis_var = tk.IntVar(value=0), tk.IntVar(value=2)

        if not self._init_files(): master.destroy(); return
        self._setup_ui()
        self.current_index = self.data_mgr.delta_data.get("info", {}).get("last_index", 0)
        self._load_current_scene()

    def _init_files(self):
        src = filedialog.askopenfilename(title="1. Source JSON")
        if not src: return False
        dst = filedialog.asksaveasfilename(title="2. Save Delta JSON", defaultextension=".json")
        if not dst: return False
        d = filedialog.askdirectory(title="3. Image Directory")
        if not d: return False
        success, msg = self.data_mgr.load_data(src, dst, d)
        if not success: messagebox.showerror("Error", msg)
        return success

    def _setup_ui(self):
        main = tk.PanedWindow(self.master, orient=tk.HORIZONTAL, sashwidth=8, bg="#888", sashrelief=tk.RAISED)
        main.pack(fill=tk.BOTH, expand=True)
        f_img = tk.Frame(main, bg="#333")
        main.add(f_img, width=1000, minsize=100, stretch="always")

        self.h_scr = tk.Scrollbar(f_img, orient=tk.HORIZONTAL)
        self.v_scr = tk.Scrollbar(f_img, orient=tk.VERTICAL)
        self.canvas = tk.Canvas(f_img, bg="#222", cursor="cross", xscrollcommand=self.h_scr.set,
                                yscrollcommand=self.v_scr.set)
        self.h_scr.config(command=self.canvas.xview)
        self.v_scr.config(command=self.canvas.yview)
        self.v_scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scr.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas_image = self.canvas.create_image(0, 0, anchor="nw")

        ctrl_outer = tk.Frame(main, bg="#f0f0f0")
        main.add(ctrl_outer, minsize=500, stretch="never")

        ctrl_canvas = tk.Canvas(ctrl_outer, bg="#f0f0f0", highlightthickness=0)
        ctrl_v_scr = tk.Scrollbar(ctrl_outer, orient=tk.VERTICAL, command=ctrl_canvas.yview)
        self.ctrl_inner = tk.Frame(ctrl_canvas, bg="#f0f0f0", padx=10, pady=10)

        ctrl_canvas.create_window((0, 0), window=self.ctrl_inner, anchor="nw")
        ctrl_canvas.config(yscrollcommand=ctrl_v_scr.set)

        ctrl_v_scr.pack(side=tk.RIGHT, fill=tk.Y)
        ctrl_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.ctrl_inner.bind("<Configure>", lambda e: ctrl_canvas.configure(scrollregion=ctrl_canvas.bbox("all")))

        nav = tk.Frame(self.ctrl_inner, bg="#ddd", padx=5, pady=5)
        nav.pack(fill=tk.X, pady=(0, 10))
        self.lbl_info = tk.Label(nav, text="Task Info", bg="#ddd", font=("Arial", 11, "bold"))
        self.lbl_info.pack(pady=5)
        self.lbl_filename = tk.Label(nav, text="File: None", bg="#ddd", font=("Arial", 9), fg="#555")
        self.lbl_filename.pack(pady=2)

        goto_frame = tk.Frame(nav, bg="#ddd")
        goto_frame.pack(fill=tk.X, pady=5)
        tk.Label(goto_frame, text="跳转到:", bg="#ddd", font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 5))
        self.goto_entry = tk.Entry(goto_frame, width=8, font=("Arial", 10), justify="center")
        self.goto_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.goto_entry.bind("<Return>", lambda e: self._goto_task())
        tk.Button(goto_frame, text="GO", command=self._goto_task, bg="#4CAF50", fg="white", font=("Arial", 9, "bold"),
                  width=6).pack(side=tk.LEFT)
        tk.Label(goto_frame, text=f"/ {len(self.data_mgr.task_list)}", bg="#ddd", font=("Arial", 9)).pack(side=tk.LEFT,
                                                                                                          padx=(5, 0))

        tk.Button(nav, text="DELETE OBJECT (Del)", command=self._toggle_delete, bg="#f44", fg="white",
                  font=("Arial", 9, "bold")).pack(fill=tk.X, pady=5, padx=20)
        btn_f = tk.Frame(nav, bg="#ddd")
        btn_f.pack(fill=tk.X)
        tk.Button(btn_f, text="< PREV (A)", command=self._prev_img, height=2, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_f, text="NEXT (D) >", command=self._next_img, bg="#8f8", height=2, width=15).pack(side=tk.RIGHT,
                                                                                                        padx=5)

        attr = tk.LabelFrame(self.ctrl_inner, text="Attributes", bg="#eee", padx=10, pady=5, font=("Arial", 10, "bold"))
        attr.pack(fill=tk.X, pady=(0, 15))
        f_tog = tk.Frame(attr, bg="#eee")
        f_tog.pack(fill=tk.X, pady=2)
        for t, v in [("BBox", self.show_bbox_var), ("Skel", self.show_skeleton_var), ("Pts", self.show_points_var)]:
            tk.Checkbutton(f_tog, text=t, variable=v, command=self._refresh_canvas, bg="#eee", font=("Arial", 9)).pack(
                side=tk.LEFT, padx=5)
        f_tv = tk.Frame(attr, bg="#eee")
        f_tv.pack(fill=tk.X)
        tk.Label(f_tv, text="TYPE:", font=("Arial", 8, "bold"), bg="#eee").grid(row=0, column=0, sticky="w")
        tk.Label(f_tv, text="VIS:", font=("Arial", 8, "bold"), bg="#eee").grid(row=1, column=0, sticky="w")
        f_t_opts = tk.Frame(f_tv, bg="#eee")
        f_t_opts.grid(row=0, column=1, sticky="w")
        for v, n in Config.TYPE_NAMES.items(): tk.Radiobutton(f_t_opts, text=n, variable=self.type_var, value=v,
                                                              command=self._on_attr_change, bg="#eee").pack(
            side=tk.LEFT)
        f_v_opts = tk.Frame(f_tv, bg="#eee")
        f_v_opts.grid(row=1, column=1, sticky="w")
        for v, n in Config.VIS_NAMES.items(): tk.Radiobutton(f_v_opts, text=n, variable=self.vis_var, value=v,
                                                             command=self._on_attr_change, bg="#eee").pack(side=tk.LEFT)

        self.btns = {}

        def add_button(parent, k, row, col):
            txt = k.replace("left_", "L_").replace("right_", "R_").replace("-Res-", "_")
            txt = txt.replace("Elbow", "Elb").replace("Knee", "Kne")
            b = tk.Button(parent, text=txt, font=("Arial", 8), bg="white", width=12,
                          command=lambda x=k: self._set_tool(x))
            b.grid(row=row, column=col, sticky="ew", padx=2, pady=1)
            self.btns[k] = b

        kp_frame = tk.LabelFrame(self.ctrl_inner, text="Standard Points", bg="#f0f0f0", font=("Arial", 10, "bold"))
        kp_frame.pack(fill=tk.X, expand=False, pady=(0, 10))

        def add_standard_col(title, klist, color, col_idx):
            tk.Label(kp_frame, text=title, bg=color, font=("Arial", 9, "bold"), pady=3).grid(row=0, column=col_idx,
                                                                                             sticky="ew", padx=2,
                                                                                             pady=(5, 5))
            for i, k in enumerate(klist): add_button(kp_frame, k, i + 1, col_idx)

        add_standard_col("Left Side", Config.BTN_L, "#eef", 0)
        add_standard_col("Right Side", Config.BTN_R, "#fee", 1)
        add_standard_col("Joints", Config.BTN_JOINTS, "#efe", 2)
        for c in range(3): kp_frame.grid_columnconfigure(c, weight=1)

        res_frame = tk.LabelFrame(self.ctrl_inner, text="Residuals (Amputation)", bg="#ffffee",
                                  font=("Arial", 10, "bold"), fg="#550")
        res_frame.pack(fill=tk.X, expand=False)

        def add_res_col(title, klist, col_idx):
            tk.Label(res_frame, text=title, bg="#ffffee", font=("Arial", 9, "bold"), pady=3).grid(row=0, column=col_idx,
                                                                                                  sticky="ew", padx=2,
                                                                                                  pady=(5, 5))
            for i, k in enumerate(klist): add_button(res_frame, k, i + 1, col_idx)

        add_res_col("Left Residuals", Config.BTN_RES_L, 0)
        add_res_col("Right Residuals", Config.BTN_RES_R, 1)
        for c in range(2): res_frame.grid_columnconfigure(c, weight=1)

        conf_frame = tk.LabelFrame(self.ctrl_inner, text="Logic Conflict Log (Warnings)", bg="#fee",
                                   font=("Arial", 10, "bold"), fg="red")
        conf_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        conf_scroll = tk.Scrollbar(conf_frame)
        conf_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.conflict_text = tk.Text(conf_frame, height=8, width=30, font=("Arial", 9), bg="#fff0f0",
                                     yscrollcommand=conf_scroll.set, state=tk.DISABLED, wrap=tk.WORD)
        self.conflict_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        conf_scroll.config(command=self.conflict_text.yview)

        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<MouseWheel>", self._on_zoom)
        self.canvas.bind("<Button-2>", lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind("<B2-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        self.canvas.bind("<Button-4>", lambda e: self._manual_zoom(e, 1))
        self.canvas.bind("<Button-5>", lambda e: self._manual_zoom(e, -1))
        self.master.bind("a", lambda e: self._prev_img())
        self.master.bind("d", lambda e: self._next_img())
        self.master.bind("q", lambda e: self._quick(self.type_var, 0))
        self.master.bind("w", lambda e: self._quick(self.type_var, 1))
        self.master.bind("e", lambda e: self._quick(self.type_var, 2))
        self.master.bind("z", lambda e: self._quick(self.vis_var, 0))
        self.master.bind("x", lambda e: self._quick(self.vis_var, 1))
        self.master.bind("c", lambda e: self._quick(self.vis_var, 2))
        self.master.bind("<Delete>", lambda e: self._toggle_delete())
        self.master.bind("g", lambda e: self._goto_task())

    def _goto_task(self):
        try:
            target_str = self.goto_entry.get().strip()
            if not target_str: return
            target = int(target_str)
            if target < 1 or target > len(self.data_mgr.task_list):
                messagebox.showerror("错误", f"请输入有效的任务编号 (1-{len(self.data_mgr.task_list)})")
                return
            self.data_mgr.save_current_state(self.current_index, self.runtime_kps, self.is_deleted)
            self.current_index = target - 1
            self._load_current_scene()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
        except Exception as e:
            messagebox.showerror("错误", f"跳转失败: {str(e)}")

    def _update_goto_display(self):
        if hasattr(self, 'goto_entry'):
            self.goto_entry.delete(0, tk.END)
            self.goto_entry.insert(0, str(self.current_index + 1))

    def _manual_zoom(self, e, direction):
        class MockEvent:
            def __init__(self, x, y, d): self.x, self.y, self.delta = x, y, d

        self._on_zoom(MockEvent(e.x, e.y, direction))

    def _quick(self, var, val):
        var.set(val);
        self._on_attr_change()

    def _on_zoom(self, e):
        if e.delta > 0:
            factor = 1.2
        elif e.delta < 0:
            factor = 0.8
        else:
            return
        new_scale = self.scale * factor
        if not (0.1 < new_scale < 20.0): return
        old_canvas_x = self.canvas.canvasx(e.x)
        old_canvas_y = self.canvas.canvasy(e.y)
        self.scale = new_scale
        self._refresh_canvas()
        new_canvas_x = old_canvas_x * factor
        new_canvas_y = old_canvas_y * factor
        target_offset_x = new_canvas_x - e.x
        target_offset_y = new_canvas_y - e.y
        bbox = self.canvas.bbox(self.canvas_image)
        if bbox:
            img_w = bbox[2] - bbox[0]
            img_h = bbox[3] - bbox[1]
            if img_w > 0: self.canvas.xview_moveto(target_offset_x / img_w)
            if img_h > 0: self.canvas.yview_moveto(target_offset_y / img_h)

    def _auto_update_prosthesis(self, trigger_kp=None):
        if not trigger_kp: return
        children = Config.AUTO_PROSTHESIS_MAP.get(trigger_kp)
        if not children: return
        if trigger_kp not in self.runtime_kps: return
        res_data = self.runtime_kps[trigger_kp]
        is_active = (res_data['v'] > 0 and res_data['type'] != 2)

        for child_name in children:
            if child_name not in self.runtime_kps: continue
            child_data = self.runtime_kps[child_name]
            if child_data['v'] == 0 or child_data['type'] == 2:
                continue
            if is_active:
                if child_data['type'] == 0:
                    child_data['type'] = 1
            else:
                if child_data['type'] == 1:
                    child_data['type'] = 0

    def _goto_id(self):
        """根据 Annotation 的真实 ID 进行全量搜索跳转"""
        try:
            target_id_str = self.id_entry.get().strip()
            if not target_id_str: return

            target_id = int(target_id_str)
            found_idx = -1

            # 在任务列表中遍历寻找匹配的 ID
            for idx, ann in enumerate(self.data_mgr.task_list):
                if ann.get('id') == target_id:
                    found_idx = idx
                    break

            if found_idx != -1:
                # 保存当前状态并跳转
                self.data_mgr.save_current_state(self.current_index, self.runtime_kps, self.is_deleted)
                self.current_index = found_idx
                self._load_current_scene()
                # 提示一下找到了
                self.id_entry.config(bg="#e8f5e9")  # 成功变绿
                self.master.after(1000, lambda: self.id_entry.config(bg="white"))
            else:
                messagebox.showwarning("未找到", f"在当前数据集中找不到 ID 为 {target_id} 的标注。")
                self.id_entry.config(bg="#ffebee")  # 失败变红
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字 ID。")

    def _update_residual_visibility(self):
        RES_TO_ALL_CHILDREN = {
            "L-Elbow-Res-Above": ["left_elbow", "left_wrist", "L_Middle_Tip"],
            "R-Elbow-Res-Above": ["right_elbow", "right_wrist", "R_Middle_Tip"],
            "L-Elbow-Res-Below": ["left_wrist", "L_Middle_Tip"],
            "R-Elbow-Res-Below": ["right_wrist", "R_Middle_Tip"],
            "L-Knee-Res-Above": ["left_knee", "left_ankle", "L_Heel", "L_Toe_Tip"],
            "R-Knee-Res-Above": ["right_knee", "right_ankle", "R_Heel", "R_Toe_Tip"],
            "L-Knee-Res-Below": ["left_ankle", "L_Heel", "L_Toe_Tip"],
            "R-Knee-Res-Below": ["right_ankle", "R_Heel", "R_Toe_Tip"]
        }

        for res_kp, all_children in RES_TO_ALL_CHILDREN.items():
            if res_kp not in self.runtime_kps: continue
            res_data = self.runtime_kps[res_kp]
            found_flesh = False
            for child_kp in all_children:
                if child_kp not in self.runtime_kps: continue
                child_data = self.runtime_kps[child_kp]
                if child_data['v'] > 0 and child_data['type'] == 0:
                    found_flesh = True
                    break
            if found_flesh:
                if res_data['type'] == 2:
                    if res_data['v'] != 2:
                        res_data['v'] = 2

    def _update_conflict_log(self, conflicts):
        self.conflict_text.config(state=tk.NORMAL)
        self.conflict_text.delete("1.0", tk.END)
        if not conflicts:
            self.conflict_text.insert(tk.END, "No logic conflicts detected.\n(逻辑检测通过)")
            self.conflict_text.config(fg="green")
        else:
            self.conflict_text.config(fg="red")
            seen_messages = set()
            for i, (kp_name, msg) in enumerate(conflicts):
                clean_msg = msg.replace("\n", " - ")
                full_msg = f"[{kp_name}]: {clean_msg}"
                if full_msg not in seen_messages:
                    self.conflict_text.insert(tk.END, f"{len(seen_messages) + 1}. {full_msg}\n")
                    seen_messages.add(full_msg)
        self.conflict_text.config(state=tk.DISABLED)

    def _load_current_scene(self):
        ctx = self.data_mgr.get_context(self.current_index)
        if not ctx: return
        file_name = ctx['img_info'].get('file_name', 'Unknown')
        print(f"[{self.current_index + 1}] Loading Image: {file_name}")
        if hasattr(self, 'lbl_filename'): self.lbl_filename.config(text=f"File: {file_name}")
        self.raw_image = ImageOps.exif_transpose(Image.open(ctx['full_path']).convert("RGB"))

        # =========================================================
        # 1. 加载原始数据
        # =========================================================
        self.runtime_kps = {}
        ann, f_kps, f_t = ctx['original_ann'], ctx['original_ann'].get('keypoints', []), ctx['original_ann'].get(
            'keypoint_types', [])

        for i, name in enumerate(Config.KEYPOINT_NAMES):
            x, y, v = (f_kps[i * 3], f_kps[i * 3 + 1], f_kps[i * 3 + 2]) if i * 3 + 2 < len(f_kps) else (0, 0, 0)
            t = f_t[i] if i < len(f_t) else -1
            if v == -1: v = 2
            if t == -1: t = 0
            self.runtime_kps[name] = {"x": x, "y": y, "v": int(v), "type": int(t)}

        # =========================================================
        # 2. 【精准狙击修复】只修复有坐标的 Missing 点
        # =========================================================
        if not self.is_deleted:
            for kp_name in Config.RES_KPS:
                if kp_name in self.runtime_kps:
                    kp_data = self.runtime_kps[kp_name]

                    # 只有同时满足以下三个条件，才会被判定为 BUG 并修复：
                    # 1. 可见 (v > 0)
                    # 2. 类型是 Missing (type == 2)
                    # 3. 【核心条件】坐标不是 (0,0) -> 说明它物理上存在！
                    if kp_data['v'] > 0 and kp_data['type'] == 2:
                        if kp_data['x'] > 1 or kp_data['y'] > 1:
                            print(
                                f"Auto-fixing {kp_name}: Has coordinates ({kp_data['x']:.1f}, {kp_data['y']:.1f}) but Type=Missing -> Force Normal")
                            kp_data['type'] = 0

        # =========================================================
        # 3. 加载 Delta 修改 (你的手动修改永远是最高优先级)
        # =========================================================
        if ctx['changes']:
            if "__DELETED__" in ctx['changes']:
                pass
            else:
                for k, v in ctx['changes'].items():
                    if k in self.runtime_kps:
                        self.runtime_kps[k] = {"x": v[0], "y": v[1], "v": v[2], "type": v[3]}

        self.is_deleted = ctx.get('is_deleted', False)

        # =========================================================
        # 4. 后处理
        # =========================================================
        if not self.is_deleted:
            for res_kp_name in Config.RES_KPS:
                if res_kp_name in self.runtime_kps:
                    kp_data = self.runtime_kps[res_kp_name]
                    if kp_data['v'] > 0 and kp_data['type'] == 0:
                        self._auto_update_prosthesis(trigger_kp=res_kp_name)
            self._update_residual_visibility()

        self.scale = min(1150 / self.raw_image.size[0], 850 / self.raw_image.size[1], 1.0)
        self.lbl_info.config(text=f"Task: {self.current_index + 1}/{ctx['total']} | ID: {ann['id']}")
        self._update_goto_display()
        self._refresh_canvas()
        if not self.is_deleted:
            if self.active_kp_name not in Config.EDITABLE_KPS and Config.EDITABLE_KPS:
                self._set_tool(Config.EDITABLE_KPS[0])
            self._set_tool(self.active_kp_name)
    def _refresh_canvas(self):
        if not hasattr(self, 'raw_image') or not self.raw_image: return
        iw, ih = self.raw_image.size
        w, h = int(iw * self.scale), int(ih * self.scale)
        disp = self.raw_image.resize((w, h), Image.Resampling.BILINEAR)
        ctx = self.data_mgr.get_context(self.current_index)

        conflicts = []
        if not self.is_deleted:
            conflicts = self.data_mgr.check_logic_conflict(self.runtime_kps)

        self._update_conflict_log(conflicts)

        self.tk_img = self.visualizer.render(
            disp, self.runtime_kps, self.active_kp_name, self.scale,
            self.show_bbox_var.get(), self.show_skeleton_var.get(),
            self.show_points_var.get(), ctx['original_ann'].get('bbox'),
            self.is_deleted, conflicts
        )
        self.canvas.itemconfig(self.canvas_image, image=self.tk_img)
        self.canvas.config(scrollregion=(0, 0, w, h))
        if not self.is_deleted:
            conflict_names = set(c[0] for c in conflicts)
            for k, b in self.btns.items():
                bg = "white"
                if k == self.active_kp_name: bg = "#fa0"
                if k in conflict_names: bg = "red"
                b.config(bg=bg)

    def _set_tool(self, kp):
        if self.is_deleted: return
        self.active_kp_name = kp
        if kp in self.runtime_kps:
            self.type_var.set(self.runtime_kps[kp]['type'])
            self.vis_var.set(self.runtime_kps[kp]['v'])
        self._refresh_canvas()

    def _on_click(self, e):
        if self.is_deleted: return
        if self.active_kp_name not in Config.EDITABLE_KPS: return

        cx, cy = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        pt = self.runtime_kps[self.active_kp_name]

        v = self.vis_var.get()
        t = self.type_var.get()
        if v <= 0: v = 2

        pt.update({'x': cx / self.scale, 'y': cy / self.scale, 'v': v, 'type': t})

        self._auto_update_prosthesis(trigger_kp=self.active_kp_name)
        self._update_residual_visibility()
        self._refresh_canvas()

    def _on_attr_change(self):
        if self.is_deleted: return
        if self.active_kp_name not in Config.EDITABLE_KPS: return

        if self.active_kp_name in self.runtime_kps:
            new_vis = self.vis_var.get()
            new_type = self.type_var.get()

            self.runtime_kps[self.active_kp_name].update({'type': new_type, 'v': new_vis})
            if new_vis == 0:
                self.runtime_kps[self.active_kp_name].update({'x': 0.0, 'y': 0.0})

            self._auto_update_prosthesis(trigger_kp=self.active_kp_name)
            self._update_residual_visibility()
            self._refresh_canvas()

    def _toggle_delete(self):
        self.is_deleted = not self.is_deleted
        self._refresh_canvas()
        self.data_mgr.save_current_state(self.current_index, self.runtime_kps, self.is_deleted)

    def _next_img(self):
        self.data_mgr.save_current_state(self.current_index, self.runtime_kps, self.is_deleted)
        self.current_index = min(self.current_index + 1, len(self.data_mgr.task_list) - 1)
        self._load_current_scene()

    def _prev_img(self):
        self.data_mgr.save_current_state(self.current_index, self.runtime_kps, self.is_deleted)
        self.current_index = max(0, self.current_index - 1)
        self._load_current_scene()


if __name__ == "__main__":
    root = tk.Tk()
    app = LabelerApp(root)
    root.mainloop()