"""Settings persistence for MediaPress."""

import json
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent.parent / "mediapress_settings.json"

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
