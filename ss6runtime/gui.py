
from __future__ import annotations

import json
import os
import queue
import re
import shutil
import sys
import tempfile
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .extractor import extract_bundle
from .batch import render_all_animations
from .spine_export import bundle_to_spine_frame_swap_all


class SS6SpineGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SS6 → Spine Toolkit v0.25")
        self.geometry("980x760")
        self.minsize(820, 650)

        self.msg_queue = queue.Queue()
        self.worker = None
        self.scan_manifest = None
        self.scan_dir = None

        self.bundle_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.setup_anim_var = tk.StringVar()
        self.setup_frame_var = tk.StringVar(value="0")
        self.include_var = tk.StringVar()
        self.exclude_var = tk.StringVar()
        self.dedupe_var = tk.BooleanVar(value=True)
        self.dedupe_tol_var = tk.StringVar(value="0.0001")
        self.export_fps_var = tk.StringVar(value="")
        self.frame_step_var = tk.StringVar(value="")
        self.mesh_v_flip_var = tk.BooleanVar(value=False)
        self.show_hidden_var = tk.BooleanVar(value=False)

        self.preview_filter_var = tk.StringVar()
        self.preview_scale_var = tk.StringVar(value="1")
        self.preview_max_frames_var = tk.StringVar(value="")
        self.preview_gif_var = tk.BooleanVar(value=True)

        self._build_ui()
        self.after(100, self._poll_queue)

    # ---------------- UI ----------------

    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        # Bundle selector
        files = ttk.LabelFrame(root, text="Character bundle", padding=10)
        files.pack(fill="x")

        ttk.Label(files, text="Bundle").grid(row=0, column=0, sticky="w", padx=(0,8), pady=4)
        ttk.Entry(files, textvariable=self.bundle_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(files, text="Browse…", command=self._browse_bundle).grid(row=0, column=2, padx=(8,0), pady=4)

        ttk.Label(files, text="Output").grid(row=1, column=0, sticky="w", padx=(0,8), pady=4)
        ttk.Entry(files, textvariable=self.output_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(files, text="Browse…", command=self._browse_output).grid(row=1, column=2, padx=(8,0), pady=4)

        files.columnconfigure(1, weight=1)

        actions = ttk.Frame(files)
        actions.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8,0))
        self.scan_btn = ttk.Button(actions, text="Scan animations", command=self._scan_bundle)
        self.scan_btn.pack(side="left")
        self.open_btn = ttk.Button(actions, text="Open output folder", command=self._open_output)
        self.open_btn.pack(side="left", padx=(8,0))

        # Main notebook
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, pady=(12,0))

        export_tab = ttk.Frame(nb, padding=12)
        preview_tab = ttk.Frame(nb, padding=12)
        info_tab = ttk.Frame(nb, padding=12)
        nb.add(export_tab, text="Spine export")
        nb.add(preview_tab, text="Python previews")
        nb.add(info_tab, text="Animations")

        self._build_export_tab(export_tab)
        self._build_preview_tab(preview_tab)
        self._build_info_tab(info_tab)

        # Log
        log_frame = ttk.LabelFrame(root, text="Log", padding=8)
        log_frame.pack(fill="both", expand=True, pady=(12,0))

        self.log = tk.Text(log_frame, height=10, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        status = ttk.Frame(root)
        status.pack(fill="x", pady=(8,0))
        self.progress = ttk.Progressbar(status, mode="indeterminate", length=160)
        self.progress.pack(side="left")
        ttk.Label(status, textvariable=self.status_var).pack(side="left", padx=(10,0))

    def _build_export_tab(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x")

        ttk.Label(top, text="Setup animation").grid(row=0, column=0, sticky="w", pady=4)
        self.setup_combo = ttk.Combobox(top, textvariable=self.setup_anim_var, state="normal")
        self.setup_combo.grid(row=0, column=1, sticky="ew", padx=(8,20), pady=4)

        ttk.Label(top, text="Setup frame").grid(row=0, column=2, sticky="w", pady=4)
        ttk.Entry(top, textvariable=self.setup_frame_var, width=8).grid(row=0, column=3, sticky="w", padx=(8,0), pady=4)

        ttk.Label(top, text="Include regex").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(top, textvariable=self.include_var).grid(row=1, column=1, sticky="ew", padx=(8,20), pady=4)

        ttk.Label(top, text="Exclude regex").grid(row=1, column=2, sticky="w", pady=4)
        ttk.Entry(top, textvariable=self.exclude_var).grid(row=1, column=3, sticky="ew", padx=(8,0), pady=4)

        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)

        opt = ttk.LabelFrame(parent, text="Compression / sampling", padding=10)
        opt.pack(fill="x", pady=(12,0))

        ttk.Checkbutton(opt, text="Geometry deduplication", variable=self.dedupe_var).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(opt, text="Tolerance").grid(row=0, column=1, sticky="e", padx=(16,4))
        ttk.Entry(opt, textvariable=self.dedupe_tol_var, width=12).grid(row=0, column=2, sticky="w")

        ttk.Label(opt, text="Export FPS").grid(row=1, column=0, sticky="w", pady=4)
        fps_box = ttk.Combobox(opt, textvariable=self.export_fps_var, values=["", "30", "20", "15", "12", "10"], width=10)
        fps_box.grid(row=1, column=1, sticky="w", padx=(16,4))
        ttk.Label(opt, text="blank = source FPS").grid(row=1, column=2, sticky="w")

        ttk.Label(opt, text="Frame step").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(opt, textvariable=self.frame_step_var, width=12).grid(row=2, column=1, sticky="w", padx=(16,4))
        ttk.Label(opt, text="blank = disabled; overrides Export FPS").grid(row=2, column=2, sticky="w")

        advanced = ttk.LabelFrame(parent, text="Advanced", padding=10)
        advanced.pack(fill="x", pady=(12,0))
        ttk.Checkbutton(advanced, text="Flip mesh V coordinate", variable=self.mesh_v_flip_var).pack(anchor="w")
        ttk.Checkbutton(advanced, text="Include SS6 hidden parts", variable=self.show_hidden_var).pack(anchor="w", pady=(4,0))

        note = ttk.Label(
            parent,
            text=(
                "Recommended: keep source FPS and tolerance 0.0001 first. "
                "After verifying quality, try 15 FPS or tolerance 0.001 for a smaller JSON."
            ),
            wraplength=760,
            justify="left"
        )
        note.pack(fill="x", pady=(14,0))

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=(18,0))
        self.export_btn = ttk.Button(buttons, text="Export all animations to Spine", command=self._export_all)
        self.export_btn.pack(side="left")
        ttk.Button(buttons, text="Reset export options", command=self._reset_export_options).pack(side="left", padx=(8,0))

    def _build_preview_tab(self, parent):
        grid = ttk.Frame(parent)
        grid.pack(fill="x")

        ttk.Label(grid, text="Animation filter").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(grid, textvariable=self.preview_filter_var).grid(row=0, column=1, sticky="ew", padx=(8,20), pady=5)
        ttk.Label(grid, text="regex; blank = all").grid(row=0, column=2, sticky="w")

        ttk.Label(grid, text="Scale").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(grid, textvariable=self.preview_scale_var, values=["0.5","1","1.5","2"], width=10).grid(row=1, column=1, sticky="w", padx=(8,20), pady=5)

        ttk.Label(grid, text="Max frames / animation").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(grid, textvariable=self.preview_max_frames_var, width=12).grid(row=2, column=1, sticky="w", padx=(8,20), pady=5)

        ttk.Checkbutton(grid, text="Generate GIF", variable=self.preview_gif_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8,0))
        grid.columnconfigure(1, weight=1)

        ttk.Label(
            parent,
            text="Preview uses the current native2d + Y-up Python renderer and automatic framing.",
            wraplength=760
        ).pack(fill="x", pady=(16,0))

        self.preview_btn = ttk.Button(parent, text="Render selected/all animations", command=self._render_previews)
        self.preview_btn.pack(anchor="w", pady=(18,0))

    def _build_info_tab(self, parent):
        bar = ttk.Frame(parent)
        bar.pack(fill="x")
        ttk.Label(bar, text="Animations found in the selected main DataAnimation").pack(side="left")

        cols=("index","name")
        self.anim_tree = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        self.anim_tree.heading("index", text="#")
        self.anim_tree.heading("name", text="Animation")
        self.anim_tree.column("index", width=60, anchor="center", stretch=False)
        self.anim_tree.column("name", width=420)
        self.anim_tree.pack(fill="both", expand=True, pady=(10,0))

        self.info_label = ttk.Label(parent, text="Scan a bundle to populate this list.", wraplength=760)
        self.info_label.pack(fill="x", pady=(10,0))

    # ---------------- Helpers ----------------

    def _browse_bundle(self):
        p = filedialog.askopenfilename(
            title="Select Unity/SS6 bundle",
            filetypes=[
                ("Bundle files", "*.bin *.*"),
                ("All files", "*.*")
            ]
        )
        if p:
            self.bundle_var.set(p)
            if not self.output_var.get():
                stem=Path(p).stem
                self.output_var.set(str(Path(p).parent / f"{stem}_spine"))

    def _browse_output(self):
        p=filedialog.askdirectory(title="Select output directory")
        if p:
            self.output_var.set(p)

    def _open_output(self):
        p=Path(self.output_var.get().strip())
        if not p.exists():
            messagebox.showinfo("Output", "The output directory does not exist yet.")
            return
        try:
            if os.name=="nt":
                os.startfile(str(p))
            elif sys.platform=="darwin":
                import subprocess
                subprocess.Popen(["open",str(p)])
            else:
                import subprocess
                subprocess.Popen(["xdg-open",str(p)])
        except Exception as e:
            messagebox.showerror("Open folder", str(e))

    def _append_log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", str(msg).rstrip()+"\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, busy, text=None):
        for b in (self.scan_btn,self.export_btn,self.preview_btn):
            b.configure(state="disabled" if busy else "normal")
        if busy:
            self.progress.start(10)
        else:
            self.progress.stop()
        self.status_var.set(text or ("Working…" if busy else "Ready"))

    def _run_worker(self, label, fn):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Busy", "Another task is still running.")
            return
        self._set_busy(True,label)
        self._append_log(f"== {label} ==")

        def run():
            try:
                result=fn()
                self.msg_queue.put(("success",label,result))
            except Exception:
                self.msg_queue.put(("error",label,traceback.format_exc()))

        self.worker=threading.Thread(target=run,daemon=True)
        self.worker.start()

    def _poll_queue(self):
        try:
            while True:
                kind,label,payload=self.msg_queue.get_nowait()
                if kind=="success":
                    self._append_log(json.dumps(payload,ensure_ascii=False,indent=2) if isinstance(payload,(dict,list)) else str(payload))
                    self._set_busy(False,f"{label}: done")
                    if label=="Scan animations":
                        self._apply_scan(payload)
                    messagebox.showinfo("Done", f"{label} completed.")
                else:
                    self._append_log(payload)
                    self._set_busy(False,f"{label}: failed")
                    messagebox.showerror("Error", payload)
        except queue.Empty:
            pass
        self.after(100,self._poll_queue)

    def _validate_paths(self):
        bundle=Path(self.bundle_var.get().strip())
        out=Path(self.output_var.get().strip())
        if not bundle.is_file():
            raise ValueError("Please select a valid bundle file.")
        if not str(out):
            raise ValueError("Please choose an output directory.")
        return bundle,out

    # ---------------- Actions ----------------

    def _scan_bundle(self):
        try:
            bundle,out=self._validate_paths()
        except Exception as e:
            messagebox.showerror("Input",str(e));return

        scan_dir=out/"_gui_scan"
        self.scan_dir=scan_dir

        def job():
            if scan_dir.exists():
                shutil.rmtree(scan_dir)
            manifest=extract_bundle(bundle,scan_dir,all_animations=True)
            return manifest

        self._run_worker("Scan animations",job)

    def _apply_scan(self, manifest):
        self.scan_manifest=manifest
        for item in self.anim_tree.get_children():
            self.anim_tree.delete(item)

        anims=manifest.get("available_animations",[]) or []
        for a in anims:
            self.anim_tree.insert("", "end", values=(a.get("index",""),a.get("name","")))

        names=[str(a.get("name","")) for a in anims]
        self.setup_combo["values"]=names

        preferred=None
        for target in ("mot_stand","stand","idle","mot_ready","ready","mot_action_01"):
            for n in names:
                if n.lower()==target:
                    preferred=n;break
            if preferred:break
        if preferred:
            self.setup_anim_var.set(preferred)
        elif names and not self.setup_anim_var.get():
            self.setup_anim_var.set(names[0])

        da=manifest.get("selected_data_animation") or {}
        self.info_label.configure(
            text=(
                f"DataAnimation: {da.get('name','?')}   |   "
                f"Parts: {manifest.get('part_count','?')}   |   "
                f"Textures: {manifest.get('texture_count','?')}   |   "
                f"Animations: {len(anims)}"
            )
        )

    def _parse_export_options(self):
        setup_frame=int(self.setup_frame_var.get().strip() or "0")
        tol=float(self.dedupe_tol_var.get().strip() or "0.0001")

        efps_txt=self.export_fps_var.get().strip()
        export_fps=float(efps_txt) if efps_txt else None
        if export_fps is not None and export_fps<=0:
            raise ValueError("Export FPS must be positive.")

        step_txt=self.frame_step_var.get().strip()
        frame_step=int(step_txt) if step_txt else None
        if frame_step is not None and frame_step<1:
            raise ValueError("Frame step must be >= 1.")

        include=self.include_var.get().strip() or None
        exclude=self.exclude_var.get().strip() or None
        if include:
            re.compile(include)
        if exclude:
            re.compile(exclude)

        return {
            "setup_frame":setup_frame,
            "dedupe_tolerance":tol,
            "export_fps":export_fps,
            "frame_step":frame_step,
            "include":include,
            "exclude":exclude,
        }

    def _export_all(self):
        try:
            bundle,out=self._validate_paths()
            opts=self._parse_export_options()
        except Exception as e:
            messagebox.showerror("Options",str(e));return

        setup_anim=self.setup_anim_var.get().strip() or None

        def job():
            out.mkdir(parents=True,exist_ok=True)
            return bundle_to_spine_frame_swap_all(
                bundle,
                out,
                setup_animation_name=setup_anim,
                setup_frame=opts["setup_frame"],
                include=opts["include"],
                exclude=opts["exclude"],
                mesh_v_flip=self.mesh_v_flip_var.get(),
                show_hidden=self.show_hidden_var.get(),
                dedupe=self.dedupe_var.get(),
                dedupe_tolerance=opts["dedupe_tolerance"],
                export_fps=opts["export_fps"],
                frame_step=opts["frame_step"],
            )

        self._run_worker("Spine export",job)

    def _render_previews(self):
        try:
            bundle,out=self._validate_paths()
            scale=float(self.preview_scale_var.get().strip() or "1")
            if scale<=0:
                raise ValueError("Preview scale must be positive.")
            max_txt=self.preview_max_frames_var.get().strip()
            max_frames=int(max_txt) if max_txt else None
            if max_frames is not None and max_frames<1:
                raise ValueError("Max frames must be >= 1.")
            filt=self.preview_filter_var.get().strip() or None
            if filt:
                re.compile(filt)
        except Exception as e:
            messagebox.showerror("Preview options",str(e));return

        preview_out=out/"python_previews"

        def job():
            preview_out.mkdir(parents=True,exist_ok=True)
            return render_all_animations(
                bundle,
                preview_out,
                mode="native2d",
                coordinate_mode="yup",
                scale=scale,
                make_gif=self.preview_gif_var.get(),
                max_frames=max_frames,
                animation_filter=filt,
                png_compression=1,
                auto_frame=True,
            )

        self._run_worker("Render previews",job)

    def _reset_export_options(self):
        self.setup_frame_var.set("0")
        self.include_var.set("")
        self.exclude_var.set("")
        self.dedupe_var.set(True)
        self.dedupe_tol_var.set("0.0001")
        self.export_fps_var.set("")
        self.frame_step_var.set("")
        self.mesh_v_flip_var.set(False)
        self.show_hidden_var.set(False)


def main():
    app=SS6SpineGUI()
    app.mainloop()


if __name__=="__main__":
    main()
