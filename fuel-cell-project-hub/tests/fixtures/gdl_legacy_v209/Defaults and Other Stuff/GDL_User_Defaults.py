# GDL USER DEFAULTS - v209
# ================================================================
# This is the ONE file intended for routine default-value changes.
# Edit values on the right side, save the file, then restart Fiji.
# Use Python spelling: True / False, quoted text, and numeric values.
# Keep commas at the ends of dictionary lines.
# ================================================================

APPLICATION_VERSION = "v209"
APPLICATION_NAME = "YOURE A BETA GDL Analysis"
DEFAULT_CODE_FOLDER = "GDL_code"
CODE_MODULE_FILES = ['01_Core_Imports_Helpers.py', '02_User_Interface_Pages.py', '03_User_Interface_Settings.py', '04_Image_Processing_Sweeps.py', '05_Reports_Manual_Tools_Pore_Maps.py', '06A_Large_Pore_Repair.py', '06B_Fiber_Fixer.py', '06_Threshold_Analysis_JMP.py', '07_Run_Engine_Exports.py', '08_Workbook_JMP_Launch_Helpers.py', '09_BEAST_Workers_Main.py']

# Startup search defaults. startup_paths.ini can still override these.
DEFAULT_FIJI_LAUNCHERS = [
    r"C:/Fixture/GDL",
    r"C:/Fixture/GDL",
    r"C:/Fixture/GDL",
    r"C:/Fixture/GDL",
]
DEFAULT_EXTRA_USER_ROOTS = "C:/Fixture/GDL;C:/Fixture/GDL;C:/Fixture/GDL;C:/Fixture/GDL"

# Executable/report location defaults.
JMP_EXE_DEFAULT = "C:/Program Files/JMP/JMPSTUDENT/19/jmp.exe"
ALL_REPORTS_FOLDER_MICHELSON = "C:/Fixture/GDL"
ALL_REPORTS_FOLDER_VGOLF = "C:/Fixture/GDL"

COMMON_JMP_PATHS = [
    "C:/Program Files/JMP/JMPSTUDENT/19/jmp.exe",
    "C:/Program Files/JMP/JMPSTUDENT/20/jmp.exe",
    "C:/Program Files/JMP/JMP/19/jmp.exe",
    "C:/Program Files/JMP/JMP/18/jmp.exe",
    "C:/Program Files/JMP/JMP/17/jmp.exe",
    "C:/Program Files/JMP/JMP/16/jmp.exe",
    "C:/Program Files/SAS/JMP/19/jmp.exe",
    "C:/Program Files/SAS/JMP/18/jmp.exe",
    "C:/Program Files/SAS/JMP/17/jmp.exe",
    "C:/Program Files/SAS/JMP/16/jmp.exe",
    "C:/Program Files/SAS/JMPPRO/19/jmp.exe",
    "C:/Program Files/SAS/JMPPRO/18/jmp.exe",
    "C:/Program Files/SAS/JMPPRO/17/jmp.exe",
    "C:/Program Files/SAS/JMPPRO/16/jmp.exe"
]

# Main application defaults. Every startup-card, processing, sweep, report,
# BEAST, measurement, pore-map, threshold, JMP, and workbook default lives here.
DEFAULTS = {
    # General / file behavior
    "batch_enabled": True,
    "batch_live_image_report_folders_enabled": False,

    # YOURE A BETA image capture fork
    # Captures frames from the active ImageJ image/camera preview window, sets scale from one scale-bar frame,
    # saves calibrated TIFFs, and can optionally run the normal analysis from those TIFFs.
    "image_capture_enabled": False,
    "image_capture_mode": "Capture scaled TIFFs only, stop",
    "image_capture_count": 1,
    "image_capture_batch_name": "",
    "image_capture_scale_known_length_mm": 0.5,
    "image_capture_save_scale_frame": True,
    "image_capture_keep_captured_windows_open": False,
    "image_capture_try_open_live_view": True,
    "image_capture_live_view_command": "Auto-detect common live-view command",
    "image_capture_show_live_view_directions": True,
    "include_subfolders": False,
    "crop_count": 0,
    "crop_mode": "Manual select",
    "crop_prompt_each_image": False,
    "fancy_progress_enabled": True,
    "auto_scale_unscaled_enabled": True,
    "auto_scale_known_length_mm": 0.5,
    "auto_scale_min_component_pixels": 25,
    "auto_scale_red_min": 120,
    "auto_scale_red_dominance": 1.4,
    "auto_scale_red_margin": 30,
    "auto_scale_blue_min": 80,
    "auto_scale_blue_dominance": 1.25,
    "auto_scale_blue_margin": 20,
    "auto_scale_orange_min": 90,
    "auto_scale_orange_green_min": 35,
    "auto_scale_orange_blue_max": 170,
    "auto_scale_blue_ocr_enabled": False,
    "auto_scale_blue_search_padding_px": 260,
    "auto_scale_show_preview": True,
    "auto_scale_preview_padding_px": 80,
    "auto_scale_preview_zoom_factor": 3.0,
    "auto_scale_save_tif_enabled": True,
    "auto_scale_save_tif_subfolder_enabled": True,
    "auto_scale_replace_png_with_tif_enabled": False,
    "set_scale_only_mode": False,
    "set_scale_direct_enabled": False,
    "set_scale_direct_mm_per_pixel": 0.0,
    "set_scale_direct_pixels_per_mm": 0.0,

    # Swift Imaging 3.0 magnification-table scale bridge.
    # Put Imaging.magn beside the source images, in a parent folder, or in the
    # bundled Swift Magnification Tables folder. v199 reads all profiles in
    # one table (currently 4X and 10X) and shows them in a dropdown. AUTO uses
    # the only profile or matches a profile token in the image/folder name.
    "swift_magn_scale_enabled": True,
    "swift_magn_filename": "Imaging.magn",
    "swift_magn_profile_name": "AUTO",
    "swift_magn_search_parent_levels": 4,
    "swift_magn_use_bundle_fallback": True,
    "swift_magn_override_existing_scale": False,
    "close_windows_when_finished": True,
    # Closes only JMP windows/tables created by this generated JMP script. It does not close the whole JMP app.
    "close_jmp_windows_when_finished": True,

    # BEAST MODE: designed for unattended batches/sweeps with thousands of runs.
    # ImageJ processing remains sequential for stability; generated JMP scripts are then
    # processed by a bounded parallel worker pool. Results are retained in deterministic run order.
    "beast_mode_enabled": False,
    "beast_jmp_parallel_instances": 10,
    # Start JMP from the live Fiji completion queue instead of waiting for all Fiji jobs.
    "beast_jmp_streaming_enabled": True,
    "beast_jmp_safe_launch_enabled": True,
    "beast_jmp_minimized_launch_enabled": True,
    "beast_jmp_isolated_temp_enabled": True,
    "beast_jmp_retry_count": 2,
    "beast_jmp_retry_delay_sec": 1.0,
    "beast_jmp_start_after_fiji_runs": 15,
    # BEAST graph generation is independent from Word report grouping in v193.
    # Checked = run JMP and create graphs/histograms. Word report output is chosen
    # separately by beast_word_report_mode below.
    "beast_create_graph_word_report": True,
    "beast_word_report_mode": "Combined Word report",  # legacy mirror; v209 uses word_report_mode
    # Optional resilient acceleration. Workers run headlessly through Fiji/SciJava.
    # If any worker cannot start or finish, missing jobs are requeued to the current Fiji controller.
    "beast_parallel_fiji_enabled": True,
    # Default ON so each external worker opens a separate Fiji window. Uncheck for silent headless workers.
    "beast_show_fiji_worker_windows": True,
    "beast_fiji_parallel_instances": 4,
    "beast_fiji_worker_timeout_sec": 21600,
    "beast_fiji_no_progress_timeout_sec": 900,
    # v195: once every assigned result has been published, the controller no longer waits forever
    # for a final worker snapshot or for the Fiji application process to close.
    "beast_fiji_finalize_grace_sec": 8,
    # If terminal job markers exist but a cloud-synced snapshot is missing, requeue only the
    # unpublished jobs after this grace period instead of appearing frozen.
    "beast_fiji_terminal_snapshot_grace_sec": 30,
    "beast_fiji_launch_stagger_sec": 1.0,
    "beast_fiji_worker_startup_timeout_sec": 120,
    "beast_fiji_worker_launch_retries": 2,
    # v209 dynamic disposable agents: every external Fiji process owns one exact run.
    # A failed/stalled process retries only that run, and a free slot immediately pulls the next
    # queued job. Heartbeat catches dead JVMs quickly; content-stall detection has a safe floor
    # so legitimate long pore-repair searches are not killed.
    "beast_fiji_runtime_retries": 4,
    "beast_fiji_heartbeat_interval_sec": 10,
    "beast_fiji_heartbeat_timeout_sec": 60,
    "beast_fiji_claim_timeout_sec": 120,
    "beast_fiji_job_timeout_sec": 3600,
    "beast_require_parallel_fiji": False,
    "beast_fiji_fallback_to_controller": True,
    # Run actual external Fiji and JMP launch probes before the progress window opens.
    # This catches blocked dialogs, bad executable paths, and launcher syntax before a long batch starts.
    "beast_preflight_enabled": True,
    "beast_preflight_timeout_sec": 60,
    "beast_jmp_timeout_sec": 900,
    "beast_jmp_exit_grace_sec": 8,
    "beast_jmp_launch_stagger_sec": 1.0,
    "beast_force_close_jmp_after_run": True,
    "beast_continue_on_imagej_error": True,
    "beast_continue_on_jmp_error": True,
    "beast_max_total_runs": 100000,
    "beast_checkpoint_every_runs": 10,
    "beast_organize_windows_enabled": True,
    "beast_organize_jmp_windows_enabled": False,
    # Normally forced in BEAST MODE. The optional graph-report checkbox can turn Graph Builder/histogram PNGs back on.
    "beast_disable_histograms_and_graphs": False,
    # Forced in BEAST MODE: one XLSX with All Pore Data, Run Overview, and Revised Summary sheets.
    "beast_two_sheet_workbook_enabled": True,

    # Word report creation
    "create_word_report": True,
    "open_word_report_when_done": False,
    # Image-storage policy. All three are OFF by default to preserve the existing v199 behavior.
    # no_lossless_images_in_reports: DOCX media is converted to temporary JPEG before embedding.
    # dont_save_lossless_generated_images: after report/XLSX export, generated run PNG/TIFF images
    # are replaced by JPEG versions. Calibrated input/capture/Scaled image TIFFs are never touched.
    # no_lossless_images_at_all: master override that enables both behaviors above.
    "no_lossless_images_in_reports": False,
    "dont_save_lossless_generated_images": False,
    "no_lossless_images_at_all": False,
    # Existing full-lossless behavior remains the default when the three controls above are OFF.
    "report_launch_all_jmp": True,
    "report_wait_for_jmp": True,
    "report_wait_timeout_sec": 180,
    "report_title": "GDL Image Analysis Report",
    "report_sample_name": "",
    # Scale-method labels printed in Word reports, summary tables, run notes, and
    # BEAST revised-summary output. Add additional labels to this list as needed.
    "report_scale_method_options": ["Needle scale", "Old Plastic", "New Glass"],
    "report_scale_method": "Needle scale",
    # Image-acquisition software metadata printed in Word reports, manifests,
    # run notes, and BEAST revised-summary output. Add more labels as needed.
    "report_imaging_software_options": ["Swift Imaging 3.0"],
    "report_imaging_software": "Swift Imaging 3.0",
    "report_include_strand_heat_map": True,
    "report_save_strand_heat_map": True,
    # Report file naming and optional Excel summary export.
    "report_filename_mode": "Auto name: image + processing steps",
    "export_main_summary_xls": True,
    "summary_xls_destination": "All available All Reports folders",
    "summary_xls_custom_folder": "",
    # v209: reports-only recovery can start from an output folder or an already generated YOURE A BETA DOCX.
    "reports_only_recovery_mode": False,
    "reports_only_source_mode": "Existing failed/incomplete output folder",
    "reports_only_output_mode": "Use normal Report card selection",
    # Report state is always checkpointed during processing so cancel/failure can finalize completed work.
    "always_finalize_partial_report": True,
    "report_main_image_width_in": 2.05,
    "report_hist_image_width_in": 4.25,
    "report_pore_map_width_in": 5.5,
    # DOCX page sizing. Body pages use portrait Letter by default; the final summary page uses landscape Letter.
    "docx_body_page_width_in": 8.5,
    "docx_body_page_height_in": 11.0,
    "docx_body_margin_in": 0.5,
    "docx_summary_page_width_in": 22.0,
    "docx_summary_page_height_in": 8.5,
    "docx_summary_margin_in": 0.3,
    # The same six-mode list is used by normal mode and BEAST MODE. The selected
    # dropdown is authoritative; the legacy create_word_report boolean is retained
    # only for old presets and internal compatibility.
    "word_report_mode_options": [
        "No Word reports",
        "Combined Word report",
        "Individual by image",
        "Completely separate individual reports",
        "Individual by image + combined",
        "Completely separate individual reports + combined"
    ],
    "word_report_mode": "Combined Word report",

    # Threshold-selection reports. OFF by default. When enabled, the script
    # creates one full combined DOCX for the complete batch and a separate
    # folder containing one selected DOCX for every image/threshold group.
    # Within each image/threshold group, the median-radius run with the lowest
    # weighted normalized distance to the enabled target criteria is selected.
    "threshold_selection_reports_enabled": False,
    "threshold_selection_create_full_combined": True,
    "threshold_selection_folder_name": "Selected_Threshold_Reports",
    "threshold_selection_importance_min": 1,
    "threshold_selection_importance_max": 5,
    "threshold_selection_criterion_1_enabled": True,
    "threshold_selection_criterion_1_metric": "Area %",
    "threshold_selection_criterion_1_target": "",
    "threshold_selection_criterion_1_importance": 5,
    "threshold_selection_criterion_2_enabled": False,
    "threshold_selection_criterion_2_metric": "Average EPD (mm)",
    "threshold_selection_criterion_2_target": "",
    "threshold_selection_criterion_2_importance": 4,
    "threshold_selection_criterion_3_enabled": False,
    "threshold_selection_criterion_3_metric": "Max EPD (mm)",
    "threshold_selection_criterion_3_target": "",
    "threshold_selection_criterion_3_importance": 3,
    "threshold_selection_criterion_4_enabled": False,
    "threshold_selection_criterion_4_metric": "Summary pore count",
    "threshold_selection_criterion_4_target": "",
    "threshold_selection_criterion_4_importance": 2,
    "threshold_selection_criterion_5_enabled": False,
    "threshold_selection_criterion_5_metric": "Average circularity",
    "threshold_selection_criterion_5_target": "",
    "threshold_selection_criterion_5_importance": 1,
    "report_sweep_comparison_enabled": True,
    # Legacy compatibility flag. v193 report grouping is controlled by word_report_mode.
    "batch_sweep_reports_by_og_image": True,
    "batch_sweep_export_all_summaries_to_all_reports": True,
    "report_save_segmented_overlay_next_to_word": True,
    "report_segmented_overlay_fiber_color": "Red",
    "report_segmented_overlay_fiber_opacity_percent": 70.0,
    "report_segmented_overlay_annotation_opacity_percent": 85.0,
    "report_segmented_pores_overlay_opacity_percent": 30.0,
    "save_fiji_log_enabled": True,
    # The main pore map has two independent groups:
    # 1) low pores below the active JMP between-band upper limit (preset-controlled), and
    # 2) high pores above a fixed 25-micron cutoff that never changes with the preset.
    # Legacy single-radius aliases retain the small-pore value.
    "report_pore_marker_radius": 8,
    "report_pore_map_marker_radius": 8,
    "report_pore_map_opacity_percent": 70.0,
    "report_pore_map_low_cutoff": 0.007,
    "report_pore_map_high_cutoff": 0.025,
    "report_pore_map_low_marker_radius": 8,
    "report_pore_map_high_marker_radius": 14,
    # Default pore-map background is the untouched original image.
    "report_pore_map_background": "Original image",
    "report_pore_map_show_legend": False,
    "report_all_pore_map_enabled": False,
    "report_all_pore_map_show_legend": True,
    "report_all_pore_map_style": "EPD-sized red markers on white",
    "report_all_pore_map_gray_min": 60,
    "report_all_pore_map_gray_max": 220,
    "report_all_pore_map_min_radius_px": 2,
    # Custom overlay colors/styles
    "guide_largest_outline_color": "red",
    "guide_selected_outline_color": "green",
    "guide_outline_extra_pixels": 10,
    "guide_outline_line_width": 1,
    "segmented_largest_fill_color": "yellow",
    "segmented_selected_fill_color": "green",
    "segmented_outline_line_width": 3,
    "pore_map_band_1_color": "cyan",
    "pore_map_band_2_color": "orange",
    "pore_map_band_3_color": "magenta",
    # Legacy color keys retained for saved-preset compatibility.
    "pore_map_low_color": "cyan",
    "pore_map_high_color": "red",
    "highlight_largest_pore_in_segmented": True,
    # Manual measurement helper:
    # When enabled, after the automated analysis it opens an unfiltered original image
    # with a red circle around the analysis-detected largest pore. You then enter
    # the manually measured pore area, and the report compares manual EPD vs analysis EPD.
    "manual_measurements_enabled": False,
    "manual_largest_pore_enabled":False,
    "manual_largest_pore_count": 1,
    "manual_selected_pore_enabled": True,
    "manual_selected_pore_count": 1,
    # Under-trigger success popup portrait. Uncheck at startup for text-only mode.
    "manual_success_popup_show_picture": True,
    "manual_strand_measurement_enabled": False,
    "manual_strand_count": 1,
    "report_scale_bar_enabled": True,
    # Auto-fit scale bars are off by default; fixed report scale bar length is 100 microns (0.100 mm).
    "report_scale_bar_auto_fit_enabled": False,
    "report_scale_bar_target_fraction": 0.2,
    "report_scale_bar_round_to_mm": 0.05,
    # Normal fixed bar: 0.1 mm = 100 microns.
    "report_scale_bar_length_mm": 0.100,
    "report_scale_bar_thickness_px": 10,
    "report_scale_bar_margin_px": 20,
    "report_scale_bar_color": "yellow",
    "report_scale_bar_label_enabled": True,
    "report_scale_bar_text_color": "yellow",
    "report_scale_bar_text_outline_enabled": True,
    "report_scale_bar_text_outline_color": "black",
    "report_scale_bar_font_size_px": 36,
    "bad_image_detection_enabled": True,
    "popup_warning_summary_enabled": True,
    "scale_sanity_warning_enabled": True,
    "scale_sanity_min_image_area_mm2": 0.000001,
    "scale_sanity_max_image_area_mm2": 1000.0,
    "scale_sanity_min_pixel_size_mm": 0.000001,
    "scale_sanity_max_pixel_size_mm": 1.0,
    "particle_count_sanity_enabled": True,
    "particle_count_high_limit": 5000,
    "particle_count_change_warning_percent": 50.0,

    "launch_jmp": True,
    "max_jmp_launches": 10,
    "jmp_streaming_enabled": True,
    "jmp_start_after_fiji_runs": 15,
    "jmp_force_exit_after_run": True,
    "jmp_exe": JMP_EXE_DEFAULT,
    "csv_decimals": 9,
    "imagej_results_precision": 9,
    "docx_report_decimals": 9,
    "save_settings_as_default": False,
    "preset_name": "GDL_default",
    "save_named_preset": False,
    "load_named_preset": False,
    "open_output_folder_when_done": True,

    # Ordered processing pipeline. Duplicate operations are allowed and each occurrence
    # has independent parameters. Threshold is the required phase boundary: grayscale
    # operations run before it and binary-mask operations run after it.
    "process_pipeline_slot_count": 20,
    "process_pipeline_order": "8bit,median,contrast,bandpass,clahe,threshold",
    "process_pipeline_steps": [],

    # Legacy keys retained for saved presets, sweep compatibility, and older reports.
    "process_order": "8bit,median,contrast,bandpass,clahe",

    # ImageJ preprocessing
    "convert_8bit": True,
    "median_enabled": True,
    "median_radius": 2.0,

    "contrast_enabled": True,
    "contrast_saturated": 0.35,
    "contrast_normalize": True,
    "contrast_equalize": True,

    "bandpass_enabled": False,
    "bandpass_large": 40.0,
    "bandpass_small": 3.0,
    "bandpass_suppress": "None",
    "bandpass_tolerance": 5.0,
    "bandpass_autoscale": True,
    "bandpass_saturate": False,

    "clahe_enabled": False,
    "clahe_blocksize": 127,
    "clahe_histogram": 256,
    "clahe_maximum": 3.0,
    "clahe_fast": False,

    # Binary mask cleanup, applied after thresholding and before Analyze Particles.
    "binary_enabled": False,
    "binary_fill_holes": False,
    "binary_watershed": False,
    "binary_despeckle_iterations": 0,
    "binary_open_iterations": 0,
    "binary_close_iterations": 0,
    "binary_erode_iterations": 0,
    "binary_dilate_iterations": 0,
    "minimum_filter_radius": 0.0,
    "maximum_filter_radius": 0.0,
    "binary_minimum_radius": 0.0,  # legacy alias retained for saved presets
    "binary_maximum_radius": 0.0,  # legacy alias retained for saved presets
    "binary_operation_order": "despeckle,fill_holes,open,close,erode,dilate,watershed",

    # Fiber Fixer. OFF by default. It makes a lower-threshold copy, skeletonizes
    # the recovered fiber network into a thin wireframe, then burns that
    # wireframe back into the main segmented mask before large-pore repair.
    "fiber_fixer_enabled": False,
    "fiber_fixer_absolute_threshold_max": 40,
    "fiber_fixer_wire_width_px": 3,
    "fiber_fixer_save_wireframe_mask": True,
    "fiber_fixer_save_preview_overlay": True,

    # Conservative large-pore repair. OFF by default. When enabled, this runs after
    # threshold/binary cleanup and before Analyze Particles. It assumes black fibers
    # and white pores, then adds small black repairs only when one large parent pore
    # becomes exactly two substantial child pores.
    "large_pore_repair_enabled": False,
    "large_pore_repair_mode": "Review proposals",
    "large_pore_repair_min_parent_area_px": 10000,
    "large_pore_repair_largest_pore_limit": 25,
    "large_pore_repair_min_child_area_px": 2000,
    "large_pore_repair_min_smaller_child_fraction": 0.15,
    "large_pore_repair_max_larger_child_fraction": 0.85,
    "large_pore_repair_min_closing_radius_px": 1,
    "large_pore_repair_max_closing_radius_px": 10,
    "large_pore_repair_radius_step_px": 1,
    "large_pore_repair_min_area_px": 2,
    "large_pore_repair_max_area_px": 150,
    "large_pore_repair_max_fraction_of_parent": 0.01,
    "large_pore_repair_max_span_px": 25,
    "large_pore_repair_crop_margin_px": 12,
    "large_pore_repair_max_repairs_per_image": 5,

    # Secondary pass for unusually large merged pores.
    # The master Large Pore Repair card remains OFF by default.
    "large_pore_repair_largest_rescue_enabled": True,
    "large_pore_repair_largest_rescue_parent_limit": 5,
    "large_pore_repair_largest_rescue_min_radius_px": 4,
    "large_pore_repair_largest_rescue_max_radius_px": 36,
    "large_pore_repair_largest_rescue_max_area_px": 5000,
    "large_pore_repair_largest_rescue_max_fraction_of_parent": 0.20,
    "large_pore_repair_largest_rescue_max_span_px": 160,
    "large_pore_repair_largest_rescue_min_smaller_child_fraction": 0.08,
    "large_pore_repair_largest_rescue_max_larger_child_fraction": 0.92,
    "large_pore_repair_largest_rescue_max_repairs_per_image": 2,

    # v193: force-test the single largest parent before the other profiles.
    # This profile ranks candidates by split balance so it does not choose a
    # tiny sliver split merely because that bridge uses fewer pixels.
    "large_pore_repair_force_largest_enabled": True,
    "large_pore_repair_force_largest_max_radius_px": 48,
    "large_pore_repair_force_largest_max_area_px": 8000,
    "large_pore_repair_force_largest_max_fraction_of_parent": 0.30,
    "large_pore_repair_force_largest_max_span_px": 220,
    "large_pore_repair_force_largest_min_child_area_px": 500,
    "large_pore_repair_force_largest_min_smaller_child_fraction": 0.05,
    "large_pore_repair_force_largest_max_larger_child_fraction": 0.95,

    # v193: recursive medium-pore neck pass tuned from the user's green marks.
    # It can split the same original merged region repeatedly by recursively
    # rechecking the resulting child pores.
    "large_pore_repair_green_target_enabled": True,
    "large_pore_repair_green_target_min_parent_area_px": 2000,
    "large_pore_repair_green_target_max_parent_area_px": 18000,
    "large_pore_repair_green_target_parent_limit": 180,
    "large_pore_repair_green_target_min_radius_px": 2,
    "large_pore_repair_green_target_max_radius_px": 10,
    "large_pore_repair_green_target_min_area_px": 100,
    "large_pore_repair_green_target_max_area_px": 2500,
    "large_pore_repair_green_target_min_fraction_of_parent": 0.02,
    "large_pore_repair_green_target_max_fraction_of_parent": 0.18,
    "large_pore_repair_green_target_min_span_px": 18,
    "large_pore_repair_green_target_max_span_px": 165,
    "large_pore_repair_green_target_min_mean_thickness_px": 2.5,
    "large_pore_repair_green_target_max_mean_thickness_px": 30.0,
    "large_pore_repair_green_target_min_child_area_px": 400,
    "large_pore_repair_green_target_min_smaller_child_fraction": 0.12,
    "large_pore_repair_green_target_max_larger_child_fraction": 0.82,
    "large_pore_repair_green_target_max_repairs_per_image": 30,

    # Review-only extra pass for a short cut that isolates a small spur/lobe.
    # This is intentionally not applied automatically in BEAST/headless mode.
    "large_pore_repair_green_spur_enabled": True,
    "large_pore_repair_green_spur_review_only": True,
    "large_pore_repair_green_spur_max_repairs_per_image": 5,

    "large_pore_repair_include_edge_pores": False,
    "large_pore_repair_show_red_overlay": True,
    "large_pore_repair_fill_red_overlay": False,
    "large_pore_repair_save_red_overlay_png": True,
    "large_pore_repair_save_mask": False,
    "large_pore_repair_save_csv": True,

    # Threshold / particle analysis
    "threshold_min": 0.0,
    "threshold_max": 40.0,
    "particle_size_min": "0",
    "particle_size_max": "Infinity",
    "particle_circ_min": 0.0,
    "particle_circ_max": 1.0,
    "particle_include_holes": True,
    "particle_exclude_edges": False,
    "black_background": True,

    # Analyze > Set Measurements options. Core-required measurements are always enabled
    # even if unchecked: Area, Centroid, Perimeter, Fit Ellipse, and Shape Descriptors.
    "measure_area": True,
    "measure_mean": False,
    "measure_std_dev": False,
    "measure_mode": False,
    "measure_min_max": False,
    "measure_centroid": True,
    "measure_center_of_mass": False,
    "measure_perimeter": True,
    "measure_bounding_rect": False,
    "measure_fit_ellipse": True,
    "measure_shape_descriptors": True,
    "measure_feret": False,
    "measure_integrated_density": False,
    "measure_median": False,
    "measure_skewness": False,
    "measure_kurtosis": False,
    "measure_area_fraction": False,
    "measure_stack_position": False,
    "measure_limit_to_threshold": False,
    # Threshold input mode shared by normal setup, threshold sweeps, and +/-5 adjustment.
    # True = enter 8-bit gray values from 0-255. False = enter percentages from 0-100.
    # Processing always converts the selected input units to an 8-bit gray-value mask internally.
    "threshold_force_8bit_numbers": True,

    # Auto threshold fit from a traced pore ROI
    "auto_threshold_fit_enabled": True,
    "auto_threshold_fit_apply_to_main": True,
    "auto_threshold_fit_roi_count": 1,
    "auto_threshold_fit_trigger_percent_diff": 5.0,
    "auto_threshold_fit_sweep_min": False,
    "auto_threshold_fit_min_start": 0.0,
    "auto_threshold_fit_min_end": 0.0,
    "auto_threshold_fit_min_step": 5.0,
    "auto_threshold_fit_sweep_max": True,
    "auto_threshold_fit_max_start": 30.0,
    "auto_threshold_fit_max_end": 50.0,
    "auto_threshold_fit_max_step": 5.0,
    "auto_threshold_fit_roi_padding": 10,
    "auto_threshold_fit_area_penalty": 0.25,
    "auto_threshold_fit_max_tests": 5000,
    "auto_threshold_fit_save_csv": True,
    "auto_threshold_fit_save_best_mask": True,

    # JMP calculations
    "small_epd_cutoff": 0.005,
    "epd_cutoff_1": 0.1,
    "epd_cutoff_2": 0.025,
    # One delete-EPD preset controls the cleaned-table cutoff, between-count band, and pore-map limit.
    # Delete at 3 -> between 3-5 um; Delete at 5 -> 5-7 um; Delete at 10 -> 10-12 um.
    # Custom restores direct manual entry for delete, between-low, and between-high values.
    "epd_between_preset": "Delete at 5 microns",
    "epd_between_low": 0.005,
    "epd_between_high": 0.007,
    "epd_between_auto_high_enabled": False,
    "epd_between_auto_offset_um": 0.0,
    # Legacy v114 keys retained for saved-preset compatibility only.
    "epd_band_1_low": 0.003,
    "epd_band_1_high": 0.005,
    "epd_band_2_low": 0.005,
    "epd_band_2_high": 0.007,
    "epd_band_3_low": 0.010,
    "epd_band_3_high": 0.012,
    "circ_cutoff": 0.15,

    # JMP histogram display
    # Max bins means JMP computes bin width as data range / this number. Default doubled to 200 for finer histograms.
    # Axis padding 0 means the histogram X scale fits tightly to cleaned data min/max.
    "jmp_hist_max_bins": 40,
    "jmp_hist_auto_binning": True,
    "jmp_hist_epd_bins": 40,
    "jmp_hist_epd_major_tick": 0.01,
    "jmp_hist_epd_x_minor_ticks": 4,
    "jmp_hist_epd_y_minor_ticks": 4,
    "jmp_hist_round_bins": 40,
    "jmp_hist_round_x_minor_ticks": 0,
    "jmp_hist_round_y_minor_ticks": 4,
    "jmp_hist_circ_bins": 40,
    "jmp_hist_circ_x_minor_ticks": 0,
    "jmp_hist_circ_y_minor_ticks": 4,
    "jmp_hist_axis_pad_percent": 0.0,
    "jmp_epd_show_cutoff_lines": True,
    # Keep the reference lines but suppress their text labels inside the graph.
    "jmp_epd_show_cutoff_labels": False,
    "jmp_hist_graph_width": 850,
    "jmp_hist_graph_height": 550,
    "jmp_hist_show_legend": False,
    "jmp_hist_show_graph_titles": False,
    "jmp_hist_show_axis_titles": True,
    "jmp_hist_trim_trailing_zeros": True,
    "jmp_hist_epd_title": "EPD Distribution [mm]",
    "jmp_hist_epd_x_axis_title": "EPD [mm]",
    "jmp_hist_epd_y_axis_title": "Count",
    "jmp_hist_round_title": "Roundness Distribution",
    "jmp_hist_round_x_axis_title": "Roundness Ratio",
    "jmp_hist_round_y_axis_title": "Count",
    "jmp_hist_circ_title": "Circularity Distribution",
    "jmp_hist_circ_x_axis_title": "Circularity Ratio",
    "jmp_hist_circ_y_axis_title": "Count",
    "jmp_hist_epd_x_min": 0.0,
    "jmp_hist_epd_x_max": 0.0,
    "jmp_hist_epd_y_max": 0.0,
    "jmp_hist_epd_y_major_tick": 0.0,
    "jmp_hist_round_x_min": 0.0,
    "jmp_hist_round_x_max": 1.0,
    "jmp_hist_round_x_major_tick": 0.1,
    "jmp_hist_round_y_max": 0.0,
    "jmp_hist_round_y_major_tick": 0.0,
    "jmp_hist_circ_x_min": 0.0,
    "jmp_hist_circ_x_max": 1.0,
    "jmp_hist_circ_x_major_tick": 0.1,
    "jmp_hist_circ_y_max": 0.0,
    "jmp_hist_circ_y_major_tick": 0.0,
    "jmp_epd_hist_round_filter_enabled": False,
    "jmp_epd_hist_round_filter_min": 0.15,
    "jmp_summary_use_all_detected": False,
    "flag_weird_pores_enabled": False,
    "flag_weird_epd_above": 0.1,
    "flag_weird_circularity_below": 0.15,
    "flag_weird_roundness_below": 0.15,
    "flag_weird_roundness_above": 0.95,

    # Sweep control
    "sweep_enabled": False,
    "sweep_all_listed": False,
    "max_sweep_runs": 100,
    "sweep_until_enabled": False,
    "sweep_until_metric": "Max EPD (mm)",
    "sweep_until_operator": "Is at or above",
    "sweep_until_target_value": "0.05",
    "sweep_until_equal_tolerance": 0.0001,
    "sweep_until_stop_scope": "Current image/crop only",

    "sweep_threshold_min": False,
    "sweep_threshold_min_start": 0.0,
    "sweep_threshold_min_end": 0.0,
    "sweep_threshold_min_step": 1.0,

    "sweep_threshold_max": True,
    "sweep_threshold_max_start": 20.0,
    "sweep_threshold_max_end": 80.0,
    "sweep_threshold_max_step": 5.0,

    # Selectable Enhance Contrast sweep modes. All four start selected for backward compatibility.
    "sweep_contrast_enabled": False,
    "sweep_contrast_mode_off": True,
    "sweep_contrast_mode_saturated": True,
    "sweep_contrast_mode_normalize": True,
    "sweep_contrast_mode_equalize": True,

    "sweep_median_radius": False,
    "sweep_median_radius_start": 1.0,
    "sweep_median_radius_end": 5.0,
    "sweep_median_radius_step": 1.0,

    "sweep_bandpass_large": False,
    "sweep_bandpass_large_start": 20.0,
    "sweep_bandpass_large_end": 100.0,
    "sweep_bandpass_large_step": 10.0,

    "sweep_bandpass_small": False,
    "sweep_bandpass_small_start": 1.0,
    "sweep_bandpass_small_end": 10.0,
    "sweep_bandpass_small_step": 1.0,

    "sweep_clahe_blocksize": False,
    "sweep_clahe_blocksize_start": 63,
    "sweep_clahe_blocksize_end": 255,
    "sweep_clahe_blocksize_step": 32,

    "sweep_clahe_maximum": False,
    "sweep_clahe_maximum_start": 1.0,
    "sweep_clahe_maximum_end": 5.0,
    "sweep_clahe_maximum_step": 0.5,

    # Binary sweep options. Boolean operations use 0=OFF and 1=ON.
    "sweep_binary_enabled": False,
    "sweep_binary_enabled_start": 0,
    "sweep_binary_enabled_end": 1,
    "sweep_binary_enabled_step": 1,
    "sweep_binary_fill_holes": False,
    "sweep_binary_fill_holes_start": 0,
    "sweep_binary_fill_holes_end": 1,
    "sweep_binary_fill_holes_step": 1,
    "sweep_binary_watershed": False,
    "sweep_binary_watershed_start": 0,
    "sweep_binary_watershed_end": 1,
    "sweep_binary_watershed_step": 1,
    "sweep_binary_despeckle_iterations": False,
    "sweep_binary_despeckle_iterations_start": 0,
    "sweep_binary_despeckle_iterations_end": 2,
    "sweep_binary_despeckle_iterations_step": 1,
    "sweep_binary_open_iterations": False,
    "sweep_binary_open_iterations_start": 0,
    "sweep_binary_open_iterations_end": 2,
    "sweep_binary_open_iterations_step": 1,
    "sweep_binary_close_iterations": False,
    "sweep_binary_close_iterations_start": 0,
    "sweep_binary_close_iterations_end": 2,
    "sweep_binary_close_iterations_step": 1,
    "sweep_binary_erode_iterations": False,
    "sweep_binary_erode_iterations_start": 0,
    "sweep_binary_erode_iterations_end": 2,
    "sweep_binary_erode_iterations_step": 1,
    "sweep_binary_dilate_iterations": False,
    "sweep_binary_dilate_iterations_start": 0,
    "sweep_binary_dilate_iterations_end": 2,
    "sweep_binary_dilate_iterations_step": 1,
    "sweep_binary_minimum_radius": False,
    "sweep_binary_minimum_radius_start": 0.0,
    "sweep_binary_minimum_radius_end": 3.0,
    "sweep_binary_minimum_radius_step": 0.5,
    "sweep_binary_maximum_radius": False,
    "sweep_binary_maximum_radius_start": 0.0,
    "sweep_binary_maximum_radius_end": 3.0,
    "sweep_binary_maximum_radius_step": 0.5
}
