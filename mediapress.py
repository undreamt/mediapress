"""
MediaPress — Media Compression Tool
A Windows 11 desktop application for compressing video and audio files.
"""

import sys
import os
import json
import csv
import subprocess
import threading
import shutil
import struct
import tempfile
import time
from pathlib import Path
from datetime import datetime

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
import tkinter.ttk as ttk

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

APP_NAME = "MediaPress"
APP_VERSION = "1.0.0"
SETTINGS_FILE = Path(__file__).parent / "mediapress_settings.json"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".3gp",
                    ".flv", ".webm", ".ts", ".mts", ".m2ts"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma", ".opus"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg"}
GIF_EXTENSIONS   = {".gif"}

ROTATE_OPTIONS = ["None", "90° Clockwise", "90° Counter-clockwise", "180°"]

# ─────────────────────────────────────────────────────────────────────────────
# Dependency Checking
# ─────────────────────────────────────────────────────────────────────────────

def check_dependencies():
    """Returns a dict with dependency status info."""
    results = {}

    # Python
    results["python"] = {
        "found": True,
        "version": sys.version.split()[0],
        "display": f"Python {sys.version.split()[0]}"
    }

    # FFmpeg
    try:
        proc = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10)
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
        proc = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True, timeout=10)
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


# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_SETTINGS = {
    "input_folder": "",
    "output_folder": "",
    "crf": 23,
    "skip_existing": True,
}

def load_settings():
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                s = dict(DEFAULT_SETTINGS)
                s.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
                return s
    except Exception:
        pass
    return dict(DEFAULT_SETTINGS)

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Motion Photo Detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_motion_photo(filepath: Path):
    """
    Returns the byte offset where the embedded video starts, or None if not a motion photo.
    """
    try:
        with open(filepath, "rb") as f:
            data = f.read()
    except Exception:
        return None

    file_size = len(data)
    header = data[:65536]  # first 64KB

    # Method A: XMP MicroVideoOffset
    for marker in [b"GCamera:MicroVideoOffset=", b"Camera:MicroVideoOffset="]:
        idx = header.find(marker)
        if idx != -1:
            # Extract the number after the marker (could be in quotes or bare)
            after = header[idx + len(marker):]
            # Strip quotes
            if after and after[0:1] in (b'"', b"'"):
                after = after[1:]
            end = 0
            while end < len(after) and chr(after[end]).isdigit():
                end += 1
            if end > 0:
                try:
                    offset_val = int(after[:end])
                    if offset_val > 0:
                        video_start = file_size - offset_val
                        if 0 < video_start < file_size:
                            return video_start
                except ValueError:
                    pass

    # Check for MotionPhoto=1 marker (newer format)
    has_motion = (b"MotionPhoto=" in header or b"GCamera:MotionPhoto=" in header)

    # Method B: Find last ftyp box
    # Search all occurrences of b'ftyp'
    last_ftyp = None
    search_start = 0
    while True:
        idx = data.find(b"ftyp", search_start)
        if idx == -1:
            break
        # The 4 bytes before ftyp should be the box size
        if idx >= 4:
            box_size = struct.unpack(">I", data[idx - 4:idx])[0]
            if box_size > 0 and idx - 4 + box_size <= file_size:
                last_ftyp = idx - 4
        search_start = idx + 1

    if last_ftyp is not None and last_ftyp > 0:
        return last_ftyp

    return None


# ─────────────────────────────────────────────────────────────────────────────
# FFprobe Analysis
# ─────────────────────────────────────────────────────────────────────────────

def probe_file(filepath: str):
    """Run ffprobe and return parsed JSON, or None on failure."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams", "-show_format",
            filepath
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            return None, proc.stderr
        return json.loads(proc.stdout), None
    except Exception as e:
        return None, str(e)


def parse_probe(probe_data):
    """Extract relevant info from ffprobe JSON output."""
    info = {
        "video_codec": None,
        "audio_codec": None,
        "width": None,
        "height": None,
        "video_bitrate": None,
        "audio_bitrate": None,
        "sample_rate": None,
        "format_name": None,
        "has_audio": False,
        "has_video": False,
        "total_bitrate": None,
    }

    if not probe_data:
        return info

    fmt = probe_data.get("format", {})
    info["format_name"] = fmt.get("format_name", "")
    info["total_bitrate"] = int(fmt.get("bit_rate", 0) or 0)

    for stream in probe_data.get("streams", []):
        codec_type = stream.get("codec_type", "")
        if codec_type == "video" and not info["has_video"]:
            info["has_video"] = True
            info["video_codec"] = stream.get("codec_name", "")
            info["width"] = stream.get("width")
            info["height"] = stream.get("height")
            br = stream.get("bit_rate") or fmt.get("bit_rate")
            info["video_bitrate"] = int(br or 0)
        elif codec_type == "audio" and not info["has_audio"]:
            info["has_audio"] = True
            info["audio_codec"] = stream.get("codec_name", "")
            br = stream.get("bit_rate") or fmt.get("bit_rate")
            info["audio_bitrate"] = int(br or 0)
            info["sample_rate"] = stream.get("sample_rate")

    # Fallback video bitrate to total
    if info["has_video"] and info["video_bitrate"] == 0 and info["total_bitrate"] > 0:
        info["video_bitrate"] = info["total_bitrate"]

    return info


def format_codec_container(info, ext):
    """Return a human-readable 'Codec / Container' string."""
    codec_map = {
        "h264": "H.264", "hevc": "HEVC", "vp8": "VP8", "vp9": "VP9",
        "av1": "AV1", "mpeg4": "MPEG-4", "mpeg2video": "MPEG-2",
        "wmv2": "WMV", "wmv3": "WMV", "flv1": "FLV",
        "mp3": "MP3", "aac": "AAC", "flac": "FLAC", "opus": "Opus",
        "vorbis": "Vorbis", "wmav2": "WMA", "pcm_s16le": "PCM",
        "pcm_s24le": "PCM", "pcm_f32le": "PCM",
    }
    container_map = {
        "mp4": "MP4", "mov,mp4,m4a,3gp,3g2,mj2": "MOV", "matroska,webm": "MKV",
        "avi": "AVI", "asf": "WMV", "flv": "FLV", "mpegts": "TS",
        "webm": "WebM", "ogg": "OGG",
    }
    ext_container = {
        ".mp4": "MP4", ".mov": "MOV", ".avi": "AVI", ".mkv": "MKV",
        ".m4v": "M4V", ".wmv": "WMV", ".3gp": "3GP", ".flv": "FLV",
        ".webm": "WebM", ".ts": "TS", ".mts": "MTS", ".m2ts": "M2TS",
        ".mp3": "MP3", ".wav": "WAV", ".flac": "FLAC", ".aac": "AAC",
        ".m4a": "M4A", ".ogg": "OGG", ".wma": "WMA", ".opus": "Opus",
    }

    codec = None
    if info["has_video"]:
        codec = codec_map.get(info["video_codec"], info["video_codec"] or "Unknown")
    elif info["has_audio"]:
        codec = codec_map.get(info["audio_codec"], info["audio_codec"] or "Unknown")

    fmt_name = info.get("format_name", "")
    container = container_map.get(fmt_name)
    if not container:
        container = ext_container.get(ext.lower(), ext.upper().lstrip("."))

    if codec and container:
        return f"{codec} / {container}"
    elif codec:
        return codec
    return "Unknown"


def format_bitrate(bps):
    if not bps:
        return "—"
    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.1f} Mbps"
    return f"{bps / 1000:.0f} kbps"


def format_resolution(info):
    if info["width"] and info["height"]:
        return f"{info['width']}x{info['height']}"
    return "—"


# ─────────────────────────────────────────────────────────────────────────────
# File Record
# ─────────────────────────────────────────────────────────────────────────────

class FileRecord:
    """Represents one row in the file table."""
    def __init__(self):
        self.filepath = None          # Path object
        self.rel_path = ""            # relative to input folder
        self.filename = ""
        self.ext = ""
        self.file_type = ""           # Video, Audio, Motion Photo (still), Motion Photo (video)
        self.current_format = ""
        self.resolution = "—"
        self.bitrate_display = "—"
        self.status = ""
        self.probe_info = None
        self.probe_error = None
        self.rotation = "None"        # dropdown value
        self.show_rotate = False

        # Motion photo specific
        self.is_motion_photo = False
        self.motion_video_offset = None
        self.is_motion_still_row = False
        self.is_motion_video_row = False
        self.linked_record = None     # other half of motion photo pair
        self.linked_still = None      # still record stored off-list (video row only)

        # Per-row include/exclude
        self.enabled = True

        # Processing results
        self.action_taken = ""
        self.original_size_mb = 0.0
        self.output_size_mb = 0.0
        self.size_reduction_pct = 0.0
        self.output_format = ""
        self.output_resolution = ""
        self.output_bitrate = ""
        self.crf_used = ""
        self.result = ""
        self.error_message = ""
        self.output_path = None


# ─────────────────────────────────────────────────────────────────────────────
# File Scanning
# ─────────────────────────────────────────────────────────────────────────────

def determine_status(record: FileRecord, output_folder: Path, skip_existing: bool, crf: int):
    """Determine what action will be taken for this file."""
    ext = record.ext.lower()
    info = record.probe_info

    if record.is_motion_still_row:
        record.status = "Will copy (still image)"
        record.action_taken = "Copied (still — motion photo)"
        return

    if record.file_type == "Unsupported":
        record.status = "Unsupported — skip"
        record.action_taken = "Skipped (unsupported)"
        return

    if info is None:
        record.status = "Unsupported — skip"
        record.action_taken = "Skipped (unsupported)"
        return

    # Determine output path
    if record.is_motion_video_row:
        out_rel = Path(record.rel_path).with_name(Path(record.rel_path).stem + "_video.mp4")
    elif record.file_type == "Video":
        out_rel = Path(record.rel_path).with_suffix(".mp4")
    else:  # Audio
        out_rel = Path(record.rel_path).with_suffix(".mp3")

    record.output_path = output_folder / out_rel

    # Check skip existing
    if skip_existing and record.output_path.exists():
        record.status = "Will skip (output exists)"
        record.action_taken = "Skipped (output exists)"
        return

    if record.file_type == "Video" or record.is_motion_video_row:
        _determine_video_status(record, info)
    elif record.file_type == "Audio":
        _determine_audio_status(record, info)


def _determine_video_status(record: FileRecord, info):
    codec = (info.get("video_codec") or "").lower()
    fmt = (info.get("format_name") or "").lower()
    bitrate = info.get("video_bitrate") or info.get("total_bitrate") or 0
    w = info.get("width") or 0
    h = info.get("height") or 0
    max_dim = max(w, h)
    is_mp4 = "mp4" in fmt or record.ext.lower() in (".mp4", ".m4v")
    rotation = record.rotation

    if codec == "h264" and max_dim <= 1080 and bitrate <= 4_000_000 and rotation == "None":
        if is_mp4:
            record.status = "Will copy (within spec)"
            record.action_taken = "Copied (within spec)"
        else:
            record.status = "Will remux (right codec, wrong container)"
            record.action_taken = "Remuxed"
    else:
        record.status = "Will compress"
        record.action_taken = "Compressed"


def _determine_audio_status(record: FileRecord, info):
    codec = (info.get("audio_codec") or "").lower()
    bitrate = info.get("audio_bitrate") or info.get("total_bitrate") or 0

    if codec == "mp3" and bitrate <= 128_000:
        record.status = "Will copy (within spec)"
        record.action_taken = "Copied (within spec)"
    else:
        record.status = "Will compress"
        record.action_taken = "Compressed"


def scan_folder(input_folder: Path, output_folder: Path, skip_existing: bool, crf: int,
                progress_callback=None, done_callback=None, cancel_event=None):
    """Scan input folder and return list of FileRecord objects."""
    records = []
    all_files = sorted(input_folder.rglob("*"))
    media_files = [f for f in all_files if f.is_file()]
    total = len(media_files)

    for i, filepath in enumerate(media_files):
        if cancel_event and cancel_event.is_set():
            break

        if progress_callback:
            progress_callback(i, total, filepath.name)

        ext = filepath.suffix.lower()
        rel = filepath.relative_to(input_folder)

        if ext in PHOTO_EXTENSIONS:
            # Check for motion photo
            video_offset = detect_motion_photo(filepath)
            if video_offset is not None:
                # Create two records
                still_rec = FileRecord()
                still_rec.filepath = filepath
                still_rec.rel_path = str(rel)
                still_rec.filename = filepath.name
                still_rec.ext = ext
                still_rec.file_type = "Motion Photo (still)"
                still_rec.is_motion_photo = True
                still_rec.is_motion_still_row = True
                still_rec.motion_video_offset = video_offset
                still_rec.show_rotate = False
                still_rec.resolution = "—"
                still_rec.bitrate_display = "—"
                still_rec.current_format = "JPEG / Still"
                still_rec.output_path = output_folder / rel

                video_rec = FileRecord()
                video_rec.filepath = filepath
                video_rec.rel_path = str(rel)
                video_rec.filename = filepath.name
                video_rec.ext = ext
                video_rec.file_type = "Motion Photo (video)"
                video_rec.is_motion_photo = True
                video_rec.is_motion_video_row = True
                video_rec.motion_video_offset = video_offset
                video_rec.show_rotate = True

                still_rec.linked_record = video_rec
                video_rec.linked_record = still_rec

                # Probe the embedded video (we'll do it via a temp file later if needed)
                # For scan, do a quick probe by extracting first
                try:
                    file_data = filepath.read_bytes()
                    video_bytes = file_data[video_offset:]
                    # Align to ftyp box start — skip any padding bytes before the MP4 container
                    ftyp_rel = video_bytes[:516].find(b'ftyp')
                    if ftyp_rel >= 4:
                        video_bytes = video_bytes[ftyp_rel - 4:]
                    if len(video_bytes) >= 10240:
                        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                            tmp.write(video_bytes)
                            tmp_path = tmp.name
                        probe_data, probe_err = probe_file(tmp_path)
                        os.unlink(tmp_path)
                        if probe_data:
                            info = parse_probe(probe_data)
                            video_rec.probe_info = info
                            video_rec.probe_error = None
                            video_rec.current_format = format_codec_container(info, ".mp4")
                            video_rec.resolution = format_resolution(info)
                            video_rec.bitrate_display = format_bitrate(
                                info.get("video_bitrate") or info.get("total_bitrate")
                            )
                        else:
                            video_rec.probe_error = probe_err
                            video_rec.current_format = "Unknown"
                    else:
                        video_rec.probe_error = "Embedded video too small"
                        video_rec.current_format = "Unknown"
                except Exception as e:
                    video_rec.probe_error = str(e)
                    video_rec.current_format = "Unknown"

                # Set up the still output path for later processing
                still_rec.output_path = output_folder / rel
                determine_status(video_rec, output_folder, skip_existing, crf)

                # Only the video row appears in the table; still is stored off-list
                video_rec.linked_still = still_rec
                records.append(video_rec)
            else:
                # Regular JPEG — unsupported
                rec = FileRecord()
                rec.filepath = filepath
                rec.rel_path = str(rel)
                rec.filename = filepath.name
                rec.ext = ext
                rec.file_type = "Unsupported"
                rec.current_format = "JPEG"
                rec.status = "Unsupported — skip"
                rec.action_taken = "Skipped (unsupported)"
                rec.show_rotate = False
                records.append(rec)

        elif ext in VIDEO_EXTENSIONS:
            rec = FileRecord()
            rec.filepath = filepath
            rec.rel_path = str(rel)
            rec.filename = filepath.name
            rec.ext = ext
            rec.file_type = "Video"
            rec.show_rotate = True

            probe_data, probe_err = probe_file(str(filepath))
            if probe_data:
                info = parse_probe(probe_data)
                rec.probe_info = info
                rec.current_format = format_codec_container(info, ext)
                rec.resolution = format_resolution(info)
                rec.bitrate_display = format_bitrate(
                    info.get("video_bitrate") or info.get("total_bitrate")
                )
            else:
                rec.probe_error = probe_err
                rec.current_format = "Unknown"

            determine_status(rec, output_folder, skip_existing, crf)
            records.append(rec)

        elif ext in AUDIO_EXTENSIONS:
            rec = FileRecord()
            rec.filepath = filepath
            rec.rel_path = str(rel)
            rec.filename = filepath.name
            rec.ext = ext
            rec.file_type = "Audio"
            rec.show_rotate = False

            probe_data, probe_err = probe_file(str(filepath))
            if probe_data:
                info = parse_probe(probe_data)
                rec.probe_info = info
                rec.current_format = format_codec_container(info, ext)
                rec.resolution = "—"
                rec.bitrate_display = format_bitrate(
                    info.get("audio_bitrate") or info.get("total_bitrate")
                )
            else:
                rec.probe_error = probe_err
                rec.current_format = "Unknown"

            determine_status(rec, output_folder, skip_existing, crf)
            records.append(rec)

        else:
            rec = FileRecord()
            rec.filepath = filepath
            rec.rel_path = str(rel)
            rec.filename = filepath.name
            rec.ext = ext
            rec.file_type = "Unsupported"
            rec.current_format = "—"
            rec.status = "Unsupported — skip"
            rec.action_taken = "Skipped (unsupported)"
            rec.show_rotate = False
            records.append(rec)

    if progress_callback:
        progress_callback(total, total, "Done")

    if done_callback:
        done_callback(records)

    return records


# ─────────────────────────────────────────────────────────────────────────────
# FFmpeg Processing
# ─────────────────────────────────────────────────────────────────────────────

def build_ffmpeg_video_cmd(input_path, output_path, info, crf, rotation):
    """Build the ffmpeg command for video compression."""
    w = info.get("width") or 0
    h = info.get("height") or 0

    if w > h:
        scale = "scale='min(1920,iw)':-2"
    else:
        scale = "scale=-2:'min(1920,ih)'"

    rotate_map = {
        "90° Clockwise": ",transpose=1",
        "90° Counter-clockwise": ",transpose=2",
        "180°": ",transpose=1,transpose=1",
    }
    rotate_filter = rotate_map.get(rotation, "")
    vf = scale + rotate_filter

    cmd = [
        "ffmpeg", "-loglevel", "error", "-i", str(input_path),
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", "medium",
    ]

    if info.get("has_audio"):
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-an"]

    cmd += [
        "-vf", vf,
        "-map_metadata", "0",
        "-movflags", "+faststart",
        "-y", str(output_path)
    ]
    return cmd


def build_ffmpeg_remux_cmd(input_path, output_path):
    return [
        "ffmpeg", "-loglevel", "error", "-i", str(input_path),
        "-c", "copy",
        "-map_metadata", "0",
        "-y", str(output_path)
    ]


def build_ffmpeg_audio_cmd(input_path, output_path):
    return [
        "ffmpeg", "-loglevel", "error", "-i", str(input_path),
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        "-map_metadata", "0",
        "-y", str(output_path)
    ]


def run_ffmpeg(cmd):
    """Run ffmpeg, return (success, stderr)."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = proc.communicate()
        return proc.returncode == 0, stderr.decode("utf-8", errors="replace")
    except Exception as e:
        return False, str(e)


def process_record(record: FileRecord, crf: int, tmp_dir: Path):
    """Process a single FileRecord. Returns updated record."""
    try:
        orig_size = record.filepath.stat().st_size
        record.original_size_mb = orig_size / (1024 * 1024)
    except Exception:
        record.original_size_mb = 0.0

    action = record.action_taken

    # Skip cases
    if action in ("Skipped (output exists)", "Skipped (unsupported)"):
        record.result = "Skipped"
        return record

    # Ensure output dir exists
    try:
        record.output_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        record.result = "Failed"
        record.error_message = f"Could not create output directory: {e}"
        return record

    # Motion photo still — byte-for-byte copy of JPEG
    if record.is_motion_still_row:
        try:
            shutil.copy2(str(record.filepath), str(record.output_path))
            record.result = "Success"
            record.output_size_mb = record.output_path.stat().st_size / (1024 * 1024)
            record.output_format = "JPEG"
            record.output_resolution = record.resolution
            record.output_bitrate = record.bitrate_display
            return record
        except Exception as e:
            record.result = "Failed"
            record.error_message = str(e)
            return record

    # Motion photo video — extract then process
    input_for_ffmpeg = record.filepath
    temp_file = None

    if record.is_motion_video_row:
        try:
            with open(record.filepath, "rb") as f:
                data = f.read()
            video_bytes = data[record.motion_video_offset:]
            # Align to ftyp box start — skip any padding bytes before the MP4 container
            ftyp_rel = video_bytes[:516].find(b'ftyp')
            if ftyp_rel >= 4:
                video_bytes = video_bytes[ftyp_rel - 4:]
            if len(video_bytes) < 10240:
                record.result = "Failed"
                record.error_message = "Embedded video too small or corrupt"
                return record
            stem = record.filepath.stem
            temp_file = tmp_dir / f"{stem}_motionphoto_tmp.mp4"
            with open(temp_file, "wb") as f:
                f.write(video_bytes)
            input_for_ffmpeg = temp_file
        except Exception as e:
            record.result = "Failed"
            record.error_message = f"Motion photo extraction failed: {e}"
            return record

    info = record.probe_info

    try:
        if action == "Copied (within spec)":
            shutil.copy2(str(input_for_ffmpeg), str(record.output_path))
            success = True
            stderr = ""
        elif action == "Remuxed":
            cmd = build_ffmpeg_remux_cmd(input_for_ffmpeg, record.output_path)
            success, stderr = run_ffmpeg(cmd)
        elif action == "Compressed":
            if record.file_type in ("Video", "Motion Photo (video)"):
                if info:
                    cmd = build_ffmpeg_video_cmd(
                        input_for_ffmpeg, record.output_path, info, crf, record.rotation
                    )
                else:
                    # Fallback basic compress
                    cmd = [
                        "ffmpeg", "-loglevel", "error", "-i", str(input_for_ffmpeg),
                        "-c:v", "libx264", "-crf", str(crf),
                        "-preset", "medium", "-y", str(record.output_path)
                    ]
                success, stderr = run_ffmpeg(cmd)
                record.crf_used = str(crf)
            elif record.file_type == "GIF":
                cmd = build_ffmpeg_gif_cmd(input_for_ffmpeg, record.output_path)
                success, stderr = run_ffmpeg(cmd)
                record.output_format = "GIF"
            else:  # Audio
                cmd = build_ffmpeg_audio_cmd(input_for_ffmpeg, record.output_path)
                success, stderr = run_ffmpeg(cmd)
        else:
            record.result = "Skipped"
            return record

        if success:
            # Validate output is non-trivial
            if record.output_path.exists() and record.output_path.stat().st_size < 1024:
                record.result = "Failed"
                record.error_message = "Output file is suspiciously small (<1 KB) — likely corrupt input"
                try:
                    record.output_path.unlink()
                except Exception:
                    pass
            else:
                record.result = "Success"
                if record.output_path.exists():
                    out_size = record.output_path.stat().st_size
                    record.output_size_mb = out_size / (1024 * 1024)
                    if record.original_size_mb > 0:
                        record.size_reduction_pct = (
                            1 - record.output_size_mb / record.original_size_mb
                        ) * 100
                if record.file_type in ("Video", "Motion Photo (video)"):
                    record.output_format = "H.264 / MP4"
                elif record.file_type == "GIF":
                    record.output_format = "GIF"
                else:
                    record.output_format = "MP3"
                if info:
                    record.output_resolution = format_resolution(info)
                    record.output_bitrate = "128 kbps (audio)"

                # Also copy the linked still JPEG (motion photo)
                if record.is_motion_video_row and record.linked_still is not None:
                    still = record.linked_still
                    try:
                        still.output_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(still.filepath), str(still.output_path))
                    except Exception as still_err:
                        record.error_message += f" | Still copy failed: {still_err}"
        else:
            record.result = "Failed"
            record.error_message = stderr[-500:] if len(stderr) > 500 else stderr
            if record.output_path.exists():
                try:
                    record.output_path.unlink()
                except Exception:
                    pass

    except Exception as e:
        record.result = "Failed"
        record.error_message = str(e)
        if record.output_path and record.output_path.exists():
            try:
                record.output_path.unlink()
            except Exception:
                pass
    finally:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass

    return record


# ─────────────────────────────────────────────────────────────────────────────
# Tooltip Helper
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Help / Setup Guide Window
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# About Window
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# File Table Widget
# ─────────────────────────────────────────────────────────────────────────────

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
        self._iid_to_idx = {}   # iid string → index into self.records

    def load_records(self, records):
        self.clear()
        self.records = list(records)
        for idx, rec in enumerate(self.records):
            self._iid_to_idx[str(idx)] = idx
            self._insert_row(idx, rec)

    def _insert_row(self, idx, rec: FileRecord):
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


# ─────────────────────────────────────────────────────────────────────────────
# Main Application Window
# ─────────────────────────────────────────────────────────────────────────────

class MediaPressApp(ctk.CTk):
    def __init__(self, dep_results):
        super().__init__()
        self.dep_results = dep_results
        self.settings = load_settings()
        self.records = []
        self.cancel_event = threading.Event()
        self.processing = False

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("MediaPress — Media Compression Tool")
        self.minsize(900, 700)
        self.geometry("1100x780")

        self._build_menu()
        self._build_ui()
        self._apply_settings()
        self._check_deps_banner()

    # ── Menu Bar ──────────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Input Folder", command=self._browse_input)
        file_menu.add_command(label="Open Output Folder", command=self._browse_output)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Setup Guide", command=self._open_help)
        help_menu.add_separator()
        help_menu.add_command(label="About MediaPress", command=self._open_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menubar)

    # ── Main UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Section 1: Folder & Options ──
        folder_frame = ctk.CTkFrame(main)
        folder_frame.pack(fill="x", pady=(0, 4))

        # Row 1: Input + Output
        row1 = ctk.CTkFrame(folder_frame, fg_color="transparent")
        row1.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(row1, text="Input Folder:", width=90, anchor="w").pack(side="left")
        self.input_var = tk.StringVar()
        self.input_entry = ctk.CTkEntry(row1, textvariable=self.input_var, state="readonly",
                                        width=300)
        self.input_entry.pack(side="left", padx=(4, 4), fill="x", expand=True)
        ctk.CTkButton(row1, text="Browse", width=80,
                      command=self._browse_input).pack(side="left", padx=(0, 16))

        ctk.CTkLabel(row1, text="Output Folder:", width=95, anchor="w").pack(side="left")
        self.output_var = tk.StringVar()
        self.output_entry = ctk.CTkEntry(row1, textvariable=self.output_var, state="readonly",
                                         width=300)
        self.output_entry.pack(side="left", padx=(4, 4), fill="x", expand=True)
        ctk.CTkButton(row1, text="Browse", width=80,
                      command=self._browse_output).pack(side="left")

        # Row 2: CRF + Skip
        row2 = ctk.CTkFrame(folder_frame, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkLabel(row2, text="Video Quality (CRF):", anchor="w").pack(side="left")
        self.crf_var = tk.IntVar(value=23)
        self.crf_label = ctk.CTkLabel(row2, text="23", width=28)

        self.crf_slider = ctk.CTkSlider(row2, from_=18, to=28, number_of_steps=10,
                                         variable=self.crf_var, width=200,
                                         command=self._on_crf_change)
        self.crf_slider.pack(side="left", padx=(6, 4))
        self.crf_label.pack(side="left", padx=(0, 4))
        ToolTip(self.crf_slider,
                "Lower = better quality & larger files.\n"
                "Higher = smaller files & lower quality.\n"
                "23 is a good default for most content.")

        self.skip_var = tk.BooleanVar(value=True)
        skip_cb = ctk.CTkCheckBox(row2, text="Skip files already in output folder",
                                   variable=self.skip_var, command=self._on_skip_change)
        skip_cb.pack(side="left", padx=(32, 8))
        ToolTip(skip_cb,
                "If an output file already exists, skip re-processing it.\n"
                "Useful for resuming interrupted runs or adding new files.")

        self.scan_btn = ctk.CTkButton(row2, text="Scan Files", width=110,
                                       command=self._start_scan)
        self.scan_btn.pack(side="left", padx=(24, 0))

        # ── Section 2: Dependency Warning Banner ──
        self.banner_frame = ctk.CTkFrame(main, fg_color="#b8860b", corner_radius=4)
        self.banner_label = ctk.CTkLabel(self.banner_frame, text="",
                                          text_color="white",
                                          font=ctk.CTkFont(size=12))
        self.banner_label.pack(padx=10, pady=6)

        # ── Section 3: File Table ──
        sel_row = ctk.CTkFrame(main, fg_color="transparent")
        sel_row.pack(fill="x", pady=(4, 0))
        ctk.CTkButton(sel_row, text="Select All", width=100,
                      command=lambda: self.table.select_all()).pack(side="left", padx=(0, 4))
        ctk.CTkButton(sel_row, text="Deselect All", width=100,
                      command=lambda: self.table.deselect_all()).pack(side="left")

        self.table = FileTableWidget(main)
        self.table._on_rotate_change = self._update_summary
        self.table.pack(fill="both", expand=True, pady=(2, 4))

        # ── Section 4: Summary Bar ──
        self.summary_var = tk.StringVar(value="No files scanned yet.")
        ctk.CTkLabel(main, textvariable=self.summary_var,
                     font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", padx=4)

        # ── Section 5: Action Bar ──
        action_frame = ctk.CTkFrame(main)
        action_frame.pack(fill="x", pady=(4, 4))

        btn_row = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=8, pady=6)

        self.run_btn = ctk.CTkButton(btn_row, text="Run Compression", width=150,
                                      command=self._start_run, state="disabled")
        self.run_btn.pack(side="left", padx=(0, 8))
        ToolTip(self.run_btn, "Start compressing files.")

        self.cancel_btn = ctk.CTkButton(btn_row, text="Cancel", width=90,
                                         command=self._cancel_run, state="disabled",
                                         fg_color="gray50")
        self.cancel_btn.pack(side="left", padx=(0, 16))

        self.progress_bar = ctk.CTkProgressBar(btn_row, width=300)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="left", padx=(0, 8))

        self.status_label = ctk.CTkLabel(btn_row, text="", font=ctk.CTkFont(size=11))
        self.status_label.pack(side="left")

        self.eta_label = ctk.CTkLabel(action_frame, text="",
                                       font=ctk.CTkFont(size=11), anchor="w")
        self.eta_label.pack(fill="x", padx=8, pady=(0, 4))

        # ── Section 6: Report Panel ──
        report_frame = ctk.CTkFrame(main)
        report_frame.pack(fill="x", pady=(4, 0))

        report_header = ctk.CTkFrame(report_frame, fg_color="transparent")
        report_header.pack(fill="x", padx=8, pady=(6, 0))
        ctk.CTkLabel(report_header, text="Report", font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").pack(side="left")
        self.save_csv_btn = ctk.CTkButton(report_header, text="Save Report as CSV",
                                           width=160, command=self._save_csv,
                                           state="disabled")
        self.save_csv_btn.pack(side="right")

        self.report_text = ctk.CTkTextbox(report_frame, height=130, state="disabled",
                                           font=ctk.CTkFont(size=11, family="Consolas"))
        self.report_text.pack(fill="x", padx=8, pady=(4, 8))

    # ── Settings & State ──────────────────────────────────────────────────────

    def _apply_settings(self):
        if self.settings.get("input_folder"):
            self.input_var.set(self.settings["input_folder"])
        if self.settings.get("output_folder"):
            self.output_var.set(self.settings["output_folder"])
        crf = self.settings.get("crf", 23)
        self.crf_var.set(crf)
        self.crf_label.configure(text=str(crf))
        self.skip_var.set(self.settings.get("skip_existing", True))

    def _save_current_settings(self):
        self.settings["input_folder"] = self.input_var.get()
        self.settings["output_folder"] = self.output_var.get()
        self.settings["crf"] = self.crf_var.get()
        self.settings["skip_existing"] = self.skip_var.get()
        save_settings(self.settings)

    def _on_crf_change(self, val):
        v = int(float(val))
        self.crf_label.configure(text=str(v))
        self._save_current_settings()

    def _on_skip_change(self):
        self._save_current_settings()

    # ── Dependency Banner ─────────────────────────────────────────────────────

    def _check_deps_banner(self):
        missing = [k for k, v in self.dep_results.items()
                   if k != "python" and not v.get("found")]
        if missing:
            names = ", ".join(self.dep_results[k]["display"] for k in missing)
            self.banner_label.configure(
                text=f"⚠  {names} not found — some features unavailable. "
                     f"See Help → Setup Guide."
            )
            self.banner_frame.pack(fill="x", pady=(0, 4))
            self.scan_btn.configure(state="disabled")
            self.run_btn.configure(state="disabled")
        else:
            self.banner_frame.pack_forget()

    # ── Browse ────────────────────────────────────────────────────────────────

    def _browse_input(self):
        folder = filedialog.askdirectory(title="Select Input Folder")
        if folder:
            self.input_var.set(folder)
            self._save_current_settings()

    def _browse_output(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_var.set(folder)
            self._save_current_settings()

    # ── Scan ──────────────────────────────────────────────────────────────────

    def _start_scan(self):
        input_folder = self.input_var.get()
        output_folder = self.output_var.get()

        if not input_folder or not output_folder:
            messagebox.showerror("Error", "Please select both input and output folders.")
            return
        if input_folder == output_folder:
            messagebox.showerror("Error", "Input and output folders must be different.")
            return

        self.scan_btn.configure(state="disabled", text="Scanning...")
        self.run_btn.configure(state="disabled")
        self.table.clear()
        self.summary_var.set("Scanning...")

        cancel_ev = threading.Event()

        def scan_done(records):
            self.after(0, lambda: self._on_scan_done(records))

        def progress(i, total, name):
            self.after(0, lambda: self.summary_var.set(f"Scanning {i}/{total}: {name}"))

        thread = threading.Thread(
            target=scan_folder,
            args=(Path(input_folder), Path(output_folder),
                  self.skip_var.get(), self.crf_var.get(),
                  progress, scan_done, cancel_ev),
            daemon=True
        )
        thread.start()

    def _on_scan_done(self, records):
        self.records = records
        self.table.load_records(records)
        self._update_summary()
        self.scan_btn.configure(state="normal", text="Scan Files")

        has_deps = all(v.get("found") for k, v in self.dep_results.items() if k != "python")
        has_work = any(r.enabled and r.status not in ("Unsupported — skip", "Will skip (output exists)")
                       for r in records)
        if has_deps and self.input_var.get() and self.output_var.get() and has_work:
            self.run_btn.configure(state="normal")

    def _update_summary(self):
        total = len(self.records)
        enabled = [r for r in self.records if r.enabled]
        excluded = total - len(enabled)
        will_compress = sum(1 for r in enabled
                            if r.status in ("Will compress",
                                            "Will remux (right codec, wrong container)"))
        will_copy = sum(1 for r in enabled
                        if r.status in ("Will copy (within spec)", "Will copy (still image)"))
        will_skip = sum(1 for r in enabled
                        if r.status in ("Will skip (output exists)", "Unsupported — skip"))
        parts = [f"{total} files found"]
        if excluded:
            parts.append(f"{excluded} excluded")
        parts += [
            f"{will_compress} will be compressed",
            f"{will_copy} will be copied/remuxed",
            f"{will_skip} will be skipped",
        ]
        self.summary_var.set(" — ".join(parts))

    # ── Run / Cancel ──────────────────────────────────────────────────────────

    def _start_run(self):
        input_folder = self.input_var.get()
        output_folder = self.output_var.get()

        if not input_folder or not output_folder:
            messagebox.showerror("Error", "Please select both folders and scan first.")
            return
        if input_folder == output_folder:
            messagebox.showerror("Error", "Input and output folders must be different.")
            return
        if not self.records:
            messagebox.showerror("Error", "No files to process. Please scan first.")
            return

        missing_deps = [k for k, v in self.dep_results.items()
                        if k != "python" and not v.get("found")]
        if missing_deps:
            messagebox.showerror(
                "Missing Dependencies",
                "Cannot run: required tools are missing.\nSee Help → Setup Guide."
            )
            return

        self.processing = True
        self.cancel_event.clear()
        self.run_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.scan_btn.configure(state="disabled")
        self.save_csv_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self._clear_report()

        crf = self.crf_var.get()
        # Read from table.records — same objects the checkbox handler mutates
        source = self.table.records if self.table.records else self.records
        records_to_process = [
            (orig_idx, r)
            for orig_idx, r in enumerate(source)
            if r.enabled and r.status not in ("Unsupported — skip",)
        ]
        total = len(records_to_process)
        start_time = time.time()

        def run_thread():
            tmp_dir = Path(tempfile.mkdtemp(prefix="mediapress_"))
            processed = 0
            results = []

            for i, (orig_idx, rec) in enumerate(records_to_process):
                if self.cancel_event.is_set():
                    rec.result = "Cancelled"
                    rec.action_taken = "Cancelled"
                    results.append(rec)
                    for _, remaining in records_to_process[i + 1:]:
                        remaining.result = "Cancelled"
                        remaining.action_taken = "Cancelled"
                        results.append(remaining)
                    break

                self.after(0, lambda r=rec, ii=i, oi=orig_idx: (
                    self.status_label.configure(
                        text=f"Processing file {ii+1} of {total}: {r.filename}"
                    ),
                    self.table.update_row_status(oi, "Processing...")
                ))

                process_record(rec, crf, tmp_dir)
                processed += 1
                results.append(rec)

                self.after(0, lambda oi=orig_idx, r=rec:
                           self.table.update_row_status(oi, r.status, r.result))

                elapsed = time.time() - start_time
                eta_str = ""
                if processed > 0:
                    avg = elapsed / processed
                    remaining_secs = avg * (total - processed)
                    eta_str = (
                        f"Elapsed: {int(elapsed//60)}m {int(elapsed%60)}s — "
                        f"Estimated remaining: ~{int(remaining_secs//60)}m {int(remaining_secs%60)}s"
                    )

                prog = processed / total if total > 0 else 1
                self.after(0, lambda p=prog, e=eta_str: (
                    self.progress_bar.set(p),
                    self.eta_label.configure(text=e)
                ))

            try:
                shutil.rmtree(str(tmp_dir), ignore_errors=True)
            except Exception:
                pass

            cancelled = self.cancel_event.is_set()
            self.after(0, lambda r=results, p=processed, t=total, c=cancelled:
                       self._on_run_done(r, p, t, c))

        threading.Thread(target=run_thread, daemon=True).start()

    def _cancel_run(self):
        self.cancel_event.set()
        self.cancel_btn.configure(state="disabled")
        self.status_label.configure(text="Cancelling — waiting for current file to finish...")

    def _on_run_done(self, results, processed, total, cancelled):
        self.processing = False
        self.run_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.scan_btn.configure(state="normal")
        self.save_csv_btn.configure(state="normal")
        self.progress_bar.set(1.0)

        if cancelled:
            self.status_label.configure(text=f"Cancelled — {processed} of {total} files processed.")
        else:
            self.status_label.configure(text=f"Done — {processed} files processed.")

        self._generate_report(results)

    # ── Report ────────────────────────────────────────────────────────────────

    def _clear_report(self):
        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.configure(state="disabled")

    def _append_report(self, text):
        self.report_text.configure(state="normal")
        self.report_text.insert("end", text)
        self.report_text.configure(state="disabled")
        self.report_text.see("end")

    def _generate_report(self, results):
        self._clear_report()
        success = sum(1 for r in results if r.result == "Success")
        skipped = sum(1 for r in results if r.result == "Skipped")
        failed = sum(1 for r in results if r.result == "Failed")
        cancelled = sum(1 for r in results if r.result == "Cancelled")

        orig_total = sum(r.original_size_mb for r in results if r.result == "Success")
        out_total = sum(r.output_size_mb for r in results if r.result == "Success")
        saved = orig_total - out_total

        lines = [
            f"{'='*60}",
            f"  MediaPress — Compression Report",
            f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"{'='*60}",
            f"  Processed:   {success} succeeded",
            f"  Skipped:     {skipped}",
            f"  Failed:      {failed}",
            f"  Cancelled:   {cancelled}",
            f"  Space saved: {saved:.1f} MB  ({orig_total:.1f} MB → {out_total:.1f} MB)",
            f"{'─'*60}",
        ]

        for r in results:
            status_line = f"  [{r.result:10s}] {r.filename}"
            if r.result == "Success":
                pct = f"{r.size_reduction_pct:.1f}% smaller" if r.size_reduction_pct > 0 else "same size"
                status_line += f"  ({r.original_size_mb:.1f} MB → {r.output_size_mb:.1f} MB, {pct})"
            elif r.result == "Failed":
                status_line += f"  ERROR: {r.error_message[:80]}"
            lines.append(status_line)

        lines.append(f"{'='*60}")
        self._append_report("\n".join(lines) + "\n")
        self._report_results = results

    def _save_csv(self):
        output_folder = self.output_var.get()
        if not output_folder:
            messagebox.showerror("Error", "No output folder set.")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = Path(output_folder) / f"compression_report_{ts}.csv"

        results = getattr(self, "_report_results", [])
        if not results:
            messagebox.showinfo("Info", "No report data to save.")
            return

        fieldnames = [
            "Filename", "Relative Path", "Type", "Source",
            "Action Taken", "Original Size (MB)", "Output Size (MB)",
            "Size Reduction %", "Original Format", "Output Format",
            "Original Resolution", "Output Resolution",
            "Original Bitrate", "Output Bitrate",
            "CRF Used", "Rotation Applied", "Result", "Error Message"
        ]

        try:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in results:
                    source = "Standard"
                    if r.is_motion_still_row:
                        source = "Motion Photo — still"
                    elif r.is_motion_video_row:
                        source = "Motion Photo — video"
                    writer.writerow({
                        "Filename": r.filename,
                        "Relative Path": r.rel_path,
                        "Type": r.file_type,
                        "Source": source,
                        "Action Taken": r.action_taken,
                        "Original Size (MB)": f"{r.original_size_mb:.2f}",
                        "Output Size (MB)": f"{r.output_size_mb:.2f}",
                        "Size Reduction %": f"{r.size_reduction_pct:.1f}",
                        "Original Format": r.current_format,
                        "Output Format": r.output_format,
                        "Original Resolution": r.resolution,
                        "Output Resolution": r.output_resolution,
                        "Original Bitrate": r.bitrate_display,
                        "Output Bitrate": r.output_bitrate,
                        "CRF Used": r.crf_used,
                        "Rotation Applied": r.rotation if r.show_rotate else "—",
                        "Result": r.result,
                        "Error Message": r.error_message,
                    })
            messagebox.showinfo("Saved", f"Report saved to:\n{csv_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save CSV:\n{e}")

    # ── Help / About ──────────────────────────────────────────────────────────

    def _open_help(self):
        HelpWindow(self, self.dep_results)

    def _open_about(self):
        AboutWindow(self)


# ─────────────────────────────────────────────────────────────────────────────
# Startup Dependency Dialog
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    dep_results = check_dependencies()

    app = MediaPressApp(dep_results)

    missing = [k for k, v in dep_results.items() if k != "python" and not v.get("found")]
    if missing:
        def open_guide():
            HelpWindow(app, dep_results)

        app.after(200, lambda: DependencyErrorDialog(app, dep_results, open_guide))

    app.mainloop()


if __name__ == "__main__":
    main()
