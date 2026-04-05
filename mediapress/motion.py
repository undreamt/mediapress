"""Motion photo detection and extraction helpers."""

import struct
from pathlib import Path


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


def align_to_ftyp(raw: bytes) -> bytes:
    """
    Given raw bytes that should be an MP4, find the first valid ftyp box
    and return bytes starting at its box-size field (4 bytes before 'ftyp').
    Searches up to 65536 bytes. Returns raw unchanged if not found.
    """
    search = raw[:65536]
    pos = 0
    while True:
        idx = search.find(b'ftyp', pos)
        if idx < 4:
            if idx == -1:
                break
            pos = idx + 1
            continue
        # Validate: 4 bytes before 'ftyp' is the box size (big-endian uint32 > 0)
        box_size = struct.unpack(">I", search[idx - 4:idx])[0]
        if box_size >= 8:  # minimum valid box: 4 (size) + 4 (type) = 8
            return raw[idx - 4:]
        pos = idx + 1
    return raw
