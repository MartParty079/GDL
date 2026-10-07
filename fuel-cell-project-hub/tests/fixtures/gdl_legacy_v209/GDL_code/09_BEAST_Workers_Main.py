# -*- coding: utf-8 -*-
# MODULE 09: BEAST workers, preflight, progress, and application main routine


def zip_beast_fiji_diagnostics(output_root):
    """Create one upload-ready ZIP from preflight and worker diagnostics."""
    zip_path = os.path.join(output_root, "BEAST_Fiji_Diagnostics.zip")
    folders = [
        (os.path.join(output_root, "BEAST_Preflight"), "BEAST_Preflight"),
        (os.path.join(output_root, "BEAST_Fiji_Workers"), "BEAST_Fiji_Workers")
    ]
    try:
        if os.path.exists(zip_path):
            os.remove(zip_path)
    except:
        pass
    fos = FileOutputStream(zip_path)
    zos = ZipOutputStream(fos)
    added = 0
    try:
        for folder, prefix in folders:
            if not os.path.isdir(folder):
                continue
            for walk_root, dirs, files in os.walk(folder):
                for fn in files:
                    file_path = os.path.join(walk_root, fn)
                    try:
                        rel = os.path.relpath(file_path, folder).replace("\\", "/")
                        zip_writefile(zos, prefix + "/" + rel, file_path)
                        added += 1
                    except:
                        pass
    finally:
        zos.close()
        fos.close()
    if added <= 0:
        try: os.remove(zip_path)
        except: pass
        return ""
    IJ.log("BEAST Fiji diagnostics ZIP: " + str(zip_path))
    return zip_path


def run_beast_fiji_preflight(output_root, fiji_exe, timeout_sec, visible_worker=False):
    preflight_dir = os.path.join(output_root, "BEAST_Preflight")
    ensure_dir(preflight_dir)
    probe_script = os.path.join(preflight_dir, "Fiji_launch_probe.py")
    marker_path = os.path.join(preflight_dir, "FIJI_PREFLIGHT_OK.txt")
    started_path = os.path.join(preflight_dir, "FIJI_PREFLIGHT_SCRIPT_STARTED.txt")
    error_path = os.path.join(preflight_dir, "FIJI_PREFLIGHT_SCRIPT_ERROR.txt")
    attempts_log = os.path.join(preflight_dir, "Fiji_preflight_attempts.log")
    for p in [marker_path, started_path, error_path, attempts_log]:
        try:
            if os.path.exists(p): os.remove(p)
        except:
            pass
    # Create the controller-side log before any launcher call, so failure can
    # never produce a missing diagnostics file again.
    _append_text_line(attempts_log, "BEAST Fiji preflight created=" + str(time.time()))
    _append_text_line(attempts_log, "probe_script=" + str(probe_script))
    _append_text_line(attempts_log, "expected_ok_marker=" + str(marker_path))
    _append_text_line(attempts_log, "selected_launcher=" + str(fiji_exe))

    f = open(probe_script, "w")
    try:
        f.write('import os, time, traceback, threading\n')
        f.write('from java.lang import System\n')
        f.write('_isolated = str(System.getProperty("gdl.beast.preflight","")).lower() == "true"\n')
        f.write('def _beast_write(_p,_t):\n')
        f.write('    _f=open(_p,"w")\n    _f.write(str(_t))\n    _f.close()\n')
        f.write('_started=r"' + str(started_path).replace('"', '\\"') + '"\n')
        f.write('_ok=r"' + str(marker_path).replace('"', '\\"') + '"\n')
        f.write('_err=r"' + str(error_path).replace('"', '\\"') + '"\n')
        f.write('try:\n')
        f.write('    if not _isolated:\n        raise Exception("BEAST preflight entered an existing Fiji instance; isolated launch property is missing")\n')
        f.write('    _beast_write(_started,"started="+str(time.time())+";pid="+str(getattr(os,"getpid",lambda:0)()))\n')
        f.write('    from ij import IJ, ImagePlus\n')
        f.write('    from ij.process import ByteProcessor\n')
        f.write('    from ij.measure import ResultsTable\n')
        f.write('    _ip=ByteProcessor(24,24)\n')
        f.write('    for _y in range(8,16):\n        for _x in range(8,16):\n            _ip.set(_x,_y,255)\n')
        f.write('    _imp=ImagePlus("BEAST_HEADLESS_PREFLIGHT",_ip)\n')
        f.write('    IJ.setThreshold(_imp,128,255)\n')
        f.write('    IJ.run(_imp,"Convert to Mask","")\n')
        f.write('    ResultsTable.getResultsTable().reset()\n')
        f.write('    IJ.run(_imp,"Analyze Particles...","size=1-Infinity show=Nothing clear")\n')
        f.write('    _count=ResultsTable.getResultsTable().getCounter()\n')
        f.write('    if _count < 1:\n        raise Exception("Headless Analyze Particles returned no rows")\n')
        f.write('    _imp.close()\n')
        f.write('    _beast_write(_ok,"FIJI_PREFLIGHT_OK;particles="+str(_count))\n')
        f.write('except:\n')
        f.write('    try:\n        _beast_write(_err,traceback.format_exc())\n    except:\n        pass\n')
        f.write('    if _isolated:\n        System.exit(2)\n')
        f.write('if _isolated:\n    System.exit(0)\n')
    finally:
        f.close()

    launchers = _native_fiji_launchers_for_selected(fiji_exe)
    if len(launchers) == 0:
        launchers = [str(fiji_exe)]
    # Three deterministic attempts: native --run, native direct-script, then
    # the batch/front-end --run if it differs. This covers both current Jaunch
    # and older Fiji without unbounded retries.
    attempts = []
    attempts.append((launchers[0], False, "native_run"))
    attempts.append((launchers[0], True, "native_direct_script"))
    if len(launchers) > 1:
        attempts.append((launchers[1], False, "frontend_run"))
    total_marker_budget = max(5, min(60, int(timeout_sec)))
    marker_deadline = time.time() + float(total_marker_budget)
    _append_text_line(attempts_log, "total_marker_budget_sec=" + str(total_marker_budget))
    _append_text_line(attempts_log, "visible_worker=" + str(bool(visible_worker)))
    failures = []

    for attempt_index, attempt in enumerate(attempts):
        remaining_budget = marker_deadline - time.time()
        if remaining_budget <= 0:
            failures.append("Preflight marker budget exhausted after " + str(total_marker_budget) + " seconds.")
            break
        launcher, direct_script, label = attempt
        for p in [marker_path, started_path, error_path]:
            try:
                if os.path.exists(p): os.remove(p)
            except:
                pass
        console_path = os.path.join(preflight_dir, "Fiji_preflight_attempt_%02d_%s_console.log" % (attempt_index + 1, label))
        try:
            if os.path.exists(console_path): os.remove(console_path)
        except:
            pass
        # Pre-create the console file before ProcessBuilder.
        _append_text_line(console_path, "BEAST controller created this log before launch.")
        launch_args = fiji_script_launch_arguments(launcher, probe_script, direct_script, True, visible_worker)
        if _is_modern_fiji_jaunch(launcher):
            property_index = len(launch_args)
            for execution_token in ["-macro", "--run"]:
                try:
                    property_index = launch_args.index(execution_token)
                    break
                except:
                    pass
            if direct_script and property_index == len(launch_args) and len(launch_args) > 0:
                property_index = len(launch_args) - 1
            launch_args.insert(property_index, "-Dgdl.beast.preflight=true")
        command_text = fiji_launch_command_text(launcher, launch_args)
        _append_text_line(attempts_log, "ATTEMPT %d label=%s" % (attempt_index + 1, label))
        _append_text_line(attempts_log, "launcher=" + str(launcher))
        _append_text_line(attempts_log, "command=" + str(command_text))
        if bool(visible_worker):
            _append_text_line(attempts_log, "autorun_macro=" + str(os.path.splitext(str(probe_script))[0] + "_autorun.ijm"))
        IJ.log("BEAST Fiji preflight attempt " + str(attempt_index + 1) + ": " + str(command_text))
        proc = None
        try:
            cmd = build_fiji_launch_command(launcher, launch_args)
            builder = ProcessBuilder(cmd)
            try: builder.directory(File(os.path.dirname(str(launcher))))
            except: pass
            try:
                builder.redirectErrorStream(True)
                builder.redirectOutput(ProcessBuilder.Redirect.appendTo(File(console_path)))
            except:
                try:
                    builder.redirectErrorStream(True)
                    builder.redirectOutput(File(console_path))
                except:
                    pass
            proc = builder.start()
            _append_text_line(attempts_log, "pid=" + _java_process_pid_text(proc))
            remaining_budget = max(1.0, marker_deadline - time.time())
            ok, reason = wait_for_marker_or_process_exit(proc, marker_path, remaining_budget)
            if path_exists(error_path):
                try:
                    ef = codecs.open(error_path, "r", "utf-8")
                    try: reason = "Probe script executed but failed: " + ef.read()
                    finally: ef.close()
                except:
                    reason = "Probe script executed but wrote an error marker."
                ok = False
            destroy_process_safely(proc, True)
            _append_text_line(attempts_log, "script_started_marker=" + str(path_exists(started_path)))
            _append_text_line(attempts_log, "ok_marker=" + str(path_exists(marker_path)))
            _append_text_line(attempts_log, "result=" + ("PASS" if ok else "FAIL: " + str(reason)))
            if ok:
                _append_text_line(attempts_log, "SUCCESS launcher=" + str(launcher) + "; mode=" + str(label))
                return console_path, str(launcher), str(label)
            failures.append(label + ": " + str(reason) + "; console=" + str(console_path))
        except Exception as launch_error:
            try:
                if proc is not None: destroy_process_safely(proc, True)
            except:
                pass
            failure_text = label + ": launcher exception: " + str(launch_error) + "; console=" + str(console_path)
            failures.append(failure_text)
            _append_text_line(attempts_log, "result=FAIL: " + failure_text)

    raise Exception("All Fiji worker preflight launch methods failed. Diagnostics: " + str(attempts_log) + ". " + " | ".join(failures))

def run_beast_jmp_preflight(output_root, jmp_exe, timeout_sec):
    preflight_dir = os.path.join(output_root, "BEAST_Preflight")
    ensure_dir(preflight_dir)
    probe_jsl = os.path.join(preflight_dir, "JMP_launch_probe.jsl")
    marker_path = os.path.join(preflight_dir, "JMP_PREFLIGHT_OK.txt")
    console_path = os.path.join(preflight_dir, "JMP_preflight_console.log")
    for p in [marker_path, console_path]:
        try:
            if os.path.exists(p): os.remove(p)
        except:
            pass
    f = codecs.open(probe_jsl, "w", "utf-8")
    try:
        f.write('Names Default To Here(1);\n')
        f.write('Save Text File("' + jsl_path(marker_path) + '", "JMP_PREFLIGHT_OK");\n')
        f.write('Exit(NoSave);\n')
    finally:
        f.close()
    cmd = ArrayList(); cmd.add(str(jmp_exe)); cmd.add(str(probe_jsl))
    builder = ProcessBuilder(cmd)
    try: builder.directory(File(os.path.dirname(str(jmp_exe))))
    except: pass
    try:
        builder.redirectErrorStream(True)
        builder.redirectOutput(File(console_path))
    except: pass
    proc = builder.start()
    ok, reason = wait_for_marker_or_process_exit(proc, marker_path, timeout_sec)
    destroy_process_safely(proc, True)
    if not ok:
        raise Exception("JMP launch preflight failed: " + reason + " Console: " + console_path)
    return console_path


def prepare_beast_runtime_before_progress(output_root, settings):
    # Fiji may be external for resilient workers. JMP is external only when the
    # BEAST graph/histogram Word-report option is enabled.
    jmp_required = beast_jmp_histograms_enabled(settings)
    if jmp_required:
        jmp_exe = find_jmp_exe(settings)
        if jmp_exe == "":
            raise Exception("JMP histograms are enabled, but the JMP executable could not be found. Check the JMP path on General + JMP.")
    else:
        jmp_exe = "DISABLED_NO_HISTOGRAMS"
        IJ.log("BEAST JMP disabled: histogram/graph Word reporting is unchecked. Fiji will write EPD directly to the XLSX data sheet.")

    configured_agents = max(1, int(settings.get("beast_fiji_parallel_instances", 1)))
    parallel_requested = bool(settings.get("beast_parallel_fiji_enabled", False)) and configured_agents > 1
    fallback_enabled = bool(settings.get("beast_fiji_fallback_to_controller", True))
    script_path = ""
    fiji_exe = "CURRENT_RUNNING_FIJI"

    if not parallel_requested:
        settings["beast_parallel_fiji_enabled"] = False
        settings["beast_fiji_parallel_instances"] = 1
        IJ.log("BEAST external Fiji preflight skipped: one controller agent is selected.")

    if parallel_requested:
        script_path = resolve_beast_parent_script_path(settings, output_root)
        fiji_exe = find_fiji_executable()
        if script_path == "" or fiji_exe == "":
            reason = "Parallel Fiji path resolution failed. script=" + str(script_path) + "; Fiji=" + str(fiji_exe)
            if fallback_enabled:
                IJ.log("BEAST Fiji workers disabled for this run: " + reason + ". Falling back to the current Fiji instance.")
                settings["beast_parallel_fiji_enabled"] = False
                settings["beast_fiji_parallel_instances"] = 1
                parallel_requested = False
                script_path = ""
                fiji_exe = "CURRENT_RUNNING_FIJI"
            else:
                raise Exception(reason)

    settings["_beast_parent_script_path"] = script_path
    settings["_beast_fiji_exe"] = fiji_exe
    settings["_beast_jmp_exe"] = jmp_exe
    settings["_beast_jmp_required"] = jmp_required
    timeout_sec = max(5, min(60, int(settings.get("beast_preflight_timeout_sec", 60))))
    IJ.log("BEAST runtime resolution: script=" + str(script_path) + "; Fiji=" + str(fiji_exe) + "; JMP=" + str(jmp_exe))

    if parallel_requested:
        ensure_dir(os.path.join(output_root, "BEAST_Preflight"))
        ensure_dir(os.path.join(output_root, "BEAST_Fiji_Workers"))
        IJ.log("BEAST Fiji diagnostics will be written before every launch under: " + os.path.join(output_root, "BEAST_Preflight") + " and " + os.path.join(output_root, "BEAST_Fiji_Workers"))

    if bool(settings.get("beast_preflight_enabled", True)):
        if parallel_requested:
            try:
                IJ.showStatus("BEAST MODE preflight: checking Fiji worker marker (60-second budget)...")
                fiji_log, successful_fiji_launcher, successful_fiji_mode = run_beast_fiji_preflight(
                    output_root, fiji_exe, timeout_sec, bool(settings.get("beast_show_fiji_worker_windows", True))
                )
                settings["_beast_fiji_preflight_log"] = fiji_log
                settings["_beast_fiji_exe"] = successful_fiji_launcher
                settings["_beast_fiji_launch_mode"] = successful_fiji_mode
                fiji_exe = successful_fiji_launcher
                IJ.log("BEAST Fiji worker preflight PASSED with " + str(successful_fiji_mode) + ": " + str(successful_fiji_launcher))
            except Exception as fiji_preflight_error:
                diagnostics_zip = zip_beast_fiji_diagnostics(output_root)
                if fallback_enabled:
                    IJ.log("BEAST Fiji preflight failed; using current Fiji instead: " + str(fiji_preflight_error) + (" Diagnostics ZIP: " + str(diagnostics_zip) if diagnostics_zip != "" else ""))
                    settings["beast_parallel_fiji_enabled"] = False
                    settings["beast_fiji_parallel_instances"] = 1
                    settings["_beast_parent_script_path"] = ""
                    settings["_beast_fiji_exe"] = "CURRENT_RUNNING_FIJI"
                    script_path = ""
                    fiji_exe = "CURRENT_RUNNING_FIJI"
                else:
                    raise
        if jmp_required:
            IJ.showStatus("BEAST MODE preflight: checking JMP launch...")
            jmp_log = run_beast_jmp_preflight(output_root, jmp_exe, timeout_sec)
            settings["_beast_jmp_preflight_log"] = jmp_log
            IJ.log("BEAST JMP preflight PASSED.")
        else:
            IJ.log("BEAST JMP preflight skipped because histograms/graphs are disabled.")
        IJ.showStatus("BEAST MODE preflight passed.")
    return script_path, fiji_exe, jmp_exe

def write_beast_fiji_worker_wrapper(wrapper_path, script_path, config_path, startup_path, error_path, heartbeat_path, heartbeat_interval_sec, worker_id):
    """Write a tiny worker bootstrap that loads split modules from the real app folder.

    v141 execfile'd the launcher while the generated wrapper remained __file__. The
    launcher consequently searched for companion modules inside BEAST_Fiji_Workers
    and stopped after the Fiji splash. v193 bypasses that ambiguity completely and uses an auto-run macro bridge for visible workers.
    """
    app_dir = os.path.dirname(os.path.abspath(str(script_path)))
    module_dir = str(globals().get("GDL_MODULE_DIR_OVERRIDE", "")).strip()
    if module_dir == "":
        module_dir = os.path.join(app_dir, str(globals().get("DEFAULT_CODE_FOLDER", "GDL_code")))
    support_dir = str(globals().get("GDL_SUPPORT_DIR", "")).strip() or os.path.join(app_dir, "Defaults and Other Stuff")
    defaults_path = os.path.join(support_dir, "GDL_User_Defaults.py")
    part_names = list(globals().get("CODE_MODULE_FILES", ['01_Core_Imports_Helpers.py', '02_User_Interface_Pages.py', '03_User_Interface_Settings.py', '04_Image_Processing_Sweeps.py', '05_Reports_Manual_Tools_Pore_Maps.py', '06A_Large_Pore_Repair.py', '06_Threshold_Analysis_JMP.py', '07_Run_Engine_Exports.py', '08_Workbook_JMP_Launch_Helpers.py', '09_BEAST_Workers_Main.py']))
    f = open(wrapper_path, "w")
    try:
        f.write('import os, time, traceback, threading\n')
        f.write('BEAST_WORKER_CONFIG_PATH = r"' + str(config_path).replace('"', '\\"') + '"\n')
        f.write('GDL_APP_LAUNCHER_PATH = r"' + str(script_path).replace('"', '\\"') + '"\n')
        f.write('GDL_APP_DIR = r"' + str(app_dir).replace('"', '\\"') + '"\n')
        f.write('_module_dir = r"' + str(module_dir).replace('"', '\\"') + '"\n')
        f.write('_defaults_path = r"' + str(defaults_path).replace('"', '\\"') + '"\n')
        f.write('_parts = ' + repr(part_names) + '\n')
        f.write('_error_path = r"' + str(error_path).replace('"', '\\"') + '"\n')
        f.write('_heartbeat_path = r"' + str(heartbeat_path).replace('"', '\\"') + '"\n')
        f.write('_heartbeat_interval = ' + repr(float(heartbeat_interval_sec)) + '\n')
        f.write('def _gdl_heartbeat_loop():\n')
        f.write('    while True:\n')
        f.write('        try:\n')
        f.write('            _hf = open(_heartbeat_path, \"w\")\n')
        f.write('            _hf.write(\"worker_id=' + str(worker_id) + ';pid=\" + str(getattr(os, \"getpid\", lambda: 0)()) + \";heartbeat=\" + str(time.time()))\n')
        f.write('            _hf.close()\n')
        f.write('        except:\n')
        f.write('            pass\n')
        f.write('        time.sleep(max(1.0, _heartbeat_interval))\n')
        f.write('_heartbeat_thread = threading.Thread(target=_gdl_heartbeat_loop)\n')
        f.write('_heartbeat_thread.setDaemon(True)\n')
        f.write('_heartbeat_thread.start()\n')
        f.write('try:\n')
        f.write('    os.environ["GDL_V193_LAUNCHER"] = GDL_APP_LAUNCHER_PATH\n')
        f.write('    if not os.path.isfile(_defaults_path):\n')
        f.write('        raise RuntimeError("Missing GDL user defaults file: " + _defaults_path)\n')
        f.write('    execfile(_defaults_path, globals(), globals())\n')
        f.write('    if not os.path.isdir(_module_dir):\n')
        f.write('        raise RuntimeError("Missing v193 code folder: " + _module_dir)\n')
        f.write('    _sf = open(r"' + str(startup_path).replace('"', '\\"') + '", "w")\n')
        f.write('    _pid = getattr(os, "getpid", lambda: 0)()\n')
        f.write('    _sf.write("worker_id=' + str(worker_id) + ';pid=" + str(_pid) + ";bootstrap=" + str(time.time()) + ";module_dir=" + _module_dir)\n')
        f.write('    _sf.close()\n')
        f.write('    for _part_name in _parts:\n')
        f.write('        _part_path = os.path.join(_module_dir, _part_name)\n')
        f.write('        if not os.path.isfile(_part_path):\n')
        f.write('            raise RuntimeError("Missing v193 code module: " + _part_path)\n')
        f.write('        execfile(_part_path, globals(), globals())\n')
        f.write('except:\n')
        f.write('    try:\n')
        f.write('        _ef=open(_error_path,"w")\n')
        f.write('        _ef.write(traceback.format_exc())\n')
        f.write('        _ef.close()\n')
        f.write('    except:\n        pass\n')
        f.write('    raise\n')
    finally:
        f.close()

def launch_beast_fiji_process(fiji_exe, wrapper_path, config_path, console_log_path, launch_log_path, launch_mode="native_run", visible_worker=False):
    # Reuse the exact launcher that passed preflight. If preflight was disabled,
    # find_fiji_executable already ranks the native Jaunch executable first.
    launcher = str(fiji_exe)
    direct_script = str(launch_mode) == "native_direct_script"
    launch_args = fiji_script_launch_arguments(launcher, wrapper_path, direct_script, True, visible_worker)
    cmd = build_fiji_launch_command(launcher, launch_args)
    command_text = fiji_launch_command_text(launcher, launch_args)
    # Controller-side logs exist before the OS process starts.
    _append_text_line(console_log_path, "BEAST controller created this console log before launch.")
    _append_text_line(launch_log_path, "created=" + str(time.time()))
    _append_text_line(launch_log_path, "launcher=" + str(launcher))
    _append_text_line(launch_log_path, "wrapper=" + str(wrapper_path))
    _append_text_line(launch_log_path, "config=" + str(config_path))
    _append_text_line(launch_log_path, "mode=" + str(launch_mode))
    _append_text_line(launch_log_path, "visible_worker=" + str(bool(visible_worker)))
    _append_text_line(launch_log_path, "command=" + str(command_text))
    if bool(visible_worker):
        _append_text_line(launch_log_path, "autorun_macro=" + str(os.path.splitext(str(wrapper_path))[0] + "_autorun.ijm"))
    IJ.log("BEAST Fiji worker command: " + str(command_text))
    builder = ProcessBuilder(cmd)
    try:
        builder.directory(File(os.path.dirname(str(launcher))))
    except:
        pass
    try:
        env = builder.environment()
        env.put("GDL_BEAST_WORKER_CONFIG", str(config_path))
        env.put("GDL_BEAST_PARENT_SCRIPT", str(wrapper_path))
    except:
        pass
    try:
        builder.redirectErrorStream(True)
        builder.redirectOutput(ProcessBuilder.Redirect.appendTo(File(str(console_log_path))))
    except:
        try:
            builder.redirectErrorStream(True)
            builder.redirectOutput(File(str(console_log_path)))
        except:
            pass
    process = builder.start()
    _append_text_line(launch_log_path, "pid=" + _java_process_pid_text(process))
    _append_text_line(launch_log_path, "process_started=true")
    return process

def beast_worker_result_candidate_paths(path):
    """Return the fixed result path plus two rotating OneDrive-safe snapshot slots."""
    base = str(path)
    return [base, base + ".slot0", base + ".slot1"]


def beast_worker_result_exists(path):
    for candidate in beast_worker_result_candidate_paths(path):
        try:
            if os.path.exists(candidate):
                return True
        except:
            pass
    return False


def beast_worker_result_latest_mtime(path):
    newest = 0.0
    for candidate in beast_worker_result_candidate_paths(path):
        try:
            if os.path.exists(candidate):
                newest = max(newest, float(os.path.getmtime(candidate)))
        except:
            pass
    return newest


def _write_worker_snapshot_bytes(target_path, payload_bytes, attempts=12):
    """Write one snapshot directly. Readers can fall back to the other rotating slot."""
    last_error = None
    attempt = 0
    while attempt < int(attempts):
        attempt += 1
        f = None
        try:
            f = open(target_path, "wb")
            f.write(payload_bytes)
            try:
                f.flush()
            except:
                pass
            try:
                os.fsync(f.fileno())
            except:
                pass
            f.close()
            return True
        except Exception as e:
            last_error = e
            try:
                if f is not None:
                    f.close()
            except:
                pass
            time.sleep(min(0.05 * float(attempt), 0.5))
    try:
        IJ.log("BEAST snapshot write failed after retries: " + str(target_path) + "; " + str(last_error))
    except:
        pass
    return False


def write_beast_worker_result(path, results, errors, sweep_events, complete=False):
    # OneDrive can lock a destination file during sync. The old remove+rename sequence
    # could therefore kill a worker even though image processing had succeeded.
    # Publish into alternating slots instead. While one slot is being rewritten, the
    # controller can continue reading the previous valid slot.
    payload = {
        "results": list(results),
        "errors": list(errors),
        "sweep_events": list(sweep_events),
        "complete": bool(complete),
        "updated_at": time.time()
    }
    payload_bytes = pickle.dumps(payload, 2)
    try:
        slot_index = int(len(results)) % 2
    except:
        slot_index = 0
    primary_slot = str(path) + ".slot" + str(slot_index)
    secondary_slot = str(path) + ".slot" + str(1 - slot_index)

    if _write_worker_snapshot_bytes(primary_slot, payload_bytes, 12):
        return True
    if _write_worker_snapshot_bytes(secondary_slot, payload_bytes, 12):
        return True

    # Last-resort direct write to the legacy path. This is non-atomic, but the reader
    # validates pickle content and will retry or use a rotating slot if it catches a
    # partial write. Never raise here solely because a cloud-sync client locked a file.
    if _write_worker_snapshot_bytes(str(path), payload_bytes, 20):
        return True
    try:
        IJ.log("BEAST worker snapshot could not be published; processing will continue and retry on the next run.")
    except:
        pass
    return False

def publish_beast_worker_snapshot(results, errors, sweep_events, complete=False):
    try:
        if BEAST_FIJI_WORKER_CONFIG is None:
            return
        result_path = str(BEAST_FIJI_WORKER_CONFIG.get("result_path", ""))
        if result_path != "":
            write_beast_worker_result(result_path, results, errors, sweep_events, complete)
    except Exception as e:
        IJ.log("Could not publish BEAST Fiji worker snapshot: " + str(e))


def mark_beast_worker_job_event(event_name, run_order, run_label):
    """Publish claim/completion proof from a real worker job."""
    try:
        if BEAST_FIJI_WORKER_CONFIG is None:
            return
        worker_id = int(BEAST_FIJI_WORKER_CONFIG.get("worker_id", 0))
        claim_path = str(BEAST_FIJI_WORKER_CONFIG.get("claim_path", ""))
        events_path = str(BEAST_FIJI_WORKER_CONFIG.get("job_events_path", ""))
        completed_count_path = str(BEAST_FIJI_WORKER_CONFIG.get("completed_count_path", ""))
        heartbeat_path = str(BEAST_FIJI_WORKER_CONFIG.get("heartbeat_path", ""))
        text = "worker_id=" + str(worker_id) + ";event=" + str(event_name) + ";run=" + str(run_order) + ";label=" + str(run_label) + ";time=" + str(time.time())
        if heartbeat_path != "":
            hf = open(heartbeat_path, "w")
            try:
                hf.write(text + ";heartbeat=event")
            finally:
                hf.close()
        if claim_path != "":
            f = open(claim_path, "w")
            try:
                f.write(text)
            finally:
                f.close()
        if events_path != "":
            _append_text_line(events_path, text)
        if str(event_name) == "COMPLETE" and completed_count_path != "":
            count_value = 0
            try:
                if os.path.exists(completed_count_path):
                    cf = open(completed_count_path, "r")
                    try:
                        count_value = int(str(cf.read()).strip() or "0")
                    finally:
                        cf.close()
            except:
                count_value = 0
            cf = open(completed_count_path, "w")
            try:
                cf.write(str(count_value + 1))
            finally:
                cf.close()
    except Exception as e:
        IJ.log("Could not publish Fiji worker job event: " + str(e))



def refresh_beast_worker_finished_markers(worker):
    """Return a live terminal-run count without depending on result snapshots."""
    previous_count = int(worker.get("marker_finished_count", 0))
    terminal_orders = worker.get("terminal_marker_orders")
    if terminal_orders is None:
        terminal_orders = set()
        worker["terminal_marker_orders"] = terminal_orders

    events_path = str(worker.get("job_events_path", ""))
    try:
        if events_path != "" and os.path.exists(events_path):
            file_size = int(os.path.getsize(events_path))
            offset = int(worker.get("job_events_offset", 0))
            if file_size < offset:
                offset = 0
                terminal_orders.clear()
            ef = open(events_path, "r")
            try:
                ef.seek(offset)
                while True:
                    line = ef.readline()
                    if line == "":
                        break
                    event_match = re.search(r"(?:^|;)event=([^;]+)", str(line))
                    run_match = re.search(r"(?:^|;)run=([^;]+)", str(line))
                    if event_match is None or run_match is None:
                        continue
                    event_name = str(event_match.group(1)).strip().upper()
                    run_order_text = str(run_match.group(1)).strip()
                    if event_name == "CLAIM":
                        worker["current_job_order"] = run_order_text
                        event_time_match = re.search(r"(?:^|;)time=([^;]+)", str(line))
                        try:
                            worker["current_job_started_at"] = float(event_time_match.group(1)) if event_time_match is not None else time.time()
                        except:
                            worker["current_job_started_at"] = time.time()
                        worker["last_progress_time"] = time.time()
                        worker["last_content_progress_seen_at"] = time.time()
                        worker["slow_warning_time"] = 0.0
                    if event_name in ["COMPLETE", "FAILED", "ERROR", "CANCELED"]:
                        terminal_orders.add(run_order_text)
                        if str(worker.get("current_job_order", "")) == run_order_text:
                            worker["current_job_order"] = ""
                            worker["current_job_started_at"] = 0.0
                worker["job_events_offset"] = int(ef.tell())
            finally:
                ef.close()
    except:
        pass

    count_file_value = 0
    count_path = str(worker.get("completed_count_path", ""))
    try:
        if count_path != "" and os.path.exists(count_path):
            cf = open(count_path, "r")
            try:
                count_file_value = max(0, int(str(cf.read()).strip() or "0"))
            finally:
                cf.close()
    except:
        count_file_value = 0

    assigned_count = len(worker.get("assigned_run_records", []))
    marker_count = max(len(terminal_orders), count_file_value)
    if assigned_count > 0:
        marker_count = min(marker_count, assigned_count)
    marker_count = max(previous_count, int(marker_count))
    worker["marker_finished_count"] = marker_count
    if marker_count > previous_count:
        worker["last_progress_time"] = time.time()
    return marker_count

def wait_for_beast_worker_pool_release():
    try:
        if BEAST_FIJI_WORKER_CONFIG is None:
            return
        release_path = str(BEAST_FIJI_WORKER_CONFIG.get("pool_release_path", ""))
        if release_path == "":
            return
        start = time.time()
        while not os.path.exists(release_path) and time.time() - start < 20.0:
            time.sleep(0.1)
    except:
        pass


def read_beast_worker_result(path):
    candidates = []
    for candidate in beast_worker_result_candidate_paths(path):
        try:
            if os.path.exists(candidate):
                candidates.append((float(os.path.getmtime(candidate)), candidate))
        except:
            pass
    candidates.sort(reverse=True)
    last_error = None
    for _mtime, candidate in candidates:
        f = None
        try:
            f = open(candidate, "rb")
            payload = pickle.load(f)
            f.close()
            if isinstance(payload, dict):
                return payload
        except Exception as e:
            last_error = e
            try:
                if f is not None:
                    f.close()
            except:
                pass
            # The newest slot may be mid-write. Try the previous valid slot.
            continue
    if last_error is not None:
        raise last_error
    raise IOError("No BEAST worker result snapshot exists for " + str(path))

def failed_run_records_for_worker(worker, reason):
    rows = []
    for order_value, item, label in worker.get("assigned_run_records", []):
        img = item.get("path", "")
        rows.append({
            "run_order_index": int(order_value), "image_path": str(img),
            "image_name": os.path.basename(str(img)), "run_label": str(label), "run_dir": "",
            "pore_csv": "", "summary_csv": "", "jsl_file": "", "particle_count": "",
            "imagej_status": "FAILED_WORKER", "jmp_status": "NOT_RUN_IMAGEJ_FAILED",
            "jmp_error": str(reason), "step_notes": ["Parallel Fiji worker failed: " + str(reason)],
            "summary_rows_for_report": []
        })
    return rows


def run_parallel_fiji_pool(output_root, input_items, sweep_combos, settings, progress_ui, errors):
    """Run BEAST Fiji work with a dynamic one-job-per-agent queue.

    v209 intentionally removes static worker chunks.  Each external Fiji process owns
    exactly one exact run.  As soon as that run publishes a terminal result, the
    process is retired and the now-free slot launches the next pending run.  This
    keeps all configured slots useful when some sweep combinations are much slower
    than others and prevents a broken Fiji JVM from contaminating later jobs.
    """
    IJ.log("BEAST worker snapshots: OneDrive-safe rotating slots enabled.")
    IJ.log("BEAST v209 dynamic disposable agents: one exact ImageJ run per Fiji process; free slots immediately pull the next queued run. A crash/stall retries only that run, never a static worker chunk.")
    try:
        if "onedrive" in str(output_root).lower():
            IJ.log("BEAST OneDrive output detected. Dynamic agents use independent per-job files so cloud-sync lag cannot block the whole pool.")
    except:
        pass

    script_path = str(settings.get("_beast_parent_script_path", "")) or resolve_beast_parent_script_path(settings, output_root)
    fiji_exe = str(settings.get("_beast_fiji_exe", "")) or find_fiji_executable()
    if script_path == "" or fiji_exe == "":
        reason = ("BEAST MODE parallel Fiji could not start. Parent script=" + str(script_path) +
                  "; Fiji executable=" + str(fiji_exe) + ".")
        IJ.log(reason)
        errors.append(reason)
        if bool(settings.get("beast_require_parallel_fiji", True)):
            raise Exception(reason)
        return None

    exact_jobs = []
    for original_item_index, item in enumerate(input_items):
        for combo_index, combo in enumerate(sweep_combos):
            overrides, label = combo
            try:
                order_base = int(item.get("_beast_order_base", original_item_index * len(sweep_combos)))
            except:
                order_base = original_item_index * len(sweep_combos)
            order_value = order_base + combo_index + 1
            item_copy = dict(item)
            item_copy["_beast_exact_overrides"] = dict(overrides)
            item_copy["_beast_exact_label"] = str(label)
            item_copy["_beast_exact_order"] = int(order_value)
            exact_jobs.append({
                "order_value": int(order_value),
                "item": item_copy,
                "label": str(label),
                "attempts": 0
            })

    total_runs = len(exact_jobs)
    configured_workers = max(1, min(16, int(settings.get("beast_fiji_parallel_instances", 4))))
    settings["beast_fiji_parallel_instances"] = configured_workers
    worker_count = min(configured_workers, max(1, total_runs))
    # v209 allows a one-run image group to use one disposable external Fiji agent.
    # This is required by strict image-by-image batch barriers.

    worker_root = os.path.join(output_root, "BEAST_Fiji_Workers")
    ensure_dir(worker_root)
    pool_release_path = os.path.join(worker_root, "POOL_RELEASE.txt")
    try:
        rf = open(pool_release_path, "w")
        try:
            rf.write("v209_dynamic_queue_released=" + str(time.time()))
        finally:
            rf.close()
    except:
        pass

    # Reliability-first supervision.  Old Quick Runs may still carry the v202/v209
    # 300/600-second limits, which were too short for real 10x pore-repair work.
    # v209 therefore enforces a safe floor while still detecting dead JVMs quickly
    # through the independent heartbeat watchdog.
    startup_timeout = max(30.0, float(settings.get("beast_fiji_worker_startup_timeout_sec", 120)))
    claim_timeout = max(30.0, float(settings.get("beast_fiji_claim_timeout_sec", 120)))
    heartbeat_timeout = max(30.0, float(settings.get("beast_fiji_heartbeat_timeout_sec", 60)))
    no_progress_timeout = max(900.0, float(settings.get("beast_fiji_no_progress_timeout_sec", 900)))
    no_progress_confirm = 45.0
    job_timeout = max(1800.0, float(settings.get("beast_fiji_job_timeout_sec", 3600)))
    worker_timeout = max(job_timeout + 600.0, float(settings.get("beast_fiji_worker_timeout_sec", 21600)))
    runtime_retries = max(0, min(10, int(settings.get("beast_fiji_runtime_retries", 4))))
    max_attempts = 1 + runtime_retries
    launch_stagger = max(0.0, float(settings.get("beast_fiji_launch_stagger_sec", 1.0)))
    fallback_enabled = bool(settings.get("beast_fiji_fallback_to_controller", True))
    checkpoint_every = max(1, int(settings.get("beast_checkpoint_every_runs", 10)))

    pending = list(exact_jobs)
    active = {}
    merged = []
    merged_events = []
    seen_orders = set()
    fallback_items = []
    failed_terminal_orders = set()
    fiji_started_count = 0
    max_fiji_active_observed = 0
    last_active_logged = None
    last_checkpoint_count = -1
    recovery_rows = []

    def safe_remove(path_value):
        try:
            if path_value not in [None, ""] and os.path.exists(path_value):
                os.remove(path_value)
        except:
            pass

    def worker_settings_for_job():
        ws = dict(settings)
        ws["_beast_fiji_worker_mode"] = True
        ws["beast_parallel_fiji_enabled"] = False
        ws["export_main_summary_xls"] = False
        # Worker processes create the report-supporting images, but the controller
        # remains the only process allowed to build Word/XLSX/JMP aggregate output.
        ws["create_word_report"] = False
        ws["launch_jmp"] = False
        ws["open_output_folder_when_done"] = False
        ws["open_word_report_when_done"] = False
        ws["fancy_progress_enabled"] = False
        ws["close_windows_when_finished"] = True
        ws["manual_measurements_enabled"] = False
        ws["manual_largest_pore_enabled"] = False
        ws["manual_selected_pore_enabled"] = False
        ws["manual_strand_measurement_enabled"] = False
        ws["auto_threshold_fit_enabled"] = False
        ws["auto_scale_show_preview"] = False
        ws["popup_warning_summary_enabled"] = False
        ws["image_capture_enabled"] = False
        ws["crop_prompt_each_image"] = False
        return ws

    def job_prefix(slot_id, job, attempt_number):
        return ("slot_" + str(int(slot_id)) + "_run_" +
                ("%06d" % int(job.get("order_value", 0))) + "_attempt_" + str(int(attempt_number)))

    def create_and_launch(slot_id, job):
        job["attempts"] = int(job.get("attempts", 0)) + 1
        attempt_number = int(job.get("attempts", 1))
        prefix = job_prefix(slot_id, job, attempt_number)
        config_path = os.path.join(worker_root, prefix + "_config.pkl")
        result_path = os.path.join(worker_root, prefix + "_result.pkl")
        wrapper_path = os.path.join(worker_root, prefix + "_launch.py")
        startup_path = os.path.join(worker_root, prefix + "_STARTED.txt")
        console_log_path = os.path.join(worker_root, prefix + "_console.log")
        launch_log_path = os.path.join(worker_root, prefix + "_launch.log")
        error_log_path = os.path.join(worker_root, prefix + "_error.log")
        claim_path = os.path.join(worker_root, prefix + "_ACTIVE_JOB.txt")
        job_events_path = os.path.join(worker_root, prefix + "_job_events.log")
        completed_count_path = os.path.join(worker_root, prefix + "_COMPLETED_COUNT.txt")
        heartbeat_path = os.path.join(worker_root, prefix + "_HEARTBEAT.txt")
        progress_path = os.path.join(worker_root, prefix + "_CONTENT_PROGRESS.txt")
        for stale in [result_path, result_path + ".slot0", result_path + ".slot1", startup_path,
                      console_log_path, launch_log_path, error_log_path, claim_path, job_events_path,
                      completed_count_path, heartbeat_path, progress_path]:
            safe_remove(stale)

        worker_cfg = {
            "settings": worker_settings_for_job(),
            "images": [],
            "output_root": output_root,
            "input_items": [dict(job.get("item", {}))],
            "sweep_combos": [({}, "__BEAST_EXACT_JOB__")],
            "run_order_values": [int(job.get("order_value", 0))],
            "result_path": result_path,
            "worker_id": int(slot_id),
            "worker_count": int(worker_count),
            "claim_path": claim_path,
            "job_events_path": job_events_path,
            "completed_count_path": completed_count_path,
            "heartbeat_path": heartbeat_path,
            "progress_path": progress_path,
            "heartbeat_interval_sec": int(settings.get("beast_fiji_heartbeat_interval_sec", 10)),
            "pool_release_path": pool_release_path
        }
        cf = open(config_path, "wb")
        try:
            pickle.dump(worker_cfg, cf, 2)
        finally:
            cf.close()
        write_beast_fiji_worker_wrapper(wrapper_path, script_path, config_path, startup_path,
                                        error_log_path, heartbeat_path,
                                        int(settings.get("beast_fiji_heartbeat_interval_sec", 10)), slot_id)
        proc = launch_beast_fiji_process(
            fiji_exe, wrapper_path, config_path, console_log_path, launch_log_path,
            str(settings.get("_beast_fiji_launch_mode", "native_run")),
            bool(settings.get("beast_show_fiji_worker_windows", True))
        )
        now_value = time.time()
        worker = {
            "slot_id": int(slot_id),
            "worker_id": int(slot_id),
            "job": job,
            "attempt": attempt_number,
            "process": proc,
            "config_path": config_path,
            "result_path": result_path,
            "wrapper_path": wrapper_path,
            "startup_path": startup_path,
            "console_log_path": console_log_path,
            "launch_log_path": launch_log_path,
            "error_log_path": error_log_path,
            "claim_path": claim_path,
            "job_events_path": job_events_path,
            "completed_count_path": completed_count_path,
            "heartbeat_path": heartbeat_path,
            "progress_path": progress_path,
            "start_time": now_value,
            "wrapper_started_time": 0.0,
            "job_started_at": 0.0,
            "started": False,
            "claimed": False,
            "heartbeat_seen": False,
            "last_heartbeat_mtime": 0.0,
            "last_heartbeat_seen_at": now_value,
            "last_content_mtime": 0.0,
            "last_content_signature": "",
            "last_content_text": "",
            "last_content_seen_at": now_value,
            "stall_suspect_at": 0.0,
            "stall_suspect_signature": "",
            "result_seen_at": 0.0,
            "result_absorbed": False
        }
        append_beast_log(beast_log_path(output_root), settings, "FIJI_POOL", "JOB_AGENT_LAUNCHED",
                         int(job.get("order_value", 0)), None, "STARTING", 0, 0, 0,
                         "slot=" + str(slot_id) + "; attempt=" + str(attempt_number) + "/" + str(max_attempts) +
                         "; label=" + str(job.get("label", "")) + "; one run per Fiji process; console=" + str(console_log_path))
        return worker

    def read_content_progress(worker):
        path_value = str(worker.get("progress_path", ""))
        try:
            if path_value == "" or not os.path.exists(path_value):
                return False
            mt = float(os.path.getmtime(path_value))
            if mt <= float(worker.get("last_content_mtime", 0.0)):
                return False
            worker["last_content_mtime"] = mt
            pf = open(path_value, "r")
            try:
                raw_text = str(pf.read()).strip()
            finally:
                pf.close()
            # Ignore the instrumentation timestamp itself.  stage/detail/seq still
            # change while algorithmic work advances.
            signature = re.sub(r";time=[^;]*", "", raw_text)
            if signature != "" and signature != str(worker.get("last_content_signature", "")):
                worker["last_content_signature"] = signature
                worker["last_content_text"] = raw_text
                worker["last_content_seen_at"] = time.time()
                worker["stall_suspect_at"] = 0.0
                worker["stall_suspect_signature"] = ""
                return True
        except:
            pass
        return False

    def read_heartbeat(worker):
        path_value = str(worker.get("heartbeat_path", ""))
        try:
            if path_value != "" and os.path.exists(path_value):
                mt = float(os.path.getmtime(path_value))
                if mt > float(worker.get("last_heartbeat_mtime", 0.0)):
                    worker["last_heartbeat_mtime"] = mt
                    worker["last_heartbeat_seen_at"] = time.time()
                    worker["heartbeat_seen"] = True
                    return True
        except:
            pass
        return False

    def absorb_result(worker):
        if not beast_worker_result_exists(worker.get("result_path", "")):
            return False
        try:
            payload = read_beast_worker_result(worker.get("result_path", ""))
        except:
            return False
        target_order = int(worker.get("job", {}).get("order_value", 0))
        found = False
        for run in list(payload.get("results", [])):
            try:
                order_value = int(run.get("run_order_index", 0))
            except:
                order_value = 0
            if order_value <= 0 or order_value in seen_orders:
                continue
            seen_orders.add(order_value)
            merged.append(run)
            found = True
            append_beast_log(beast_log_path(output_root), settings, "FIJI_POOL", "RUN_PUBLISHED",
                             order_value, run, str(run.get("imagej_status", "COMPLETED")), 0, 0, 0,
                             "slot=" + str(worker.get("slot_id")) + "; attempt=" + str(worker.get("attempt")) +
                             "; dynamic queue completed=" + str(len(seen_orders)) + "/" + str(total_runs))
        for event_text in list(payload.get("sweep_events", [])):
            if event_text not in merged_events:
                merged_events.append(event_text)
        payload_errors = list(payload.get("errors", []))
        for error_text in payload_errors:
            if error_text not in errors:
                errors.append(error_text)
        if target_order in seen_orders:
            worker["result_absorbed"] = True
            if float(worker.get("result_seen_at", 0.0)) <= 0.0:
                worker["result_seen_at"] = time.time()
            return True
        if bool(payload.get("complete", False)) and not found:
            worker["complete_without_result"] = True
        return False

    def failed_record_for_job(job, reason, status_text="FAILED_WORKER"):
        item_value = job.get("item", {})
        img = item_value.get("path", "")
        return {
            "run_order_index": int(job.get("order_value", 0)),
            "image_path": str(img),
            "image_name": os.path.basename(str(img)),
            "run_label": str(job.get("label", "")),
            "run_dir": "", "pore_csv": "", "summary_csv": "", "jsl_file": "", "particle_count": "",
            "imagej_status": str(status_text), "jmp_status": "NOT_RUN_IMAGEJ_FAILED",
            "jmp_error": str(reason), "step_notes": ["Dynamic Fiji agent failed: " + str(reason)],
            "summary_rows_for_report": []
        }

    def retire_worker(slot_id, reason, retryable):
        worker = active.get(slot_id)
        if worker is None:
            return
        try:
            destroy_process_safely(worker.get("process"), True)
        except:
            pass
        job = worker.get("job", {})
        order_value = int(job.get("order_value", 0))
        if retryable and order_value not in seen_orders and int(job.get("attempts", 0)) < max_attempts and not global_cancel_requested():
            recovery_rows.append("run=" + str(order_value) + "; attempt=" + str(job.get("attempts")) + "; reason=" + str(reason))
            pending.append(job)
            append_beast_log(beast_log_path(output_root), settings, "FIJI_POOL", "JOB_REQUEUED",
                             order_value, None, "REQUEUED", 0, 0, 0,
                             "slot=" + str(slot_id) + "; next attempt=" + str(int(job.get("attempts", 0)) + 1) +
                             "/" + str(max_attempts) + "; reason=" + str(reason))
            IJ.log("BEAST dynamic agent requeue: run " + str(order_value) + "; attempt " + str(job.get("attempts")) +
                   "/" + str(max_attempts) + "; reason=" + str(reason))
        elif order_value not in seen_orders and not global_cancel_requested():
            recovery_rows.append("run=" + str(order_value) + "; attempts_exhausted=" + str(job.get("attempts")) + "; reason=" + str(reason))
            if fallback_enabled:
                fallback_item = dict(job.get("item", {}))
                fallback_item["_beast_worker_fallback_reason"] = str(reason)
                fallback_items.append(fallback_item)
                append_beast_log(beast_log_path(output_root), settings, "FIJI_POOL", "REQUEUE_TO_CONTROLLER",
                                 order_value, None, "REQUEUED", 0, 0, 0,
                                 "Disposable-agent attempts exhausted after " + str(job.get("attempts")) + "; reason=" + str(reason))
            else:
                failed_run = failed_record_for_job(job, reason)
                merged.append(failed_run)
                seen_orders.add(order_value)
                failed_terminal_orders.add(order_value)
        try:
            del active[slot_id]
        except:
            pass

    append_beast_log(beast_log_path(output_root), settings, "PIPELINE", "DYNAMIC_AGENT_POOL_START",
                     0, None, "RUNNING", 0, 0, 0,
                     "slots=" + str(worker_count) + "; runs=" + str(total_runs) +
                     "; one run per Fiji process; retry attempts=" + str(max_attempts) +
                     "; heartbeat timeout=" + str(int(heartbeat_timeout)) +
                     " sec; content stall=" + str(int(no_progress_timeout)) + "+" + str(int(no_progress_confirm)) +
                     " sec; job timeout=" + str(int(job_timeout)) + " sec")

    while len(pending) > 0 or len(active) > 0:
        if global_cancel_requested():
            for slot_id in list(active.keys()):
                retire_worker(slot_id, "Canceled by user.", False)
            break

        # Fill every free slot from the shared queue.  This is the key v209 change:
        # work is never permanently owned by a worker/chunk.
        free_slots = []
        for slot_id in range(1, worker_count + 1):
            if slot_id not in active:
                free_slots.append(slot_id)
        while len(free_slots) > 0 and len(pending) > 0 and not global_cancel_requested():
            slot_id = free_slots.pop(0)
            job = pending.pop(0)
            if int(job.get("order_value", 0)) in seen_orders:
                continue
            try:
                active[slot_id] = create_and_launch(slot_id, job)
                if launch_stagger > 0:
                    time.sleep(launch_stagger)
            except Exception as launch_error:
                # Launch exceptions use the same bounded per-run retry queue.
                dummy_worker = {"slot_id": slot_id, "job": job, "process": None}
                active[slot_id] = dummy_worker
                retire_worker(slot_id, "Fiji process launch failed: " + str(launch_error), True)

        now_value = time.time()
        for slot_id, worker in list(active.items()):
            proc = worker.get("process")
            job = worker.get("job", {})
            order_value = int(job.get("order_value", 0))

            read_heartbeat(worker)
            read_content_progress(worker)
            absorb_result(worker)

            if worker.get("result_absorbed", False):
                # The result record is the authoritative completion event.  Do not
                # wait for a Fiji GUI process that may linger after the Jython script.
                if now_value - float(worker.get("result_seen_at", now_value)) >= 2.0:
                    retire_worker(slot_id, "result published", False)
                continue

            if not worker.get("started", False):
                if path_exists(worker.get("startup_path", "")):
                    worker["started"] = True
                    worker["wrapper_started_time"] = now_value
                    fiji_started_count += 1
                    append_beast_log(beast_log_path(output_root), settings, "FIJI_POOL", "JOB_AGENT_STARTED",
                                     order_value, None, "RUNNING", 0, 0, 0,
                                     "slot=" + str(slot_id) + "; attempt=" + str(worker.get("attempt")))
                elif proc is not None and not process_is_alive(proc):
                    retire_worker(slot_id, "Fiji exited before executing the worker wrapper.", True)
                    continue
                elif now_value - float(worker.get("start_time", now_value)) > startup_timeout:
                    retire_worker(slot_id, "Fiji did not execute its wrapper within " + str(int(startup_timeout)) + " seconds.", True)
                    continue

            if worker.get("started", False) and not worker.get("claimed", False):
                if path_exists(worker.get("claim_path", "")):
                    worker["claimed"] = True
                    worker["job_started_at"] = now_value
                    worker["last_content_seen_at"] = now_value
                    append_beast_log(beast_log_path(output_root), settings, "FIJI_POOL", "JOB_CLAIMED",
                                     order_value, None, "RUNNING", 0, 0, 0,
                                     "slot=" + str(slot_id) + "; attempt=" + str(worker.get("attempt")) + "; label=" + str(job.get("label", "")))
                elif now_value - float(worker.get("wrapper_started_time", now_value)) > claim_timeout:
                    retire_worker(slot_id, "Fiji wrapper started but did not claim its single run within " + str(int(claim_timeout)) + " seconds.", True)
                    continue

            if worker.get("claimed", False):
                heartbeat_age = now_value - float(worker.get("last_heartbeat_seen_at", worker.get("start_time", now_value)))
                if heartbeat_age > heartbeat_timeout:
                    retire_worker(slot_id, "Fiji heartbeat disappeared for " + str(int(heartbeat_age)) + " seconds.", True)
                    continue

                content_age = now_value - float(worker.get("last_content_seen_at", worker.get("job_started_at", now_value)))
                if content_age > no_progress_timeout:
                    current_signature = str(worker.get("last_content_signature", ""))
                    suspect_at = float(worker.get("stall_suspect_at", 0.0))
                    if suspect_at <= 0.0 or current_signature != str(worker.get("stall_suspect_signature", "")):
                        worker["stall_suspect_at"] = now_value
                        worker["stall_suspect_signature"] = current_signature
                        last_text = str(worker.get("last_content_text", ""))
                        if len(last_text) > 220:
                            last_text = last_text[:220] + "..."
                        append_beast_log(beast_log_path(output_root), settings, "FIJI_POOL", "JOB_STALL_SUSPECT",
                                         order_value, None, "WATCHING", 0, 0, 0,
                                         "slot=" + str(slot_id) + "; no changing work marker for " + str(int(content_age)) +
                                         " sec; confirming for " + str(int(no_progress_confirm)) + " sec; last=" + last_text)
                    elif now_value - suspect_at >= no_progress_confirm:
                        last_text = str(worker.get("last_content_text", ""))
                        if len(last_text) > 220:
                            last_text = last_text[:220] + "..."
                        retire_worker(slot_id,
                                      "Heartbeat is alive but algorithmic progress stayed unchanged for " +
                                      str(int(content_age)) + " seconds plus confirmation. Last marker: " + last_text,
                                      True)
                        continue
                else:
                    worker["stall_suspect_at"] = 0.0
                    worker["stall_suspect_signature"] = ""

                job_started_at = float(worker.get("job_started_at", 0.0))
                if job_started_at > 0.0 and now_value - job_started_at > job_timeout:
                    retire_worker(slot_id, "Single ImageJ run exceeded hard limit of " + str(int(job_timeout)) + " seconds.", True)
                    continue

            if proc is not None and not process_is_alive(proc):
                # One final snapshot read handles the normal case where SystemExit
                # closes Fiji immediately after writing the result.
                if absorb_result(worker):
                    retire_worker(slot_id, "result published at process exit", False)
                else:
                    retire_worker(slot_id, "Fiji process exited before publishing its run result.", True)
                continue

            if now_value - float(worker.get("start_time", now_value)) > worker_timeout:
                retire_worker(slot_id, "Fiji process exceeded emergency lifetime of " + str(int(worker_timeout)) + " seconds.", True)
                continue

        active_count = len(active)
        max_fiji_active_observed = max(max_fiji_active_observed, active_count)
        if last_active_logged is None or int(last_active_logged) != int(active_count):
            last_active_logged = int(active_count)
            IJ.log("BEAST active disposable Fiji agents: " + str(active_count) + "/" + str(worker_count) +
                   "; queued=" + str(len(pending)) + "; published=" + str(len(seen_orders)) + "/" + str(total_runs))
            append_beast_log(beast_log_path(output_root), settings, "FIJI_POOL", "ACTIVE_AGENT_COUNT",
                             0, None, "RUNNING", 0, 0, 0,
                             "active=" + str(active_count) + "/" + str(worker_count) +
                             "; queued=" + str(len(pending)) + "; published=" + str(len(seen_orders)) + "/" + str(total_runs))

        batch_offset = int(settings.get("_batch_live_completed_runs_before", 0)) if bool(settings.get("_batch_live_group_mode", False)) else 0
        progress_total_runs = int(settings.get("_batch_live_total_runs", total_runs)) if bool(settings.get("_batch_live_group_mode", False)) else total_runs
        progress_done_runs = batch_offset + len(seen_orders)
        update_beast_progress_popup(progress_ui, "BEAST MODE: dynamic Fiji agents",
                                    "Active " + str(active_count) + "/" + str(worker_count) +
                                    " | queued in current image " + str(len(pending)) +
                                    " | Fiji results " + str(progress_done_runs) + "/" + str(progress_total_runs),
                                    progress_done_runs, progress_total_runs, 0, 0, len(errors), active_count, worker_count)
        IJ.showStatus("BEAST dynamic Fiji: " + str(progress_done_runs) + "/" + str(progress_total_runs) +
                      " published; " + str(active_count) + "/" + str(worker_count) + " active")
        maybe_tile_visible_fiji_worker_windows(settings, False)

        if len(seen_orders) > 0 and len(seen_orders) % checkpoint_every == 0 and len(seen_orders) != last_checkpoint_count:
            merged.sort(key=lambda r: int(r.get("run_order_index", 0)))
            write_beast_checkpoint(output_root, merged, settings)
            last_checkpoint_count = len(seen_orders)

        if len(pending) > 0 or len(active) > 0:
            time.sleep(0.35)

    # If the user canceled, do not turn untouched jobs into worker failures.
    if global_cancel_requested():
        for job in pending:
            order_value = int(job.get("order_value", 0))
            if order_value in seen_orders:
                continue
            canceled = failed_record_for_job(job, "Canceled by user.", "CANCELED")
            canceled["jmp_status"] = "NOT_LAUNCHED_CANCELED"
            merged.append(canceled)
            seen_orders.add(order_value)

    # Deduplicate controller fallback jobs by exact run order.
    fallback_by_order = {}
    for item_value in fallback_items:
        try:
            fallback_by_order[int(item_value.get("_beast_exact_order", 0))] = item_value
        except:
            pass
    fallback_items = [fallback_by_order[k] for k in sorted(fallback_by_order.keys()) if k not in seen_orders]

    # v209 strict per-image batch mode resolves exhausted disposable-agent jobs
    # immediately in the controller BEFORE the next image is allowed to start.
    if bool(settings.get("_batch_live_group_mode", False)) and len(fallback_items) > 0 and not global_cancel_requested():
        immediate_fallback = list(fallback_items)
        fallback_items = []
        for fallback_item in immediate_fallback:
            order_value = int(fallback_item.get("_beast_exact_order", 0))
            if order_value in seen_orders:
                continue
            img = fallback_item.get("path", "")
            overrides = dict(fallback_item.get("_beast_exact_overrides", {}))
            label = str(fallback_item.get("_beast_exact_label", "normal"))
            run_settings = merged_settings(settings, overrides)
            for crop_key in fallback_item.get("crop_meta", {}).keys():
                run_settings[crop_key] = fallback_item.get("crop_meta", {}).get(crop_key)
            run_settings["create_word_report"] = False
            run_settings["export_main_summary_xls"] = False
            run_settings["launch_jmp"] = False
            run_settings["open_output_folder_when_done"] = False
            run_settings["open_word_report_when_done"] = False
            try:
                IJ.log("BATCH LIVE controller fallback: completing run " + str(order_value) + " before moving to the next image.")
                res = process_one_image(img, output_root, run_settings, label, order_value)
                res["run_order_index"] = order_value
                res["sweep_overrides"] = dict(overrides)
                res["imagej_status"] = "COMPLETED"
                res["jmp_status"] = "NOT_STARTED" if beast_jmp_histograms_enabled(settings) else "SKIPPED_NO_HISTOGRAMS"
                merged.append(res)
                seen_orders.add(order_value)
            except Exception as fallback_error:
                failed_job = {"order_value": order_value, "item": fallback_item, "label": label}
                failed_run = failed_record_for_job(failed_job, "Controller fallback failed: " + str(fallback_error))
                merged.append(failed_run)
                seen_orders.add(order_value)
                errors.append("Batch live controller fallback failed for run " + str(order_value) + ": " + str(fallback_error))

    merged.sort(key=lambda r: int(r.get("run_order_index", 0)))
    write_beast_checkpoint(output_root, merged, settings)

    # Reliability-first v209: JMP starts only after the dynamic Fiji queue has settled.
    # This removes cross-pool contention while Fiji is doing the expensive repair work.
    jmp_stats = {"launched": 0, "completed": 0, "failed": 0, "skipped": 0, "canceled": 0}
    if not global_cancel_requested() and len(merged) > 0:
        if beast_jmp_histograms_enabled(settings):
            try:
                append_beast_log(beast_log_path(output_root), settings, "PIPELINE", "JMP_AFTER_FIJI",
                                 0, None, "RUNNING", 0, 0, 0,
                                 "v209 reliability mode: starting bounded JMP pool only after Fiji agent queue settled")
                jmp_stats = run_beast_jmp_pool(output_root, merged, settings, progress_ui, errors)
            except Exception as jmp_pool_error:
                errors.append("BEAST JMP pool failed after Fiji queue: " + str(jmp_pool_error))
                IJ.log("BEAST JMP pool failed after Fiji queue: " + str(jmp_pool_error))
        else:
            for run in merged:
                if str(run.get("imagej_status", "")) == "COMPLETED":
                    run["jmp_status"] = "SKIPPED_NO_HISTOGRAMS"
                    run["jmp_error"] = ""
                    run["raw_all_pores_csv"] = run.get("pore_csv", "")
                    jmp_stats["skipped"] = int(jmp_stats.get("skipped", 0)) + 1
                    jmp_stats["completed"] = int(jmp_stats.get("completed", 0)) + 1

    append_beast_log(beast_log_path(output_root), settings, "PIPELINE", "DYNAMIC_AGENT_POOL_COMPLETE",
                     0, None, "CANCELED" if global_cancel_requested() else "COMPLETED", 0,
                     int(jmp_stats.get("completed", 0)), int(jmp_stats.get("failed", 0)),
                     "published=" + str(len(seen_orders)) + "/" + str(total_runs) +
                     "; controller fallback jobs=" + str(len(fallback_items)) +
                     "; agent launches started=" + str(fiji_started_count) +
                     "; max concurrent Fiji=" + str(max_fiji_active_observed) +
                     "; static chunks=REMOVED")

    try:
        recovery_summary_path = os.path.join(worker_root, "BEAST_Agent_Recovery_Summary.txt")
        recovery_file = open(recovery_summary_path, "w")
        try:
            recovery_file.write("YOURE A BETA v209 dynamic disposable-agent recovery summary\n")
            recovery_file.write("One exact run per Fiji process; shared pending queue; no static worker chunks.\n")
            recovery_file.write("Configured slots: " + str(worker_count) + "\n")
            recovery_file.write("Total exact runs: " + str(total_runs) + "\n")
            recovery_file.write("Published by agents: " + str(len(seen_orders)) + "\n")
            recovery_file.write("Controller fallback jobs: " + str(len(fallback_items)) + "\n")
            recovery_file.write("Recovery/requeue events: " + str(len(recovery_rows)) + "\n\n")
            for row_text in recovery_rows:
                recovery_file.write(str(row_text) + "\n")
        finally:
            recovery_file.close()
        IJ.log("BEAST dynamic-agent recovery summary saved: " + str(recovery_summary_path))
    except Exception as recovery_error:
        IJ.log("Could not save BEAST dynamic-agent recovery summary: " + str(recovery_error))

    return {
        "results": merged,
        "sweep_events": merged_events,
        "workers": worker_count,
        "fiji_workers_started": fiji_started_count,
        "max_fiji_active_observed": max_fiji_active_observed,
        "fallback_input_items": fallback_items,
        "jmp_streamed": True,
        "jmp_stats": jmp_stats
    }

# ======================================================
# MAIN
# ======================================================

BEAST_FIJI_WORKER_CONFIG = beast_worker_config_from_globals()
if BEAST_FIJI_WORKER_CONFIG is not None:
    settings = dict(BEAST_FIJI_WORKER_CONFIG.get("settings", {}))
    try:
        _beast_worker_id = int(BEAST_FIJI_WORKER_CONFIG.get("worker_id", 0))
        _beast_worker_count = int(BEAST_FIJI_WORKER_CONFIG.get("worker_count", settings.get("beast_fiji_parallel_instances", 1)))
        _ij_instance = IJ.getInstance()
        if _ij_instance is not None:
            _ij_instance.setTitle("Fiji BEAST Worker " + str(_beast_worker_id))
            if bool(settings.get("beast_show_fiji_worker_windows", True)):
                place_current_fiji_worker_window(_beast_worker_id, _beast_worker_count)
    except:
        pass
else:
    settings = show_settings_dialog()

if settings is None:
    IJ.log("Settings dialog canceled or validation failed; stopping cleanly.")
    raise SystemExit

reset_global_run_control()

# v209 reports-only recovery mode. Source can be either an existing failed/incomplete
# output root or an already generated YOURE A BETA DOCX used as the split/rebuild anchor.
if BEAST_FIJI_WORKER_CONFIG is None and settings.get("reports_only_recovery_mode", False):
    set_gdl_file_chooser_start_directory()
    source_mode = str(settings.get("reports_only_source_mode", "Existing failed/incomplete output folder"))
    recovery_root = ""
    source_report_path = ""

    if source_mode == "Existing generated Word report":
        recovery_od = OpenDialog("Select existing YOURE A BETA Word report (.docx)")
        recovery_name = recovery_od.getFileName()
        recovery_dir = recovery_od.getDirectory()
        if recovery_name is None or recovery_dir is None:
            IJ.error("Canceled", "No existing Word report selected.")
            raise SystemExit
        source_report_path = os.path.join(str(recovery_dir), str(recovery_name))
        if not str(source_report_path).lower().endswith(".docx"):
            IJ.error("Reports Only", "The selected file is not a .docx Word report.")
            raise SystemExit
        recovery_root = find_output_root_for_existing_report(source_report_path)
        if recovery_root == "":
            # Reports copied outside the run tree do not contain all binary/run assets.
            # Let the user point to the matching original GDL output folder.
            IJ.showMessage(
                "Locate Original Output Folder",
                "The selected DOCX is not inside its original GDL output tree.\n\n" +
                "Select the matching original output folder so the separate reports can reuse its completed run data and images."
            )
            recovery_dc = DirectoryChooser("Select matching original GDL output folder for this Word report")
            recovery_root = recovery_dc.getDirectory()
            if recovery_root is None:
                IJ.error("Canceled", "No matching output folder selected.")
                raise SystemExit
            recovery_root = str(recovery_root).rstrip("\\/")
        IJ.log("v209 REPORTS ONLY existing Word report: " + source_report_path)
        IJ.log("v209 REPORTS ONLY matched output root: " + recovery_root)
    else:
        recovery_dc = DirectoryChooser("Select existing failed/incomplete GDL output folder for REPORTS ONLY recovery")
        recovery_root = recovery_dc.getDirectory()
        if recovery_root is None:
            IJ.error("Canceled", "No recovery output folder selected.")
            raise SystemExit
        recovery_root = str(recovery_root).rstrip("\\/")
        IJ.log("v209 REPORTS ONLY recovery source: " + recovery_root)

    try:
        recovery_report_paths, recovery_summary_paths, recovery_manual_copies, recovery_results = run_reports_only_recovery(
            recovery_root, settings, source_report_path
        )
        msg = "Reports-only recovery complete.\n\nRecovered runs: " + str(len(recovery_results))
        msg += "\nWord reports created: " + str(len(recovery_report_paths))
        msg += "\nSummary files created: " + str(len(recovery_summary_paths))
        msg += "\nManual summary copies: " + str(len(recovery_manual_copies))
        if source_report_path != "":
            msg += "\n\nExisting report used as source:\n" + source_report_path
            msg += "\n\nSplit/rebuilt reports are under:\n" + os.path.join(recovery_root, "Word_Report")
        msg += "\n\nOutput root:\n" + recovery_root
        IJ.showMessage("YOURE A BETA Reports Only", msg)
    except Exception as recovery_error:
        IJ.log("Reports-only recovery failed: " + str(recovery_error))
        IJ.log(traceback.format_exc())
        try:
            create_minimal_status_report(recovery_root, settings, "REPORTS-ONLY RECOVERY FAILED", [str(recovery_error)], 0)
        except:
            pass
        IJ.error("Reports-only recovery failed", str(recovery_error))
    raise SystemExit

# Choose input(s) and output folder
capture_mode_enabled = bool(settings.get("image_capture_enabled", False))
if BEAST_FIJI_WORKER_CONFIG is not None:
    images = list(BEAST_FIJI_WORKER_CONFIG.get("images", []))
    output_root = str(BEAST_FIJI_WORKER_CONFIG.get("output_root", ""))
    ensure_dir(output_root)
elif capture_mode_enabled:

    set_gdl_file_chooser_start_directory()
    output_dc = DirectoryChooser("Select output folder for YOURE A BETA captured TIFF batch")
    output_parent = output_dc.getDirectory()

    if output_parent is None:
        IJ.error("Canceled", "No output folder selected.")
        raise SystemExit

    default_batch_name = settings.get("image_capture_batch_name", "")
    if str(default_batch_name).strip() == "":
        default_batch_name = "Captured_Batch"
    batch_safe = ask_capture_batch_name(default_batch_name)
    if batch_safe is None:
        IJ.error("Canceled", "No capture batch name entered.")
        raise SystemExit

    stamp_main = SimpleDateFormat("yyyyMMdd_HHmmss").format(Date())
    output_root = os.path.join(output_parent, "YOURE_A_BETA_" + str(batch_safe) + "_" + str(stamp_main))
    ensure_dir(output_root)

    try:
        images, yab_scale_path, yab_notes_path, yab_scale_note = run_youre_a_beta_image_capture_workflow(settings, output_root, batch_safe)
    except Exception as e_yab:
        IJ.error("YOURE A BETA Image Capture", str(e_yab))
        raise SystemExit

    IJ.log("YOURE A BETA captured TIFFs: " + str(len(images)))
    IJ.log("YOURE A BETA output root: " + str(output_root))

    capture_mode_text = str(settings.get("image_capture_mode", ""))
    if capture_mode_text.startswith("Capture scaled TIFF batch only") or capture_mode_text.startswith("Capture scaled TIFFs only"):
        msg_yab = "YOURE A BETA capture-only complete.\n\n"
        msg_yab += "Captured calibrated TIFFs: " + str(len(images)) + "\n"
        msg_yab += "Output root:\n" + str(output_root) + "\n\n"
        msg_yab += "Captured TIFFs:\n"
        for p in images[:20]:
            msg_yab += str(p) + "\n"
        if len(images) > 20:
            msg_yab += "... plus " + str(len(images) - 20) + " more\n"
        if yab_scale_path != "":
            msg_yab += "\nScale frame:\n" + str(yab_scale_path) + "\n"
        if yab_notes_path != "":
            msg_yab += "\nNotes:\n" + str(yab_notes_path) + "\n"
        IJ.log(msg_yab)
        if settings.get("open_output_folder_when_done", False):
            open_output_folder(output_root)
        IJ.showMessage("YOURE A BETA Capture Only", msg_yab)
        raise SystemExit

else:
    if settings["batch_enabled"]:
        set_gdl_file_chooser_start_directory()
        dc_in = DirectoryChooser("Select folder containing images for batch processing")
        input_folder = dc_in.getDirectory()

        if input_folder is None:
            IJ.error("Canceled", "No input folder selected.")
            raise SystemExit

        images = collect_images(input_folder, settings["include_subfolders"])

        if len(images) == 0:
            IJ.error("No Images Found", "No image files were found in:\n" + input_folder)
            raise SystemExit

    else:
        set_gdl_file_chooser_start_directory()
        od = OpenDialog("Select the image to process")
        image_path = od.getPath()

        if image_path is None:
            IJ.error("Canceled", "No image selected.")
            raise SystemExit

        images = [image_path]

    warn_if_non_tif_images(images)
    warn_if_png_images(images)

    if settings.get("set_scale_only_mode", False):
        run_set_scale_only_mode(images, settings)
        raise SystemExit

    # v89: PNG inputs are converted to calibrated TIFFs in Scaled image first,
    # then the rest of the analysis uses those TIFF files as its input list.
    images = prepare_png_inputs_for_scaled_analysis(images, settings)

    # Output folder
    set_gdl_file_chooser_start_directory()
    output_dc = DirectoryChooser("Select folder where output run folder(s) should be created")
    output_parent = output_dc.getDirectory()

    if output_parent is None:
        IJ.error("Canceled", "No output folder selected.")
        raise SystemExit

    stamp_main = SimpleDateFormat("yyyyMMdd_HHmmss").format(Date())

    if settings["batch_enabled"] or settings["sweep_enabled"]:
        # Keep root folder short so JMP/Windows can open generated CSV paths reliably.
        output_root = os.path.join(output_parent, "GDL_" + stamp_main)
    else:
        output_root = output_parent

    ensure_dir(output_root)

# v209: begin report recovery bookkeeping as soon as the output root exists, before
# crop expansion, Fiber Fixer, sweep construction, or segmentation can fail.
if BEAST_FIJI_WORKER_CONFIG is None:
    try:
        init_report_recovery_state(output_root, settings, 0)
    except Exception as early_recovery_error:
        IJ.log("Could not start early report recovery state: " + str(early_recovery_error))

# Optional crop expansion. If crop_count > 0, each selected image is converted into crop image inputs.
input_items = list(BEAST_FIJI_WORKER_CONFIG.get("input_items", [])) if BEAST_FIJI_WORKER_CONFIG is not None else build_crop_input_items(images, output_root, settings)

# Fiber Fixer v193: generate one fixed threshold-40 / 3-pixel network per
# selected image or crop BEFORE any sweep combinations are processed.
if settings.get("fiber_fixer_enabled", False):
    settings["_fiber_fixer_output_root"] = str(output_root)
    prepare_fiber_fixer_before_sweeps(input_items, output_root, settings)

# Build sweep combinations
try:
    sweep_combos = list(BEAST_FIJI_WORKER_CONFIG.get("sweep_combos", [])) if BEAST_FIJI_WORKER_CONFIG is not None else build_sweep_combinations(settings)
except Exception as e:
    IJ.error("Sweep Error", str(e))
    raise SystemExit

IJ.log("Images selected: " + str(len(images)))
IJ.log("Image/crop inputs to process: " + str(len(input_items)))
IJ.log("Sweep combinations per input: " + str(len(sweep_combos)))
IJ.log("Output root: " + output_root)
if settings.get("beast_mode_enabled", False):
    IJ.log("BEAST MODE enabled: Fiji workers=" + str(settings.get("beast_fiji_parallel_instances", 1) if settings.get("beast_parallel_fiji_enabled", False) else 1) + "; resilient fallback=" + str(settings.get("beast_fiji_fallback_to_controller", True)) + "; JMP=" + ("enabled for histograms/Word; strict workers=" + str(settings.get("beast_jmp_parallel_instances", 10)) + "; streaming=" + str(settings.get("beast_jmp_streaming_enabled", True)) if beast_jmp_histograms_enabled(settings) else "disabled; Fiji EPD to XLSX") + ".")

results = []
errors = []
launch_state = [0]
beast_mode = bool(settings.get("beast_mode_enabled", False))
beast_fiji_worker_mode = bool(settings.get("_beast_fiji_worker_mode", False))
worker_run_order_values = list(BEAST_FIJI_WORKER_CONFIG.get("run_order_values", [])) if BEAST_FIJI_WORKER_CONFIG is not None else []
beast_log_file = ""
beast_jmp_stats = {"launched": 0, "completed": 0, "failed": 0, "skipped": 0, "canceled": 0}
beast_jmp_streamed = False
sweep_until_events = []
sweep_until_skipped_runs = 0
stop_entire_batch_for_sweep_until = False
user_cancelled = False
pipeline_start_time = time.time()
settings["_pipeline_start_time"] = pipeline_start_time

total_runs = len(input_items) * len(sweep_combos)
if beast_mode and total_runs > int(settings.get("beast_max_total_runs", DEFAULTS["beast_max_total_runs"])):
    IJ.error("BEAST MODE Run Limit", "This job would create " + str(total_runs) + " runs, above the BEAST MODE maximum of " + str(settings.get("beast_max_total_runs")) + ".")
    raise SystemExit
run_counter = 0
# v209: report recovery starts BEFORE image processing. The first snapshot exists even
# if the user cancels immediately after the run begins. External BEAST workers keep
# their own result snapshots; only the controller owns the master report state.
if not beast_fiji_worker_mode:
    try:
        update_report_recovery_state(output_root, results, settings, errors, "STARTED", "Planned runs=" + str(total_runs))
    except Exception as recovery_init_error:
        IJ.log("Could not update initial report recovery state: " + str(recovery_init_error))
progress_ui = None
if beast_mode and not beast_fiji_worker_mode:
    # Resolve the parent script and verify real Fiji/JMP launches before the progress
    # dialog exists. This prevents a native file selector from being hidden behind it.
    try:
        prepare_beast_runtime_before_progress(output_root, settings)
    except Exception as beast_preflight_error:
        IJ.log("BEAST MODE preflight failed: " + str(beast_preflight_error))
        IJ.error("BEAST MODE Preflight Failed", str(beast_preflight_error) + "\n\nNo batch work was started. Check the BEAST_Preflight folder for console logs.")
        raise SystemExit
    beast_log_file = init_beast_log(output_root, settings, total_runs)
    progress_ui = create_beast_progress_popup(total_runs)
    _initial_fiji_limit = max(1, int(settings.get("beast_fiji_parallel_instances", 1))) if settings.get("beast_parallel_fiji_enabled", False) else 1
    update_beast_progress_popup(progress_ui, "BEAST MODE: preflight passed", "Preparing Fiji/JMP queues" if beast_jmp_histograms_enabled(settings) else "Preparing Fiji data-only queue; JMP disabled", 0, total_runs, 0, 0, 0, 0, _initial_fiji_limit)
elif beast_fiji_worker_mode:
    beast_log_file = os.path.join(output_root, "BEAST_Fiji_Workers", "worker_" + str(BEAST_FIJI_WORKER_CONFIG.get("worker_id", "")) + "_log.csv")
    try:
        write_csv(beast_log_file, BEAST_LOG_HEADERS, [], int(settings.get("csv_decimals", 9)))
        settings["_beast_start_time"] = time.time()
    except:
        pass
elif settings.get("fancy_progress_enabled", True):
    progress_ui = create_beast_progress_popup(total_runs, "GDL Processing + Parallel JMP Progress")
    update_beast_progress_popup(progress_ui, "NORMAL MODE: preparing", "Fiji processing; JMP pool waiting", 0, total_runs, 0, 0, 0, 1, 1)
if not beast_mode and not beast_fiji_worker_mode and settings.get("launch_jmp", True):
    beast_log_file = init_beast_log(output_root, settings, total_runs)

# Optional resilient parallel Fiji stage. The worker pool streams successful runs to JMP.
# If startup fails, or a worker misses jobs, those jobs are processed by this Fiji instance.
parallel_fiji_payload = None
beast_streaming_jmp_manager = None
controller_input_items = input_items
controller_sweep_combos = sweep_combos
batch_live_mode = batch_live_image_reports_enabled(settings) and len(input_items) > 0
if beast_mode and not beast_fiji_worker_mode and settings.get("beast_parallel_fiji_enabled", False) and int(settings.get("beast_fiji_parallel_instances", 1)) > 1:
    try:
        if batch_live_mode:
            # v209 strict batch barrier: parallelize runs INSIDE one image only.
            # The next image is not released until the current image has finished
            # Fiji + JMP + its live per-run report folder.
            results = []
            sweep_until_events = []
            aggregate_jmp_stats = {"launched": 0, "completed": 0, "failed": 0, "skipped": 0, "canceled": 0, "max_active_observed": 0}
            max_fiji_observed = 0
            total_inputs = len(input_items)
            for batch_image_zero_index in range(total_inputs):
                if global_cancel_requested():
                    user_cancelled = True
                    break
                batch_image_index = batch_image_zero_index + 1
                batch_item = dict(input_items[batch_image_zero_index])
                batch_item["_beast_order_base"] = batch_image_zero_index * len(sweep_combos)
                settings["_batch_live_group_mode"] = True
                settings["_batch_live_completed_runs_before"] = batch_image_zero_index * len(sweep_combos)
                settings["_batch_live_total_runs"] = total_runs
                IJ.log("BATCH LIVE START: Image " + str(batch_image_index) + " of " + str(total_inputs) + " - " + str(batch_item.get("path", "")))
                update_beast_progress_popup(
                    progress_ui, "BEAST MODE: batch image " + str(batch_image_index) + " of " + str(total_inputs),
                    "Finishing every sweep run for this image before the next image is released",
                    batch_image_zero_index * len(sweep_combos), total_runs,
                    int(aggregate_jmp_stats.get("completed", 0)), 0, len(errors), 0,
                    min(int(settings.get("beast_fiji_parallel_instances", 1)), max(1, len(sweep_combos)))
                )
                group_payload = run_parallel_fiji_pool(output_root, [batch_item], sweep_combos, settings, progress_ui, errors)
                if group_payload is None:
                    raise Exception("Batch live disposable-agent group returned no payload for image " + str(batch_image_index))
                group_results = list(group_payload.get("results", []))
                results.extend(group_results)
                for event_text in list(group_payload.get("sweep_events", [])):
                    if event_text not in sweep_until_events:
                        sweep_until_events.append(event_text)
                group_stats = dict(group_payload.get("jmp_stats", {}))
                for stat_key in ["launched", "completed", "failed", "skipped", "canceled"]:
                    aggregate_jmp_stats[stat_key] = int(aggregate_jmp_stats.get(stat_key, 0)) + int(group_stats.get(stat_key, 0))
                aggregate_jmp_stats["max_active_observed"] = max(int(aggregate_jmp_stats.get("max_active_observed", 0)), int(group_stats.get("max_active_observed", 0)))
                max_fiji_observed = max(max_fiji_observed, int(group_payload.get("max_fiji_active_observed", 0)))

                # Create the current image's live folder only after every run and
                # its JMP outputs have settled. This is the batch barrier.
                live_paths, live_folder = create_batch_live_reports_for_image(
                    output_root, batch_item, group_results, settings, batch_image_index, total_inputs
                )
                update_batch_image_completion_display(
                    progress_ui, batch_image_index, total_inputs,
                    os.path.basename(str(batch_item.get("path", ""))), live_folder
                )
                try:
                    results.sort(key=lambda r: int(r.get("run_order_index", 0)))
                    update_report_recovery_state(
                        output_root, results, settings, errors, "RUNNING",
                        "Image " + str(batch_image_index) + " of " + str(total_inputs) + " complete; live reports=" + str(len(live_paths))
                    )
                    write_beast_checkpoint(output_root, results, settings)
                except Exception as batch_checkpoint_error:
                    IJ.log("Batch live checkpoint warning: " + str(batch_checkpoint_error))

            settings["_batch_live_group_mode"] = False
            settings["_batch_live_completed_runs_before"] = 0
            results.sort(key=lambda r: int(r.get("run_order_index", 0)))
            beast_jmp_stats = aggregate_jmp_stats
            settings["_max_fiji_active_observed"] = max_fiji_observed
            settings["_max_jmp_active_observed"] = int(aggregate_jmp_stats.get("max_active_observed", 0))
            parallel_fiji_payload = {
                "results": list(results),
                "sweep_events": list(sweep_until_events),
                "fallback_input_items": [],
                "jmp_streamed": True,
                "jmp_stats": dict(aggregate_jmp_stats),
                "max_fiji_active_observed": max_fiji_observed
            }
            controller_input_items = []
            controller_sweep_combos = []
            beast_jmp_streamed = True
            run_counter = len(results)
        else:
            parallel_fiji_payload = run_parallel_fiji_pool(output_root, input_items, sweep_combos, settings, progress_ui, errors)
            if parallel_fiji_payload is not None:
                results = list(parallel_fiji_payload.get("results", []))
                try:
                    update_report_recovery_state(output_root, results, settings, errors, "RUNNING", "Parallel Fiji queue returned " + str(len(results)) + " records")
                except:
                    pass
                sweep_until_events = list(parallel_fiji_payload.get("sweep_events", []))
                beast_jmp_stats = dict(parallel_fiji_payload.get("jmp_stats", beast_jmp_stats))
                settings["_max_fiji_active_observed"] = int(parallel_fiji_payload.get("max_fiji_active_observed", 0))
                settings["_max_jmp_active_observed"] = int(beast_jmp_stats.get("max_active_observed", 0))
                fallback_items = list(parallel_fiji_payload.get("fallback_input_items", []))
                run_counter = len(results)
                if len(fallback_items) > 0:
                    IJ.log("BEAST resilient fallback: rerunning " + str(len(fallback_items)) + " missing worker job(s) in the current Fiji instance.")
                    controller_input_items = fallback_items
                    controller_sweep_combos = [({}, "__BEAST_EXACT_JOB__")]
                    beast_jmp_streamed = False
                else:
                    controller_input_items = []
                    controller_sweep_combos = []
                    beast_jmp_streamed = True
    except Exception as parallel_fiji_error:
        settings["_batch_live_group_mode"] = False
        settings["_batch_live_completed_runs_before"] = 0
        if settings.get("beast_fiji_fallback_to_controller", True):
            IJ.log("BEAST parallel Fiji unavailable; processing all jobs in the current Fiji instance: " + str(parallel_fiji_error))
            append_beast_log(beast_log_file, settings, "FIJI_POOL", "FALLBACK_ALL_TO_CONTROLLER", 0, None,
                             "FALLBACK", 0, beast_jmp_stats.get("completed", 0), beast_jmp_stats.get("failed", 0), str(parallel_fiji_error))
            controller_input_items = input_items
            controller_sweep_combos = sweep_combos
            parallel_fiji_payload = None
        else:
            raise

parallel_jmp_requested = ((beast_mode and beast_jmp_histograms_enabled(settings)) or ((not beast_mode) and settings.get("launch_jmp", True)))
if not beast_fiji_worker_mode and len(controller_input_items) > 0 and parallel_jmp_requested:
    try:
        if not beast_mode:
            settings["beast_jmp_parallel_instances"] = max(1, min(32, int(settings.get("max_jmp_launches", 10))))
            settings["beast_jmp_streaming_enabled"] = bool(settings.get("jmp_streaming_enabled", True))
            settings["beast_jmp_start_after_fiji_runs"] = max(1, int(settings.get("jmp_start_after_fiji_runs", 15)))
            settings["beast_force_close_jmp_after_run"] = True
            settings["beast_create_graph_word_report"] = bool(settings.get("beast_create_graph_word_report", settings.get("create_word_report", False)))
            settings["beast_word_report_mode"] = str(settings.get("word_report_mode", "Combined Word report"))
            settings["_parallel_jmp_mode_label"] = "NORMAL MODE"
            settings["_parallel_jmp_auto_exit"] = True
            settings["report_launch_all_jmp"] = False
            settings["report_wait_for_jmp"] = False
        beast_streaming_jmp_manager = BeastStreamingJmpManager(output_root, settings, progress_ui, errors, total_runs)
    except Exception as stream_manager_error:
        IJ.log("Could not initialize BEAST streaming JMP manager: " + str(stream_manager_error))
        errors.append("Streaming JMP manager initialization failed: " + str(stream_manager_error))
        beast_streaming_jmp_manager = None

if settings.get("manual_strand_measurement_enabled", False) and not beast_mode:
    settings["_manual_strand_batch_cache"] = {}
    settings["manual_strand_count"] = 1
    IJ.log("Manual strand mode: one selection per original batch image; reused across that image's runs/sweeps.")

controller_image_counter = 0
controller_image_total = len(controller_input_items)
for input_item in controller_input_items:
    controller_image_counter += 1
    controller_image_result_start = len(results)
    if global_cancel_requested():
        user_cancelled = True
        break
    if stop_entire_batch_for_sweep_until:
        break
    img = input_item.get("path", "")
    crop_meta = input_item.get("crop_meta", {})
    stop_current_input_for_sweep_until = False
    for overrides, label in controller_sweep_combos:
        # Exact jobs are used by headless workers and by resilient controller fallback.
        if str(label) == "__BEAST_EXACT_JOB__" and "_beast_exact_overrides" in input_item:
            overrides = dict(input_item.get("_beast_exact_overrides", {}))
            label = str(input_item.get("_beast_exact_label", "normal"))
        if global_cancel_requested():
            user_cancelled = True
            stop_entire_batch_for_sweep_until = True
            break
        if stop_current_input_for_sweep_until or stop_entire_batch_for_sweep_until:
            break
        run_counter = run_counter + 1
        if beast_streaming_jmp_manager is not None:
            beast_streaming_jmp_manager.tick(run_counter - 1)
        if "_beast_exact_order" in input_item:
            actual_run_order = int(input_item.get("_beast_exact_order", run_counter))
        elif beast_fiji_worker_mode:
            actual_run_order = int(worker_run_order_values[run_counter - 1] if run_counter - 1 < len(worker_run_order_values) else run_counter)
        else:
            actual_run_order = run_counter
        IJ.showStatus("ImageJ/JMP run " + str(run_counter) + " of " + str(total_runs))
        if beast_mode:
            update_beast_progress_popup(progress_ui, "BEAST MODE: ImageJ generation",
                                        os.path.basename(str(img)) + " / " + str(label),
                                        run_counter - 1, total_runs,
                                        beast_streaming_jmp_manager.done_count() if beast_streaming_jmp_manager is not None else 0,
                                        beast_streaming_jmp_manager.active_count() if beast_streaming_jmp_manager is not None else 0,
                                        len(errors), 1, 1)
            append_beast_log(beast_log_file, settings, "IMAGEJ", "START", run_counter, {"image_path": img, "run_label": label}, "RUNNING", 0, 0, 0,
                             "Active Fiji agents=1; configured limit=1")
        else:
            if beast_streaming_jmp_manager is not None:
                update_beast_progress_popup(progress_ui, "NORMAL MODE: Fiji + parallel JMP",
                                            os.path.basename(str(img)) + " / " + str(label) + " starting",
                                            run_counter - 1, total_runs, beast_streaming_jmp_manager.done_count(),
                                            beast_streaming_jmp_manager.active_count(), len(errors), 1, 1)
            else:
                update_progress_popup(progress_ui, run_counter, total_runs, os.path.basename(str(img)), "Starting")

        run_settings = merged_settings(settings, overrides)
        for crop_key in crop_meta.keys():
            run_settings[crop_key] = crop_meta[crop_key]

        # If sweep_all_listed enabled, make sure swept processing features can actually run.
        # Thresholds always apply. These lines make sweep-all useful without extra clicks.
        if settings["sweep_all_listed"]:
            if "median_radius" in overrides:
                run_settings["median_enabled"] = True
            if "bandpass_large" in overrides or "bandpass_small" in overrides:
                run_settings["bandpass_enabled"] = True
            if "clahe_blocksize" in overrides or "clahe_maximum" in overrides:
                run_settings["clahe_enabled"] = True
            for override_key in overrides.keys():
                if str(override_key).startswith("binary_"):
                    run_settings["binary_enabled"] = True if "binary_enabled" not in overrides else bool(int(overrides["binary_enabled"]))
                    break

        if beast_fiji_worker_mode:
            mark_beast_worker_job_event("CLAIM", actual_run_order, label)
            if run_counter == 1:
                wait_for_beast_worker_pool_release()
        imagej_run_start = time.time()
        imagej_start_timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
        try:
            res = process_one_image(img, output_root, run_settings, label, actual_run_order)
            res["imagej_elapsed_sec"] = time.time() - imagej_run_start
            res["imagej_start_timestamp"] = imagej_start_timestamp
            res["imagej_end_timestamp"] = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
            sweep_until_evaluation = evaluate_sweep_until_condition(res, settings)
            res["sweep_until_condition_met"] = bool(sweep_until_evaluation.get("met", False))
            res["sweep_until_actual_value"] = sweep_until_evaluation.get("actual", "")
            res["sweep_until_target_numeric"] = sweep_until_evaluation.get("target", "")
            res["sweep_until_message"] = sweep_until_evaluation.get("message", "")
            res["run_order_index"] = actual_run_order
            res["sweep_overrides"] = dict(overrides)
            res["imagej_status"] = "COMPLETED"
            if beast_mode and not beast_jmp_histograms_enabled(settings):
                res["jmp_status"] = "SKIPPED_NO_HISTOGRAMS"
                res["jmp_error"] = ""
                res["raw_all_pores_csv"] = res.get("pore_csv", "")
            else:
                res["jmp_status"] = "NOT_STARTED"
            results.append(res)
            if not beast_fiji_worker_mode:
                try:
                    update_report_recovery_state(output_root, results, settings, errors, "RUNNING", "Completed run " + str(actual_run_order))
                except:
                    pass
            if beast_streaming_jmp_manager is not None:
                beast_streaming_jmp_manager.publish(res, run_counter)
            if beast_fiji_worker_mode:
                mark_beast_worker_job_event("COMPLETE", actual_run_order, label)
                publish_beast_worker_snapshot(results, errors, sweep_until_events, False)
            if beast_mode:
                update_beast_progress_popup(progress_ui, "BEAST MODE: ImageJ generation",
                                            os.path.basename(str(img)) + " / " + str(label) + " completed",
                                            run_counter, total_runs,
                                            beast_streaming_jmp_manager.done_count() if beast_streaming_jmp_manager is not None else 0,
                                            beast_streaming_jmp_manager.active_count() if beast_streaming_jmp_manager is not None else 0,
                                            len(errors), 1, 1)
                append_beast_log(beast_log_file, settings, "IMAGEJ", "COMPLETE", run_counter, res, "COMPLETED", 0, 0, 0,
                                 "Particle count=" + str(res.get("particle_count", "")))
                checkpoint_every = max(1, int(settings.get("beast_checkpoint_every_runs", 10)))
                if not beast_fiji_worker_mode and run_counter % checkpoint_every == 0:
                    write_beast_checkpoint(output_root, results, settings)
            else:
                if beast_streaming_jmp_manager is not None:
                    update_beast_progress_popup(progress_ui, "NORMAL MODE: Fiji + parallel JMP",
                                                os.path.basename(str(img)) + " / " + str(label) + " completed",
                                                run_counter, total_runs, beast_streaming_jmp_manager.done_count(),
                                                beast_streaming_jmp_manager.active_count(), len(errors), 1, 1)
                else:
                    update_progress_popup(progress_ui, run_counter, total_runs, os.path.basename(str(img)), "Completed")
            if sweep_until_evaluation.get("enabled", False) and sweep_until_evaluation.get("available", False):
                IJ.log("Sweep Until check: " + str(sweep_until_evaluation.get("message", "")))
            if sweep_until_evaluation.get("met", False):
                event_text = (
                    str(os.path.basename(str(img))) + " / " + str(label) + ": " +
                    str(sweep_until_evaluation.get("message", ""))
                )
                sweep_until_events.append(event_text)
                IJ.log("Sweep Until target reached. " + event_text)
                scope = str(settings.get("sweep_until_stop_scope", "Current image/crop only"))
                if scope == "Entire batch":
                    stop_entire_batch_for_sweep_until = True
                else:
                    stop_current_input_for_sweep_until = True
            # If the Word report is set to launch all JMP scripts, wait until all ImageJ runs are done
            # so each JMP script launches only once and the report can gather all outputs.
            if global_cancel_requested():
                user_cancelled = True
                stop_entire_batch_for_sweep_until = True
            if not global_cancel_requested() and not beast_mode and beast_streaming_jmp_manager is None and not (settings.get("create_word_report", False) and settings.get("report_launch_all_jmp", True)):
                launch_jmp_script(res["jsl_file"], settings, launch_state)
        except Exception as e2:
            was_user_cancel = global_cancel_requested()
            if was_user_cancel:
                user_cancelled = True
                stop_entire_batch_for_sweep_until = True
                msg = "Canceled processing " + str(img) + " / " + str(label) + ": " + str(e2)
            else:
                msg = "Error processing " + str(img) + " / " + str(label) + ": " + str(e2)
                errors.append(msg)
            IJ.log(msg)
            try:
                run_traceback_text = traceback.format_exc()
                if run_traceback_text not in [None, "", "None\n"]:
                    IJ.log("Full processing traceback follows:")
                    IJ.log(run_traceback_text)
            except:
                pass
            if beast_fiji_worker_mode:
                mark_beast_worker_job_event("FAILED", actual_run_order, label)
            if beast_mode:
                failed_run = {
                    "run_order_index": actual_run_order,
                    "image_path": str(img),
                    "image_name": os.path.basename(str(img)),
                    "run_label": str(label),
                    "run_dir": "",
                    "pore_csv": "",
                    "summary_csv": "",
                    "jsl_file": "",
                    "particle_count": "",
                    "sweep_overrides": dict(overrides),
                    "sample_size_text": "",
                    "imagej_elapsed_sec": time.time() - imagej_run_start,
                    "imagej_start_timestamp": imagej_start_timestamp,
                    "imagej_end_timestamp": SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date()),
                    "imagej_status": "CANCELED" if was_user_cancel else "FAILED",
                    "jmp_status": "NOT_RUN_CANCELED" if was_user_cancel else "NOT_RUN_IMAGEJ_FAILED",
                    "jmp_error": str(e2),
                    "step_notes": [("Canceled by user: " if was_user_cancel else "ImageJ processing failed: ") + str(e2)],
                    "summary_rows_for_report": []
                }
                results.append(failed_run)
                if not beast_fiji_worker_mode:
                    try:
                        update_report_recovery_state(output_root, results, settings, errors, "CANCELED" if was_user_cancel else "RUNNING_WITH_ERRORS", "Run " + str(actual_run_order) + " did not complete")
                    except:
                        pass
                if beast_streaming_jmp_manager is not None:
                    beast_streaming_jmp_manager.publish(failed_run, run_counter)
                if beast_fiji_worker_mode:
                    publish_beast_worker_snapshot(results, errors, sweep_until_events, False)
                event_name = "CANCELED" if was_user_cancel else "ERROR"
                event_status = "CANCELED" if was_user_cancel else "FAILED"
                append_beast_log(beast_log_file, settings, "IMAGEJ", event_name, run_counter,
                                 failed_run, event_status, 0, 0, 0, str(e2))
                update_beast_progress_popup(progress_ui,
                                            "BEAST MODE: cancel requested" if was_user_cancel else "BEAST MODE: ImageJ generation",
                                            os.path.basename(str(img)) + " / " + str(label) + (" CANCELED" if was_user_cancel else " ERROR"),
                                            run_counter, total_runs,
                                            beast_streaming_jmp_manager.done_count() if beast_streaming_jmp_manager is not None else 0,
                                            beast_streaming_jmp_manager.active_count() if beast_streaming_jmp_manager is not None else 0,
                                            len(errors), 1, 1)
                checkpoint_every = max(1, int(settings.get("beast_checkpoint_every_runs", 10)))
                if not beast_fiji_worker_mode and (run_counter % checkpoint_every == 0 or was_user_cancel):
                    write_beast_checkpoint(output_root, results, settings)
                if was_user_cancel or not settings.get("beast_continue_on_imagej_error", True):
                    stop_entire_batch_for_sweep_until = True
            else:
                update_progress_popup(progress_ui, run_counter, total_runs, os.path.basename(str(img)),
                                      "Canceled" if was_user_cancel else "Error")

    # v209 normal-mode / controller-fallback batch barrier. The outer loop already
    # completes every sweep for one image before reaching this point, so live
    # reports are finalized here before the next image starts.
    if batch_live_image_reports_enabled(settings) and not beast_fiji_worker_mode:
        try:
            image_group_results = list(results[controller_image_result_start:])
            live_paths, live_folder = create_batch_live_reports_for_image(
                output_root, input_item, image_group_results, settings, controller_image_counter, controller_image_total
            )
            update_batch_image_completion_display(
                progress_ui, controller_image_counter, controller_image_total,
                os.path.basename(str(input_item.get("path", ""))), live_folder
            )
        except Exception as live_controller_report_error:
            IJ.log("Batch live report finalization failed for image " + str(controller_image_counter) + ": " + str(live_controller_report_error))
            errors.append("Batch live report finalization failed for image " + str(controller_image_counter) + ": " + str(live_controller_report_error))

if global_cancel_requested():
    user_cancelled = True
sweep_until_skipped_runs = max(0, int(total_runs) - int(run_counter))
if not beast_mode and beast_streaming_jmp_manager is None:
    close_progress_popup(progress_ui)
elif beast_mode and not beast_fiji_worker_mode:
    write_beast_checkpoint(output_root, results, settings)

if beast_fiji_worker_mode:
    try:
        worker_result_path = str(BEAST_FIJI_WORKER_CONFIG.get("result_path", ""))
        write_beast_worker_result(worker_result_path, results, errors, sweep_until_events, True)
        IJ.log("BEAST Fiji worker completed: " + str(worker_result_path))
    except Exception as e_worker_result:
        IJ.log("Could not write BEAST Fiji worker result: " + str(e_worker_result))
    try:
        close_progress_popup(progress_ui)
    except:
        pass
    try:
        worker_log_name = "Fiji_Log_worker_" + str(BEAST_FIJI_WORKER_CONFIG.get("worker_id", "unknown")) + ".txt"
        save_fiji_log_file(output_root, errors, "BEAST Fiji worker final", worker_log_name, settings)
    except:
        pass
    raise SystemExit

# Finish/drain the bounded JMP queue after the single Fiji controller is done.
if beast_streaming_jmp_manager is not None:
    try:
        _fallback_jmp_stats = beast_streaming_jmp_manager.finish(run_counter)
        for _stat_key in ["launched", "completed", "failed", "skipped", "canceled"]:
            beast_jmp_stats[_stat_key] = int(beast_jmp_stats.get(_stat_key, 0)) + int(_fallback_jmp_stats.get(_stat_key, 0))
        beast_jmp_stats["max_active_observed"] = max(int(beast_jmp_stats.get("max_active_observed", 0)), int(_fallback_jmp_stats.get("max_active_observed", 0)))
        settings["_max_jmp_active_observed"] = int(beast_jmp_stats.get("max_active_observed", 0))
        beast_jmp_streamed = True
    except Exception as stream_finish_error:
        IJ.log("BEAST streaming JMP finish error: " + str(stream_finish_error))
        errors.append("Streaming JMP finish error: " + str(stream_finish_error))

# Restore deterministic order after any controller fallback jobs.
try:
    results.sort(key=lambda r: int(r.get("run_order_index", 0)))
except:
    pass

# Write manifest and helper BAT file
manifest_path = ""
bat_path = ""
try:
    manifest_path, bat_path = write_master_files(output_root, results, settings)
except Exception as e3:
    IJ.log("Could not write master manifest / BAT file: " + str(e3))

# BEAST MODE JMP phase: bounded parallel processes, each tied to one run and completion marker.
if beast_mode and beast_jmp_histograms_enabled(settings) and len(results) > 0 and not user_cancelled and not beast_jmp_streamed:
    beast_jmp_stats = run_beast_jmp_pool(output_root, results, settings, progress_ui, errors)
    if global_cancel_requested():
        user_cancelled = True
    try:
        manifest_path, bat_path = write_master_files(output_root, results, settings)
    except Exception as e_manifest_beast:
        IJ.log("Could not refresh manifest after BEAST JMP phase: " + str(e_manifest_beast))

elif beast_mode and beast_jmp_histograms_enabled(settings) and len(results) > 0 and user_cancelled:
    for cancel_run in results:
        if str(cancel_run.get("jmp_status", "NOT_STARTED")) in ["", "NOT_STARTED"]:
            cancel_run["jmp_status"] = "NOT_LAUNCHED_CANCELED"
            cancel_run["jmp_error"] = "Canceled by user before the JMP phase began."
    beast_jmp_stats["canceled"] = len(results)
    try:
        append_beast_log(beast_log_file, settings, "SYSTEM", "USER_CANCEL", 0, None, "CANCELED", 0, 0, 0,
                         str(RUN_CONTROL.get("cancel_reason", "Canceled by user.")))
        write_beast_checkpoint(output_root, results, settings)
    except:
        pass

# v209: CANCEL EVERYTHING stops image/JMP processing, but it must NOT poison the
# final report/export phase. Preserve user_cancelled=True for status/logging, then
# clear only the low-level cancel latch after workers have been drained/terminated.
if user_cancelled and global_cancel_requested():
    try:
        settings["_processing_cancel_reason"] = str(RUN_CONTROL.get("cancel_reason", "User cancel"))
        RUN_CONTROL["cancel_requested"] = False
        IJ.log("Processing cancel acknowledged. Entering protected final-report phase; no new Fiji analysis will start.")
    except Exception as final_phase_cancel_error:
        IJ.log("Could not clear cancel latch for final-report phase: " + str(final_phase_cancel_error))

# v209: Word-report grouping has ONE authority in Normal and BEAST: word_report_mode.
# The legacy beast_word_report_mode key mirrors it but can never override it.
if beast_mode:
    beast_report_mode = normalize_word_report_mode(settings.get("word_report_mode", "Combined Word report"))
    settings["word_report_mode"] = beast_report_mode
    settings["beast_word_report_mode"] = beast_report_mode
    settings["create_word_report"] = beast_report_mode != "No Word reports"
    if settings["create_word_report"] and ("combined" in beast_report_mode.lower() or beast_report_mode == "Combined Word report"):
        settings["report_sweep_comparison_enabled"] = True

# The report is built after JMP outputs exist so it can include the final JMP summary CSV,
# original/processed images, pore maps, settings tables, and lossless PNG histograms.
report_path = ""
report_paths = []
summary_xls_paths = []
report_jmp_launches = 0

# v199: recompute Word-report intent from the six-mode dropdown immediately before
# report creation. Excel/main-summary checkboxes are deliberately excluded here.
word_report_plan = word_report_mode_output_plan(settings)
settings["word_report_mode"] = word_report_plan["mode"]
settings["create_word_report"] = bool(word_report_plan["requested"])
effective_word_report_creation = bool(word_report_plan["requested"] or settings.get("threshold_selection_reports_enabled", False))
IJ.log(
    "Final report plan: mode=" + str(word_report_plan["mode"]) +
    "; combined=" + str(bool(word_report_plan["include_combined"])) +
    "; by-image=" + str(bool(word_report_plan["include_by_image"])) +
    "; separate=" + str(bool(word_report_plan["include_separate"])) +
    "; batch summary mirror=" + str(bool(settings.get("batch_sweep_export_all_summaries_to_all_reports", False))) +
    "; Excel summary export=" + str(bool(settings.get("export_main_summary_xls", False)))
)
# v209: build one authoritative final ledger from controller records + persistent
# disposable-agent/recovery snapshots before ANY final report or summary export.
_final_report_results = build_final_report_ledger(output_root, results, settings)

# v209 live-batch final organization: live per-run reports already exist inside
# image folders. The final combined report (when selected) and summary collection
# are written only after every image barrier has completed.
if batch_live_image_reports_enabled(settings):
    try:
        _batch_combined_dir, _batch_summaries_dir = prepare_batch_final_report_folders(output_root, settings)
        if bool(word_report_plan.get("include_combined", False)) and _batch_combined_dir != "":
            settings["_report_output_dir_override"] = _batch_combined_dir
        IJ.log("Batch live final folders: combined=" + str(_batch_combined_dir) + "; summaries=" + str(_batch_summaries_dir))
    except Exception as batch_final_folder_error:
        IJ.log("Could not prepare batch final report folders: " + str(batch_final_folder_error))

if effective_word_report_creation and len(_final_report_results) > 0:
    try:
        _report_results_now = list(_final_report_results)
        if (not user_cancelled) and settings.get("report_launch_all_jmp", True) and beast_streaming_jmp_manager is None:
            report_jmp_launches = launch_all_jmp_scripts_for_report(_report_results_now, settings)
            IJ.log("JMP scripts launched for report: " + str(report_jmp_launches))

        if (not user_cancelled) and settings.get("report_wait_for_jmp", True):
            wait_for_jmp_outputs_for_report(_report_results_now, settings)

        report_paths = create_word_reports_by_mode(output_root, _report_results_now, settings)
        if len(report_paths) > 0:
            report_path = report_paths[0]
            for rp in report_paths:
                IJ.log("Word report created: " + rp)
        if bool(word_report_plan.get("include_separate", False)):
            IJ.log(
                "Completely individual report verification: expected=" +
                str(settings.get("_completely_individual_expected_count", len(_final_report_results))) +
                "; created=" + str(settings.get("_completely_individual_created_count", 0)) +
                "; failures=" + str(len(settings.get("_completely_individual_failures", []))) +
                "; summaries XLS=" + str(bool(settings.get("export_main_summary_xls", False))) +
                "; batch summary mirror=" + str(bool(settings.get("batch_sweep_export_all_summaries_to_all_reports", False)))
            )
    except Exception as e_report:
        msg_report = "Could not create Word report: " + str(e_report)
        IJ.log(msg_report)
        IJ.log(traceback.format_exc())
        errors.append(msg_report + " | " + traceback.format_exc())

if len(report_paths) > 0:
    settings["_final_report_phase_completed"] = True

# v209 ALWAYS-REPORT invariant. If the selected full-report pipeline created no
# DOCX (cancel, failure, No Word reports, or an exporter error), finish a recovery
# report from every completed run available so far.
if len(report_paths) == 0 and settings.get("always_finalize_partial_report", True):
    try:
        report_paths = finalize_partial_reports(
            output_root, _final_report_results, settings, errors,
            "CANCELED BY USER" if user_cancelled else "AUTOMATIC FINAL REPORT", True
        )
        if len(report_paths) > 0:
            report_path = report_paths[0]
            for _rp in report_paths:
                IJ.log("Automatic partial/recovery Word report created: " + str(_rp))
    except Exception as auto_report_error:
        IJ.log("Automatic partial/recovery report failed: " + str(auto_report_error))
        errors.append("Automatic partial/recovery report failed: " + str(auto_report_error))

settings["_elapsed_before_export_sec"] = time.time() - float(settings.get("_pipeline_start_time", time.time()))
if settings.get("export_main_summary_xls", False) and len(_final_report_results) > 0:
    try:
        if beast_mode:
            settings["_beast_progress_ui"] = progress_ui
            update_beast_progress_popup(progress_ui, "BEAST MODE: building three-sheet XLSX",
                                        "Preparing All Pore Data, Run Overview, and Revised Summary",
                                        total_runs, total_runs, total_runs, 0, len(errors), 0, 1)
            append_beast_log(beast_log_file, settings, "EXPORT", "WORKBOOK_START", 0, None, "RUNNING", 0,
                             beast_jmp_stats.get("completed", 0), beast_jmp_stats.get("failed", 0),
                             "Creating cleaned All Pore Data, Run Overview, and Revised Summary sheets")
        summary_xls_paths = export_main_summary_xls_for_reports(output_root, report_paths, _final_report_results, settings)
        if len(summary_xls_paths) == 0:
            msg_xls = "Excel workbook export was requested, but no workbook could be created."
            IJ.log(msg_xls)
            errors.append(msg_xls)
    except Exception as e_xls:
        msg_xls = "Could not create Excel workbook: " + str(e_xls)
        IJ.log(msg_xls)
        errors.append(msg_xls)

manual_summary_copy_paths = []
try:
    manual_summary_copy_paths = manual_summary_selection_dialog(output_root, summary_xls_paths, settings)
except Exception as manual_summary_error:
    IJ.log("Manual summary selection failed: " + str(manual_summary_error))
    errors.append("Manual summary selection failed: " + str(manual_summary_error))

try:
    update_report_recovery_state(output_root, _final_report_results, settings, errors, "CANCELED" if user_cancelled else "COMPLETED", "Final reports=" + str(len(report_paths)) + "; summaries=" + str(len(summary_xls_paths)))
except:
    pass

lossy_generated_cleanup_stats = {"enabled": False, "jpeg_created": 0, "lossless_removed": 0, "failed": 0}
if len(results) > 0 and no_lossless_generated_images_enabled(settings):
    try:
        lossy_generated_cleanup_stats = apply_generated_image_storage_policy(results, settings)
        # Refresh manifest/checkpoint path records after PNG/TIFF -> JPEG replacement.
        try:
            manifest_path, bat_path = write_master_files(output_root, results, settings)
        except Exception as e_manifest_lossy:
            IJ.log("Could not refresh manifest after lossy generated-image cleanup: " + str(e_manifest_lossy))
    except Exception as e_lossy_cleanup:
        msg_lossy_cleanup = "Could not apply generated-image space-saving cleanup: " + str(e_lossy_cleanup)
        IJ.log(msg_lossy_cleanup)
        errors.append(msg_lossy_cleanup)

if beast_mode:
    try:
        if len(summary_xls_paths) > 0:
            append_beast_log(beast_log_file, settings, "EXPORT", "WORKBOOK_CREATED", 0, None, "COMPLETED", 0,
                             beast_jmp_stats.get("completed", 0), beast_jmp_stats.get("failed", 0),
                             " | ".join([str(p) for p in summary_xls_paths]))
        write_beast_checkpoint(output_root, results, settings)
        final_beast_status = "CANCELED" if user_cancelled else "COMPLETED"
        append_beast_log(beast_log_file, settings, "SYSTEM", "FINISH", 0, None, final_beast_status, 0,
                         beast_jmp_stats.get("completed", 0), beast_jmp_stats.get("failed", 0),
                         "Run records=" + str(len(results)) + "; total errors=" + str(len(errors)) + "; canceled=" + str(user_cancelled) +
                         "; total elapsed=" + format_elapsed_seconds(time.time() - float(settings.get("_pipeline_start_time", time.time()))))
    except Exception as e_beast_finish:
        IJ.log("Could not finalize BEAST MODE log/checkpoint: " + str(e_beast_finish))
    close_progress_popup(progress_ui)

if not beast_mode:
    close_progress_popup(progress_ui)
if not user_cancelled:
    show_warning_summary_popup(results, errors, settings)

IJ.showStatus("Canceled" if user_cancelled else "Done")

fiji_log_path = save_fiji_log_file(output_root, errors, "Final export/report stage", "Fiji_Log.txt", settings)

summary_msg = ("Processing canceled by user. Partial results and checkpoints were retained.\nReason: " + str(RUN_CONTROL.get("cancel_reason", "User cancel")) + "\n\n" if user_cancelled else "ImageJ processing complete.\n\n")
summary_msg = summary_msg + "Images selected: " + str(len(images)) + "\n"
summary_msg = summary_msg + "Image/crop inputs processed: " + str(len(input_items)) + "\n"
summary_msg = summary_msg + "Sweep combinations per input: " + str(len(sweep_combos)) + "\n"
successful_imagej_runs = 0
for summary_run in results:
    if str(summary_run.get("imagej_status", "COMPLETED")) == "COMPLETED":
        successful_imagej_runs += 1
summary_msg = summary_msg + "Successful ImageJ runs: " + str(successful_imagej_runs) + "\n"
summary_msg = summary_msg + "Attempted run records: " + str(len(results)) + "\n"
summary_msg = summary_msg + "Errors: " + str(len(errors)) + "\n"
summary_msg = summary_msg + "Sweep Until targets reached: " + str(len(sweep_until_events)) + "\n"
summary_msg = summary_msg + "Sweep runs skipped after early stop: " + str(sweep_until_skipped_runs) + "\n"
total_elapsed_sec = time.time() - float(settings.get("_pipeline_start_time", pipeline_start_time))
summary_msg = summary_msg + "Total elapsed time: " + format_elapsed_seconds(total_elapsed_sec) + "\n"
summary_msg = summary_msg + "Total elapsed seconds: " + str(round(total_elapsed_sec, 2)) + "\n"
if successful_imagej_runs > 0:
    summary_msg = summary_msg + "Average wall-clock seconds per successful run: " + str(round(total_elapsed_sec / float(successful_imagej_runs), 2)) + "\n"
summary_msg = summary_msg + "JMP scripts auto-launched during ImageJ processing: " + str(launch_state[0]) + "\n"
summary_msg = summary_msg + "JMP scripts launched for report: " + str(report_jmp_launches) + "\n"
summary_msg = summary_msg + "Lossless report images disabled: " + str(no_lossless_report_images_enabled(settings)) + "\n"
summary_msg = summary_msg + "Lossless generated images retained: " + str(not no_lossless_generated_images_enabled(settings)) + "\n"
if lossy_generated_cleanup_stats.get("enabled", False):
    summary_msg = summary_msg + "Generated JPEG replacements created: " + str(lossy_generated_cleanup_stats.get("jpeg_created", 0)) + "\n"
    summary_msg = summary_msg + "Generated PNG/TIFF files removed: " + str(lossy_generated_cleanup_stats.get("lossless_removed", 0)) + "\n"
    summary_msg = summary_msg + "Generated-image conversion failures: " + str(lossy_generated_cleanup_stats.get("failed", 0)) + "\n"
if beast_mode:
    summary_msg = summary_msg + "Maximum active Fiji agents observed: " + str(settings.get("_max_fiji_active_observed", 0)) + " / " + str(settings.get("beast_fiji_parallel_instances", 1) if settings.get("beast_parallel_fiji_enabled", False) else 1) + "\n"
    if beast_jmp_histograms_enabled(settings):
        summary_msg = summary_msg + "BEAST JMP processes launched: " + str(beast_jmp_stats.get("launched", 0)) + "\n"
        summary_msg = summary_msg + "BEAST JMP runs completed/skipped: " + str(beast_jmp_stats.get("completed", 0)) + "\n"
        summary_msg = summary_msg + "BEAST JMP failures: " + str(beast_jmp_stats.get("failed", 0)) + "\n"
        summary_msg = summary_msg + "BEAST JMP canceled/not launched: " + str(beast_jmp_stats.get("canceled", 0)) + "\n"
    else:
        summary_msg = summary_msg + "BEAST JMP: skipped because histograms/graphs were disabled\n"
        summary_msg = summary_msg + "EPD source: calculated directly by Fiji and appended to All Pore Data\n"
elif beast_streaming_jmp_manager is not None:
    summary_msg = summary_msg + "Maximum active JMP instances observed: " + str(settings.get("_max_jmp_active_observed", 0)) + "\n"
    summary_msg = summary_msg + "Parallel JMP instances configured: " + str(settings.get("max_jmp_launches", 10)) + "\n"
    summary_msg = summary_msg + "JMP start threshold: " + str(settings.get("jmp_start_after_fiji_runs", 15)) + " completed Fiji runs\n"
    summary_msg = summary_msg + "Parallel JMP processes launched: " + str(beast_jmp_stats.get("launched", 0)) + "\n"
    summary_msg = summary_msg + "Parallel JMP completed/skipped: " + str(beast_jmp_stats.get("completed", 0)) + "\n"
    summary_msg = summary_msg + "Parallel JMP failures: " + str(beast_jmp_stats.get("failed", 0)) + "\n"
if settings["close_windows_when_finished"]:
    summary_msg = summary_msg + "Close-all on finish: enabled for ImageJ/Fiji windows\n"
else:
    summary_msg = summary_msg + "Close-all on finish: disabled\n"
summary_msg = summary_msg + "Binary cleanup: " + ("enabled" if settings.get("binary_enabled", False) else "disabled") + "\n"
summary_msg = summary_msg + "Binary order: " + str(settings.get("binary_operation_order", "")) + "\n"
summary_msg = summary_msg + "Minimum/Maximum grayscale filter radius (px): " + str(settings.get("binary_minimum_radius", 0.0)) + " / " + str(settings.get("binary_maximum_radius", 0.0)) + "\n"
summary_msg = summary_msg + "\n"
summary_msg = summary_msg + "Output root:\n" + output_root + "\n\n"
if fiji_log_path != "":
    summary_msg = summary_msg + "Fiji/ImageJ saved log:\n" + fiji_log_path + "\n\n"

if manifest_path != "":
    summary_msg = summary_msg + "Manifest:\n" + manifest_path + "\n\n"
if beast_mode:
    summary_msg = summary_msg + "BEAST MODE detailed log:\n" + beast_log_path(output_root) + "\n\n"
    summary_msg = summary_msg + "BEAST MODE checkpoint:\n" + beast_checkpoint_path(output_root) + "\n\n"
if bat_path != "":
    summary_msg = summary_msg + "Run all JMP scripts BAT:\n" + bat_path + "\n\n"
if len(report_paths) > 0:
    summary_msg = summary_msg + "Word report(s):\n"
    for rp in report_paths:
        summary_msg = summary_msg + rp + "\n"
    if settings.get("open_word_report_when_done", False):
        summary_msg = summary_msg + "Open Word DOCX on finish: enabled\n"
    else:
        summary_msg = summary_msg + "Open Word DOCX on finish: disabled\n"
    summary_msg = summary_msg + "\n"

if len(summary_xls_paths) > 0:
    summary_msg = summary_msg + "Excel workbook file(s):\n"
    for xls_path in summary_xls_paths:
        summary_msg = summary_msg + xls_path + "\n"
    summary_msg = summary_msg + "\n"

if len(sweep_until_events) > 0:
    summary_msg = summary_msg + "Sweep Until stop event(s):\n"
    for sweep_event in sweep_until_events:
        summary_msg = summary_msg + "- " + str(sweep_event) + "\n"
    summary_msg = summary_msg + "\n"

if len(errors) > 0:
    summary_msg = summary_msg + "Check the ImageJ log for error details."

IJ.log("ImageJ/JMP canceled." if user_cancelled else "ImageJ/JMP complete.")
IJ.log("Output root: " + output_root)
_successful_run_count = 0
for _success_run in results:
    try:
        if str(_success_run.get("imagej_status", "COMPLETED")) == "COMPLETED":
            _successful_run_count += 1
    except:
        pass
IJ.log("Successful runs: " + str(_successful_run_count))
IJ.log("Errors: " + str(len(errors)))
if len(report_paths) > 0:
    for rp in report_paths:
        IJ.log("Word report: " + rp)
if len(summary_xls_paths) > 0:
    for xls_path in summary_xls_paths:
        IJ.log("Excel workbook: " + xls_path)

if len(errors) > 0:
    for er in errors:
        IJ.log(er)

fiji_log_path = save_fiji_log_file(output_root, errors, "Final completed log refresh", "Fiji_Log.txt", settings)

# v193 completion behavior: open the completed output folder rather than Word.
# Word reports are still created when enabled, but are not auto-opened.
if not beast_fiji_worker_mode:
    open_output_folder(output_root)

if settings["close_windows_when_finished"]:
    close_imagej_windows_when_finished()

IJ.showMessage("Done", summary_msg)
