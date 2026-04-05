"""Report generation for MediaPress — shared by GUI and CLI."""

import csv
from datetime import datetime
from pathlib import Path


def generate_text_report(results):
    """Generate a text report string from processing results."""
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
            if r.error_message:
                for line in r.error_message.splitlines():
                    lines.append(f"             {line}")
            else:
                status_line += "  (no error detail)"
        lines.append(status_line)

    lines.append(f"{'='*60}")
    return "\n".join(lines) + "\n"


def write_csv_report(results, output_path: Path):
    """Write a CSV report to the given path."""
    fieldnames = [
        "Filename", "Relative Path", "Type", "Source",
        "Action Taken", "Original Size (MB)", "Output Size (MB)",
        "Size Reduction %", "Original Format", "Output Format",
        "Original Resolution", "Output Resolution",
        "Original Bitrate", "Output Bitrate",
        "CRF Used", "Rotation Applied", "Result", "Error Message"
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
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
