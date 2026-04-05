"""Main application window."""

import shutil
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import tkinter as tk

from .. import APP_NAME
from ..settings import load_settings, save_settings
from ..scanner import scan_folder
from ..processor import process_record
from ..report import generate_text_report, write_csv_report
from .dialogs import ToolTip, HelpWindow, AboutWindow, DependencyErrorDialog
from .table import FileTableWidget


class MediaPressApp(ctk.CTk):
    def __init__(self, dep_results):
        super().__init__()
        self.dep_results = dep_results
        self.settings = load_settings()
        self.records = []
        self.cancel_event = threading.Event()
        self.processing = False

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("MediaPress — Media Compression Tool")
        self.minsize(900, 700)
        self.geometry("1100x780")

        self._build_menu()
        self._build_ui()
        self._apply_settings()
        self._check_deps_banner()

    # ── Menu Bar ──────────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Input Folder", command=self._browse_input)
        file_menu.add_command(label="Open Output Folder", command=self._browse_output)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Setup Guide", command=self._open_help)
        help_menu.add_separator()
        help_menu.add_command(label="About MediaPress", command=self._open_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menubar)

    # ── Main UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Section 1: Folder & Options ──
        folder_frame = ctk.CTkFrame(main)
        folder_frame.pack(fill="x", pady=(0, 4))

        # Row 1: Input + Output
        row1 = ctk.CTkFrame(folder_frame, fg_color="transparent")
        row1.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(row1, text="Input Folder:", width=90, anchor="w").pack(side="left")
        self.input_var = tk.StringVar()
        self.input_entry = ctk.CTkEntry(row1, textvariable=self.input_var, state="readonly",
                                        width=300)
        self.input_entry.pack(side="left", padx=(4, 4), fill="x", expand=True)
        ctk.CTkButton(row1, text="Browse", width=80,
                      command=self._browse_input).pack(side="left", padx=(0, 16))

        ctk.CTkLabel(row1, text="Output Folder:", width=95, anchor="w").pack(side="left")
        self.output_var = tk.StringVar()
        self.output_entry = ctk.CTkEntry(row1, textvariable=self.output_var, state="readonly",
                                         width=300)
        self.output_entry.pack(side="left", padx=(4, 4), fill="x", expand=True)
        ctk.CTkButton(row1, text="Browse", width=80,
                      command=self._browse_output).pack(side="left")

        # Row 2: CRF + Skip
        row2 = ctk.CTkFrame(folder_frame, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkLabel(row2, text="Video Quality (CRF):", anchor="w").pack(side="left")
        self.crf_var = tk.IntVar(value=23)
        self.crf_label = ctk.CTkLabel(row2, text="23", width=28)

        self.crf_slider = ctk.CTkSlider(row2, from_=18, to=28, number_of_steps=10,
                                         variable=self.crf_var, width=200,
                                         command=self._on_crf_change)
        self.crf_slider.pack(side="left", padx=(6, 4))
        self.crf_label.pack(side="left", padx=(0, 4))
        ToolTip(self.crf_slider,
                "Lower = better quality & larger files.\n"
                "Higher = smaller files & lower quality.\n"
                "23 is a good default for most content.")

        self.skip_var = tk.BooleanVar(value=True)
        skip_cb = ctk.CTkCheckBox(row2, text="Skip files already in output folder",
                                   variable=self.skip_var, command=self._on_skip_change)
        skip_cb.pack(side="left", padx=(32, 8))
        ToolTip(skip_cb,
                "If an output file already exists, skip re-processing it.\n"
                "Useful for resuming interrupted runs or adding new files.")

        self.scan_btn = ctk.CTkButton(row2, text="Scan Files", width=110,
                                       command=self._start_scan)
        self.scan_btn.pack(side="left", padx=(24, 0))

        # ── Section 2: Dependency Warning Banner ──
        self.banner_frame = ctk.CTkFrame(main, fg_color="#b8860b", corner_radius=4)
        self.banner_label = ctk.CTkLabel(self.banner_frame, text="",
                                          text_color="white",
                                          font=ctk.CTkFont(size=12))
        self.banner_label.pack(padx=10, pady=6)

        # ── Section 3: File Table ──
        sel_row = ctk.CTkFrame(main, fg_color="transparent")
        sel_row.pack(fill="x", pady=(4, 0))
        ctk.CTkButton(sel_row, text="Select All", width=100,
                      command=lambda: self.table.select_all()).pack(side="left", padx=(0, 4))
        ctk.CTkButton(sel_row, text="Deselect All", width=100,
                      command=lambda: self.table.deselect_all()).pack(side="left")

        self.table = FileTableWidget(main)
        self.table._on_rotate_change = self._update_summary
        self.table.pack(fill="both", expand=True, pady=(2, 4))

        # ── Section 4: Summary Bar ──
        self.summary_var = tk.StringVar(value="No files scanned yet.")
        ctk.CTkLabel(main, textvariable=self.summary_var,
                     font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", padx=4)

        # ── Section 5: Action Bar ──
        action_frame = ctk.CTkFrame(main)
        action_frame.pack(fill="x", pady=(4, 4))

        btn_row = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=8, pady=6)

        self.run_btn = ctk.CTkButton(btn_row, text="Run Compression", width=150,
                                      command=self._start_run, state="disabled")
        self.run_btn.pack(side="left", padx=(0, 8))
        ToolTip(self.run_btn, "Start compressing files.")

        self.cancel_btn = ctk.CTkButton(btn_row, text="Cancel", width=90,
                                         command=self._cancel_run, state="disabled",
                                         fg_color="gray50")
        self.cancel_btn.pack(side="left", padx=(0, 16))

        self.progress_bar = ctk.CTkProgressBar(btn_row, width=300)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="left", padx=(0, 8))

        self.status_label = ctk.CTkLabel(btn_row, text="", font=ctk.CTkFont(size=11))
        self.status_label.pack(side="left")

        self.eta_label = ctk.CTkLabel(action_frame, text="",
                                       font=ctk.CTkFont(size=11), anchor="w")
        self.eta_label.pack(fill="x", padx=8, pady=(0, 4))

        # ── Section 6: Report Panel ──
        report_frame = ctk.CTkFrame(main)
        report_frame.pack(fill="x", pady=(4, 0))

        report_header = ctk.CTkFrame(report_frame, fg_color="transparent")
        report_header.pack(fill="x", padx=8, pady=(6, 0))
        ctk.CTkLabel(report_header, text="Report", font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").pack(side="left")
        self.save_csv_btn = ctk.CTkButton(report_header, text="Save Report as CSV",
                                           width=160, command=self._save_csv,
                                           state="disabled")
        self.save_csv_btn.pack(side="right")

        self.report_text = ctk.CTkTextbox(report_frame, height=130, state="disabled",
                                           font=ctk.CTkFont(size=11, family="Consolas"))
        self.report_text.pack(fill="x", padx=8, pady=(4, 8))

    # ── Settings & State ──────────────────────────────────────────────────────

    def _apply_settings(self):
        if self.settings.get("input_folder"):
            self.input_var.set(self.settings["input_folder"])
        if self.settings.get("output_folder"):
            self.output_var.set(self.settings["output_folder"])
        crf = self.settings.get("crf", 23)
        self.crf_var.set(crf)
        self.crf_label.configure(text=str(crf))
        self.skip_var.set(self.settings.get("skip_existing", True))

    def _save_current_settings(self):
        self.settings["input_folder"] = self.input_var.get()
        self.settings["output_folder"] = self.output_var.get()
        self.settings["crf"] = self.crf_var.get()
        self.settings["skip_existing"] = self.skip_var.get()
        save_settings(self.settings)

    def _on_crf_change(self, val):
        v = int(float(val))
        self.crf_label.configure(text=str(v))
        self._save_current_settings()

    def _on_skip_change(self):
        self._save_current_settings()

    # ── Dependency Banner ─────────────────────────────────────────────────────

    def _check_deps_banner(self):
        missing = [k for k, v in self.dep_results.items()
                   if k != "python" and not v.get("found")]
        if missing:
            names = ", ".join(self.dep_results[k]["display"] for k in missing)
            self.banner_label.configure(
                text=f"⚠  {names} not found — some features unavailable. "
                     f"See Help → Setup Guide."
            )
            self.banner_frame.pack(fill="x", pady=(0, 4))
            self.scan_btn.configure(state="disabled")
            self.run_btn.configure(state="disabled")
        else:
            self.banner_frame.pack_forget()

    # ── Browse ────────────────────────────────────────────────────────────────

    def _browse_input(self):
        folder = filedialog.askdirectory(title="Select Input Folder")
        if folder:
            self.input_var.set(folder)
            self._save_current_settings()

    def _browse_output(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_var.set(folder)
            self._save_current_settings()

    # ── Scan ──────────────────────────────────────────────────────────────────

    def _start_scan(self):
        input_folder = self.input_var.get()
        output_folder = self.output_var.get()

        if not input_folder or not output_folder:
            messagebox.showerror("Error", "Please select both input and output folders.")
            return
        if input_folder == output_folder:
            messagebox.showerror("Error", "Input and output folders must be different.")
            return

        self.scan_btn.configure(state="disabled", text="Scanning...")
        self.run_btn.configure(state="disabled")
        self.table.clear()
        self.summary_var.set("Scanning...")

        cancel_ev = threading.Event()

        def scan_done(records):
            self.after(0, lambda: self._on_scan_done(records))

        def progress(i, total, name):
            self.after(0, lambda: self.summary_var.set(f"Scanning {i}/{total}: {name}"))

        thread = threading.Thread(
            target=scan_folder,
            args=(Path(input_folder), Path(output_folder),
                  self.skip_var.get(), self.crf_var.get(),
                  progress, scan_done, cancel_ev),
            daemon=True
        )
        thread.start()

    def _on_scan_done(self, records):
        self.records = records
        self.table.load_records(records)
        self._update_summary()
        self.scan_btn.configure(state="normal", text="Scan Files")

        has_deps = all(v.get("found") for k, v in self.dep_results.items() if k != "python")
        has_work = any(r.enabled and r.status not in ("Unsupported — skip", "Will skip (output exists)")
                       for r in records)
        if has_deps and self.input_var.get() and self.output_var.get() and has_work:
            self.run_btn.configure(state="normal")

    def _update_summary(self):
        total = len(self.records)
        enabled = [r for r in self.records if r.enabled]
        excluded = total - len(enabled)
        will_compress = sum(1 for r in enabled
                            if r.status in ("Will compress",
                                            "Will remux (right codec, wrong container)"))
        will_copy = sum(1 for r in enabled
                        if r.status in ("Will copy (within spec)", "Will copy (still image)"))
        will_skip = sum(1 for r in enabled
                        if r.status in ("Will skip (output exists)", "Unsupported — skip"))
        parts = [f"{total} files found"]
        if excluded:
            parts.append(f"{excluded} excluded")
        parts += [
            f"{will_compress} will be compressed",
            f"{will_copy} will be copied/remuxed",
            f"{will_skip} will be skipped",
        ]
        self.summary_var.set(" — ".join(parts))

    # ── Run / Cancel ──────────────────────────────────────────────────────────

    def _start_run(self):
        input_folder = self.input_var.get()
        output_folder = self.output_var.get()

        if not input_folder or not output_folder:
            messagebox.showerror("Error", "Please select both folders and scan first.")
            return
        if input_folder == output_folder:
            messagebox.showerror("Error", "Input and output folders must be different.")
            return
        if not self.records:
            messagebox.showerror("Error", "No files to process. Please scan first.")
            return

        missing_deps = [k for k, v in self.dep_results.items()
                        if k != "python" and not v.get("found")]
        if missing_deps:
            messagebox.showerror(
                "Missing Dependencies",
                "Cannot run: required tools are missing.\nSee Help → Setup Guide."
            )
            return

        self.processing = True
        self.cancel_event.clear()
        self.run_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.scan_btn.configure(state="disabled")
        self.save_csv_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self._clear_report()

        crf = self.crf_var.get()
        # Read from table.records — same objects the checkbox handler mutates
        source = self.table.records if self.table.records else self.records
        records_to_process = [
            (orig_idx, r)
            for orig_idx, r in enumerate(source)
            if r.enabled and r.status not in ("Unsupported — skip",)
        ]
        total = len(records_to_process)
        start_time = time.time()

        def run_thread():
            tmp_dir = Path(tempfile.mkdtemp(prefix="mediapress_"))
            processed = 0
            results = []

            for i, (orig_idx, rec) in enumerate(records_to_process):
                if self.cancel_event.is_set():
                    rec.result = "Cancelled"
                    rec.action_taken = "Cancelled"
                    results.append(rec)
                    for _, remaining in records_to_process[i + 1:]:
                        remaining.result = "Cancelled"
                        remaining.action_taken = "Cancelled"
                        results.append(remaining)
                    break

                self.after(0, lambda r=rec, ii=i, oi=orig_idx: (
                    self.status_label.configure(
                        text=f"Processing file {ii+1} of {total}: {r.filename}"
                    ),
                    self.table.update_row_status(oi, "Processing...")
                ))

                process_record(rec, crf, tmp_dir)
                processed += 1
                results.append(rec)

                self.after(0, lambda oi=orig_idx, r=rec:
                           self.table.update_row_status(oi, r.status, r.result))

                elapsed = time.time() - start_time
                eta_str = ""
                if processed > 0:
                    avg = elapsed / processed
                    remaining_secs = avg * (total - processed)
                    eta_str = (
                        f"Elapsed: {int(elapsed//60)}m {int(elapsed%60)}s — "
                        f"Estimated remaining: ~{int(remaining_secs//60)}m {int(remaining_secs%60)}s"
                    )

                prog = processed / total if total > 0 else 1
                self.after(0, lambda p=prog, e=eta_str: (
                    self.progress_bar.set(p),
                    self.eta_label.configure(text=e)
                ))

            try:
                shutil.rmtree(str(tmp_dir), ignore_errors=True)
            except Exception:
                pass

            cancelled = self.cancel_event.is_set()
            self.after(0, lambda r=results, p=processed, t=total, c=cancelled:
                       self._on_run_done(r, p, t, c))

        threading.Thread(target=run_thread, daemon=True).start()

    def _cancel_run(self):
        self.cancel_event.set()
        self.cancel_btn.configure(state="disabled")
        self.status_label.configure(text="Cancelling — waiting for current file to finish...")

    def _on_run_done(self, results, processed, total, cancelled):
        self.processing = False
        self.run_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.scan_btn.configure(state="normal")
        self.save_csv_btn.configure(state="normal")
        self.progress_bar.set(1.0)

        if cancelled:
            self.status_label.configure(text=f"Cancelled — {processed} of {total} files processed.")
        else:
            self.status_label.configure(text=f"Done — {processed} files processed.")

        self._generate_report(results)

    # ── Report ────────────────────────────────────────────────────────────────

    def _clear_report(self):
        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.configure(state="disabled")

    def _append_report(self, text):
        self.report_text.configure(state="normal")
        self.report_text.insert("end", text)
        self.report_text.configure(state="disabled")
        self.report_text.see("end")

    def _generate_report(self, results):
        self._clear_report()
        self._append_report(generate_text_report(results))
        self._report_results = results

    def _save_csv(self):
        output_folder = self.output_var.get()
        if not output_folder:
            messagebox.showerror("Error", "No output folder set.")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = Path(output_folder) / f"compression_report_{ts}.csv"

        results = getattr(self, "_report_results", [])
        if not results:
            messagebox.showinfo("Info", "No report data to save.")
            return

        try:
            write_csv_report(results, csv_path)
            messagebox.showinfo("Saved", f"Report saved to:\n{csv_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save CSV:\n{e}")

    # ── Help / About ──────────────────────────────────────────────────────────

    def _open_help(self):
        HelpWindow(self, self.dep_results)

    def _open_about(self):
        AboutWindow(self)
