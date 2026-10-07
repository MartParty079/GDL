# -*- coding: utf-8 -*-
# MODULE 07: Per-run engine, CSV exports, logs, and image handling

# Cached per Fiji process so repeated sweeps of the same source image do not
# reconvert and remeasure the untouched image for every run.
ORIGINAL_8BIT_MEAN_CACHE = {}


def resolve_og_image_name(image_path, image_name, settings):
    crop_source_name = str(settings.get("crop_source_name", "")).strip()
    if crop_source_name != "":
        return crop_source_name
    crop_source_image = str(settings.get("crop_source_image", "")).strip()
    if crop_source_image != "":
        try:
            return os.path.basename(crop_source_image)
        except:
            pass
    return str(image_name if image_name not in [None, ""] else os.path.basename(str(image_path)))


def measure_original_8bit_mean_gray(imp_original, image_path):
    """Return the full-image mean after only an ImageJ 8-bit conversion (0-255)."""
    cache_key = str(image_path)
    try:
        cache_key = os.path.normcase(os.path.abspath(str(image_path)))
        if os.path.exists(str(image_path)):
            cache_key += "|" + str(os.path.getmtime(str(image_path))) + "|" + str(os.path.getsize(str(image_path)))
    except:
        pass
    if cache_key in ORIGINAL_8BIT_MEAN_CACHE:
        return ORIGINAL_8BIT_MEAN_CACHE.get(cache_key, "")

    measure_imp = None
    try:
        measure_imp = Duplicator().run(imp_original)
        if measure_imp is None:
            return ""
        try:
            measure_imp.killRoi()
        except:
            pass
        if measure_imp.getBitDepth() != 8:
            IJ.run(measure_imp, "8-bit", "")

        weighted_sum = 0.0
        pixel_total = 0.0
        stack_size = max(1, int(measure_imp.getStackSize()))
        for slice_index in range(1, stack_size + 1):
            try:
                measure_imp.setSlice(slice_index)
            except:
                pass
            stats = measure_imp.getStatistics(Measurements.MEAN)
            pixel_count = 0.0
            try:
                pixel_count = float(stats.pixelCount)
            except:
                pixel_count = float(measure_imp.getWidth() * measure_imp.getHeight())
            if pixel_count <= 0:
                continue
            weighted_sum += float(stats.mean) * pixel_count
            pixel_total += pixel_count

        if pixel_total <= 0:
            return ""
        mean_value = weighted_sum / pixel_total
        if mean_value < 0.0:
            mean_value = 0.0
        if mean_value > 255.0:
            mean_value = 255.0
        ORIGINAL_8BIT_MEAN_CACHE[cache_key] = mean_value
        return mean_value
    except Exception as e_mean:
        IJ.log("Could not measure original 8-bit mean gray value: " + str(e_mean))
        return ""
    finally:
        try:
            if measure_imp is not None:
                measure_imp.changes = False
                measure_imp.close()
        except:
            pass


def process_one_image(image_path, parent_output_dir, settings, run_label, run_counter_hint=0):
    raise_if_cancel_requested("run startup")
    mark_beast_worker_content_progress("RUN_START", os.path.basename(str(image_path)))
    # Reset transient large-pore repair state for every image/crop/sweep run.
    settings["_large_pore_repair_review_consumed"] = False
    settings["_large_pore_repair_review_accepted_centers"] = []
    settings["_large_pore_repair_review_rejected_centers"] = []
    settings["_large_pore_repair_analysis_pass"] = 0
    settings["_large_pore_repair_result"] = {}
    settings["_fiber_fixer_result"] = {}
    image_file = File(image_path)
    image_name = image_file.getName()
    base_name = os.path.splitext(image_name)[0]
    base_safe_full = safe_name(base_name)

    # Keep ImageJ window/file titles unique during cropped batch runs.
    # Crops and repeated image names can truncate to the same base_safe title,
    # which can make later steps accidentally target an older open ImageJ window.
    try:
        if int(run_counter_hint) > 0:
            base_safe = short_safe_name(base_name, 12) + "_R" + str(int(run_counter_hint))
        else:
            base_safe = short_safe_name(base_name, 18)
    except:
        base_safe = short_safe_name(base_name, 18)

    param_suffix = settings_suffix(settings)

    if run_label is None or str(run_label).strip() == "" or run_label == "normal":
        label_safe = short_safe_name(param_suffix, 16)
    else:
        label_safe = short_safe_name(run_label, 16)

    # Very short run folder names are important. Long batch/sweep paths can make JMP fail to open CSVs.
    run_dir_name = ultra_short_run_id(base_name, label_safe, run_counter_hint)

    run_dir = os.path.join(parent_output_dir, run_dir_name)
    image_dir = os.path.join(run_dir, "Images")
    hist_dir = os.path.join(run_dir, "Histograms")
    jmp_dir = os.path.join(run_dir, "JMP")
    save_run_images = run_image_outputs_enabled(settings)
    settings["_save_run_images"] = bool(save_run_images)
    # Always initialize the optional overlay path. Overlay failure must never abort the run.
    segmented_overlay_png = ""
    segmented_pores_overlay_png = ""

    ensure_dir(run_dir)
    if save_run_images:
        ensure_dir(image_dir)
        ensure_dir(hist_dir)
    ensure_dir(jmp_dir)
    if not save_run_images:
        IJ.log("BEAST DATA-ONLY FAST PATH: graph/Word reporting is disabled; per-run image files/folders will not be written.")

    settings["_fiber_fixer_current_image_path"] = str(image_path)
    settings["_fiber_fixer_output_root"] = str(parent_output_dir)
    IJ.log("Processing image: " + image_path)
    IJ.log("Run folder: " + run_dir)
    IJ.log("Run folder path length: " + str(len(run_dir)))
    if len(run_dir) > 190:
        IJ.log("WARNING: Run folder path is still long. If JMP cannot open CSVs, choose a shorter output folder such as C:/GDL_OUT.")

    imp_original = IJ.openImage(image_path)

    if imp_original is None:
        raise Exception("Could not open selected image: " + image_path)

    mark_beast_worker_content_progress("IMAGE_OPENED", os.path.basename(str(image_path)))
    raise_if_cancel_requested("image opening")
    imp_original.setTitle(base_safe + "_original")

    og_image_name = resolve_og_image_name(image_path, image_name, settings)
    original_8bit_mean_gray = measure_original_8bit_mean_gray(imp_original, image_path)
    if original_8bit_mean_gray not in [None, ""]:
        IJ.log("Original 8-bit mean gray value (0-255): " + ("%.6f" % float(original_8bit_mean_gray)))

    step_notes = []
    quality_warnings = []
    step_notes.append("OG image name: " + str(og_image_name))
    step_notes.append("Original 8-bit mean gray value before processing (0-255): " + str(original_8bit_mean_gray))

    # Optional auto-scale for unscaled images before any duplicate/preprocessing/particle analysis.
    # Duplicates inherit this calibration, so all areas/EPD values use the corrected mm scale.
    try:
        did_scale_before_processing = apply_preferred_scale_to_image(
            imp_original, image_path, settings, image_name, step_notes, quality_warnings
        )
        if did_scale_before_processing:
            save_scaled_tif_next_to_input(imp_original, image_path, settings, step_notes)
    except Exception as e_auto_scale:
        if global_cancel_requested():
            raise
        msg_auto_scale = "AUTO SCALE WARNING: auto-scale failed before processing " + str(image_name) + ": " + str(e_auto_scale)
        IJ.log(msg_auto_scale)
        step_notes.append(msg_auto_scale)
        quality_warnings.append(msg_auto_scale)

    mark_beast_worker_content_progress("SCALE_READY", str(og_image_name))
    raise_if_cancel_requested("scale/original preparation")
    original_tif = os.path.join(image_dir, base_safe + "_original.tif")
    original_png = os.path.join(image_dir, base_safe + "_original.png")

    if save_run_images:
        if not no_lossless_generated_images_enabled(settings):
            FileSaver(imp_original).saveAsTiff(original_tif)
        else:
            original_tif = ""
        FileSaver(imp_original).saveAsPng(original_png)
        starting_png, starting_tif = save_starting_image_for_report(image_path, imp_original, image_dir, base_safe, settings)
    else:
        original_tif = ""
        original_png = ""
        starting_png = ""
        starting_tif = ""

    # v201: create/cache the rainbow heat map NOW, before preprocessing and segmentation.
    # It is keyed to the true OG source (crop_source_image when present), so all sweeps/crops
    # referring to one original image share one heat map and every report can embed it reliably.
    strand_heat_map_png = ""
    if save_run_images:
        preseg_heat_map_run = {
            "image_path": image_path,
            "image_name": image_name,
            "og_image_name": og_image_name,
            "crop_source_image": settings.get("crop_source_image", ""),
            "crop_source_name": settings.get("crop_source_name", ""),
            "starting_png": starting_png,
            "original_png": original_png,
            "image_dir": image_dir,
            "run_dir": run_dir,
            "heat_map_fallback_dir": os.path.join(parent_output_dir, "Heat Maps"),
            "base_safe": base_safe
        }
        try:
            strand_heat_map_png = ensure_strand_heat_map_for_run(preseg_heat_map_run, settings)
        except Exception as e_preseg_heat_map:
            strand_heat_map_png = ""
            IJ.log("WARNING: pre-segmentation strand rainbow heat map could not be created for " + str(og_image_name) + ": " + str(e_preseg_heat_map))
    mark_beast_worker_content_progress("HEAT_MAP_READY", str(strand_heat_map_png))

    # Preprocess image
    work = Duplicator().run(imp_original)
    work.setTitle(base_safe + "_preprocessed")

    run_preprocessing(work, settings, step_notes)
    mark_beast_worker_content_progress("PREPROCESSING_COMPLETE", os.path.basename(str(image_path)))
    raise_if_cancel_requested("preprocessing")

    preprocessed_tif = os.path.join(image_dir, base_safe + "_preprocessed.tif")
    preprocessed_png = os.path.join(image_dir, base_safe + "_preprocessed.png")

    if save_run_images:
        if not no_lossless_generated_images_enabled(settings):
            FileSaver(work).saveAsTiff(preprocessed_tif)
        else:
            preprocessed_tif = ""
        FileSaver(work).saveAsPng(preprocessed_png)
    else:
        preprocessed_tif = ""
        preprocessed_png = ""

    # Use the fully preprocessed image for thresholding, particle analysis, segmented report images,
    # outlines, pore maps, manual-comparison table matching, and conditional auto-fit.
    # This keeps the report/analysis consistent with the enabled processing steps.
    threshold_source = Duplicator().run(work)
    threshold_source.setTitle(base_safe + "_preprocessed_threshold_source")
    threshold_source_tif = os.path.join(image_dir, base_safe + "_preprocessed_threshold_source.tif")
    threshold_source_png = os.path.join(image_dir, base_safe + "_preprocessed_threshold_source.png")
    if save_run_images:
        try:
            if not no_lossless_generated_images_enabled(settings):
                FileSaver(threshold_source).saveAsTiff(threshold_source_tif)
            else:
                threshold_source_tif = ""
            FileSaver(threshold_source).saveAsPng(threshold_source_png)
        except:
            pass
    else:
        threshold_source_tif = ""
        threshold_source_png = ""
    step_notes.append("Threshold source: preprocessed image after the enabled processing steps.")
    step_notes.append("Threshold input mode: " + threshold_input_mode_label(settings.get("threshold_force_8bit_numbers", True)) + ".")
    step_notes.append("Initial threshold analysis uses " + threshold_range_with_percent(settings.get("threshold_min", ""), settings.get("threshold_max", ""), settings.get("threshold_force_8bit_numbers", True)) + ".")

    auto_threshold_fit_result = None
    auto_threshold_fit_triggered = False
    auto_threshold_fit_direction = ""
    auto_threshold_fit_normal_area_percent_diff = ""
    auto_threshold_fit_final_area_percent_diff = ""
    auto_threshold_fit_normal_table_area_mm2 = ""
    auto_threshold_fit_final_table_area_mm2 = ""
    auto_threshold_fit_manual_area_mm2 = ""
    auto_threshold_fit_final_match_method = ""
    auto_threshold_fit_threshold_before = settings.get("threshold_max", "")
    auto_threshold_fit_threshold_after = ""
    threshold_step_adjustment_made = False
    final_threshold_analysis_source = "initial preprocessed threshold source"

    # Threshold and analyze the preprocessed image at the starting/default threshold first.
    mark_beast_worker_content_progress("THRESHOLD_ANALYSIS_START", os.path.basename(str(image_path)))
    mask, segmented_tif, segmented_png, outline, outlines_tif, outlines_png, rt, particle_count = analyze_threshold_source(
        threshold_source, settings, image_dir, base_safe
    )
    mark_beast_worker_content_progress("THRESHOLD_ANALYSIS_COMPLETE", os.path.basename(str(image_path)))
    raise_if_cancel_requested("thresholding and particle analysis")
    step_notes.append(
        "Actual histogram-derived threshold: gray " + str(settings.get("_threshold_actual_min_gray", "")) +
        " to " + str(settings.get("_threshold_actual_max_gray", "")) +
        "; cumulative histogram " + str(settings.get("_threshold_histogram_min_percent", "")) +
        "% to " + str(settings.get("_threshold_histogram_max_percent", "")) + "% ."
    )

    # Calibration and area conversion
    cal = imp_original.getCalibration()
    unit = cal.getUnit()

    length_to_mm = unit_to_mm_factor(unit)
    area_to_mm2 = length_to_mm * length_to_mm

    try:
        unit_norm_for_warning = str(unit).replace("µ", "u").replace("μ", "u").strip().lower()
        if unit_norm_for_warning in ["", "pixel", "pixels", "px"]:
            scale_warning_msg = "WARNING: image is not scaled in mm. Calibration unit is pixel/blank; set scale before trusting mm^2 or EPD(mm)."
            IJ.log(scale_warning_msg)
            step_notes.append(scale_warning_msg)
            quality_warnings.append(scale_warning_msg)
            quality_warnings.append(scale_warning_msg)
        elif unit_norm_for_warning not in ["mm", "millimeter", "millimeters"]:
            scale_warning_msg = "WARNING: image calibration unit is " + str(unit) + ", not mm. Recognized units are converted to mm; verify scale."
            IJ.log(scale_warning_msg)
            step_notes.append(scale_warning_msg)
    except:
        pass

    pixel_width_mm = cal.pixelWidth * length_to_mm
    pixel_height_mm = cal.pixelHeight * length_to_mm

    image_total_area_mm2 = (
        imp_original.getWidth() *
        pixel_width_mm *
        imp_original.getHeight() *
        pixel_height_mm
    )

    unit_note = (
        "Original ImageJ unit: " +
        str(unit) +
        "; length conversion factor to mm: " +
        str(length_to_mm)
    )

    segmented_display_png = segmented_png
    segmented_display_tif = segmented_tif
    largest_pore_id = -1
    largest_pore_epd_mm = 0.0
    largest_pore_area_mm2 = 0.0
    try:
        tmp_largest_row, tmp_largest_epd, tmp_x, tmp_y, tmp_largest_area, tmp_area_raw = find_largest_pore_from_results(rt, cal, area_to_mm2)
        if tmp_largest_row >= 0:
            largest_pore_id = tmp_largest_row + 1
            largest_pore_epd_mm = tmp_largest_epd
            largest_pore_area_mm2 = tmp_largest_area
    except:
        pass

    highlight_png, highlight_tif, highlight_largest_pore_id, highlight_largest_pore_epd_mm = make_segmented_highlight_with_largest_pore(
        mask, rt, cal, area_to_mm2, settings, image_dir, base_safe
    )
    if highlight_largest_pore_id > 0:
        largest_pore_id = highlight_largest_pore_id
    if highlight_largest_pore_epd_mm > 0:
        largest_pore_epd_mm = highlight_largest_pore_epd_mm
    if highlight_png != "":
        segmented_display_png = highlight_png
        segmented_display_tif = highlight_tif

    manual_largest_pore_area_mm2 = None
    manual_largest_pore_epd_mm = None
    manual_largest_pore_trace_tool = ""
    manual_circled_png = ""
    manual_circled_tif = ""
    manual_largest_pore_entries = []

    manual_selected_pore_area_mm2 = None
    manual_selected_pore_epd_mm = None
    manual_selected_pore_id = -1
    manual_selected_table_epd_mm = 0.0
    manual_selected_table_area_mm2 = 0.0
    manual_selected_pore_png = ""
    manual_selected_match_method = ""
    manual_selected_trace_tool = ""
    manual_combined_guide_png = ""
    manual_combined_guide_tif = ""
    manual_selected_roi = None
    manual_selected_pore_entries = []
    manual_selected_rois_for_autofit = []
    segmented_selected_png = ""
    segmented_selected_tif = ""
    manual_strand_lengths_mm = []
    manual_strand_trace_tools = []
    manual_strand_png = ""
    manual_strand_tif = ""
    manual_strand_reused = False

    if settings.get("manual_largest_pore_enabled", False):
        largest_measure_count = int(settings.get("manual_largest_pore_count", 1))
        if largest_measure_count < 1:
            largest_measure_count = 1

        for ml_i in range(largest_measure_count):
            ml_result = manual_largest_pore_entry_from_circled_image(
                imp_original, mask, rt, cal, area_to_mm2, settings, image_dir, base_safe, image_name, ml_i
            )
            ml_manual_area, ml_manual_epd, ml_png, ml_tif, ml_pore_id, ml_table_epd, ml_table_area, ml_tool = ml_result

            if ml_png != "" and manual_circled_png == "":
                manual_circled_png = ml_png
                manual_circled_tif = ml_tif

            if ml_manual_area not in [None, ""]:
                manual_largest_pore_entries.append({
                    "rank": ml_i + 1,
                    "pore_id": ml_pore_id,
                    "manual_area_mm2": ml_manual_area,
                    "manual_epd_mm": ml_manual_epd,
                    "analysis_area_mm2": ml_table_area,
                    "analysis_epd_mm": ml_table_epd,
                    "trace_tool": ml_tool,
                    "guide_png": ml_png,
                    "guide_tif": ml_tif
                })

                if manual_largest_pore_area_mm2 is None:
                    manual_largest_pore_area_mm2 = ml_manual_area
                    manual_largest_pore_epd_mm = ml_manual_epd
                    manual_largest_pore_trace_tool = ml_tool

            if largest_pore_id <= 0 and ml_pore_id > 0:
                largest_pore_id = ml_pore_id
            if largest_pore_epd_mm <= 0 and ml_table_epd > 0:
                largest_pore_epd_mm = ml_table_epd
            if largest_pore_area_mm2 <= 0 and ml_table_area > 0:
                largest_pore_area_mm2 = ml_table_area

    if settings.get("manual_selected_pore_enabled", False):
        selected_measure_count = int(settings.get("manual_selected_pore_count", 1))
        if selected_measure_count < 1:
            selected_measure_count = 1

        for ms_i in range(selected_measure_count):
            selected_base_safe = base_safe
            if ms_i > 0:
                selected_base_safe = base_safe + "_selected_" + str(ms_i + 1)

            ms_result = manual_selected_pore_entry(
                imp_original, mask, rt, cal, area_to_mm2, settings, image_dir, selected_base_safe, image_name, manual_circled_png
            )
            ms_manual_area, ms_manual_epd, ms_pore_id, ms_table_epd, ms_table_area, ms_png, ms_method, ms_combined_png, ms_combined_tif, ms_roi, ms_tool = ms_result

            if ms_png != "" and manual_selected_pore_png == "":
                manual_selected_pore_png = ms_png
            if ms_combined_png != "" and manual_combined_guide_png == "":
                manual_combined_guide_png = ms_combined_png
                manual_combined_guide_tif = ms_combined_tif

            if ms_manual_area not in [None, ""]:
                ms_normal_diff = area_percent_difference(ms_manual_area, ms_table_area)
                try:
                    ms_trigger_limit = float(settings.get("auto_threshold_fit_trigger_percent_diff", 5.0))
                except:
                    ms_trigger_limit = 5.0
                if ms_trigger_limit < 0:
                    ms_trigger_limit = 0.0
                try:
                    ms_normal_abs_diff = abs(float(ms_normal_diff))
                except:
                    ms_normal_abs_diff = 0.0
                ms_trigger_reached = ms_normal_abs_diff >= ms_trigger_limit
                ms_auto_fit_choice = str(settings.get("_manual_selected_pore_high_diff_choice", ""))

                manual_selected_pore_entries.append({
                    "index": ms_i + 1,
                    "pore_id": ms_pore_id,
                    "manual_area_mm2": ms_manual_area,
                    "manual_epd_mm": ms_manual_epd,
                    "table_area_mm2": ms_table_area,
                    "table_epd_mm": ms_table_epd,
                    "normal_area_percent_diff": ms_normal_diff,
                    "trigger_limit_percent": ms_trigger_limit,
                    "auto_fit_trigger_percent_reached": ms_trigger_reached,
                    "auto_fit_choice": ms_auto_fit_choice,
                    "match_method": ms_method,
                    "trace_tool": ms_tool,
                    "selected_png": ms_png,
                    "combined_png": ms_combined_png
                })

                if ms_roi is not None:
                    try:
                        ms_area_raw_for_fit = float(ms_manual_area) / float(area_to_mm2)
                    except:
                        ms_area_raw_for_fit = 0.0
                    manual_selected_rois_for_autofit.append({
                        "roi": ms_roi,
                        "manual_area_mm2": ms_manual_area,
                        "manual_area_raw": ms_area_raw_for_fit,
                        "normal_table_area_mm2": ms_table_area,
                        "normal_table_epd_mm": ms_table_epd,
                        "normal_area_percent_diff": ms_normal_diff,
                        "trigger_limit_percent": ms_trigger_limit,
                        "auto_fit_trigger_percent_reached": ms_trigger_reached,
                        "auto_fit_choice": ms_auto_fit_choice,
                        "pore_id": ms_pore_id,
                        "match_method": ms_method,
                        "trace_tool": ms_tool
                    })

                if manual_selected_pore_area_mm2 is None:
                    manual_selected_pore_area_mm2 = ms_manual_area
                    manual_selected_pore_epd_mm = ms_manual_epd
                    manual_selected_pore_id = ms_pore_id
                    manual_selected_table_epd_mm = ms_table_epd
                    manual_selected_table_area_mm2 = ms_table_area
                    manual_selected_match_method = ms_method
                    manual_selected_trace_tool = ms_tool

            if manual_selected_roi is None and ms_roi is not None:
                manual_selected_roi = ms_roi

        selected_highlight_allowed = False
        try:
            if len(manual_selected_pore_entries) > 0:
                selected_highlight_allowed = bool(manual_selected_pore_entries[0].get("auto_fit_trigger_percent_reached", False))
        except:
            selected_highlight_allowed = False

        if manual_selected_roi is not None and selected_highlight_allowed:
            segmented_selected_png, segmented_selected_tif = make_segmented_highlight_with_selected_pore(
                mask, rt, cal, area_to_mm2, settings, manual_selected_roi, image_dir, base_safe
            )

    # Manual selected-pore threshold adjustment happens AFTER the initial threshold analysis and user-selected pore measurement.
    # It no longer traces a separate auto-fit ROI or runs a threshold sweep.
    # Instead, it shows the selected-pore percent difference and lets you step threshold max by exactly +5 or -5.
    if settings.get("auto_threshold_fit_enabled", False) and len(manual_selected_rois_for_autofit) > 0:
        fit_check = manual_selected_rois_for_autofit[0]
        auto_threshold_fit_manual_area_mm2 = fit_check.get("manual_area_mm2", "")
        auto_threshold_fit_normal_table_area_mm2 = fit_check.get("normal_table_area_mm2", "")
        auto_threshold_fit_normal_area_percent_diff = fit_check.get("normal_area_percent_diff", "")
        auto_threshold_fit_final_table_area_mm2 = auto_threshold_fit_normal_table_area_mm2
        auto_threshold_fit_final_area_percent_diff = auto_threshold_fit_normal_area_percent_diff
        auto_threshold_fit_final_match_method = fit_check.get("match_method", "")

        try:
            trigger_limit = float(settings.get("auto_threshold_fit_trigger_percent_diff", 5.0))
        except:
            trigger_limit = 5.0

        try:
            current_max = float(settings.get("threshold_max", 40.0))
        except:
            current_max = 40.0

        auto_threshold_fit_threshold_before = current_max
        auto_threshold_fit_threshold_after = current_max
        current_table_area = auto_threshold_fit_normal_table_area_mm2
        current_percent_diff = auto_threshold_fit_normal_area_percent_diff
        current_match_method = fit_check.get("match_method", "")
        step_count = 0

        try:
            auto_threshold_fit_abs_diff = abs(float(auto_threshold_fit_normal_area_percent_diff))
        except:
            auto_threshold_fit_abs_diff = 0.0

        fit_choice = str(fit_check.get("auto_fit_choice", settings.get("_manual_selected_pore_high_diff_choice", "")))

        if auto_threshold_fit_abs_diff < trigger_limit:
            step_notes.append(
                "Manual selected-pore area difference = " + str(auto_threshold_fit_normal_area_percent_diff) +
                "%, which is within +/-" + str(trigger_limit) + "%; auto-fit/threshold adjustment was not opened."
            )
        elif fit_choice != "autofit":
            step_notes.append(
                "Manual selected-pore area difference = " + str(auto_threshold_fit_normal_area_percent_diff) +
                "%, but user chose Move On/skip from the auto-fit summary; threshold adjustment was not applied."
            )
        elif not settings.get("auto_threshold_fit_apply_to_main", True):
            step_notes.append(
                "Manual selected-pore threshold step check was enabled, but apply-to-main was disabled. " +
                "Normal selected-pore area difference = " + str(auto_threshold_fit_normal_area_percent_diff) + "%."
            )
        else:
            while True:
                decision = threshold_step_adjustment_decision(
                    current_max,
                    auto_threshold_fit_manual_area_mm2,
                    current_table_area,
                    current_percent_diff,
                    trigger_limit,
                    settings.get("threshold_force_8bit_numbers", True)
                )

                if decision == "accept":
                    if step_count <= 0:
                        step_notes.append(
                            "Manual selected-pore threshold check accepted without +/-5 adjustment. " +
                            "Normal selected-pore area difference = " + str(auto_threshold_fit_normal_area_percent_diff) + "%."
                        )
                    else:
                        step_notes.append(
                            "Manual selected-pore threshold adjustment accepted after " + str(step_count) +
                            " step(s). Final threshold max = " + str(current_max) +
                            "; final selected-pore area difference = " + str(current_percent_diff) + "%."
                        )
                    break

                if decision == "skip":
                    step_notes.append(
                        "Manual selected-pore threshold adjustment skipped. Normal selected-pore area difference = " +
                        str(auto_threshold_fit_normal_area_percent_diff) + "%."
                    )
                    break

                if decision == "plus":
                    new_max = current_max + 5.0
                    auto_threshold_fit_direction = "manual +5 threshold step; increasing threshold increases pore area"
                elif decision == "minus":
                    new_max = current_max - 5.0
                    auto_threshold_fit_direction = "manual -5 threshold step; decreasing threshold decreases pore area"
                else:
                    break

                threshold_adjustment_limit = 255.0 if threshold_mode_is_gray(settings.get("threshold_force_8bit_numbers", True)) else 100.0
                if new_max < 0.0:
                    new_max = 0.0
                if new_max > threshold_adjustment_limit:
                    new_max = threshold_adjustment_limit

                if new_max == current_max:
                    IJ.log("Threshold max step did not change because it hit the selected-unit limit of 0-" + str(int(threshold_adjustment_limit)) + ".")
                    continue

                previous_threshold_max = current_max
                previous_particle_count = particle_count

                current_max = new_max
                settings["threshold_max"] = current_max
                auto_threshold_fit_threshold_after = current_max
                auto_threshold_fit_triggered = True
                threshold_step_adjustment_made = True
                final_threshold_analysis_source = "manual +/-5 threshold max adjustment on preprocessed threshold source"
                step_count = step_count + 1

                step_notes.append(
                    "Manual selected-pore threshold step " + str(step_count) +
                    ": threshold max changed to " + str(current_max) +
                    " based on selected-pore % difference = " + str(current_percent_diff) + "%."
                )

                try:
                    mask.changes = False
                    mask.close()
                except:
                    pass
                try:
                    outline.changes = False
                    outline.close()
                except:
                    pass

                mask, segmented_tif, segmented_png, outline, outlines_tif, outlines_png, rt, particle_count = analyze_threshold_source(
                    threshold_source, settings, image_dir, base_safe
                )

                pc_change_warning = particle_count_change_issue(previous_particle_count, particle_count, settings, previous_threshold_max, current_max)
                if pc_change_warning != "":
                    IJ.log(pc_change_warning)
                    step_notes.append(pc_change_warning)
                    quality_warnings.append(pc_change_warning)

                # Recompute largest-pore values and final selected-pore match after the threshold step is applied.
                try:
                    tmp_largest_row, tmp_largest_epd, tmp_x, tmp_y, tmp_largest_area, tmp_area_raw = find_largest_pore_from_results(rt, cal, area_to_mm2)
                    if tmp_largest_row >= 0:
                        largest_pore_id = tmp_largest_row + 1
                        largest_pore_epd_mm = tmp_largest_epd
                        largest_pore_area_mm2 = tmp_largest_area
                except:
                    pass

                highlight_png, highlight_tif, highlight_largest_pore_id, highlight_largest_pore_epd_mm = make_segmented_highlight_with_largest_pore(
                    mask, rt, cal, area_to_mm2, settings, image_dir, base_safe
                )
                segmented_display_png = segmented_png
                segmented_display_tif = segmented_tif
                if highlight_largest_pore_id > 0:
                    largest_pore_id = highlight_largest_pore_id
                if highlight_largest_pore_epd_mm > 0:
                    largest_pore_epd_mm = highlight_largest_pore_epd_mm
                if highlight_png != "":
                    segmented_display_png = highlight_png
                    segmented_display_tif = highlight_tif

                try:
                    final_roi = fit_check.get("roi")
                    final_cx, final_cy = roi_center_from_bounds(final_roi)
                    final_row, final_epd, final_area, final_dist2, final_method = find_analysis_pore_matching_manual_roi(
                        rt,
                        cal,
                        area_to_mm2,
                        final_roi,
                        final_cx,
                        final_cy,
                        fit_check.get("manual_area_raw", 0.0)
                    )
                    current_table_area = final_area
                    current_percent_diff = area_percent_difference(auto_threshold_fit_manual_area_mm2, final_area)
                    current_match_method = final_method
                    auto_threshold_fit_final_table_area_mm2 = final_area
                    auto_threshold_fit_final_match_method = final_method
                    auto_threshold_fit_final_area_percent_diff = current_percent_diff
                    auto_threshold_fit_result = {
                        "best_min": settings.get("threshold_min", ""),
                        "best_max": current_max,
                        "manual_area_mm2": auto_threshold_fit_manual_area_mm2,
                        "normal_table_area_mm2": auto_threshold_fit_normal_table_area_mm2,
                        "normal_area_percent_diff": auto_threshold_fit_normal_area_percent_diff,
                        "final_table_area_mm2": final_area,
                        "final_area_percent_diff": current_percent_diff,
                        "final_match_method": final_method,
                        "final_pore_id": final_row + 1,
                        "step_count": step_count
                    }

                    # Keep manual selected-pore tables synced to the accepted final threshold.
                    # The complete summary comparison recalculates % difference from table_area_mm2,
                    # so update table_area_mm2/pore_id/match_method to final values.
                    try:
                        if len(manual_selected_pore_entries) > 0:
                            manual_selected_pore_entries[0]["final_pore_id"] = final_row + 1
                            manual_selected_pore_entries[0]["final_table_area_mm2"] = final_area
                            manual_selected_pore_entries[0]["final_area_percent_diff"] = current_percent_diff
                            manual_selected_pore_entries[0]["final_match_method"] = final_method
                            manual_selected_pore_entries[0]["final_threshold_max"] = current_max

                            manual_selected_pore_entries[0]["pore_id"] = final_row + 1
                            manual_selected_pore_entries[0]["table_area_mm2"] = final_area
                            manual_selected_pore_entries[0]["match_method"] = final_method
                    except Exception as e_sync:
                        IJ.log("Could not sync final threshold-step values to manual selected pore entries: " + str(e_sync))
                except Exception as efitfinal:
                    IJ.log("Could not compute final threshold-step percent difference: " + str(efitfinal))

                if manual_selected_roi is not None:
                    segmented_selected_png, segmented_selected_tif = make_segmented_highlight_with_selected_pore(
                        mask, rt, cal, area_to_mm2, settings, manual_selected_roi, image_dir, base_safe
                    )

                # Update single-value selected-pore fields so report fallbacks use the final threshold too.
                try:
                    manual_selected_pore_id = int(auto_threshold_fit_result.get("final_pore_id", manual_selected_pore_id))
                    manual_selected_table_area_mm2 = auto_threshold_fit_final_table_area_mm2
                    manual_selected_match_method = auto_threshold_fit_final_match_method
                except:
                    pass

    # Final safety pass for manual +/-5 threshold changes.
    # This guarantees the report images, numbered outlines, pore maps, CSV table, and summary use
    # the accepted final threshold on the preprocessed threshold source, not the initial threshold image.
    if threshold_step_adjustment_made:
        try:
            step_notes.append("Final threshold image regeneration: using preprocessed threshold source with final threshold min/max = " + str(settings.get("threshold_min", "")) + " / " + str(settings.get("threshold_max", "")) + ".")

            try:
                mask.changes = False
                mask.close()
            except:
                pass
            try:
                outline.changes = False
                outline.close()
            except:
                pass

            final_base_safe = base_safe + "_FINAL_T" + safe_name(str(settings.get("threshold_min", ""))) + "_" + safe_name(str(settings.get("threshold_max", "")))
            mask, segmented_tif, segmented_png, outline, outlines_tif, outlines_png, rt, particle_count = analyze_threshold_source(
                threshold_source, settings, image_dir, final_base_safe
            )

            highlight_png, highlight_tif, highlight_largest_pore_id, highlight_largest_pore_epd_mm = make_segmented_highlight_with_largest_pore(
                mask, rt, cal, area_to_mm2, settings, image_dir, final_base_safe
            )
            segmented_display_png = segmented_png
            segmented_display_tif = segmented_tif
            if highlight_largest_pore_id > 0:
                largest_pore_id = highlight_largest_pore_id
            if highlight_largest_pore_epd_mm > 0:
                largest_pore_epd_mm = highlight_largest_pore_epd_mm
            if highlight_png != "":
                segmented_display_png = highlight_png
                segmented_display_tif = highlight_tif

            try:
                tmp_largest_row, tmp_largest_epd, tmp_x, tmp_y, tmp_largest_area, tmp_area_raw = find_largest_pore_from_results(rt, cal, area_to_mm2)
                if tmp_largest_row >= 0:
                    largest_pore_id = tmp_largest_row + 1
                    largest_pore_epd_mm = tmp_largest_epd
                    largest_pore_area_mm2 = tmp_largest_area
            except:
                pass

            if manual_selected_roi is not None:
                segmented_selected_png, segmented_selected_tif = make_segmented_highlight_with_selected_pore(
                    mask, rt, cal, area_to_mm2, settings, manual_selected_roi, image_dir, final_base_safe
                )

            try:
                if len(manual_selected_rois_for_autofit) > 0:
                    fit_check_final = manual_selected_rois_for_autofit[0]
                    final_roi = fit_check_final.get("roi")
                    final_cx, final_cy = roi_center_from_bounds(final_roi)
                    final_row, final_epd, final_area, final_dist2, final_method = find_analysis_pore_matching_manual_roi(
                        rt,
                        cal,
                        area_to_mm2,
                        final_roi,
                        final_cx,
                        final_cy,
                        fit_check_final.get("manual_area_raw", 0.0)
                    )
                    if final_row >= 0:
                        auto_threshold_fit_final_table_area_mm2 = final_area
                        auto_threshold_fit_final_match_method = final_method
                        auto_threshold_fit_final_area_percent_diff = area_percent_difference(auto_threshold_fit_manual_area_mm2, final_area)
                        auto_threshold_fit_threshold_after = settings.get("threshold_max", "")
                        if auto_threshold_fit_result is None:
                            auto_threshold_fit_result = {}
                        auto_threshold_fit_result["best_min"] = settings.get("threshold_min", "")
                        auto_threshold_fit_result["best_max"] = settings.get("threshold_max", "")
                        auto_threshold_fit_result["manual_area_mm2"] = auto_threshold_fit_manual_area_mm2
                        auto_threshold_fit_result["normal_table_area_mm2"] = auto_threshold_fit_normal_table_area_mm2
                        auto_threshold_fit_result["normal_area_percent_diff"] = auto_threshold_fit_normal_area_percent_diff
                        auto_threshold_fit_result["final_table_area_mm2"] = final_area
                        auto_threshold_fit_result["final_area_percent_diff"] = auto_threshold_fit_final_area_percent_diff
                        auto_threshold_fit_result["final_match_method"] = final_method
                        auto_threshold_fit_result["final_pore_id"] = final_row + 1
                        auto_threshold_fit_result["final_report_regenerated"] = True

                        if len(manual_selected_pore_entries) > 0:
                            manual_selected_pore_entries[0]["final_pore_id"] = final_row + 1
                            manual_selected_pore_entries[0]["final_table_area_mm2"] = final_area
                            manual_selected_pore_entries[0]["final_area_percent_diff"] = auto_threshold_fit_final_area_percent_diff
                            manual_selected_pore_entries[0]["final_match_method"] = final_method
                            manual_selected_pore_entries[0]["final_threshold_max"] = settings.get("threshold_max", "")
                            manual_selected_pore_entries[0]["pore_id"] = final_row + 1
                            manual_selected_pore_entries[0]["table_area_mm2"] = final_area
                            manual_selected_pore_entries[0]["match_method"] = final_method

                        manual_selected_pore_id = final_row + 1
                        manual_selected_table_area_mm2 = final_area
                        manual_selected_match_method = final_method
            except Exception as e_final_sync:
                IJ.log("Could not sync manual selected pore after final threshold image regeneration: " + str(e_final_sync))

        except Exception as e_final_images:
            IJ.log("Could not regenerate final threshold report images after +/-5 adjustment: " + str(e_final_images))

    if settings.get("manual_strand_measurement_enabled", False):
        manual_strand_lengths_mm, manual_strand_trace_tools, manual_strand_png, manual_strand_tif, manual_strand_reused = manual_strand_measurement_once_per_original(
            imp_original, cal, length_to_mm, settings, image_dir, base_safe, image_name, image_path
        )

    fiber_fixer_result = settings.get("_fiber_fixer_result", {})
    large_pore_repair_result = settings.get("_large_pore_repair_result", {})
    if settings.get("fiber_fixer_enabled", False):
        step_notes.append(
            "Fiber Fixer: applied=" + str(fiber_fixer_result.get("applied", False)) +
            "; changed pixels=" + str(fiber_fixer_result.get("applied_pixel_count", 0)) +
            "; wire pixels=" + str(fiber_fixer_result.get("wire_pixel_count", 0)) +
            "; preview overlay=" + str(fiber_fixer_result.get("preview_overlay_png", ""))
        )
    if settings.get("large_pore_repair_enabled", False):
        step_notes.append(
            "Large pore repair: mode=" + str(large_pore_repair_result.get("mode_used", settings.get("large_pore_repair_mode", ""))) +
            "; accepted=" + str(large_pore_repair_result.get("accepted_count", 0)) +
            "; v193 aggressive/forced largest=" + str(large_pore_repair_result.get("largest_rescue_accepted_count", 0)) +
            "; green-target recursive=" + str(large_pore_repair_result.get("green_target_accepted_count", 0)) +
            "; tiny spur=" + str(large_pore_repair_result.get("green_spur_accepted_count", 0)) +
            "; repaired pixels=" + str(large_pore_repair_result.get("repaired_pixels", 0)) +
            "; conservative rule=one parent becomes exactly two substantial children."
        )

    mark_beast_worker_content_progress("MEASUREMENTS_COMPLETE", os.path.basename(str(image_path)))
    # Write ImageJ pore results CSV
    pore_csv = os.path.join(run_dir, "Pores.csv")

    headings = get_headings(rt)

    headers_out = ["Pore ID", "Pore Area"]

    for h in headings:
        if h != "Area":
            headers_out.append(h)

    # Fiji calculates EPD directly. Keep it as the final pore-data column so
    # BEAST MODE can skip JMP completely when histograms are disabled.
    headers_out.append("epd(mm)")

    rows_out = []
    total_pore_area_mm2 = 0.0
    solidity_values = []

    for r in range(particle_count):
        area_raw = rt_value(rt, "Area", r)

        if area_raw is None:
            pore_area_mm2 = 0.0
        else:
            pore_area_mm2 = float(area_raw) * area_to_mm2

        total_pore_area_mm2 += pore_area_mm2

        row = [r + 1, pore_area_mm2]

        for h in headings:
            if h == "Area":
                continue

            val = rt_value(rt, h, r)
            row.append(val)

            if h == "Solidity" and val is not None:
                try:
                    solidity_values.append(float(val))
                except:
                    pass

        row.append(pore_epd_mm_from_area_mm2(pore_area_mm2))
        rows_out.append(row)

    write_csv(pore_csv, headers_out, rows_out, settings["csv_decimals"])

    weird_pore_rows = build_weird_pore_rows(rt, cal, area_to_mm2, settings)
    weird_pore_csv = os.path.join(run_dir, "Weird_Pores.csv")
    if settings.get("flag_weird_pores_enabled", False):
        write_csv(weird_pore_csv, ["Pore ID", "EPD mm", "Area mm^2", "Circularity", "Roundness", "X", "Y", "Reason"], weird_pore_rows, settings["csv_decimals"])

    mark_beast_worker_content_progress("PORE_CSV_WRITTEN", str(pore_csv))
    # Write ImageJ summary CSV
    if image_total_area_mm2 != 0:
        area_percent = (total_pore_area_mm2 / image_total_area_mm2) * 100.0
    else:
        area_percent = 0.0

    if len(solidity_values) > 0:
        mean_solidity = sum(solidity_values) / float(len(solidity_values))
    else:
        mean_solidity = 0.0

    imagej_summary_csv = os.path.join(run_dir, "IJ_Summary.csv")

    sweep_until_metrics = build_sweep_until_metrics(rt, area_to_mm2, image_total_area_mm2, settings)

    threshold_gray_mode_for_summary = settings.get("threshold_force_8bit_numbers", True)
    threshold_min_gray_for_summary = settings.get("_threshold_actual_min_gray", threshold_input_to_gray(settings.get("threshold_min", ""), threshold_gray_mode_for_summary))
    threshold_max_gray_for_summary = settings.get("_threshold_actual_max_gray", threshold_input_to_gray(settings.get("threshold_max", ""), threshold_gray_mode_for_summary))
    threshold_min_percent_for_summary = settings.get("_threshold_histogram_min_percent", "")
    threshold_max_percent_for_summary = settings.get("_threshold_histogram_max_percent", "")
    threshold_selected_histogram_percent_for_summary = settings.get("_threshold_histogram_selected_percent", "")
    threshold_percent_basis_for_summary = settings.get("_threshold_percent_basis", "Cumulative histogram of the preprocessed 8-bit threshold source")

    summary_headers = [
        "OG Image Name",
        "Image",
        "Original 8-bit Mean Gray Value (0-255)",
        "Count",
        "Area %",
        "Total Area",
        "Solidity",
        "Image Total Area",
        "Threshold Input Mode",
        "Threshold Min Selected Units",
        "Threshold Max Selected Units",
        "Threshold Min 8-bit Gray",
        "Threshold Max 8-bit Gray",
        "Threshold Min Cumulative Histogram %",
        "Threshold Max Cumulative Histogram %",
        "Histogram Pixels Inside Threshold Range %",
        "Threshold Percent Basis",
        "Unit Note"
    ]

    summary_rows = [[
        og_image_name,
        image_name,
        original_8bit_mean_gray,
        particle_count,
        area_percent,
        total_pore_area_mm2,
        mean_solidity,
        image_total_area_mm2,
        threshold_input_mode_label(threshold_gray_mode_for_summary),
        settings.get("threshold_min", ""),
        settings.get("threshold_max", ""),
        threshold_min_gray_for_summary,
        threshold_max_gray_for_summary,
        threshold_min_percent_for_summary,
        threshold_max_percent_for_summary,
        threshold_selected_histogram_percent_for_summary,
        threshold_percent_basis_for_summary,
        unit_note
    ]]

    for sweep_metric_name in SWEEP_UNTIL_METRIC_OPTIONS:
        summary_headers.append("Sweep Until metric - " + str(sweep_metric_name))
        summary_rows[0].append(sweep_until_metrics.get(sweep_metric_name, ""))

    write_csv(imagej_summary_csv, summary_headers, summary_rows, settings["csv_decimals"])

    mark_beast_worker_content_progress("SUMMARY_CSV_WRITTEN", str(imagej_summary_csv))
    # Create lossless PNG pore map overlay for the Word report
    pore_map_png, pore_map_tif, pore_map_below_1_count, pore_map_below_2_count, pore_map_below_3_count = make_pore_map(
        imp_original, mask, rt, cal, area_to_mm2, settings, image_dir, base_safe
    )
    all_pore_map_png, all_pore_map_tif, all_pore_map_count, all_pore_map_min_epd_mm, all_pore_map_max_epd_mm = make_all_pore_map(
        imp_original, mask, rt, cal, area_to_mm2, settings, image_dir, base_safe
    )

    sample_size_text_value = image_size_text(imp_original, cal, length_to_mm)
    bad_image_status, bad_image_issues = detect_bad_image_issues(image_path, imp_original, cal, length_to_mm, image_total_area_mm2, particle_count)

    try:
        for scale_issue in scale_sanity_issues_for_image(imp_original, cal, length_to_mm, image_total_area_mm2, settings):
            if scale_issue not in bad_image_issues:
                bad_image_issues.append(scale_issue)
            if scale_issue not in quality_warnings:
                quality_warnings.append(scale_issue)
            IJ.log(scale_issue)
    except Exception as e_scale_sanity:
        IJ.log("Could not run scale sanity checker: " + str(e_scale_sanity))

    try:
        for particle_issue in particle_count_limit_issues(particle_count, settings):
            if particle_issue not in bad_image_issues:
                bad_image_issues.append(particle_issue)
            if particle_issue not in quality_warnings:
                quality_warnings.append(particle_issue)
            IJ.log(particle_issue)
    except Exception as e_particle_limit:
        IJ.log("Could not run particle count limit checker: " + str(e_particle_limit))

    scale_bar_paths = [starting_png, starting_tif, segmented_display_png, segmented_display_tif, outlines_png, outlines_tif, pore_map_png, pore_map_tif, all_pore_map_png, all_pore_map_tif]
    optional_scale_bar_paths = [manual_circled_png, manual_circled_tif, manual_selected_pore_png, manual_combined_guide_png, manual_combined_guide_tif, segmented_selected_png, segmented_selected_tif]
    # The cached strand image already received its scale bar during the first run for this original image.
    if not manual_strand_reused:
        optional_scale_bar_paths.extend([manual_strand_png, manual_strand_tif])
    for sb_path in optional_scale_bar_paths:
        if sb_path not in [None, ""]:
            scale_bar_paths.append(sb_path)
    scale_bar_applied_count = 0
    if settings.get("report_scale_bar_enabled", False):
        seen_scale = {}
        for sb_path in scale_bar_paths:
            if sb_path in [None, ""]:
                continue
            if seen_scale.get(sb_path, False):
                continue
            seen_scale[sb_path] = True
            if add_scale_bar_to_saved_file(sb_path, cal, length_to_mm, settings):
                scale_bar_applied_count += 1

    # Create and verify the segmented-over-original overlay during the Fiji run.
    overlay_run_seed = {
        "starting_png": starting_png,
        "original_png": original_png,
        "image_path": image_path,
        "segmented_png": segmented_png,
        "segmented_selected_png": segmented_selected_png,
        "image_dir": image_dir,
        "base_safe": base_safe
    }
    try:
        segmented_overlay_png = save_segmented_overlay_in_images(overlay_run_seed, settings)
    except Exception as overlay_run_error:
        segmented_overlay_png = ""
        IJ.log("Segmented overlay generation raised an unexpected nonfatal error for " + str(base_safe) + ": " + str(overlay_run_error))
        IJ.log(traceback.format_exc())
    if segmented_overlay_png == "" and settings.get("report_save_segmented_overlay_next_to_word", True):
        IJ.log("WARNING: segmented overlay was requested but could not be created for " + str(base_safe))
    elif segmented_overlay_png != "":
        IJ.log("Run result will publish segmented overlay path: " + str(segmented_overlay_png))

    try:
        segmented_pores_overlay_png = save_segmented_pores_overlay_in_images(overlay_run_seed, settings)
    except Exception as pores_overlay_error:
        segmented_pores_overlay_png = ""
        IJ.log("Segmented black/white overlay generation raised an unexpected nonfatal error for " + str(base_safe) + ": " + str(pores_overlay_error))
        IJ.log(traceback.format_exc())
    if segmented_pores_overlay_png == "" and settings.get("report_save_segmented_overlay_next_to_word", True):
        IJ.log("WARNING: segmented black/white overlay was requested but could not be created for " + str(base_safe))
    elif segmented_pores_overlay_png != "":
        IJ.log("Run result will publish segmented black/white overlay path: " + str(segmented_pores_overlay_png))

    mark_beast_worker_content_progress("REPORT_IMAGES_READY", os.path.basename(str(image_path)))
    # Create JMP script
    jsl_file = os.path.join(jmp_dir, "Run_JMP.jsl")
    create_jmp_script(jsl_file, pore_csv, imagej_summary_csv, run_dir, hist_dir, base_safe, settings)

    mark_beast_worker_content_progress("JMP_SCRIPT_READY", os.path.basename(str(image_path)))
    # Write ImageJ notes
    notes_path = os.path.join(run_dir, base_safe + "_ImageJ_Processing_Notes.txt")

    # These ranges are used inside analyze_threshold_source(), but also need to be
    # rebuilt here for the processing notes. Keeping them local prevents a NameError
    # after manual selected-pore/auto-fit workflows.
    size_range = str(settings.get("particle_size_min", "0")) + "-" + str(settings.get("particle_size_max", "Infinity"))
    circ_range = str(settings.get("particle_circ_min", 0.0)) + "-" + str(settings.get("particle_circ_max", 1.0))

    notes = []
    notes.append("ImageJ automated GDL processing notes")
    notes.append("Input image: " + image_path)
    notes.append("OG image name: " + str(og_image_name))
    notes.append("Original 8-bit mean gray value before processing (0-255): " + str(original_8bit_mean_gray))
    notes.append("Image details: " + str(sample_size_text_value))
    notes.append("Bad image check status: " + str(bad_image_status))
    if len(bad_image_issues) > 0:
        for bad_issue in bad_image_issues:
            notes.append("Bad image warning: " + str(bad_issue))
    notes.append("Output folder: " + run_dir)
    notes.append("Generated output base name shortened for JMP/Windows path safety: " + str(base_safe))
    notes.append("Run folder path length: " + str(len(run_dir)))
    notes.append("Original image saved: " + original_tif)
    notes.append("Original PNG saved: " + original_png)
    notes.append("True original input for report PNG saved: " + starting_png)
    notes.append("Preprocessed image saved: " + preprocessed_tif)
    notes.append("Segmented mask saved: " + segmented_tif)
    notes.append("Segmented-over-original overlay PNG: " + str(segmented_overlay_png))
    notes.append("Segmented black/white overlay PNG: " + str(segmented_pores_overlay_png))
    notes.append("Large pore repair enabled: " + str(settings.get("large_pore_repair_enabled", False)))
    notes.append("Fiber Fixer enabled: " + str(bool(settings.get("fiber_fixer_enabled", False))))
    notes.append("Fiber Fixer applied: " + str(fiber_fixer_result.get("applied", False)))
    notes.append("Fiber Fixer absolute threshold max: " + str(fiber_fixer_result.get("threshold_max_used", settings.get("fiber_fixer_absolute_threshold_max", 40))))
    notes.append("Fiber Fixer fixed wire width: 3 px")
    notes.append("Fiber Fixer source image: " + str(fiber_fixer_result.get("source_image_path", "")))
    notes.append("Fiber Fixer changed pixels: " + str(fiber_fixer_result.get("applied_pixel_count", 0)))
    notes.append("Fiber Fixer wire pixels: " + str(fiber_fixer_result.get("wire_pixel_count", 0)))
    notes.append("Fiber Fixer wireframe mask TIFF: " + str(fiber_fixer_result.get("wireframe_mask_tif", "")))
    notes.append("Fiber Fixer wireframe mask PNG: " + str(fiber_fixer_result.get("wireframe_mask_png", "")))
    notes.append("Fiber Fixer preview overlay TIFF: " + str(fiber_fixer_result.get("preview_overlay_tif", "")))
    notes.append("Fiber Fixer preview overlay PNG: " + str(fiber_fixer_result.get("preview_overlay_png", "")))
    notes.append("Fiber Fixer low-threshold mask TIFF: " + str(fiber_fixer_result.get("low_threshold_mask_tif", "")))
    notes.append("Fiber Fixer low-threshold mask PNG: " + str(fiber_fixer_result.get("low_threshold_mask_png", "")))
    notes.append("Large pore repair mode used: " + str(large_pore_repair_result.get("mode_used", "Off")))
    notes.append("Large pore repairs accepted: " + str(large_pore_repair_result.get("accepted_count", 0)))
    notes.append("v193 aggressive/forced largest-pore repairs accepted: " + str(large_pore_repair_result.get("largest_rescue_accepted_count", 0)))
    notes.append("v193 green-target recursive repairs accepted: " + str(large_pore_repair_result.get("green_target_accepted_count", 0)))
    notes.append("v193 tiny-spur repairs accepted: " + str(large_pore_repair_result.get("green_spur_accepted_count", 0)))
    notes.append("Large pore repaired pixels: " + str(large_pore_repair_result.get("repaired_pixels", 0)))
    notes.append("Large pore red overlay PNG: " + str(large_pore_repair_result.get("red_overlay_png", "")))
    notes.append("Large pore repair mask TIFF: " + str(large_pore_repair_result.get("repair_mask_tif", "")))
    notes.append("Large pore repair CSV: " + str(large_pore_repair_result.get("repair_csv", "")))
    notes.append("Analyze Particles include holes: " + str(settings.get("particle_include_holes", False)))
    notes.append("Analyze Particles exclude edge particles: " + str(settings.get("particle_exclude_edges", False)))
    notes.append("ImageJ Set Measurements options: " + build_set_measurements_options(settings))
    notes.append("Threshold source image: preprocessed image after enabled processing steps")
    notes.append("Auto-fit enabled: " + str(settings.get("auto_threshold_fit_enabled", False)))
    notes.append("Auto-fit trigger percent difference: " + str(settings.get("auto_threshold_fit_trigger_percent_diff", "")))
    notes.append("Auto-fit triggered: " + str(auto_threshold_fit_triggered))
    notes.append("Auto-fit direction: " + str(auto_threshold_fit_direction))
    notes.append("Auto-fit normal selected-pore percent difference: " + str(auto_threshold_fit_normal_area_percent_diff))
    notes.append("Auto-fit final selected-pore percent difference: " + str(auto_threshold_fit_final_area_percent_diff))
    notes.append("Auto-fit threshold before/after: " + str(auto_threshold_fit_threshold_before) + " / " + str(auto_threshold_fit_threshold_after))
    notes.append("Final threshold adjustment made: " + str(threshold_step_adjustment_made))
    notes.append("Final threshold analysis source: " + str(final_threshold_analysis_source))
    if settings.get("highlight_largest_pore_in_segmented", False):
        notes.append("Segmented display with largest pore highlighted: " + segmented_display_tif)
        if largest_pore_id > 0:
            notes.append("Largest pore highlighted with yellow fill: Pore ID " + str(largest_pore_id) + ", epd(mm) = " + str(largest_pore_epd_mm))
    notes.append("Numbered particle outlines saved: " + outlines_tif)
    notes.append("ImageJ pore results CSV: " + pore_csv)
    notes.append("ImageJ summary CSV: " + imagej_summary_csv)
    notes.append("JMP script created: " + jsl_file)
    notes.append("BEAST JMP execution: " + ("enabled for histograms/Word report" if beast_jmp_histograms_enabled(settings) else "disabled; Fiji-calculated EPD exported directly"))
    notes.append("")
    notes.append("Run settings:")
    notes.append("Process order: " + str(settings["process_order"]))
    notes.append("Convert 8-bit: " + bool_to_text(settings["convert_8bit"]))
    notes.append("Median enabled: " + bool_to_text(settings["median_enabled"]))
    notes.append("Median radius: " + str(settings["median_radius"]))
    notes.append("Contrast enabled: " + bool_to_text(settings["contrast_enabled"]))
    notes.append("Contrast mode: " + contrast_mode_label(settings))
    notes.append("Contrast saturated: " + str(settings["contrast_saturated"]))
    notes.append("Contrast normalize: " + bool_to_text(settings["contrast_normalize"]))
    notes.append("Contrast equalize: " + bool_to_text(settings["contrast_equalize"]))
    notes.append("Bandpass enabled: " + bool_to_text(settings["bandpass_enabled"]))
    notes.append("Bandpass large: " + str(settings["bandpass_large"]))
    notes.append("Bandpass small: " + str(settings["bandpass_small"]))
    notes.append("Bandpass suppress: " + str(settings["bandpass_suppress"]))
    notes.append("Bandpass tolerance: " + str(settings["bandpass_tolerance"]))
    notes.append("CLAHE enabled: " + bool_to_text(settings["clahe_enabled"]))
    notes.append("CLAHE block size: " + str(settings["clahe_blocksize"]))
    notes.append("CLAHE histogram bins: " + str(settings["clahe_histogram"]))
    notes.append("CLAHE maximum slope: " + str(settings["clahe_maximum"]))
    notes.append("Binary cleanup enabled: " + bool_to_text(settings.get("binary_enabled", False)))
    notes.append("Binary fill holes: " + bool_to_text(settings.get("binary_fill_holes", False)))
    notes.append("Binary watershed: " + bool_to_text(settings.get("binary_watershed", False)))
    notes.append("Binary despeckle iterations: " + str(settings.get("binary_despeckle_iterations", 0)))
    notes.append("Binary open iterations: " + str(settings.get("binary_open_iterations", 0)))
    notes.append("Binary close iterations: " + str(settings.get("binary_close_iterations", 0)))
    notes.append("Binary erode iterations: " + str(settings.get("binary_erode_iterations", 0)))
    notes.append("Binary dilate iterations: " + str(settings.get("binary_dilate_iterations", 0)))
    notes.append("Minimum grayscale filter radius (px): " + str(settings.get("binary_minimum_radius", 0.0)))
    notes.append("Maximum grayscale filter radius (px): " + str(settings.get("binary_maximum_radius", 0.0)))
    notes.append("Binary operation order: " + str(settings.get("binary_operation_order", "")))
    notes.append("Threshold input mode: " + threshold_input_mode_label(settings.get("threshold_force_8bit_numbers", True)))
    notes.append("Threshold selected-unit min: " + str(settings["threshold_min"]))
    notes.append("Threshold selected-unit max: " + str(settings["threshold_max"]))
    notes.append("Threshold with equivalents: " + threshold_range_with_percent(settings["threshold_min"], settings["threshold_max"], settings.get("threshold_force_8bit_numbers", True)))
    notes.append("Sweep Until enabled: " + str(settings.get("sweep_until_enabled", False)))
    notes.append("Sweep Until metric/operator/target: " + str(settings.get("sweep_until_metric", "")) + " / " + str(settings.get("sweep_until_operator", "")) + " / " + str(settings.get("sweep_until_target_value", "")))
    notes.append("Sweep Until scope: " + str(settings.get("sweep_until_stop_scope", "")))
    notes.append("Sweep Until calculated metrics: " + str(sweep_until_metrics))
    notes.append("Auto threshold fit enabled: " + str(settings.get("auto_threshold_fit_enabled", False)))
    notes.append("Auto threshold fit apply to main: " + str(settings.get("auto_threshold_fit_apply_to_main", False)))
    if auto_threshold_fit_result is not None:
        notes.append("Auto threshold fit best min: " + str(auto_threshold_fit_result.get("best_min", "")))
        notes.append("Auto threshold fit best max: " + str(auto_threshold_fit_result.get("best_max", "")))
        notes.append("Auto threshold fit score: " + str(auto_threshold_fit_result.get("score", "")))
        notes.append("Auto threshold fit IoU: " + str(auto_threshold_fit_result.get("iou", "")))
        notes.append("Auto threshold fit area error: " + str(auto_threshold_fit_result.get("area_error", "")))
        notes.append("Auto threshold fit manual ROI pixels: " + str(auto_threshold_fit_result.get("manual_pixels", "")))
        notes.append("Auto threshold fit fit pixels: " + str(auto_threshold_fit_result.get("fit_pixels", "")))
        notes.append("Auto threshold fit sweep CSV: " + str(auto_threshold_fit_result.get("csv", "")))
        notes.append("Auto threshold fit selected ROI count: " + str(auto_threshold_fit_result.get("roi_count", "")))
        notes.append("Auto threshold fit threshold step: " + str(auto_threshold_fit_result.get("step", "")))
        notes.append("Auto threshold fit best mask PNG: " + str(auto_threshold_fit_result.get("best_mask_png", "")))
    notes.append("Threshold method: selected input units converted to a manual pixel-level inclusive 8-bit mask")
    notes.append("Threshold mode uses gray-value inputs: " + str(threshold_mode_is_gray(settings.get("threshold_force_8bit_numbers", True))))
    notes.append("Particle size: " + size_range)
    notes.append("Particle circularity: " + circ_range)
    notes.append("JMP delete epd at or below: " + str(settings["small_epd_cutoff"]))
    notes.append("JMP epd cutoff 1: " + str(settings["epd_cutoff_1"]))
    notes.append("JMP epd cutoff 2: " + str(settings["epd_cutoff_2"]))
    notes.append("JMP circularity cutoff: " + str(settings["circ_cutoff"]))
    notes.append("JMP cleaned table sort: epd(mm) descending")
    notes.append("JMP histogram image size px: " + str(settings.get("jmp_hist_graph_width", "")) + " x " + str(settings.get("jmp_hist_graph_height", "")))
    notes.append("JMP histogram legend shown: " + str(settings.get("jmp_hist_show_legend", True)))
    notes.append("JMP histogram graph titles shown: " + str(settings.get("jmp_hist_show_graph_titles", True)))
    notes.append("JMP histogram axis titles shown: " + str(settings.get("jmp_hist_show_axis_titles", True)))
    notes.append("JMP legacy/default histogram bins: " + str(settings["jmp_hist_max_bins"]))
    notes.append("JMP EPD histogram title: " + str(settings.get("jmp_hist_epd_title", "")))
    notes.append("JMP EPD X-axis title: " + str(settings.get("jmp_hist_epd_x_axis_title", "")))
    notes.append("JMP EPD Y-axis title: " + str(settings.get("jmp_hist_epd_y_axis_title", "")))
    notes.append("JMP EPD histogram bins: " + str(settings.get("jmp_hist_epd_bins", "")))
    notes.append("JMP EPD X axis min/max mm: " + str(settings.get("jmp_hist_epd_x_min", "")) + " / " + str(settings.get("jmp_hist_epd_x_max", "")))
    notes.append("JMP EPD X major tick spacing mm (0=auto): " + str(settings.get("jmp_hist_epd_major_tick", "")))
    notes.append("JMP EPD Y max/tick count (0=auto): " + str(settings.get("jmp_hist_epd_y_max", "")) + " / " + str(settings.get("jmp_hist_epd_y_major_tick", "")))
    notes.append("JMP EPD roundness filter enabled/min: " + str(settings.get("jmp_epd_hist_round_filter_enabled", "")) + " / " + str(settings.get("jmp_epd_hist_round_filter_min", "")))
    notes.append("JMP Roundness histogram title: " + str(settings.get("jmp_hist_round_title", "")))
    notes.append("JMP Roundness X-axis title: " + str(settings.get("jmp_hist_round_x_axis_title", "")))
    notes.append("JMP Roundness Y-axis title: " + str(settings.get("jmp_hist_round_y_axis_title", "")))
    notes.append("JMP Roundness histogram bins: " + str(settings.get("jmp_hist_round_bins", "")))
    notes.append("JMP Roundness X min/max/tick: " + str(settings.get("jmp_hist_round_x_min", "")) + " / " + str(settings.get("jmp_hist_round_x_max", "")) + " / " + str(settings.get("jmp_hist_round_x_major_tick", "")))
    notes.append("JMP Roundness Y max/tick count (0=auto): " + str(settings.get("jmp_hist_round_y_max", "")) + " / " + str(settings.get("jmp_hist_round_y_major_tick", "")))
    notes.append("JMP Circularity histogram title: " + str(settings.get("jmp_hist_circ_title", "")))
    notes.append("JMP Circularity X-axis title: " + str(settings.get("jmp_hist_circ_x_axis_title", "")))
    notes.append("JMP Circularity Y-axis title: " + str(settings.get("jmp_hist_circ_y_axis_title", "")))
    notes.append("JMP Circularity histogram bins: " + str(settings.get("jmp_hist_circ_bins", "")))
    notes.append("JMP Circularity X min/max/tick: " + str(settings.get("jmp_hist_circ_x_min", "")) + " / " + str(settings.get("jmp_hist_circ_x_max", "")) + " / " + str(settings.get("jmp_hist_circ_x_major_tick", "")))
    notes.append("JMP Circularity Y max/tick count (0=auto): " + str(settings.get("jmp_hist_circ_y_max", "")) + " / " + str(settings.get("jmp_hist_circ_y_major_tick", "")))
    notes.append("JMP EPD cutoff reference lines: " + str(settings.get("jmp_epd_show_cutoff_lines", False)))
    notes.append("JMP statistics/histograms use cleaned EPD table; selected between-band count uses all detected pores")
    notes.append("Flag weird pores: " + str(settings.get("flag_weird_pores_enabled", False)))
    notes.append("JMP histogram X-axis padding percent: " + str(settings["jmp_hist_axis_pad_percent"]))
    notes.append("JMP histogram X scale: user controlled; default EPD 0 to 0.06 mm, Circularity/Roundness 0 to 1")
    notes.append("JMP histogram axis trailing-zero trimming: " + str(settings.get("jmp_hist_trim_trailing_zeros", True)))
    notes.append("JMP delete cutoff preset: " + str(settings.get("epd_between_preset", "Custom")))
    notes.append("EPD between low mm: " + str(settings.get("epd_between_low", "")))
    notes.append("EPD between high mm: " + str(settings.get("epd_between_high", "")))
    notes.append("Pore map background: " + str(settings.get("report_pore_map_background", "Original image")))
    notes.append("DOCX body page size inches: " + str(settings.get("docx_body_page_width_in", "")) + " x " + str(settings.get("docx_body_page_height_in", "")))
    notes.append("DOCX end summary page size inches: " + str(settings.get("docx_summary_page_width_in", "")) + " x " + str(settings.get("docx_summary_page_height_in", "")))
    notes.append("Scale bar enabled: " + str(settings.get("report_scale_bar_enabled", False)))
    notes.append("Scale bar auto-fit enabled: " + str(settings.get("report_scale_bar_auto_fit_enabled", False)))
    notes.append("Normal fixed scale bar length mm: " + str(settings.get("report_scale_bar_length_mm", "")))
    notes.append("Last applied scale bar length mm: " + str(settings.get("_last_scale_bar_length_mm", "")))
    notes.append("Scale bar thickness px: " + str(settings.get("report_scale_bar_thickness_px", "")))
    notes.append("Scale bar margin px: " + str(settings.get("report_scale_bar_margin_px", "")))
    notes.append("Scale bar color: " + str(settings.get("report_scale_bar_color", "")))
    notes.append("Scale bar label enabled: " + str(settings.get("report_scale_bar_label_enabled", True)))
    notes.append("Scale bar label text color: " + str(settings.get("report_scale_bar_text_color", "")))
    notes.append("Scale bar label outline enabled: " + str(settings.get("report_scale_bar_text_outline_enabled", True)))
    notes.append("Scale bar label outline color: " + str(settings.get("report_scale_bar_text_outline_color", "")))
    notes.append("Scale bar label font size px: " + str(settings.get("report_scale_bar_font_size_px", "")))
    notes.append("Scale bar images updated: " + str(scale_bar_applied_count))
    notes.append("Bad image detection enabled: " + str(settings.get("bad_image_detection_enabled", True)))
    notes.append("Popup warning summary enabled: " + str(settings.get("popup_warning_summary_enabled", True)))
    notes.append("Scale set using: " + str(settings.get("_effective_report_scale_method", settings.get("report_scale_method", "Needle scale"))))
    notes.append("Imaging software: " + str(settings.get("report_imaging_software", "Swift Imaging 3.0")))
    notes.append("Swift .magn scaling enabled: " + str(settings.get("swift_magn_scale_enabled", True)))
    notes.append("Swift .magn table path: " + str(settings.get("_swift_magn_table_path", "")))
    notes.append("Swift .magn profile: " + str(settings.get("_swift_magn_profile_name", "")))
    notes.append("Swift .magn Resolution pixels per meter (px/m): " + str(settings.get("_swift_magn_resolution_pixels_per_meter", "")))
    notes.append("Swift .magn scale um/pixel: " + str(settings.get("_swift_magn_um_per_pixel", "")))
    notes.append("Auto scale unscaled images enabled: " + str(settings.get("auto_scale_unscaled_enabled", False)))
    notes.append("Auto scale known red-line length mm default: " + str(settings.get("auto_scale_known_length_mm", "")))
    notes.append("Auto scale orange/blue reader enabled: " + str(settings.get("auto_scale_blue_ocr_enabled", False)))
    notes.append("Auto scale preview crop enabled: " + str(settings.get("auto_scale_show_preview", True)))
    notes.append("Auto scale preview padding px: " + str(settings.get("auto_scale_preview_padding_px", "")))
    notes.append("Auto scale preview zoom factor: " + str(settings.get("auto_scale_preview_zoom_factor", "")))
    notes.append("Auto scale save calibrated TIFF enabled: " + str(settings.get("auto_scale_save_tif_enabled", True)))
    notes.append("Auto scale save TIFF in Scaled image subfolder enabled: " + str(settings.get("auto_scale_save_tif_subfolder_enabled", False)))
    notes.append("Auto scale replace PNG/JPG workflow with TIFF enabled: " + str(settings.get("auto_scale_replace_png_with_tif_enabled", False)))
    notes.append("Auto scale applied: " + str(settings.get("_auto_scale_applied", False)))
    notes.append("Auto scale detected red-line pixels: " + str(settings.get("_auto_scale_detected_pixels", "")))
    notes.append("Auto scale detected endpoints: " + str(settings.get("_auto_scale_endpoints", "")))
    notes.append("Auto scale orange/blue label bbox: " + str(settings.get("_auto_scale_blue_bbox", "")))
    notes.append("Auto scale orange/blue label pixels: " + str(settings.get("_auto_scale_blue_pixels", "")))
    notes.append("Auto scale orange/blue reader text: " + str(settings.get("_auto_scale_blue_ocr_text", "")))
    notes.append("Auto scale orange/blue reader note: " + str(settings.get("_auto_scale_blue_ocr_note", "")))
    notes.append("Auto scale saved calibrated TIFF: " + str(settings.get("_auto_scale_saved_tif", "")))
    notes.append("Auto scale mm per pixel: " + str(settings.get("_auto_scale_mm_per_pixel", "")))
    notes.append("Auto scale pixels per mm: " + str(settings.get("_auto_scale_pixels_per_mm", "")))
    notes.append("Scale sanity checker enabled: " + str(settings.get("scale_sanity_warning_enabled", True)))
    notes.append("Scale sanity image area warning range mm^2: " + str(settings.get("scale_sanity_min_image_area_mm2", "")) + " to " + str(settings.get("scale_sanity_max_image_area_mm2", "")))
    notes.append("Scale sanity pixel-size warning range mm/pixel: " + str(settings.get("scale_sanity_min_pixel_size_mm", "")) + " to " + str(settings.get("scale_sanity_max_pixel_size_mm", "")))
    notes.append("Particle-count sanity checker enabled: " + str(settings.get("particle_count_sanity_enabled", True)))
    notes.append("Particle-count high limit: " + str(settings.get("particle_count_high_limit", "")))
    notes.append("Particle-count change warning percent: " + str(settings.get("particle_count_change_warning_percent", "")))
    notes.append("Quality warnings: " + str(quality_warnings))
    notes.append("Close ImageJ/Fiji windows when finished: " + str(settings["close_windows_when_finished"]))
    notes.append("Highlight largest pore on segmented image: " + str(settings.get("highlight_largest_pore_in_segmented", False)))
    notes.append("CSV decimal places: " + str(settings.get("csv_decimals", "")))
    notes.append("ImageJ Results precision: " + str(settings.get("imagej_results_precision", "")))
    notes.append("DOCX max decimal places, trailing zeros removed: " + str(settings.get("docx_report_decimals", "")))
    notes.append("Report filename mode: " + str(settings.get("report_filename_mode", "")))
    notes.append("Pre-segmentation OG-image rainbow heat map: " + str(strand_heat_map_png))
    notes.append("Rainbow heat map is keyed/reused per original image: True")
    notes.append("Excel main summary export enabled: " + str(settings.get("export_main_summary_xls", False)))
    notes.append("Excel main summary destination: " + str(settings.get("summary_xls_destination", "")))
    notes.append("No lossless images in Word reports: " + str(no_lossless_report_images_enabled(settings)))
    notes.append("Do not retain lossless generated run images: " + str(no_lossless_generated_images_enabled(settings)))
    notes.append("No lossless generated/report images master override: " + str(settings.get("no_lossless_images_at_all", False)))
    notes.append("BEAST MODE enabled: " + str(settings.get("beast_mode_enabled", False)))
    notes.append("BEAST MODE parallel JMP instances: " + str(settings.get("beast_jmp_parallel_instances", "")))
    notes.append("Guide largest-pore outline color: " + str(settings.get("guide_largest_outline_color", "")))
    notes.append("Guide selected-pore outline color: " + str(settings.get("guide_selected_outline_color", "")))
    notes.append("Guide outline offset, pixels: " + str(settings.get("guide_outline_extra_pixels", "")))
    notes.append("Guide outline line width: " + str(settings.get("guide_outline_line_width", "")))
    notes.append("Segmented largest-pore fill color: " + str(settings.get("segmented_largest_fill_color", "")))
    notes.append("Selected-pore high-difference guide: green offset outline, shown only when the auto-fit/redo percent trigger is reached.")
    notes.append("Segmented label/backup line width: " + str(settings.get("segmented_outline_line_width", "")))
    notes.append("Pore map band-1 color: " + str(settings.get("pore_map_band_1_color", "")))
    notes.append("Pore map band-2 color: " + str(settings.get("pore_map_band_2_color", "")))
    notes.append("Pore map band-3 color: " + str(settings.get("pore_map_band_3_color", "")))
    notes.append("Pore map small-pore marker radius px: " + str(settings.get("report_pore_map_low_marker_radius", 8)))
    notes.append("Pore map large-pore marker radius px: " + str(settings.get("report_pore_map_high_marker_radius", 14)))
    notes.append("Pore map marker opacity percent: " + str(settings.get("report_pore_map_opacity_percent", "")))
    notes.append("Pore map highlighted count below selected upper limit: " + str(pore_map_below_1_count))
    notes.append("Pore map fixed high cutoff mm: " + str(settings.get("report_pore_map_high_cutoff", 0.025)))
    notes.append("Pore map highlighted count above 25 microns: " + str(pore_map_below_2_count))
    notes.append("Second all-pore map enabled: " + str(settings.get("report_all_pore_map_enabled", False)))
    notes.append("Second all-pore map style: " + str(settings.get("report_all_pore_map_style", "")))
    notes.append("Second all-pore map legend enabled: " + str(settings.get("report_all_pore_map_show_legend", True)))
    notes.append("Second all-pore map count: " + str(all_pore_map_count))
    notes.append("Second all-pore map EPD range mm: " + str(all_pore_map_min_epd_mm) + " to " + str(all_pore_map_max_epd_mm))
    notes.append("Manual measurements master enabled: " + str(settings.get("manual_measurements_enabled", True)))
    notes.append("Manual largest pore measurement enabled: " + str(settings.get("manual_largest_pore_enabled", False)))
    notes.append("Manual largest pore count requested: " + str(settings.get("manual_largest_pore_count", 0)))
    if settings.get("manual_largest_pore_enabled", False):
        notes.append("Manual measurement guide image, unfiltered original with outline: " + str(manual_circled_tif))
        notes.append("Manual largest pore area mm^2: " + str(manual_largest_pore_area_mm2))
        notes.append("Manual largest pore EPD mm: " + str(manual_largest_pore_epd_mm))
        notes.append("Manual largest pore trace tool: " + str(manual_largest_pore_trace_tool))
        notes.append("Manual largest pore entries: " + str(manual_largest_pore_entries))
    notes.append("Manual selected pore measurement enabled: " + str(settings.get("manual_selected_pore_enabled", False)))
    notes.append("Manual success popup picture enabled: " + str(settings.get("manual_success_popup_show_picture", True)))
    notes.append("Manual selected pore count requested: " + str(settings.get("manual_selected_pore_count", 0)))
    notes.append("Manual strand measurement enabled: " + str(settings.get("manual_strand_measurement_enabled", False)))
    notes.append("Manual strand selections per original batch image: 1")
    notes.append("Manual strand measurement reused from first run of original image: " + str(manual_strand_reused))
    notes.append("Manual strand lengths mm: " + str(manual_strand_lengths_mm))
    notes.append("Manual strand tracing tools: " + str(manual_strand_trace_tools))
    if settings.get("manual_selected_pore_enabled", False):
        notes.append("Manual selected pore area mm^2: " + str(manual_selected_pore_area_mm2))
        notes.append("Manual selected pore EPD mm: " + str(manual_selected_pore_epd_mm))
        notes.append("Manual selected nearest analysis pore ID: " + str(manual_selected_pore_id))
        notes.append("Manual selected nearest analysis table EPD mm: " + str(manual_selected_table_epd_mm))
        notes.append("Manual selected match method: " + str(manual_selected_match_method))
        notes.append("Manual selected trace tool: " + str(manual_selected_trace_tool))
        notes.append("Manual selected pore entries: " + str(manual_selected_pore_entries))
        notes.append("Manual combined guide image (largest + selected markers): " + str(manual_combined_guide_tif))
        notes.append("Segmented image with selected pore highlighted: " + str(segmented_selected_tif))
    if settings.get("crop_enabled", False):
        notes.append("Crop enabled: True")
        notes.append("Crop source image: " + str(settings.get("crop_source_image", "")))
        notes.append("Crop mode: " + str(settings.get("crop_mode", "")))
        notes.append("Crop region: " + str(settings.get("crop_region_text", "")))
        notes.append("Crop overview image: " + str(settings.get("crop_overview_tif", "")))
    notes.append("")
    notes.append("Actual preprocessing steps run:")
    if len(step_notes) == 0:
        notes.append("No preprocessing steps were enabled.")
    else:
        for i in range(len(step_notes)):
            notes.append(str(i + 1) + ". " + step_notes[i])
    notes.append("")
    notes.append("Area / unit note:")
    notes.append(unit_note)
    notes.append("If the image is not calibrated, Pore Area and epd(mm) are not true mm units.")

    f = codecs.open(notes_path, "w", "utf-8")
    f.write("\n".join([unicode(n) for n in notes]))
    f.close()

    # Close image windows to keep batch runs lighter
    try:
        imp_original.close()
    except:
        pass
    try:
        work.close()
    except:
        pass
    try:
        threshold_source.close()
    except:
        pass
    try:
        mask.close()
    except:
        pass
    try:
        outline.close()
    except:
        pass

    mark_beast_worker_content_progress("RUN_RESULT_READY", os.path.basename(str(image_path)))
    return {
        "image_path": image_path,
        "image_name": image_name,
        "og_image_name": og_image_name,
        "original_8bit_mean_gray": original_8bit_mean_gray,
        "crop_enabled": settings.get("crop_enabled", False),
        "crop_mode": settings.get("crop_mode", ""),
        "crop_source_image": settings.get("crop_source_image", ""),
        "crop_source_name": settings.get("crop_source_name", ""),
        "crop_index": settings.get("crop_index", ""),
        "crop_total": settings.get("crop_total", ""),
        "crop_region_text": settings.get("crop_region_text", ""),
        "crop_overview_png": settings.get("crop_overview_png", ""),
        "crop_overview_tif": settings.get("crop_overview_tif", ""),
        "base_safe": base_safe,
        "run_label": run_label,
        "run_dir": run_dir,
        "image_dir": image_dir,
        "hist_dir": hist_dir,
        "jmp_dir": jmp_dir,
        "pore_csv": pore_csv,
        "raw_all_pores_csv": pore_csv if not beast_jmp_histograms_enabled(settings) else "",
        "summary_csv": imagej_summary_csv,
        "jsl_file": jsl_file,
        "particle_count": particle_count,
        "area_percent": area_percent,
        "total_pore_area_mm2": total_pore_area_mm2,
        "mean_solidity": mean_solidity,
        "image_total_area_mm2": image_total_area_mm2,
        "sweep_until_metrics": sweep_until_metrics,
        "sweep_until_enabled": settings.get("sweep_until_enabled", False),
        "sweep_until_metric": settings.get("sweep_until_metric", ""),
        "sweep_until_operator": settings.get("sweep_until_operator", ""),
        "sweep_until_target_value": settings.get("sweep_until_target_value", ""),
        "sweep_until_equal_tolerance": settings.get("sweep_until_equal_tolerance", ""),
        "sweep_until_stop_scope": settings.get("sweep_until_stop_scope", ""),
        "quality_warnings": quality_warnings,
        "particle_count_high_limit": settings.get("particle_count_high_limit", ""),
        "particle_count_change_warning_percent": settings.get("particle_count_change_warning_percent", ""),
        "particle_include_holes": settings.get("particle_include_holes", False),
        "particle_exclude_edges": settings.get("particle_exclude_edges", False),
        "large_pore_repair_enabled": settings.get("large_pore_repair_enabled", False),
        "large_pore_repair_mode": settings.get("large_pore_repair_mode", "Review proposals"),
        "fiber_fixer_enabled": bool(settings.get("fiber_fixer_enabled", False)),
        "fiber_fixer_applied": fiber_fixer_result.get("applied", False),
        "fiber_fixer_threshold_max_used": fiber_fixer_result.get("threshold_max_used", settings.get("fiber_fixer_absolute_threshold_max", 40)),
        "fiber_fixer_wire_width_px": 3,
        "fiber_fixer_source_image_path": fiber_fixer_result.get("source_image_path", ""),
        "fiber_fixer_applied_pixel_count": fiber_fixer_result.get("applied_pixel_count", 0),
        "fiber_fixer_wire_pixel_count": fiber_fixer_result.get("wire_pixel_count", 0),
        "fiber_fixer_wireframe_mask_tif": fiber_fixer_result.get("wireframe_mask_tif", ""),
        "fiber_fixer_wireframe_mask_png": fiber_fixer_result.get("wireframe_mask_png", ""),
        "fiber_fixer_preview_overlay_tif": fiber_fixer_result.get("preview_overlay_tif", ""),
        "fiber_fixer_preview_overlay_png": fiber_fixer_result.get("preview_overlay_png", ""),
        "fiber_fixer_error": fiber_fixer_result.get("error", ""),
        "large_pore_repair_mode_used": large_pore_repair_result.get("mode_used", "Off"),
        "large_pore_repair_accepted_count": large_pore_repair_result.get("accepted_count", 0),
        "large_pore_repair_largest_rescue_accepted_count": large_pore_repair_result.get("largest_rescue_accepted_count", 0),
        "large_pore_repair_green_target_accepted_count": large_pore_repair_result.get("green_target_accepted_count", 0),
        "large_pore_repair_green_spur_accepted_count": large_pore_repair_result.get("green_spur_accepted_count", 0),
        "large_pore_repair_repaired_pixels": large_pore_repair_result.get("repaired_pixels", 0),
        "large_pore_repair_parent_count": large_pore_repair_result.get("parent_count", 0),
        "large_pore_repair_proposal_count": large_pore_repair_result.get("proposal_count", 0),
        "large_pore_repair_records": large_pore_repair_result.get("repairs", []),
        "large_pore_repair_red_overlay_png": large_pore_repair_result.get("red_overlay_png", ""),
        "large_pore_repair_mask_tif": large_pore_repair_result.get("repair_mask_tif", ""),
        "large_pore_repair_csv": large_pore_repair_result.get("repair_csv", ""),
        "auto_threshold_fit_enabled": settings.get("auto_threshold_fit_enabled", False),
        "auto_threshold_fit_apply_to_main": settings.get("auto_threshold_fit_apply_to_main", False),
        "auto_threshold_fit_roi_count": settings.get("auto_threshold_fit_roi_count", 1),
        "auto_threshold_fit_result": auto_threshold_fit_result,
        "auto_threshold_fit_triggered": auto_threshold_fit_triggered,
        "auto_threshold_fit_direction": auto_threshold_fit_direction,
        "auto_threshold_fit_trigger_percent_diff": settings.get("auto_threshold_fit_trigger_percent_diff", ""),
        "auto_threshold_fit_normal_area_percent_diff": auto_threshold_fit_normal_area_percent_diff,
        "auto_threshold_fit_final_area_percent_diff": auto_threshold_fit_final_area_percent_diff,
        "auto_threshold_fit_normal_table_area_mm2": auto_threshold_fit_normal_table_area_mm2,
        "auto_threshold_fit_final_table_area_mm2": auto_threshold_fit_final_table_area_mm2,
        "auto_threshold_fit_manual_area_mm2": auto_threshold_fit_manual_area_mm2,
        "auto_threshold_fit_final_match_method": auto_threshold_fit_final_match_method,
        "auto_threshold_fit_threshold_before": auto_threshold_fit_threshold_before,
        "auto_threshold_fit_threshold_after": auto_threshold_fit_threshold_after,
        "final_threshold_adjustment_made": threshold_step_adjustment_made,
        "final_threshold_analysis_source": final_threshold_analysis_source,
        "auto_threshold_fit_best_min": "" if auto_threshold_fit_result is None else auto_threshold_fit_result.get("best_min", ""),
        "auto_threshold_fit_best_max": "" if auto_threshold_fit_result is None else auto_threshold_fit_result.get("best_max", ""),
        "auto_threshold_fit_score": "" if auto_threshold_fit_result is None else auto_threshold_fit_result.get("score", ""),
        "auto_threshold_fit_iou": "" if auto_threshold_fit_result is None else auto_threshold_fit_result.get("iou", ""),
        "auto_threshold_fit_area_error": "" if auto_threshold_fit_result is None else auto_threshold_fit_result.get("area_error", ""),
        "auto_threshold_fit_selected_roi_count": "" if auto_threshold_fit_result is None else auto_threshold_fit_result.get("roi_count", ""),
        "auto_threshold_fit_step": "" if auto_threshold_fit_result is None else auto_threshold_fit_result.get("step", ""),
        "auto_threshold_fit_csv": "" if auto_threshold_fit_result is None else auto_threshold_fit_result.get("csv", ""),
        "auto_threshold_fit_best_mask_png": "" if auto_threshold_fit_result is None else auto_threshold_fit_result.get("best_mask_png", ""),
        "original_png": original_png,
        "original_tif": original_tif,
        "starting_png": starting_png,
        "starting_tif": starting_tif,
        "strand_heat_map_png": strand_heat_map_png,
        "heat_map_fallback_dir": os.path.join(parent_output_dir, "Heat Maps"),
        "preprocessed_png": preprocessed_png,
        "preprocessed_tif": preprocessed_tif,
        "segmented_png": segmented_display_png,
        "segmented_tif": segmented_display_tif,
        "segmented_raw_png": segmented_png,
        "segmented_raw_tif": segmented_tif,
        "segmented_overlay_png": segmented_overlay_png,
        "segmented_pores_overlay_png": segmented_pores_overlay_png,
        "manual_measurements_enabled": settings.get("manual_measurements_enabled", True),
        "manual_largest_pore_enabled": settings.get("manual_largest_pore_enabled", False),
        "manual_largest_pore_count": settings.get("manual_largest_pore_count", 0),
        "manual_largest_pore_entries": manual_largest_pore_entries,
        "manual_largest_pore_area_mm2": manual_largest_pore_area_mm2,
        "manual_largest_pore_epd_mm": manual_largest_pore_epd_mm,
        "manual_largest_pore_trace_tool": manual_largest_pore_trace_tool,
        "manual_largest_pore_circled_png": manual_circled_png,
        "manual_largest_pore_circled_tif": manual_circled_tif,
        "analysis_largest_pore_id": largest_pore_id,
        "analysis_largest_pore_epd_mm": largest_pore_epd_mm,
        "analysis_largest_pore_area_mm2": largest_pore_area_mm2,
        "manual_selected_pore_enabled": settings.get("manual_selected_pore_enabled", False),
        "manual_selected_pore_count": settings.get("manual_selected_pore_count", 0),
        "manual_selected_pore_entries": manual_selected_pore_entries,
        "manual_selected_pore_area_mm2": manual_selected_pore_area_mm2,
        "manual_selected_pore_epd_mm": manual_selected_pore_epd_mm,
        "manual_selected_pore_id": manual_selected_pore_id,
        "manual_selected_table_epd_mm": manual_selected_table_epd_mm,
        "manual_selected_table_area_mm2": manual_selected_table_area_mm2,
        "manual_selected_pore_png": manual_selected_pore_png,
        "manual_selected_match_method": manual_selected_match_method,
        "manual_selected_trace_tool": manual_selected_trace_tool,
        "manual_combined_guide_png": manual_combined_guide_png,
        "manual_combined_guide_tif": manual_combined_guide_tif,
        "segmented_selected_png": segmented_selected_png,
        "segmented_selected_tif": segmented_selected_tif,
        "manual_strand_lengths_mm": manual_strand_lengths_mm,
        "manual_strand_trace_tools": manual_strand_trace_tools,
        "manual_strand_png": manual_strand_png,
        "manual_strand_tif": manual_strand_tif,
        "manual_strand_reused": bool(manual_strand_reused),
        "weird_pore_rows": weird_pore_rows,
        "weird_pore_csv": weird_pore_csv,
        "outlines_png": outlines_png,
        "outlines_tif": outlines_tif,
        "pore_map_png": pore_map_png,
        "pore_map_tif": pore_map_tif,
        "pore_map_below_1_count": pore_map_below_1_count,
        "pore_map_below_2_count": pore_map_below_2_count,
        "pore_map_below_3_count": 0,
        # Legacy aliases.
        "pore_map_low_count": pore_map_below_1_count,
        "pore_map_high_count": pore_map_below_2_count,
        "all_pore_map_png": all_pore_map_png,
        "all_pore_map_tif": all_pore_map_tif,
        "all_pore_map_count": all_pore_map_count,
        "all_pore_map_min_epd_mm": all_pore_map_min_epd_mm,
        "all_pore_map_max_epd_mm": all_pore_map_max_epd_mm,
        "sample_size_text": sample_size_text_value,
        "report_scale_method": settings.get("_effective_report_scale_method", settings.get("report_scale_method", "Needle scale")),
        "report_imaging_software": settings.get("report_imaging_software", "Swift Imaging 3.0"),
        "scale_source": settings.get("_effective_scale_source", settings.get("report_scale_method", "Needle scale")),
        "swift_magn_table_path": settings.get("_swift_magn_table_path", ""),
        "swift_magn_profile_name": settings.get("_swift_magn_profile_name", ""),
        "swift_magn_resolution_pixels_per_meter": settings.get("_swift_magn_resolution_pixels_per_meter", ""),
        "swift_magn_mm_per_pixel": settings.get("_swift_magn_mm_per_pixel", ""),
        "swift_magn_um_per_pixel": settings.get("_swift_magn_um_per_pixel", ""),
        "bad_image_status": bad_image_status,
        "bad_image_issues": bad_image_issues,
        "step_notes": step_notes,
        "threshold_min": settings["threshold_min"],
        "threshold_max": settings["threshold_max"],
        "threshold_force_8bit_numbers": settings.get("threshold_force_8bit_numbers", True),
        "threshold_input_mode": threshold_input_mode_label(settings.get("threshold_force_8bit_numbers", True)),
        "threshold_min_gray": settings.get("_threshold_actual_min_gray", ""),
        "threshold_max_gray": settings.get("_threshold_actual_max_gray", ""),
        "threshold_min_percent": settings.get("_threshold_histogram_min_percent", ""),
        "threshold_max_percent": settings.get("_threshold_histogram_max_percent", ""),
        "threshold_histogram_selected_percent": settings.get("_threshold_histogram_selected_percent", ""),
        "threshold_percent_basis": settings.get("_threshold_percent_basis", "Cumulative histogram of the preprocessed 8-bit threshold source"),
        "set_measurements_options": build_set_measurements_options(settings),
        "beast_mode_enabled": bool(settings.get("beast_mode_enabled", False)),
        "small_epd_cutoff": settings["small_epd_cutoff"],
        "report_pore_map_background": settings.get("report_pore_map_background", "Original image"),
        "report_pore_map_marker_radius": settings.get("report_pore_map_low_marker_radius", 8),
        "report_pore_map_low_marker_radius": settings.get("report_pore_map_low_marker_radius", 8),
        "report_pore_map_high_marker_radius": settings.get("report_pore_map_high_marker_radius", 14),
        "report_pore_map_opacity_percent": settings.get("report_pore_map_opacity_percent", 70.0),
        "report_pore_map_high_cutoff": settings.get("report_pore_map_high_cutoff", 0.025),
        "epd_cutoff_1": settings["epd_cutoff_1"],
        "epd_cutoff_2": settings["epd_cutoff_2"],
        "epd_between_preset": settings.get("epd_between_preset", DEFAULTS["epd_between_preset"]),
        "epd_between_low": settings.get("epd_between_low", DEFAULTS["epd_between_low"]),
        "epd_between_high": settings.get("epd_between_high", DEFAULTS["epd_between_high"]),
        "epd_between_manual_high": settings.get("epd_between_manual_high", settings.get("epd_between_high", DEFAULTS["epd_between_high"])),
        "epd_between_auto_high_enabled": False,
        "epd_between_auto_offset_um": 0.0,
        "epd_between_high_source": settings.get("epd_between_high_source", "Custom"),
        # Legacy v114 aliases synchronized to the active band.
        "epd_band_1_low": settings.get("epd_between_low", DEFAULTS["epd_between_low"]),
        "epd_band_1_high": settings.get("epd_between_high", DEFAULTS["epd_between_high"]),
        "epd_band_2_low": settings.get("epd_between_low", DEFAULTS["epd_between_low"]),
        "epd_band_2_high": settings.get("epd_between_high", DEFAULTS["epd_between_high"]),
        "epd_band_3_low": settings.get("epd_between_low", DEFAULTS["epd_between_low"]),
        "epd_band_3_high": settings.get("epd_between_high", DEFAULTS["epd_between_high"]),
        "circ_cutoff": settings["circ_cutoff"],
        "process_pipeline_order": settings.get("process_pipeline_order", ""),
        "process_pipeline_summary": processing_pipeline_summary(settings),
        "process_pipeline_steps": pipeline_steps_from_settings(settings),
        "median_enabled": settings.get("median_enabled", False),
        "median_radius": settings.get("median_radius", ""),
        "contrast_enabled": settings.get("contrast_enabled", False),
        "bandpass_enabled": settings.get("bandpass_enabled", False),
        "bandpass_large": settings.get("bandpass_large", ""),
        "bandpass_small": settings.get("bandpass_small", ""),
        "clahe_enabled": settings.get("clahe_enabled", False),
        "clahe_blocksize": settings.get("clahe_blocksize", ""),
        "clahe_maximum": settings.get("clahe_maximum", ""),
        "binary_enabled": settings.get("binary_enabled", False),
        "binary_fill_holes": settings.get("binary_fill_holes", False),
        "binary_watershed": settings.get("binary_watershed", False),
        "binary_despeckle_iterations": settings.get("binary_despeckle_iterations", 0),
        "binary_open_iterations": settings.get("binary_open_iterations", 0),
        "binary_close_iterations": settings.get("binary_close_iterations", 0),
        "binary_erode_iterations": settings.get("binary_erode_iterations", 0),
        "binary_dilate_iterations": settings.get("binary_dilate_iterations", 0),
        "binary_minimum_radius": settings.get("binary_minimum_radius", 0.0),
        "binary_maximum_radius": settings.get("binary_maximum_radius", 0.0),
        "binary_operation_order": settings.get("binary_operation_order", "")
    }

# ======================================================
# FINAL WINDOW CLEANUP HELPER
# ======================================================

def close_imagej_windows_when_finished():
    # Closes open image windows and common non-image windows created by ImageJ processing.
    # This intentionally does not try to close JMP, because JMP is a separate program.
    try:
        ids = WindowManager.getIDList()
        if ids is not None:
            for image_id in ids:
                try:
                    imp = WindowManager.getImage(image_id)
                    if imp is not None:
                        imp.changes = False
                        imp.close()
                except:
                    pass
    except:
        pass

    try:
        IJ.run("Clear Results")
    except:
        pass

    try:
        frames = WindowManager.getNonImageWindows()
        if frames is not None:
            for frame in frames:
                try:
                    title = str(frame.getTitle())

                    # Do not dispose the main ImageJ/Fiji application frame.
                    if title == "ImageJ" or title == "Fiji":
                        continue

                    frame.dispose()
                except:
                    pass
    except:
        pass

# ======================================================
# JMP LAUNCH AND BATCH HELPERS
# ======================================================

BEAST_LOG_HEADERS = [
    "Timestamp", "Elapsed Seconds", "Phase", "Event", "Run Order", "Image", "Run Label",
    "Status", "JMP Active", "JMP Completed", "JMP Failed", "Details"
]


def beast_log_path(output_root):
    return os.path.join(output_root, "BEAST_MODE_Detailed_Log.csv")


def beast_checkpoint_path(output_root):
    return os.path.join(output_root, "BEAST_MODE_Checkpoint.csv")


def init_beast_log(output_root, settings, total_runs):
    path = beast_log_path(output_root)
    write_csv(path, BEAST_LOG_HEADERS, [], int(settings.get("csv_decimals", 9)))
    settings["_beast_start_time"] = time.time()
    append_beast_log(path, settings, "SYSTEM", "START", 0, None, "RUNNING", 0, 0, 0,
                     "Total runs=" + str(total_runs) + "; parallel JMP=" + str(settings.get("beast_jmp_parallel_instances", 10)))
    return path


def append_beast_log(path, settings, phase, event, run_order, run, status, jmp_active, jmp_completed, jmp_failed, details):
    try:
        timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
        elapsed = time.time() - float(settings.get("_beast_start_time", time.time()))
        image_name = ""
        run_label = ""
        if run is not None:
            image_name = str(run.get("image_name", os.path.basename(str(run.get("image_path", "")))))
            run_label = str(run.get("run_label", ""))
        row = [timestamp, elapsed, phase, event, run_order, image_name, run_label, status,
               jmp_active, jmp_completed, jmp_failed, details]
        f = open(path, "a")
        try:
            f.write(",".join([csv_escape(v) for v in row]) + "\n")
            f.flush()
        finally:
            f.close()
    except Exception as e:
        IJ.log("BEAST MODE log write failed: " + str(e))


def write_beast_checkpoint(output_root, results, settings):
    rows = []
    ordered = sorted(list(results), key=lambda r: int(r.get("run_order_index", 0)))
    for run in ordered:
        rows.append([
            run.get("run_order_index", ""), run.get("image_path", ""), run.get("run_label", ""),
            run.get("run_dir", ""), run.get("jsl_file", ""), run.get("particle_count", ""),
            run.get("imagej_status", ""), run.get("imagej_elapsed_sec", ""),
            run.get("jmp_status", "NOT_STARTED"), run.get("jmp_elapsed_sec", ""),
            run.get("imagej_elapsed_sec", 0.0) + run.get("jmp_elapsed_sec", 0.0) if isinstance(run.get("imagej_elapsed_sec", 0.0), (int, float)) and isinstance(run.get("jmp_elapsed_sec", 0.0), (int, float)) else "",
            run.get("jmp_error", ""),
            run.get("final_summary_csv", ""), run.get("jmp_done_file", "")
        ])
    path = beast_checkpoint_path(output_root)
    write_csv(path, [
        "Run Order", "Image", "Run Label", "Run Folder", "JMP Script", "Particle Count",
        "ImageJ Status", "ImageJ Elapsed Seconds", "JMP Status", "JMP Elapsed Seconds", "Total Elapsed Seconds", "JMP Error",
        "Final Summary CSV", "JMP Done File"
    ], rows, int(settings.get("csv_decimals", 9)))
    return path


def process_is_alive(process):
    try:
        return bool(process.isAlive())
    except:
        try:
            process.exitValue()
            return False
        except:
            return True


def destroy_process_safely(process, force=False):
    if process is None:
        return
    try:
        if not process_is_alive(process):
            return
    except:
        pass
    try:
        process.destroy()
    except:
        pass
    if force:
        time.sleep(0.25)
        try:
            if process_is_alive(process):
                process.destroyForcibly()
        except:
            try:
                process.destroy()
            except:
                pass


def jmp_beast_outputs_exist(run, settings=None):
    refresh_jmp_output_paths(run)
    core_ready = (
        path_exists(run.get("final_summary_csv", "")) and
        path_exists(run.get("jmp_done_file", "")) and
        path_exists(run.get("raw_all_pores_csv", ""))
    )
    if not core_ready:
        return False
    if settings is not None and bool(settings.get("beast_create_graph_word_report", False)):
        return (
            path_exists(run.get("hist_epd_png", "")) and
            path_exists(run.get("hist_round_png", "")) and
            path_exists(run.get("hist_circ_png", ""))
        )
    return True


def _jmp_powershell_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def launch_beast_jmp_worker(run, jmp_exe, settings=None):
    jsl_path = str(run.get("jsl_file", ""))
    if jsl_path == "" or not File(jsl_path).exists():
        raise Exception("JMP script does not exist: " + jsl_path)

    settings = settings or {}
    run_dir = str(run.get("run_dir", os.path.dirname(jsl_path)))
    minimized = bool(settings.get("beast_jmp_minimized_launch_enabled", True))
    isolated_temp = bool(settings.get("beast_jmp_isolated_temp_enabled", True))

    cmd = ArrayList()
    if os.name == "nt" and minimized:
        window_style = "Minimized"
        ps = (
            "$ErrorActionPreference='Stop'; "
            "$p=Start-Process -FilePath " + _jmp_powershell_quote(jmp_exe) +
            " -ArgumentList @(" + _jmp_powershell_quote(jsl_path) + ")" +
            " -WindowStyle " + window_style + " -PassThru; "
            "$p.WaitForExit(); exit $p.ExitCode"
        )
        cmd.add("powershell.exe")
        cmd.add("-NoProfile")
        cmd.add("-NonInteractive")
        cmd.add("-ExecutionPolicy")
        cmd.add("Bypass")
        cmd.add("-WindowStyle")
        cmd.add("Hidden")
        cmd.add("-Command")
        cmd.add(ps)
    else:
        cmd.add(str(jmp_exe))
        cmd.add(jsl_path)

    builder = ProcessBuilder(cmd)
    try:
        builder.directory(File(os.path.dirname(str(jmp_exe))))
    except:
        pass

    if isolated_temp:
        try:
            worker_temp = os.path.join(run_dir, "JMP_Worker_TEMP")
            if not os.path.isdir(worker_temp):
                os.makedirs(worker_temp)
            environment = builder.environment()
            environment.put("TEMP", worker_temp)
            environment.put("TMP", worker_temp)
            environment.put("GDL_JMP_WORKER_RUN_DIR", run_dir)
            run["jmp_worker_temp_dir"] = worker_temp
        except Exception as e_temp:
            IJ.log("Could not isolate JMP worker TEMP folder: " + str(e_temp))

    try:
        builder.redirectErrorStream(True)
        jmp_console = os.path.join(run_dir, "JMP_console.log")
        builder.redirectOutput(File(jmp_console))
        run["jmp_console_log"] = jmp_console
    except:
        pass
    return builder.start()


def run_beast_jmp_pool(output_root, results, settings, progress_ui, errors):
    ordered = sorted(list(results), key=lambda r: int(r.get("run_order_index", 0)))
    total = len(ordered)
    log_path = beast_log_path(output_root)
    max_parallel = int(settings.get("beast_jmp_parallel_instances", 10))
    max_parallel = max(1, min(32, max_parallel))
    timeout_sec = float(settings.get("beast_jmp_timeout_sec", 900))
    exit_grace_sec = float(settings.get("beast_jmp_exit_grace_sec", 8))
    stagger_sec = float(settings.get("beast_jmp_launch_stagger_sec", 0.5))
    force_close = bool(settings.get("beast_force_close_jmp_after_run", True))
    continue_on_error = bool(settings.get("beast_continue_on_jmp_error", True))
    retry_count = max(0, int(settings.get("beast_jmp_retry_count", 1)))
    retry_delay_sec = max(0.0, float(settings.get("beast_jmp_retry_delay_sec", 1.0)))
    checkpoint_every = max(1, int(settings.get("beast_checkpoint_every_runs", 10)))

    jmp_exe = find_jmp_exe(settings)
    if jmp_exe == "":
        msg = "BEAST MODE could not find JMP executable. No JMP workers were launched."
        errors.append(msg)
        IJ.log(msg)
        append_beast_log(log_path, settings, "JMP", "NO_EXECUTABLE", 0, None, "FAILED", 0, 0, total, msg)
        for run in ordered:
            run["jmp_status"] = "FAILED_NO_EXECUTABLE"
            run["jmp_error"] = msg
        write_beast_checkpoint(output_root, ordered, settings)
        return {"launched": 0, "completed": 0, "failed": total, "skipped": 0, "canceled": 0, "max_active_observed": 0}

    pending = []
    active = []
    launched = 0
    completed = 0
    failed = 0
    skipped = 0
    canceled = 0
    for run in ordered:
        if str(run.get("imagej_status", "COMPLETED")) != "COMPLETED" or str(run.get("jsl_file", "")).strip() == "":
            run["jmp_status"] = "NOT_RUN_IMAGEJ_FAILED"
            if str(run.get("jmp_error", "")).strip() == "":
                run["jmp_error"] = "JMP was not launched because ImageJ processing failed."
            skipped += 1
            completed += 1
            append_beast_log(log_path, settings, "JMP", "SKIP_IMAGEJ_FAILED", int(run.get("run_order_index", 0)), run,
                             run["jmp_status"], 0, completed, failed, run.get("jmp_error", ""))
        else:
            pending.append(run)
    abort_queue = False
    cancel_queue = False
    last_checkpoint_done = -1

    max_active_observed = 0
    append_beast_log(log_path, settings, "JMP", "POOL_START", 0, None, "RUNNING", 0, 0, 0,
                     "Strict worker limit=" + str(max_parallel) + "; timeout=" + str(timeout_sec) + " sec")

    while len(pending) > 0 or len(active) > 0:
        if global_cancel_requested():
            abort_queue = True
            cancel_queue = True
        while not abort_queue and not global_cancel_requested() and len(pending) > 0 and len(active) < max_parallel:
            run = pending.pop(0)
            order_index = int(run.get("run_order_index", 0))
            refresh_jmp_output_paths(run)
            if jmp_beast_outputs_exist(run, settings):
                run["jmp_status"] = "SKIPPED_OUTPUTS_EXIST"
                run["jmp_elapsed_sec"] = 0.0
                run["jmp_end_timestamp"] = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
                skipped += 1
                completed += 1
                append_beast_log(log_path, settings, "JMP", "SKIP_EXISTING", order_index, run, run["jmp_status"],
                                 len(active), completed, failed, "Final summary and JMP_DONE already exist")
                continue
            try:
                proc = launch_beast_jmp_worker(run, jmp_exe, settings)
                job = {
                    "run": run,
                    "process": proc,
                    "start": time.time(),
                    "done_seen": None
                }
                active.append(job)
                if len(active) > max_parallel:
                    # Defensive invariant: never permit more JMP processes than requested.
                    destroy_process_safely(proc, True)
                    active.pop()
                    raise Exception("Internal JMP worker-limit violation: active=" + str(len(active) + 1) + ", limit=" + str(max_parallel))
                max_active_observed = max(max_active_observed, len(active))
                register_active_process(proc)
                launched += 1
                run["jmp_status"] = "RUNNING"
                run["jmp_start_timestamp"] = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
                run["jmp_error"] = ""
                append_beast_log(log_path, settings, "JMP", "LAUNCH", order_index, run, "RUNNING",
                                 len(active), completed, failed, run.get("jsl_file", ""))
                IJ.log("BEAST JMP launch " + str(order_index) + "/" + str(total) + ": " + str(run.get("jsl_file", "")))
                if stagger_sec > 0:
                    time.sleep(stagger_sec)
            except Exception as e:
                attempts = int(run.get("_beast_jmp_retry_attempts", 0))
                if attempts < retry_count and not global_cancel_requested():
                    attempts += 1
                    run["_beast_jmp_retry_attempts"] = attempts
                    run["jmp_status"] = "RETRY_QUEUED"
                    run["jmp_error"] = "JMP launch failed: " + str(e) + ". Retry " + str(attempts) + "/" + str(retry_count) + " queued."
                    pending.append(run)
                    append_beast_log(log_path, settings, "JMP", "LAUNCH_RETRY_QUEUED", order_index, run, run["jmp_status"],
                                     len(active), completed, failed, run["jmp_error"])
                    if retry_delay_sec > 0:
                        time.sleep(retry_delay_sec)
                    continue
                failed += 1
                run["jmp_status"] = "FAILED_TO_LAUNCH"
                run["jmp_error"] = str(e)
                msg = "BEAST JMP launch failed for run " + str(order_index) + ": " + str(e)
                errors.append(msg)
                IJ.log(msg)
                append_beast_log(log_path, settings, "JMP", "LAUNCH_ERROR", order_index, run, run["jmp_status"],
                                 len(active), completed, failed, str(e))
                if not continue_on_error:
                    abort_queue = True
                    break

        now = time.time()
        survivors = []
        for job in active:
            run = job["run"]
            proc = job["process"]
            order_index = int(run.get("run_order_index", 0))
            elapsed = now - float(job["start"])
            if cancel_queue or global_cancel_requested():
                cancel_queue = True
                abort_queue = True
                destroy_process_safely(proc, True)
                unregister_active_process(proc)
                canceled += 1
                run["jmp_status"] = "CANCELED"
                run["jmp_elapsed_sec"] = elapsed
                run["jmp_end_timestamp"] = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
                run["jmp_error"] = "Canceled by user."
                append_beast_log(log_path, settings, "JMP", "CANCELED_ACTIVE", order_index, run, "CANCELED",
                                 max(0, len(active) - 1), completed, failed, run["jmp_error"])
                continue
            outputs_ready = jmp_beast_outputs_exist(run, settings)
            alive = process_is_alive(proc)

            if outputs_ready:
                if job.get("done_seen") is None:
                    job["done_seen"] = now
                    append_beast_log(log_path, settings, "JMP", "OUTPUTS_READY", order_index, run, "FINISHING",
                                     len(active), completed, failed, "JMP_DONE and Final_Summary.csv found")
                grace_elapsed = now - float(job.get("done_seen", now))
                if (not alive) or grace_elapsed >= exit_grace_sec:
                    if alive and force_close:
                        destroy_process_safely(proc, True)
                    unregister_active_process(proc)
                    completed += 1
                    run["jmp_status"] = "COMPLETED"
                    run["jmp_elapsed_sec"] = elapsed
                    run["jmp_end_timestamp"] = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
                    run["jmp_error"] = ""
                    append_beast_log(log_path, settings, "JMP", "COMPLETE", order_index, run, "COMPLETED",
                                     max(0, len(active) - 1), completed, failed,
                                     "Elapsed=" + format_elapsed_seconds(elapsed) + ("; forced process close" if alive and force_close else ""))
                    continue
                survivors.append(job)
                continue

            if not alive:
                unregister_active_process(proc)
                attempts = int(run.get("_beast_jmp_retry_attempts", 0))
                retry_reason = "JMP process exited before Final_Summary.csv and JMP_DONE.txt were both created."
                if attempts < retry_count and not global_cancel_requested():
                    attempts += 1
                    run["_beast_jmp_retry_attempts"] = attempts
                    run["jmp_status"] = "RETRY_QUEUED"
                    run["jmp_elapsed_sec"] = elapsed
                    run["jmp_error"] = retry_reason + " Retry " + str(attempts) + "/" + str(retry_count) + " queued."
                    pending.append(run)
                    append_beast_log(log_path, settings, "JMP", "EARLY_EXIT_RETRY_QUEUED", order_index, run, run["jmp_status"],
                                     max(0, len(active) - 1), completed, failed, run["jmp_error"])
                    if retry_delay_sec > 0:
                        time.sleep(retry_delay_sec)
                    continue
                failed += 1
                run["jmp_status"] = "FAILED_EARLY_EXIT"
                run["jmp_elapsed_sec"] = elapsed
                run["jmp_end_timestamp"] = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
                run["jmp_error"] = retry_reason
                msg = "BEAST JMP early exit for run " + str(order_index)
                errors.append(msg)
                append_beast_log(log_path, settings, "JMP", "EARLY_EXIT", order_index, run, run["jmp_status"],
                                 max(0, len(active) - 1), completed, failed, run["jmp_error"])
                if not continue_on_error:
                    abort_queue = True
                continue

            if elapsed > timeout_sec:
                destroy_process_safely(proc, True)
                unregister_active_process(proc)
                attempts = int(run.get("_beast_jmp_retry_attempts", 0))
                retry_reason = "JMP exceeded timeout of " + str(timeout_sec) + " seconds."
                if attempts < retry_count and not global_cancel_requested():
                    attempts += 1
                    run["_beast_jmp_retry_attempts"] = attempts
                    run["jmp_status"] = "RETRY_QUEUED"
                    run["jmp_elapsed_sec"] = elapsed
                    run["jmp_error"] = retry_reason + " Retry " + str(attempts) + "/" + str(retry_count) + " queued."
                    pending.append(run)
                    append_beast_log(log_path, settings, "JMP", "TIMEOUT_RETRY_QUEUED", order_index, run, run["jmp_status"],
                                     max(0, len(active) - 1), completed, failed, run["jmp_error"])
                    if retry_delay_sec > 0:
                        time.sleep(retry_delay_sec)
                    continue
                failed += 1
                run["jmp_status"] = "FAILED_TIMEOUT"
                run["jmp_elapsed_sec"] = elapsed
                run["jmp_end_timestamp"] = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(Date())
                run["jmp_error"] = retry_reason
                msg = "BEAST JMP timeout for run " + str(order_index) + " after " + format_elapsed_seconds(elapsed)
                errors.append(msg)
                append_beast_log(log_path, settings, "JMP", "TIMEOUT", order_index, run, run["jmp_status"],
                                 max(0, len(active) - 1), completed, failed, run["jmp_error"])
                if not continue_on_error:
                    abort_queue = True
                continue

            survivors.append(job)

        active = survivors

        if abort_queue:
            abort_text = "Canceled by user." if cancel_queue else "JMP queue aborted after an error."
            active_status = "CANCELED" if cancel_queue else "ABORTED"
            pending_status = "NOT_LAUNCHED_CANCELED" if cancel_queue else "NOT_LAUNCHED_ABORTED"
            for job in active:
                proc_abort = job.get("process")
                destroy_process_safely(proc_abort, True)
                unregister_active_process(proc_abort)
                run = job.get("run")
                if run is not None:
                    if cancel_queue:
                        canceled += 1
                    else:
                        failed += 1
                    run["jmp_status"] = active_status
                    run["jmp_error"] = abort_text
            active = []
            for run in pending:
                if cancel_queue:
                    canceled += 1
                else:
                    failed += 1
                run["jmp_status"] = pending_status
                run["jmp_error"] = abort_text
            if cancel_queue:
                append_beast_log(log_path, settings, "JMP", "USER_CANCEL", 0, None, "CANCELED", 0, completed, failed, abort_text)
            pending = []

        done_for_progress = completed + failed + canceled
        update_beast_progress_popup(progress_ui, "BEAST MODE: JMP worker pool",
                                    "Running up to " + str(max_parallel) + " separate JMP processes",
                                    total, total, done_for_progress, len(active), len(errors), 0, 1)
        IJ.showStatus("BEAST JMP: " + str(done_for_progress) + "/" + str(total) + " finished; " + str(len(active)) + " active")
        maybe_tile_visible_jmp_windows(settings, False)

        if done_for_progress > 0 and done_for_progress % checkpoint_every == 0 and done_for_progress != last_checkpoint_done:
            write_beast_checkpoint(output_root, ordered, settings)
            last_checkpoint_done = done_for_progress

        if len(pending) > 0 or len(active) > 0:
            time.sleep(0.5)

    write_beast_checkpoint(output_root, ordered, settings)
    pool_status = "CANCELED" if cancel_queue else "COMPLETED"
    append_beast_log(log_path, settings, "JMP", "POOL_COMPLETE", 0, None, pool_status, 0, completed, failed,
                     "Configured limit=" + str(max_parallel) + "; max active observed=" + str(max_active_observed) +
                     "; launched=" + str(launched) + "; completed/skipped=" + str(completed) +
                     "; failed=" + str(failed) + "; canceled=" + str(canceled))
    maybe_tile_visible_jmp_windows(settings, True)
    return {"launched": launched, "completed": completed, "failed": failed, "skipped": skipped, "canceled": canceled, "max_active_observed": max_active_observed}
