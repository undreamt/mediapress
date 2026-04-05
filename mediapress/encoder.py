"""Hardware encoder detection and selection."""

import subprocess

# Preferred encoder order: HW first, then software fallback
_HW_ENCODERS = [
    ("h264_videotoolbox", "VideoToolbox"),  # macOS
    ("h264_nvenc", "NVENC"),                # NVIDIA
    ("h264_qsv", "QuickSync"),             # Intel
    ("h264_vaapi", "VAAPI"),               # Linux VA-API
]

_cached_encoder = None
_cached_available = None


def detect_available_encoders():
    """Return list of available H.264 encoders as (name, label) tuples."""
    global _cached_available
    if _cached_available is not None:
        return _cached_available

    kwargs = {}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        proc = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True, text=True, timeout=10,
            **kwargs,
        )
        output = proc.stdout if proc.returncode == 0 else ""
    except Exception:
        output = ""

    available = []
    for enc_name, label in _HW_ENCODERS:
        if enc_name in output:
            available.append((enc_name, label))

    # Software fallback is always available
    available.append(("libx264", "Software"))

    _cached_available = available
    return available


def get_best_encoder():
    """Return the best available H.264 encoder name."""
    global _cached_encoder
    if _cached_encoder is not None:
        return _cached_encoder

    available = detect_available_encoders()
    _cached_encoder = available[0][0]  # first = highest priority
    return _cached_encoder


def get_encoder_label(encoder_name):
    """Return a human-readable label for an encoder."""
    labels = dict(_HW_ENCODERS)
    labels["libx264"] = "Software"
    return labels.get(encoder_name, encoder_name)


def build_encoder_args(encoder_name, crf):
    """Return encoder-specific ffmpeg arguments."""
    if encoder_name == "h264_videotoolbox":
        # VideoToolbox uses -q:v for quality (1-100, lower=better)
        # Map CRF 18-28 → q:v roughly 30-65
        quality = int(30 + (crf - 18) * 3.5)
        return ["-c:v", "h264_videotoolbox", "-q:v", str(quality)]
    elif encoder_name == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-cq", str(crf), "-preset", "p4"]
    elif encoder_name == "h264_qsv":
        return ["-c:v", "h264_qsv", "-global_quality", str(crf)]
    elif encoder_name == "h264_vaapi":
        return ["-c:v", "h264_vaapi", "-qp", str(crf)]
    else:
        # libx264 software
        return ["-c:v", "libx264", "-crf", str(crf), "-preset", "medium"]
