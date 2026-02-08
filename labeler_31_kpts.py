import json
import os
import tkinter as tk
from tkinter import messagebox, filedialog
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw, ImageOps


# =================CONFIGURATION=================
class Config:
    WINDOW_WIDTH = 1600
    WINDOW_HEIGHT = 900

    KEYPOINT_NAMES = [
        "nose", "left_eye", "right_eye", "left_ear", "right_ear",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist",
        "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle",
        "L_Middle_Tip", "R_Middle_Tip", "L_Heel", "R_Heel", "L_Toe_Tip", "R_Toe_Tip",
        "L-Elbow-Res-Above", "R-Elbow-Res-Above", "L-Elbow-Res-Below", "R-Elbow-Res-Below",
        "L-Knee-Res-Above", "R-Knee-Res-Above", "L-Knee-Res-Below", "R-Knee-Res-Below"
    ]

    EDITABLE_KPS = [
        "left_elbow", "right_elbow", "left_knee", "right_knee",
        "left_wrist", "right_wrist", "left_ankle", "right_ankle",
        "L_Middle_Tip", "R_Middle_Tip", "L_Heel", "R_Heel", "L_Toe_Tip", "R_Toe_Tip",
        "L-Elbow-Res-Above", "R-Elbow-Res-Above", "L-Elbow-Res-Below", "R-Elbow-Res-Below",
        "L-Knee-Res-Above", "R-Knee-Res-Above", "L-Knee-Res-Below", "R-Knee-Res-Below"
    ]

    TIPS_L = ["left_elbow", "left_wrist", "L_Middle_Tip", "left_knee", "left_ankle", "L_Heel", "L_Toe_Tip"]
    TIPS_R = ["right_elbow", "right_wrist", "R_Middle_Tip", "right_knee", "right_ankle", "R_Heel", "R_Toe_Tip"]
    RES_L = ["L-Elbow-Res-Above", "L-Elbow-Res-Below", "L-Knee-Res-Above", "L-Knee-Res-Below"]
    RES_R = ["R-Elbow-Res-Above", "R-Elbow-Res-Below", "R-Knee-Res-Above", "R-Knee-Res-Below"]

    BBOX_COLOR, SKELETON_COLOR = "#FFFF00", "#0000FF"
    SKELETON_LINKS = [
        (0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12), (11, 12),
        (11, 13), (13, 15), (12, 14), (14, 16), (9, 17), (10, 18), (15, 19), (15, 21), (16, 20), (16, 22),
        (5, 23), (6, 24), (7, 25), (8, 26), (11, 27), (12, 28), (13, 29), (14, 30)
    ]
    TYPE_NAMES = {0: "Normal", 1: "Prosthesis", 2: "Missing", -1: "Unset"}
    VIS_NAMES = {0: "无(0)", 1: "遮挡(1)", 2: "可见(2)", -1: "Init(-1)"}

    # 级联关系表
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


# =================VISUALIZER=================
class ImageVisualizer:
    def render(self, base_img, runtime_kps, active_kp, scale, show_bbox, show_skel, show_pts, bbox, is_deleted):
        img = base_img.copy()
        draw = ImageDraw.Draw(img)
        s = lambda v: v * scale

        if is_deleted:
            w, h = img.size
            draw.line([(0, 0), (w, h)], fill="red", width=5)
            draw.line([(0, h), (w, 0)], fill="red", width=5)
            try:
                draw.text((20, 20), "OBJECT DELETED", fill="red")
            except:
                pass
            return ImageTk.PhotoImage(img)

        if show_bbox and bbox:
            draw.rectangle([s(bbox[0]), s(bbox[1]), s(bbox[0] + bbox[2]), s(bbox[1] + bbox[3])],
                           outline=Config.BBOX_COLOR, width=2)
        if show_skel:
            for i1, i2 in Config.SKELETON_LINKS:
                p1, p2 = runtime_kps.get(Config.KEYPOINT_NAMES[i1]), runtime_kps.get(Config.KEYPOINT_NAMES[i2])
                if p1 and p2 and p1['x'] > 1 and p2['x'] > 1 and p1['v'] > 0 and p2['v'] > 0:
                    draw.line([(s(p1['x']), s(p1['y'])), (s(p2['x']), s(p2['y']))], fill=Config.SKELETON_COLOR, width=2)
        if show_pts:
            for name, d in runtime_kps.items():
                if d['v'] == 0 or d['x'] <= 1: continue
                is_ed = name in Config.EDITABLE_KPS
                if not is_ed and not show_skel: continue
                color = "#00FFFF" if "left" in name or name.startswith("L") else "#FF00FF"
                if name == active_kp: color = "#FFFF00"
                r = 7 if name == active_kp else (4 if is_ed else 2)
                draw.ellipse([s(d['x']) - r, s(d['y']) - r, s(d['x']) + r, s(d['y']) + r], fill=color,
                             outline="white" if is_ed else None)
                if is_ed:
                    info_txt = f"T:{d['type']} V:{d['v']}"
                    text_x, text_y = s(d['x']) + 10, s(d['y']) - 10
                    try:
                        draw.text((text_x, text_y), info_txt, fill="yellow", stroke_width=1, stroke_fill="black")
                    except:
                        draw.text((text_x, text_y), info_txt, fill="yellow")
        return ImageTk.PhotoImage(img)


# =================APP=================
class LabelerApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Amputee Pose Labeler Pro (Smart Logic)")
        self.master.geometry(f"{Config.WINDOW_WIDTH}x{Config.WINDOW_HEIGHT}")
        self.data_mgr, self.visualizer = DataManager(), ImageVisualizer()
        self.current_index, self.scale, self.runtime_kps = 0, 1.0, {}
        self.active_kp_name = Config.EDITABLE_KPS[0]
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
        f_img = tk.Frame(main, bg="#333");
        main.add(f_img, width=900, minsize=100, stretch="always")
        self.h_scr = tk.Scrollbar(f_img, orient=tk.HORIZONTAL);
        self.v_scr = tk.Scrollbar(f_img, orient=tk.VERTICAL)
        self.canvas = tk.Canvas(f_img, bg="#222", cursor="cross", xscrollcommand=self.h_scr.set,
                                yscrollcommand=self.v_scr.set)
        self.h_scr.config(command=self.canvas.xview);
        self.v_scr.config(command=self.canvas.yview)
        self.v_scr.pack(side=tk.RIGHT, fill=tk.Y);
        self.h_scr.pack(side=tk.BOTTOM, fill=tk.X);
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas_image = self.canvas.create_image(0, 0, anchor="nw")

        ctrl_outer = tk.Frame(main, bg="#f0f0f0");
        main.add(ctrl_outer, minsize=400, stretch="never")
        ctrl_canvas = tk.Canvas(ctrl_outer, bg="#f0f0f0", highlightthickness=0)
        ctrl_v_scr = tk.Scrollbar(ctrl_outer, orient=tk.VERTICAL, command=ctrl_canvas.yview)
        self.ctrl_inner = tk.Frame(ctrl_canvas, bg="#f0f0f0", padx=10, pady=10)
        ctrl_canvas.create_window((0, 0), window=self.ctrl_inner, anchor="nw")
        ctrl_canvas.config(yscrollcommand=ctrl_v_scr.set)
        ctrl_v_scr.pack(side=tk.RIGHT, fill=tk.Y);
        ctrl_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.ctrl_inner.bind("<Configure>", lambda e: ctrl_canvas.configure(scrollregion=ctrl_canvas.bbox("all")))

        nav = tk.Frame(self.ctrl_inner, bg="#ddd", padx=5, pady=5);
        nav.pack(fill=tk.X, pady=(0, 10))
        self.lbl_info = tk.Label(nav, text="Task Info", bg="#ddd", font=("Arial", 11, "bold"));
        self.lbl_info.pack(pady=5)
        tk.Button(nav, text="DELETE OBJECT (Del)", command=self._toggle_delete, bg="#f44", fg="white",
                  font=("Arial", 9, "bold")).pack(fill=tk.X, pady=5, padx=20)
        btn_f = tk.Frame(nav, bg="#ddd");
        btn_f.pack(fill=tk.X)
        tk.Button(btn_f, text="< PREV (A)", command=self._prev_img, height=2, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_f, text="NEXT (D) >", command=self._next_img, bg="#8f8", height=2, width=15).pack(side=tk.RIGHT,
                                                                                                        padx=5)

        attr = tk.LabelFrame(self.ctrl_inner, text="Attributes", bg="#eee", padx=10, pady=5,
                             font=("Arial", 10, "bold"));
        attr.pack(fill=tk.X, pady=(0, 15))
        f_tog = tk.Frame(attr, bg="#eee");
        f_tog.pack(fill=tk.X, pady=2)
        for t, v in [("BBox", self.show_bbox_var), ("Skel", self.show_skeleton_var), ("Pts", self.show_points_var)]:
            tk.Checkbutton(f_tog, text=t, variable=v, command=self._refresh_canvas, bg="#eee", font=("Arial", 9)).pack(
                side=tk.LEFT, padx=5)
        f_tv = tk.Frame(attr, bg="#eee");
        f_tv.pack(fill=tk.X)
        tk.Label(f_tv, text="TYPE:", font=("Arial", 8, "bold"), bg="#eee").grid(row=0, column=0, sticky="w")
        tk.Label(f_tv, text="VIS:", font=("Arial", 8, "bold"), bg="#eee").grid(row=1, column=0, sticky="w")
        f_t_opts = tk.Frame(f_tv, bg="#eee");
        f_t_opts.grid(row=0, column=1, sticky="w")
        for v, n in Config.TYPE_NAMES.items(): tk.Radiobutton(f_t_opts, text=n, variable=self.type_var, value=v,
                                                              command=self._on_attr_change, bg="#eee").pack(
            side=tk.LEFT)
        f_v_opts = tk.Frame(f_tv, bg="#eee");
        f_v_opts.grid(row=1, column=1, sticky="w")
        for v, n in Config.VIS_NAMES.items(): tk.Radiobutton(f_v_opts, text=n, variable=self.vis_var, value=v,
                                                             command=self._on_attr_change, bg="#eee").pack(side=tk.LEFT)

        kp_frame = tk.LabelFrame(self.ctrl_inner, text="Keypoints (4 Cols)", bg="#f0f0f0", font=("Arial", 10, "bold"));
        kp_frame.pack(fill=tk.BOTH, expand=True)
        self.btns = {}

        def add_grp_col(parent, title, klist, color, col_idx):
            tk.Label(parent, text=title, bg=color, font=("Arial", 9, "bold"), pady=3).grid(row=0, column=col_idx,
                                                                                           sticky="ew", padx=2,
                                                                                           pady=(5, 5))
            for i, k in enumerate(klist):
                txt = k.replace("left_", "L_").replace("right_", "R_").replace("-Res-", "_")
                b = tk.Button(parent, text=txt, font=("Arial", 8), bg="white", width=14,
                              command=lambda x=k: self._set_tool(x))
                b.grid(row=i + 1, column=col_idx, sticky="ew", padx=2, pady=1);
                self.btns[k] = b

        add_grp_col(kp_frame, "Tips L", Config.TIPS_L, "#eef", 0);
        add_grp_col(kp_frame, "Tips R", Config.TIPS_R, "#fee", 1)
        add_grp_col(kp_frame, "Res L", Config.RES_L, "#e8f4f8", 2);
        add_grp_col(kp_frame, "Res R", Config.RES_R, "#f8f4e8", 3)
        for c in range(4): kp_frame.grid_columnconfigure(c, weight=1)

        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<MouseWheel>", self._on_zoom)
        self.canvas.bind("<Button-2>", lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind("<B2-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        self.master.bind("a", lambda e: self._prev_img());
        self.master.bind("d", lambda e: self._next_img())
        self.master.bind("q", lambda e: self._quick(self.type_var, 0));
        self.master.bind("w", lambda e: self._quick(self.type_var, 1));
        self.master.bind("e", lambda e: self._quick(self.type_var, 2))
        self.master.bind("z", lambda e: self._quick(self.vis_var, 0));
        self.master.bind("x", lambda e: self._quick(self.vis_var, 1));
        self.master.bind("c", lambda e: self._quick(self.vis_var, 2))
        self.master.bind("<Delete>", lambda e: self._toggle_delete())

    def _quick(self, var, val):
        var.set(val); self._on_attr_change()

    def _on_zoom(self, e):
        # 1. 确定缩放系数 (Factor)
        if e.delta > 0:
            factor = 1.2
        elif e.delta < 0:
            factor = 0.8
        else:
            return

        new_scale = self.scale * factor

        # 2. 限制缩放范围
        if not (0.1 < new_scale < 20.0):
            return

        # 3. 【核心逻辑】获取鼠标在 Canvas 内容中的绝对坐标（缩放前）
        # canvasx/y 将屏幕坐标 (e.x) 转换为包含滚动偏移量的画布坐标
        old_canvas_x = self.canvas.canvasx(e.x)
        old_canvas_y = self.canvas.canvasy(e.y)

        # 4. 更新 Scale 并重绘图片 (此时 Canvas 的 scrollregion 大小会发生变化)
        self.scale = new_scale
        self._refresh_canvas()

        # 5. 计算该点在缩放后的新位置
        # 因为图片是以 (0,0) 为原点重绘的，所以新坐标 = 旧坐标 * 缩放系数
        new_canvas_x = old_canvas_x * factor
        new_canvas_y = old_canvas_y * factor

        # 6. 计算新的滚动条位置
        # 目标：让 new_canvas_x 在屏幕上的位置依然是 e.x
        # 此时 Canvas 左上角（Scroll 0点）应该在：new_canvas_x - e.x
        target_offset_x = new_canvas_x - e.x
        target_offset_y = new_canvas_y - e.y

        # 7. 应用滚动 (xview_moveto 需要 0.0-1.0 的比例)
        # 获取新图像的实际宽高
        bbox = self.canvas.bbox(self.canvas_image)
        if bbox:
            img_w = bbox[2] - bbox[0]
            img_h = bbox[3] - bbox[1]

            if img_w > 0:
                self.canvas.xview_moveto(target_offset_x / img_w)
            if img_h > 0:
                self.canvas.yview_moveto(target_offset_y / img_h)

    def _auto_update_prosthesis(self):
        # 1. 残肢点本身是 Normal (0)
        # 2. 残肢点之下的点是 Prosthesis (1)
        for res_kp, children in Config.AUTO_PROSTHESIS_MAP.items():
            if res_kp in self.runtime_kps:
                res_data = self.runtime_kps[res_kp]
                if res_data['v'] > 0:
                    res_data['type'] = 0  # 自身为 Normal
                    for child_name in children:
                        if child_name in self.runtime_kps:
                            child_data = self.runtime_kps[child_name]
                            if child_data['v'] > 0:
                                child_data['type'] = 1  # 下游为 Prosthesis

    def _load_current_scene(self):
        ctx = self.data_mgr.get_context(self.current_index)
        if not ctx: return
        self.raw_image = ImageOps.exif_transpose(Image.open(ctx['full_path']).convert("RGB"))
        self.runtime_kps = {}
        ann, f_kps, f_t = ctx['original_ann'], ctx['original_ann'].get('keypoints', []), ctx['original_ann'].get(
            'keypoint_types', [])
        for i, name in enumerate(Config.KEYPOINT_NAMES):
            x, y, v = (f_kps[i * 3], f_kps[i * 3 + 1], f_kps[i * 3 + 2]) if i * 3 + 2 < len(f_kps) else (0, 0, 0)
            t = f_t[i] if i < len(f_t) else -1
            self.runtime_kps[name] = {"x": x, "y": y, "v": int(v), "type": int(t)}
        if ctx['changes']:
            if "__DELETED__" in ctx['changes']:
                pass
            else:
                for k, v in ctx['changes'].items():
                    if k in self.runtime_kps: self.runtime_kps[k] = {"x": v[0], "y": v[1], "v": v[2], "type": v[3]}

        self.is_deleted = ctx.get('is_deleted', False)
        if not self.is_deleted: self._auto_update_prosthesis()
        self.scale = min(1150 / self.raw_image.size[0], 850 / self.raw_image.size[1], 1.0)
        self.lbl_info.config(text=f"Task: {self.current_index + 1}/{ctx['total']} | ID: {ann['id']}")
        if self.is_deleted:
            self._refresh_canvas()
        else:
            self._set_tool(self.active_kp_name)

    def _refresh_canvas(self):
        if not self.raw_image: return
        iw, ih = self.raw_image.size
        w, h = int(iw * self.scale), int(ih * self.scale)
        disp = self.raw_image.resize((w, h), Image.Resampling.BILINEAR)
        ctx = self.data_mgr.get_context(self.current_index)
        self.tk_img = self.visualizer.render(disp, self.runtime_kps, self.active_kp_name, self.scale,
                                             self.show_bbox_var.get(), self.show_skeleton_var.get(),
                                             self.show_points_var.get(), ctx['original_ann'].get('bbox'),
                                             self.is_deleted)
        self.canvas.itemconfig(self.canvas_image, image=self.tk_img)
        self.canvas.config(scrollregion=(0, 0, w, h))
        if not self.is_deleted:
            for k, b in self.btns.items(): b.config(bg="#fa0" if k == self.active_kp_name else "white")

    def _set_tool(self, kp):
        if self.is_deleted: return
        self.active_kp_name = kp;
        self.type_var.set(self.runtime_kps[kp]['type']);
        self.vis_var.set(self.runtime_kps[kp]['v']);
        self._refresh_canvas()

    def _on_click(self, e):
        if self.is_deleted: return
        cx, cy = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        pt = self.runtime_kps[self.active_kp_name]
        pt['x'], pt['y'] = cx / self.scale, cy / self.scale
        if self.vis_var.get() <= 0: self.vis_var.set(2)
        pt['v'], pt['type'] = self.vis_var.get(), self.type_var.get()
        self._auto_update_prosthesis()
        self._refresh_canvas()

    def _on_attr_change(self):
        if self.is_deleted: return
        if self.active_kp_name in self.runtime_kps:
            new_vis = self.vis_var.get()
            self.runtime_kps[self.active_kp_name].update({'type': self.type_var.get(), 'v': new_vis})
            if new_vis == 0: self.runtime_kps[self.active_kp_name].update({'x': 0.0, 'y': 0.0})
            self._auto_update_prosthesis()
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
    root = tk.Tk();
    app = LabelerApp(root);
    root.mainloop()