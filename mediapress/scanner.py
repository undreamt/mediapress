"""File scanning and status determination logic."""

import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .constants import VIDEO_EXTENSIONS, AUDIO_EXTENSIONS, PHOTO_EXTENSIONS, GIF_EXTENSIONS
from .models import FileRecord
from .probe import probe_file, parse_probe, format_codec_container, format_bitrate, format_resolution
from .motion import detect_motion_photo, align_to_ftyp


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

    # Motion photo video rows always attempt compression, even if probe failed
    if record.is_motion_video_row:
        out_rel = Path(record.rel_path).with_name(Path(record.rel_path).stem + "_video.mp4")
        record.output_path = output_folder / out_rel
        if skip_existing and record.output_path.exists():
            record.status = "Will skip (output exists)"
            record.action_taken = "Skipped (output exists)"
            return
        if info is None:
            # Probe failed — still compress, we'll figure it out at extraction time
            record.status = "Will compress"
            record.action_taken = "Compressed"
        else:
            _determine_video_status(record, info)
        return

    if info is None:
        record.status = "Unsupported — skip"
        record.action_taken = "Skipped (unsupported)"
        return

    # Determine output path
    if record.file_type == "Video":
        out_rel = Path(record.rel_path).with_suffix(".mp4")
    else:  # Audio
        out_rel = Path(record.rel_path).with_suffix(".mp3")

    record.output_path = output_folder / out_rel

    # Check skip existing
    if skip_existing and record.output_path.exists():
        record.status = "Will skip (output exists)"
        record.action_taken = "Skipped (output exists)"
        return

    if record.file_type == "Video":
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


def _probe_motion_photo(filepath, video_offset):
    """Extract embedded video from motion photo and probe it. Returns (probe_data, probe_err)."""
    try:
        file_data = filepath.read_bytes()
        video_bytes = align_to_ftyp(file_data[video_offset:])
        if len(video_bytes) >= 10240:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(video_bytes)
                tmp_path = tmp.name
            probe_data, probe_err = probe_file(tmp_path)
            os.unlink(tmp_path)
            return probe_data, probe_err
        else:
            return None, "Embedded video too small"
    except Exception as e:
        return None, str(e)


def scan_folder(input_folder: Path, output_folder: Path, skip_existing: bool, crf: int,
                progress_callback=None, done_callback=None, cancel_event=None,
                probe_workers=None):
    """Scan input folder and return list of FileRecord objects.

    Args:
        probe_workers: number of parallel ffprobe workers (None = auto-detect)
    """
    if probe_workers is None:
        probe_workers = min(os.cpu_count() or 4, 8)

    records = []
    all_files = sorted(input_folder.rglob("*"))
    media_files = [f for f in all_files if f.is_file()]
    total = len(media_files)

    # Phase 1: Classify files and create records (no subprocess calls)
    probe_tasks = []  # list of (record, probe_target, is_motion_photo)

    for i, filepath in enumerate(media_files):
        if cancel_event and cancel_event.is_set():
            break

        if progress_callback:
            progress_callback(i, total, filepath.name)

        ext = filepath.suffix.lower()
        rel = filepath.relative_to(input_folder)

        if ext in PHOTO_EXTENSIONS:
            video_offset = detect_motion_photo(filepath)
            if video_offset is not None:
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
                still_rec.output_path = output_folder / rel
                video_rec.linked_still = still_rec

                # Queue motion photo probe
                probe_tasks.append((video_rec, video_offset, True))
                records.append(video_rec)
            else:
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
            probe_tasks.append((rec, str(filepath), False))
            records.append(rec)

        elif ext in AUDIO_EXTENSIONS:
            rec = FileRecord()
            rec.filepath = filepath
            rec.rel_path = str(rel)
            rec.filename = filepath.name
            rec.ext = ext
            rec.file_type = "Audio"
            rec.show_rotate = False
            probe_tasks.append((rec, str(filepath), False))
            records.append(rec)

        elif ext in GIF_EXTENSIONS:
            rec = FileRecord()
            rec.filepath = filepath
            rec.rel_path = str(rel)
            rec.filename = filepath.name
            rec.ext = ext
            rec.file_type = "GIF"
            rec.show_rotate = False
            rec.current_format = "GIF"
            rec.bitrate_display = "—"
            probe_tasks.append((rec, str(filepath), False))
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

    # Phase 2: Parallel FFprobe
    def _run_probe(task):
        rec, target, is_motion = task
        if is_motion:
            return rec, _probe_motion_photo(rec.filepath, target)
        else:
            return rec, probe_file(target)

    if probe_tasks:
        with ThreadPoolExecutor(max_workers=probe_workers) as executor:
            futures = {executor.submit(_run_probe, t): t for t in probe_tasks}
            for future in as_completed(futures):
                rec, (probe_data, probe_err) = future.result()
                ext = rec.ext.lower()

                if probe_data:
                    info = parse_probe(probe_data)
                    rec.probe_info = info
                    rec.probe_error = None

                    if rec.file_type in ("Video", "Motion Photo (video)"):
                        probe_ext = ".mp4" if rec.file_type == "Motion Photo (video)" else ext
                        rec.current_format = format_codec_container(info, probe_ext)
                        rec.resolution = format_resolution(info)
                        rec.bitrate_display = format_bitrate(
                            info.get("video_bitrate") or info.get("total_bitrate")
                        )
                    elif rec.file_type == "Audio":
                        rec.current_format = format_codec_container(info, ext)
                        rec.resolution = "—"
                        rec.bitrate_display = format_bitrate(
                            info.get("audio_bitrate") or info.get("total_bitrate")
                        )
                    elif rec.file_type == "GIF":
                        rec.resolution = format_resolution(info)
                else:
                    rec.probe_error = probe_err
                    if rec.file_type == "GIF":
                        rec.resolution = "—"
                    elif rec.file_type != "Unsupported":
                        rec.current_format = "Unknown"

    # Phase 3: Determine status for all records
    for rec in records:
        if rec.status:  # already set (unsupported, etc.)
            continue

        if rec.file_type == "GIF":
            rec.output_path = output_folder / Path(rec.rel_path).with_suffix(".mp4")
            if skip_existing and rec.output_path.exists():
                rec.status = "Will skip (output exists)"
                rec.action_taken = "Skipped (output exists)"
            else:
                rec.status = "Will compress"
                rec.action_taken = "Compressed"
        else:
            determine_status(rec, output_folder, skip_existing, crf)

    if progress_callback:
        progress_callback(total, total, "Done")

    if done_callback:
        done_callback(records)

    return records
