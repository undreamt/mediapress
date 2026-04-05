"""File table widget using Treeview for fast rendering."""

import customtkinter as ctk
import tkinter as tk
import tkinter.ttk as ttk

from ..constants import ROTATE_OPTIONS
from ..scanner import _determine_video_status

COL_IDS    = ["include", "num", "filename", "relpath", "filetype",
               "format", "resolution", "bitrate", "status", "rotate"]
COLUMNS    = ["Include", "#", "Filename", "Relative Path", "Type",
               "Current Format", "Resolution", "Bitrate", "Status", "Rotate"]
COL_WIDTHS = [52, 40, 180, 160, 140, 160, 100, 100, 200, 160]


def _apply_treeview_theme(tree_widget):
    """Style the Treeview to match the current CTk appearance mode."""
    try:
        mode = ctk.get_appearance_mode()
    except Exception:
        mode = "Dark"
    is_dark = mode in ("Dark",) or (mode == "System")

    bg      = "#1e1e1e" if is_dark else "#f0f0f0"
    fg      = "#e0e0e0" if is_dark else "#1a1a1a"
    sel_bg  = "#2d5a8e" if is_dark else "#4a90d9"
    hdr_bg  = "#2b2b2b" if is_dark else "#d0d0d0"
    odd_bg  = "#252525" if is_dark else "#f5f5f5"
    even_bg = "#1e1e1e" if is_dark else "#ebebeb"

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("MediaPress.Treeview",
                    background=bg,
                    foreground=fg,
                    fieldbackground=bg,
                    rowheight=26,
                    borderwidth=0,
                    font=("Segoe UI", 10))
    style.configure("MediaPress.Treeview.Heading",
                    background=hdr_bg,
                    foreground=fg,
                    relief="flat",
                    font=("Segoe UI", 10, "bold"))
    style.map("MediaPress.Treeview",
              background=[("selected", sel_bg)],
              foreground=[("selected", "white")])

    try:
        tree_widget.tag_configure("odd",       background=odd_bg,  foreground=fg)
        tree_widget.tag_configure("even",      background=even_bg, foreground=fg)
        tree_widget.tag_configure("compress",  foreground="#e07840")
        tree_widget.tag_configure("copy",      foreground="#40c070")
        tree_widget.tag_configure("remux",     foreground="#4090d0")
        tree_widget.tag_configure("skip",      foreground="#aaaaaa")
        tree_widget.tag_configure("unsupport", foreground="#666666")
        tree_widget.tag_configure("dim",       foreground="#555555")
    except Exception:
        pass


class FileTableWidget(tk.Frame):
    """Treeview-based file table — fast, properly aligned, resizable columns."""

    def __init__(self, parent, **kwargs):
        # Use plain tk.Frame to avoid CTk canvas redraws on every window resize
        kwargs.pop("fg_color", None)
        super().__init__(parent, **kwargs)
        self.records = []
        self._iid_to_idx = {}           # iid string → index into self.records
        self._on_rotate_change = None   # callback set by MediaPressApp
        self._overlay = None            # floating CTkOptionMenu for rotate
        self._build_ui()

    def _build_ui(self):
        # Plain tk.Frame so scrollbar docks flush with no CTk padding
        container = tk.Frame(self, bg="#1e1e1e")
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            container,
            columns=COL_IDS,
            show="headings",
            selectmode="none",
            style="MediaPress.Treeview",
        )

        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        for col_id, col_name, width in zip(COL_IDS, COLUMNS, COL_WIDTHS):
            self.tree.heading(col_id, text=col_name, anchor="w")
            self.tree.column(col_id, width=width, minwidth=36, stretch=False, anchor="w")

        _apply_treeview_theme(self.tree)

        self.tree.bind("<ButtonPress-1>", self._on_click)
        self.tree.bind("<MouseWheel>", self._dismiss_overlay)

    def _status_tag(self, status):
        s = status.lower()
        if "compress" in s:
            return "compress"
        if "remux" in s:
            return "remux"
        if "copy" in s:
            return "copy"
        if "unsupported" in s:
            return "unsupport"
        if "skip" in s:
            return "skip"
        return ""

    def clear(self):
        self._dismiss_overlay()
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.records = []
        self._iid_to_idx = {}

    def load_records(self, records):
        self.clear()
        self.records = list(records)
        for idx, rec in enumerate(self.records):
            self._iid_to_idx[str(idx)] = idx
            self._insert_row(idx, rec)

    def _insert_row(self, idx, rec):
        include_glyph = "☑" if rec.enabled else "☐"
        rotate_text   = rec.rotation if rec.show_rotate else "—"
        base_tag = "even" if idx % 2 == 0 else "odd"
        status_tag = self._status_tag(rec.status)
        tags = (base_tag, status_tag) if status_tag else (base_tag,)

        self.tree.insert(
            "", "end",
            iid=str(idx),
            values=(
                include_glyph,
                str(idx + 1),
                rec.filename,
                rec.rel_path,
                rec.file_type,
                rec.current_format,
                rec.resolution,
                rec.bitrate_display,
                rec.status,
                rotate_text,
            ),
            tags=tags,
        )

    def _on_click(self, event):
        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if not row:
            self._dismiss_overlay()
            return

        idx = self._iid_to_idx.get(row)
        if idx is None or idx >= len(self.records):
            return
        rec = self.records[idx]

        if col == "#1":      # Include column
            rec.enabled = not rec.enabled
            self.tree.set(row, "include", "☑" if rec.enabled else "☐")
            # Dim excluded rows so the visual state is unambiguous
            base_tag = "even" if idx % 2 == 0 else "odd"
            st = self._status_tag(rec.status)
            dim = () if rec.enabled else ("dim",)
            self.tree.item(row, tags=(base_tag, st) + dim if st else (base_tag,) + dim)
            if self._on_rotate_change:
                self._on_rotate_change()

        elif col == "#10":   # Rotate column
            if rec.show_rotate:
                self._show_rotate_overlay(row, rec, idx)
            else:
                self._dismiss_overlay()
        else:
            self._dismiss_overlay()

    def _show_rotate_overlay(self, iid, rec, idx):
        """Float a CTkOptionMenu over the rotate cell."""
        self._dismiss_overlay()
        bbox = self.tree.bbox(iid, column="rotate")
        if not bbox:
            return
        x, y, w, h = bbox
        # Offset by the tree widget's position within this CTkFrame
        tx = self.tree.winfo_x()
        ty = self.tree.winfo_y()

        var = tk.StringVar(value=rec.rotation)

        def on_select(val):
            rec.rotation = val
            self.tree.set(iid, "rotate", val)
            self._dismiss_overlay()
            if rec.file_type in ("Video", "Motion Photo (video)") and rec.probe_info:
                _determine_video_status(rec, rec.probe_info)
                self.tree.set(iid, "status", rec.status)
                base_tag = "even" if idx % 2 == 0 else "odd"
                st = self._status_tag(rec.status)
                self.tree.item(iid, tags=(base_tag, st) if st else (base_tag,))
            if self._on_rotate_change:
                self._on_rotate_change()

        overlay = ctk.CTkOptionMenu(
            self,
            values=ROTATE_OPTIONS,
            variable=var,
            command=on_select,
            font=ctk.CTkFont(size=11),
            dynamic_resizing=False,
        )
        overlay.place(x=tx + x, y=ty + y, width=max(w, 160), height=max(h, 28))
        self._overlay = overlay

    def _dismiss_overlay(self, event=None):
        if self._overlay:
            try:
                self._overlay.place_forget()
                self._overlay.destroy()
            except Exception:
                pass
            self._overlay = None

    def update_row_status(self, idx, status, result=""):
        """Update status cell during a processing run (called via self.after)."""
        try:
            iid = str(idx)
            text = result if result else status
            self.tree.set(iid, "status", text)
            base_tag = "even" if idx % 2 == 0 else "odd"
            st = self._status_tag(status)
            self.tree.item(iid, tags=(base_tag, st) if st else (base_tag,))
        except Exception:
            pass

    def select_all(self):
        for rec in self.records:
            rec.enabled = True
        for iid in self.tree.get_children():
            self.tree.set(iid, "include", "☑")
        if self._on_rotate_change:
            self._on_rotate_change()

    def deselect_all(self):
        for rec in self.records:
            rec.enabled = False
        for iid in self.tree.get_children():
            self.tree.set(iid, "include", "☐")
        if self._on_rotate_change:
            self._on_rotate_change()
