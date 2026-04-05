"""Entry point for MediaPress: python -m mediapress"""

import sys
import subprocess


def check_dependencies():
    """Returns a dict with dependency status info."""
    results = {}

    # Python
    results["python"] = {
        "found": True,
        "version": sys.version.split()[0],
        "display": f"Python {sys.version.split()[0]}"
    }

    kwargs = {}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    # FFmpeg
    try:
        proc = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10,
                              **kwargs)
        if proc.returncode == 0:
            line = proc.stdout.splitlines()[0] if proc.stdout else ""
            ver = line.split("version")[1].strip().split()[0] if "version" in line else "unknown"
            results["ffmpeg"] = {"found": True, "version": ver, "display": f"FFmpeg {ver}"}
        else:
            results["ffmpeg"] = {"found": False, "version": None, "display": "FFmpeg"}
    except Exception:
        results["ffmpeg"] = {"found": False, "version": None, "display": "FFmpeg"}

    # FFprobe
    try:
        proc = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True, timeout=10,
                              **kwargs)
        if proc.returncode == 0:
            line = proc.stdout.splitlines()[0] if proc.stdout else ""
            ver = line.split("version")[1].strip().split()[0] if "version" in line else "unknown"
            results["ffprobe"] = {"found": True, "version": ver, "display": f"FFprobe {ver}"}
        else:
            results["ffprobe"] = {"found": False, "version": None, "display": "FFprobe"}
    except Exception:
        results["ffprobe"] = {"found": False, "version": None, "display": "FFprobe"}

    # CustomTkinter
    try:
        import customtkinter
        ver = getattr(customtkinter, "__version__", "unknown")
        results["customtkinter"] = {"found": True, "version": ver, "display": f"CustomTkinter {ver}"}
    except ImportError:
        results["customtkinter"] = {"found": False, "version": None, "display": "CustomTkinter"}

    return results


def main():
    dep_results = check_dependencies()

    from .gui.app import MediaPressApp
    from .gui.dialogs import HelpWindow, DependencyErrorDialog

    app = MediaPressApp(dep_results)

    missing = [k for k, v in dep_results.items() if k != "python" and not v.get("found")]
    if missing:
        def open_guide():
            HelpWindow(app, dep_results)

        app.after(200, lambda: DependencyErrorDialog(app, dep_results, open_guide))

    app.mainloop()


if __name__ == "__main__":
    main()
