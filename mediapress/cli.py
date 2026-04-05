"""Command-line interface for MediaPress."""

import argparse
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from . import APP_NAME, APP_VERSION


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mediapress",
        description=f"{APP_NAME} — Batch media compression tool",
    )
    parser.add_argument("-i", "--input", type=Path, required=True,
                        help="Input folder path")
    parser.add_argument("-o", "--output", type=Path, required=True,
                        help="Output folder path")
    parser.add_argument("--crf", type=int, default=23,
                        help="Video quality (CRF 18-28, lower=better, default: 23)")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip files that already exist in output (default)")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false",
                        help="Re-process files even if output exists")
    parser.add_argument("--scan-only", action="store_true",
                        help="Scan and report but do not process")
    parser.add_argument("--dry-run", action="store_true",
                        help="Alias for --scan-only")
    parser.add_argument("--csv-report", type=Path, default=None,
                        help="Save CSV report to this path (default: output_folder/compression_report_*.csv)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {APP_VERSION}")
    return parser


def cli_main(args=None):
    parser = build_parser()
    args = parser.parse_args(args)

    input_folder = args.input.resolve()
    output_folder = args.output.resolve()

    # Validate
    if not input_folder.exists():
        print(f"Error: Input folder does not exist: {input_folder}", file=sys.stderr)
        return 1
    if not input_folder.is_dir():
        print(f"Error: Input path is not a directory: {input_folder}", file=sys.stderr)
        return 1
    if input_folder == output_folder:
        print("Error: Input and output folders must be different.", file=sys.stderr)
        return 1
    if not (18 <= args.crf <= 28):
        print(f"Error: CRF must be between 18 and 28 (got {args.crf}).", file=sys.stderr)
        return 1

    # Check dependencies (skip customtkinter — not needed for CLI)
    from .__main__ import check_dependencies
    deps = check_dependencies(include_gui=False)

    missing = [k for k, v in deps.items() if k in ("ffmpeg", "ffprobe") and not v["found"]]
    if missing:
        from .platform_compat import get_ffmpeg_install_hint
        print(f"Error: Required tools not found: {', '.join(missing)}", file=sys.stderr)
        print(f"  {get_ffmpeg_install_hint()}", file=sys.stderr)
        return 1

    if args.verbose:
        for k, v in deps.items():
            status = f"v{v['version']}" if v['found'] else "NOT FOUND"
            print(f"  {v['display']:30s} {status}")
        print()

    # Create output folder
    output_folder.mkdir(parents=True, exist_ok=True)

    # Import here to keep startup fast
    from .scanner import scan_folder
    from .processor import process_record
    from .report import generate_text_report, write_csv_report

    scan_only = args.scan_only or args.dry_run

    # Phase 1: Scan
    print(f"Scanning {input_folder} ...")
    scan_start = time.perf_counter()

    def progress(i, total, name):
        sys.stdout.write(f"\r  Scanning {i+1}/{total}: {name[:60]:<60s}")
        sys.stdout.flush()

    records = scan_folder(
        input_folder, output_folder,
        skip_existing=args.skip_existing, crf=args.crf,
        progress_callback=progress,
    )
    scan_elapsed = time.perf_counter() - scan_start
    sys.stdout.write("\r" + " " * 80 + "\r")  # clear progress line

    # Print scan results
    print(f"  {len(records)} files found ({scan_elapsed:.2f}s)")
    print()

    # Summary counts
    will_compress = sum(1 for r in records if "compress" in r.status.lower() or "remux" in r.status.lower())
    will_copy = sum(1 for r in records if "copy" in r.status.lower())
    will_skip = sum(1 for r in records if "skip" in r.status.lower() or "unsupported" in r.status.lower())

    print(f"  Compress/remux: {will_compress}")
    print(f"  Copy:           {will_copy}")
    print(f"  Skip:           {will_skip}")
    print()

    if args.verbose or scan_only:
        fmt = "  {:<40s} {:<25s} {}"
        print(fmt.format("Filename", "Type", "Status"))
        print(fmt.format("─" * 40, "─" * 25, "─" * 30))
        for rec in records:
            print(fmt.format(rec.filename[:40], rec.file_type, rec.status))
        print()

    if scan_only:
        print("Scan-only mode — no files were processed.")
        return 0

    # Phase 2: Process
    actionable = [r for r in records if r.status not in ("Unsupported — skip",)]
    if not actionable:
        print("No files to process.")
        return 0

    total = len(actionable)
    print(f"Processing {total} files ...")
    tmp_dir = Path(tempfile.mkdtemp(prefix="mediapress_"))
    process_start = time.perf_counter()
    results = []

    for i, rec in enumerate(actionable):
        file_start = time.perf_counter()
        sys.stdout.write(f"\r  [{i+1}/{total}] {rec.filename[:55]:<55s}")
        sys.stdout.flush()

        process_record(rec, args.crf, tmp_dir)
        file_elapsed = time.perf_counter() - file_start
        results.append(rec)

        if args.verbose:
            sys.stdout.write(f"\r  [{i+1}/{total}] {rec.result:8s} {rec.filename:35s} "
                             f"{rec.original_size_mb:.1f}→{rec.output_size_mb:.1f}MB "
                             f"({file_elapsed:.1f}s)\n")
        elif rec.result == "Failed":
            sys.stdout.write(f"\r  [{i+1}/{total}] FAILED: {rec.filename} — {rec.error_message[:80]}\n")

    sys.stdout.write("\r" + " " * 80 + "\r")
    process_elapsed = time.perf_counter() - process_start

    # Cleanup
    shutil.rmtree(str(tmp_dir), ignore_errors=True)

    # Report
    report = generate_text_report(results)
    print(report)

    print(f"  Scan time:    {scan_elapsed:.2f}s")
    print(f"  Process time: {process_elapsed:.2f}s")
    print(f"  Total time:   {scan_elapsed + process_elapsed:.2f}s")
    print()

    # CSV report
    csv_path = args.csv_report
    if csv_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = output_folder / f"compression_report_{ts}.csv"

    try:
        write_csv_report(results, csv_path)
        print(f"  CSV report: {csv_path}")
    except Exception as e:
        print(f"  Warning: Failed to save CSV report: {e}", file=sys.stderr)

    failed_count = sum(1 for r in results if r.result == "Failed")
    return 1 if failed_count > 0 else 0
