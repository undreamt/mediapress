#!/usr/bin/env python3
"""
MediaPress Benchmark Script
Runs scan + process on test/input → test/output and logs timing + results.
"""

import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# Add parent dir so we can import the mediapress package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mediapress.__main__ import check_dependencies
from mediapress.scanner import scan_folder
from mediapress.processor import process_records
from mediapress.encoder import get_best_encoder, get_encoder_label, detect_available_encoders


def main():
    script_dir = Path(__file__).resolve().parent
    input_folder = script_dir / "input"
    output_folder = script_dir / "output"
    log_dir = script_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"benchmark_{ts}.log"

    lines = []

    def log(msg=""):
        print(msg)
        lines.append(msg)

    log(f"{'='*70}")
    log(f"  MediaPress Benchmark — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'='*70}")
    log()

    # Check dependencies
    deps = check_dependencies()
    for k, v in deps.items():
        status = f"v{v['version']}" if v['found'] else "NOT FOUND"
        log(f"  {v['display']:30s} {status}")
    log()

    missing = [k for k, v in deps.items() if k in ("ffmpeg", "ffprobe") and not v["found"]]
    if missing:
        log("ERROR: FFmpeg/FFprobe not found. Install with: brew install ffmpeg")
        with open(log_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        return 1

    encoder = get_best_encoder()
    avail = detect_available_encoders()
    log(f"  Encoder: {encoder} ({get_encoder_label(encoder)})")
    log(f"  Available: {', '.join(f'{n} ({l})' for n, l in avail)}")

    # Clean output folder
    if output_folder.exists():
        shutil.rmtree(output_folder)
    output_folder.mkdir()

    # List input files
    input_files = sorted(f for f in input_folder.rglob("*") if f.is_file())
    total_input_size = sum(f.stat().st_size for f in input_files)
    log(f"  Input folder:  {input_folder}")
    log(f"  Output folder: {output_folder}")
    log(f"  Files:         {len(input_files)}")
    log(f"  Total size:    {total_input_size / (1024*1024):.1f} MB")
    log()

    # Phase 1: Scan
    log(f"{'─'*70}")
    log("  PHASE 1: SCAN")
    log(f"{'─'*70}")

    scan_start = time.perf_counter()
    records = scan_folder(
        input_folder, output_folder,
        skip_existing=False, crf=23,
        progress_callback=lambda i, t, name: log(f"    [{i+1}/{t}] {name}") if i < t else None,
    )
    scan_elapsed = time.perf_counter() - scan_start

    log()
    log(f"  Scan completed: {len(records)} records in {scan_elapsed:.2f}s")
    log(f"  Per-file avg:   {scan_elapsed/max(len(records),1)*1000:.0f}ms")
    log()

    for rec in records:
        log(f"    {rec.filename:40s} {rec.file_type:25s} {rec.status}")
    log()

    # Phase 2: Process
    log(f"{'─'*70}")
    log("  PHASE 2: PROCESS")
    log(f"{'─'*70}")

    actionable = [(i, r) for i, r in enumerate(records) if r.status != "Unsupported — skip"]
    skipped = [r for r in records if r.status == "Unsupported — skip"]
    for r in skipped:
        log(f"    SKIP  {r.filename}")

    process_start = time.perf_counter()

    def on_progress(orig_idx, rec, i, total_count):
        log(f"    [{i+1}/{total_count}] {rec.result:8s} {rec.filename:35s} "
            f"{rec.original_size_mb:.1f}MB → {rec.output_size_mb:.1f}MB")

    results = process_records(
        actionable, crf=23,
        encoder=encoder,
        progress_callback=on_progress,
    )

    process_elapsed = time.perf_counter() - process_start
    total_elapsed = scan_elapsed + process_elapsed

    # Summary
    log()
    log(f"{'='*70}")
    log("  SUMMARY")
    log(f"{'='*70}")

    success = [r for r in results if r.result == "Success"]
    failed = [r for r in results if r.result == "Failed"]
    skipped = [r for r in results if r.result == "Skipped"]

    orig_mb = sum(r.original_size_mb for r in success)
    out_mb = sum(r.output_size_mb for r in success)
    saved_mb = orig_mb - out_mb

    log(f"  Succeeded:      {len(success)}")
    log(f"  Failed:         {len(failed)}")
    log(f"  Skipped:        {len(skipped)}")
    log(f"  Space saved:    {saved_mb:.1f} MB  ({orig_mb:.1f} MB → {out_mb:.1f} MB)")
    if orig_mb > 0:
        log(f"  Reduction:      {saved_mb/orig_mb*100:.1f}%")
    log()
    log(f"  Scan time:      {scan_elapsed:.2f}s")
    log(f"  Process time:   {process_elapsed:.2f}s")
    log(f"  Total time:     {total_elapsed:.2f}s")
    log(f"  Throughput:     {orig_mb/max(total_elapsed,0.01):.1f} MB/s")
    log()

    if failed:
        log("  FAILURES:")
        for r in failed:
            log(f"    {r.filename}: {r.error_message[:200]}")
        log()

    log(f"  Log saved to: {log_path}")

    # Write log
    with open(log_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
