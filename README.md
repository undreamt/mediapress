# MediaPress — Media Compression Tool

A Windows 11 desktop application for compressing video and audio files to efficient storage parameters. It scans an input folder, re-encodes files using FFmpeg, and writes compressed copies to an output folder — mirroring the folder structure exactly. Source files are never modified.

## Requirements

- Windows 10/11
- Python 3.10 or newer
- FFmpeg & FFprobe (on PATH)
- CustomTkinter (Python package)

---

## Installation

### 1. Install Python

Download from [python.org/downloads](https://www.python.org/downloads/).

**Important:** On the first install screen, check **"Add Python to PATH"**.

Verify: open PowerShell and run:
```
python --version
```

### 2. Install FFmpeg

**Option A — winget (easiest, built into Windows 11):**
```
winget install Gyan.FFmpeg
```
Restart PowerShell after installing.

**Option B — Manual:**
1. Download from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) → `ffmpeg-release-essentials.zip`
2. Extract and move the folder to e.g. `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your Windows PATH:
   - `Win+S` → "Environment Variables" → System variables → Path → Edit → New
4. Restart PowerShell

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
python -m pip install customtkinter
```

---

## Running MediaPress

```
cd C:\path\to\mediapress
python mediapress.py
```

Or double-click `mediapress.py` if Python is associated with `.py` files.

---

## Features

- Scans input folders recursively for video, audio, and motion photo files
- Smart compression decisions: compress, remux, copy, or skip based on codec/bitrate/container
- Video compression: H.264 / MP4, CRF-controlled quality (default 23)
- Audio compression: MP3 128kbps with full ID3 tag preservation
- Motion Photo support: detects and splits Google Pixel motion photos into still + video
- Rotation correction: per-file dropdown (none / 90° CW / 90° CCW / 180°)
- Skip existing files: resume interrupted runs without re-processing
- CSV report: full per-file report saved to the output folder
- Settings persistence: remembers your last folders and preferences

## Supported Formats

**Video:** `.mp4`, `.mov`, `.avi`, `.mkv`, `.m4v`, `.wmv`, `.3gp`, `.flv`, `.webm`, `.ts`, `.mts`, `.m2ts`

**Audio:** `.mp3`, `.wav`, `.flac`, `.aac`, `.m4a`, `.ogg`, `.wma`, `.opus`

**Motion Photos:** `.jpg`, `.jpeg` (Google Pixel / Android moving picture format)
