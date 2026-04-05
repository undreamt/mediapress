"""FFprobe analysis and format helpers."""

import json
import subprocess


def probe_file(filepath: str):
    """Run ffprobe and return parsed JSON, or None on failure."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams", "-show_format",
            filepath
        ]
        kwargs = {}
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                              **kwargs)
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
