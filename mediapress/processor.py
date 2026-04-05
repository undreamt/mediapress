"""FFmpeg command building and file processing."""

import shutil
import subprocess
from pathlib import Path

from .models import FileRecord
from .probe import format_resolution
from .motion import align_to_ftyp


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
        kwargs = {}
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                **kwargs)
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
            video_bytes = align_to_ftyp(data[record.motion_video_offset:])
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
            if record.file_type == "Motion Photo (video)":
                # Extracted motion photo MP4 can have 2 video streams (video + embedded still).
                # Force selection of the first (shortest) video stream only.
                cmd = [
                    "ffmpeg", "-loglevel", "warning",
                    "-i", str(input_for_ffmpeg),
                    "-map", "0:v:0",  # first video stream only
                    "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
                    "-an",
                ]
                if record.rotation != "None":
                    rotate_map = {
                        "90° Clockwise": "transpose=1",
                        "90° Counter-clockwise": "transpose=2",
                        "180°": "transpose=1,transpose=1",
                    }
                    vf = rotate_map.get(record.rotation)
                    if vf:
                        cmd += ["-vf", vf]
                cmd += ["-movflags", "+faststart", "-y", str(record.output_path)]
                success, stderr = run_ffmpeg(cmd)
                record.crf_used = str(crf)
            elif record.file_type == "Video":
                if info:
                    cmd = build_ffmpeg_video_cmd(
                        input_for_ffmpeg, record.output_path, info, crf, record.rotation
                    )
                else:
                    cmd = [
                        "ffmpeg", "-loglevel", "error", "-i", str(input_for_ffmpeg),
                        "-c:v", "libx264", "-crf", str(crf),
                        "-preset", "medium", "-y", str(record.output_path)
                    ]
                success, stderr = run_ffmpeg(cmd)
                record.crf_used = str(crf)
            elif record.file_type == "GIF":
                # Convert GIF to H.264 MP4 with embedded thumbnail (first frame).
                filter_complex = (
                    "[0:v]split=2[vid][th];"
                    "[vid]scale=trunc(iw/2)*2:trunc(ih/2)*2[v];"
                    "[th]select=eq(n\\,0),scale=trunc(iw/2)*2:trunc(ih/2)*2[t]"
                )
                cmd = [
                    "ffmpeg", "-loglevel", "error", "-i", str(input_for_ffmpeg),
                    "-filter_complex", filter_complex,
                    "-map", "[v]", "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
                    "-map", "[t]", "-c:v:1", "mjpeg", "-disposition:v:1", "attached_pic",
                    "-an", "-movflags", "+faststart", "-y", str(record.output_path)
                ]
                success, stderr = run_ffmpeg(cmd)
                record.crf_used = str(crf)
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
                if record.file_type in ("Video", "Motion Photo (video)", "GIF"):
                    record.output_format = "H.264 / MP4"
                else:
                    record.output_format = "MP3"
                if info:
                    record.output_resolution = format_resolution(info)
                    record.output_bitrate = "128 kbps (audio)"

        else:
            record.result = "Failed"
            record.error_message = stderr[-2000:] if len(stderr) > 2000 else stderr
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
