"""Data model for MediaPress file records."""


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
