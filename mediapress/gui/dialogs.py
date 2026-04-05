"""Dialog windows: ToolTip, HelpWindow, AboutWindow, DependencyErrorDialog."""

import customtkinter as ctk
import tkinter as tk

from .. import APP_NAME, APP_VERSION


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
                         font=("Segoe UI", 9),
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
        body(
            "How to install:\n"
            "  • Option A (Recommended): https://www.python.org/downloads/\n"
            "    During install, CHECK 'Add Python to PATH' — this is critical.\n"
            "  • Option B: Microsoft Store → search 'Python 3.12'\n\n"
            "Verify: open PowerShell and run:  python --version"
        )
        sep()

        head("2. FFMPEG & FFPROBE")
        status_lbl("ffmpeg")
        status_lbl("ffprobe")
        body(
            "Method A — winget (easiest, built into Windows 11):\n"
            "  winget install Gyan.FFmpeg\n"
            "  Then restart PowerShell and MediaPress.\n\n"
            "Method B — Manual:\n"
            "  1. Download from https://www.gyan.dev/ffmpeg/builds/\n"
            "     → 'ffmpeg-release-essentials.zip' under 'release builds'\n"
            "  2. Extract and move folder to e.g. C:\\ffmpeg\n"
            "  3. Add C:\\ffmpeg\\bin to Windows PATH:\n"
            "     Win+S → 'Environment Variables' → System variables → Path → Edit → New\n"
            "  4. Restart PowerShell and MediaPress\n\n"
            "Verify: ffmpeg -version  and  ffprobe -version"
        )
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
        body(
            "  cd C:\\path\\to\\mediapress\n"
            "  python mediapress.py"
        )
        sep()

        head("TROUBLESHOOTING")
        body(
            "'FFmpeg not found' after installing:\n"
            "  → Restart PowerShell after changing PATH. Confirm with: ffmpeg -version\n\n"
            "'python is not recognised':\n"
            "  → Reinstall Python and check 'Add Python to PATH' on the first screen.\n\n"
            "'pip is not recognised':\n"
            "  → Use: python -m pip install customtkinter\n\n"
            "Scan/Run buttons are greyed out:\n"
            "  → See the yellow warning banner. Open Help → Setup Guide."
        )

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
            fix_map = {
                "ffmpeg": "Install FFmpeg: winget install Gyan.FFmpeg",
                "ffprobe": "Install FFmpeg (includes ffprobe): winget install Gyan.FFmpeg",
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
