# -*- coding: utf-8 -*-
# MODULE 08: XLSX workbook, JMP streaming, and launcher discovery



class BeastStreamingJmpManager(object):
    """Incremental bounded JMP pool driven by the single active Fiji controller."""
    def __init__(self, output_root, settings, progress_ui, errors, total_expected):
        self.output_root = output_root
        self.settings = settings
        self.progress_ui = progress_ui
        self.errors = errors
        self.total_expected = max(0, int(total_expected))
        self.log_path = beast_log_path(output_root)
        self.mode_label = str(settings.get("_parallel_jmp_mode_label", "BEAST MODE"))
        self.safe_launch = bool(settings.get("beast_jmp_safe_launch_enabled", True))
        self.max_parallel = max(1, min(32, int(settings.get("beast_jmp_parallel_instances", settings.get("max_jmp_launches", 1)))))
        self.timeout_sec = float(settings.get("beast_jmp_timeout_sec", 900))
        self.exit_grace_sec = float(settings.get("beast_jmp_exit_grace_sec", 8))
        self.stagger_sec = float(settings.get("beast_jmp_launch_stagger_sec", 4.0))
        if self.safe_launch and self.stagger_sec < 0.25:
            self.stagger_sec = 0.25
        self.retry_count = max(0, int(settings.get("beast_jmp_retry_count", 1)))
        self.retry_delay_sec = max(0.0, float(settings.get("beast_jmp_retry_delay_sec", 6.0)))
        self.force_close = bool(settings.get("beast_force_close_jmp_after_run", True))
        self.continue_on_error = bool(settings.get("beast_continue_on_jmp_error", True))
        self.checkpoint_every = max(1, int(settings.get("beast_checkpoint_every_runs", 10)))
        self.streaming_enabled = bool(settings.get("beast_jmp_streaming_enabled", settings.get("jmp_streaming_enabled", True)))
        self.start_threshold = max(1, int(settings.get("beast_jmp_start_after_fiji_runs", settings.get("jmp_start_after_fiji_runs", 15))))
        self.jmp_exe = find_jmp_exe(settings)
        self.pending = []
        self.active = []
        self.all_published = []
        self.published_count = 0
        self.gate_open = False
        self.finished_fiji = False
        self.aborted = False
        self.canceling = False
        self.launched = 0
        self.completed = 0
        self.failed = 0
        self.skipped = 0
        self.canceled = 0
        self.max_active_observed = 0
        self.last_checkpoint_done = -1
        if self.jmp_exe == "":
            raise Exception(self.mode_label + " could not find JMP executable for streaming.")
        append_beast_log(self.log_path, settings, "JMP", "STREAM_MANAGER_START", 0, None, "WAITING", 0, 0, 0,
                         "Single Fiji controller; strict JMP limit=" + str(self.max_parallel) +
                         "; streaming=" + str(self.streaming_enabled) + "; threshold=" + str(self.start_threshold))

    def active_count(self):
        return len(self.active)

    def done_count(self):
        return self.completed + self.failed + self.canceled

    def stats(self):
        return {"launched": self.launched, "completed": self.completed, "failed": self.failed,
                "skipped": self.skipped, "canceled": self.canceled,
                "max_active_observed": self.max_active_observed}

    def _open_gate_if_ready(self):
        if self.gate_open:
            return
        if self.finished_fiji or (self.streaming_enabled and self.published_count >= self.start_threshold):
            self.gate_open = True
            reason = "Fiji finished" if self.finished_fiji else (str(self.published_count) + " Fiji runs published")
            append_beast_log(self.log_path, self.settings, "JMP", "STREAM_GATE_OPEN", 0, None, "RUNNING",
                             len(self.active), self.completed, self.failed,
                             reason + "; strict JMP limit=" + str(self.max_parallel))
            IJ.log(self.mode_label + " JMP streaming gate opened: " + reason)

    def publish(self, run, fiji_completed):
        if run is None:
            return
        self.all_published.append(run)
        self.published_count += 1
        if str(run.get("imagej_status", "COMPLETED")) != "COMPLETED" or str(run.get("jsl_file", "")).strip() == "":
            run["jmp_status"] = "NOT_RUN_IMAGEJ_FAILED"
            if str(run.get("jmp_error", "")).strip() == "":
                run["jmp_error"] = "JMP was not launched because ImageJ processing failed or was canceled."
            self.skipped += 1
            self.completed += 1
            append_beast_log(self.log_path, self.settings, "JMP", "SKIP_IMAGEJ_FAILED",
                             int(run.get("run_order_index", 0)), run, run["jmp_status"],
                             len(self.active), self.completed, self.failed, run.get("jmp_error", ""))
        else:
            self.pending.append(run)
            append_beast_log(self.log_path, self.settings, "JMP", "QUEUE",
                             int(run.get("run_order_index", 0)), run, "QUEUED",
                             len(self.active), self.completed, self.failed,
                             "Pending=" + str(len(self.pending)))
        self._open_gate_if_ready()
        self.tick(fiji_completed)

    def _launch_available(self):
        if not self.gate_open or self.aborted or global_cancel_requested():
            return
        while len(self.pending) > 0 and len(self.active) < self.max_parallel and not self.aborted and not global_cancel_requested():
            run = self.pending.pop(0)
            order_index = int(run.get("run_order_index", 0))
            refresh_jmp_output_paths(run)
            if jmp_beast_outputs_exist(run, self.settings):
                run["jmp_status"] = "SKIPPED_OUTPUTS_EXIST"
                run["jmp_elapsed_sec"] = 0.0
                run["jmp_end_timestamp"] = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
                self.skipped += 1
                self.completed += 1
                append_beast_log(self.log_path, self.settings, "JMP", "SKIP_EXISTING", order_index, run,
                                 run["jmp_status"], len(self.active), self.completed, self.failed,
                                 "Required JMP outputs already exist")
                continue
            try:
                proc = launch_beast_jmp_worker(run, self.jmp_exe, self.settings)
                job = {"run": run, "process": proc, "start": time.time(), "done_seen": None}
                self.active.append(job)
                if len(self.active) > self.max_parallel:
                    destroy_process_safely(proc, True)
                    self.active.pop()
                    raise Exception("Internal JMP worker-limit violation: active=" + str(len(self.active) + 1) +
                                    ", limit=" + str(self.max_parallel))
                self.max_active_observed = max(self.max_active_observed, len(self.active))
                register_active_process(proc)
                self.launched += 1
                run["jmp_status"] = "RUNNING"
                run["jmp_start_timestamp"] = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
                run["jmp_error"] = ""
                append_beast_log(self.log_path, self.settings, "JMP", "LAUNCH", order_index, run, "RUNNING",
                                 len(self.active), self.completed, self.failed,
                                 "Fiji still processing=" + str(not self.finished_fiji) + "; " + str(run.get("jsl_file", "")))
                IJ.log("BEAST streaming JMP launch run " + str(order_index) + "; active=" +
                       str(len(self.active)) + "/" + str(self.max_parallel))
                if self.stagger_sec > 0:
                    time.sleep(self.stagger_sec)
            except Exception as e:
                self.failed += 1
                run["jmp_status"] = "FAILED_TO_LAUNCH"
                run["jmp_error"] = str(e)
                msg = "BEAST streaming JMP launch failed for run " + str(order_index) + ": " + str(e)
                self.errors.append(msg)
                IJ.log(msg)
                append_beast_log(self.log_path, self.settings, "JMP", "LAUNCH_ERROR", order_index, run,
                                 run["jmp_status"], len(self.active), self.completed, self.failed, str(e))
                if not self.continue_on_error:
                    self.aborted = True

    def _requeue_after_failure(self, run, order_index, reason, elapsed):
        attempts = int(run.get("_beast_jmp_retry_attempts", 0))
        if attempts >= self.retry_count:
            return False
        attempts += 1
        run["_beast_jmp_retry_attempts"] = attempts
        run["jmp_status"] = "RETRY_QUEUED"
        run["jmp_error"] = reason + " Retry " + str(attempts) + "/" + str(self.retry_count) + " queued."
        run["jmp_elapsed_sec"] = elapsed
        self.pending.insert(0, run)
        append_beast_log(self.log_path, self.settings, "JMP", "RETRY_QUEUED", order_index, run,
                         run["jmp_status"], len(self.active), self.completed, self.failed, run["jmp_error"])
        IJ.log("BEAST JMP retry queued for run " + str(order_index) + ": " + run["jmp_error"])
        if self.retry_delay_sec > 0:
            time.sleep(self.retry_delay_sec)
        return True

    def _poll_active(self):
        now = time.time()
        survivors = []
        for job in self.active:
            run = job["run"]
            proc = job["process"]
            order_index = int(run.get("run_order_index", 0))
            elapsed = now - float(job["start"])
            if global_cancel_requested() or self.canceling:
                self.canceling = True
                self.aborted = True
                destroy_process_safely(proc, True)
                unregister_active_process(proc)
                self.canceled += 1
                run["jmp_status"] = "CANCELED"
                run["jmp_elapsed_sec"] = elapsed
                run["jmp_end_timestamp"] = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
                run["jmp_error"] = "Canceled by user."
                continue
            outputs_ready = jmp_beast_outputs_exist(run, self.settings)
            alive = process_is_alive(proc)
            if outputs_ready:
                if job.get("done_seen") is None:
                    job["done_seen"] = now
                    append_beast_log(self.log_path, self.settings, "JMP", "OUTPUTS_READY", order_index, run,
                                     "FINISHING", len(self.active), self.completed, self.failed,
                                     "JMP outputs and completion marker found")
                grace_elapsed = now - float(job.get("done_seen", now))
                if (not alive) or grace_elapsed >= self.exit_grace_sec:
                    if alive and self.force_close:
                        destroy_process_safely(proc, True)
                    unregister_active_process(proc)
                    self.completed += 1
                    run["jmp_status"] = "COMPLETED"
                    run["jmp_elapsed_sec"] = elapsed
                    run["jmp_end_timestamp"] = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
                    run["jmp_error"] = ""
                    append_beast_log(self.log_path, self.settings, "JMP", "COMPLETE", order_index, run,
                                     "COMPLETED", max(0, len(self.active) - 1), self.completed, self.failed,
                                     "Elapsed=" + format_elapsed_seconds(elapsed))
                    continue
                survivors.append(job)
                continue
            if not alive:
                unregister_active_process(proc)
                retry_reason = "JMP exited before required outputs and JMP_DONE.txt were created."
                if self._requeue_after_failure(run, order_index, retry_reason, elapsed):
                    continue
                self.failed += 1
                run["jmp_status"] = "FAILED_EARLY_EXIT"
                run["jmp_elapsed_sec"] = elapsed
                run["jmp_end_timestamp"] = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
                run["jmp_error"] = retry_reason
                self.errors.append("BEAST JMP early exit for run " + str(order_index))
                if not self.continue_on_error:
                    self.aborted = True
                continue
            if elapsed > self.timeout_sec:
                destroy_process_safely(proc, True)
                unregister_active_process(proc)
                retry_reason = "JMP exceeded timeout of " + str(self.timeout_sec) + " seconds."
                if self._requeue_after_failure(run, order_index, retry_reason, elapsed):
                    continue
                self.failed += 1
                run["jmp_status"] = "FAILED_TIMEOUT"
                run["jmp_elapsed_sec"] = elapsed
                run["jmp_end_timestamp"] = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
                run["jmp_error"] = retry_reason
                self.errors.append("BEAST JMP timeout for run " + str(order_index))
                if not self.continue_on_error:
                    self.aborted = True
                continue
            survivors.append(job)
        self.active = survivors

    def _abort_remaining(self):
        reason = "Canceled by user." if (self.canceling or global_cancel_requested()) else "JMP queue aborted after an error."
        active_status = "CANCELED" if (self.canceling or global_cancel_requested()) else "ABORTED"
        pending_status = "NOT_LAUNCHED_CANCELED" if (self.canceling or global_cancel_requested()) else "NOT_LAUNCHED_ABORTED"
        for job in self.active:
            proc = job.get("process")
            destroy_process_safely(proc, True)
            unregister_active_process(proc)
            run = job.get("run")
            if run is not None:
                if active_status == "CANCELED": self.canceled += 1
                else: self.failed += 1
                run["jmp_status"] = active_status
                run["jmp_error"] = reason
        self.active = []
        for run in self.pending:
            if pending_status == "NOT_LAUNCHED_CANCELED": self.canceled += 1
            else: self.failed += 1
            run["jmp_status"] = pending_status
            run["jmp_error"] = reason
        self.pending = []

    def tick(self, fiji_completed):
        if global_cancel_requested():
            self.canceling = True
            self.aborted = True
        self._open_gate_if_ready()
        if self.gate_open:
            self._poll_active()
            self._launch_available()
            # A launch failure or immediately completed skipped item can free another slot.
            self._poll_active()
            self._launch_available()
        if self.aborted:
            self._abort_remaining()
        update_beast_progress_popup(self.progress_ui,
                                    self.mode_label + ": Fiji + streaming JMP",
                                    "Fiji run " + str(fiji_completed) + "/" + str(self.total_expected) +
                                    "; JMP queued=" + str(len(self.pending)) +
                                    "; active=" + str(len(self.active)) + "/" + str(self.max_parallel),
                                    fiji_completed, self.total_expected, self.done_count(), len(self.active), len(self.errors),
                                    0 if self.finished_fiji else 1, 1)
        maybe_tile_visible_jmp_windows(self.settings, False)
        done = self.done_count()
        if done > 0 and done % self.checkpoint_every == 0 and done != self.last_checkpoint_done:
            write_beast_checkpoint(self.output_root, self.all_published, self.settings)
            self.last_checkpoint_done = done

    def finish(self, fiji_completed):
        self.finished_fiji = True
        self._open_gate_if_ready()
        while (len(self.pending) > 0 or len(self.active) > 0) and not (self.aborted and len(self.pending) == 0 and len(self.active) == 0):
            self.tick(fiji_completed)
            if len(self.pending) > 0 or len(self.active) > 0:
                time.sleep(0.5)
        self.tick(fiji_completed)
        write_beast_checkpoint(self.output_root, self.all_published, self.settings)
        status = "CANCELED" if self.canceling else ("FAILED" if self.failed > 0 and not self.continue_on_error else "COMPLETED")
        append_beast_log(self.log_path, self.settings, "JMP", "STREAM_MANAGER_COMPLETE", 0, None, status,
                         0, self.completed, self.failed,
                         "Configured limit=" + str(self.max_parallel) +
                         "; max active observed=" + str(self.max_active_observed) +
                         "; launched=" + str(self.launched) +
                         "; completed/skipped=" + str(self.completed) +
                         "; failed=" + str(self.failed) + "; canceled=" + str(self.canceled))
        maybe_tile_visible_jmp_windows(self.settings, True)
        return self.stats()

def launch_jmp_script(jsl_file, settings, launch_state):
    if not settings["launch_jmp"]:
        return False

    if launch_state[0] >= int(settings["max_jmp_launches"]):
        return False

    jmp_exe = find_jmp_exe(settings)

    if jmp_exe == "":
        IJ.log("JMP executable not found. Script was created but not launched: " + jsl_file)
        return False

    try:
        IJ.log("Launching JMP executable: " + jmp_exe)
        IJ.log("Launching generated JMP script: " + jsl_file)

        cmd = ArrayList()
        cmd.add(jmp_exe)
        cmd.add(jsl_file)

        proc = ProcessBuilder(cmd).start()
        register_active_process(proc)
        launch_state[0] = launch_state[0] + 1
        return True

    except Exception as e:
        IJ.log("Could not launch JMP automatically: " + str(e))
        return False

def write_master_files(output_root, results, settings):
    manifest = os.path.join(output_root, "ImageJ_JMP_Run_Manifest.csv")
    rows = []
    for r in results:
        rows.append([
            r.get("run_order_index", ""),
            r.get("og_image_name", r.get("image_name", os.path.basename(str(r.get("image_path", ""))))),
            r.get("report_scale_method", settings.get("report_scale_method", "Needle scale")),
            r.get("report_imaging_software", settings.get("report_imaging_software", "Swift Imaging 3.0")),
            r.get("swift_magn_profile_name", ""),
            r.get("swift_magn_resolution_pixels_per_meter", ""),
            r.get("swift_magn_um_per_pixel", ""),
            r.get("swift_magn_table_path", ""),
            r.get("original_8bit_mean_gray", ""),
            r["image_path"],
            r["run_dir"],
            r["pore_csv"],
            r["summary_csv"],
            r["jsl_file"],
            r["particle_count"],
            r.get("threshold_input_mode", ""),
            r.get("threshold_min", ""),
            r.get("threshold_max", ""),
            r.get("threshold_min_gray", ""),
            r.get("threshold_max_gray", ""),
            r.get("threshold_min_percent", ""),
            r.get("threshold_max_percent", ""),
            r.get("threshold_histogram_selected_percent", ""),
            r.get("threshold_percent_basis", ""),
            r.get("sweep_until_metric", ""),
            r.get("sweep_until_operator", ""),
            r.get("sweep_until_target_value", ""),
            r.get("sweep_until_actual_value", ""),
            r.get("sweep_until_condition_met", False),
            r.get("imagej_status", ""),
            r.get("jmp_status", ""),
            r.get("jmp_elapsed_sec", ""),
            r.get("jmp_error", "")
        ])
    write_csv(
        manifest,
        [
            "Run Order", "OG Image Name", "Scale Set Using", "Imaging Software",
            "Swift Magnification Profile", "Swift Resolution (pixels per meter, px/m)", "Applied Pixel Size (um/pixel)", "Swift Magnification Table",
            "Original 8-bit Mean Gray Value (0-255)", "Image", "Run Folder", "Pore CSV", "ImageJ Summary CSV", "JMP Script", "Particle Count",
            "Threshold Input Mode", "Threshold Min Selected Units", "Threshold Max Selected Units",
            "Threshold Min 8-bit Gray", "Threshold Max 8-bit Gray",
            "Threshold Min Cumulative Histogram %", "Threshold Max Cumulative Histogram %",
            "Histogram Pixels Inside Threshold Range %", "Threshold Percent Basis",
            "Sweep Until Metric", "Sweep Until Operator", "Sweep Until Target",
            "Sweep Until Actual", "Sweep Until Condition Met",
            "ImageJ Status", "JMP Status", "JMP Elapsed Seconds", "JMP Error"
        ],
        rows,
        settings["csv_decimals"]
    )

    jmp_exe = find_jmp_exe(settings)
    bat = os.path.join(output_root, "Run_All_JMP_Scripts.bat")
    f = open(bat, "w")
    f.write("@echo off\n")
    f.write("REM Auto-generated batch file to run every generated JMP Script.jsl\n")
    if jmp_exe == "":
        f.write("REM JMP executable was not found. Edit JMP_EXE below.\n")
        f.write("set JMP_EXE=" + str(settings["jmp_exe"]) + "\n")
    else:
        f.write("set JMP_EXE=" + jmp_exe + "\n")
    f.write("\n")
    for r2 in results:
        f.write('"%JMP_EXE%" "' + r2["jsl_file"] + '"\n')
    f.write("\n")
    f.write("pause\n")
    f.close()

    return manifest, bat


def report_original_image_group_key(run):
    source_path = str(run.get("crop_source_image", "")).strip()
    if source_path == "":
        source_path = str(run.get("image_path", "")).strip()
    if source_path != "":
        try:
            return os.path.normcase(os.path.normpath(source_path))
        except:
            return source_path.lower()
    return str(run.get("og_image_name", run.get("image_name", "Unknown image"))).strip().lower()


def report_original_image_group_name(run):
    name = str(run.get("og_image_name", "")).strip()
    if name == "":
        source_path = str(run.get("crop_source_image", run.get("image_path", ""))).strip()
        try:
            name = os.path.basename(source_path)
        except:
            name = source_path
    if name == "":
        name = str(run.get("image_name", "Original_Image"))
    return name


def group_report_results_by_original_image(results):
    ordered_keys = []
    grouped = {}
    labels = {}
    for run in results:
        key = report_original_image_group_key(run)
        if key not in grouped:
            grouped[key] = []
            labels[key] = report_original_image_group_name(run)
            ordered_keys.append(key)
        grouped[key].append(run)
    out = []
    for key in ordered_keys:
        out.append((labels.get(key, "Original_Image"), grouped.get(key, [])))
    return out


def normalize_word_report_mode(mode):
    text = str(mode).strip()
    legacy_map = {
        "Combined DOCX only": "Combined Word report",
        "Individual DOCX files only": "Completely separate individual reports",
        "Both combined and individual DOCXs": "Completely separate individual reports + combined"
    }
    if text in legacy_map:
        return legacy_map[text]
    valid = [
        "No Word reports",
        "Combined Word report",
        "Individual by image",
        "Completely separate individual reports",
        "Individual by image + combined",
        "Completely separate individual reports + combined"
    ]
    if text not in valid:
        return "Combined Word report"
    return text


def word_report_mode_output_plan(settings):
    """
    Resolve the six Word-report modes from the authoritative report dropdown only.

    v209 invariant: Excel/main-summary settings are never consulted here. In BEAST
    MODE the BEAST report dropdown is authoritative; in normal mode the normal
    report dropdown is authoritative. This prevents either summary checkbox from
    mutating completely-individual report intent.
    """
    # v209: ONE authoritative Word-report selection for both Normal and BEAST.
    # The old beast_word_report_mode key is retained only as a legacy fallback for
    # old saved settings that predate word_report_mode. It can no longer override
    # the Report-card selection when BEAST MODE is enabled.
    raw_mode = settings.get("word_report_mode", settings.get("beast_word_report_mode", "Combined Word report"))
    mode = normalize_word_report_mode(raw_mode)
    settings["word_report_mode"] = mode
    settings["beast_word_report_mode"] = mode
    return {
        "mode": mode,
        "requested": mode != "No Word reports",
        "include_combined": mode in [
            "Combined Word report",
            "Individual by image + combined",
            "Completely separate individual reports + combined"
        ],
        "include_by_image": mode in [
            "Individual by image",
            "Individual by image + combined"
        ],
        "include_separate": mode in [
            "Completely separate individual reports",
            "Completely separate individual reports + combined"
        ]
    }



# ======================================================
# v209 IDEMPOTENT REPORT EMISSION REGISTRY
# ======================================================

def _report_run_registry_key(run):
    """Stable semantic identity used to prevent the same report content from being emitted twice."""
    try:
        order_value = int(run.get("run_order_index", 0))
    except:
        order_value = 0
    if order_value > 0:
        return "ORDER:" + str(order_value)
    run_dir = str(run.get("run_dir", "")).strip()
    if run_dir != "":
        try:
            return "DIR:" + os.path.normcase(os.path.abspath(run_dir))
        except:
            return "DIR:" + run_dir.lower()
    image_path = str(run.get("crop_source_image", run.get("image_path", run.get("image_name", "")))).strip()
    return "FALLBACK:" + image_path.lower() + "|" + str(run.get("run_label", "")) + "|" + str(run.get("threshold_min", "")) + "|" + str(run.get("threshold_max", "")) + "|" + str(run.get("median_radius", ""))


def report_group_registry_key(results):
    keys = []
    for run in list(results or []):
        keys.append(_report_run_registry_key(run))
    keys.sort()
    return "||".join(keys)


def _report_emission_registry(settings):
    registry = settings.get("_report_emission_registry", None)
    if not isinstance(registry, dict):
        registry = {}
        settings["_report_emission_registry"] = registry
    return registry


def find_registered_report(settings, results):
    key = report_group_registry_key(results)
    if key == "":
        return ""
    record = _report_emission_registry(settings).get(key, None)
    if isinstance(record, dict):
        path = str(record.get("path", ""))
    else:
        path = str(record or "")
    if path != "" and path_exists(path):
        return path
    return ""


def register_report_emission(settings, results, report_path, source="normal"):
    path = str(report_path or "").strip()
    if path == "":
        return ""
    key = report_group_registry_key(results)
    if key == "":
        return path
    registry = _report_emission_registry(settings)
    existing = registry.get(key, None)
    if isinstance(existing, dict):
        old_path = str(existing.get("path", ""))
    else:
        old_path = str(existing or "")
    if old_path != "" and path_exists(old_path):
        return old_path
    registry[key] = {"path": path, "source": str(source), "run_count": len(list(results or []))}
    return path


def _unique_report_paths(paths):
    out = []
    seen = {}
    for path in list(paths or []):
        text = str(path or "").strip()
        if text == "":
            continue
        try:
            key = os.path.normcase(os.path.abspath(text))
        except:
            key = text.lower()
        if key in seen:
            continue
        seen[key] = True
        out.append(text)
    return out


def _unique_report_groups(groups):
    out = []
    seen = {}
    for group in list(groups or []):
        path = str(group.get("report_path", "")).strip()
        try:
            key = os.path.normcase(os.path.abspath(path)) if path != "" else report_group_registry_key(group.get("results", []))
        except:
            key = path.lower()
        if key in seen:
            continue
        seen[key] = True
        out.append(group)
    return out


def write_report_emission_manifest(output_root, settings):
    try:
        registry = _report_emission_registry(settings)
        rows = []
        for semantic_key in sorted(registry.keys()):
            record = registry.get(semantic_key, {})
            if isinstance(record, dict):
                path = str(record.get("path", ""))
                source = str(record.get("source", ""))
                run_count = record.get("run_count", "")
            else:
                path = str(record)
                source = "legacy"
                run_count = ""
            rows.append([semantic_key, run_count, source, path, "YES" if path_exists(path) else "NO"])
        manifest_dir = os.path.join(str(output_root), "Word_Report")
        ensure_dir(manifest_dir)
        path = os.path.join(manifest_dir, "Report_Emission_Manifest.csv")
        write_csv(path, ["Semantic Run Set", "Run Count", "First Emission Source", "Report Path", "File Exists"], rows, 9)
        settings["_report_emission_manifest"] = path
        return path
    except Exception as e:
        IJ.log("Could not write report-emission manifest: " + str(e))
        return ""

def threshold_selection_active_criteria(settings):
    criteria = []
    for criterion_index in range(1, 6):
        prefix = "threshold_selection_criterion_" + str(criterion_index) + "_"
        if not bool(settings.get(prefix + "enabled", False)):
            continue
        metric = str(settings.get(prefix + "metric", "")).strip()
        target_raw = str(settings.get(prefix + "target", "")).strip()
        importance = int(settings.get(prefix + "importance", 1))
        if importance < 1:
            importance = 1
        if importance > 5:
            importance = 5
        target_value, target_had_percent = parse_sweep_until_target(target_raw, metric)
        criteria.append({
            "index": criterion_index,
            "metric": metric,
            "target_raw": target_raw,
            "target": float(target_value),
            "importance": importance,
            "target_had_percent": target_had_percent
        })
    return criteria


def threshold_selection_image_key(run):
    source_path = str(run.get("crop_source_image", run.get("image_path", ""))).strip()
    if source_path == "":
        source_path = str(run.get("og_image_name", run.get("image_name", ""))).strip()
    try:
        source_path = os.path.normcase(os.path.abspath(source_path))
    except:
        source_path = source_path.lower()
    crop_key = ""
    if bool(run.get("crop_enabled", False)):
        crop_key = "|crop=" + str(run.get("crop_index", "")) + "|" + str(run.get("crop_region_text", ""))
    return source_path + crop_key


def threshold_selection_image_label(run):
    name = str(run.get("og_image_name", "")).strip()
    if name == "":
        try:
            name = os.path.basename(str(run.get("crop_source_image", run.get("image_path", run.get("image_name", "Image")))))
        except:
            name = str(run.get("image_name", "Image"))
    if bool(run.get("crop_enabled", False)):
        name += "_Crop_" + str(run.get("crop_index", ""))
    return name


def threshold_selection_threshold_key(run):
    return (
        str(run.get("threshold_input_mode", "")),
        str(run.get("threshold_min", "")),
        str(run.get("threshold_max", ""))
    )


def threshold_selection_threshold_label(run):
    return "T" + compact_report_name_number(run.get("threshold_min", "")) + "_to_" + compact_report_name_number(run.get("threshold_max", ""))


def threshold_selection_group_results(results):
    ordered_keys = []
    grouped = {}
    for run_index in range(len(results)):
        run = results[run_index]
        key = (threshold_selection_image_key(run), threshold_selection_threshold_key(run))
        if key not in grouped:
            grouped[key] = []
            ordered_keys.append(key)
        grouped[key].append((run_index, run))
    out = []
    for key in ordered_keys:
        out.append(grouped[key])
    return out


def threshold_selection_metric_value(run, metric):
    metrics = run.get("sweep_until_metrics", {})
    if metric in metrics:
        return float(metrics.get(metric))
    # Fallback to the final JMP summary table when available.
    summary_path = str(run.get("final_summary_csv", os.path.join(str(run.get("run_dir", "")), "Final_Summary.csv")))
    summary_rows = read_jmp_summary_for_report(summary_path)
    requested = pretty_summary_metric_name(metric)
    for row in summary_rows:
        if len(row) < 2:
            continue
        if pretty_summary_metric_name(str(row[0])) == requested:
            return float(row[1])
    raise Exception("Metric unavailable: " + str(metric))


def threshold_selection_score_run(run, criteria):
    total_weight = 0.0
    weighted_error = 0.0
    details = []
    for criterion in criteria:
        actual = float(threshold_selection_metric_value(run, criterion["metric"]))
        target = float(criterion["target"])
        importance = float(criterion["importance"])
        # Relative distance preserves comparability across counts, percentages,
        # and millimeter metrics. A target of zero uses a denominator of 1.
        denominator = max(abs(target), 1.0)
        normalized_distance = abs(actual - target) / denominator
        weighted_error += importance * normalized_distance
        total_weight += importance
        details.append({
            "metric": criterion["metric"],
            "actual": actual,
            "target": target,
            "target_raw": criterion["target_raw"],
            "importance": int(importance),
            "normalized_distance": normalized_distance
        })
    if total_weight <= 0.0:
        raise Exception("No active threshold-selection criteria were available.")
    return weighted_error / total_weight, details


def threshold_selection_median_sort_value(run):
    try:
        return float(run.get("median_radius", 0.0))
    except:
        return 0.0


def threshold_selection_manifest_rows(selected_records, criteria):
    rows = []
    header = [
        "Selection order", "Image", "Threshold input mode", "Threshold min",
        "Threshold max", "Selected median radius", "Candidate count", "Weighted score",
        "Selected run directory", "Selected report"
    ]
    for criterion in criteria:
        prefix = "Target " + str(criterion["index"])
        header.extend([
            prefix + " metric", prefix + " actual", prefix + " target",
            prefix + " importance", prefix + " normalized distance"
        ])
    rows.append(header)

    for record_index in range(len(selected_records)):
        record = selected_records[record_index]
        run = record["run"]
        row = [
            record_index + 1,
            threshold_selection_image_label(run),
            run.get("threshold_input_mode", ""),
            run.get("threshold_min", ""),
            run.get("threshold_max", ""),
            run.get("median_radius", ""),
            record.get("candidate_count", ""),
            record.get("score", ""),
            run.get("run_dir", ""),
            record.get("report_path", "")
        ]
        detail_by_metric = {}
        for detail in record.get("details", []):
            detail_by_metric[detail.get("metric", "")] = detail
        for criterion in criteria:
            detail = detail_by_metric.get(criterion["metric"], {})
            row.extend([
                criterion["metric"],
                detail.get("actual", ""),
                criterion["target_raw"],
                criterion["importance"],
                detail.get("normalized_distance", "")
            ])
        rows.append(row)
    return rows


def write_threshold_selection_manifest_xls(path, selected_records, criteria):
    rows = threshold_selection_manifest_rows(selected_records, criteria)
    workbook_xml = []
    workbook_xml.append('<?xml version="1.0" encoding="UTF-8"?>')
    workbook_xml.append('<?mso-application progid="Excel.Sheet"?>')
    workbook_xml.append('<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" ')
    workbook_xml.append('xmlns:o="urn:schemas-microsoft-com:office:office" ')
    workbook_xml.append('xmlns:x="urn:schemas-microsoft-com:office:excel" ')
    workbook_xml.append('xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet" ')
    workbook_xml.append('xmlns:html="http://www.w3.org/TR/REC-html40">')
    workbook_xml.append('<Styles>')
    workbook_xml.append('<Style ss:ID="Default" ss:Name="Normal"><Alignment ss:Vertical="Bottom"/><Borders/><Font ss:FontName="Calibri" ss:Size="10"/><Interior/><NumberFormat/><Protection/></Style>')
    workbook_xml.append('<Style ss:ID="Header"><Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/><Borders><Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#808080"/></Borders><Font ss:FontName="Calibri" ss:Size="10" ss:Bold="1"/><Interior ss:Color="#D9EAF7" ss:Pattern="Solid"/></Style>')
    workbook_xml.append('<Style ss:ID="Data"><Alignment ss:Vertical="Top" ss:WrapText="1"/><Font ss:FontName="Calibri" ss:Size="10"/></Style>')
    workbook_xml.append('<Style ss:ID="MeanEPD"><Alignment ss:Vertical="Top"/><Font ss:FontName="Calibri" ss:Size="10"/><Interior ss:Color="#EAF2F8" ss:Pattern="Solid"/></Style>')
    workbook_xml.append('<Style ss:ID="MaxEPD"><Alignment ss:Vertical="Top"/><Font ss:FontName="Calibri" ss:Size="10"/><Interior ss:Color="#FFF2CC" ss:Pattern="Solid"/></Style>')
    workbook_xml.append('<Style ss:ID="MeanEPDHeader"><Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/><Font ss:FontName="Calibri" ss:Size="10" ss:Bold="1"/><Interior ss:Color="#EAF2F8" ss:Pattern="Solid"/></Style>')
    workbook_xml.append('<Style ss:ID="MaxEPDHeader"><Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/><Font ss:FontName="Calibri" ss:Size="10" ss:Bold="1"/><Interior ss:Color="#FFF2CC" ss:Pattern="Solid"/></Style>')
    workbook_xml.append('</Styles>')
    workbook_xml.append(excel_xml_worksheet("Threshold Selection", rows))
    workbook_xml.append('</Workbook>')

    ensure_dir(os.path.dirname(path))
    output_file = codecs.open(path, "w", "utf-8")
    try:
        output_file.write("".join(workbook_xml))
    finally:
        output_file.close()
    return path


def create_threshold_selection_reports(output_root, results, settings, resolved_base):
    paths = []
    export_groups = []
    selected_records = []
    if not bool(settings.get("threshold_selection_reports_enabled", False)):
        return paths, export_groups, selected_records

    criteria = threshold_selection_active_criteria(settings)
    if len(criteria) == 0:
        raise Exception("Threshold-selection reports require at least one enabled target.")

    word_root = os.path.join(output_root, "Word_Report")
    ensure_dir(word_root)
    folder_name = safe_name(str(settings.get("threshold_selection_folder_name", "Selected_Threshold_Reports")))
    if folder_name == "":
        folder_name = "Selected_Threshold_Reports"
    selected_dir = os.path.join(word_root, folder_name)
    ensure_dir(selected_dir)

    # v209: threshold-selection output must never duplicate a normal report that
    # already contains the exact same run set. Reuse the existing file instead.
    if bool(settings.get("threshold_selection_create_full_combined", True)):
        combined_path = find_registered_report(settings, results)
        if combined_path != "":
            IJ.log("Threshold-selection full-batch report reused existing report instead of creating a duplicate: " + str(combined_path))
        else:
            combined_base = short_safe_name(resolved_base + "_Threshold_Selection_Full_Batch", 180)
            combined_path = create_word_report(output_root, results, settings, combined_base, selected_dir)
            if combined_path != "":
                register_report_emission(settings, results, combined_path, "threshold_selection_full_batch")
                paths.append(combined_path)
                export_groups.append({
                    "report_path": combined_path,
                    "results": list(results),
                    "group_type": "threshold_selection_full_batch"
                })

    grouped_results = threshold_selection_group_results(results)
    used_bases = {}
    for group_index in range(len(grouped_results)):
        candidates = grouped_results[group_index]
        scored = []
        for run_index, run in candidates:
            try:
                score, details = threshold_selection_score_run(run, criteria)
                scored.append((score, threshold_selection_median_sort_value(run), run_index, run, details))
            except Exception as score_error:
                IJ.log(
                    "Threshold selection candidate skipped: " +
                    str(run.get("run_dir", run.get("image_name", ""))) +
                    " / " + str(score_error)
                )
        if len(scored) == 0:
            IJ.log("Threshold selection group skipped because no candidate had all target metrics.")
            continue
        scored.sort(key=lambda item: (item[0], item[1], item[2]))
        best_score, best_median, best_index, best_run, best_details = scored[0]
        selected_run = dict(best_run)
        selected_run["threshold_selection_selected"] = True
        selected_run["threshold_selection_score"] = best_score
        selected_run["threshold_selection_selected_median_radius"] = best_run.get("median_radius", "")
        selected_run["threshold_selection_candidate_count"] = len(scored)
        selected_run["threshold_selection_details"] = best_details

        image_stem = os.path.splitext(os.path.basename(threshold_selection_image_label(best_run)))[0]
        image_stem = short_safe_name(safe_name(image_stem), 90)
        if image_stem == "":
            image_stem = "Image_" + str(group_index + 1)
        report_base = short_safe_name(
            image_stem + "_" + threshold_selection_threshold_label(best_run) +
            "_Selected_Median_" + compact_report_name_number(best_run.get("median_radius", "")),
            180
        )
        base_count = int(used_bases.get(report_base, 0)) + 1
        used_bases[report_base] = base_count
        if base_count > 1:
            report_base = short_safe_name(report_base + "_" + str(base_count), 180)

        selected_path = find_registered_report(settings, [selected_run])
        selected_was_created = False
        if selected_path != "":
            IJ.log("Threshold-selection run reused existing individual report instead of creating a duplicate: " + str(selected_path))
        else:
            selected_path = create_word_report(output_root, [selected_run], settings, report_base, selected_dir)
            if selected_path != "":
                register_report_emission(settings, [selected_run], selected_path, "threshold_selection_individual")
                selected_was_created = True
        record = {
            "run": selected_run,
            "score": best_score,
            "details": best_details,
            "candidate_count": len(scored),
            "report_path": selected_path
        }
        selected_records.append(record)
        if selected_path != "":
            # Only add a threshold-selection report to the final report list when
            # this feature actually emitted a new file. Reused normal reports are
            # referenced by the selection manifest but are not listed twice.
            if selected_was_created:
                paths.append(selected_path)
                export_groups.append({
                    "report_path": selected_path,
                    "results": [selected_run],
                    "group_type": "threshold_selection_individual",
                    "threshold_selection_score": best_score
                })

    manifest_path = os.path.join(selected_dir, "Threshold_Selection_Manifest.xls")
    write_threshold_selection_manifest_xls(manifest_path, selected_records, criteria)
    settings["_threshold_selection_manifest_xls"] = manifest_path
    settings["_threshold_selection_manifest_csv"] = ""
    settings["_threshold_selection_selected_count"] = len(selected_records)
    settings["_threshold_selection_output_folder"] = selected_dir
    IJ.log(
        "Threshold-selection reports: groups=" + str(len(grouped_results)) +
        "; selected=" + str(len(selected_records)) +
        "; folder=" + selected_dir
    )
    return paths, export_groups, selected_records



def individual_report_output_dir(output_root, settings=None):
    """Dedicated folder for one-DOCX-per-run output, with reports-only override support."""
    settings = settings or {}
    explicit = str(settings.get("_completely_individual_output_dir_override", "")).strip()
    if explicit != "":
        path = explicit
    else:
        parent_override = str(settings.get("_report_output_dir_override", "")).strip()
        if parent_override != "":
            path = os.path.join(parent_override, "Completely_Individual_Reports")
        else:
            path = os.path.join(output_root, "Word_Report", "Completely_Individual_Reports")
    ensure_dir(path)
    return path


def individual_report_base_name(run, run_index, settings, resolved_base):
    """Deterministic, collision-resistant file name for a single processed run."""
    try:
        order_value = int(run.get("run_order_index", run_index))
    except:
        order_value = int(run_index)
    if order_value <= 0:
        order_value = int(run_index)

    identity = report_run_identity_suffix(run, order_value)
    # Prefix every completely-individual report with its global run number. This
    # guarantees that two sweep permutations with similar/truncated labels do not
    # silently collapse onto the same apparent name.
    prefix = "Run_%04d" % int(order_value)
    if str(settings.get("report_filename_mode", "")).startswith("Ask me"):
        base = prefix + "_" + short_safe_name(str(resolved_base), 70) + "_" + identity
    else:
        base = prefix + "_" + identity
    return short_safe_name(base, 180)


def _write_completely_individual_manifest(out_dir, ordered, groups, failures):
    """Write an auditable one-row-per-run report manifest."""
    try:
        created_by_order = {}
        for group in list(groups or []):
            try:
                key = int(group.get("run_order_index", group.get("run_index", 0)))
            except:
                key = 0
            if key > 0:
                created_by_order[key] = str(group.get("report_path", ""))
        rows = []
        for idx in range(len(ordered)):
            run = ordered[idx]
            try:
                order_value = int(run.get("run_order_index", idx + 1))
            except:
                order_value = idx + 1
            rows.append([
                order_value,
                run.get("og_image_name", run.get("image_name", "")),
                run.get("run_label", ""),
                run.get("imagej_status", ""),
                "CREATED" if order_value in created_by_order else "FAILED",
                created_by_order.get(order_value, ""),
                run.get("run_dir", "")
            ])
        manifest = os.path.join(out_dir, "Individual_Report_Manifest.csv")
        write_csv(manifest, ["Run Order", "Original Image", "Run Label", "ImageJ Status", "Individual Report Status", "Individual Report Path", "Run Folder"], rows, 9)
        return manifest
    except Exception as e:
        IJ.log("Could not write completely-individual report manifest: " + str(e))
        return ""


def create_completely_individual_reports(output_root, results, settings, resolved_base):
    """
    Create exactly one independent DOCX for every reportable completed run.

    v209 invariants:
    - Word grouping is independent of BOTH summary checkboxes.
    - Every run is attempted independently.
    - A failed DOCX is retried with a fresh settings snapshot.
    - The exporter writes an auditable manifest showing every expected run.
    """
    paths = []
    groups = []
    failures = []
    out_dir = individual_report_output_dir(output_root, settings)

    ordered = list(results or [])
    try:
        ordered.sort(key=lambda r: int(r.get("run_order_index", 0)))
    except:
        pass

    settings["_completely_individual_expected_count"] = len(ordered)
    settings["_completely_individual_created_count"] = 0
    settings["_completely_individual_failures"] = []
    settings["_completely_individual_output_dir"] = out_dir

    used_bases = {}
    for idx in range(len(ordered)):
        run = ordered[idx]
        run_number = idx + 1
        base = individual_report_base_name(run, run_number, settings, resolved_base)
        base_count = int(used_bases.get(base, 0)) + 1
        used_bases[base] = base_count
        if base_count > 1:
            base = short_safe_name(base + "_" + str(base_count), 180)

        # v209: live batch reporting may already have emitted this exact run.
        # Reuse that verified DOCX instead of creating a second copy at finalization.
        report_path = find_registered_report(settings, [run])
        last_error = None
        if report_path != "":
            IJ.log("Completely individual report reused existing live/normal file: " + str(report_path))

        # Snapshot report settings so create_word_report cannot accidentally see
        # later Excel-summary state changes through the shared settings dict.
        report_settings = dict(settings)
        report_settings["word_report_mode"] = "Completely separate individual reports"
        report_settings["create_word_report"] = True
        report_settings["_resolved_report_base_name"] = ""

        for report_attempt in (range(1, 4) if report_path == "" else []):
            try:
                # Fresh dict on every attempt prevents a failed DOCX builder from
                # leaving mutable report state behind for the retry.
                attempt_settings = dict(report_settings)
                attempt_settings["_completely_individual_attempt"] = report_attempt
                report_path = create_word_report(output_root, [run], attempt_settings, base, out_dir)
                if report_path == "" or not path_exists(report_path):
                    raise Exception("DOCX builder returned no verified file")
                if os.path.getsize(report_path) <= 0:
                    raise Exception("DOCX file was created with zero bytes")
                report_path = register_report_emission(settings, [run], report_path, "completely_separate_individual")
                last_error = None
                break
            except Exception as individual_error:
                last_error = individual_error
                IJ.log(
                    "WARNING: completely individual report attempt " + str(report_attempt) +
                    "/3 failed for run " + str(run.get("run_order_index", run_number)) +
                    ": " + str(individual_error)
                )
                try:
                    IJ.log(traceback.format_exc())
                except:
                    pass

        if last_error is None and report_path != "":
            paths.append(report_path)
            groups.append({
                "report_path": report_path,
                "results": [run],
                "group_type": "completely_separate_individual",
                "run_index": run_number,
                "run_order_index": run.get("run_order_index", run_number)
            })
            IJ.log(
                "Completely individual report created " + str(len(paths)) + "/" + str(len(ordered)) +
                ": " + str(report_path)
            )
        else:
            failure_text = (
                "Run " + str(run.get("run_order_index", run_number)) + " / " +
                str(run.get("run_label", run.get("image_name", "run"))) + ": " +
                str(last_error)
            )
            failures.append(failure_text)
            IJ.log("ERROR: completely individual report failed after 3 attempts; continuing with remaining runs: " + failure_text)

    settings["_completely_individual_created_count"] = len(paths)
    settings["_completely_individual_failures"] = list(failures)
    settings["_completely_individual_manifest"] = _write_completely_individual_manifest(out_dir, ordered, groups, failures)
    IJ.log(
        "Completely individual report export finished: expected=" + str(len(ordered)) +
        "; created=" + str(len(paths)) + "; failed=" + str(len(failures)) +
        "; summary XLS=" + str(bool(settings.get("export_main_summary_xls", False))) +
        "; batch summary mirror=" + str(bool(settings.get("batch_sweep_export_all_summaries_to_all_reports", False))) +
        "; manifest=" + str(settings.get("_completely_individual_manifest", ""))
    )
    return paths, groups, failures

def create_word_reports_by_mode(output_root, results, settings):
    plan = word_report_mode_output_plan(settings)
    mode = plan["mode"]
    settings["word_report_mode"] = mode
    settings["create_word_report"] = bool(plan["requested"])
    paths = []
    export_groups = []

    if results is None or len(results) == 0:
        settings["_report_export_groups"] = export_groups
        return paths

    resolved_base = resolve_report_base_name(results, settings)
    report_output_override = str(settings.get("_report_output_dir_override", "")).strip()
    if report_output_override != "":
        ensure_dir(report_output_override)

    if plan["requested"]:
        include_combined = bool(plan["include_combined"])
        include_by_image = bool(plan["include_by_image"])
        include_separate = bool(plan["include_separate"])

        if include_combined:
            combined_base = resolved_base
            if mode != "Combined Word report":
                combined_base = short_safe_name(resolved_base + "_Combined", 180)
            combined_path = find_registered_report(settings, results)
            if combined_path == "":
                combined_path = create_word_report(output_root, results, settings, combined_base, report_output_override if report_output_override != "" else None)
                if combined_path != "":
                    combined_path = register_report_emission(settings, results, combined_path, "combined")
            else:
                IJ.log("Combined report reused an existing identical report: " + str(combined_path))
            if combined_path != "":
                paths.append(combined_path)
                export_groups.append({
                    "report_path": combined_path,
                    "results": list(results),
                    "group_type": "combined"
                })

        if include_by_image:
            grouped_results = group_report_results_by_original_image(results)
            used_bases = {}
            for group_index in range(len(grouped_results)):
                og_name, group_runs = grouped_results[group_index]
                try:
                    og_stem = os.path.splitext(os.path.basename(str(og_name)))[0]
                except:
                    og_stem = str(og_name)
                og_stem = short_safe_name(safe_name(og_stem), 110)
                if og_stem == "":
                    og_stem = "Original_Image_" + str(group_index + 1)

                if str(settings.get("report_filename_mode", "")).startswith("Ask me"):
                    group_base = short_safe_name(resolved_base + "_" + og_stem + "_By_Image", 180)
                else:
                    group_base = short_safe_name(og_stem + "_Image_Report", 180)

                base_count = int(used_bases.get(group_base, 0)) + 1
                used_bases[group_base] = base_count
                if base_count > 1:
                    group_base = short_safe_name(group_base + "_" + str(base_count), 180)

                group_path = find_registered_report(settings, group_runs)
                if group_path == "":
                    group_path = create_word_report(output_root, group_runs, settings, group_base, report_output_override if report_output_override != "" else None)
                    if group_path != "":
                        group_path = register_report_emission(settings, group_runs, group_path, "individual_by_image")
                else:
                    IJ.log("By-image report reused an existing identical report: " + str(group_path))
                if group_path != "":
                    paths.append(group_path)
                    export_groups.append({
                        "report_path": group_path,
                        "results": list(group_runs),
                        "group_type": "individual_by_image",
                        "og_image_name": og_name
                    })

        if include_separate:
            separate_paths, separate_groups, separate_failures = create_completely_individual_reports(
                output_root, results, settings, resolved_base
            )
            paths.extend(separate_paths)
            export_groups.extend(separate_groups)

    selection_paths, selection_groups, selection_records = create_threshold_selection_reports(
        output_root, results, settings, resolved_base
    )
    paths.extend(selection_paths)
    export_groups.extend(selection_groups)

    paths = _unique_report_paths(paths)
    export_groups = _unique_report_groups(export_groups)
    settings["_report_export_groups"] = export_groups
    write_report_emission_manifest(output_root, settings)
    IJ.log(
        "Word report mode=" + str(mode) +
        "; batch summary mirror=" + str(bool(settings.get("batch_sweep_export_all_summaries_to_all_reports", False))) +
        "; Excel summary export=" + str(bool(settings.get("export_main_summary_xls", False))) +
        "; threshold selection=" + str(bool(settings.get("threshold_selection_reports_enabled", False))) +
        "; reports created=" + str(len(paths))
    )
    return paths



# ======================================================
# v209 BATCH LIVE IMAGE REPORT FOLDERS
# ======================================================

def batch_live_image_reports_enabled(settings):
    return bool(settings.get("batch_enabled", False)) and bool(settings.get("batch_live_image_report_folders_enabled", False))


def _batch_live_image_stem(input_item, image_index):
    path = str(input_item.get("path", ""))
    try:
        stem = os.path.splitext(os.path.basename(path))[0]
    except:
        stem = "Image_" + str(image_index)
    stem = short_safe_name(safe_name(stem), 100)
    if stem == "":
        stem = "Image_" + str(image_index)
    try:
        crop_meta = input_item.get("crop_meta", {})
        crop_index = str(crop_meta.get("crop_index", "")).strip()
        if crop_index != "":
            stem = short_safe_name(stem + "_Crop_" + crop_index, 110)
    except:
        pass
    return stem


def batch_live_image_report_dir(output_root, input_item, image_index):
    root = os.path.join(str(output_root), "Word_Report", "Batch_Live_By_Image")
    ensure_dir(root)
    folder = ("%03d_" % int(image_index)) + _batch_live_image_stem(input_item, image_index)
    path = os.path.join(root, folder)
    ensure_dir(path)
    return path


def create_batch_live_reports_for_image(output_root, input_item, image_results, settings, image_index, image_total):
    """Create/reuse one DOCX per completed run for a finished batch image before moving on."""
    if not batch_live_image_reports_enabled(settings):
        return [], ""
    reportable = reportable_completed_results(image_results)
    out_dir = batch_live_image_report_dir(output_root, input_item, image_index)
    if len(reportable) == 0:
        IJ.log("Batch live report folder created but no completed runs were reportable for image " + str(image_index) + ": " + str(out_dir))
        return [], out_dir

    local = dict(settings)
    # Share the semantic report registry so the final batch pass reuses these
    # per-run DOCXs instead of creating a second copy of every report.
    local["_report_emission_registry"] = _report_emission_registry(settings)
    local["_completely_individual_output_dir_override"] = out_dir
    local["export_main_summary_xls"] = False
    local["batch_sweep_export_all_summaries_to_all_reports"] = False
    local["threshold_selection_reports_enabled"] = False
    local["word_report_mode"] = "Completely separate individual reports"
    local["create_word_report"] = True
    local["report_launch_all_jmp"] = False
    local["report_wait_for_jmp"] = False

    resolved_base = resolve_report_base_name(reportable, local)
    paths, groups, failures = create_completely_individual_reports(output_root, reportable, local, resolved_base)
    settings["_report_emission_registry"] = local.get("_report_emission_registry", settings.get("_report_emission_registry", {}))
    all_groups = list(settings.get("_batch_live_report_groups", []) or [])
    all_groups.extend(groups)
    settings["_batch_live_report_groups"] = _unique_report_groups(all_groups)

    marker = os.path.join(out_dir, "IMAGE_COMPLETE.txt")
    try:
        f = open(marker, "w")
        try:
            f.write("Image " + str(image_index) + " of " + str(image_total) + " complete\n")
            f.write("Image: " + str(input_item.get("path", "")) + "\n")
            f.write("Completed reportable runs: " + str(len(reportable)) + "\n")
            f.write("Individual reports present: " + str(len(paths)) + "\n")
            f.write("Report failures: " + str(len(failures)) + "\n")
            f.write("Completed: " + SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(Date()) + "\n")
        finally:
            f.close()
    except Exception as marker_error:
        IJ.log("Could not write batch image-complete marker: " + str(marker_error))

    IJ.log(
        "BATCH IMAGE COMPLETE: Image " + str(image_index) + " of " + str(image_total) +
        "; reports=" + str(len(paths)) + "; folder=" + str(out_dir)
    )
    return paths, out_dir


def prepare_batch_final_report_folders(output_root, settings):
    if not batch_live_image_reports_enabled(settings):
        return "", ""
    batch_final_root = os.path.join(str(output_root), "Word_Report", "Batch_Final")
    combined_dir = os.path.join(batch_final_root, "Combined_Report")
    summaries_dir = os.path.join(batch_final_root, "Summaries")
    ensure_dir(batch_final_root)
    ensure_dir(combined_dir)
    if bool(settings.get("export_main_summary_xls", False)):
        ensure_dir(summaries_dir)
    settings["_batch_final_combined_dir"] = combined_dir
    settings["_batch_final_summary_dir"] = summaries_dir
    return combined_dir, summaries_dir


# ======================================================
# v209 REPORT RECOVERY + MANUAL SUMMARY COLLECTION
# ======================================================

REPORT_RECOVERY_FOLDER_NAME = "Report_Recovery"
REPORT_RECOVERY_RESULTS_BASENAME = "Report_Results.pkl"
REPORT_RECOVERY_SETTINGS_BASENAME = "Report_Settings.pkl"


def report_recovery_dir(output_root):
    path = os.path.join(str(output_root), REPORT_RECOVERY_FOLDER_NAME)
    ensure_dir(path)
    return path


def _recovery_pickle_write(path, payload):
    """OneDrive-tolerant two-slot pickle writer used for report recovery state."""
    try:
        data = pickle.dumps(payload, 2)
    except Exception as e:
        IJ.log("Report recovery pickle serialization failed: " + str(e))
        return False
    slot_index = 0
    try:
        slot_index = int(payload.get("revision", 0)) % 2
    except:
        pass
    candidates = [str(path) + ".slot" + str(slot_index), str(path) + ".slot" + str(1 - slot_index), str(path)]
    for candidate in candidates:
        temp = candidate + ".tmp"
        try:
            f = open(temp, "wb")
            try:
                f.write(data)
                f.flush()
            finally:
                f.close()
            try:
                if os.path.exists(candidate):
                    os.remove(candidate)
            except:
                pass
            try:
                os.rename(temp, candidate)
            except:
                shutil.copyfile(temp, candidate)
                try:
                    os.remove(temp)
                except:
                    pass
            return True
        except Exception as e:
            try:
                if os.path.exists(temp):
                    os.remove(temp)
            except:
                pass
    IJ.log("Report recovery state could not be written: " + str(path))
    return False


def _recovery_pickle_read(path):
    candidates = [str(path) + ".slot0", str(path) + ".slot1", str(path)]
    ranked = []
    for candidate in candidates:
        try:
            if os.path.isfile(candidate):
                ranked.append((os.path.getmtime(candidate), candidate))
        except:
            pass
    ranked.sort(reverse=True)
    for _mtime, candidate in ranked:
        try:
            f = open(candidate, "rb")
            try:
                return pickle.load(f)
            finally:
                f.close()
        except Exception as e:
            IJ.log("Skipping unreadable report recovery snapshot " + str(candidate) + ": " + str(e))
    return None


def _report_safe_settings_snapshot(settings):
    out = {}
    for key in settings.keys():
        # GUI/process/runtime objects live under private keys. Only keep a few private
        # metadata strings/numbers that are useful in a recovered report.
        k = str(key)
        if k.startswith("_") and k not in ["_effective_report_scale_method", "_effective_scale_source", "_swift_magn_table_path", "_swift_magn_profile_name", "_swift_magn_resolution_pixels_per_meter", "_swift_magn_mm_per_pixel", "_swift_magn_um_per_pixel"]:
            continue
        value = settings.get(key)
        try:
            pickle.dumps(value, 2)
            out[key] = value
        except:
            out[key] = str(value)
    return out


def update_report_recovery_state(output_root, results, settings, errors=None, status="RUNNING", note=""):
    if str(output_root).strip() == "":
        return ""
    try:
        recovery_dir = report_recovery_dir(output_root)
        revision = int(settings.get("_report_recovery_revision", 0)) + 1
        settings["_report_recovery_revision"] = revision
        payload = {
            "revision": revision,
            "status": str(status),
            "updated_at": time.time(),
            "note": str(note),
            "results": list(results or []),
            "errors": list(errors or [])
        }
        _recovery_pickle_write(os.path.join(recovery_dir, REPORT_RECOVERY_RESULTS_BASENAME), payload)
        settings_payload = {
            "revision": revision,
            "updated_at": time.time(),
            "settings": _report_safe_settings_snapshot(settings)
        }
        _recovery_pickle_write(os.path.join(recovery_dir, REPORT_RECOVERY_SETTINGS_BASENAME), settings_payload)
        status_path = os.path.join(recovery_dir, "Report_Recovery_Status.txt")
        f = open(status_path, "w")
        try:
            f.write("YOURE A BETA v209 report recovery state\n")
            f.write("Status: " + str(status) + "\n")
            f.write("Completed/report records captured: " + str(len(results or [])) + "\n")
            f.write("Revision: " + str(revision) + "\n")
            f.write("Updated epoch: " + str(time.time()) + "\n")
            if str(note).strip() != "":
                f.write("Note: " + str(note) + "\n")
        finally:
            f.close()
        return recovery_dir
    except Exception as e:
        IJ.log("Could not update report recovery state: " + str(e))
        return ""


def init_report_recovery_state(output_root, settings, total_runs):
    settings["_report_recovery_revision"] = 0
    return update_report_recovery_state(output_root, [], settings, [], "STARTED", "Planned runs=" + str(total_runs))


def _recovery_result_quality(run):
    score = 0
    if str(run.get("imagej_status", "")) == "COMPLETED":
        score += 100
    if str(run.get("run_dir", "")).strip() != "" and os.path.isdir(str(run.get("run_dir", ""))):
        score += 25
    for key in ["summary_csv", "pore_csv", "starting_png", "segmented_png", "pore_map_png", "final_summary_csv"]:
        try:
            if path_exists(run.get(key, "")):
                score += 5
        except:
            pass
    return score


def _merge_recovered_results(target, source):
    keyed = {}
    for run in list(target or []) + list(source or []):
        run_dir = str(run.get("run_dir", "") or "").strip()
        if run_dir != "":
            try:
                order_key = "dir:" + os.path.normcase(os.path.abspath(run_dir))
            except:
                order_key = "dir:" + run_dir.lower()
        else:
            try:
                order_value = int(run.get("run_order_index", 0))
            except:
                order_value = 0
            if order_value > 0:
                order_key = "order:" + str(order_value)
            else:
                order_key = "fallback:" + str(run.get("image_path", "")) + "|" + str(run.get("run_label", ""))
        if order_key not in keyed or _recovery_result_quality(run) >= _recovery_result_quality(keyed[order_key]):
            keyed[order_key] = run
    out = list(keyed.values())
    try:
        out.sort(key=lambda r: int(r.get("run_order_index", 999999999)))
    except:
        pass
    return out


def _read_csv_dicts(path):
    out = []
    try:
        f = open(path, "r")
        try:
            reader = csv.reader(f)
            rows = list(reader)
        finally:
            f.close()
        if len(rows) < 2:
            return out
        headers = rows[0]
        for row in rows[1:]:
            d = {}
            for i in range(len(headers)):
                d[str(headers[i])] = row[i] if i < len(row) else ""
            out.append(d)
    except Exception as e:
        IJ.log("Could not parse recovery CSV " + str(path) + ": " + str(e))
    return out


def _find_recovery_asset(folder, include_tokens, exclude_tokens=None, extensions=None):
    if exclude_tokens is None:
        exclude_tokens = []
    if extensions is None:
        extensions = [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
    try:
        if not os.path.isdir(folder):
            return ""
        names = os.listdir(folder)
    except:
        return ""
    includes = [str(x).lower() for x in include_tokens]
    excludes = [str(x).lower() for x in exclude_tokens]
    for name in sorted(names):
        low = str(name).lower()
        if os.path.splitext(low)[1] not in extensions:
            continue
        if not all(token in low for token in includes):
            continue
        if any(token in low for token in excludes):
            continue
        return os.path.join(folder, name)
    return ""


def _parse_processing_notes(notes_path):
    out = {}
    try:
        for line in open(notes_path, "r"):
            text = str(line).strip()
            if ": " in text:
                key, value = text.split(": ", 1)
                out[key.strip()] = value.strip()
    except:
        pass
    return out


def _decorate_recovered_run(run, output_root):
    run_dir = str(run.get("run_dir", "") or "").strip()
    image_dir = os.path.join(run_dir, "Images") if run_dir != "" else ""
    run["image_dir"] = image_dir
    if str(run.get("image_name", "")).strip() == "":
        run["image_name"] = os.path.basename(str(run.get("image_path", "")))
    if str(run.get("og_image_name", "")).strip() == "":
        run["og_image_name"] = run.get("image_name", "Recovered image")
    if str(run.get("run_label", "")).strip() == "":
        run["run_label"] = os.path.basename(run_dir) if run_dir != "" else "Recovered run"
    run["base_safe"] = str(run.get("base_safe", os.path.basename(run_dir)))
    run.setdefault("crop_enabled", False)
    run.setdefault("quality_warnings", [])
    run.setdefault("bad_image_issues", [])
    run.setdefault("bad_image_status", "RECOVERED")
    run.setdefault("step_notes", ["Recovered from an existing output folder by v209 reports-only mode."])
    run.setdefault("sample_size_text", "Recovered run")
    run.setdefault("threshold_force_8bit_numbers", True)
    run.setdefault("manual_largest_pore_entries", [])
    run.setdefault("manual_selected_pore_entries", [])
    run.setdefault("manual_strand_lengths_mm", [])
    run.setdefault("manual_strand_trace_tools", [])
    run.setdefault("summary_rows_for_report", [])

    if run_dir != "":
        notes_files = []
        try:
            notes_files = [os.path.join(run_dir, n) for n in os.listdir(run_dir) if str(n).endswith("_ImageJ_Processing_Notes.txt")]
        except:
            pass
        if len(notes_files) > 0:
            note_map = _parse_processing_notes(notes_files[0])
            if str(run.get("image_path", "")).strip() == "":
                run["image_path"] = note_map.get("Input image", "")
            run["og_image_name"] = note_map.get("OG image name", run.get("og_image_name", ""))
            run["sample_size_text"] = note_map.get("Image details", run.get("sample_size_text", "Recovered run"))
            run["starting_png"] = note_map.get("True original input for report PNG saved", run.get("starting_png", ""))
            run["original_png"] = note_map.get("Original PNG saved", run.get("original_png", ""))
            run["preprocessed_tif"] = note_map.get("Preprocessed image saved", run.get("preprocessed_tif", ""))
            run["segmented_tif"] = note_map.get("Segmented mask saved", run.get("segmented_tif", ""))
            run["segmented_overlay_png"] = note_map.get("Segmented-over-original overlay PNG", run.get("segmented_overlay_png", ""))
            run["segmented_pores_overlay_png"] = note_map.get("Segmented black/white overlay PNG", run.get("segmented_pores_overlay_png", ""))
            run["pore_csv"] = note_map.get("ImageJ pore results CSV", run.get("pore_csv", ""))
            run["summary_csv"] = note_map.get("ImageJ summary CSV", run.get("summary_csv", ""))
            run["jsl_file"] = note_map.get("JMP script created", run.get("jsl_file", ""))

    # Recover report media by deterministic filename patterns if the original run
    # record is unavailable. JPEGs are accepted after the space-saving cleanup.
    if str(run.get("starting_png", "")).strip() == "" or not path_exists(run.get("starting_png", "")):
        run["starting_png"] = _find_recovery_asset(image_dir, ["true_original_input_for_report"], [], [".png", ".jpg", ".jpeg"])
    if str(run.get("preprocessed_png", "")).strip() == "" or not path_exists(run.get("preprocessed_png", "")):
        run["preprocessed_png"] = _find_recovery_asset(image_dir, ["preprocessed"], [], [".png", ".jpg", ".jpeg"])
    if str(run.get("segmented_png", "")).strip() == "" or not path_exists(run.get("segmented_png", "")):
        run["segmented_png"] = _find_recovery_asset(image_dir, ["segmented"], ["overlay", "selected", "pores"], [".png", ".jpg", ".jpeg"])
    if str(run.get("outlines_png", "")).strip() == "" or not path_exists(run.get("outlines_png", "")):
        run["outlines_png"] = _find_recovery_asset(image_dir, ["outline"], [], [".png", ".jpg", ".jpeg"])
    if str(run.get("pore_map_png", "")).strip() == "" or not path_exists(run.get("pore_map_png", "")):
        run["pore_map_png"] = _find_recovery_asset(image_dir, ["pore_map"], ["all_pore"], [".png", ".jpg", ".jpeg"])
    if str(run.get("pore_map_tif", "")).strip() == "" or not path_exists(run.get("pore_map_tif", "")):
        run["pore_map_tif"] = _find_recovery_asset(image_dir, ["pore_map"], ["all_pore"], [".tif", ".tiff"])
    if str(run.get("all_pore_map_png", "")).strip() == "" or not path_exists(run.get("all_pore_map_png", "")):
        run["all_pore_map_png"] = _find_recovery_asset(image_dir, ["all_pore", "map"], [], [".png", ".jpg", ".jpeg"])
    if str(run.get("strand_heat_map_png", "")).strip() == "" or not path_exists(run.get("strand_heat_map_png", "")):
        run["strand_heat_map_png"] = _find_recovery_asset(image_dir, ["rainbow", "heat", "map"], [], [".png", ".jpg", ".jpeg"])
        if str(run.get("strand_heat_map_png", "")).strip() == "":
            run["strand_heat_map_png"] = _find_recovery_asset(os.path.join(output_root, "Heat Maps"), ["rainbow", "heat", "map"], [], [".png", ".jpg", ".jpeg"])
    refresh_jmp_output_paths(run)
    run["summary_rows_for_report"] = read_jmp_summary_for_report(run.get("final_summary_csv", ""))
    return run


def recover_report_results_from_output(output_root, current_settings=None):
    """Recover as many completed/reportable run dictionaries as possible."""
    recovered = []
    recovered_settings = {}

    # v209 native controller report snapshot.
    payload = _recovery_pickle_read(os.path.join(output_root, REPORT_RECOVERY_FOLDER_NAME, REPORT_RECOVERY_RESULTS_BASENAME))
    if isinstance(payload, dict):
        recovered = _merge_recovered_results(recovered, payload.get("results", []))
    sp = _recovery_pickle_read(os.path.join(output_root, REPORT_RECOVERY_FOLDER_NAME, REPORT_RECOVERY_SETTINGS_BASENAME))
    if isinstance(sp, dict):
        recovered_settings = dict(sp.get("settings", {}))

    # BEAST v202+ worker/agent snapshots, including rotating OneDrive-safe slots.
    worker_root = os.path.join(output_root, "BEAST_Fiji_Workers")
    if os.path.isdir(worker_root):
        try:
            names = os.listdir(worker_root)
        except:
            names = []
        bases = []
        for name in names:
            low = str(name).lower()
            if "_result.pkl" in low:
                base = os.path.join(worker_root, str(name).split(".slot")[0])
                if base not in bases:
                    bases.append(base)
        for base in bases:
            worker_payload = _recovery_pickle_read(base)
            if isinstance(worker_payload, dict):
                recovered = _merge_recovered_results(recovered, worker_payload.get("results", []))

    # Master manifest fallback.
    manifest_path = os.path.join(output_root, "ImageJ_JMP_Run_Manifest.csv")
    if os.path.isfile(manifest_path):
        manifest_runs = []
        for row in _read_csv_dicts(manifest_path):
            run = {
                "run_order_index": row.get("Run Order", ""),
                "og_image_name": row.get("OG Image Name", ""),
                "report_scale_method": row.get("Scale Set Using", ""),
                "report_imaging_software": row.get("Imaging Software", ""),
                "swift_magn_profile_name": row.get("Swift Magnification Profile", ""),
                "swift_magn_resolution_pixels_per_meter": row.get("Swift Resolution (pixels per meter, px/m)", ""),
                "swift_magn_um_per_pixel": row.get("Applied Pixel Size (um/pixel)", ""),
                "swift_magn_table_path": row.get("Swift Magnification Table", ""),
                "image_path": row.get("Image", ""),
                "run_dir": row.get("Run Folder", ""),
                "pore_csv": row.get("Pore CSV", ""),
                "summary_csv": row.get("ImageJ Summary CSV", ""),
                "jsl_file": row.get("JMP Script", ""),
                "particle_count": row.get("Particle Count", ""),
                "threshold_input_mode": row.get("Threshold Input Mode", ""),
                "threshold_min": row.get("Threshold Min Selected Units", ""),
                "threshold_max": row.get("Threshold Max Selected Units", ""),
                "threshold_min_gray": row.get("Threshold Min 8-bit Gray", ""),
                "threshold_max_gray": row.get("Threshold Max 8-bit Gray", ""),
                "threshold_min_percent": row.get("Threshold Min Cumulative Histogram %", ""),
                "threshold_max_percent": row.get("Threshold Max Cumulative Histogram %", ""),
                "threshold_histogram_selected_percent": row.get("Histogram Pixels Inside Threshold Range %", ""),
                "threshold_percent_basis": row.get("Threshold Percent Basis", ""),
                "imagej_status": row.get("ImageJ Status", ""),
                "jmp_status": row.get("JMP Status", ""),
                "jmp_elapsed_sec": row.get("JMP Elapsed Seconds", ""),
                "jmp_error": row.get("JMP Error", "")
            }
            manifest_runs.append(run)
        recovered = _merge_recovered_results(recovered, manifest_runs)

    # Checkpoint fallback when a failure occurred before the manifest was written.
    checkpoint_path = os.path.join(output_root, "BEAST_MODE_Checkpoint.csv")
    if os.path.isfile(checkpoint_path):
        cp_runs = []
        for row in _read_csv_dicts(checkpoint_path):
            cp_runs.append({
                "run_order_index": row.get("Run Order", ""),
                "image_path": row.get("Image", ""),
                "run_label": row.get("Run Label", ""),
                "run_dir": row.get("Run Folder", ""),
                "jsl_file": row.get("JMP Script", ""),
                "particle_count": row.get("Particle Count", ""),
                "imagej_status": row.get("ImageJ Status", ""),
                "jmp_status": row.get("JMP Status", ""),
                "jmp_elapsed_sec": row.get("JMP Elapsed Seconds", ""),
                "jmp_error": row.get("JMP Error", ""),
                "final_summary_csv": row.get("Final Summary CSV", ""),
                "jmp_done_file": row.get("JMP Done File", "")
            })
        recovered = _merge_recovered_results(recovered, cp_runs)

    # Last-resort run-folder scan. This recovers normal-mode runs even if the script
    # crashed before writing a manifest/checkpoint.
    try:
        root_names = os.listdir(output_root)
    except:
        root_names = []
    scan_runs = []
    for name in root_names:
        run_dir = os.path.join(output_root, name)
        low = str(name).lower()
        if not os.path.isdir(run_dir) or low in ["word_report", "report_recovery", "beast_fiji_workers", "beast_preflight", "heat maps"]:
            continue
        try:
            note_files = [n for n in os.listdir(run_dir) if str(n).endswith("_ImageJ_Processing_Notes.txt")]
        except:
            note_files = []
        if len(note_files) == 0:
            continue
        note_map = _parse_processing_notes(os.path.join(run_dir, note_files[0]))
        scan_runs.append({
            "run_dir": run_dir,
            "run_label": name,
            "image_path": note_map.get("Input image", ""),
            "og_image_name": note_map.get("OG image name", ""),
            "sample_size_text": note_map.get("Image details", "Recovered run"),
            "pore_csv": note_map.get("ImageJ pore results CSV", ""),
            "summary_csv": note_map.get("ImageJ summary CSV", ""),
            "jsl_file": note_map.get("JMP script created", ""),
            "starting_png": note_map.get("True original input for report PNG saved", ""),
            "imagej_status": "COMPLETED"
        })
    recovered = _merge_recovered_results(recovered, scan_runs)

    decorated = []
    for index_value in range(len(recovered)):
        run = recovered[index_value]
        if str(run.get("run_order_index", "")).strip() == "":
            run["run_order_index"] = index_value + 1
        decorated.append(_decorate_recovered_run(run, output_root))
    decorated = _merge_recovered_results([], decorated)
    return decorated, recovered_settings


def reportable_completed_results(results):
    out = []
    for run in list(results or []):
        status = str(run.get("imagej_status", "")).upper().strip()
        run_dir = str(run.get("run_dir", "") or "").strip()
        has_output = False
        for key in ["summary_csv", "pore_csv", "starting_png", "segmented_png", "pore_map_png"]:
            try:
                if path_exists(run.get(key, "")):
                    has_output = True
                    break
            except:
                pass
        if status == "COMPLETED" or (run_dir != "" and has_output):
            out.append(run)
    try:
        out.sort(key=lambda r: int(r.get("run_order_index", 0)))
    except:
        pass
    return out


def build_final_report_ledger(output_root, results, settings):
    """
    Build the authoritative final report ledger.

    BEAST uses disposable Fiji processes, so the final reporter must not depend on
    only one in-memory controller list. Merge the controller records with the
    persistent report-recovery state, worker result snapshots, manifest, checkpoint,
    and run-folder scan, then keep exactly the reportable completed runs.
    """
    merged = _merge_recovered_results([], list(results or []))
    if bool(settings.get("beast_mode_enabled", False)) or bool(settings.get("always_finalize_partial_report", True)):
        try:
            recovered, _recovered_settings = recover_report_results_from_output(output_root, settings)
            merged = _merge_recovered_results(merged, recovered)
        except Exception as e:
            IJ.log("Final report ledger recovery merge warning: " + str(e))
    reportable = reportable_completed_results(merged)

    # One completed run order must map to exactly one final report record. Recovery
    # sources can describe the same run at different levels of detail; choose the
    # richest record instead of emitting duplicate reports.
    deduped_by_order = {}
    unnumbered = []
    for run in reportable:
        try:
            order_value = int(run.get("run_order_index", 0))
        except:
            order_value = 0
        if order_value > 0:
            if order_value not in deduped_by_order or _recovery_result_quality(run) >= _recovery_result_quality(deduped_by_order[order_value]):
                deduped_by_order[order_value] = run
        else:
            unnumbered.append(run)
    reportable = list(deduped_by_order.values()) + unnumbered
    try:
        reportable.sort(key=lambda r: int(r.get("run_order_index", 999999999)))
    except:
        pass

    settings["_final_report_ledger_count"] = len(reportable)
    try:
        settings["_final_report_ledger_run_orders"] = [int(r.get("run_order_index", 0)) for r in reportable]
    except:
        settings["_final_report_ledger_run_orders"] = []
    IJ.log(
        "Final report ledger: in-memory records=" + str(len(list(results or []))) +
        "; merged records=" + str(len(merged)) +
        "; reportable completed runs=" + str(len(reportable)) +
        "; run orders=" + str(settings.get("_final_report_ledger_run_orders", []))
    )
    return reportable


def create_minimal_status_report(output_root, settings, status_text, errors=None, recovered_count=0):
    """Create a valid DOCX even when zero analytical runs completed."""
    status_run = {
        "run_order_index": 1,
        "image_path": "",
        "image_name": "Run status",
        "og_image_name": "Run status",
        "run_label": str(status_text),
        "run_dir": "",
        "imagej_status": str(status_text),
        "jmp_status": "NOT_AVAILABLE",
        "sample_size_text": "No completed analytical run was available for this report.",
        "threshold_min": "",
        "threshold_max": "",
        "threshold_force_8bit_numbers": True,
        "bad_image_status": "N/A",
        "bad_image_issues": [],
        "quality_warnings": list(errors or []),
        "step_notes": ["Automatic v209 recovery/status report.", "Recovered completed runs: " + str(recovered_count)] + [str(e) for e in list(errors or [])],
        "summary_rows_for_report": [],
        "manual_largest_pore_entries": [],
        "manual_selected_pore_entries": [],
        "manual_strand_lengths_mm": [],
        "manual_strand_trace_tools": []
    }
    local = dict(settings)
    local["word_report_mode"] = "Combined Word report"
    local["create_word_report"] = True
    local["report_launch_all_jmp"] = False
    local["report_wait_for_jmp"] = False
    local["manual_largest_pore_enabled"] = False
    local["manual_selected_pore_enabled"] = False
    local["manual_strand_measurement_enabled"] = False
    local["report_include_strand_heat_map"] = False
    base = "GDL_Partial_Status_Report_" + SimpleDateFormat("yyyyMMdd_HHmmss").format(Date())
    return create_word_report(output_root, [status_run], local, base)


def finalize_partial_reports(output_root, results, settings, errors=None, reason="PARTIAL", force=False):
    """Finish reports from everything already completed; never rerun Fiji analysis."""
    reportable = reportable_completed_results(results)
    paths = []
    if len(reportable) > 0:
        local = dict(settings)
        plan = word_report_mode_output_plan(local)
        if not plan.get("requested", False):
            # 'Always report' invariant: No Word reports suppresses the full selected
            # report set, but a combined recovery report is still produced.
            local["word_report_mode"] = "Combined Word report"
            local["create_word_report"] = True
        local["report_launch_all_jmp"] = False
        local["report_wait_for_jmp"] = False
        try:
            paths = create_word_reports_by_mode(output_root, reportable, local)
        except Exception as e:
            IJ.log("Partial report finalization failed; creating status report instead: " + str(e))
            paths = []
    if len(paths) == 0:
        try:
            paths = [create_minimal_status_report(output_root, settings, reason, errors, len(reportable))]
        except Exception as e2:
            IJ.log("Could not create minimal partial/status report: " + str(e2))
            paths = []
    update_report_recovery_state(output_root, reportable, settings, errors, "REPORT_FINALIZED", reason + "; reports=" + str(len(paths)))
    return paths


def emergency_finalize_report_from_shared(shared_globals, error_text):
    """Launcher-level safety net for uncaught failures after an output root exists."""
    try:
        output_root = str(shared_globals.get("output_root", "") or "").strip()
        settings = shared_globals.get("settings", None)
        if output_root == "" or settings is None or not os.path.isdir(output_root):
            return []
        if int(settings.get("_report_recovery_revision", 0)) <= 0:
            return []
        if bool(settings.get("_final_report_phase_completed", False)):
            IJ.log("Emergency report finalizer skipped because the final report phase already created report files.")
            return []
        if bool(shared_globals.get("BEAST_FIJI_WORKER_CONFIG", None)):
            return []
        results = list(shared_globals.get("results", []))
        errors = list(shared_globals.get("errors", []))
        errors.append("Unhandled script failure: " + str(error_text))
        IJ.log("v209 emergency report finalizer activated: " + str(error_text))
        return finalize_partial_reports(output_root, results, settings, errors, "UNHANDLED FAILURE", True)
    except Exception as emergency_error:
        try:
            IJ.log("Emergency report finalizer itself failed: " + str(emergency_error))
        except:
            pass
        return []


def _summary_candidate_paths(output_root, generated_paths=None):
    candidates = []
    for path in list(generated_paths or []):
        try:
            if os.path.isfile(str(path)) and str(path) not in candidates:
                candidates.append(str(path))
        except:
            pass
    # Include already-existing summary workbooks/CSVs in case reports-only recovery
    # is being used after an earlier failed run.
    for base, dirs, files in os.walk(str(output_root)):
        low_base = str(base).lower()
        if "completely_individual_reports" in low_base and len(candidates) > 300:
            continue
        for name in files:
            low = str(name).lower()
            if not (low.endswith(".xls") or low.endswith(".xlsx") or low.endswith(".csv")):
                continue
            # Keep the picker focused on report-level summary exports, not the
            # thousands of per-run Final_Summary.csv files in a large sweep.
            if (("_summaries" in low) or ("all_data" in low) or ("revised_summary" in low)) and "checkpoint" not in low and "manifest" not in low and "detailed_log" not in low:
                p = os.path.join(base, name)
                if p not in candidates:
                    candidates.append(p)
    return candidates


def _copy_summary_file(source_path, destination_dir):
    ensure_dir(destination_dir)
    name = os.path.basename(str(source_path))
    dest = os.path.join(destination_dir, name)
    if os.path.isfile(dest):
        root, ext = os.path.splitext(dest)
        index_value = 2
        while os.path.isfile(root + "_" + str(index_value) + ext):
            index_value += 1
        dest = root + "_" + str(index_value) + ext
    shutil.copy2(str(source_path), dest)
    return dest


def manual_summary_selection_dialog(output_root, generated_paths, settings):
    if str(settings.get("summary_xls_destination", "")) != "Manual selection at end":
        return []
    if not bool(settings.get("export_main_summary_xls", False)):
        return []
    candidates = _summary_candidate_paths(output_root, generated_paths)
    if len(candidates) == 0:
        IJ.showMessage("Manual Summary Selection", "No summary files were found to copy.")
        return []

    display = ["COPY ALL AVAILABLE SUMMARIES (" + str(len(candidates)) + ")"]
    for path in candidates:
        display.append(os.path.basename(path) + "  |  " + os.path.dirname(path))
    open_index = len(display)
    display.append("OPEN SUMMARY SOURCE/STAGING FOLDER")
    done_index = len(display)
    display.append("DONE")
    combo = JComboBox(display)
    copied = []
    destination_dir = ""

    while True:
        result = JOptionPane.showConfirmDialog(None, combo, "Manual Summary Selection - choose a summary to copy", JOptionPane.OK_CANCEL_OPTION, JOptionPane.PLAIN_MESSAGE)
        if result != JOptionPane.OK_OPTION:
            break
        selected_index = int(combo.getSelectedIndex())
        if selected_index == done_index:
            break
        if selected_index == open_index:
            try:
                source_folder = os.path.join(output_root, "Word_Report", "_Manual_Summary_Staging")
                if not os.path.isdir(source_folder) and len(candidates) > 0:
                    source_folder = os.path.dirname(candidates[0])
                open_output_folder(source_folder)
            except Exception as open_error:
                IJ.log("Could not open summary source folder: " + str(open_error))
            continue

        source_paths = candidates if selected_index == 0 else [candidates[selected_index - 1]]
        if destination_dir == "":
            set_gdl_file_chooser_start_directory()
            chooser = DirectoryChooser("Choose parent folder for NEW Selected Summaries folder")
            parent = chooser.getDirectory()
            if parent is None:
                break
            default_name = "Selected_Summaries_" + SimpleDateFormat("yyyyMMdd_HHmmss").format(Date())
            folder_name = JOptionPane.showInputDialog(None, "New folder name:", default_name)
            if folder_name is None:
                break
            folder_name = short_safe_name(safe_name(str(folder_name)), 120)
            if folder_name == "":
                folder_name = default_name
            destination_dir = os.path.join(parent, folder_name)
            ensure_dir(destination_dir)

        for source in source_paths:
            try:
                dest = _copy_summary_file(source, destination_dir)
                copied.append(dest)
                IJ.log("Manual summary copy created: " + str(dest))
            except Exception as copy_error:
                IJ.log("Manual summary copy failed for " + str(source) + ": " + str(copy_error))

        if selected_index == 0:
            IJ.showMessage("Manual Summary Selection", "Copied " + str(len(source_paths)) + " summary files to:\n" + destination_dir)
            break
        else:
            choice = JOptionPane.showConfirmDialog(None, "Copied:\n" + os.path.basename(source_paths[0]) + "\n\nCopy another summary into the same folder?", "Manual Summary Selection", JOptionPane.YES_NO_OPTION)
            if choice != JOptionPane.YES_OPTION:
                break

    if len(copied) > 0:
        try:
            open_output_folder(destination_dir)
        except:
            pass
    return copied


def find_output_root_for_existing_report(report_path):
    """Find the GDL output root associated with an already generated YOURE A BETA DOCX."""
    report_path = os.path.abspath(str(report_path))
    current = os.path.dirname(report_path)
    checked = []
    for depth in range(12):
        if current is None or str(current).strip() == "":
            break
        checked.append(current)
        base = os.path.basename(current).lower()
        if base == "word_report":
            return os.path.dirname(current)
        parent = os.path.dirname(current)
        if os.path.basename(parent).lower() == "word_report":
            return os.path.dirname(parent)
        if os.path.isdir(os.path.join(current, REPORT_RECOVERY_FOLDER_NAME)):
            return current
        if os.path.isfile(os.path.join(current, "BEAST_MODE_Checkpoint.csv")):
            return current
        if os.path.isdir(os.path.join(current, "BEAST_Fiji_Workers")):
            return current
        if parent == current:
            break
        current = parent
    return ""


def reports_only_output_mode(settings):
    requested = str(settings.get("reports_only_output_mode", "Use normal Report card selection")).strip()
    if requested == "" or requested == "Use normal Report card selection":
        requested = str(settings.get("word_report_mode", "Combined Word report"))
    return normalize_word_report_mode(requested)


def reports_only_split_output_dir(output_root, source_report_path):
    stem = os.path.splitext(os.path.basename(str(source_report_path)))[0]
    stem = short_safe_name(safe_name(stem), 90)
    if stem == "":
        stem = "Existing_Report"
    out_dir = os.path.join(output_root, "Word_Report", "Split_From_" + stem)
    ensure_dir(out_dir)
    return out_dir


def run_reports_only_recovery(output_root, settings, source_report_path=""):
    recovered, recovered_settings = recover_report_results_from_output(output_root, settings)
    # Current GUI choices control report grouping/destination/appearance. Recovered
    # settings only fill missing metadata defaults.
    merged_settings = dict(recovered_settings)
    merged_settings.update(dict(settings))
    merged_settings["reports_only_recovery_mode"] = True
    merged_settings["beast_mode_enabled"] = False
    merged_settings["word_report_mode"] = reports_only_output_mode(merged_settings)
    if merged_settings["word_report_mode"] == "No Word reports":
        merged_settings["word_report_mode"] = "Combined Word report"
    merged_settings["create_word_report"] = True
    source_report_path = str(source_report_path or "").strip()
    if source_report_path != "":
        merged_settings["reports_only_source_report_path"] = source_report_path
        split_dir = reports_only_split_output_dir(output_root, source_report_path)
        merged_settings["_report_output_dir_override"] = split_dir
        merged_settings["_completely_individual_output_dir_override"] = os.path.join(split_dir, "Completely_Individual_Reports")
        IJ.log("Reports-only existing-report split source: " + source_report_path)
        IJ.log("Reports-only split/rebuild destination: " + split_dir)
    # Reports-only means no Fiji rerun and no new JMP analysis launch. The builder
    # uses whatever JMP summaries/histograms already exist and falls back to ImageJ
    # summaries when needed.
    merged_settings["report_launch_all_jmp"] = False
    merged_settings["report_wait_for_jmp"] = False
    reportable = reportable_completed_results(recovered)
    if len(reportable) == 0:
        paths = [create_minimal_status_report(output_root, merged_settings, "REPORTS-ONLY RECOVERY: no completed runs found", [], 0)]
        summary_paths = []
    else:
        IJ.log("Reports-only recovery: Fiji/JMP analysis relaunch is disabled; using existing report artifacts only.")
        paths = create_word_reports_by_mode(output_root, reportable, merged_settings)
        if len(paths) == 0:
            paths = [create_minimal_status_report(output_root, merged_settings, "REPORTS-ONLY RECOVERY", [], len(reportable))]
        summary_paths = export_main_summary_xls_for_reports(output_root, paths, reportable, merged_settings) if merged_settings.get("export_main_summary_xls", False) else []
    manual_copies = manual_summary_selection_dialog(output_root, summary_paths, merged_settings)
    update_report_recovery_state(output_root, reportable, merged_settings, [], "REPORTS_ONLY_COMPLETED", "reports=" + str(len(paths)) + "; manual summary copies=" + str(len(manual_copies)))
    return paths, summary_paths, manual_copies, reportable


def excel_xml_number_or_string(value):
    if value is None:
        return "String", ""
    if isinstance(value, bool):
        return "String", str(value)
    if isinstance(value, int) or isinstance(value, float):
        try:
            f = float(value)
            if math.isnan(f) or math.isinf(f):
                return "String", str(value)
        except:
            pass
        return "Number", str(value)

    text = str(value).strip()
    if text == "":
        return "String", ""
    if text.endswith("%"):
        return "String", text

    allowed = "0123456789+-.eE,"
    numeric_candidate = True
    for ch in text:
        if ch not in allowed:
            numeric_candidate = False
            break
    if numeric_candidate:
        try:
            number_value = float(text.replace(",", ""))
            if not math.isnan(number_value) and not math.isinf(number_value):
                return "Number", str(number_value)
        except:
            pass
    return "String", text


def excel_xml_cell(value, style_id="Data"):
    value_type, clean_value = excel_xml_number_or_string(value)
    return (
        '<Cell ss:StyleID="' + str(style_id) + '"><Data ss:Type="' +
        str(value_type) + '">' + xml_escape(clean_value) + '</Data></Cell>'
    )


def excel_xml_worksheet(sheet_name, rows, title_text=None):
    # Simple one-table worksheet: no merged title banner, one plain header row, and data rows.
    # Average/Mean EPD and Max EPD columns are highlighted for rapid comparison.
    epd_column_styles = {}
    if rows is not None and len(rows) > 0 and rows[0] is not None:
        for header_index in range(len(rows[0])):
            header_text = str(rows[0][header_index]).strip().lower()
            if header_text in ["average epd (mm)", "mean epd (mm)"]:
                epd_column_styles[header_index] = ("MeanEPDHeader", "MeanEPD")
            elif header_text == "max epd (mm)":
                epd_column_styles[header_index] = ("MaxEPDHeader", "MaxEPD")
    safe_sheet = str(sheet_name).replace("/", "-").replace("\\", "-").replace("?", "-")
    safe_sheet = safe_sheet.replace("*", "-").replace("[", "(").replace("]", ")").replace(":", "-")
    if len(safe_sheet) > 31:
        safe_sheet = safe_sheet[:31]
    if safe_sheet == "":
        safe_sheet = "Summary"

    max_cols = 1
    for row in rows:
        if row is not None and len(row) > max_cols:
            max_cols = len(row)

    out = []
    out.append('<Worksheet ss:Name="' + xml_escape(safe_sheet) + '"><Table>')
    for col_index in range(max_cols):
        width = 90
        if col_index == 0:
            width = 170
        elif col_index == 1:
            width = 130
        out.append('<Column ss:AutoFitWidth="0" ss:Width="' + str(width) + '"/>')

    for row_index in range(len(rows)):
        row = rows[row_index]
        if row is None:
            row = []
        out.append('<Row>')
        for col_index in range(max_cols):
            value = ""
            if col_index < len(row):
                value = row[col_index]
            if col_index in epd_column_styles:
                style_id = epd_column_styles[col_index][0] if row_index == 0 else epd_column_styles[col_index][1]
            else:
                style_id = "Header" if row_index == 0 else "Data"
            out.append(excel_xml_cell(value, style_id))
        out.append('</Row>')

    out.append('</Table><WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">')
    out.append('<FreezePanes/><FrozenNoSplit/><SplitHorizontal>1</SplitHorizontal><TopRowBottomPane>1</TopRowBottomPane>')
    out.append('<ProtectObjects>False</ProtectObjects><ProtectScenarios>False</ProtectScenarios>')
    out.append('</WorksheetOptions></Worksheet>')
    return "".join(out)


def imagej_summary_rows_for_excel(results):
    all_headers = []
    run_maps = []
    for run in results:
        rows = read_csv_rows(run.get("summary_csv", ""))
        row_map = {}
        if len(rows) >= 2:
            headers = rows[0]
            values = rows[1]
            for index_value in range(len(headers)):
                header = str(headers[index_value])
                if header not in all_headers:
                    all_headers.append(header)
                if index_value < len(values):
                    row_map[header] = values[index_value]
        row_map["Report run"] = report_run_title(len(run_maps) + 1, run, len(results))
        run_maps.append(row_map)

    headers_out = ["Report run"]
    for header in all_headers:
        if header != "Report run":
            headers_out.append(header)
    rows_out = [headers_out]
    for row_map in run_maps:
        row_out = []
        for header in headers_out:
            row_out.append(row_map.get(header, ""))
        rows_out.append(row_out)
    return rows_out


def metric_rows_for_excel(results):
    rows = [["Report run", "Run label", "Metric", "Value"]]
    for run_index in range(len(results)):
        run = results[run_index]
        label = str(run.get("run_label", "normal"))
        if label in ["", "None"]:
            label = "normal"
        summary_rows = run.get("summary_rows_for_report", [])
        for summary_row in summary_rows:
            if len(summary_row) >= 2:
                rows.append([
                    report_run_title(run_index + 1, run, len(results)),
                    label,
                    pretty_summary_metric_name(summary_row[0]),
                    summary_row[1]
                ])
        if len(summary_rows) == 0:
            rows.append([report_run_title(run_index + 1, run, len(results)), label, "Particle Count", run.get("particle_count", "")])
            rows.append([report_run_title(run_index + 1, run, len(results)), label, "Area %", run.get("area_percent", "")])
    return rows


def processing_rows_for_excel(results):
    rows = [["Report run", "Run label", "Setting", "Value"]]
    for run_index in range(len(results)):
        run = results[run_index]
        label = str(run.get("run_label", "normal"))
        if label in ["", "None"]:
            label = "normal"
        for setting_name, setting_value in report_parameter_columns_for_run(run):
            rows.append([
                report_run_title(run_index + 1, run, len(results)),
                label,
                setting_name,
                setting_value
            ])
    return rows


def summary_xls_destination_folders(output_root, settings):
    choice = str(settings.get("summary_xls_destination", "Auto-detect available All Reports folder"))
    fallback = os.path.join(output_root, "Word_Report")
    folders = []

    if choice == "Michelson/Andrew All Reports folder":
        folders = [ALL_REPORTS_FOLDER_MICHELSON]
    elif choice == "vgolf/OneDrive All Reports folder":
        folders = [ALL_REPORTS_FOLDER_VGOLF]
    elif choice == "All available All Reports folders":
        for candidate in [ALL_REPORTS_FOLDER_MICHELSON, ALL_REPORTS_FOLDER_VGOLF]:
            if File(candidate).exists():
                folders.append(candidate)
    elif choice == "Word_Report output folder":
        folders = [fallback]
    elif choice == "Custom folder":
        custom_folder = str(settings.get("summary_xls_custom_folder", "")).strip()
        if custom_folder != "":
            folders = [custom_folder]
    elif choice == "Manual selection at end":
        # Always create the summaries first in a local staging folder. The end-of-run
        # picker copies the chosen files into a newly named destination folder.
        folders = [os.path.join(output_root, "Word_Report", "_Manual_Summary_Staging")]
    else:
        for candidate in [ALL_REPORTS_FOLDER_MICHELSON, ALL_REPORTS_FOLDER_VGOLF]:
            if File(candidate).exists():
                folders.append(candidate)
                break

    if len(folders) == 0:
        folders = [fallback]
        IJ.log("No configured All Reports folder was available. Excel summary will use: " + fallback)

    unique_folders = []
    for folder in folders:
        if folder not in unique_folders:
            unique_folders.append(folder)
    return unique_folders



XLSX_MAX_ROWS = 1048576


def xlsx_column_name(index_zero_based):
    n = int(index_zero_based) + 1
    out = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        out = chr(65 + remainder) + out
    return out


def xlsx_clean_text(value):
    if value is None:
        return ""
    s = str(value)
    cleaned = []
    for ch in s:
        try:
            code = ord(ch)
        except:
            continue
        if code in [9, 10, 13] or code >= 32:
            cleaned.append(ch)
    return "".join(cleaned)


def xlsx_write_text(zos, text_value):
    data = str(text_value).encode("utf-8")
    zos.write(data, 0, len(data))


def xlsx_cell_xml(row_number, column_index, value, header=False, style_id=None):
    ref = xlsx_column_name(column_index) + str(row_number)
    if style_id is None:
        style_id = 1 if header else 0
    try:
        style_number = int(style_id)
    except:
        style_number = 1 if header else 0
    style = '' if style_number == 0 else ' s="' + str(style_number) + '"'
    value_type, clean_value = excel_xml_number_or_string(value)
    if value_type == "Number":
        return '<c r="' + ref + '"' + style + '><v>' + xml_escape(clean_value) + '</v></c>'
    text_value = xlsx_clean_text(clean_value)
    preserve = ' xml:space="preserve"' if text_value.startswith(" ") or text_value.endswith(" ") or "\n" in text_value else ''
    return '<c r="' + ref + '"' + style + ' t="inlineStr"><is><t' + preserve + '>' + xml_escape(text_value) + '</t></is></c>'


def xlsx_write_row(zos, row_number, values, header=False, style_by_column=None):
    if style_by_column is None:
        style_by_column = {}
    parts = ['<row r="' + str(row_number) + '">']
    for column_index in range(len(values)):
        style_id = style_by_column.get(column_index, None)
        parts.append(xlsx_cell_xml(row_number, column_index, values[column_index], header, style_id))
    parts.append('</row>')
    xlsx_write_text(zos, "".join(parts))


def xlsx_start_sheet(zos, entry_name, widths, freeze_header=True):
    entry = ZipEntry(entry_name)
    zos.putNextEntry(entry)
    xlsx_write_text(zos, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
    xlsx_write_text(zos, '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">')
    if freeze_header:
        xlsx_write_text(zos, '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>')
    else:
        xlsx_write_text(zos, '<sheetViews><sheetView workbookViewId="0"/></sheetViews>')
    xlsx_write_text(zos, '<sheetFormatPr defaultRowHeight="15"/>')
    xlsx_write_text(zos, '<cols>')
    for index_value in range(len(widths)):
        width = widths[index_value]
        xlsx_write_text(zos, '<col min="' + str(index_value + 1) + '" max="' + str(index_value + 1) + '" width="' + str(width) + '" customWidth="1"/>')
    xlsx_write_text(zos, '</cols><sheetData>')


def xlsx_finish_sheet(zos, last_row, last_column_count):
    xlsx_write_text(zos, '</sheetData>')
    if last_row >= 1 and last_column_count >= 1:
        last_ref = xlsx_column_name(last_column_count - 1) + str(last_row)
        xlsx_write_text(zos, '<autoFilter ref="A1:' + last_ref + '"/>')
    xlsx_write_text(zos, '<pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>')
    xlsx_write_text(zos, '</worksheet>')
    zos.closeEntry()


def read_csv_header_only(path):
    if not path_exists(path):
        return []
    f = None
    try:
        f = open(path, "r")
        reader = csv.reader(f)
        for row in reader:
            return list(row)
    except Exception as e:
        IJ.log("Could not read CSV header for BEAST workbook: " + str(path) + " / " + str(e))
    finally:
        try:
            if f is not None:
                f.close()
        except:
            pass
    return []


def beast_summary_metric_map(run):
    refresh_jmp_output_paths(run)
    metric_map = {}
    for metric, value in read_jmp_summary_for_report(run.get("final_summary_csv", "")):
        metric_map[pretty_summary_metric_name(metric)] = value
    return metric_map


def beast_processing_steps_text(run):
    notes = run.get("step_notes", [])
    if notes is None:
        notes = []
    return " | ".join([str(v) for v in notes])


def beast_epd_number_from_row(row_map):
    for candidate in ["epd(mm)", "EPD(mm)", "EPD (mm)", "EPD mm"]:
        if candidate in row_map and str(row_map.get(candidate, "")).strip() != "":
            try:
                return float(row_map.get(candidate, ""))
            except:
                pass
    for area_candidate in ["Pore Area", "Area (mm^2)", "Area mm^2"]:
        if area_candidate in row_map:
            try:
                return float(pore_epd_mm_from_area_mm2(float(row_map.get(area_candidate, ""))))
            except:
                pass
    return None


def beast_sweep_column_label(key):
    labels = {
        "threshold_min": "Threshold Min",
        "threshold_max": "Threshold Max",
        "contrast_enabled": "Enhance Contrast Enabled",
        "contrast_mode": "Enhance Contrast Mode",
        "median_radius": "Median Filter Radius (px)",
        "bandpass_large": "Bandpass Large Structure (px)",
        "bandpass_small": "Bandpass Small Structure (px)",
        "clahe_blocksize": "CLAHE Block Size",
        "clahe_maximum": "CLAHE Maximum",
        "binary_enabled": "Binary Cleanup Enabled",
        "binary_fill_holes": "Fill Holes",
        "binary_watershed": "Watershed",
        "binary_despeckle_iterations": "Despeckle Iterations",
        "binary_open_iterations": "Open Iterations",
        "binary_close_iterations": "Close Iterations",
        "binary_erode_iterations": "Erode Iterations",
        "binary_dilate_iterations": "Dilate Iterations",
        "binary_minimum_radius": "Minimum Filter Radius (px)",
        "binary_maximum_radius": "Maximum Filter Radius (px)"
    }
    if key in labels:
        return labels[key]
    text = str(key).replace("pipeline_", "Pipeline ").replace("_", " ").strip()
    return " ".join([word.capitalize() for word in text.split()])


def beast_run_sweep_overrides(run):
    overrides = run.get("sweep_overrides", {})
    if isinstance(overrides, dict):
        return overrides
    try:
        return dict(overrides)
    except:
        return {}


def beast_display_sweep_value(key, value):
    if key == "contrast_mode":
        return str(value)
    if key in ["contrast_enabled", "binary_enabled", "binary_fill_holes", "binary_watershed"]:
        try:
            return "ON" if int(round(float(value))) != 0 else "OFF"
        except:
            return str(value)
    return value


def write_beast_three_sheet_xlsx(path, results, settings):
    ordered = sorted(list(results), key=lambda r: int(r.get("run_order_index", 0)))
    for run in ordered:
        refresh_jmp_output_paths(run)
        if str(run.get("jmp_status", "")) == "SKIPPED_NO_HISTOGRAMS" or not path_exists(run.get("raw_all_pores_csv", "")):
            run["raw_all_pores_csv"] = run.get("pore_csv", "")

    # Discover the union of pore-data columns. EPD is normalized and always
    # placed as the final column, regardless of whether Fiji or JMP produced it.
    pore_headers = []
    epd_aliases = ["epd(mm)", "EPD(mm)", "EPD (mm)", "EPD mm"]
    for run in ordered:
        header = read_csv_header_only(run.get("raw_all_pores_csv", ""))
        for name in header:
            name_text = str(name)
            if name_text in epd_aliases:
                continue
            if name_text not in pore_headers:
                pore_headers.append(name_text)
    pore_headers.append("epd(mm)")

    metadata_headers = [
        "Run Order", "Pore Row in Run", "Source Pore Row in Run", "Image", "Image Path",
        "Run Label", "Run Folder", "ImageJ Status", "JMP Status", "Delete EPD Cutoff (mm)"
    ]
    all_data_headers = metadata_headers + pore_headers

    # The third sheet adds one row per run and one dynamic column per parameter
    # that actually appeared in a sweep override.
    revised_sweep_keys = []
    for run in ordered:
        for sweep_key in beast_run_sweep_overrides(run).keys():
            sweep_key_text = str(sweep_key)
            if sweep_key_text in ["threshold_min", "threshold_max"]:
                continue
            if sweep_key_text not in revised_sweep_keys:
                revised_sweep_keys.append(sweep_key_text)
    revised_sweep_keys.sort()
    revised_headers = [
        "Run #", "OG Image Name", "Image", "Original 8-bit Mean Gray Value (0-255)",
        "Run Label", "Number of Pores", "Mean EPD (mm)", "Max EPD (mm)",
        "Cutoff Size (mm)", "Threshold Min", "Threshold Max", "Threshold Mode", "Scale Set Using", "Imaging Software",
        "Swift Magnification Profile", "Swift Resolution (pixels per meter, px/m)", "Applied Pixel Size (um/pixel)", "Swift Magnification Table"
    ] + [beast_sweep_column_label(key) for key in revised_sweep_keys]

    # Aggregate-only overview. Individual runs appear only in the exception section when needed.
    overview_headers = ["Metric", "Value"]
    ensure_dir(os.path.dirname(path))
    fos = FileOutputStream(path)
    zos = ZipOutputStream(fos)
    try:
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            '</Types>'
        )
        root_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            '</Relationships>'
        )
        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<bookViews><workbookView/></bookViews><sheets>'
            '<sheet name="All Pore Data" sheetId="1" r:id="rId1"/>'
            '<sheet name="Run Overview" sheetId="2" r:id="rId2"/>'
            '<sheet name="Revised Summary" sheetId="3" r:id="rId3"/>'
            '</sheets></workbook>'
        )
        workbook_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/>'
            '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>'
        )
        styles_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="10"/><name val="Calibri"/></font><font><b/><sz val="10"/><name val="Calibri"/></font></fonts>'
            '<fills count="5"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE7E6E6"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFEAF2F8"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/><bgColor indexed="64"/></patternFill></fill></fills>'
            '<borders count="2"><border/><border><bottom style="thin"><color rgb="FF808080"/></bottom></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="6"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/><xf numFmtId="0" fontId="0" fillId="4" borderId="0" xfId="0" applyFill="1"/><xf numFmtId="0" fontId="1" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            '</styleSheet>'
        )
        now_text = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'").format(Date())
        core_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>GDL BEAST MODE data workbook</dc:title><dc:creator>Fiji/ImageJ GDL script</dc:creator>'
            '<dcterms:created xsi:type="dcterms:W3CDTF">' + now_text + '</dcterms:created>'
            '</cp:coreProperties>'
        )
        app_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            '<Application>Fiji/ImageJ GDL BEAST MODE</Application><TitlesOfParts><vt:vector size="3" baseType="lpstr"><vt:lpstr>All Pore Data</vt:lpstr><vt:lpstr>Run Overview</vt:lpstr><vt:lpstr>Revised Summary</vt:lpstr></vt:vector></TitlesOfParts>'
            '</Properties>'
        )

        zip_writestr(zos, "[Content_Types].xml", content_types)
        zip_writestr(zos, "_rels/.rels", root_rels)
        zip_writestr(zos, "xl/workbook.xml", workbook_xml)
        zip_writestr(zos, "xl/_rels/workbook.xml.rels", workbook_rels)
        zip_writestr(zos, "xl/styles.xml", styles_xml)
        zip_writestr(zos, "docProps/core.xml", core_xml)
        zip_writestr(zos, "docProps/app.xml", app_xml)

        # Sheet 1: cleaned pore data only. Rows at or below the configured
        # delete/cutoff EPD are excluded before export.
        data_widths = [11, 12, 16, 24, 38, 20, 34, 14, 18, 16] + [14 for _ in pore_headers]
        xlsx_start_sheet(zos, "xl/worksheets/sheet1.xml", data_widths, True)
        xlsx_write_row(zos, 1, all_data_headers, True)
        sheet_row = 2
        for run in ordered:
            run["beast_pore_rows_exported"] = 0
            run["beast_pore_rows_excluded_cutoff"] = 0
            run["cleaned_pore_count"] = 0
            run["cleaned_mean_epd_mm"] = ""
            run["cleaned_max_epd_mm"] = ""
            raw_path = run.get("raw_all_pores_csv", "")
            if not path_exists(raw_path):
                continue
            f = None
            try:
                cutoff_value = float(run.get("small_epd_cutoff", settings.get("small_epd_cutoff", 0.0)))
            except:
                cutoff_value = 0.0
            try:
                f = open(raw_path, "r")
                reader = csv.reader(f)
                source_headers = []
                source_pore_index = 0
                clean_pore_index = 0
                clean_epd_sum = 0.0
                clean_epd_max = None
                excluded_count = 0
                for source_row in reader:
                    if len(source_headers) == 0:
                        source_headers = list(source_row)
                        continue
                    source_pore_index += 1
                    row_map = {}
                    for source_index in range(len(source_headers)):
                        row_map[str(source_headers[source_index])] = source_row[source_index] if source_index < len(source_row) else ""
                    epd_number = beast_epd_number_from_row(row_map)
                    if epd_number is None or float(epd_number) <= cutoff_value:
                        excluded_count += 1
                        continue
                    if sheet_row > XLSX_MAX_ROWS:
                        raise Exception("Excel row limit exceeded. All Pore Data supports at most " + str(XLSX_MAX_ROWS - 1) + " cleaned pore rows plus its header.")
                    clean_pore_index += 1
                    clean_epd_sum += float(epd_number)
                    if clean_epd_max is None or float(epd_number) > clean_epd_max:
                        clean_epd_max = float(epd_number)
                    values = [
                        run.get("run_order_index", ""), clean_pore_index, source_pore_index,
                        run.get("image_name", os.path.basename(str(run.get("image_path", "")))),
                        run.get("image_path", ""), run.get("run_label", ""), run.get("run_dir", ""),
                        run.get("imagej_status", ""), run.get("jmp_status", ""), cutoff_value
                    ]
                    for header_name in pore_headers:
                        if header_name == "epd(mm)":
                            values.append(epd_number)
                        else:
                            values.append(row_map.get(header_name, ""))
                    xlsx_write_row(zos, sheet_row, values, False)
                    sheet_row += 1
                    if sheet_row % 5000 == 0:
                        if global_cancel_requested():
                            raise Exception("Canceled by user during BEAST MODE workbook export.")
                        progress_ui = settings.get("_beast_progress_ui", None)
                        update_beast_progress_popup(
                            progress_ui, "BEAST MODE: building three-sheet XLSX",
                            "Cleaned All Pore Data rows written: " + str(sheet_row - 2),
                            len(ordered), len(ordered), len(ordered), 0, 0, 0, 1
                        )
                        IJ.showStatus("BEAST XLSX: " + str(sheet_row - 2) + " cleaned pore rows written")
                run["beast_pore_rows_exported"] = clean_pore_index
                run["beast_pore_rows_excluded_cutoff"] = excluded_count
                run["cleaned_pore_count"] = clean_pore_index
                if clean_pore_index > 0:
                    run["cleaned_mean_epd_mm"] = clean_epd_sum / float(clean_pore_index)
                    run["cleaned_max_epd_mm"] = clean_epd_max
            finally:
                try:
                    if f is not None:
                        f.close()
                except:
                    pass
        xlsx_finish_sheet(zos, sheet_row - 1, len(all_data_headers))

        # Sheet 2: aggregate totals plus exceptions only.
        overview_widths = [34, 90]
        xlsx_start_sheet(zos, "xl/worksheets/sheet2.xml", overview_widths, True)
        xlsx_write_row(zos, 1, overview_headers, True)
        overview_row_number = 2
        completed_imagej = 0
        failed_imagej = 0
        canceled_imagej = 0
        completed_jmp = 0
        failed_jmp = 0
        canceled_jmp = 0
        total_particles = 0.0
        total_pore_rows = 0
        total_imagej_seconds = 0.0
        total_jmp_seconds = 0.0
        imagej_timing_count = 0
        jmp_timing_count = 0
        exceptions = []
        unique_images = set()
        for run in ordered:
            unique_images.add(str(run.get("image_path", "")))
            imagej_status = str(run.get("imagej_status", ""))
            jmp_status = str(run.get("jmp_status", ""))
            if imagej_status == "COMPLETED": completed_imagej += 1
            elif "CANCEL" in imagej_status: canceled_imagej += 1
            else: failed_imagej += 1
            if jmp_status in ["COMPLETED", "SKIPPED_EXISTING", "SKIPPED_NO_HISTOGRAMS"]: completed_jmp += 1
            elif "CANCEL" in jmp_status or "NOT_LAUNCHED" in jmp_status: canceled_jmp += 1
            elif jmp_status not in ["", "NOT_STARTED"]: failed_jmp += 1
            try:
                total_particles += float(run.get("particle_count", 0))
            except: pass
            try:
                total_pore_rows += int(run.get("beast_pore_rows_exported", 0))
            except: pass
            try:
                total_imagej_seconds += float(run.get("imagej_elapsed_sec", 0)); imagej_timing_count += 1
            except: pass
            try:
                total_jmp_seconds += float(run.get("jmp_elapsed_sec", 0)); jmp_timing_count += 1
            except: pass
            error_text = str(run.get("jmp_error", ""))
            if imagej_status != "COMPLETED" or jmp_status not in ["COMPLETED", "SKIPPED_EXISTING", "SKIPPED_NO_HISTOGRAMS"]:
                if error_text == "": error_text = beast_processing_steps_text(run)
                exceptions.append([run.get("run_order_index", ""), run.get("image_name", os.path.basename(str(run.get("image_path", "")))), imagej_status, jmp_status, error_text])
        elapsed_batch = time.time() - float(settings.get("_pipeline_start_time", settings.get("_beast_start_time", time.time())))
        binary_sweep_parts = []
        for binary_sweep_key in [
            "binary_enabled", "binary_fill_holes", "binary_watershed",
            "binary_despeckle_iterations", "binary_open_iterations", "binary_close_iterations",
            "binary_erode_iterations", "binary_dilate_iterations",
            "binary_minimum_radius", "binary_maximum_radius"
        ]:
            if settings.get("sweep_" + binary_sweep_key, False):
                binary_sweep_parts.append(
                    binary_sweep_key + "=" + str(settings.get("sweep_" + binary_sweep_key + "_start", "")) +
                    ".." + str(settings.get("sweep_" + binary_sweep_key + "_end", "")) +
                    " step " + str(settings.get("sweep_" + binary_sweep_key + "_step", ""))
                )
        totals = [
            ["BEAST batch status", "COMPLETED WITH EXCEPTIONS" if len(exceptions) > 0 else "COMPLETED"],
            ["Unique images", len(unique_images)], ["Total ordered runs", len(ordered)],
            ["ImageJ completed", completed_imagej], ["ImageJ failed", failed_imagej], ["ImageJ canceled", canceled_imagej],
            ["JMP completed/skipped", completed_jmp], ["JMP failed", failed_jmp], ["JMP canceled/not launched", canceled_jmp],
            ["Total particles detected", total_particles], ["Total pore rows exported", total_pore_rows],
            ["Total ImageJ processing seconds", total_imagej_seconds],
            ["Average ImageJ seconds per timed run", (total_imagej_seconds / imagej_timing_count) if imagej_timing_count > 0 else ""],
            ["Total JMP processing seconds", total_jmp_seconds],
            ["Average JMP seconds per timed run", (total_jmp_seconds / jmp_timing_count) if jmp_timing_count > 0 else ""],
            ["Total elapsed wall-clock", format_elapsed_seconds(elapsed_batch)],
            ["Total elapsed wall-clock seconds", elapsed_batch],
            ["Configured Fiji workers", settings.get("beast_fiji_parallel_instances", 1) if settings.get("beast_parallel_fiji_enabled", False) else 1],
            ["Maximum active Fiji agents observed", settings.get("_max_fiji_active_observed", "")],
            ["Configured JMP workers", settings.get("beast_jmp_parallel_instances", 1) if beast_jmp_histograms_enabled(settings) else 0],
            ["Maximum active JMP instances observed", settings.get("_max_jmp_active_observed", "")],
            ["JMP execution", "ENABLED for histogram/graph Word report" if beast_jmp_histograms_enabled(settings) else "SKIPPED; Fiji EPD exported directly"],
            ["JMP graphs/histograms", "ENABLED" if beast_jmp_histograms_enabled(settings) else "DISABLED"], ["Analyze Particles measurements", settings.get("set_measurements_options", "")],
            ["Binary cleanup base enabled", settings.get("binary_enabled", False)],
            ["Binary fill holes base", settings.get("binary_fill_holes", False)],
            ["Binary watershed base", settings.get("binary_watershed", False)],
            ["Binary despeckle iterations base", settings.get("binary_despeckle_iterations", 0)],
            ["Binary open iterations base", settings.get("binary_open_iterations", 0)],
            ["Binary close iterations base", settings.get("binary_close_iterations", 0)],
            ["Binary erode iterations base", settings.get("binary_erode_iterations", 0)],
            ["Binary dilate iterations base", settings.get("binary_dilate_iterations", 0)],
            ["Minimum grayscale filter radius base (px)", settings.get("binary_minimum_radius", 0.0)],
            ["Maximum grayscale filter radius base (px)", settings.get("binary_maximum_radius", 0.0)],
            ["Binary operation order", settings.get("binary_operation_order", "")],
            ["Binary sweep configuration", "; ".join(binary_sweep_parts) if len(binary_sweep_parts) > 0 else "None"],
            ["Delete EPD cutoff preset", settings.get("epd_delete_cutoff_preset", settings.get("epd_between_preset", ""))],
            ["Exception count", len(exceptions)]
        ]
        for metric_name, metric_value in totals:
            xlsx_write_row(zos, overview_row_number, [metric_name, metric_value], False)
            overview_row_number += 1
        if len(exceptions) > 0:
            overview_row_number += 1
            xlsx_write_row(zos, overview_row_number, ["FAILED / CANCELED / TIMED-OUT IMAGES ONLY", ""], True)
            overview_row_number += 1
            xlsx_write_row(zos, overview_row_number, ["Run Order", "Image | ImageJ Status | JMP Status | Error"], True)
            overview_row_number += 1
            for exception_row in exceptions:
                detail = str(exception_row[1]) + " | " + str(exception_row[2]) + " | " + str(exception_row[3]) + " | " + str(exception_row[4])
                xlsx_write_row(zos, overview_row_number, [exception_row[0], detail], False)
                overview_row_number += 1
        xlsx_finish_sheet(zos, overview_row_number - 1, len(overview_headers))

        # Sheet 3: concise run-by-run analysis table. Pore statistics use the
        # same cutoff-cleaned population exported to All Pore Data.
        revised_widths = [10, 30, 26, 22, 24, 16, 16, 16, 16, 14, 14, 22, 24, 22, 22, 22, 48, 20] + [20 for _ in revised_sweep_keys]
        xlsx_start_sheet(zos, "xl/worksheets/sheet3.xml", revised_widths, True)
        # Highlight the two EPD result columns: Mean EPD in light blue and Max EPD in light gold.
        revised_epd_header_styles = {6: 4, 7: 5}
        revised_epd_data_styles = {6: 2, 7: 3}
        xlsx_write_row(zos, 1, revised_headers, True, revised_epd_header_styles)
        revised_row_number = 2
        for run in ordered:
            overrides = beast_run_sweep_overrides(run)
            revised_values = [
                run.get("run_order_index", ""),
                run.get("og_image_name", run.get("image_name", os.path.basename(str(run.get("image_path", ""))))),
                run.get("image_name", os.path.basename(str(run.get("image_path", "")))),
                run.get("original_8bit_mean_gray", ""),
                run.get("run_label", ""),
                run.get("cleaned_pore_count", ""),
                run.get("cleaned_mean_epd_mm", ""),
                run.get("cleaned_max_epd_mm", ""),
                run.get("small_epd_cutoff", settings.get("small_epd_cutoff", "")),
                run.get("threshold_min", ""),
                run.get("threshold_max", ""),
                run.get("threshold_input_mode", ""),
                run.get("report_scale_method", settings.get("report_scale_method", "Needle scale")),
                run.get("report_imaging_software", settings.get("report_imaging_software", "Swift Imaging 3.0")),
                run.get("swift_magn_profile_name", ""),
                run.get("swift_magn_resolution_pixels_per_meter", ""),
                run.get("swift_magn_um_per_pixel", ""),
                run.get("swift_magn_table_path", "")
            ]
            for sweep_key in revised_sweep_keys:
                if sweep_key in overrides:
                    sweep_value = overrides.get(sweep_key, "")
                else:
                    sweep_value = run.get(sweep_key, "")
                revised_values.append(beast_display_sweep_value(sweep_key, sweep_value))
            xlsx_write_row(zos, revised_row_number, revised_values, False, revised_epd_data_styles)
            revised_row_number += 1
        xlsx_finish_sheet(zos, revised_row_number - 1, len(revised_headers))
    finally:
        try:
            zos.close()
        finally:
            try:
                fos.close()
            except:
                pass
    return path


def export_beast_three_sheet_xlsx(output_root, results, settings):
    destinations = list(summary_xls_destination_folders(output_root, settings))
    batch_summary_dir = str(settings.get("_batch_final_summary_dir", "")).strip()
    if batch_summary_dir != "":
        destinations.insert(0, batch_summary_dir)
    deduped_destinations = []
    seen_destinations = {}
    for destination in destinations:
        try:
            key = os.path.normcase(os.path.abspath(str(destination)))
        except:
            key = str(destination).lower()
        if key in seen_destinations:
            continue
        seen_destinations[key] = True
        deduped_destinations.append(destination)
    destinations = deduped_destinations
    base_name = resolve_report_base_name(results, settings)
    if base_name == "":
        base_name = "GDL_BEAST_MODE"
    workbook_name = short_safe_name(base_name, 110) + "_BEAST_MODE_All_Data.xlsx"
    created = []
    for destination in destinations:
        try:
            ensure_dir(destination)
            output_path = os.path.join(destination, workbook_name)
            write_beast_three_sheet_xlsx(output_path, results, settings)
            created.append(output_path)
            IJ.log("BEAST MODE three-sheet XLSX created: " + output_path)
        except Exception as e:
            try:
                if File(output_path).exists():
                    File(output_path).delete()
            except:
                pass
            IJ.log("Could not create BEAST MODE XLSX in " + str(destination) + ": " + str(e))
    return created


def export_beast_two_sheet_xlsx(output_root, results, settings):
    return export_beast_three_sheet_xlsx(output_root, results, settings)

def write_main_summary_xls(path, results, settings, report_path):
    results = sorted(list(results), key=lambda r: int(r.get("run_order_index", 0)))
    for run in results:
        refresh_jmp_output_paths(run)
        run["summary_rows_for_report"] = read_jmp_summary_for_report(run.get("final_summary_csv", ""))

    main_rows = build_combined_summary_table_rows(results)
    ij_rows = imagej_summary_rows_for_excel(results)
    has_jmp_summary = False
    for run in results:
        if len(run.get("summary_rows_for_report", [])) > 0:
            has_jmp_summary = True
            break
    if not has_jmp_summary:
        main_rows = ij_rows

    workbook_xml = []
    workbook_xml.append('<?xml version="1.0" encoding="UTF-8"?>')
    workbook_xml.append('<?mso-application progid="Excel.Sheet"?>')
    workbook_xml.append('<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" ')
    workbook_xml.append('xmlns:o="urn:schemas-microsoft-com:office:office" ')
    workbook_xml.append('xmlns:x="urn:schemas-microsoft-com:office:excel" ')
    workbook_xml.append('xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet" ')
    workbook_xml.append('xmlns:html="http://www.w3.org/TR/REC-html40">')
    workbook_xml.append('<Styles>')
    workbook_xml.append('<Style ss:ID="Default" ss:Name="Normal"><Alignment ss:Vertical="Bottom"/><Borders/><Font ss:FontName="Calibri" ss:Size="10"/><Interior/><NumberFormat/><Protection/></Style>')
    workbook_xml.append('<Style ss:ID="Header"><Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/><Borders><Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#808080"/></Borders><Font ss:FontName="Calibri" ss:Size="10" ss:Bold="1"/><Interior ss:Color="#E7E6E6" ss:Pattern="Solid"/></Style>')
    workbook_xml.append('<Style ss:ID="Data"><Alignment ss:Vertical="Top" ss:WrapText="0"/><Font ss:FontName="Calibri" ss:Size="10"/></Style>')
    workbook_xml.append('<Style ss:ID="MeanEPD"><Alignment ss:Vertical="Top"/><Font ss:FontName="Calibri" ss:Size="10"/><Interior ss:Color="#EAF2F8" ss:Pattern="Solid"/></Style>')
    workbook_xml.append('<Style ss:ID="MaxEPD"><Alignment ss:Vertical="Top"/><Font ss:FontName="Calibri" ss:Size="10"/><Interior ss:Color="#FFF2CC" ss:Pattern="Solid"/></Style>')
    workbook_xml.append('<Style ss:ID="MeanEPDHeader"><Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/><Borders><Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#808080"/></Borders><Font ss:FontName="Calibri" ss:Size="10" ss:Bold="1"/><Interior ss:Color="#EAF2F8" ss:Pattern="Solid"/></Style>')
    workbook_xml.append('<Style ss:ID="MaxEPDHeader"><Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/><Borders><Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#808080"/></Borders><Font ss:FontName="Calibri" ss:Size="10" ss:Bold="1"/><Interior ss:Color="#FFF2CC" ss:Pattern="Solid"/></Style>')
    workbook_xml.append('</Styles>')
    workbook_xml.append(excel_xml_worksheet("Main Summary", main_rows))
    workbook_xml.append('</Workbook>')

    ensure_dir(os.path.dirname(path))
    output_file = codecs.open(path, "w", "utf-8")
    try:
        output_file.write("".join(workbook_xml))
    finally:
        output_file.close()
    return path


def _summary_destinations_for_report(output_root, settings, report_path):
    """Resolve destinations for one report summary, including the v209 batch-final summary folder."""
    destinations = []
    batch_summary_dir = str(settings.get("_batch_final_summary_dir", "")).strip()
    if batch_summary_dir != "" and bool(settings.get("export_main_summary_xls", False)):
        ensure_dir(batch_summary_dir)
        destinations.append(batch_summary_dir)

    choice = str(settings.get("summary_xls_destination", "Auto-detect available All Reports folder"))
    if choice == "Word_Report output folder" and str(report_path).strip() != "":
        folder = os.path.dirname(str(report_path))
        if folder != "":
            destinations.append(folder)
    else:
        destinations.extend(summary_xls_destination_folders(output_root, settings))

    out = []
    seen = {}
    for folder in destinations:
        text = str(folder or "").strip()
        if text == "":
            continue
        try:
            key = os.path.normcase(os.path.abspath(text))
        except:
            key = text.lower()
        if key in seen:
            continue
        seen[key] = True
        out.append(text)
    return out


def export_main_summary_xls_for_reports(output_root, report_paths, results, settings):
    """
    Export summaries for the actual report groups.

    v209 fixes the old BEAST short-circuit that returned only the master BEAST XLSX.
    If completely-individual reports are selected, every per-run DOCX now receives
    its own matching *_summaries.xls when summary export is selected. The BEAST
    three-sheet workbook is still created as an additional batch workbook.
    """
    if not settings.get("export_main_summary_xls", False):
        return []

    groups = settings.get("_report_export_groups", [])
    if groups is None or len(groups) == 0:
        base_name = resolve_report_base_name(results, settings)
        pseudo_report = os.path.join(output_root, "Word_Report", base_name + ".docx")
        groups = [{"report_path": pseudo_report, "results": list(results), "group_type": "fallback"}]

    created = []
    created_keys = {}
    summary_manifest_rows = []
    for group in groups:
        report_path = str(group.get("report_path", ""))
        group_results = list(group.get("results", results) or [])
        report_base = os.path.splitext(os.path.basename(report_path))[0]
        if report_base == "":
            report_base = resolve_report_base_name(group_results, settings)
        xls_name = report_base + "_summaries.xls"

        for destination in _summary_destinations_for_report(output_root, settings, report_path):
            try:
                ensure_dir(destination)
                xls_path = os.path.join(destination, xls_name)
                key = os.path.normcase(os.path.abspath(xls_path))
                if key in created_keys:
                    continue
                write_main_summary_xls(xls_path, group_results, settings, report_path)
                created_keys[key] = True
                created.append(xls_path)
                summary_manifest_rows.append([
                    group.get("group_type", ""),
                    report_path,
                    len(group_results),
                    xls_path
                ])
                IJ.log("Excel main summary created: " + xls_path)
            except Exception as e:
                IJ.log("Could not create Excel summary in " + str(destination) + ": " + str(e))

    # Preserve the rich BEAST batch workbook, but never let it replace per-report
    # summaries. It is an additional file when summary export is selected.
    if settings.get("beast_mode_enabled", False) and settings.get("beast_two_sheet_workbook_enabled", True):
        try:
            for master_path in export_beast_two_sheet_xlsx(output_root, results, settings):
                key = os.path.normcase(os.path.abspath(master_path))
                if key not in created_keys:
                    created_keys[key] = True
                    created.append(master_path)
        except Exception as e:
            IJ.log("Could not create additional BEAST master workbook: " + str(e))

    try:
        manifest_dir = os.path.join(output_root, "Word_Report")
        ensure_dir(manifest_dir)
        manifest_path = os.path.join(manifest_dir, "Report_Summary_Manifest.csv")
        write_csv(manifest_path, ["Report Group", "Word Report", "Run Count", "Summary File"], summary_manifest_rows, 9)
        settings["_report_summary_manifest"] = manifest_path
    except Exception as e:
        IJ.log("Could not write report-summary manifest: " + str(e))

    settings["_report_summary_created_count"] = len(created)
    return created

def show_warning_summary_popup(results, errors, settings):
    if not settings.get("popup_warning_summary_enabled", True):
        return

    warnings = []

    try:
        if errors is not None:
            for err in errors:
                warnings.append("ERROR: " + str(err))
    except:
        pass

    try:
        for run in results:
            image_label = str(run.get("image_name", run.get("image_path", "Unknown image")))
            crop_text = ""
            if run.get("crop_enabled", False):
                crop_text = " / " + str(run.get("crop_region_text", ""))

            run_warns = []

            for item in run.get("quality_warnings", []):
                if item not in run_warns:
                    run_warns.append(item)

            for item in run.get("bad_image_issues", []):
                if item not in run_warns:
                    run_warns.append(item)

            if len(run_warns) > 0:
                warnings.append(image_label + crop_text)
                for item in run_warns:
                    warnings.append("  - " + str(item))
    except Exception as e:
        IJ.log("Could not build warning summary popup list: " + str(e))

    if len(warnings) <= 0:
        return

    max_lines = 45
    shown = warnings[:max_lines]
    msg = "Quality warning summary\\n\\n" + "\\n".join(shown)
    if len(warnings) > max_lines:
        msg += "\\n\\n... plus " + str(len(warnings) - max_lines) + " more warning lines. See the ImageJ log and run notes for full details."

    try:
        JOptionPane.showMessageDialog(
            None,
            msg,
            "GDL Quality Warning Summary",
            JOptionPane.WARNING_MESSAGE
        )
    except Exception as e2:
        IJ.log("Could not show warning summary popup: " + str(e2))

    try:
        IJ.log("Quality warning summary:")
        for w in warnings:
            IJ.log(str(w))
    except:
        pass


def open_output_folder(path):
    try:
        if path is None or str(path).strip() == "":
            return
        Desktop.getDesktop().open(File(path))
    except Exception as e:
        IJ.log("Could not open output folder: " + str(e))


def open_word_report(path):
    try:
        if path is None or str(path).strip() == "":
            return
        if not File(path).exists():
            IJ.log("Could not open Word report because it does not exist: " + str(path))
            return
        Desktop.getDesktop().open(File(path))
        IJ.log("Opened Word report: " + str(path))
    except Exception as e:
        IJ.log("Could not open Word report: " + str(path) + " / " + str(e))




# ======================================================
# YOURE A BETA IMAGE CAPTURE FORK HELPERS
# ======================================================

def yab_safe_batch_name(name):
    try:
        s = safe_name(str(name).strip())
    except:
        s = ""
    if s == "":
        s = "Captured_Batch"
    return short_safe_name(s, 48)


def duplicate_full_image_without_roi(src_imp, new_title):
    if src_imp is None:
        return None
    old_roi = None
    try:
        old_roi = src_imp.getRoi()
    except:
        old_roi = None
    try:
        src_imp.killRoi()
    except:
        pass
    try:
        dup = Duplicator().run(src_imp)
    finally:
        try:
            if old_roi is not None:
                src_imp.setRoi(old_roi)
        except:
            pass
    try:
        dup.setTitle(str(new_title))
    except:
        pass
    return dup


def get_active_image_for_capture(blocked_titles=None):
    try:
        imp = WindowManager.getCurrentImage()
    except:
        imp = None
    if imp is None:
        return None
    if blocked_titles is not None:
        try:
            title = str(imp.getTitle())
            for b in blocked_titles:
                if b is not None and str(b) != "" and title == str(b):
                    return None
        except:
            pass
    return imp


def roi_trace_length_pixels(roi):
    if roi is None:
        return 0.0
    # Prefer the actual polyline/line length in pixel coordinates.
    try:
        fp = roi.getFloatPolygon()
        n = int(fp.npoints)
        if n >= 2:
            total = 0.0
            for i in range(1, n):
                dx = float(fp.xpoints[i]) - float(fp.xpoints[i - 1])
                dy = float(fp.ypoints[i]) - float(fp.ypoints[i - 1])
                total += math.sqrt(dx * dx + dy * dy)
            if total > 0:
                return total
    except:
        pass
    # Fallback to ImageJ ROI length. On an unscaled scale frame this is pixels.
    try:
        v = float(roi.getLength())
        if v > 0:
            return v
    except:
        pass
    # Last fallback for a rectangle or oval ROI: use the bounding-box width.
    try:
        b = roi.getBounds()
        if float(b.width) > 0:
            return float(b.width)
    except:
        pass
    return 0.0


def apply_capture_scale_to_image(imp, mm_per_pixel):
    if imp is None:
        return False
    try:
        mm_per_pixel = float(mm_per_pixel)
    except:
        mm_per_pixel = 0.0
    if mm_per_pixel <= 0:
        return False
    try:
        cal = imp.getCalibration()
        cal.pixelWidth = mm_per_pixel
        cal.pixelHeight = mm_per_pixel
        cal.setUnit("mm")
        imp.setCalibration(cal)
        return True
    except Exception as e:
        IJ.log("YOURE A BETA: could not apply captured scale: " + str(e))
        return False


def capture_active_image_snapshot(title, blocked_titles=None):
    imp = get_active_image_for_capture(blocked_titles)
    if imp is None:
        return None
    try:
        return duplicate_full_image_without_roi(imp, title)
    except Exception as e:
        IJ.log("YOURE A BETA: active image capture failed: " + str(e))
        return None


def ask_capture_batch_name(default_name):
    try:
        gd = GenericDialog("YOURE A BETA - Batch Name")
        gd.addMessage("Name this capture batch. The output folder will be prefixed with YOURE_A_BETA.")
        gd.addStringField("Batch name", str(default_name), 32)
        gd.showDialog()
        if gd.wasCanceled():
            return None
        name = gd.getNextString()
        return yab_safe_batch_name(name)
    except:
        try:
            return yab_safe_batch_name(default_name)
        except:
            return "Captured_Batch"



def imagej_menu_command_exists(command_name):
    try:
        commands = Menus.getCommands()
        if commands is None:
            return False
        return bool(commands.containsKey(str(command_name)))
    except:
        return False


def get_live_view_directions_text():
    return (
        "Live-view setup directions\n\n"
        "1. Plug in the Celestron/USB microscope or camera before starting Fiji.\n"
        "2. Use the Fiji menu for the camera plugin that creates a live ImageJ image window. Common locations are:\n"
        "   - Plugins > Micro-Manager > Micro-Manager Studio\n"
        "   - Plugins > Acquisition / Camera / USB Camera\n"
        "   - Plugins > TWAIN Acquire, if your camera driver installs TWAIN support\n"
        "3. If auto-open works, a camera/live image window should appear. If it does not, open your camera plugin manually.\n"
        "4. Once the live image window is visible, click that image window once so it becomes the active ImageJ image.\n"
        "5. Then continue the YOURE A BETA capture workflow.\n\n"
        "Note: Fiji itself does not have one universal live-camera command for every USB microscope. This helper tries common installed plugin commands, but the exact menu depends on your camera driver/plugin."
    )


def try_open_live_view_if_requested(settings):
    try:
        if settings.get("image_capture_show_live_view_directions", True):
            IJ.showMessage("YOURE A BETA - Live View Directions", get_live_view_directions_text())
    except:
        pass

    try:
        if not bool(settings.get("image_capture_try_open_live_view", True)):
            IJ.log("YOURE A BETA: live-view auto-open skipped by setting.")
            return "skipped"
    except:
        return "skipped"

    selected = str(settings.get("image_capture_live_view_command", "Auto-detect common live-view command")).strip()
    if selected == "" or selected.lower().startswith("do not"):
        IJ.log("YOURE A BETA: live-view auto-open set to Do not auto-open.")
        return "skipped"

    # If a live/camera image is already active, do not disturb it.
    try:
        current = WindowManager.getCurrentImage()
        if current is not None:
            IJ.log("YOURE A BETA: active ImageJ image already exists. Auto-open not needed: " + str(current.getTitle()))
            return "already_active"
    except:
        pass

    auto_candidates = [
        "Micro-Manager Studio",
        "Micro-Manager",
        "Video Capture...",
        "Video Capture...",
        "Capture Video...",
        "Capture Video...",
        "Webcam Capture...",
        "USB Camera...",
        "TWAIN Acquire...",
        "Twain Acquire...",
        "Acquire...",
        "Camera..."
    ]

    if selected.lower().startswith("auto"):
        candidates = auto_candidates
    else:
        candidates = [selected]

    tried_any = False
    for cmd in candidates:
        try:
            if not imagej_menu_command_exists(cmd):
                continue
            tried_any = True
            IJ.log("YOURE A BETA: trying to open live view with ImageJ command: " + str(cmd))
            IJ.run(str(cmd))
            IJ.wait(1200)
            try:
                current2 = WindowManager.getCurrentImage()
                if current2 is not None:
                    try:
                        current2.getWindow().toFront()
                    except:
                        pass
                    IJ.log("YOURE A BETA: live-view/image command opened or activated image: " + str(current2.getTitle()))
                    return "opened:" + str(cmd)
            except:
                pass
            return "tried:" + str(cmd)
        except Exception as e:
            IJ.log("YOURE A BETA: live-view command failed: " + str(cmd) + " / " + str(e))

    if not tried_any:
        IJ.showMessage(
            "YOURE A BETA - Live View Not Found",
            "I could not find one of the common live-camera commands in your Fiji menus.\n\n" +
            "Open the live view manually using your installed camera plugin, then click the live image window once and continue.\n\n" +
            get_live_view_directions_text()
        )
    return "not_found"

def wait_for_scale_capture_from_active_window(batch_name):
    msg = (
        "Open your Fiji camera/live-preview window and place the scale bar in view.\n\n"
        "Click the live image window once so it is the active ImageJ image, then click Capture Scale Frame.\n\n"
        "This fork captures the active ImageJ image window. It does not directly control every camera plugin."
    )
    return show_modeless_choice_dialog(
        "YOURE A BETA - Capture Scale Frame",
        msg,
        [("Capture Scale Frame", "capture", True), ("Cancel", "cancel", False)],
        "cancel",
        None,
        650,
        260
    )


def wait_for_sample_capture_choice(index, total, batch_name):
    msg = (
        "Capture sample image " + str(index) + " of " + str(total) + ".\n\n"
        "Put the sample in view. Click the camera/live-preview image once so that image is active, then click Capture Image.\n\n"
        "The frame will be duplicated, calibrated with the scale you set, and saved as a TIFF."
    )
    return show_modeless_choice_dialog(
        "YOURE A BETA - Capture Sample Image",
        msg,
        [("Capture Image", "capture", True), ("Finish Batch", "finish", False), ("Cancel", "cancel", False)],
        "cancel",
        None,
        650,
        260
    )


def set_scale_from_captured_scale_frame(scale_imp, settings, output_root, batch_safe):
    if scale_imp is None:
        return 0.0, "", "no scale image"

    scale_title = "YOURE_A_BETA_" + str(batch_safe) + "_scale_frame"
    try:
        scale_imp.setTitle(scale_title)
        scale_imp.show()
    except:
        pass

    detected_len = 0.0
    endpoints = None
    detect_msg = ""
    try:
        pix_len, comp_pixels, bbox, endpoints_found, err = detect_red_scale_line_pixels(scale_imp, settings)
        if pix_len > 0 and endpoints_found is not None:
            detected_len = float(pix_len)
            endpoints = endpoints_found
            x1, y1, x2, y2 = endpoints_found
            try:
                scale_imp.setRoi(Line(float(x1), float(y1), float(x2), float(y2)))
            except:
                pass
            detect_msg = "Auto trace found a scale edge-to-edge line. Adjust the line endpoints if needed."
        else:
            detect_msg = "Auto trace could not find the red scale bar. Draw the scale distance manually with the straight or segmented line tool. " + str(err)
    except Exception as e:
        detect_msg = "Auto trace failed. Draw the scale distance manually with the straight or segmented line tool. " + str(e)

    trace_msg = (
        "Scale-frame trace step\n\n"
        + str(detect_msg) + "\n\n"
        "Use the normal ImageJ tools to zoom/pan.\n"
        "If the line is wrong, manually fix it or draw a new straight/segmented line from one edge of the scale bar to the other.\n"
        "Leave the final scale trace selected, then click Continue."
    )
    choice = wait_for_manual_pore_trace_nonmodal(
        "YOURE A BETA - Fix Scale Trace",
        trace_msg,
        scale_title
    )
    if choice != "ok":
        return 0.0, "", "user canceled scale trace"

    roi = None
    try:
        roi = scale_imp.getRoi()
    except:
        roi = None
    pix_len_user = roi_trace_length_pixels(roi)
    if pix_len_user <= 0 and detected_len > 0:
        pix_len_user = detected_len
    if pix_len_user <= 0:
        return 0.0, "", "no valid scale trace was selected"

    try:
        default_mm = float(settings.get("image_capture_scale_known_length_mm", settings.get("auto_scale_known_length_mm", 0.5)))
    except:
        default_mm = 0.5
    if default_mm <= 0:
        default_mm = 0.5

    gd = GenericDialog("YOURE A BETA - Known Scale Distance")
    gd.addMessage(
        "Final traced scale length = " + str(pix_len_user) + " pixels\n\n"
        "Enter the real distance represented by that trace."
    )
    gd.addNumericField("Known distance, mm", float(default_mm), 9)
    gd.showDialog()
    if gd.wasCanceled():
        return 0.0, "", "user canceled known distance entry"
    known_mm = gd.getNextNumber()
    if known_mm <= 0:
        known_mm = default_mm

    mm_per_pixel = float(known_mm) / float(pix_len_user)
    apply_capture_scale_to_image(scale_imp, mm_per_pixel)

    scale_path = ""
    try:
        if settings.get("image_capture_save_scale_frame", True):
            scale_dir = os.path.join(output_root, "Scale_Setup")
            ensure_dir(scale_dir)
            scale_path = os.path.join(scale_dir, str(batch_safe) + "_scale_frame_scaled.tif")
            FileSaver(scale_imp).saveAsTiff(scale_path)
    except Exception as e_save:
        IJ.log("YOURE A BETA: could not save scale frame TIFF: " + str(e_save))

    note = (
        "Scale set from captured frame: pixels=" + str(pix_len_user) +
        "; known_mm=" + str(known_mm) +
        "; mm_per_pixel=" + str(mm_per_pixel) +
        "; pixels_per_mm=" + str(1.0 / float(mm_per_pixel))
    )
    IJ.log("YOURE A BETA: " + note)
    return mm_per_pixel, scale_path, note


def write_yab_capture_notes(output_root, batch_safe, scale_note, scale_path, captured_paths, settings):
    try:
        notes_path = os.path.join(output_root, "YOURE_A_BETA_capture_notes.txt")
        f = open(notes_path, "w")
        f.write("YOURE A BETA image capture fork\n")
        f.write("Batch: " + str(batch_safe) + "\n")
        f.write("Scale note: " + str(scale_note) + "\n")
        f.write("Scale frame TIFF: " + str(scale_path) + "\n")
        f.write("Capture mode: " + str(settings.get("image_capture_mode", "")) + "\n")
        f.write("Captured TIFF count: " + str(len(captured_paths)) + "\n\n")
        for p in captured_paths:
            f.write(str(p) + "\n")
        f.close()
        return notes_path
    except Exception as e:
        IJ.log("YOURE A BETA: could not write capture notes: " + str(e))
        return ""


def run_youre_a_beta_image_capture_workflow(settings, output_root, batch_safe):
    """
    Captures one scale frame from the active ImageJ image window, lets the user fix the scale trace,
    then captures sample images from the active ImageJ image/camera preview window and saves calibrated TIFFs.
    Returns (captured_paths, scale_path, notes_path, scale_note).
    """
    ensure_dir(output_root)
    capture_dir = os.path.join(output_root, "Captured_TIFFs")
    ensure_dir(capture_dir)

    # Use the same red-line detection settings as the existing PNG set-scale workflow, but do not require input files.
    local_settings = dict(settings)
    local_settings["auto_scale_unscaled_enabled"] = True
    local_settings["auto_scale_show_preview"] = False

    try_open_live_view_if_requested(settings)

    choice = wait_for_scale_capture_from_active_window(batch_safe)
    if choice != "capture":
        raise Exception("YOURE A BETA image capture canceled before scale frame capture.")

    scale_imp = capture_active_image_snapshot("YOURE_A_BETA_" + str(batch_safe) + "_scale_frame")
    if scale_imp is None:
        raise Exception("No active ImageJ image/camera preview was available for the scale frame. Open the camera/live-preview image, click it once, then run again.")

    mm_per_pixel, scale_path, scale_note = set_scale_from_captured_scale_frame(scale_imp, local_settings, output_root, batch_safe)
    if mm_per_pixel <= 0:
        raise Exception("Could not set scale from captured scale frame: " + str(scale_note))

    try:
        scale_imp.changes = False
        if not settings.get("image_capture_keep_captured_windows_open", False):
            scale_imp.close()
    except:
        pass

    captured_paths = []
    total = int(settings.get("image_capture_count", 1))
    if total < 1:
        total = 1

    i = 1
    while i <= total:
        choice_img = wait_for_sample_capture_choice(i, total, batch_safe)
        if choice_img == "finish":
            break
        if choice_img != "capture":
            raise Exception("YOURE A BETA image capture canceled during sample capture.")

        cap_title = "YOURE_A_BETA_" + str(batch_safe) + "_capture_" + str(i)
        cap_imp = capture_active_image_snapshot(cap_title, blocked_titles=["YOURE_A_BETA_" + str(batch_safe) + "_scale_frame"])
        if cap_imp is None:
            IJ.showMessage("YOURE A BETA Capture", "No valid active image was found. Click the live camera/image window once, then click Capture Image again.")
            continue

        apply_capture_scale_to_image(cap_imp, mm_per_pixel)
        try:
            cap_imp.setTitle(cap_title)
        except:
            pass
        out_name = str(batch_safe) + "_" + str(i).zfill(3) + ".tif"
        out_path = os.path.join(capture_dir, out_name)
        FileSaver(cap_imp).saveAsTiff(out_path)
        captured_paths.append(out_path)
        IJ.log("YOURE A BETA: saved calibrated capture TIFF: " + str(out_path))

        try:
            cap_imp.changes = False
            if not settings.get("image_capture_keep_captured_windows_open", False):
                cap_imp.close()
        except:
            pass
        i = i + 1

    if len(captured_paths) <= 0:
        raise Exception("No sample images were captured.")

    notes_path = write_yab_capture_notes(output_root, batch_safe, scale_note, scale_path, captured_paths, settings)
    return captured_paths, scale_path, notes_path, scale_note



# ======================================================
# BEAST MODE PARALLEL FIJI WORKERS
# ======================================================

def beast_worker_config_from_globals():
    try:
        p = globals().get("BEAST_WORKER_CONFIG_PATH", "")
        if str(p).strip() == "":
            p = os.environ.get("GDL_BEAST_WORKER_CONFIG", "")
        if str(p).strip() == "" or not File(str(p)).exists():
            return None
        f = open(str(p), "rb")
        try:
            return pickle.load(f)
        finally:
            f.close()
    except Exception as e:
        IJ.log("Could not load BEAST Fiji worker configuration: " + str(e))
        return None


def _append_unique_path(items, value):
    try:
        if value is None:
            return
        p = os.path.abspath(str(value).strip())
        if p == "":
            return
        key = p.lower()
        for existing in items:
            if str(existing).lower() == key:
                return
        items.append(p)
    except:
        pass


def _fiji_launcher_names():
    # Fiji switched to the Jaunch launcher in February 2025. On Windows the
    # supported front end is normally fiji.bat, which dispatches to the correct
    # platform-specific Jaunch executable. Keep legacy ImageJ launcher names for
    # older Fiji installations, but only when the containing folder is verified.
    return [
        "fiji-windows-x64.exe", "fiji-windows-arm64.exe", "fiji-windows-x86.exe",
        "fiji.bat", "Fiji.bat", "fiji.cmd", "Fiji.cmd", "fiji.exe", "Fiji.exe",
        "ImageJ-win64.exe", "ImageJ.exe", "ImageJ-win32.exe",
        "fiji", "ImageJ-linux64", "ImageJ-linux32", "ImageJ-macosx"
    ]


def _fiji_install_root_from_launcher(launcher_path):
    try:
        p = os.path.abspath(str(launcher_path))
        folder = os.path.dirname(p) if os.path.isfile(p) else p
        normalized = folder.replace("/", "\\")
        low = normalized.lower()
        marker = "\\contents\\macos"
        if low.endswith(marker):
            return os.path.dirname(os.path.dirname(folder))
        # Modern Jaunch launchers can be reached through a small app/jaunch or
        # jaunch subfolder. Walk upward until the full Fiji root is found.
        current = folder
        for _i in range(5):
            if (os.path.isdir(os.path.join(current, "jars")) and
                    os.path.isdir(os.path.join(current, "plugins"))):
                return current
            parent = os.path.dirname(current)
            if parent == current or parent == "":
                break
            current = parent
        return folder
    except:
        return ""


def _is_verified_fiji_launcher(launcher_path):
    """Accept only a launcher that belongs to a full Fiji installation."""
    try:
        p = os.path.abspath(str(launcher_path))
        if not os.path.isfile(p):
            return False
        low_path = p.lower().replace("/", "\\")
        # Explicitly reject the legacy standalone ImageJ download that caused v126
        # to launch the wrong application.
        if "ij154-win-java8" in low_path or "ij1" + os.sep + "imagej" in low_path:
            return False
        root = _fiji_install_root_from_launcher(p)
        if root == "":
            return False
        # Fiji distributions have both jars and plugins at the installation root.
        # Modern Jaunch Fiji additionally has config/jaunch/fiji.toml or fiji.bat.
        # Requiring the Fiji content folders prevents a random legacy ImageJ.exe
        # from winning discovery while accepting both old and current Fiji.
        if not os.path.isdir(os.path.join(root, "jars")):
            return False
        if not os.path.isdir(os.path.join(root, "plugins")):
            return False
        name = os.path.basename(p).lower()
        if name in ["fiji.bat", "fiji.cmd", "fiji.exe", "fiji"]:
            return True
        # Legacy launcher names are accepted only inside the verified Fiji root.
        return True
    except:
        return False


def _fiji_launcher_score(candidate, preferred_roots=None):
    try:
        p = os.path.abspath(str(candidate))
        if not _is_verified_fiji_launcher(p):
            return -1000000
        name = os.path.basename(p).lower()
        score = 0
        if name == "fiji-windows-x64.exe": score += 14000
        elif name == "fiji-windows-arm64.exe": score += 13500
        elif name == "fiji-windows-x86.exe": score += 13000
        elif name == "fiji.bat": score += 9000
        elif name == "fiji.cmd": score += 8500
        elif name == "fiji.exe": score += 8000
        elif name == "imagej-win64.exe": score += 5000
        elif name == "imagej.exe": score += 3000
        elif name == "imagej-win32.exe": score += 1000
        root = _fiji_install_root_from_launcher(p).lower()
        if preferred_roots is not None:
            for index, preferred in enumerate(preferred_roots):
                try:
                    pref = os.path.abspath(str(preferred)).lower()
                    if pref != "" and (root == pref or root.startswith(pref + os.sep)):
                        score += max(0, 20000 - index * 100)
                        break
                except:
                    pass
        if "\\users\\mkime\\fiji" in root.replace("/", "\\"):
            score += 8000
        if "\\users\\vgolf\\fiji" in root.replace("/", "\\"):
            score += 8000
        normalized_root = root.replace("/", "\\")
        if "\\users\\vgolf\\documents\\fiji.app" in normalized_root:
            score += 12000
        if "\\users\\mkime\\fiji-latest-win64-jdk\\fiji" in normalized_root:
            score += 12000
        if "downloads" in root:
            score -= 2000
        return score
    except:
        return -1000000


def _find_fiji_launcher_near(base_path, preferred_roots=None):
    if base_path is None or str(base_path).strip() == "":
        return ""
    try:
        base = os.path.abspath(str(base_path).strip().strip('"'))
    except:
        return ""

    candidates = []
    try:
        if os.path.isfile(base) and _is_verified_fiji_launcher(base):
            candidates.append(base)
    except:
        pass

    roots = []
    try:
        for _base in os.environ.get("GDL_EXTRA_USER_ROOTS", "").split(";"):
            _base = _base.strip()
            if _base:
                roots.extend([os.path.join(_base, "Fiji"), os.path.join(_base, "Fiji.app")])
    except Exception:
        pass
    current = base
    try:
        if os.path.isfile(current):
            current = os.path.dirname(current)
    except:
        pass
    for i in range(8):
        _append_unique_path(roots, current)
        parent = os.path.dirname(current)
        if parent == current or parent == "":
            break
        current = parent

    relative_candidates = ["", "Fiji", "Fiji.app", "ImageJ.app", os.path.join("Fiji.app", "Contents", "MacOS"), os.path.join("ImageJ.app", "Contents", "MacOS")]
    for root in roots:
        for rel in relative_candidates:
            folder = os.path.join(root, rel) if rel != "" else root
            for name in _fiji_launcher_names():
                candidate = os.path.join(folder, name)
                try:
                    if _is_verified_fiji_launcher(candidate):
                        candidates.append(os.path.abspath(candidate))
                except:
                    pass

    # Search only a shallow depth and retain only verified Fiji installations.
    for root in roots[:3]:
        try:
            if not os.path.isdir(root):
                continue
            root_depth = root.rstrip("\\/").count(os.sep)
            for walk_root, dirs, files in os.walk(root):
                depth = walk_root.rstrip("\\/").count(os.sep) - root_depth
                if depth > 3:
                    dirs[:] = []
                    continue
                lower_files = dict([(str(fn).lower(), fn) for fn in files])
                for launcher_name in _fiji_launcher_names():
                    actual = lower_files.get(launcher_name.lower())
                    if actual is not None:
                        candidate = os.path.abspath(os.path.join(walk_root, actual))
                        if _is_verified_fiji_launcher(candidate):
                            candidates.append(candidate)
        except:
            pass

    unique = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    if len(unique) == 0:
        return ""
    unique.sort(key=lambda p: _fiji_launcher_score(p, preferred_roots), reverse=True)
    return unique[0]

def _current_java_process_lines():
    lines = []
    try:
        from java.lang.management import ManagementFactory
        pid_text = str(ManagementFactory.getRuntimeMXBean().getName()).split("@")[0]
        if os.name == "nt" and pid_text != "":
            temp_dir = str(System.getProperty("java.io.tmpdir")) if 'System' in globals() else str(os.environ.get("TEMP", ""))
            if temp_dir == "":
                temp_dir = os.getcwd()
            capture_path = os.path.join(temp_dir, "gdl_fiji_process_" + pid_text + ".txt")
            ps = (
                "$p=Get-CimInstance Win32_Process -Filter \"ProcessId=" + pid_text + "\"; "
                "if($p){$p.ExecutablePath; $p.CommandLine; "
                "$q=Get-CimInstance Win32_Process -Filter (\"ProcessId=\"+$p.ParentProcessId); "
                "if($q){$q.ExecutablePath; $q.CommandLine}}"
            )
            cmd = ArrayList()
            cmd.add("powershell.exe")
            cmd.add("-NoProfile")
            cmd.add("-ExecutionPolicy")
            cmd.add("Bypass")
            cmd.add("-Command")
            cmd.add(ps)
            pb = ProcessBuilder(cmd)
            pb.redirectErrorStream(True)
            pb.redirectOutput(File(capture_path))
            proc = pb.start()
            proc.waitFor()
            if os.path.isfile(capture_path):
                f = codecs.open(capture_path, "r", "utf-8")
                try:
                    lines = [str(x).strip() for x in f.readlines() if str(x).strip() != ""]
                finally:
                    f.close()
                try:
                    os.remove(capture_path)
                except:
                    pass
    except Exception as e:
        IJ.log("BEAST Fiji process-path query was unavailable: " + str(e))
    return lines


def _bounded_fiji_root_candidates():
    """Return a small, ordered set of plausible Fiji installation roots.

    This intentionally avoids java.class.path expansion and recursive directory
    walks. Those paths can contain hundreds of JAR entries and made v127 appear
    frozen before the preflight started.
    """
    roots = []

    def add_root(value):
        try:
            if value is None:
                return
            raw = str(value).strip().strip('"')
            if raw == "":
                return
            p = os.path.abspath(raw)
            if os.path.isfile(p):
                p = os.path.dirname(p)
            low_name = os.path.basename(p).lower()
            if low_name in ["plugins", "macros", "jars", "scripts", "luts"]:
                p = os.path.dirname(p)
            _append_unique_path(roots, p)
        except:
            pass

    # The active Fiji instance is authoritative and must be checked first.
    for directory_name in ["imagej", "startup", "plugins", "macros"]:
        try:
            add_root(IJ.getDirectory(directory_name))
        except:
            pass

    try:
        for prop_name in ["ij.dir", "fiji.dir", "user.dir"]:
            add_root(System.getProperty(prop_name, ""))
    except:
        pass

    for env_name in ["FIJI_HOME", "IMAGEJ_HOME", "IJ_HOME"]:
        try:
            add_root(os.environ.get(env_name, ""))
        except:
            pass

    # Explicit operator roots requested for both workstations.
    for root in [
        r"C:/Fixture/GDL", r"C:/Fixture/GDL",
        r"C:/Fixture/GDL", r"C:/Fixture/GDL",
        r"C:/Fixture/GDL",
        r"C:/Fixture/GDL"
    ]:
        add_root(root)

    try:
        user_profile = str(os.environ.get("USERPROFILE", ""))
        add_root(os.path.join(user_profile, "Fiji"))
        add_root(os.path.join(user_profile, "Fiji.app"))
    except:
        pass

    # A verified cache is useful, but never outranks the active Fiji root.
    try:
        cached = str(Prefs.get(SETTINGS_PREF_PREFIX + "beast_fiji_executable", ""))
        if _is_verified_fiji_launcher(cached):
            add_root(_fiji_install_root_from_launcher(cached))
        elif cached != "":
            IJ.log("BEAST cleared cached non-Fiji/legacy launcher: " + cached)
            Prefs.set(SETTINGS_PREF_PREFIX + "beast_fiji_executable", "")
            Prefs.savePreferences()
    except:
        pass

    return roots


def _direct_fiji_launchers_for_root(root):
    candidates = []
    if root is None or str(root).strip() == "":
        return candidates
    try:
        root = os.path.abspath(str(root))
    except:
        return candidates

    folders = [
        root,
        os.path.join(root, "Fiji"),
        os.path.join(root, "Fiji.app"),
        os.path.join(root, "ImageJ.app"),
        os.path.join(root, "Fiji.app", "Contents", "MacOS"),
        os.path.join(root, "ImageJ.app", "Contents", "MacOS")
    ]
    seen_folders = []
    known_names = set([str(x).lower() for x in _fiji_launcher_names()])
    for folder in folders:
        try:
            key = os.path.abspath(folder).lower()
            if key in seen_folders:
                continue
            seen_folders.append(key)
            if not os.path.isdir(folder):
                continue

            # Enumerate only the installation folder itself. This is bounded and
            # case-insensitive, and it recognizes Jaunch's fiji.bat even when the
            # filename capitalization differs.
            for actual_name in os.listdir(folder):
                low_name = str(actual_name).lower()
                candidate = os.path.join(folder, actual_name)
                recognized = low_name in known_names
                if not recognized:
                    # Accept application-named top-level launchers from current
                    # Fiji packages, but never generic Java/configurator binaries.
                    extension_ok = low_name.endswith(".exe") or low_name.endswith(".bat") or low_name.endswith(".cmd")
                    app_name_ok = low_name.startswith("fiji") or low_name.startswith("imagej")
                    recognized = extension_ok and app_name_ok
                if recognized and _is_verified_fiji_launcher(candidate):
                    absolute = os.path.abspath(candidate)
                    if absolute not in candidates:
                        candidates.append(absolute)
        except Exception as e_list_fiji:
            try:
                IJ.log("BEAST could not list Fiji launcher folder " + str(folder) + ": " + str(e_list_fiji))
            except:
                pass
    return candidates


def _process_reported_fiji_launchers():
    candidates = []
    try:
        lines = _current_java_process_lines()
        for line in lines:
            raw = str(line).strip().strip('"')
            possible = []
            if os.path.isfile(raw):
                possible.append(raw)
            # Extract executable or batch paths from a full Windows command line.
            try:
                matches = re.findall(r'(?i)(?:"([A-Z]:\\[^"\r\n]+?\.(?:exe|bat|cmd))"|([A-Z]:\\[^\r\n]+?\.(?:exe|bat|cmd)))', str(line))
                for match in matches:
                    for value in match:
                        if value is not None and str(value).strip() != "":
                            possible.append(str(value).strip())
            except:
                pass
            for candidate in possible:
                try:
                    if _is_verified_fiji_launcher(candidate):
                        absolute = os.path.abspath(candidate)
                        if absolute not in candidates:
                            candidates.append(absolute)
                except:
                    pass
    except Exception as e:
        try: IJ.log("BEAST current-process Fiji launcher detection failed: " + str(e))
        except: pass
    return candidates


def _log_root_launcher_inventory(root):
    try:
        if root is None or not os.path.isdir(str(root)):
            return
        names = []
        for fn in os.listdir(str(root)):
            low = str(fn).lower()
            if low.endswith(".exe") or low.endswith(".bat") or low.endswith(".cmd"):
                names.append(str(fn))
        if len(names) > 0:
            IJ.log("BEAST Fiji launcher files in " + str(root) + ": " + " | ".join(sorted(names)[:40]))
    except:
        pass


def find_fiji_executable():
    override = os.environ.get("GDL_FIJI_LAUNCHER_OVERRIDE", "").strip()
    if override and os.path.isfile(override):
        return override
    """Resolve Fiji quickly without recursively scanning user folders or JARs."""
    started = time.time()
    roots = _bounded_fiji_root_candidates()
    try:
        IJ.showStatus("BEAST MODE: locating the active Fiji launcher...")
        IJ.log("BEAST Fiji bounded roots (" + str(len(roots)) + "): " +
               " | ".join([str(x) for x in roots[:12]]))
    except:
        pass

    candidates = []
    # The executable path of the already-running Fiji process is the strongest
    # signal and supports custom/renamed Jaunch front ends.
    for candidate in _process_reported_fiji_launchers():
        if candidate not in candidates:
            candidates.append(candidate)
    if len(candidates) > 0:
        candidates.sort(key=lambda p: _fiji_launcher_score(p, roots), reverse=True)
        found = candidates[0]
        try:
            Prefs.set(SETTINGS_PREF_PREFIX + "beast_fiji_executable", found)
            Prefs.savePreferences()
        except:
            pass
        IJ.log("BEAST current-process Fiji launcher selected: " + str(found))
        return found

    for root_index, root in enumerate(roots):
        if root_index < 4:
            _log_root_launcher_inventory(root)
        try:
            IJ.showStatus("BEAST Fiji detection: checking " + str(root))
        except:
            pass
        for candidate in _direct_fiji_launchers_for_root(root):
            if candidate not in candidates:
                candidates.append(candidate)
        # The first root normally comes directly from IJ.getDirectory("imagej").
        # Return immediately when it contains a verified launcher.
        if root_index == 0 and len(candidates) > 0:
            break

    if len(candidates) == 0:
        elapsed = time.time() - started
        IJ.log("BEAST Fiji bounded detection finished in %.2f s with no verified launcher." % elapsed)
        return ""

    candidates.sort(key=lambda p: _fiji_launcher_score(p, roots), reverse=True)
    found = candidates[0]
    try:
        Prefs.set(SETTINGS_PREF_PREFIX + "beast_fiji_executable", found)
        Prefs.savePreferences()
    except:
        pass
    elapsed = time.time() - started
    IJ.log("BEAST verified Fiji launcher selected in %.2f s: %s" % (elapsed, str(found)))
    IJ.showStatus("BEAST Fiji launcher found: " + os.path.basename(str(found)))
    return found


def current_script_path():
    candidates = []
    # Explicit modular-launcher handoff must precede __file__, because a worker
    # wrapper's __file__ points into BEAST_Fiji_Workers rather than the app bundle.
    try:
        candidates.append(str(globals().get("GDL_APP_LAUNCHER_PATH", "")))
    except:
        pass
    try:
        candidates.append(str(os.environ.get("GDL_V193_LAUNCHER", "")))
    except:
        pass
    try:
        candidates.append(str(globals().get("__file__", "")))
    except:
        pass
    try:
        import sys
        if len(sys.argv) > 0:
            candidates.append(str(sys.argv[0]))
    except:
        pass
    try:
        candidates.append(str(os.environ.get("GDL_BEAST_PARENT_SCRIPT", "")))
    except:
        pass
    try:
        candidates.append(str(Prefs.get(SETTINGS_PREF_PREFIX + "beast_parent_script_path", "")))
    except:
        pass
    for candidate in candidates:
        try:
            if candidate is not None and str(candidate).strip() != "" and File(str(candidate)).exists():
                p = os.path.abspath(str(candidate))
                if p.lower().endswith(".py"):
                    return p
        except:
            pass
    return ""


def _script_candidate_score(path):
    try:
        name = os.path.basename(str(path)).lower()
        score = 0
        if "youre_a_beta" in name or "gdl_analysis" in name or name in ["run me.py", "run in fiji.py"]: score += 1000
        if "beast_mode" in name: score += 300
        if "v193" in name: score += 20000
        if name.endswith(".py"): score += 100
        score += min(99, int(os.path.getmtime(path)) % 100)
        return score
    except:
        return -1


def _search_saved_script_near(output_root):
    roots = []
    try:
        _append_unique_path(roots, os.path.dirname(os.path.abspath(str(output_root))))
    except:
        pass
    try:
        _append_unique_path(roots, os.getcwd())
    except:
        pass
    try:
        from java.lang import System
        _append_unique_path(roots, System.getProperty("user.dir", ""))
        user_home = str(System.getProperty("user.home", ""))
        _append_unique_path(roots, os.path.join(user_home, "Downloads"))
        _append_unique_path(roots, os.path.join(user_home, "Desktop"))
    except:
        pass

    candidates = []
    excluded_tokens = ["beast_fiji_workers", "beast_preflight", "__pycache__"]
    for root_index, root in enumerate(roots):
        if root == "" or not os.path.isdir(root):
            continue
        try:
            max_depth = 1 if root_index == 0 else 2
            root_depth = root.rstrip("\\/").count(os.sep)
            for walk_root, dirs, files in os.walk(root):
                low_root = str(walk_root).lower()
                if any(token in low_root for token in excluded_tokens):
                    dirs[:] = []
                    continue
                depth = walk_root.rstrip("\\/").count(os.sep) - root_depth
                if depth > max_depth:
                    dirs[:] = []
                    continue
                for fn in files:
                    low_name = str(fn).lower()
                    if low_name.endswith(".py") and ("youre_a_beta" in low_name or "gdl_analysis" in low_name or low_name in ["run me.py", "run in fiji.py"]):
                        candidate_path = os.path.abspath(os.path.join(walk_root, fn))
                        root_priority = 100000 if root_index == 0 else max(0, 10000 - root_index * 1000)
                        candidates.append((root_priority, candidate_path))
        except:
            pass
    if len(candidates) == 0:
        return ""
    candidates.sort(key=lambda item: (item[0] + _script_candidate_score(item[1]), os.path.getmtime(item[1])), reverse=True)
    return candidates[0][1]


def is_current_v193_launcher_path(path):
    try:
        p = os.path.abspath(str(path))
        if not os.path.isfile(p):
            return False
        low_name = os.path.basename(p).lower()
        low_parent = os.path.basename(os.path.dirname(p)).lower()
        if "v193" in low_name or "v193" in low_parent:
            return True
        app_dir = os.path.dirname(p)
        support_dir = os.path.join(app_dir, "Defaults and Other Stuff")
        return os.path.isfile(os.path.join(support_dir, "GDL_User_Defaults.py")) and os.path.isdir(os.path.join(app_dir, "GDL_code"))
    except:
        return False


def resolve_beast_parent_script_path(settings=None, output_root=None):
    # External workers must execute this version, never a stale cached older file.
    # The folder containing the selected output root is searched first because the
    # downloadable ZIP is normally extracted and run from that folder.
    nearby = ""
    if output_root is not None:
        nearby = _search_saved_script_near(output_root)
        if nearby != "" and is_current_v193_launcher_path(nearby):
            if settings is not None:
                settings["_beast_parent_script_path"] = nearby
            try:
                Prefs.set(SETTINGS_PREF_PREFIX + "beast_parent_script_path", nearby)
                Prefs.savePreferences()
            except:
                pass
            return nearby

    path = current_script_path()
    if path != "" and not is_current_v193_launcher_path(path):
        IJ.log("BEAST ignored stale parent-script path: " + str(path))
        path = ""

    if path == "" and nearby != "":
        path = nearby

    if path != "":
        if settings is not None:
            settings["_beast_parent_script_path"] = path
        try:
            Prefs.set(SETTINGS_PREF_PREFIX + "beast_parent_script_path", path)
            Prefs.savePreferences()
        except:
            pass
        return path

    if settings is not None:
        settings["_beast_parent_script_path"] = ""
    try:
        Prefs.set(SETTINGS_PREF_PREFIX + "beast_parent_script_path", "")
        Prefs.savePreferences()
    except:
        pass
    return ""

def wait_for_marker_or_process_exit(process, marker_path, timeout_sec):
    """Wait for a marker for the full timeout, even if the native launcher detaches.

    On Windows the Fiji launcher can exit after spawning the JVM. Treating that
    launcher exit as a failed probe caused false negatives in v125-v127.
    """
    start = time.time()
    launcher_exited = False
    while time.time() - start <= float(timeout_sec):
        if path_exists(marker_path):
            return True, ""
        if process is not None and not process_is_alive(process):
            launcher_exited = True
        try:
            elapsed = int(time.time() - start)
            IJ.showStatus("BEAST launch preflight: waiting for marker " +
                          str(elapsed) + "/" + str(int(timeout_sec)) + " s")
        except:
            pass
        time.sleep(0.2)
    if launcher_exited:
        return False, ("Timed out after " + str(timeout_sec) +
                       " seconds. The native launcher detached/exited, but the Fiji JVM never wrote the marker.")
    return False, "Timed out after " + str(timeout_sec) + " seconds waiting for marker."


def _windows_command_line_quote(value):
    s = str(value)
    return '"' + s.replace('"', '""') + '"'


def _is_windows_runtime():
    try:
        return str(System.getProperty("os.name", "")).lower().startswith("windows")
    except:
        try:
            return str(os.sep) == "\\"
        except:
            return False


def _is_modern_fiji_jaunch(fiji_launcher):
    """Detect current Jaunch-based Fiji launchers reliably.

    Some current Windows Fiji packages expose fiji-windows-x64.exe directly and
    keep fiji.toml under config rather than config/jaunch. Missing those layouts
    caused BEAST preflight macros to enter Fiji's single-instance handoff and run
    inside the controller process. The probe calls System.exit, so that handoff
    could close the user's main Fiji session.
    """
    try:
        launcher = os.path.abspath(str(fiji_launcher))
        root = _fiji_install_root_from_launcher(launcher)
        name = os.path.basename(launcher).lower()
        if name in ["fiji.bat", "fiji.cmd", "fiji.exe", "fiji"]:
            return True
        if name.startswith("fiji-windows-") and name.endswith(".exe"):
            return True
        if name.startswith("fiji-linux-") or name.startswith("fiji-macos-"):
            return True
        config_candidates = [
            os.path.join(root, "config", "jaunch", "fiji.toml"),
            os.path.join(root, "config", "fiji.toml")
        ]
        for config_path in config_candidates:
            if os.path.isfile(config_path):
                return True
    except:
        pass
    return False


def _native_fiji_launchers_for_selected(selected_launcher):
    """Return verified launchers in deterministic worker order.

    The native Jaunch executable stays attached to its JVM more reliably than the
    fiji.bat shim on Windows, so it is preferred for diagnostics and workers.
    """
    candidates = []
    try:
        selected = os.path.abspath(str(selected_launcher))
        root = _fiji_install_root_from_launcher(selected)
        preferred_names = [
            "fiji-windows-x64.exe", "fiji-windows-arm64.exe", "fiji-windows-x86.exe",
            "fiji.exe", "fiji.bat", "fiji.cmd", "ImageJ-win64.exe", "ImageJ.exe"
        ]
        for name in preferred_names:
            candidate = os.path.join(root, name)
            if _is_verified_fiji_launcher(candidate) and candidate not in candidates:
                candidates.append(candidate)
        if _is_verified_fiji_launcher(selected) and selected not in candidates:
            candidates.append(selected)
    except:
        pass
    return candidates


def preferred_fiji_worker_launcher(selected_launcher):
    candidates = _native_fiji_launchers_for_selected(selected_launcher)
    if len(candidates) > 0:
        return candidates[0]
    return str(selected_launcher)


def _write_visible_jython_macro_bridge(script_path):
    """Write an ImageJ macro that executes a Jython file automatically.

    Fiji's GUI-mode ``--run path.py`` can open the Script Editor instead of
    executing the script. ImageJ's ``-macro`` route executes automatically in
    GUI mode. The bridge reads the generated wrapper and evaluates it with the
    installed Python (Jython) interpreter.
    """
    script_text_path = str(script_path)
    bridge_path = os.path.splitext(script_text_path)[0] + "_autorun.ijm"
    macro_path = script_text_path.replace("\\", "/").replace('"', '\\"')
    f = open(bridge_path, "w")
    try:
        f.write('scriptPath = "' + macro_path + '";\n')
        f.write('scriptText = File.openAsString(scriptPath);\n')
        f.write('if (startsWith(scriptText, "Error:")) exit(scriptText);\n')
        f.write('eval("python", scriptText);\n')
    finally:
        f.close()
    return bridge_path


def fiji_script_launch_arguments(fiji_launcher, script_path, direct_script=False, diagnostic=False, visible_worker=False):
    """Build a Fiji command that executes Jython without manual intervention.

    Silent agents use Fiji's documented ``--headless --run`` route. Visible
    agents use ``-macro`` with a generated macro bridge; otherwise Fiji may
    merely open the Jython file in the Script Editor and wait for a click on
    Run.
    """
    args = []
    if _is_modern_fiji_jaunch(fiji_launcher):
        args.append("--no-python")
        args.append("--forbid-single-instance")
        args.append("--allow-multiple")
        if not bool(visible_worker):
            args.append("--headless")
        args.append("--no-splash")
        if diagnostic:
            args.append("--debug")
        args.append("-Dimagej.updater.disableAutocheck=true")
    else:
        # Legacy ImageJ uses port 0 to disable its OtherInstance/RMI handoff.
        args.append("-port0")
        if not bool(visible_worker):
            args.append("--headless")

    if bool(visible_worker):
        bridge_path = _write_visible_jython_macro_bridge(script_path)
        args.extend(["-macro", str(bridge_path)])
    elif direct_script:
        args.append(str(script_path))
    else:
        args.extend(["--run", str(script_path)])
    return args

def build_fiji_launch_command(fiji_launcher, arguments):
    """Build a ProcessBuilder command for legacy executables or modern fiji.bat."""
    launcher = str(fiji_launcher)
    args = [str(x) for x in arguments]
    low = launcher.lower()
    cmd = ArrayList()
    if _is_windows_runtime() and (low.endswith(".bat") or low.endswith(".cmd")):
        command_line = "call " + _windows_command_line_quote(launcher)
        for arg in args:
            command_line += " " + _windows_command_line_quote(arg)
        cmd.add("cmd.exe")
        cmd.add("/d")
        cmd.add("/s")
        cmd.add("/c")
        cmd.add(command_line)
    else:
        cmd.add(launcher)
        for arg in args:
            cmd.add(arg)
    return cmd


def fiji_launch_command_text(fiji_launcher, arguments):
    try:
        cmd = build_fiji_launch_command(fiji_launcher, arguments)
        return " ".join([str(cmd.get(i)) for i in range(cmd.size())])
    except:
        return str(fiji_launcher) + " " + " ".join([str(x) for x in arguments])


def _java_process_pid_text(process):
    try:
        return str(process.pid())
    except:
        try:
            text = str(process)
            match = re.search(r"pid[=:](\d+)", text, re.I)
            if match:
                return str(match.group(1))
        except:
            pass
    return "UNKNOWN"


def _append_text_line(path, text):
    try:
        parent = os.path.dirname(str(path))
        if parent != "":
            ensure_dir(parent)
        f = codecs.open(str(path), "a", "utf-8")
        try:
            f.write(str(text) + "\n")
        finally:
            f.close()
    except:
        pass
