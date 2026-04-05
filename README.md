# MediaPress — Media Compression Tool

A cross-platform desktop application for compressing video and audio files to efficient storage parameters. It scans an input folder, re-encodes files using FFmpeg, and writes compressed copies to an output folder — mirroring the folder structure exactly. Source files are never modified.

## Requirements

- **Windows 10+**, **macOS 12+**, or **Linux**
- Python 3.10 or newer
- FFmpeg & FFprobe (on PATH)
- CustomTkinter (Python package)

---

## Installation

### 1. Install Python

**macOS:**
```
brew install python
```
Or download from [python.org/downloads](https://www.python.org/downloads/).

**Linux (Debian/Ubuntu):**
```
sudo apt install python3 python3-pip python3-tk
```

**Windows:**
Download from [python.org/downloads](https://www.python.org/downloads/).
**Important:** On the first install screen, check **"Add Python to PATH"**.

Verify:
```
python3 --version
```

### 2. Install FFmpeg

**macOS:**
```
brew install ffmpeg
```

**Linux (Debian/Ubuntu):**
```
sudo apt update && sudo apt install ffmpeg
```

**Linux (Fedora):**
```
sudo dnf install ffmpeg
```

**Windows — winget (easiest, built into Windows 11):**
```
winget install Gyan.FFmpeg
```

**Windows — Manual:**
1. Download from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) → `ffmpeg-release-essentials.zip`
2. Extract and move the folder to e.g. `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your Windows PATH:
   - `Win+S` → "Environment Variables" → System variables → Path → Edit → New
4. Restart your terminal

Verify:
```
ffmpeg -version
ffprobe -version
```

### 3. Install CustomTkinter

```
pip install customtkinter
```

If `pip` is not found:
```
python3 -m pip install customtkinter
```

---

## Running MediaPress

```
cd /path/to/mediapress
python3 mediapress.py
```

Or run as a Python package:
```
python3 -m mediapress
```

---

## Features

- Scans input folders recursively for video, audio, GIF, and motion photo files
- Smart compression decisions: compress, remux, copy, or skip based on codec/bitrate/container
- Video compression: H.264 / MP4, CRF-controlled quality (default 23)
- GIF conversion: converts animated GIFs to H.264 MP4 for dramatically smaller output
- Audio compression: MP3 128kbps with full ID3 tag preservation
- Motion Photo support: detects and extracts Google Pixel motion photos to compressed MP4
- Rotation correction: per-file dropdown (none / 90° CW / 90° CCW / 180°)
- Skip existing files: resume interrupted runs without re-processing
- CSV report: full per-file report saved to the output folder
- Settings persistence: remembers your last folders and preferences

## Supported Formats

**Video:** `.mp4`, `.mov`, `.avi`, `.mkv`, `.m4v`, `.wmv`, `.3gp`, `.flv`, `.webm`, `.ts`, `.mts`, `.m2ts`

**Audio:** `.mp3`, `.wav`, `.flac`, `.aac`, `.m4a`, `.ogg`, `.wma`, `.opus`

**GIF:** `.gif` (converted to H.264 MP4)

**Motion Photos:** `.jpg`, `.jpeg` (Google Pixel / Android moving picture format — extracted to MP4)

## Utilities

- `create_shortcut.ps1` — Windows-only: creates a desktop shortcut (PowerShell)
- `diagnose_motionphoto.ps1` — Windows-only: debug tool for motion photo extraction (PowerShell)
