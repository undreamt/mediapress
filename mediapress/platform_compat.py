"""Cross-platform compatibility helpers."""

import sys


def get_platform():
    """Return 'windows', 'macos', or 'linux'."""
    if sys.platform == "win32":
        return "windows"
    elif sys.platform == "darwin":
        return "macos"
    return "linux"


def get_ui_font():
    """Return a platform-appropriate UI font family."""
    plat = get_platform()
    if plat == "windows":
        return "Segoe UI"
    elif plat == "macos":
        return "SF Pro"
    return "DejaVu Sans"


def get_ffmpeg_install_hint():
    """Return platform-appropriate FFmpeg install instructions."""
    plat = get_platform()
    if plat == "windows":
        return "Install FFmpeg: winget install Gyan.FFmpeg"
    elif plat == "macos":
        return "Install FFmpeg: brew install ffmpeg"
    return "Install FFmpeg: sudo apt install ffmpeg"


def get_ffmpeg_setup_text():
    """Return detailed FFmpeg setup instructions for the Help window."""
    plat = get_platform()
    if plat == "macos":
        return (
            "Method A — Homebrew (recommended):\n"
            "  brew install ffmpeg\n"
            "  Then restart your terminal and MediaPress.\n\n"
            "Method B — MacPorts:\n"
            "  sudo port install ffmpeg\n\n"
            "If Homebrew is not installed:\n"
            "  /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"\n\n"
            "Verify: ffmpeg -version  and  ffprobe -version"
        )
    elif plat == "linux":
        return (
            "Method A — apt (Debian/Ubuntu):\n"
            "  sudo apt update && sudo apt install ffmpeg\n\n"
            "Method B — dnf (Fedora):\n"
            "  sudo dnf install ffmpeg\n\n"
            "Method C — pacman (Arch):\n"
            "  sudo pacman -S ffmpeg\n\n"
            "Verify: ffmpeg -version  and  ffprobe -version"
        )
    # Windows
    return (
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


def get_python_setup_text():
    """Return platform-appropriate Python install instructions."""
    plat = get_platform()
    if plat == "macos":
        return (
            "How to install:\n"
            "  • Option A (Recommended): brew install python\n"
            "  • Option B: https://www.python.org/downloads/\n\n"
            "Verify: python3 --version"
        )
    elif plat == "linux":
        return (
            "How to install:\n"
            "  • Debian/Ubuntu: sudo apt install python3 python3-pip python3-tk\n"
            "  • Fedora: sudo dnf install python3 python3-pip python3-tkinter\n\n"
            "Verify: python3 --version"
        )
    # Windows
    return (
        "How to install:\n"
        "  • Option A (Recommended): https://www.python.org/downloads/\n"
        "    During install, CHECK 'Add Python to PATH' — this is critical.\n"
        "  • Option B: Microsoft Store → search 'Python 3.12'\n\n"
        "Verify: open PowerShell and run:  python --version"
    )


def get_quickstart_text():
    """Return platform-appropriate quick start instructions."""
    plat = get_platform()
    if plat == "windows":
        return "  cd C:\\path\\to\\mediapress\n  python mediapress.py"
    return "  cd /path/to/mediapress\n  python3 mediapress.py"


def get_troubleshooting_text():
    """Return platform-appropriate troubleshooting text."""
    plat = get_platform()
    if plat == "macos":
        return (
            "'FFmpeg not found' after installing:\n"
            "  → Restart your terminal. Confirm with: ffmpeg -version\n"
            "  → If using a new shell, run: eval \"$(/opt/homebrew/bin/brew shellenv)\"\n\n"
            "'python3 is not found':\n"
            "  → Install with: brew install python\n\n"
            "'pip is not found':\n"
            "  → Use: python3 -m pip install customtkinter\n\n"
            "Scan/Run buttons are greyed out:\n"
            "  → See the yellow warning banner. Open Help → Setup Guide."
        )
    elif plat == "linux":
        return (
            "'FFmpeg not found' after installing:\n"
            "  → Restart your terminal. Confirm with: ffmpeg -version\n\n"
            "'ModuleNotFoundError: tkinter':\n"
            "  → Install: sudo apt install python3-tk  (Debian/Ubuntu)\n"
            "  → Or: sudo dnf install python3-tkinter  (Fedora)\n\n"
            "'pip is not found':\n"
            "  → Use: python3 -m pip install customtkinter\n\n"
            "Scan/Run buttons are greyed out:\n"
            "  → See the yellow warning banner. Open Help → Setup Guide."
        )
    # Windows
    return (
        "'FFmpeg not found' after installing:\n"
        "  → Restart PowerShell after changing PATH. Confirm with: ffmpeg -version\n\n"
        "'python is not recognised':\n"
        "  → Reinstall Python and check 'Add Python to PATH' on the first screen.\n\n"
        "'pip is not recognised':\n"
        "  → Use: python -m pip install customtkinter\n\n"
        "Scan/Run buttons are greyed out:\n"
        "  → See the yellow warning banner. Open Help → Setup Guide."
    )
