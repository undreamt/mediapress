"""Dialog windows: ToolTip, HelpWindow, AboutWindow, DependencyErrorDialog."""

import customtkinter as ctk
import tkinter as tk

from .. import APP_NAME, APP_VERSION
from ..platform_compat import (
    get_ui_font, get_ffmpeg_install_hint, get_ffmpeg_setup_text,
    get_python_setup_text, get_quickstart_text, get_troubleshooting_text,
)


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify="left",
                         background="#333333", foreground="white",
                         relief="solid", borderwidth=1,
                         font=(get_ui_font(), 9),
                         wraplength=300, padx=6, pady=4)
        label.pack()

    def hide(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class HelpWindow(ctk.CTkToplevel):
    def __init__(self, parent, dep_results):
        super().__init__(parent)
        self.title("MediaPress — Setup Guide")
        self.geometry("700x600")
        self.minsize(600, 500)
        self.dep_results = dep_results

        self._build_ui()
        self.grab_set()

    def _status_line(self, dep_key):
        d = self.dep_results.get(dep_key, {})
        if d.get("found"):
            return f"[FOUND — {d.get('display', '')}]", "green"
        return f"[NOT FOUND ❌]", "red"

    def _build_ui(self):
        frame = ctk.CTkScrollableFrame(self, corner_radius=0)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        def head(text, size=14, bold=True):
            weight = "bold" if bold else "normal"
            lbl = ctk.CTkLabel(frame, text=text, font=ctk.CTkFont(size=size, weight=weight),
                               anchor="w", justify="left")
            lbl.pack(anchor="w", pady=(8, 2))

        def body(text):
            lbl = ctk.CTkLabel(frame, text=text, font=ctk.CTkFont(size=12),
                               anchor="w", justify="left", wraplength=640)
            lbl.pack(anchor="w", padx=4)

        def sep():
            ctk.CTkFrame(frame, height=1, fg_color="gray40").pack(fill="x", pady=6)

        def status_lbl(dep_key):
            txt, color = self._status_line(dep_key)
            lbl = ctk.CTkLabel(frame, text=f"   Status: {txt}",
                               font=ctk.CTkFont(size=12, weight="bold"),
                               anchor="w", text_color=color)
            lbl.pack(anchor="w", padx=4)

        head("MEDIAPRESS SETUP GUIDE", size=16)
        body("MediaPress requires the following software. All items are free and open source.")
        sep()

        head("1. PYTHON 3.10 OR NEWER")
        status_lbl("python")
        body(get_python_setup_text())
        sep()

        head("2. FFMPEG & FFPROBE")
        status_lbl("ffmpeg")
        status_lbl("ffprobe")
        body(get_ffmpeg_setup_text())
        sep()

        head("3. CUSTOMTKINTER (Python package)")
        status_lbl("customtkinter")
        body(
            "Install:  pip install customtkinter\n"
            "If pip not found:  python -m pip install customtkinter\n\n"
            "Then restart MediaPress."
        )
        sep()

        head("QUICK START (once all dependencies installed)")
        body(get_quickstart_text())
        sep()

        head("TROUBLESHOOTING")
        body(get_troubleshooting_text())

        close_btn = ctk.CTkButton(frame, text="Close", command=self.destroy, width=100)
        close_btn.pack(pady=(16, 4))


class AboutWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(f"About {APP_NAME}")
        self.geometry("400x280")
        self.resizable(False, False)
        self._build_ui()
        self.grab_set()

    def _build_ui(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text=APP_NAME,
                     font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(0, 4))
        ctk.CTkLabel(frame, text=f"Version {APP_VERSION}",
                     font=ctk.CTkFont(size=13)).pack()
        ctk.CTkLabel(frame, text="Local media compression tool for efficient cloud storage.",
                     font=ctk.CTkFont(size=12), wraplength=360).pack(pady=(8, 4))
        ctk.CTkLabel(frame, text="Built with Python, CustomTkinter, and FFmpeg",
                     font=ctk.CTkFont(size=11)).pack()

        ctk.CTkFrame(frame, height=1, fg_color="gray40").pack(fill="x", pady=12)

        links_frame = ctk.CTkFrame(frame, fg_color="transparent")
        links_frame.pack()
        for text, url in [
            ("python.org", "https://www.python.org"),
            ("ffmpeg.org", "https://ffmpeg.org"),
            ("CustomTkinter", "https://github.com/TomSchimansky/CustomTkinter"),
        ]:
            e = ctk.CTkEntry(links_frame, width=250)
            e.insert(0, url)
            e.configure(state="readonly")
            e.pack(pady=2)

        ctk.CTkButton(frame, text="Close", command=self.destroy, width=100).pack(pady=(12, 0))


class DependencyErrorDialog(ctk.CTkToplevel):
    def __init__(self, parent, dep_results, on_open_guide):
        super().__init__(parent)
        self.title("MediaPress — Missing Dependencies")
        self.geometry("500x350")
        self.resizable(False, False)
        self.dep_results = dep_results
        self.on_open_guide = on_open_guide

        missing = {k: v for k, v in dep_results.items() if k != "python" and not v.get("found")}

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Missing Dependencies",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 10))

        ctk.CTkLabel(frame, text="The following required components were not found:",
                     font=ctk.CTkFont(size=12)).pack()

        for k, v in missing.items():
            ffmpeg_hint = get_ffmpeg_install_hint()
            fix_map = {
                "ffmpeg": ffmpeg_hint,
                "ffprobe": ffmpeg_hint.replace("FFmpeg:", "FFmpeg (includes ffprobe):"),
                "customtkinter": "Run: pip install customtkinter",
            }
            lbl = ctk.CTkLabel(frame,
                               text=f"  • {v['display']}: {fix_map.get(k, 'See Setup Guide')}",
                               font=ctk.CTkFont(size=12), anchor="w", justify="left")
            lbl.pack(anchor="w", padx=10)

        ctk.CTkLabel(frame,
                     text="\nThe app will open but Scan and Run will be disabled\nuntil dependencies are installed.",
                     font=ctk.CTkFont(size=11)).pack(pady=(8, 0))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=(16, 0))

        ctk.CTkButton(btn_frame, text="Open Setup Guide",
                      command=lambda: (self.destroy(), on_open_guide())).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Continue Anyway",
                      command=self.destroy, fg_color="gray50").pack(side="left", padx=8)

        self.grab_set()
