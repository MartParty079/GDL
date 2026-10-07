# -*- coding: utf-8 -*-
# MODULE 03: Main settings window and settings collection



def show_settings_dialog():
    IJ.log("Opening YOURE A BETA compact GUI v209 BEAST MODE")
    apply_nimbus_look_and_feel()
    fields = {}
    quick_run_registry = discover_quick_runs()
    active_quick_run_slot = [None]
    active_quick_run_baseline = [None]
    quick_run_buttons = {}
    quick_run_rename_buttons = {}
    quick_run_status_labels = {}

    dialog = JDialog()
    dialog.setTitle("GDL ImageJ + JMP Settings")
    dialog.setModal(True)
    dialog.setSize(1320, 780)
    dialog.setMinimumSize(Dimension(1000, 650))
    dialog.setResizable(True)
    dialog.setLocationRelativeTo(None)
    dialog.setLayout(BorderLayout())

    main_shell = JPanel(BorderLayout(12, 12))
    main_shell.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10))

    header = JPanel(BorderLayout())
    header.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(185, 200, 220)),
        BorderFactory.createEmptyBorder(12, 14, 12, 14)
    ))
    header.setBackground(Color(245, 248, 252))
    title_lab = JLabel("YOURE A BETA v209 - Configurable Fiji + Unified JMP Pipeline")
    try:
        title_lab.setFont(Font("SansSerif", Font.BOLD, 20))
    except:
        pass
    sub_lab = JLabel("Modern settings view with sidebar navigation, presets, validation, live summary, and better scrolling")
    title_wrap = JPanel()
    title_wrap.setOpaque(False)
    title_wrap.setLayout(BoxLayout(title_wrap, BoxLayout.Y_AXIS))
    title_wrap.add(title_lab)
    title_wrap.add(Box.createVerticalStrut(4))
    title_wrap.add(sub_lab)
    header.add(title_wrap, BorderLayout.WEST)
    main_shell.add(header, BorderLayout.NORTH)

    center = JPanel(BorderLayout(10, 10))

    nav_panel = JPanel()
    nav_panel.setLayout(BoxLayout(nav_panel, BoxLayout.Y_AXIS))
    nav_panel.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(210, 210, 210)),
        BorderFactory.createEmptyBorder(10, 10, 10, 10)
    ))
    nav_panel.setBackground(Color(250, 250, 250))
    nav_panel.setPreferredSize(Dimension(190, 560))
    nav_panel.add(JLabel("Navigate"))
    nav_panel.add(Box.createVerticalStrut(8))

    cards = JPanel(CardLayout())
    cards.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(210, 210, 210)),
        BorderFactory.createEmptyBorder(4, 4, 4, 4)
    ))

    side_right = JPanel(BorderLayout(8, 8))
    side_right.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(210, 210, 210)),
        BorderFactory.createEmptyBorder(10, 10, 10, 10)
    ))
    side_right.setPreferredSize(Dimension(270, 560))

    top_right = JPanel()
    top_right.setLayout(BoxLayout(top_right, BoxLayout.Y_AXIS))
    top_right.add(JLabel("View mode"))
    mode_combo = JComboBox(["Simple", "Advanced"])
    top_right.add(mode_combo)
    top_right.add(Box.createVerticalStrut(8))
    maximize_button = JButton("Maximize GUI")
    style_dialog_button(maximize_button, False)
    top_right.add(maximize_button)
    top_right.add(Box.createVerticalStrut(10))
    top_right.add(JLabel("Quick presets"))

    preset_row1 = JPanel()
    preset_row2 = JPanel()
    preset_buttons = {}
    for pname, prow in [("Default GDL", preset_row1), ("Fast Batch", preset_row1), ("Manual QA", preset_row1), ("Crop Mode", preset_row2), ("High Detail Report", preset_row2), ("No Manual Measurements", preset_row2)]:
        btn = JButton(pname)
        style_dialog_button(btn, False)
        btn.setPreferredSize(Dimension(125, 30))
        preset_buttons[pname] = btn
        prow.add(btn)
    top_right.add(preset_row1)
    top_right.add(preset_row2)
    top_right.add(Box.createVerticalStrut(10))
    top_right.add(JLabel("Live run summary"))

    summary_area = JTextArea(14, 22)
    summary_area.setEditable(False)
    summary_area.setLineWrap(True)
    summary_area.setWrapStyleWord(True)
    summary_area.setBackground(Color(252, 252, 252))
    summary_scroll = JScrollPane(summary_area)
    summary_scroll.getVerticalScrollBar().setUnitIncrement(16)

    side_right.add(top_right, BorderLayout.NORTH)
    side_right.add(summary_scroll, BorderLayout.CENTER)

    center.add(nav_panel, BorderLayout.WEST)
    center.add(cards, BorderLayout.CENTER)
    center.add(side_right, BorderLayout.EAST)
    main_shell.add(center, BorderLayout.CENTER)

    card_layout = cards.getLayout()
    nav_buttons = {}
    advanced_pages = ["Auto Threshold Fit", "BEAST MODE", "Image Capturing", "Set Scale"]
    page_order = []
    current_page = [None]

    def show_page(page_name):
        card_layout.show(cards, page_name)
        current_page[0] = page_name
        select_nav_button_style(nav_buttons, page_name)
        try:
            summary_area.setText(gui_summary_text(fields, str(mode_combo.getSelectedItem())))
            summary_area.setCaretPosition(0)
        except:
            pass

    def add_nav_page(page_name, component):
        left_align_component_tree(component)
        cards.add(component, page_name)
        btn = JButton(page_name)
        style_nav_button(btn)
        def btn_action(event, n=page_name):
            show_page(n)
        btn.addActionListener(btn_action)
        nav_buttons[page_name] = btn
        page_order.append(page_name)
        nav_panel.add(btn)
        nav_panel.add(Box.createVerticalStrut(6))

    def update_nav_mode():
        mode_name = str(mode_combo.getSelectedItem())
        for n in page_order:
            visible = True
            if mode_name == "Simple" and n in advanced_pages:
                visible = False
            nav_buttons[n].setVisible(visible)
        if current_page[0] is None or (mode_name == "Simple" and current_page[0] in advanced_pages):
            for n in page_order:
                if nav_buttons[n].isVisible():
                    show_page(n)
                    break
        else:
            show_page(current_page[0])

    def populate_page_safely(page_name, page, builder):
        try:
            builder(page, fields)
            if page.getComponentCount() <= 0:
                raise RuntimeError("Page builder returned without adding controls")
        except Exception as page_error:
            try:
                page.removeAll()
            except:
                pass
            error_panel = JPanel(BorderLayout())
            error_panel.setBackground(Color(255, 238, 238))
            error_panel.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(Color(180, 60, 60)),
                BorderFactory.createEmptyBorder(16, 16, 16, 16)
            ))
            error_text = str(page_error).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            error_panel.add(JLabel("<html><b>Could not build " + page_name + ".</b><br>" + error_text + "<br><br>See the Fiji Log window for details.</html>"), BorderLayout.CENTER)
            page.add(error_panel)
            IJ.log("v193 settings page error [" + page_name + "]: " + str(page_error))

    # ---------------- Dashboard landing page ----------------
    dashboard = page_panel()

    dash_banner = JPanel(BorderLayout())
    dash_banner.setBackground(Color(35, 80, 130))
    dash_banner.setBorder(BorderFactory.createEmptyBorder(18, 18, 18, 18))
    dash_title = JLabel("<html><span style='color:white;font-size:24px;font-weight:bold;'>YOURE A BETA v209 Configurable Fiji + Unified JMP</span></html>")
    dash_sub = JLabel("<html><span style='color:white;'>If you see this page, you are running the new GUI, not the old tabbed popup.</span></html>")
    dash_text = JPanel()
    dash_text.setOpaque(False)
    dash_text.setLayout(BoxLayout(dash_text, BoxLayout.Y_AXIS))
    dash_text.add(dash_title)
    dash_text.add(Box.createVerticalStrut(6))
    dash_text.add(dash_sub)
    dash_banner.add(dash_text, BorderLayout.CENTER)
    dashboard.add(dash_banner)
    dashboard.add(Box.createVerticalStrut(14))

    quick_run_card = JPanel()
    quick_run_card.setLayout(BoxLayout(quick_run_card, BoxLayout.Y_AXIS))
    quick_run_card.setBackground(Color(242, 248, 255))
    quick_run_card.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(145, 175, 210)),
        BorderFactory.createEmptyBorder(14, 14, 14, 14)
    ))
    quick_run_card.setMaximumSize(Dimension(900, 430))
    quick_run_card.add(JLabel("<html><b style='font-size:16px;'>Portable Quick Runs</b><br>Select one of five slots, configure any page, then press Run. v199 saves every current editable setting, including Word/JMP histogram binning and the selected Swift objective profile. A save confirmation appears only when the selected Quick Run name or configuration changed.</html>"))
    quick_run_card.add(Box.createVerticalStrut(8))
    quick_run_active_label = JLabel("No Quick Run selected. A normal Run will not create or update a Quick Run file.")
    quick_run_card.add(quick_run_active_label)
    quick_run_card.add(Box.createVerticalStrut(10))

    for quick_slot in range(1, QUICK_RUN_SLOT_COUNT + 1):
        quick_row = JPanel(BorderLayout(8, 4))
        quick_row.setOpaque(False)
        quick_row.setBorder(BorderFactory.createCompoundBorder(
            BorderFactory.createLineBorder(Color(205, 220, 235)),
            BorderFactory.createEmptyBorder(8, 8, 8, 8)
        ))
        quick_main_button = JButton()
        style_dialog_button(quick_main_button, False)
        quick_main_button.setPreferredSize(Dimension(310, 36))
        quick_rename_button = JButton("Rename")
        style_dialog_button(quick_rename_button, False)
        quick_rename_button.setPreferredSize(Dimension(95, 30))
        quick_status = JLabel()
        quick_status.setPreferredSize(Dimension(420, 48))
        quick_row.add(quick_main_button, BorderLayout.WEST)
        quick_row.add(quick_status, BorderLayout.CENTER)
        quick_row.add(quick_rename_button, BorderLayout.EAST)
        quick_run_buttons[quick_slot] = quick_main_button
        quick_run_rename_buttons[quick_slot] = quick_rename_button
        quick_run_status_labels[quick_slot] = quick_status
        quick_run_card.add(quick_row)
        if quick_slot < QUICK_RUN_SLOT_COUNT:
            quick_run_card.add(Box.createVerticalStrut(6))

    dashboard.add(quick_run_card)
    dashboard.add(Box.createVerticalStrut(14))

    poem_card = JPanel(BorderLayout(14, 0))
    poem_card.setBackground(Color(255, 255, 245))
    poem_card.setBorder(BorderFactory.createCompoundBorder(
        BorderFactory.createLineBorder(Color(210, 195, 140)),
        BorderFactory.createEmptyBorder(14, 14, 14, 14)
    ))
    poem_card.setMaximumSize(Dimension(900, 265))

    poem_label = JLabel(random_john_gdl_poem_html())
    poem_card.add(poem_label, BorderLayout.CENTER)
    poem_card.add(make_john_gdl_startup_photo_panel(), BorderLayout.EAST)

    dashboard.add(poem_card)
    dashboard.add(Box.createVerticalStrut(14))

    dash_cards = JPanel()
    dash_cards.setLayout(BoxLayout(dash_cards, BoxLayout.Y_AXIS))
    dash_cards.setOpaque(False)

    for card_title, card_body in [
        ("1. Pick a preset or use your saved defaults", "Use the preset buttons on the right, then fine tune settings from the sidebar."),
        ("2. Use the left sidebar", "Start with ORDER, then tune each numbered occurrence on Processing. Threshold, Sweep, Report, and Report Selection remain separate sidebar pages."),
        ("3. Watch the live summary", "The right panel updates as you change key settings and highlights obvious bad values."),
        ("4. Run with progress", "When processing starts, a separate progress window shows which image/crop is running.")
    ]:
        card = JPanel(BorderLayout())
        card.setBackground(Color(255, 255, 255))
        card.setBorder(BorderFactory.createCompoundBorder(
            BorderFactory.createLineBorder(Color(205, 215, 225)),
            BorderFactory.createEmptyBorder(12, 12, 12, 12)
        ))
        card.setMaximumSize(Dimension(900, 82))
        card.add(JLabel("<html><b>" + card_title + "</b><br>" + card_body + "</html>"), BorderLayout.CENTER)
        dash_cards.add(card)
        dash_cards.add(Box.createVerticalStrut(10))

    dashboard.add(dash_cards)
    dashboard.add(Box.createVerticalStrut(10))
    dashboard.add(JLabel("<html><b>Tip:</b> Use the Simple/Advanced dropdown on the right. Simple mode hides the advanced pages.</html>"))

    add_nav_page("Dashboard", make_scroll(dashboard))

    # ---------------- YOURE A BETA Image Capturing tab ----------------
    capture_page = page_panel()
    populate_page_safely("Image Capturing", capture_page, populate_v193_capture_page)
    add_nav_page("Image Capturing", make_scroll(capture_page))

    # ---------------- Set Scale tab ----------------
    scale_page = page_panel()
    populate_page_safely("Set Scale", scale_page, populate_v193_scale_page)
    add_nav_page("Set Scale", make_scroll(scale_page))

    # ---------------- General tab ----------------
    general = page_panel()
    populate_page_safely("General + JMP", general, populate_v193_general_jmp_page)
    add_nav_page("General + JMP", make_scroll(general))

    # ---------------- BEAST MODE tab ----------------
    beast = page_panel()
    populate_page_safely("BEAST MODE", beast, populate_v193_beast_page)
    add_nav_page("BEAST MODE", make_scroll(beast))

    # ---------------- ORDER + dynamic Processing tabs ----------------
    order_page = page_panel()
    proc = page_panel()
    populate_page_safely("ORDER", order_page, lambda panel, flds: populate_v193_order_page(panel, proc, flds))
    add_nav_page("ORDER", make_scroll(order_page))
    add_nav_page("Processing", make_scroll(proc))

    # ---------------- Threshold tab ----------------
    thresh = page_panel()
    populate_page_safely("Threshold + Analysis", thresh, populate_v193_threshold_page)
    add_nav_page("Threshold + Analysis", make_scroll(thresh))

    # ---------------- Large Pore Repair tab ----------------
    large_pore_repair_page = page_panel()
    populate_page_safely("Large Pore Repair", large_pore_repair_page, populate_v193_large_pore_repair_page)
    add_nav_page("Large Pore Repair", make_scroll(large_pore_repair_page))

    # ---------------- Auto threshold fit tab ----------------
    fit = page_panel()
    populate_page_safely("Auto Threshold Fit", fit, populate_v193_auto_fit_page)
    add_nav_page("Auto Threshold Fit", make_scroll(fit))

    # ---------------- Sweep tab ----------------
    sweep = page_panel()
    populate_page_safely("Sweep", sweep, populate_v193_sweep_page)
    add_nav_page("Sweep", make_scroll(sweep))

    # ---------------- Report tab ----------------
    report = page_panel()
    populate_page_safely("Report", report, populate_v193_report_page)
    add_nav_page("Report", make_scroll(report))

    # ---------------- Report Selection tab ----------------
    report_selection = page_panel()
    populate_page_safely("Report Selection", report_selection, populate_v193_report_selection_page)
    add_nav_page("Report Selection", make_scroll(report_selection))

    # ---------------- Report Recovery + Summaries tab ----------------
    report_recovery = page_panel()
    populate_page_safely("Report Recovery + Summaries", report_recovery, populate_v209_report_recovery_page)
    add_nav_page("Report Recovery + Summaries", make_scroll(report_recovery))

    apply_tooltips(fields)

    def refresh_gui_summary(*args):
        try:
            summary_area.setText(gui_summary_text(fields, str(mode_combo.getSelectedItem())))
            summary_area.setCaretPosition(0)
        except:
            pass

    fields["_pipeline_refresh_callback"] = refresh_gui_summary
    try:
        build_dynamic_processing_page(proc, fields)
    except Exception as e_pipeline_refresh:
        IJ.log("Could not attach dynamic Processing listeners: " + str(e_pipeline_refresh))

    # Live updates for key fields.
    watch_keys = [
        "batch_enabled", "crop_count", "crop_mode", "median_enabled", "median_radius", "contrast_enabled",
        "batch_enabled", "image_capture_enabled", "image_capture_mode", "image_capture_count", "image_capture_scale_known_length_mm", "image_capture_try_open_live_view", "image_capture_live_view_command", "set_scale_only_mode", "swift_magn_scale_enabled", "swift_magn_filename", "swift_magn_profile_name", "swift_magn_search_parent_levels", "swift_magn_use_bundle_fallback", "swift_magn_override_existing_scale", "set_scale_direct_enabled", "set_scale_direct_mm_per_pixel", "set_scale_direct_pixels_per_mm", "bandpass_enabled", "clahe_enabled", "binary_enabled", "binary_fill_holes", "binary_watershed", "binary_despeckle_iterations", "binary_open_iterations", "binary_close_iterations", "binary_erode_iterations", "binary_dilate_iterations", "binary_minimum_radius", "binary_maximum_radius", "threshold_min", "threshold_max", "threshold_force_8bit_numbers", "sweep_enabled", "sweep_all_listed", "sweep_until_enabled", "sweep_until_metric", "sweep_until_operator", "sweep_until_target_value", "sweep_until_equal_tolerance", "sweep_until_stop_scope", "sweep_threshold_min", "sweep_threshold_min_start", "sweep_threshold_min_end", "sweep_threshold_min_step", "sweep_threshold_max", "sweep_threshold_max_start", "sweep_threshold_max_end", "sweep_threshold_max_step", "sweep_contrast_enabled", "sweep_contrast_mode_off", "sweep_contrast_mode_saturated", "sweep_contrast_mode_normalize", "sweep_contrast_mode_equalize", "auto_scale_unscaled_enabled", "auto_scale_known_length_mm", "auto_scale_show_preview", "auto_scale_blue_ocr_enabled", "manual_selected_pore_enabled", "manual_success_popup_show_picture",
        "manual_largest_pore_enabled", "auto_threshold_fit_enabled", "create_word_report", "word_report_mode", "report_scale_method", "report_imaging_software", "threshold_selection_reports_enabled", "threshold_selection_create_full_combined", "threshold_selection_folder_name", "threshold_selection_criterion_1_enabled", "threshold_selection_criterion_1_metric", "threshold_selection_criterion_1_target", "threshold_selection_criterion_1_importance", "threshold_selection_criterion_2_enabled", "threshold_selection_criterion_2_metric", "threshold_selection_criterion_2_target", "threshold_selection_criterion_2_importance", "threshold_selection_criterion_3_enabled", "threshold_selection_criterion_3_metric", "threshold_selection_criterion_3_target", "threshold_selection_criterion_3_importance", "threshold_selection_criterion_4_enabled", "threshold_selection_criterion_4_metric", "threshold_selection_criterion_4_target", "threshold_selection_criterion_4_importance", "threshold_selection_criterion_5_enabled", "threshold_selection_criterion_5_metric", "threshold_selection_criterion_5_target", "threshold_selection_criterion_5_importance", "report_include_strand_heat_map", "report_save_strand_heat_map", "report_save_segmented_overlay_next_to_word", "report_segmented_overlay_fiber_color", "report_segmented_overlay_fiber_opacity_percent", "report_segmented_overlay_annotation_opacity_percent", "report_segmented_pores_overlay_opacity_percent", "save_fiji_log_enabled",
        "report_filename_mode", "export_main_summary_xls", "summary_xls_destination", "summary_xls_custom_folder", "reports_only_recovery_mode", "reports_only_source_mode", "reports_only_output_mode", "batch_sweep_reports_by_og_image", "batch_sweep_export_all_summaries_to_all_reports", "batch_live_image_report_folders_enabled", "no_lossless_images_in_reports", "dont_save_lossless_generated_images", "no_lossless_images_at_all",
        "beast_mode_enabled", "beast_parallel_fiji_enabled", "beast_show_fiji_worker_windows", "beast_preflight_enabled", "beast_preflight_timeout_sec", "beast_fiji_no_progress_timeout_sec", "beast_fiji_heartbeat_interval_sec", "beast_fiji_heartbeat_timeout_sec", "beast_fiji_claim_timeout_sec", "beast_fiji_job_timeout_sec", "beast_fiji_runtime_retries", "beast_jmp_parallel_instances", "beast_jmp_streaming_enabled", "beast_jmp_start_after_fiji_runs", "beast_create_graph_word_report", "beast_word_report_mode",
        "epd_between_preset", "small_epd_cutoff", "epd_between_low", "epd_between_high", "report_pore_map_background", "report_pore_map_opacity_percent",
        "particle_count_high_limit", "report_scale_bar_auto_fit_enabled", "report_scale_bar_length_mm", "fiber_fixer_enabled", "fiber_fixer_absolute_threshold_max", "fiber_fixer_wire_width_px", "fiber_fixer_save_wireframe_mask", "fiber_fixer_save_preview_overlay", "large_pore_repair_enabled", "large_pore_repair_mode", "large_pore_repair_min_parent_area_px", "large_pore_repair_largest_pore_limit", "large_pore_repair_min_child_area_px", "large_pore_repair_min_smaller_child_fraction", "large_pore_repair_max_larger_child_fraction", "large_pore_repair_min_closing_radius_px", "large_pore_repair_max_closing_radius_px", "large_pore_repair_radius_step_px", "large_pore_repair_min_area_px", "large_pore_repair_max_area_px", "large_pore_repair_max_fraction_of_parent", "large_pore_repair_max_span_px", "large_pore_repair_max_repairs_per_image", "large_pore_repair_largest_rescue_enabled", "large_pore_repair_largest_rescue_parent_limit", "large_pore_repair_largest_rescue_min_radius_px", "large_pore_repair_largest_rescue_max_radius_px", "large_pore_repair_largest_rescue_max_area_px", "large_pore_repair_largest_rescue_max_fraction_of_parent", "large_pore_repair_largest_rescue_max_span_px", "large_pore_repair_largest_rescue_min_smaller_child_fraction", "large_pore_repair_largest_rescue_max_larger_child_fraction", "large_pore_repair_largest_rescue_max_repairs_per_image", "large_pore_repair_force_largest_enabled", "large_pore_repair_force_largest_max_radius_px", "large_pore_repair_force_largest_max_area_px", "large_pore_repair_force_largest_max_fraction_of_parent", "large_pore_repair_force_largest_max_span_px", "large_pore_repair_force_largest_min_child_area_px", "large_pore_repair_force_largest_min_smaller_child_fraction", "large_pore_repair_force_largest_max_larger_child_fraction", "large_pore_repair_green_target_enabled", "large_pore_repair_green_target_min_parent_area_px", "large_pore_repair_green_target_max_parent_area_px", "large_pore_repair_green_target_parent_limit", "large_pore_repair_green_target_min_radius_px", "large_pore_repair_green_target_max_radius_px", "large_pore_repair_green_target_min_area_px", "large_pore_repair_green_target_max_area_px", "large_pore_repair_green_target_min_fraction_of_parent", "large_pore_repair_green_target_max_fraction_of_parent", "large_pore_repair_green_target_min_span_px", "large_pore_repair_green_target_max_span_px", "large_pore_repair_green_target_min_mean_thickness_px", "large_pore_repair_green_target_max_mean_thickness_px", "large_pore_repair_green_target_min_child_area_px", "large_pore_repair_green_target_min_smaller_child_fraction", "large_pore_repair_green_target_max_larger_child_fraction", "large_pore_repair_green_target_max_repairs_per_image", "large_pore_repair_green_spur_enabled", "large_pore_repair_green_spur_review_only", "large_pore_repair_green_spur_max_repairs_per_image"
    ]
    for dynamic_key in fields.keys():
        if str(dynamic_key).startswith("pipeline_") and not str(dynamic_key).startswith("pipeline_order_"):
            if dynamic_key not in watch_keys:
                watch_keys.append(dynamic_key)
    for wk in watch_keys:
        comp = fields.get(wk)
        if comp is None:
            continue
        try:
            if isinstance(comp, JTextField):
                comp.getDocument().addDocumentListener(SimpleDocListener(refresh_gui_summary))
            else:
                comp.addActionListener(refresh_gui_summary)
        except:
            pass

    def mode_changed(event):
        update_nav_mode()
        refresh_gui_summary()
    mode_combo.addActionListener(mode_changed)

    def maximize_gui_action(event):
        try:
            screen = Toolkit.getDefaultToolkit().getScreenSize()
            dialog.setLocation(0, 0)
            dialog.setSize(int(screen.width), int(screen.height) - 40)
            dialog.validate()
            dialog.repaint()
        except Exception as e_max_gui:
            IJ.log("Could not maximize GUI window: " + str(e_max_gui))
    maximize_button.addActionListener(maximize_gui_action)

    def refresh_quick_run_dashboard():
        active_slot = active_quick_run_slot[0]
        if active_slot is None:
            quick_run_active_label.setText("No Quick Run selected. A normal Run will not create or update a Quick Run file.")
        else:
            active_record = quick_run_registry.get(active_slot, {})
            quick_run_active_label.setText("ACTIVE: Quick Run " + str(active_slot) + " - " + str(active_record.get("name", "")) + ". Unchanged runs skip the save prompt.")
        for slot_number in range(1, QUICK_RUN_SLOT_COUNT + 1):
            record = quick_run_registry.get(slot_number, {})
            display_name = str(record.get("name", "Quick Run " + str(slot_number)))
            button_prefix = "ACTIVE - " if active_slot == slot_number else ""
            quick_run_buttons[slot_number].setText(button_prefix + "Quick Run " + str(slot_number) + ": " + display_name)
            error_text = str(record.get("error", "")).strip()
            if record.get("settings") is None:
                if error_text != "":
                    detail = "File error: " + error_text + ". Selecting this slot loads current defaults instead. Process: " + quick_run_process_summary(DEFAULTS)
                else:
                    detail = "Not saved yet. Default process: " + quick_run_process_summary(DEFAULTS)
            else:
                detail = "Process: " + quick_run_process_summary(record.get("settings", {}))
                file_name = os.path.basename(str(record.get("path", "")))
                if file_name != "":
                    detail += " | File: " + file_name
            quick_run_status_labels[slot_number].setText("<html><div style='width:410px;'>" + quick_run_html_text(detail) + "</div></html>")

    def activate_quick_run(slot_number, announce=True):
        record = quick_run_registry.get(slot_number)
        if record is None:
            return
        if str(record.get("path", "")).strip() != "" and os.path.isfile(str(record.get("path", ""))):
            fresh = load_quick_run_file(str(record.get("path", "")), slot_number)
            if fresh.get("settings") is not None:
                fresh["name"] = str(record.get("name", fresh.get("name", "")))
                quick_run_registry[slot_number] = fresh
                record = fresh
            else:
                record["error"] = fresh.get("error", "")
        source_settings = record.get("settings")
        if not isinstance(source_settings, dict):
            source_settings = dict(DEFAULTS)
        try:
            apply_quick_run_settings_to_fields(fields, source_settings, proc)
        except Exception as quick_apply_error:
            IJ.log("Could not load Quick Run " + str(slot_number) + " into GUI: " + str(quick_apply_error))
            JOptionPane.showMessageDialog(dialog, "Could not load Quick Run settings:\n" + str(quick_apply_error), "Quick Run Error", JOptionPane.ERROR_MESSAGE)
            return
        active_quick_run_slot[0] = int(slot_number)
        active_quick_run_baseline[0] = quick_run_gui_snapshot(fields, str(record.get("name", "")))
        refresh_quick_run_dashboard()
        refresh_gui_summary()
        show_page("ORDER")
        if announce:
            source_note = "saved portable file" if record.get("settings") is not None else "current installation defaults"
            JOptionPane.showMessageDialog(dialog,
                "Loaded Quick Run " + str(slot_number) + ": " + str(record.get("name", "")) + "\n\nSource: " + source_note + "\nEdit any normal settings, then press Run.",
                "Quick Run Loaded", JOptionPane.INFORMATION_MESSAGE)

    def rename_quick_run(slot_number):
        record = quick_run_registry.get(slot_number, {})
        current_name = str(record.get("name", "Quick Run " + str(slot_number)))
        entered = JOptionPane.showInputDialog(dialog, "Enter the name for Quick Run " + str(slot_number) + ":", current_name)
        if entered is None:
            return
        new_name = str(entered).strip()
        if new_name == "":
            JOptionPane.showMessageDialog(dialog, "Quick Run name cannot be blank.", "Rename Quick Run", JOptionPane.WARNING_MESSAGE)
            return
        if active_quick_run_slot[0] != int(slot_number):
            activate_quick_run(slot_number, False)
            record = quick_run_registry.get(slot_number, record)
        record["name"] = new_name
        quick_run_registry[slot_number] = record
        refresh_quick_run_dashboard()
        JOptionPane.showMessageDialog(dialog,
            "Quick Run " + str(slot_number) + " is now named " + new_name + " for this setup.\n\nBecause the name changed, Run will ask whether to save the updated portable file.",
            "Quick Run Renamed", JOptionPane.INFORMATION_MESSAGE)

    for quick_slot in range(1, QUICK_RUN_SLOT_COUNT + 1):
        def _make_quick_run_action(slot_number):
            def _quick_run_action(event):
                activate_quick_run(slot_number, True)
            return _quick_run_action
        def _make_quick_rename_action(slot_number):
            def _quick_rename_action(event):
                rename_quick_run(slot_number)
            return _quick_rename_action
        quick_run_buttons[quick_slot].addActionListener(_make_quick_run_action(quick_slot))
        quick_run_rename_buttons[quick_slot].addActionListener(_make_quick_rename_action(quick_slot))

    refresh_quick_run_dashboard()

    for pname in preset_buttons.keys():
        def _make_preset_action(name):
            def _preset_action(event):
                apply_gui_preset(fields, name)
                refresh_gui_summary()
            return _preset_action
        preset_buttons[pname].addActionListener(_make_preset_action(pname))

    dialog.add(main_shell, BorderLayout.CENTER)

    buttons = JPanel()
    ok_button = JButton("Run")
    cancel_button = JButton("Cancel")
    style_dialog_button(ok_button, True)
    style_dialog_button(cancel_button, False)
    buttons.add(ok_button)
    buttons.add(cancel_button)
    dialog.add(buttons, BorderLayout.SOUTH)

    left_align_component_tree(main_shell)
    update_nav_mode()
    refresh_gui_summary()

    result = [False]

    def ok_action(event):
        try:
            collect_pipeline_steps_from_fields(fields)
        except Exception as pipeline_error:
            IJ.error("ORDER / Processing Error", str(pipeline_error))
            try:
                show_page("ORDER")
            except:
                pass
            return
        result[0] = True
        dialog.dispose()

    def cancel_action(event):
        result[0] = False
        dialog.dispose()

    ok_button.addActionListener(ok_action)
    cancel_button.addActionListener(cancel_action)

    dialog.setVisible(True)

    if not result[0]:
        return None

    try:
        settings = {}

        settings["batch_enabled"] = parse_bool_checkbox(fields["batch_enabled"])
        settings["batch_live_image_report_folders_enabled"] = parse_bool_checkbox(fields["batch_live_image_report_folders_enabled"])
        settings["image_capture_enabled"] = parse_bool_checkbox(fields["image_capture_enabled"])
        settings["image_capture_mode"] = str(fields["image_capture_mode"].getSelectedItem())
        settings["image_capture_count"] = parse_int_field(fields["image_capture_count"], "Image capture count")
        settings["image_capture_batch_name"] = parse_text(fields["image_capture_batch_name"])
        settings["image_capture_scale_known_length_mm"] = parse_float_field(fields["image_capture_scale_known_length_mm"], "Image capture known scale distance")
        settings["image_capture_save_scale_frame"] = parse_bool_checkbox(fields["image_capture_save_scale_frame"])
        settings["image_capture_keep_captured_windows_open"] = parse_bool_checkbox(fields["image_capture_keep_captured_windows_open"])
        settings["image_capture_try_open_live_view"] = parse_bool_checkbox(fields["image_capture_try_open_live_view"])
        settings["image_capture_live_view_command"] = str(fields["image_capture_live_view_command"].getSelectedItem())
        settings["image_capture_show_live_view_directions"] = parse_bool_checkbox(fields["image_capture_show_live_view_directions"])
        if settings["image_capture_count"] < 1:
            settings["image_capture_count"] = 1
        if settings["image_capture_scale_known_length_mm"] <= 0:
            settings["image_capture_scale_known_length_mm"] = DEFAULTS["image_capture_scale_known_length_mm"]
        if settings["image_capture_enabled"]:
            # Capture mode creates calibrated TIFF inputs itself; the normal file/folder input picker is skipped.
            settings["batch_enabled"] = True
            settings["auto_scale_unscaled_enabled"] = False
            settings["auto_scale_save_tif_enabled"] = True
        settings["include_subfolders"] = parse_bool_checkbox(fields["include_subfolders"])
        settings["crop_count"] = parse_int_field(fields["crop_count"], "Number of crop regions")
        settings["crop_mode"] = str(fields["crop_mode"].getSelectedItem())
        settings["crop_prompt_each_image"] = parse_bool_checkbox(fields["crop_prompt_each_image"])
        settings["fancy_progress_enabled"] = parse_bool_checkbox(fields["fancy_progress_enabled"])
        if settings["crop_count"] < 0:
            settings["crop_count"] = 0
        if settings["crop_count"] <= 0:
            settings["crop_prompt_each_image"] = False
        settings["close_windows_when_finished"] = parse_bool_checkbox(fields["close_windows_when_finished"])
        settings["close_jmp_windows_when_finished"] = parse_bool_checkbox(fields["close_jmp_windows_when_finished"])
        settings["manual_measurements_enabled"] = parse_bool_checkbox(fields["manual_measurements_enabled"])

        settings["beast_mode_enabled"] = parse_bool_checkbox(fields["beast_mode_enabled"])
        settings["beast_parallel_fiji_enabled"] = parse_bool_checkbox(fields["beast_parallel_fiji_enabled"])
        settings["beast_show_fiji_worker_windows"] = parse_bool_checkbox(fields["beast_show_fiji_worker_windows"])
        settings["beast_fiji_parallel_instances"] = parse_int_field(fields["beast_fiji_parallel_instances"], "BEAST MODE parallel Fiji workers")
        settings["beast_fiji_fallback_to_controller"] = parse_bool_checkbox(fields["beast_fiji_fallback_to_controller"])
        settings["beast_fiji_worker_timeout_sec"] = parse_int_field(fields["beast_fiji_worker_timeout_sec"], "BEAST MODE Fiji worker timeout")
        settings["beast_fiji_no_progress_timeout_sec"] = parse_int_field(fields["beast_fiji_no_progress_timeout_sec"], "BEAST MODE Fiji no-progress watchdog")
        settings["beast_fiji_heartbeat_interval_sec"] = parse_int_field(fields["beast_fiji_heartbeat_interval_sec"], "BEAST MODE Fiji heartbeat interval")
        settings["beast_fiji_heartbeat_timeout_sec"] = parse_int_field(fields["beast_fiji_heartbeat_timeout_sec"], "BEAST MODE Fiji heartbeat timeout")
        settings["beast_fiji_claim_timeout_sec"] = parse_int_field(fields["beast_fiji_claim_timeout_sec"], "BEAST MODE Fiji claim timeout")
        settings["beast_fiji_job_timeout_sec"] = parse_int_field(fields["beast_fiji_job_timeout_sec"], "BEAST MODE Fiji single-run timeout")
        settings["beast_fiji_runtime_retries"] = parse_int_field(fields["beast_fiji_runtime_retries"], "BEAST MODE Fiji runtime retries")
        settings["beast_fiji_launch_stagger_sec"] = parse_float_field(fields["beast_fiji_launch_stagger_sec"], "BEAST MODE Fiji launch stagger")
        settings["beast_fiji_worker_startup_timeout_sec"] = parse_int_field(fields["beast_fiji_worker_startup_timeout_sec"], "BEAST MODE Fiji startup timeout")
        settings["beast_preflight_enabled"] = parse_bool_checkbox(fields["beast_preflight_enabled"])
        settings["beast_preflight_timeout_sec"] = parse_int_field(fields["beast_preflight_timeout_sec"], "BEAST MODE launch self-test timeout")
        settings["beast_jmp_parallel_instances"] = parse_int_field(fields["beast_jmp_parallel_instances"], "BEAST MODE parallel JMP instances")
        settings["beast_jmp_safe_launch_enabled"] = parse_bool_checkbox(fields["beast_jmp_safe_launch_enabled"])
        settings["beast_jmp_minimized_launch_enabled"] = parse_bool_checkbox(fields["beast_jmp_minimized_launch_enabled"])
        settings["beast_jmp_isolated_temp_enabled"] = parse_bool_checkbox(fields["beast_jmp_isolated_temp_enabled"])
        settings["beast_jmp_retry_count"] = parse_int_field(fields["beast_jmp_retry_count"], "BEAST MODE JMP retry count")
        settings["beast_jmp_retry_delay_sec"] = parse_float_field(fields["beast_jmp_retry_delay_sec"], "BEAST MODE JMP retry delay")
        settings["beast_jmp_streaming_enabled"] = parse_bool_checkbox(fields["beast_jmp_streaming_enabled"])
        settings["beast_jmp_start_after_fiji_runs"] = parse_int_field(fields["beast_jmp_start_after_fiji_runs"], "BEAST MODE JMP streaming start threshold")
        settings["beast_create_graph_word_report"] = parse_bool_checkbox(fields["beast_create_graph_word_report"])
        settings["beast_word_report_mode"] = str(fields["beast_word_report_mode"].getSelectedItem())
        settings["beast_jmp_timeout_sec"] = parse_int_field(fields["beast_jmp_timeout_sec"], "BEAST MODE JMP timeout")
        settings["beast_jmp_exit_grace_sec"] = parse_float_field(fields["beast_jmp_exit_grace_sec"], "BEAST MODE JMP exit grace")
        settings["beast_jmp_launch_stagger_sec"] = parse_float_field(fields["beast_jmp_launch_stagger_sec"], "BEAST MODE JMP launch stagger")
        settings["beast_force_close_jmp_after_run"] = parse_bool_checkbox(fields["beast_force_close_jmp_after_run"])
        settings["beast_continue_on_imagej_error"] = parse_bool_checkbox(fields["beast_continue_on_imagej_error"])
        settings["beast_continue_on_jmp_error"] = parse_bool_checkbox(fields["beast_continue_on_jmp_error"])
        settings["beast_max_total_runs"] = parse_int_field(fields["beast_max_total_runs"], "BEAST MODE maximum total runs")
        settings["beast_checkpoint_every_runs"] = parse_int_field(fields["beast_checkpoint_every_runs"], "BEAST MODE checkpoint interval")
        settings["beast_organize_windows_enabled"] = parse_bool_checkbox(fields["beast_organize_windows_enabled"])
        settings["beast_organize_jmp_windows_enabled"] = parse_bool_checkbox(fields["beast_organize_jmp_windows_enabled"])
        # v193: Fiji worker count is user-configurable while remaining strictly bounded.
        if settings["beast_fiji_parallel_instances"] < 1:
            settings["beast_fiji_parallel_instances"] = 1
        if settings["beast_fiji_parallel_instances"] > 16:
            settings["beast_fiji_parallel_instances"] = 16
        if settings["beast_fiji_parallel_instances"] <= 1:
            settings["beast_parallel_fiji_enabled"] = False
        if settings["beast_fiji_worker_timeout_sec"] < 60:
            settings["beast_fiji_worker_timeout_sec"] = 60
        if settings["beast_fiji_no_progress_timeout_sec"] < 30:
            settings["beast_fiji_no_progress_timeout_sec"] = 30
        if settings["beast_fiji_worker_startup_timeout_sec"] < 5:
            settings["beast_fiji_worker_startup_timeout_sec"] = 5
        if settings["beast_fiji_worker_startup_timeout_sec"] > 300:
            settings["beast_fiji_worker_startup_timeout_sec"] = 300
        if settings["beast_fiji_heartbeat_interval_sec"] < 2:
            settings["beast_fiji_heartbeat_interval_sec"] = 2
        if settings["beast_fiji_heartbeat_interval_sec"] > 60:
            settings["beast_fiji_heartbeat_interval_sec"] = 60
        if settings["beast_fiji_heartbeat_timeout_sec"] < settings["beast_fiji_heartbeat_interval_sec"] * 3:
            settings["beast_fiji_heartbeat_timeout_sec"] = settings["beast_fiji_heartbeat_interval_sec"] * 3
        if settings["beast_fiji_claim_timeout_sec"] < 30:
            settings["beast_fiji_claim_timeout_sec"] = 30
        if settings["beast_fiji_job_timeout_sec"] < 60:
            settings["beast_fiji_job_timeout_sec"] = 60
        if settings["beast_fiji_runtime_retries"] < 0:
            settings["beast_fiji_runtime_retries"] = 0
        if settings["beast_fiji_runtime_retries"] > 10:
            settings["beast_fiji_runtime_retries"] = 10
        # v135 intentionally caps the full Fiji preflight marker budget at 15 seconds.
        if settings["beast_preflight_timeout_sec"] < 5:
            settings["beast_preflight_timeout_sec"] = 5
        if settings["beast_preflight_timeout_sec"] > 60:
            settings["beast_preflight_timeout_sec"] = 60
        if settings["beast_fiji_launch_stagger_sec"] < 0:
            settings["beast_fiji_launch_stagger_sec"] = 0.0
        if settings["beast_jmp_parallel_instances"] < 1:
            settings["beast_jmp_parallel_instances"] = 1
        if settings.get("beast_jmp_safe_launch_enabled", True):
            if settings["beast_jmp_launch_stagger_sec"] < 0.25:
                settings["beast_jmp_launch_stagger_sec"] = 0.25
            settings["beast_organize_jmp_windows_enabled"] = False
        if settings.get("beast_jmp_retry_count", 1) < 0:
            settings["beast_jmp_retry_count"] = 0
        if settings.get("beast_jmp_retry_delay_sec", 6.0) < 0.0:
            settings["beast_jmp_retry_delay_sec"] = 0.0
        if settings["beast_jmp_parallel_instances"] > 32:
            settings["beast_jmp_parallel_instances"] = 32
        if settings["beast_jmp_start_after_fiji_runs"] < 1:
            settings["beast_jmp_start_after_fiji_runs"] = 1
        if settings["beast_jmp_timeout_sec"] < 30:
            settings["beast_jmp_timeout_sec"] = 30
        if settings["beast_jmp_exit_grace_sec"] < 0:
            settings["beast_jmp_exit_grace_sec"] = 0.0
        if settings["beast_jmp_launch_stagger_sec"] < 0:
            settings["beast_jmp_launch_stagger_sec"] = 0.0
        if settings["beast_max_total_runs"] < 1:
            settings["beast_max_total_runs"] = DEFAULTS["beast_max_total_runs"]
        if settings["beast_checkpoint_every_runs"] < 1:
            settings["beast_checkpoint_every_runs"] = 1

        settings["create_word_report"] = parse_bool_checkbox(fields["create_word_report"])
        settings["open_word_report_when_done"] = parse_bool_checkbox(fields["open_word_report_when_done"])
        settings["open_word_report_when_done"] = False
        settings["report_filename_mode"] = str(fields["report_filename_mode"].getSelectedItem())
        settings["export_main_summary_xls"] = parse_bool_checkbox(fields["export_main_summary_xls"])
        settings["summary_xls_destination"] = str(fields["summary_xls_destination"].getSelectedItem())
        settings["summary_xls_custom_folder"] = parse_text(fields["summary_xls_custom_folder"])
        settings["reports_only_recovery_mode"] = parse_bool_checkbox(fields["reports_only_recovery_mode"])
        settings["reports_only_source_mode"] = str(fields["reports_only_source_mode"].getSelectedItem())
        settings["reports_only_output_mode"] = str(fields["reports_only_output_mode"].getSelectedItem())
        settings["always_finalize_partial_report"] = True
        settings["no_lossless_images_in_reports"] = parse_bool_checkbox(fields["no_lossless_images_in_reports"])
        settings["dont_save_lossless_generated_images"] = parse_bool_checkbox(fields["dont_save_lossless_generated_images"])
        settings["no_lossless_images_at_all"] = parse_bool_checkbox(fields["no_lossless_images_at_all"])
        if settings["no_lossless_images_at_all"]:
            settings["no_lossless_images_in_reports"] = True
            settings["dont_save_lossless_generated_images"] = True
        # Runtime helper used by image writers to skip redundant TIFF copies when the
        # user does not want to retain lossless generated analysis images.
        settings["_skip_redundant_generated_tiff"] = bool(settings["dont_save_lossless_generated_images"])
        # Excel summary export is intentionally independent from Word-report creation.
        # The six-mode Word report dropdown below is the only normal-mode authority.
        settings["report_launch_all_jmp"] = parse_bool_checkbox(fields["report_launch_all_jmp"])
        settings["report_wait_for_jmp"] = parse_bool_checkbox(fields["report_wait_for_jmp"])
        settings["report_wait_timeout_sec"] = parse_int_field(fields["report_wait_timeout_sec"], "Report JMP wait timeout")
        settings["report_title"] = parse_text(fields["report_title"])
        settings["report_sample_name"] = parse_text(fields["report_sample_name"])
        settings["report_scale_method"] = str(fields["report_scale_method"].getSelectedItem())
        settings["report_imaging_software"] = str(fields["report_imaging_software"].getSelectedItem())
        settings["word_report_mode"] = str(fields["word_report_mode"].getSelectedItem())
        settings["create_word_report"] = settings["word_report_mode"] != "No Word reports"
        settings["threshold_selection_reports_enabled"] = parse_bool_checkbox(fields["threshold_selection_reports_enabled"])
        settings["threshold_selection_create_full_combined"] = parse_bool_checkbox(fields["threshold_selection_create_full_combined"])
        settings["threshold_selection_folder_name"] = parse_text(fields["threshold_selection_folder_name"])
        settings["threshold_selection_criterion_1_enabled"] = parse_bool_checkbox(fields["threshold_selection_criterion_1_enabled"])
        settings["threshold_selection_criterion_1_metric"] = str(fields["threshold_selection_criterion_1_metric"].getSelectedItem())
        settings["threshold_selection_criterion_1_target"] = parse_text(fields["threshold_selection_criterion_1_target"])
        settings["threshold_selection_criterion_1_importance"] = parse_int_field(fields["threshold_selection_criterion_1_importance"], "Threshold selection target 1 importance")
        settings["threshold_selection_criterion_2_enabled"] = parse_bool_checkbox(fields["threshold_selection_criterion_2_enabled"])
        settings["threshold_selection_criterion_2_metric"] = str(fields["threshold_selection_criterion_2_metric"].getSelectedItem())
        settings["threshold_selection_criterion_2_target"] = parse_text(fields["threshold_selection_criterion_2_target"])
        settings["threshold_selection_criterion_2_importance"] = parse_int_field(fields["threshold_selection_criterion_2_importance"], "Threshold selection target 2 importance")
        settings["threshold_selection_criterion_3_enabled"] = parse_bool_checkbox(fields["threshold_selection_criterion_3_enabled"])
        settings["threshold_selection_criterion_3_metric"] = str(fields["threshold_selection_criterion_3_metric"].getSelectedItem())
        settings["threshold_selection_criterion_3_target"] = parse_text(fields["threshold_selection_criterion_3_target"])
        settings["threshold_selection_criterion_3_importance"] = parse_int_field(fields["threshold_selection_criterion_3_importance"], "Threshold selection target 3 importance")
        settings["threshold_selection_criterion_4_enabled"] = parse_bool_checkbox(fields["threshold_selection_criterion_4_enabled"])
        settings["threshold_selection_criterion_4_metric"] = str(fields["threshold_selection_criterion_4_metric"].getSelectedItem())
        settings["threshold_selection_criterion_4_target"] = parse_text(fields["threshold_selection_criterion_4_target"])
        settings["threshold_selection_criterion_4_importance"] = parse_int_field(fields["threshold_selection_criterion_4_importance"], "Threshold selection target 4 importance")
        settings["threshold_selection_criterion_5_enabled"] = parse_bool_checkbox(fields["threshold_selection_criterion_5_enabled"])
        settings["threshold_selection_criterion_5_metric"] = str(fields["threshold_selection_criterion_5_metric"].getSelectedItem())
        settings["threshold_selection_criterion_5_target"] = parse_text(fields["threshold_selection_criterion_5_target"])
        settings["threshold_selection_criterion_5_importance"] = parse_int_field(fields["threshold_selection_criterion_5_importance"], "Threshold selection target 5 importance")
        if settings["threshold_selection_folder_name"].strip() == "":
            settings["threshold_selection_folder_name"] = "Selected_Threshold_Reports"
        settings["threshold_selection_folder_name"] = safe_name(settings["threshold_selection_folder_name"])
        if settings["threshold_selection_reports_enabled"]:
            active_selection_criteria = 0
            if settings["threshold_selection_criterion_1_importance"] < 1:
                settings["threshold_selection_criterion_1_importance"] = 1
            if settings["threshold_selection_criterion_1_importance"] > 5:
                settings["threshold_selection_criterion_1_importance"] = 5
            if settings["threshold_selection_criterion_1_enabled"]:
                active_selection_criteria += 1
                if settings["threshold_selection_criterion_1_target"].strip() == "":
                    raise Exception("Threshold selection target 1 is enabled but its target value is blank.")
                parse_sweep_until_target(settings["threshold_selection_criterion_1_target"], settings["threshold_selection_criterion_1_metric"])
            if settings["threshold_selection_criterion_2_importance"] < 1:
                settings["threshold_selection_criterion_2_importance"] = 1
            if settings["threshold_selection_criterion_2_importance"] > 5:
                settings["threshold_selection_criterion_2_importance"] = 5
            if settings["threshold_selection_criterion_2_enabled"]:
                active_selection_criteria += 1
                if settings["threshold_selection_criterion_2_target"].strip() == "":
                    raise Exception("Threshold selection target 2 is enabled but its target value is blank.")
                parse_sweep_until_target(settings["threshold_selection_criterion_2_target"], settings["threshold_selection_criterion_2_metric"])
            if settings["threshold_selection_criterion_3_importance"] < 1:
                settings["threshold_selection_criterion_3_importance"] = 1
            if settings["threshold_selection_criterion_3_importance"] > 5:
                settings["threshold_selection_criterion_3_importance"] = 5
            if settings["threshold_selection_criterion_3_enabled"]:
                active_selection_criteria += 1
                if settings["threshold_selection_criterion_3_target"].strip() == "":
                    raise Exception("Threshold selection target 3 is enabled but its target value is blank.")
                parse_sweep_until_target(settings["threshold_selection_criterion_3_target"], settings["threshold_selection_criterion_3_metric"])
            if settings["threshold_selection_criterion_4_importance"] < 1:
                settings["threshold_selection_criterion_4_importance"] = 1
            if settings["threshold_selection_criterion_4_importance"] > 5:
                settings["threshold_selection_criterion_4_importance"] = 5
            if settings["threshold_selection_criterion_4_enabled"]:
                active_selection_criteria += 1
                if settings["threshold_selection_criterion_4_target"].strip() == "":
                    raise Exception("Threshold selection target 4 is enabled but its target value is blank.")
                parse_sweep_until_target(settings["threshold_selection_criterion_4_target"], settings["threshold_selection_criterion_4_metric"])
            if settings["threshold_selection_criterion_5_importance"] < 1:
                settings["threshold_selection_criterion_5_importance"] = 1
            if settings["threshold_selection_criterion_5_importance"] > 5:
                settings["threshold_selection_criterion_5_importance"] = 5
            if settings["threshold_selection_criterion_5_enabled"]:
                active_selection_criteria += 1
                if settings["threshold_selection_criterion_5_target"].strip() == "":
                    raise Exception("Threshold selection target 5 is enabled but its target value is blank.")
                parse_sweep_until_target(settings["threshold_selection_criterion_5_target"], settings["threshold_selection_criterion_5_metric"])
            if active_selection_criteria < 1:
                raise Exception("Enable at least one threshold-selection target.")
        settings["report_sweep_comparison_enabled"] = parse_bool_checkbox(fields["report_sweep_comparison_enabled"])
        # v209: these Report-page controls existed in v198-v200 but were never copied into
        # the runtime settings dict, so the DOCX builder could silently see them as False/missing.
        settings["report_include_strand_heat_map"] = parse_bool_checkbox(fields["report_include_strand_heat_map"]) if fields.get("report_include_strand_heat_map") is not None else bool(DEFAULTS.get("report_include_strand_heat_map", True))
        settings["report_save_strand_heat_map"] = parse_bool_checkbox(fields["report_save_strand_heat_map"]) if fields.get("report_save_strand_heat_map") is not None else bool(DEFAULTS.get("report_save_strand_heat_map", True))
        settings["batch_sweep_reports_by_og_image"] = parse_bool_checkbox(fields["batch_sweep_reports_by_og_image"])
        settings["batch_sweep_export_all_summaries_to_all_reports"] = parse_bool_checkbox(fields["batch_sweep_export_all_summaries_to_all_reports"])
        settings["report_save_segmented_overlay_next_to_word"] = parse_bool_checkbox(fields.get("report_save_segmented_overlay_next_to_word")) if fields.get("report_save_segmented_overlay_next_to_word") is not None else bool(DEFAULTS.get("report_save_segmented_overlay_next_to_word", True))
        settings["report_segmented_overlay_fiber_color"] = str(fields["report_segmented_overlay_fiber_color"].getSelectedItem()) if fields.get("report_segmented_overlay_fiber_color") is not None else str(DEFAULTS.get("report_segmented_overlay_fiber_color", "Red"))
        settings["report_segmented_overlay_fiber_opacity_percent"] = max(0.0, min(100.0, parse_float_field(fields["report_segmented_overlay_fiber_opacity_percent"], "Segmented overlay fiber opacity"))) if fields.get("report_segmented_overlay_fiber_opacity_percent") is not None else float(DEFAULTS.get("report_segmented_overlay_fiber_opacity_percent", 70.0))
        settings["report_segmented_overlay_annotation_opacity_percent"] = max(0.0, min(100.0, parse_float_field(fields["report_segmented_overlay_annotation_opacity_percent"], "Segmented overlay annotation opacity"))) if fields.get("report_segmented_overlay_annotation_opacity_percent") is not None else float(DEFAULTS.get("report_segmented_overlay_annotation_opacity_percent", 85.0))
        settings["report_segmented_pores_overlay_opacity_percent"] = max(0.0, min(100.0, parse_float_field(fields["report_segmented_pores_overlay_opacity_percent"], "Segmented black/white overlay opacity"))) if fields.get("report_segmented_pores_overlay_opacity_percent") is not None else float(DEFAULTS.get("report_segmented_pores_overlay_opacity_percent", 20.0))
        settings["save_fiji_log_enabled"] = parse_bool_checkbox(fields.get("save_fiji_log_enabled")) if fields.get("save_fiji_log_enabled") is not None else bool(DEFAULTS.get("save_fiji_log_enabled", True))
        settings["report_main_image_width_in"] = parse_float_field(fields["report_main_image_width_in"], "Report main image width")
        settings["report_hist_image_width_in"] = parse_float_field(fields["report_hist_image_width_in"], "Report histogram image width")
        settings["report_pore_map_width_in"] = parse_float_field(fields["report_pore_map_width_in"], "Report pore map image width")
        settings["docx_body_page_width_in"] = parse_float_field(fields["docx_body_page_width_in"], "Entire report/body page width")
        settings["docx_body_page_height_in"] = parse_float_field(fields["docx_body_page_height_in"], "Entire report/body page height")
        settings["docx_body_margin_in"] = parse_float_field(fields["docx_body_margin_in"], "Entire report/body page margin")
        settings["docx_summary_page_width_in"] = parse_float_field(fields["docx_summary_page_width_in"], "End summary page width")
        settings["docx_summary_page_height_in"] = parse_float_field(fields["docx_summary_page_height_in"], "End summary page height")
        settings["docx_summary_margin_in"] = parse_float_field(fields["docx_summary_margin_in"], "End summary page margin")
        settings["highlight_largest_pore_in_segmented"] = parse_bool_checkbox(fields["highlight_largest_pore_in_segmented"])
        settings["manual_largest_pore_enabled"] = parse_bool_checkbox(fields["manual_largest_pore_enabled"])
        settings["manual_largest_pore_count"] = parse_int_field(fields["manual_largest_pore_count"], "Manual largest pore count")
        settings["manual_selected_pore_enabled"] = parse_bool_checkbox(fields["manual_selected_pore_enabled"])
        settings["manual_selected_pore_count"] = parse_int_field(fields["manual_selected_pore_count"], "Manual selected pore count")
        settings["manual_success_popup_show_picture"] = parse_bool_checkbox(fields["manual_success_popup_show_picture"])
        settings["manual_strand_measurement_enabled"] = parse_bool_checkbox(fields["manual_strand_measurement_enabled"])
        # One accepted strand is measured per original batch image and reused across its runs/sweeps.
        settings["manual_strand_count"] = 1 if settings["manual_strand_measurement_enabled"] else 0
        if settings["manual_largest_pore_count"] < 1:
            settings["manual_largest_pore_count"] = 1
        if settings["manual_selected_pore_count"] < 1:
            settings["manual_selected_pore_count"] = 1
        if settings["manual_strand_count"] < 0:
            settings["manual_strand_count"] = 0

        # v89: separate manual-largest-pore measurement is retired from the normal startup flow.
        # Manual pore tracing now shows the largest-pore guide on the same trace image and lets the user trace any pore.
        settings["manual_largest_pore_enabled"] = False
        settings["manual_largest_pore_count"] = 0

        if not settings.get("manual_measurements_enabled", True):
            settings["manual_largest_pore_enabled"] = False
            settings["manual_largest_pore_count"] = 0
            settings["manual_selected_pore_enabled"] = False
            settings["manual_selected_pore_count"] = 0
            settings["manual_strand_measurement_enabled"] = False
            settings["manual_strand_count"] = 0
        settings["guide_largest_outline_color"] = str(fields["guide_largest_outline_color"].getSelectedItem())
        settings["guide_selected_outline_color"] = str(fields["guide_selected_outline_color"].getSelectedItem())
        settings["guide_outline_extra_pixels"] = parse_float_field(fields["guide_outline_extra_pixels"], "Guide outline outward offset")
        settings["guide_outline_line_width"] = parse_int_field(fields["guide_outline_line_width"], "Guide outline line width")
        settings["segmented_largest_fill_color"] = str(fields["segmented_largest_fill_color"].getSelectedItem())
        settings["segmented_selected_fill_color"] = str(fields["segmented_selected_fill_color"].getSelectedItem())
        settings["segmented_outline_line_width"] = parse_int_field(fields["segmented_outline_line_width"], "Segmented label/backup line width")
        settings["report_pore_map_low_marker_radius"] = parse_int_field(fields["report_pore_map_low_marker_radius"], "Small-pore marker radius")
        settings["report_pore_map_high_marker_radius"] = parse_int_field(fields["report_pore_map_high_marker_radius"], "Large-pore marker radius")
        # Legacy aliases retain the small-pore size for saved-preset compatibility.
        settings["report_pore_map_marker_radius"] = settings["report_pore_map_low_marker_radius"]
        settings["report_pore_marker_radius"] = settings["report_pore_map_low_marker_radius"]
        settings["report_pore_map_opacity_percent"] = parse_float_field(fields["report_pore_map_opacity_percent"], "Pore-map opacity")
        settings["report_pore_map_background"] = str(fields["report_pore_map_background"].getSelectedItem())
        settings["pore_map_low_color"] = str(fields["pore_map_low_color"].getSelectedItem())
        settings["pore_map_high_color"] = "red"
        # Keep legacy v114 color keys synchronized.
        settings["pore_map_band_1_color"] = settings["pore_map_low_color"]
        settings["pore_map_band_2_color"] = settings["pore_map_low_color"]
        settings["pore_map_band_3_color"] = settings["pore_map_low_color"]
        settings["report_pore_map_high_cutoff"] = 0.025
        settings["report_pore_map_show_legend"] = parse_bool_checkbox(fields["report_pore_map_show_legend"])
        settings["report_all_pore_map_enabled"] = parse_bool_checkbox(fields["report_all_pore_map_enabled"])
        settings["report_all_pore_map_style"] = str(fields["report_all_pore_map_style"].getSelectedItem())
        settings["report_all_pore_map_show_legend"] = parse_bool_checkbox(fields["report_all_pore_map_show_legend"])
        settings["report_scale_bar_enabled"] = True  # forced on: report scale bars are always added
        settings["report_scale_bar_auto_fit_enabled"] = parse_bool_checkbox(fields["report_scale_bar_auto_fit_enabled"])
        settings["report_scale_bar_length_mm"] = parse_float_field(fields["report_scale_bar_length_mm"], "Normal fixed scale bar length")
        settings["report_scale_bar_thickness_px"] = parse_int_field(fields["report_scale_bar_thickness_px"], "Scale bar thickness")
        settings["report_scale_bar_margin_px"] = parse_int_field(fields["report_scale_bar_margin_px"], "Scale bar margin")
        settings["report_scale_bar_color"] = str(fields["report_scale_bar_color"].getSelectedItem())
        settings["report_scale_bar_label_enabled"] = parse_bool_checkbox(fields["report_scale_bar_label_enabled"])
        settings["report_scale_bar_text_color"] = str(fields["report_scale_bar_text_color"].getSelectedItem())
        settings["report_scale_bar_text_outline_enabled"] = parse_bool_checkbox(fields["report_scale_bar_text_outline_enabled"])
        settings["report_scale_bar_text_outline_color"] = str(fields["report_scale_bar_text_outline_color"].getSelectedItem())
        settings["report_scale_bar_font_size_px"] = parse_int_field(fields["report_scale_bar_font_size_px"], "Scale bar label font size")
        settings["bad_image_detection_enabled"] = parse_bool_checkbox(fields["bad_image_detection_enabled"])
        settings["popup_warning_summary_enabled"] = parse_bool_checkbox(fields["popup_warning_summary_enabled"])
        settings["scale_sanity_warning_enabled"] = parse_bool_checkbox(fields["scale_sanity_warning_enabled"])
        settings["scale_sanity_min_image_area_mm2"] = parse_float_field(fields["scale_sanity_min_image_area_mm2"], "Scale sanity minimum image area")
        settings["scale_sanity_max_image_area_mm2"] = parse_float_field(fields["scale_sanity_max_image_area_mm2"], "Scale sanity maximum image area")
        settings["scale_sanity_min_pixel_size_mm"] = parse_float_field(fields["scale_sanity_min_pixel_size_mm"], "Scale sanity minimum pixel size")
        settings["scale_sanity_max_pixel_size_mm"] = parse_float_field(fields["scale_sanity_max_pixel_size_mm"], "Scale sanity maximum pixel size")
        settings["particle_count_sanity_enabled"] = parse_bool_checkbox(fields["particle_count_sanity_enabled"])
        settings["particle_count_high_limit"] = parse_int_field(fields["particle_count_high_limit"], "Particle count warning limit")
        settings["particle_count_change_warning_percent"] = parse_float_field(fields["particle_count_change_warning_percent"], "Particle count change warning percent")
        if settings["scale_sanity_min_image_area_mm2"] < 0:
            settings["scale_sanity_min_image_area_mm2"] = DEFAULTS["scale_sanity_min_image_area_mm2"]
        if settings["scale_sanity_max_image_area_mm2"] <= 0:
            settings["scale_sanity_max_image_area_mm2"] = DEFAULTS["scale_sanity_max_image_area_mm2"]
        if settings["scale_sanity_max_image_area_mm2"] < settings["scale_sanity_min_image_area_mm2"]:
            settings["scale_sanity_max_image_area_mm2"] = settings["scale_sanity_min_image_area_mm2"]
        if settings["scale_sanity_min_pixel_size_mm"] < 0:
            settings["scale_sanity_min_pixel_size_mm"] = DEFAULTS["scale_sanity_min_pixel_size_mm"]
        if settings["scale_sanity_max_pixel_size_mm"] <= 0:
            settings["scale_sanity_max_pixel_size_mm"] = DEFAULTS["scale_sanity_max_pixel_size_mm"]
        if settings["scale_sanity_max_pixel_size_mm"] < settings["scale_sanity_min_pixel_size_mm"]:
            settings["scale_sanity_max_pixel_size_mm"] = settings["scale_sanity_min_pixel_size_mm"]
        if settings["particle_count_high_limit"] < 1:
            settings["particle_count_high_limit"] = DEFAULTS["particle_count_high_limit"]
        if settings["particle_count_change_warning_percent"] < 0:
            settings["particle_count_change_warning_percent"] = DEFAULTS["particle_count_change_warning_percent"]
        if settings["report_wait_timeout_sec"] < 0:
            settings["report_wait_timeout_sec"] = 0
        if settings["report_main_image_width_in"] <= 0:
            settings["report_main_image_width_in"] = DEFAULTS["report_main_image_width_in"]
        if settings["report_hist_image_width_in"] <= 0:
            settings["report_hist_image_width_in"] = DEFAULTS["report_hist_image_width_in"]
        if settings["report_pore_map_width_in"] <= 0:
            settings["report_pore_map_width_in"] = DEFAULTS["report_pore_map_width_in"]
        if settings["docx_body_page_width_in"] <= 0:
            settings["docx_body_page_width_in"] = DEFAULTS["docx_body_page_width_in"]
        if settings["docx_body_page_height_in"] <= 0:
            settings["docx_body_page_height_in"] = DEFAULTS["docx_body_page_height_in"]
        if settings["docx_body_margin_in"] < 0:
            settings["docx_body_margin_in"] = DEFAULTS["docx_body_margin_in"]
        if settings["docx_summary_page_width_in"] <= 0:
            settings["docx_summary_page_width_in"] = DEFAULTS["docx_summary_page_width_in"]
        if settings["docx_summary_page_height_in"] <= 0:
            settings["docx_summary_page_height_in"] = DEFAULTS["docx_summary_page_height_in"]
        if settings["docx_summary_margin_in"] < 0:
            settings["docx_summary_margin_in"] = DEFAULTS["docx_summary_margin_in"]
        if settings["report_pore_map_low_marker_radius"] < 1:
            settings["report_pore_map_low_marker_radius"] = DEFAULTS["report_pore_map_low_marker_radius"]
        if settings["report_pore_map_high_marker_radius"] < 1:
            settings["report_pore_map_high_marker_radius"] = DEFAULTS["report_pore_map_high_marker_radius"]
        if settings["report_pore_map_opacity_percent"] < 0.0:
            settings["report_pore_map_opacity_percent"] = 0.0
        if settings["report_pore_map_opacity_percent"] > 100.0:
            settings["report_pore_map_opacity_percent"] = 100.0
        settings["report_pore_map_marker_radius"] = settings["report_pore_map_low_marker_radius"]
        settings["report_pore_marker_radius"] = settings["report_pore_map_low_marker_radius"]
        settings["report_pore_map_high_cutoff"] = 0.025
        if settings["report_scale_bar_length_mm"] <= 0:
            settings["report_scale_bar_length_mm"] = DEFAULTS["report_scale_bar_length_mm"]
        if settings["report_scale_bar_thickness_px"] < 1:
            settings["report_scale_bar_thickness_px"] = DEFAULTS["report_scale_bar_thickness_px"]
        if settings["report_scale_bar_margin_px"] < 0:
            settings["report_scale_bar_margin_px"] = DEFAULTS["report_scale_bar_margin_px"]
        if settings["report_scale_bar_font_size_px"] < 6:
            settings["report_scale_bar_font_size_px"] = DEFAULTS["report_scale_bar_font_size_px"]
        if settings["guide_outline_extra_pixels"] < 0:
            settings["guide_outline_extra_pixels"] = DEFAULTS["guide_outline_extra_pixels"]
        if settings["guide_outline_line_width"] < 1:
            settings["guide_outline_line_width"] = DEFAULTS["guide_outline_line_width"]
        if settings["segmented_outline_line_width"] < 1:
            settings["segmented_outline_line_width"] = DEFAULTS["segmented_outline_line_width"]

        settings["launch_jmp"] = parse_bool_checkbox(fields["launch_jmp"])
        settings["max_jmp_launches"] = parse_int_field(fields["max_jmp_launches"], "Maximum simultaneous JMP instances")
        settings["jmp_streaming_enabled"] = parse_bool_checkbox(fields["jmp_streaming_enabled"])
        settings["jmp_start_after_fiji_runs"] = parse_int_field(fields["jmp_start_after_fiji_runs"], "JMP streaming start threshold")
        settings["jmp_force_exit_after_run"] = True
        if settings["max_jmp_launches"] < 1:
            settings["max_jmp_launches"] = 1
        if settings["max_jmp_launches"] > 32:
            settings["max_jmp_launches"] = 32
        if settings["jmp_start_after_fiji_runs"] < 1:
            settings["jmp_start_after_fiji_runs"] = 1
        settings["jmp_exe"] = parse_text(fields["jmp_exe"])
        settings["jmp_hist_graph_width"] = parse_int_field(fields["jmp_hist_graph_width"], "Histogram image width")
        settings["jmp_hist_graph_height"] = parse_int_field(fields["jmp_hist_graph_height"], "Histogram image height")
        settings["jmp_hist_show_legend"] = parse_bool_checkbox(fields["jmp_hist_show_legend"])
        settings["jmp_hist_show_graph_titles"] = parse_bool_checkbox(fields["jmp_hist_show_graph_titles"])
        settings["jmp_hist_show_axis_titles"] = parse_bool_checkbox(fields["jmp_hist_show_axis_titles"])
        settings["jmp_hist_trim_trailing_zeros"] = parse_bool_checkbox(fields["jmp_hist_trim_trailing_zeros"])
        settings["jmp_hist_axis_pad_percent"] = parse_float_field(fields["jmp_hist_axis_pad_percent"], "Histogram X-axis padding percent")
        settings["jmp_hist_auto_binning"] = parse_bool_checkbox(fields["jmp_hist_auto_binning"])
        settings["jmp_hist_max_bins"] = parse_int_field(fields["jmp_hist_max_bins"], "Fixed-bin fallback/default histogram bins")

        settings["jmp_hist_epd_title"] = parse_text(fields["jmp_hist_epd_title"])
        settings["jmp_hist_epd_x_axis_title"] = parse_text(fields["jmp_hist_epd_x_axis_title"])
        settings["jmp_hist_epd_y_axis_title"] = parse_text(fields["jmp_hist_epd_y_axis_title"])
        settings["jmp_hist_epd_bins"] = parse_int_field(fields["jmp_hist_epd_bins"], "EPD histogram bins")
        settings["jmp_hist_epd_x_min"] = parse_float_field(fields["jmp_hist_epd_x_min"], "EPD X-axis min")
        settings["jmp_hist_epd_x_max"] = parse_float_field(fields["jmp_hist_epd_x_max"], "EPD X-axis max")
        settings["jmp_hist_epd_major_tick"] = parse_float_field(fields["jmp_hist_epd_major_tick"], "EPD X-axis major tick spacing")
        settings["jmp_hist_epd_x_minor_ticks"] = parse_int_field(fields["jmp_hist_epd_x_minor_ticks"], "EPD X-axis minor ticks")
        settings["jmp_hist_epd_y_max"] = parse_float_field(fields["jmp_hist_epd_y_max"], "EPD Y-axis max")
        settings["jmp_hist_epd_y_major_tick"] = parse_float_field(fields["jmp_hist_epd_y_major_tick"], "EPD Y-axis major tick spacing")
        settings["jmp_hist_epd_y_minor_ticks"] = parse_int_field(fields["jmp_hist_epd_y_minor_ticks"], "EPD Y-axis minor ticks")
        settings["jmp_epd_show_cutoff_lines"] = parse_bool_checkbox(fields["jmp_epd_show_cutoff_lines"])
        settings["jmp_epd_hist_round_filter_enabled"] = parse_bool_checkbox(fields["jmp_epd_hist_round_filter_enabled"])
        settings["jmp_epd_hist_round_filter_min"] = parse_float_field(fields["jmp_epd_hist_round_filter_min"], "EPD histogram minimum roundness")

        settings["jmp_hist_round_title"] = parse_text(fields["jmp_hist_round_title"])
        settings["jmp_hist_round_x_axis_title"] = parse_text(fields["jmp_hist_round_x_axis_title"])
        settings["jmp_hist_round_y_axis_title"] = parse_text(fields["jmp_hist_round_y_axis_title"])
        settings["jmp_hist_round_bins"] = parse_int_field(fields["jmp_hist_round_bins"], "Roundness histogram bins")
        settings["jmp_hist_round_x_min"] = parse_float_field(fields["jmp_hist_round_x_min"], "Roundness X-axis min")
        settings["jmp_hist_round_x_max"] = parse_float_field(fields["jmp_hist_round_x_max"], "Roundness X-axis max")
        settings["jmp_hist_round_x_major_tick"] = parse_float_field(fields["jmp_hist_round_x_major_tick"], "Roundness X-axis major tick spacing")
        settings["jmp_hist_round_x_minor_ticks"] = parse_int_field(fields["jmp_hist_round_x_minor_ticks"], "Roundness X-axis minor ticks")
        settings["jmp_hist_round_y_max"] = parse_float_field(fields["jmp_hist_round_y_max"], "Roundness Y-axis max")
        settings["jmp_hist_round_y_major_tick"] = parse_float_field(fields["jmp_hist_round_y_major_tick"], "Roundness Y-axis major tick spacing")
        settings["jmp_hist_round_y_minor_ticks"] = parse_int_field(fields["jmp_hist_round_y_minor_ticks"], "Roundness Y-axis minor ticks")

        settings["jmp_hist_circ_title"] = parse_text(fields["jmp_hist_circ_title"])
        settings["jmp_hist_circ_x_axis_title"] = parse_text(fields["jmp_hist_circ_x_axis_title"])
        settings["jmp_hist_circ_y_axis_title"] = parse_text(fields["jmp_hist_circ_y_axis_title"])
        settings["jmp_hist_circ_bins"] = parse_int_field(fields["jmp_hist_circ_bins"], "Circularity histogram bins")
        settings["jmp_hist_circ_x_min"] = parse_float_field(fields["jmp_hist_circ_x_min"], "Circularity X-axis min")
        settings["jmp_hist_circ_x_max"] = parse_float_field(fields["jmp_hist_circ_x_max"], "Circularity X-axis max")
        settings["jmp_hist_circ_x_major_tick"] = parse_float_field(fields["jmp_hist_circ_x_major_tick"], "Circularity X-axis major tick spacing")
        settings["jmp_hist_circ_x_minor_ticks"] = parse_int_field(fields["jmp_hist_circ_x_minor_ticks"], "Circularity X-axis minor ticks")
        settings["jmp_hist_circ_y_max"] = parse_float_field(fields["jmp_hist_circ_y_max"], "Circularity Y-axis max")
        settings["jmp_hist_circ_y_major_tick"] = parse_float_field(fields["jmp_hist_circ_y_major_tick"], "Circularity Y-axis major tick spacing")
        settings["jmp_hist_circ_y_minor_ticks"] = parse_int_field(fields["jmp_hist_circ_y_minor_ticks"], "Circularity Y-axis minor ticks")

        settings["jmp_summary_use_all_detected"] = False
        settings["flag_weird_pores_enabled"] = parse_bool_checkbox(fields["flag_weird_pores_enabled"])
        settings["flag_weird_epd_above"] = parse_float_field(fields["flag_weird_epd_above"], "Flag EPD above")
        settings["flag_weird_circularity_below"] = parse_float_field(fields["flag_weird_circularity_below"], "Flag Circularity below")
        settings["flag_weird_roundness_below"] = parse_float_field(fields["flag_weird_roundness_below"], "Flag Roundness below")
        settings["flag_weird_roundness_above"] = parse_float_field(fields["flag_weird_roundness_above"], "Flag Roundness above")
        if settings["jmp_hist_graph_width"] < 200:
            settings["jmp_hist_graph_width"] = DEFAULTS["jmp_hist_graph_width"]
        if settings["jmp_hist_graph_height"] < 150:
            settings["jmp_hist_graph_height"] = DEFAULTS["jmp_hist_graph_height"]
        if settings["jmp_hist_max_bins"] < 1:
            settings["jmp_hist_max_bins"] = 1
        if settings["jmp_hist_epd_bins"] < 1:
            settings["jmp_hist_epd_bins"] = settings["jmp_hist_max_bins"]
        if settings["jmp_hist_epd_title"] == "":
            settings["jmp_hist_epd_title"] = DEFAULTS["jmp_hist_epd_title"]
        if settings["jmp_hist_epd_x_axis_title"] == "":
            settings["jmp_hist_epd_x_axis_title"] = DEFAULTS["jmp_hist_epd_x_axis_title"]
        if settings["jmp_hist_epd_y_axis_title"] == "":
            settings["jmp_hist_epd_y_axis_title"] = DEFAULTS["jmp_hist_epd_y_axis_title"]
        if settings["jmp_hist_epd_major_tick"] < 0:
            settings["jmp_hist_epd_major_tick"] = 0.0
        if settings["jmp_hist_epd_x_minor_ticks"] < 0:
            settings["jmp_hist_epd_x_minor_ticks"] = 0
        if settings["jmp_hist_epd_x_min"] < 0:
            settings["jmp_hist_epd_x_min"] = 0.0
        if settings["jmp_hist_epd_x_max"] < 0:
            settings["jmp_hist_epd_x_max"] = 0.0
        if settings["jmp_hist_epd_y_max"] < 0:
            settings["jmp_hist_epd_y_max"] = 0.0
        if settings["jmp_hist_epd_y_major_tick"] < 0:
            settings["jmp_hist_epd_y_major_tick"] = 0.0
        if settings["jmp_hist_epd_y_minor_ticks"] < 0:
            settings["jmp_hist_epd_y_minor_ticks"] = 0
        if settings["jmp_epd_hist_round_filter_min"] < 0:
            settings["jmp_epd_hist_round_filter_min"] = 0.0
        if settings["jmp_epd_hist_round_filter_min"] > 1:
            settings["jmp_epd_hist_round_filter_min"] = 1.0
        if settings["jmp_hist_round_bins"] < 1:
            settings["jmp_hist_round_bins"] = settings["jmp_hist_max_bins"]
        if settings["jmp_hist_round_title"] == "":
            settings["jmp_hist_round_title"] = DEFAULTS["jmp_hist_round_title"]
        if settings["jmp_hist_round_x_axis_title"] == "":
            settings["jmp_hist_round_x_axis_title"] = DEFAULTS["jmp_hist_round_x_axis_title"]
        if settings["jmp_hist_round_y_axis_title"] == "":
            settings["jmp_hist_round_y_axis_title"] = DEFAULTS["jmp_hist_round_y_axis_title"]
        if settings["jmp_hist_round_x_min"] < 0:
            settings["jmp_hist_round_x_min"] = 0.0
        if settings["jmp_hist_round_x_max"] < 0:
            settings["jmp_hist_round_x_max"] = 0.0
        if settings["jmp_hist_round_x_major_tick"] < 0:
            settings["jmp_hist_round_x_major_tick"] = 0.0
        if settings["jmp_hist_round_x_minor_ticks"] < 0:
            settings["jmp_hist_round_x_minor_ticks"] = 0
        if settings["jmp_hist_round_y_max"] < 0:
            settings["jmp_hist_round_y_max"] = 0.0
        if settings["jmp_hist_round_y_major_tick"] < 0:
            settings["jmp_hist_round_y_major_tick"] = 0.0
        if settings["jmp_hist_round_y_minor_ticks"] < 0:
            settings["jmp_hist_round_y_minor_ticks"] = 0
        if settings["jmp_hist_circ_bins"] < 1:
            settings["jmp_hist_circ_bins"] = settings["jmp_hist_max_bins"]
        if settings["jmp_hist_circ_title"] == "":
            settings["jmp_hist_circ_title"] = DEFAULTS["jmp_hist_circ_title"]
        if settings["jmp_hist_circ_x_axis_title"] == "":
            settings["jmp_hist_circ_x_axis_title"] = DEFAULTS["jmp_hist_circ_x_axis_title"]
        if settings["jmp_hist_circ_y_axis_title"] == "":
            settings["jmp_hist_circ_y_axis_title"] = DEFAULTS["jmp_hist_circ_y_axis_title"]
        if settings["jmp_hist_circ_x_min"] < 0:
            settings["jmp_hist_circ_x_min"] = 0.0
        if settings["jmp_hist_circ_x_max"] < 0:
            settings["jmp_hist_circ_x_max"] = 0.0
        if settings["jmp_hist_circ_x_major_tick"] < 0:
            settings["jmp_hist_circ_x_major_tick"] = 0.0
        if settings["jmp_hist_circ_x_minor_ticks"] < 0:
            settings["jmp_hist_circ_x_minor_ticks"] = 0
        if settings["jmp_hist_circ_y_max"] < 0:
            settings["jmp_hist_circ_y_max"] = 0.0
        if settings["jmp_hist_circ_y_major_tick"] < 0:
            settings["jmp_hist_circ_y_major_tick"] = 0.0
        if settings["jmp_hist_circ_y_minor_ticks"] < 0:
            settings["jmp_hist_circ_y_minor_ticks"] = 0
        if settings["jmp_hist_axis_pad_percent"] < 0:
            settings["jmp_hist_axis_pad_percent"] = 0.0
        settings["csv_decimals"] = parse_int_field(fields["csv_decimals"], "CSV decimal places")
        settings["imagej_results_precision"] = parse_int_field(fields["imagej_results_precision"], "ImageJ Results precision")
        settings["docx_report_decimals"] = parse_int_field(fields["docx_report_decimals"], "DOCX max decimal places")
        if "save_settings_as_default" in fields:
            settings["save_settings_as_default"] = parse_bool_checkbox(fields["save_settings_as_default"])
        else:
            settings["save_settings_as_default"] = False
        settings["open_output_folder_when_done"] = parse_bool_checkbox(fields["open_output_folder_when_done"])
        settings["set_scale_only_mode"] = parse_bool_checkbox(fields["set_scale_only_mode"])
        settings["swift_magn_scale_enabled"] = parse_bool_checkbox(fields["swift_magn_scale_enabled"])
        settings["swift_magn_filename"] = parse_text(fields["swift_magn_filename"])
        settings["swift_magn_profile_name"] = str(field_text_value(fields["swift_magn_profile_name"])).strip()
        settings["swift_magn_search_parent_levels"] = parse_int_field(fields["swift_magn_search_parent_levels"], "Swift .magn parent-folder search levels")
        settings["swift_magn_use_bundle_fallback"] = parse_bool_checkbox(fields["swift_magn_use_bundle_fallback"])
        settings["swift_magn_override_existing_scale"] = parse_bool_checkbox(fields["swift_magn_override_existing_scale"])
        if settings["swift_magn_filename"].strip() == "":
            settings["swift_magn_filename"] = "Imaging.magn"
        if settings["swift_magn_profile_name"].strip() == "":
            settings["swift_magn_profile_name"] = "AUTO"
        if settings["swift_magn_search_parent_levels"] < 0:
            settings["swift_magn_search_parent_levels"] = 0
        if settings["swift_magn_search_parent_levels"] > 12:
            settings["swift_magn_search_parent_levels"] = 12
        settings["set_scale_direct_enabled"] = parse_bool_checkbox(fields["set_scale_direct_enabled"])
        settings["set_scale_direct_mm_per_pixel"] = parse_float_field(fields["set_scale_direct_mm_per_pixel"], "Manual scale mm per pixel")
        settings["set_scale_direct_pixels_per_mm"] = parse_float_field(fields["set_scale_direct_pixels_per_mm"], "Manual scale pixels per mm")
        settings["auto_scale_save_tif_enabled"] = parse_bool_checkbox(fields["auto_scale_save_tif_enabled"])
        settings["auto_scale_save_tif_subfolder_enabled"] = parse_bool_checkbox(fields["auto_scale_save_tif_subfolder_enabled"])
        settings["auto_scale_replace_png_with_tif_enabled"] = parse_bool_checkbox(fields["auto_scale_replace_png_with_tif_enabled"])
        if settings["auto_scale_replace_png_with_tif_enabled"] or settings["auto_scale_save_tif_subfolder_enabled"]:
            settings["auto_scale_save_tif_enabled"] = True
        settings["auto_scale_blue_ocr_enabled"] = parse_bool_checkbox(fields["auto_scale_blue_ocr_enabled"])
        settings["auto_scale_blue_search_padding_px"] = parse_int_field(fields["auto_scale_blue_search_padding_px"], "Orange/blue text search padding")
        settings["auto_scale_preview_zoom_factor"] = parse_float_field(fields["auto_scale_preview_zoom_factor"], "Scale preview zoom factor")
        if settings["auto_scale_blue_search_padding_px"] < 20:
            settings["auto_scale_blue_search_padding_px"] = DEFAULTS["auto_scale_blue_search_padding_px"]
        if settings["auto_scale_preview_zoom_factor"] < 1.0:
            settings["auto_scale_preview_zoom_factor"] = 1.0
        if settings["auto_scale_preview_zoom_factor"] > 10.0:
            settings["auto_scale_preview_zoom_factor"] = 10.0
        if settings["set_scale_direct_mm_per_pixel"] < 0:
            settings["set_scale_direct_mm_per_pixel"] = 0.0
        if settings["set_scale_direct_pixels_per_mm"] < 0:
            settings["set_scale_direct_pixels_per_mm"] = 0.0
        settings["preset_name"] = parse_text(fields["preset_name"])
        settings["load_named_preset"] = parse_bool_checkbox(fields["load_named_preset"])
        settings["save_named_preset"] = parse_bool_checkbox(fields["save_named_preset"])

        if settings["load_named_preset"]:
            settings = load_named_preset_into_settings(settings, settings.get("preset_name", ""))

        if settings["csv_decimals"] < 0:
            settings["csv_decimals"] = DEFAULTS["csv_decimals"]
        if settings["imagej_results_precision"] < 0:
            settings["imagej_results_precision"] = DEFAULTS["imagej_results_precision"]
        if settings["docx_report_decimals"] < 0:
            settings["docx_report_decimals"] = DEFAULTS["docx_report_decimals"]

        settings["process_pipeline_steps"] = collect_pipeline_steps_from_fields(fields)
        settings["process_pipeline_order"] = ",".join(str(step.get("operation", "")) for step in settings["process_pipeline_steps"])
        sync_legacy_processing_settings(settings)

        settings["threshold_min"] = parse_float_field(fields["threshold_min"], "Threshold min")
        settings["threshold_max"] = parse_float_field(fields["threshold_max"], "Threshold max")
        settings["black_background"] = parse_bool_checkbox(fields["black_background"])
        settings["threshold_force_8bit_numbers"] = parse_bool_checkbox(fields["threshold_force_8bit_numbers"])
        settings["threshold_input_mode"] = threshold_input_mode_label(settings["threshold_force_8bit_numbers"])
        threshold_input_limit = 255.0 if threshold_mode_is_gray(settings["threshold_force_8bit_numbers"]) else 100.0
        if settings["threshold_min"] < 0.0 or settings["threshold_min"] > threshold_input_limit:
            raise Exception("Threshold min must be between 0 and " + str(int(threshold_input_limit)) + " for " + settings["threshold_input_mode"] + ".")
        if settings["threshold_max"] < 0.0 or settings["threshold_max"] > threshold_input_limit:
            raise Exception("Threshold max must be between 0 and " + str(int(threshold_input_limit)) + " for " + settings["threshold_input_mode"] + ".")

        settings["fiber_fixer_enabled"] = parse_bool_checkbox(fields["fiber_fixer_enabled"])
        settings["fiber_fixer_absolute_threshold_max"] = parse_int_field(fields["fiber_fixer_absolute_threshold_max"], "Fiber Fixer absolute threshold max")
        settings["fiber_fixer_wire_width_px"] = parse_int_field(fields["fiber_fixer_wire_width_px"], "Fiber Fixer wire width")
        settings["fiber_fixer_save_wireframe_mask"] = parse_bool_checkbox(fields["fiber_fixer_save_wireframe_mask"])
        settings["fiber_fixer_save_preview_overlay"] = parse_bool_checkbox(fields["fiber_fixer_save_preview_overlay"])

        settings["large_pore_repair_enabled"] = parse_bool_checkbox(fields["large_pore_repair_enabled"])
        settings["large_pore_repair_mode"] = str(fields["large_pore_repair_mode"].getSelectedItem())
        settings["large_pore_repair_min_parent_area_px"] = parse_int_field(fields["large_pore_repair_min_parent_area_px"], "Large pore minimum parent area")
        settings["large_pore_repair_largest_pore_limit"] = parse_int_field(fields["large_pore_repair_largest_pore_limit"], "Large pore count limit")
        settings["large_pore_repair_min_child_area_px"] = parse_int_field(fields["large_pore_repair_min_child_area_px"], "Large pore minimum child area")
        settings["large_pore_repair_min_smaller_child_fraction"] = parse_float_field(fields["large_pore_repair_min_smaller_child_fraction"], "Large pore minimum smaller-child fraction")
        settings["large_pore_repair_max_larger_child_fraction"] = parse_float_field(fields["large_pore_repair_max_larger_child_fraction"], "Large pore maximum larger-child fraction")
        settings["large_pore_repair_min_closing_radius_px"] = parse_int_field(fields["large_pore_repair_min_closing_radius_px"], "Large pore minimum closing radius")
        settings["large_pore_repair_max_closing_radius_px"] = parse_int_field(fields["large_pore_repair_max_closing_radius_px"], "Large pore maximum closing radius")
        settings["large_pore_repair_radius_step_px"] = parse_int_field(fields["large_pore_repair_radius_step_px"], "Large pore closing-radius step")
        settings["large_pore_repair_min_area_px"] = parse_int_field(fields["large_pore_repair_min_area_px"], "Large pore minimum repair area")
        settings["large_pore_repair_max_area_px"] = parse_int_field(fields["large_pore_repair_max_area_px"], "Large pore maximum repair area")
        settings["large_pore_repair_max_fraction_of_parent"] = parse_float_field(fields["large_pore_repair_max_fraction_of_parent"], "Large pore maximum repair fraction")
        settings["large_pore_repair_max_span_px"] = parse_int_field(fields["large_pore_repair_max_span_px"], "Large pore maximum repair span")
        settings["large_pore_repair_crop_margin_px"] = parse_int_field(fields["large_pore_repair_crop_margin_px"], "Large pore crop margin")
        settings["large_pore_repair_max_repairs_per_image"] = parse_int_field(fields["large_pore_repair_max_repairs_per_image"], "Large pore maximum repairs")

        settings["large_pore_repair_largest_rescue_enabled"] = parse_bool_checkbox(fields["large_pore_repair_largest_rescue_enabled"])
        settings["large_pore_repair_largest_rescue_parent_limit"] = parse_int_field(fields["large_pore_repair_largest_rescue_parent_limit"], "Largest-pore rescue parent limit")
        settings["large_pore_repair_largest_rescue_min_radius_px"] = parse_int_field(fields["large_pore_repair_largest_rescue_min_radius_px"], "Largest-pore rescue minimum radius")
        settings["large_pore_repair_largest_rescue_max_radius_px"] = parse_int_field(fields["large_pore_repair_largest_rescue_max_radius_px"], "Largest-pore rescue maximum radius")
        settings["large_pore_repair_largest_rescue_max_area_px"] = parse_int_field(fields["large_pore_repair_largest_rescue_max_area_px"], "Largest-pore rescue maximum area")
        settings["large_pore_repair_largest_rescue_max_fraction_of_parent"] = parse_float_field(fields["large_pore_repair_largest_rescue_max_fraction_of_parent"], "Largest-pore rescue maximum fraction")
        settings["large_pore_repair_largest_rescue_max_span_px"] = parse_int_field(fields["large_pore_repair_largest_rescue_max_span_px"], "Largest-pore rescue maximum span")
        settings["large_pore_repair_largest_rescue_min_smaller_child_fraction"] = parse_float_field(fields["large_pore_repair_largest_rescue_min_smaller_child_fraction"], "Largest-pore rescue minimum smaller-child fraction")
        settings["large_pore_repair_largest_rescue_max_larger_child_fraction"] = parse_float_field(fields["large_pore_repair_largest_rescue_max_larger_child_fraction"], "Largest-pore rescue maximum larger-child fraction")
        settings["large_pore_repair_largest_rescue_max_repairs_per_image"] = parse_int_field(fields["large_pore_repair_largest_rescue_max_repairs_per_image"], "Largest-pore rescue maximum repairs")

        settings["large_pore_repair_force_largest_enabled"] = parse_bool_checkbox(fields["large_pore_repair_force_largest_enabled"])
        settings["large_pore_repair_force_largest_max_radius_px"] = parse_int_field(fields["large_pore_repair_force_largest_max_radius_px"], "Forced-largest maximum radius")
        settings["large_pore_repair_force_largest_max_area_px"] = parse_int_field(fields["large_pore_repair_force_largest_max_area_px"], "Forced-largest maximum area")
        settings["large_pore_repair_force_largest_max_fraction_of_parent"] = parse_float_field(fields["large_pore_repair_force_largest_max_fraction_of_parent"], "Forced-largest maximum fraction")
        settings["large_pore_repair_force_largest_max_span_px"] = parse_int_field(fields["large_pore_repair_force_largest_max_span_px"], "Forced-largest maximum span")
        settings["large_pore_repair_force_largest_min_child_area_px"] = parse_int_field(fields["large_pore_repair_force_largest_min_child_area_px"], "Forced-largest minimum child area")
        settings["large_pore_repair_force_largest_min_smaller_child_fraction"] = parse_float_field(fields["large_pore_repair_force_largest_min_smaller_child_fraction"], "Forced-largest minimum smaller-child fraction")
        settings["large_pore_repair_force_largest_max_larger_child_fraction"] = parse_float_field(fields["large_pore_repair_force_largest_max_larger_child_fraction"], "Forced-largest maximum larger-child fraction")

        settings["large_pore_repair_green_target_enabled"] = parse_bool_checkbox(fields["large_pore_repair_green_target_enabled"])
        settings["large_pore_repair_green_target_min_parent_area_px"] = parse_int_field(fields["large_pore_repair_green_target_min_parent_area_px"], "Green-target minimum parent area")
        settings["large_pore_repair_green_target_max_parent_area_px"] = parse_int_field(fields["large_pore_repair_green_target_max_parent_area_px"], "Green-target maximum parent area")
        settings["large_pore_repair_green_target_parent_limit"] = parse_int_field(fields["large_pore_repair_green_target_parent_limit"], "Green-target parent limit")
        settings["large_pore_repair_green_target_min_radius_px"] = parse_int_field(fields["large_pore_repair_green_target_min_radius_px"], "Green-target minimum radius")
        settings["large_pore_repair_green_target_max_radius_px"] = parse_int_field(fields["large_pore_repair_green_target_max_radius_px"], "Green-target maximum radius")
        settings["large_pore_repair_green_target_min_area_px"] = parse_int_field(fields["large_pore_repair_green_target_min_area_px"], "Green-target minimum repair area")
        settings["large_pore_repair_green_target_max_area_px"] = parse_int_field(fields["large_pore_repair_green_target_max_area_px"], "Green-target maximum repair area")
        settings["large_pore_repair_green_target_min_fraction_of_parent"] = parse_float_field(fields["large_pore_repair_green_target_min_fraction_of_parent"], "Green-target minimum repair fraction")
        settings["large_pore_repair_green_target_max_fraction_of_parent"] = parse_float_field(fields["large_pore_repair_green_target_max_fraction_of_parent"], "Green-target maximum repair fraction")
        settings["large_pore_repair_green_target_min_span_px"] = parse_int_field(fields["large_pore_repair_green_target_min_span_px"], "Green-target minimum repair span")
        settings["large_pore_repair_green_target_max_span_px"] = parse_int_field(fields["large_pore_repair_green_target_max_span_px"], "Green-target maximum repair span")
        settings["large_pore_repair_green_target_min_mean_thickness_px"] = parse_float_field(fields["large_pore_repair_green_target_min_mean_thickness_px"], "Green-target minimum mean thickness")
        settings["large_pore_repair_green_target_max_mean_thickness_px"] = parse_float_field(fields["large_pore_repair_green_target_max_mean_thickness_px"], "Green-target maximum mean thickness")
        settings["large_pore_repair_green_target_min_child_area_px"] = parse_int_field(fields["large_pore_repair_green_target_min_child_area_px"], "Green-target minimum child area")
        settings["large_pore_repair_green_target_min_smaller_child_fraction"] = parse_float_field(fields["large_pore_repair_green_target_min_smaller_child_fraction"], "Green-target minimum smaller-child fraction")
        settings["large_pore_repair_green_target_max_larger_child_fraction"] = parse_float_field(fields["large_pore_repair_green_target_max_larger_child_fraction"], "Green-target maximum larger-child fraction")
        settings["large_pore_repair_green_target_max_repairs_per_image"] = parse_int_field(fields["large_pore_repair_green_target_max_repairs_per_image"], "Green-target maximum repairs")
        settings["large_pore_repair_green_spur_enabled"] = parse_bool_checkbox(fields["large_pore_repair_green_spur_enabled"])
        settings["large_pore_repair_green_spur_review_only"] = parse_bool_checkbox(fields["large_pore_repair_green_spur_review_only"])
        settings["large_pore_repair_green_spur_max_repairs_per_image"] = parse_int_field(fields["large_pore_repair_green_spur_max_repairs_per_image"], "Green-target tiny-spur maximum repairs")

        settings["large_pore_repair_include_edge_pores"] = parse_bool_checkbox(fields["large_pore_repair_include_edge_pores"])
        settings["large_pore_repair_show_red_overlay"] = parse_bool_checkbox(fields["large_pore_repair_show_red_overlay"])
        settings["large_pore_repair_fill_red_overlay"] = parse_bool_checkbox(fields["large_pore_repair_fill_red_overlay"])
        settings["large_pore_repair_save_red_overlay_png"] = parse_bool_checkbox(fields["large_pore_repair_save_red_overlay_png"])
        settings["large_pore_repair_save_mask"] = parse_bool_checkbox(fields["large_pore_repair_save_mask"])
        settings["large_pore_repair_save_csv"] = parse_bool_checkbox(fields["large_pore_repair_save_csv"])

        if settings["fiber_fixer_enabled"]:
            settings["fiber_fixer_absolute_threshold_max"] = max(0, min(255, int(settings["fiber_fixer_absolute_threshold_max"])))
            # v193 intentionally fixes the recovered network to 3 pixels wide.
            settings["fiber_fixer_wire_width_px"] = 3

        if settings["large_pore_repair_enabled"]:
            if not settings.get("black_background", True):
                raise Exception("Large Pore Repair requires Black background for binary conversion: black fibers and white pores.")
            if settings["large_pore_repair_min_parent_area_px"] < 1:
                raise Exception("Large pore minimum parent area must be at least 1 pixel.")
            if settings["large_pore_repair_largest_pore_limit"] < 1:
                raise Exception("Large pore count limit must be at least 1.")
            if settings["large_pore_repair_min_child_area_px"] < 1:
                raise Exception("Large pore minimum child area must be at least 1 pixel.")
            if settings["large_pore_repair_min_smaller_child_fraction"] < 0.0 or settings["large_pore_repair_min_smaller_child_fraction"] >= 0.5:
                raise Exception("Large pore minimum smaller-child fraction must be from 0.0 through less than 0.5.")
            if settings["large_pore_repair_max_larger_child_fraction"] <= 0.5 or settings["large_pore_repair_max_larger_child_fraction"] > 1.0:
                raise Exception("Large pore maximum larger-child fraction must be greater than 0.5 and at most 1.0.")
            if settings["large_pore_repair_min_closing_radius_px"] < 1:
                settings["large_pore_repair_min_closing_radius_px"] = 1
            if settings["large_pore_repair_max_closing_radius_px"] < settings["large_pore_repair_min_closing_radius_px"]:
                settings["large_pore_repair_max_closing_radius_px"] = settings["large_pore_repair_min_closing_radius_px"]
            if settings["large_pore_repair_radius_step_px"] < 1:
                settings["large_pore_repair_radius_step_px"] = 1
            if settings["large_pore_repair_min_area_px"] < 1:
                settings["large_pore_repair_min_area_px"] = 1
            if settings["large_pore_repair_max_area_px"] < settings["large_pore_repair_min_area_px"]:
                settings["large_pore_repair_max_area_px"] = settings["large_pore_repair_min_area_px"]
            if settings["large_pore_repair_max_fraction_of_parent"] <= 0.0:
                raise Exception("Large pore maximum repair fraction must be above 0.")
            if settings["large_pore_repair_max_span_px"] < 1:
                settings["large_pore_repair_max_span_px"] = 1
            if settings["large_pore_repair_crop_margin_px"] < 0:
                settings["large_pore_repair_crop_margin_px"] = 0
            if settings["large_pore_repair_max_repairs_per_image"] < 1:
                settings["large_pore_repair_max_repairs_per_image"] = 1

            if settings["large_pore_repair_largest_rescue_enabled"]:
                if settings["large_pore_repair_largest_rescue_parent_limit"] < 1:
                    settings["large_pore_repair_largest_rescue_parent_limit"] = 1
                if settings["large_pore_repair_largest_rescue_min_radius_px"] < 1:
                    settings["large_pore_repair_largest_rescue_min_radius_px"] = 1
                if settings["large_pore_repair_largest_rescue_max_radius_px"] < settings["large_pore_repair_largest_rescue_min_radius_px"]:
                    settings["large_pore_repair_largest_rescue_max_radius_px"] = settings["large_pore_repair_largest_rescue_min_radius_px"]
                if settings["large_pore_repair_largest_rescue_max_area_px"] < 1:
                    settings["large_pore_repair_largest_rescue_max_area_px"] = 1
                if settings["large_pore_repair_largest_rescue_max_fraction_of_parent"] <= 0.0:
                    raise Exception("Largest-pore rescue maximum repair fraction must be above 0.")
                if settings["large_pore_repair_largest_rescue_max_span_px"] < 1:
                    settings["large_pore_repair_largest_rescue_max_span_px"] = 1
                if settings["large_pore_repair_largest_rescue_min_smaller_child_fraction"] < 0.0 or settings["large_pore_repair_largest_rescue_min_smaller_child_fraction"] >= 0.5:
                    raise Exception("Largest-pore rescue minimum smaller-child fraction must be from 0.0 through less than 0.5.")
                if settings["large_pore_repair_largest_rescue_max_larger_child_fraction"] <= 0.5 or settings["large_pore_repair_largest_rescue_max_larger_child_fraction"] > 1.0:
                    raise Exception("Largest-pore rescue maximum larger-child fraction must be greater than 0.5 and at most 1.0.")
                if settings["large_pore_repair_largest_rescue_max_repairs_per_image"] < 1:
                    settings["large_pore_repair_largest_rescue_max_repairs_per_image"] = 1

            if settings["large_pore_repair_green_target_enabled"]:
                if settings["large_pore_repair_green_target_min_parent_area_px"] < 1:
                    settings["large_pore_repair_green_target_min_parent_area_px"] = 1
                if settings["large_pore_repair_green_target_max_parent_area_px"] < settings["large_pore_repair_green_target_min_parent_area_px"]:
                    settings["large_pore_repair_green_target_max_parent_area_px"] = settings["large_pore_repair_green_target_min_parent_area_px"]
                if settings["large_pore_repair_green_target_parent_limit"] < 1:
                    settings["large_pore_repair_green_target_parent_limit"] = 1
                if settings["large_pore_repair_green_target_min_radius_px"] < 1:
                    settings["large_pore_repair_green_target_min_radius_px"] = 1
                if settings["large_pore_repair_green_target_max_radius_px"] < settings["large_pore_repair_green_target_min_radius_px"]:
                    settings["large_pore_repair_green_target_max_radius_px"] = settings["large_pore_repair_green_target_min_radius_px"]
                if settings["large_pore_repair_green_target_min_area_px"] < 1:
                    settings["large_pore_repair_green_target_min_area_px"] = 1
                if settings["large_pore_repair_green_target_max_area_px"] < settings["large_pore_repair_green_target_min_area_px"]:
                    settings["large_pore_repair_green_target_max_area_px"] = settings["large_pore_repair_green_target_min_area_px"]
                if settings["large_pore_repair_green_target_min_fraction_of_parent"] < 0.0:
                    settings["large_pore_repair_green_target_min_fraction_of_parent"] = 0.0
                if settings["large_pore_repair_green_target_max_fraction_of_parent"] <= settings["large_pore_repair_green_target_min_fraction_of_parent"]:
                    raise Exception("Green-target maximum repair fraction must be above the minimum fraction.")
                if settings["large_pore_repair_green_target_min_span_px"] < 1:
                    settings["large_pore_repair_green_target_min_span_px"] = 1
                if settings["large_pore_repair_green_target_max_span_px"] < settings["large_pore_repair_green_target_min_span_px"]:
                    settings["large_pore_repair_green_target_max_span_px"] = settings["large_pore_repair_green_target_min_span_px"]
                if settings["large_pore_repair_green_target_min_mean_thickness_px"] <= 0.0:
                    settings["large_pore_repair_green_target_min_mean_thickness_px"] = 0.1
                if settings["large_pore_repair_green_target_max_mean_thickness_px"] < settings["large_pore_repair_green_target_min_mean_thickness_px"]:
                    settings["large_pore_repair_green_target_max_mean_thickness_px"] = settings["large_pore_repair_green_target_min_mean_thickness_px"]
                if settings["large_pore_repair_green_target_min_child_area_px"] < 1:
                    settings["large_pore_repair_green_target_min_child_area_px"] = 1
                if settings["large_pore_repair_green_target_min_smaller_child_fraction"] < 0.0 or settings["large_pore_repair_green_target_min_smaller_child_fraction"] >= 0.5:
                    raise Exception("Green-target minimum smaller-child fraction must be from 0.0 through less than 0.5.")
                if settings["large_pore_repair_green_target_max_larger_child_fraction"] <= 0.5 or settings["large_pore_repair_green_target_max_larger_child_fraction"] > 1.0:
                    raise Exception("Green-target maximum larger-child fraction must be greater than 0.5 and at most 1.0.")
                if settings["large_pore_repair_green_target_max_repairs_per_image"] < 1:
                    settings["large_pore_repair_green_target_max_repairs_per_image"] = 1
                if settings["large_pore_repair_green_spur_max_repairs_per_image"] < 1:
                    settings["large_pore_repair_green_spur_max_repairs_per_image"] = 1

            if settings["large_pore_repair_force_largest_enabled"]:
                if settings["large_pore_repair_force_largest_max_radius_px"] < 1:
                    settings["large_pore_repair_force_largest_max_radius_px"] = 1
                if settings["large_pore_repair_force_largest_max_area_px"] < 1:
                    settings["large_pore_repair_force_largest_max_area_px"] = 1
                if settings["large_pore_repair_force_largest_max_fraction_of_parent"] <= 0.0:
                    raise Exception("Forced-largest maximum repair fraction must be above 0.")
                if settings["large_pore_repair_force_largest_max_span_px"] < 1:
                    settings["large_pore_repair_force_largest_max_span_px"] = 1
                if settings["large_pore_repair_force_largest_min_child_area_px"] < 1:
                    settings["large_pore_repair_force_largest_min_child_area_px"] = 1
                if settings["large_pore_repair_force_largest_min_smaller_child_fraction"] < 0.0 or settings["large_pore_repair_force_largest_min_smaller_child_fraction"] >= 0.5:
                    raise Exception("Forced-largest minimum smaller-child fraction must be from 0.0 through less than 0.5.")
                if settings["large_pore_repair_force_largest_max_larger_child_fraction"] <= 0.5 or settings["large_pore_repair_force_largest_max_larger_child_fraction"] > 1.0:
                    raise Exception("Forced-largest maximum larger-child fraction must be greater than 0.5 and at most 1.0.")

        settings["auto_scale_unscaled_enabled"] = parse_bool_checkbox(fields["auto_scale_unscaled_enabled"])
        settings["auto_scale_known_length_mm"] = parse_float_field(fields["auto_scale_known_length_mm"], "Known red reference line length")
        settings["auto_scale_min_component_pixels"] = parse_int_field(fields["auto_scale_min_component_pixels"], "Minimum red-line component pixels")
        settings["auto_scale_show_preview"] = parse_bool_checkbox(fields["auto_scale_show_preview"])
        settings["auto_scale_preview_padding_px"] = parse_int_field(fields["auto_scale_preview_padding_px"], "Scale preview crop padding")
        if settings["auto_scale_known_length_mm"] <= 0:
            settings["auto_scale_known_length_mm"] = DEFAULTS["auto_scale_known_length_mm"]
        if settings["auto_scale_min_component_pixels"] < 1:
            settings["auto_scale_min_component_pixels"] = DEFAULTS["auto_scale_min_component_pixels"]
        if settings["auto_scale_preview_padding_px"] < 0:
            settings["auto_scale_preview_padding_px"] = DEFAULTS["auto_scale_preview_padding_px"]
        settings["auto_scale_red_min"] = DEFAULTS["auto_scale_red_min"]
        settings["auto_scale_red_dominance"] = DEFAULTS["auto_scale_red_dominance"]
        settings["auto_scale_red_margin"] = DEFAULTS["auto_scale_red_margin"]

        settings["particle_size_min"] = parse_text(fields["particle_size_min"])
        settings["particle_size_max"] = parse_text(fields["particle_size_max"])
        settings["particle_circ_min"] = parse_float_field(fields["particle_circ_min"], "Particle circularity min")
        settings["particle_circ_max"] = parse_float_field(fields["particle_circ_max"], "Particle circularity max")
        settings["particle_include_holes"] = parse_bool_checkbox(fields["particle_include_holes"])
        settings["particle_exclude_edges"] = parse_bool_checkbox(fields["particle_exclude_edges"])
        measurement_keys = [
            "measure_area", "measure_mean", "measure_std_dev", "measure_mode", "measure_min_max",
            "measure_centroid", "measure_center_of_mass", "measure_perimeter", "measure_bounding_rect",
            "measure_fit_ellipse", "measure_shape_descriptors", "measure_feret",
            "measure_integrated_density", "measure_median", "measure_skewness", "measure_kurtosis",
            "measure_area_fraction", "measure_stack_position", "measure_limit_to_threshold"
        ]
        for measurement_key in measurement_keys:
            settings[measurement_key] = parse_bool_checkbox(fields[measurement_key])
        # Preserve fields required by EPD, pore maps, and shape summaries.
        for required_measurement in ["measure_area", "measure_centroid", "measure_perimeter", "measure_fit_ellipse", "measure_shape_descriptors"]:
            if not settings.get(required_measurement, False):
                IJ.log("Set Measurements: auto-enabling core-required option " + str(required_measurement))
                settings[required_measurement] = True

        settings["auto_threshold_fit_enabled"] = parse_bool_checkbox(fields["auto_threshold_fit_enabled"])
        settings["auto_threshold_fit_apply_to_main"] = parse_bool_checkbox(fields["auto_threshold_fit_apply_to_main"])
        settings["auto_threshold_fit_roi_count"] = parse_int_field(fields["auto_threshold_fit_roi_count"], "Auto threshold fit ROI count")
        settings["auto_threshold_fit_trigger_percent_diff"] = parse_float_field(fields["auto_threshold_fit_trigger_percent_diff"], "Auto-fit trigger percent difference")
        settings["auto_threshold_fit_sweep_min"] = parse_bool_checkbox(fields["auto_threshold_fit_sweep_min"])
        settings["auto_threshold_fit_min_start"] = parse_float_field(fields["auto_threshold_fit_min_start"], "Auto threshold fit min start")
        settings["auto_threshold_fit_min_end"] = parse_float_field(fields["auto_threshold_fit_min_end"], "Auto threshold fit min end")
        settings["auto_threshold_fit_min_step"] = parse_float_field(fields["auto_threshold_fit_min_step"], "Auto threshold fit min step")
        settings["auto_threshold_fit_sweep_max"] = parse_bool_checkbox(fields["auto_threshold_fit_sweep_max"])
        settings["auto_threshold_fit_max_start"] = parse_float_field(fields["auto_threshold_fit_max_start"], "Auto threshold fit max start")
        settings["auto_threshold_fit_max_end"] = parse_float_field(fields["auto_threshold_fit_max_end"], "Auto threshold fit max end")
        settings["auto_threshold_fit_max_step"] = parse_float_field(fields["auto_threshold_fit_max_step"], "Auto threshold fit max step")
        settings["auto_threshold_fit_roi_padding"] = parse_int_field(fields["auto_threshold_fit_roi_padding"], "Auto threshold fit ROI padding")
        settings["auto_threshold_fit_area_penalty"] = parse_float_field(fields["auto_threshold_fit_area_penalty"], "Auto threshold fit area penalty")
        settings["auto_threshold_fit_max_tests"] = parse_int_field(fields["auto_threshold_fit_max_tests"], "Auto threshold fit max tests")
        settings["auto_threshold_fit_save_csv"] = parse_bool_checkbox(fields["auto_threshold_fit_save_csv"])
        settings["auto_threshold_fit_save_best_mask"] = parse_bool_checkbox(fields["auto_threshold_fit_save_best_mask"])

        # Auto-fit threshold always sweeps in increments of 5 selected units (gray levels or histogram percentage points).
        settings["auto_threshold_fit_min_step"] = 5.0
        settings["auto_threshold_fit_max_step"] = 5.0
        if settings["auto_threshold_fit_roi_count"] < 1:
            settings["auto_threshold_fit_roi_count"] = 1
        if settings["auto_threshold_fit_trigger_percent_diff"] < 0:
            settings["auto_threshold_fit_trigger_percent_diff"] = 0.0
        if settings["auto_threshold_fit_roi_padding"] < 0:
            settings["auto_threshold_fit_roi_padding"] = 0
        if settings["auto_threshold_fit_area_penalty"] < 0:
            settings["auto_threshold_fit_area_penalty"] = 0.0
        if settings["auto_threshold_fit_max_tests"] < 1:
            settings["auto_threshold_fit_max_tests"] = 1

        custom_delete_cutoff = parse_float_field(fields["small_epd_cutoff"], "Custom delete EPD cutoff")
        settings["epd_cutoff_1"] = parse_float_field(fields["epd_cutoff_1"], "EPD cutoff 1")
        settings["epd_cutoff_2"] = parse_float_field(fields["epd_cutoff_2"], "EPD cutoff 2")
        settings["epd_between_preset"] = str(fields["epd_between_preset"].getSelectedItem())
        custom_between_low = parse_float_field(fields["epd_between_low"], "Custom EPD between low")
        custom_between_high = parse_float_field(fields["epd_between_high"], "Custom EPD between high")
        resolved_between_low, resolved_between_high, resolved_between_source = resolve_epd_between_preset(
            settings["epd_between_preset"],
            custom_between_low,
            custom_between_high
        )
        if settings["epd_between_preset"] == "Custom":
            if custom_delete_cutoff < 0.0:
                raise Exception("Custom delete EPD cutoff cannot be negative.")
            settings["small_epd_cutoff"] = custom_delete_cutoff
        else:
            # Preset delete cutoff is the lower edge of its generated between-count band.
            settings["small_epd_cutoff"] = resolved_between_low
        settings["epd_between_low"] = resolved_between_low
        settings["epd_between_high"] = resolved_between_high
        settings["epd_between_manual_high"] = custom_between_high
        settings["epd_between_auto_high_enabled"] = False
        settings["epd_between_auto_offset_um"] = 0.0
        settings["epd_between_high_source"] = resolved_between_source

        # Synchronize legacy v114 keys to the one active band.
        settings["epd_band_1_low"] = settings["epd_between_low"]
        settings["epd_band_1_high"] = settings["epd_between_high"]
        settings["epd_band_2_low"] = settings["epd_between_low"]
        settings["epd_band_2_high"] = settings["epd_between_high"]
        settings["epd_band_3_low"] = settings["epd_between_low"]
        settings["epd_band_3_high"] = settings["epd_between_high"]
        settings["circ_cutoff"] = parse_float_field(fields["circ_cutoff"], "Circularity cutoff")

        settings["sweep_enabled"] = parse_bool_checkbox(fields["sweep_enabled"])
        settings["sweep_all_listed"] = parse_bool_checkbox(fields["sweep_all_listed"])
        settings["max_sweep_runs"] = parse_int_field(fields["max_sweep_runs"], "Maximum sweep runs allowed")
        settings["sweep_until_enabled"] = parse_bool_checkbox(fields["sweep_until_enabled"])
        settings["sweep_until_metric"] = str(fields["sweep_until_metric"].getSelectedItem())
        settings["sweep_until_operator"] = str(fields["sweep_until_operator"].getSelectedItem())
        settings["sweep_until_target_value"] = parse_text(fields["sweep_until_target_value"])
        settings["sweep_until_equal_tolerance"] = parse_float_field(fields["sweep_until_equal_tolerance"], "Sweep Until equal tolerance")
        settings["sweep_until_stop_scope"] = str(fields["sweep_until_stop_scope"].getSelectedItem())
        if settings["sweep_until_equal_tolerance"] < 0:
            raise Exception("Sweep Until equal-to tolerance cannot be negative.")
        if settings["sweep_until_enabled"]:
            parse_sweep_until_target(settings["sweep_until_target_value"], settings["sweep_until_metric"])

        settings["sweep_contrast_enabled"] = parse_bool_checkbox(fields["sweep_contrast_enabled"])
        settings["sweep_contrast_mode_off"] = parse_bool_checkbox(fields["sweep_contrast_mode_off"])
        settings["sweep_contrast_mode_saturated"] = parse_bool_checkbox(fields["sweep_contrast_mode_saturated"])
        settings["sweep_contrast_mode_normalize"] = parse_bool_checkbox(fields["sweep_contrast_mode_normalize"])
        settings["sweep_contrast_mode_equalize"] = parse_bool_checkbox(fields["sweep_contrast_mode_equalize"])
        if settings["sweep_contrast_enabled"] and len(selected_contrast_sweep_modes(settings)) <= 0:
            raise Exception("Enhance Contrast sweep is enabled, but no contrast modes are selected.")

        sweep_names = [
            "threshold_min", "threshold_max", "median_radius",
            "bandpass_large", "bandpass_small", "clahe_blocksize", "clahe_maximum",
            "binary_enabled", "binary_fill_holes", "binary_watershed",
            "binary_despeckle_iterations", "binary_open_iterations", "binary_close_iterations",
            "binary_erode_iterations", "binary_dilate_iterations",
            "binary_minimum_radius", "binary_maximum_radius"
        ]

        for nm in sweep_names:
            settings["sweep_" + nm] = parse_bool_checkbox(fields["sweep_" + nm])
            settings["sweep_" + nm + "_start"] = parse_float_field(fields["sweep_" + nm + "_start"], "Sweep " + nm + " start")
            settings["sweep_" + nm + "_end"] = parse_float_field(fields["sweep_" + nm + "_end"], "Sweep " + nm + " end")
            settings["sweep_" + nm + "_step"] = parse_float_field(fields["sweep_" + nm + "_step"], "Sweep " + nm + " step")

        threshold_range_keys = []
        if settings.get("sweep_enabled", False):
            if settings.get("sweep_all_listed", False) or settings.get("sweep_threshold_min", False):
                threshold_range_keys.extend(["sweep_threshold_min_start", "sweep_threshold_min_end"])
            if settings.get("sweep_all_listed", False) or settings.get("sweep_threshold_max", False):
                threshold_range_keys.extend(["sweep_threshold_max_start", "sweep_threshold_max_end"])
        if settings.get("auto_threshold_fit_enabled", False):
            if settings.get("auto_threshold_fit_sweep_min", False):
                threshold_range_keys.extend(["auto_threshold_fit_min_start", "auto_threshold_fit_min_end"])
            if settings.get("auto_threshold_fit_sweep_max", False):
                threshold_range_keys.extend(["auto_threshold_fit_max_start", "auto_threshold_fit_max_end"])
        for threshold_range_key in threshold_range_keys:
            threshold_range_value = float(settings.get(threshold_range_key, 0.0))
            if threshold_range_value < 0.0 or threshold_range_value > threshold_input_limit:
                raise Exception(
                    threshold_range_key + " must be between 0 and " + str(int(threshold_input_limit)) +
                    " for " + settings["threshold_input_mode"] + "."
                )

        # Force integer fields after parsing as floats
        settings["sweep_clahe_blocksize_start"] = int(settings["sweep_clahe_blocksize_start"])
        settings["sweep_clahe_blocksize_end"] = int(settings["sweep_clahe_blocksize_end"])
        settings["sweep_clahe_blocksize_step"] = int(settings["sweep_clahe_blocksize_step"])
        for binary_sweep_key in [
            "binary_enabled", "binary_fill_holes", "binary_watershed",
            "binary_despeckle_iterations", "binary_open_iterations", "binary_close_iterations",
            "binary_erode_iterations", "binary_dilate_iterations"
        ]:
            settings["sweep_" + binary_sweep_key + "_start"] = int(round(settings["sweep_" + binary_sweep_key + "_start"]))
            settings["sweep_" + binary_sweep_key + "_end"] = int(round(settings["sweep_" + binary_sweep_key + "_end"]))
            settings["sweep_" + binary_sweep_key + "_step"] = int(round(settings["sweep_" + binary_sweep_key + "_step"]))

        # Batch sweep summary export only controls Excel summary mirroring. It must
        # never change the selected Word-report grouping/permutation.
        if settings.get("batch_enabled", False) and settings.get("sweep_enabled", False) and settings.get("batch_sweep_export_all_summaries_to_all_reports", True) and str(settings.get("summary_xls_destination", "")) != "Manual selection at end":
            settings["export_main_summary_xls"] = True
            settings["summary_xls_destination"] = "All available All Reports folders"

        # Reassert the Word-report invariant after all summary-export settings are parsed.
        # This specifically keeps combined/by-image/separate modes working when the
        # final batch-summaries checkbox is unchecked.
        settings["create_word_report"] = str(settings.get("word_report_mode", "Combined Word report")) != "No Word reports"

        if settings.get("image_capture_enabled", False):
            # Capture mode creates already calibrated TIFF inputs. Do not run the regular PNG/red-line scaler again.
            settings["batch_enabled"] = True
            settings["auto_scale_unscaled_enabled"] = False
            settings["auto_scale_save_tif_enabled"] = True
            settings["set_scale_only_mode"] = False

        if settings.get("beast_mode_enabled", False):
            # Unattended high-volume mode: manual/modal workflows remain disabled.
            # v193 decouples JMP graph generation from the six Word-report modes.
            graph_report_enabled = bool(settings.get("beast_create_graph_word_report", False))
            # v209: the Report-card dropdown is authoritative in BEAST too.
            beast_report_mode = normalize_word_report_mode(settings.get("word_report_mode", "Combined Word report"))
            settings["word_report_mode"] = beast_report_mode
            settings["beast_word_report_mode"] = beast_report_mode
            settings["create_word_report"] = beast_report_mode != "No Word reports"
            settings["open_word_report_when_done"] = False
            if settings["create_word_report"] and ("combined" in beast_report_mode.lower() or beast_report_mode == "Combined Word report"):
                settings["report_sweep_comparison_enabled"] = True
            # v209: summary export remains user-selected. BEAST no longer forces it ON.
            settings["beast_disable_histograms_and_graphs"] = not graph_report_enabled
            settings["beast_two_sheet_workbook_enabled"] = True
            settings["report_filename_mode"] = "Auto name: image + processing steps"
            # The BEAST JMP pool creates the outputs; the report builder must not relaunch scripts.
            settings["report_launch_all_jmp"] = False
            settings["report_wait_for_jmp"] = False
            settings["launch_jmp"] = False
            settings["close_jmp_windows_when_finished"] = True
            settings["manual_measurements_enabled"] = False
            settings["manual_largest_pore_enabled"] = False
            settings["manual_largest_pore_count"] = 0
            settings["manual_selected_pore_enabled"] = False
            settings["manual_selected_pore_count"] = 0
            settings["manual_strand_measurement_enabled"] = False
            settings["manual_strand_count"] = 0
            settings["auto_threshold_fit_enabled"] = False
            settings["crop_prompt_each_image"] = False
            settings["popup_warning_summary_enabled"] = False
            settings["max_sweep_runs"] = int(settings.get("beast_max_total_runs", DEFAULTS["beast_max_total_runs"]))

        selected_quick_slot = active_quick_run_slot[0]
        if selected_quick_slot is not None:
            selected_quick_record = quick_run_registry.get(int(selected_quick_slot), {})
            selected_quick_name = str(selected_quick_record.get("name", "Quick Run " + str(selected_quick_slot))).strip()
            current_quick_snapshot = quick_run_gui_snapshot(fields, selected_quick_name)
            quick_run_changed = active_quick_run_baseline[0] is None or current_quick_snapshot != active_quick_run_baseline[0]
            if quick_run_changed:
                target_quick_path = quick_run_target_path(int(selected_quick_slot), selected_quick_name)
                quick_answer = JOptionPane.showConfirmDialog(None,
                    "This Quick Run changed. Save the updated configuration as Quick Run " + str(selected_quick_slot) + " - " + selected_quick_name + "?\n\nThe portable file will be written inside the Quick Runs folder as:\n" + target_quick_path + "\n\nChoose No to run without changing the saved Quick Run.",
                    "Save Changed Portable Quick Run", JOptionPane.YES_NO_OPTION, JOptionPane.QUESTION_MESSAGE)
                if quick_answer == JOptionPane.YES_OPTION:
                    try:
                        quick_run_settings_to_save = quick_run_capture_all_settings(fields, settings)
                        saved_quick_path = save_quick_run_file(int(selected_quick_slot), selected_quick_name, quick_run_settings_to_save)
                        IJ.log("Quick Run v209 saved all current GUI settings; captured GUI fields=" + str(quick_run_settings_to_save.get("quick_run_saved_gui_field_count", "")))
                        JOptionPane.showMessageDialog(None,
                            "Quick Run saved successfully.\n\n" + saved_quick_path + "\n\nCopy this file into the Quick Runs folder on another installation to share the same configuration.",
                            "Quick Run Saved", JOptionPane.INFORMATION_MESSAGE)
                    except Exception as quick_save_error:
                        IJ.log("Could not save portable Quick Run: " + str(quick_save_error))
                        JOptionPane.showMessageDialog(None,
                            "The analysis will continue, but the Quick Run file could not be saved:\n\n" + str(quick_save_error),
                            "Quick Run Save Error", JOptionPane.ERROR_MESSAGE)
            else:
                IJ.log("Quick Run " + str(selected_quick_slot) + " was unchanged; save confirmation skipped.")

        if settings.get("save_settings_as_default", False):
            save_settings_as_defaults(settings)
        if settings.get("save_named_preset", False):
            save_named_preset(settings, settings.get("preset_name", ""))

        return settings

    except Exception as e:
        IJ.log("v209 settings collection error: " + str(e))
        IJ.error("Settings Error", str(e))
        return None



# ======================================================
# AUTO SCALE FROM RED SCALE-LINE HELPERS
# ======================================================

def calibration_unit_is_unscaled(cal):
    try:
        unit = str(cal.getUnit()).replace("µ", "u").replace("μ", "u").strip().lower()
    except:
        unit = ""
    if unit in ["", "pixel", "pixels", "px"]:
        return True
    return False


def detect_red_scale_line_pixels(imp, settings):
    # Finds the largest connected red component and measures the top edge of its rotated four-corner box.
    # This avoids measuring the diagonal of the red scale bar.
    # Returns: pixel_length, component_pixel_count, bbox, endpoints, error_text
    if imp is None:
        return 0.0, 0, None, None, "No image was available."

    try:
        ip = imp.getProcessor()
        w = int(imp.getWidth())
        h = int(imp.getHeight())
    except Exception as e:
        return 0.0, 0, None, None, "Could not read image pixels: " + str(e)

    try:
        red_min = int(float(settings.get("auto_scale_red_min", 120)))
    except:
        red_min = 120
    try:
        red_dom = float(settings.get("auto_scale_red_dominance", 1.4))
    except:
        red_dom = 1.4
    try:
        red_margin = float(settings.get("auto_scale_red_margin", 30))
    except:
        red_margin = 30.0
    try:
        min_component_pixels = int(float(settings.get("auto_scale_min_component_pixels", 25)))
    except:
        min_component_pixels = 25

    red_points = set()
    rgb = zeros(3, 'i')

    try:
        for y in range(h):
            for x in range(w):
                try:
                    ip.getPixel(int(x), int(y), rgb)
                    r = int(rgb[0])
                    g = int(rgb[1])
                    b = int(rgb[2])
                except:
                    try:
                        pix = int(ip.getPixel(int(x), int(y)))
                        r = (pix >> 16) & 255
                        g = (pix >> 8) & 255
                        b = pix & 255
                    except:
                        continue

                if r >= red_min and r > (g * red_dom + red_margin) and r > (b * red_dom + red_margin):
                    red_points.add((int(x), int(y)))
    except Exception as e2:
        return 0.0, 0, None, None, "Could not scan for red scale line pixels: " + str(e2)

    if len(red_points) < min_component_pixels:
        return 0.0, len(red_points), None, None, "Not enough red pixels found. Found " + str(len(red_points)) + ", need at least " + str(min_component_pixels) + "."

    visited = set()
    largest = []

    try:
        for p in red_points:
            if p in visited:
                continue
            stack = [p]
            visited.add(p)
            comp = []
            while len(stack) > 0:
                x, y = stack.pop()
                comp.append((x, y))
                for yy in [y - 1, y, y + 1]:
                    for xx in [x - 1, x, x + 1]:
                        if xx == x and yy == y:
                            continue
                        np = (xx, yy)
                        if np in red_points and np not in visited:
                            visited.add(np)
                            stack.append(np)
            if len(comp) > len(largest):
                largest = comp
    except Exception as e3:
        return 0.0, len(red_points), None, None, "Could not group red pixels into a scale line: " + str(e3)

    if len(largest) < min_component_pixels:
        return 0.0, len(largest), None, None, "Largest red component was too small. Found " + str(len(largest)) + " pixels."

    xs = [int(x) for x, y in largest]
    ys = [int(y) for x, y in largest]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    bbox = (min_x, min_y, max_x, max_y)

    # Principal-axis rotated rectangle:
    #   - long axis follows the red bar
    #   - perpendicular axis follows bar thickness
    #   - the four projected extremes create four pinned corners
    #   - scale length is the top long edge, not the diagonal
    try:
        n = float(len(largest))
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n

        sxx = 0.0
        syy = 0.0
        sxy = 0.0
        for x, y in largest:
            dx = float(x) - mean_x
            dy = float(y) - mean_y
            sxx += dx * dx
            syy += dy * dy
            sxy += dx * dy

        theta = 0.5 * math.atan2(2.0 * sxy, (sxx - syy))
        axis_x = math.cos(theta)
        axis_y = math.sin(theta)
        perp_x = -axis_y
        perp_y = axis_x

        u_vals = []
        v_vals = []
        for x, y in largest:
            dx = float(x) - mean_x
            dy = float(y) - mean_y
            u_vals.append(dx * axis_x + dy * axis_y)
            v_vals.append(dx * perp_x + dy * perp_y)

        min_u = min(u_vals)
        max_u = max(u_vals)
        min_v = min(v_vals)
        max_v = max(v_vals)

        def corner(u, v):
            return (
                int(round(mean_x + float(u) * axis_x + float(v) * perp_x)),
                int(round(mean_y + float(u) * axis_y + float(v) * perp_y))
            )

        c_min_min = corner(min_u, min_v)
        c_max_min = corner(max_u, min_v)
        c_min_max = corner(min_u, max_v)
        c_max_max = corner(max_u, max_v)

        edge_a = (c_min_min, c_max_min)
        edge_b = (c_min_max, c_max_max)

        avg_y_a = (float(edge_a[0][1]) + float(edge_a[1][1])) / 2.0
        avg_y_b = (float(edge_b[0][1]) + float(edge_b[1][1])) / 2.0

        if avg_y_a <= avg_y_b:
            p1, p2 = edge_a
            other1, other2 = edge_b
        else:
            p1, p2 = edge_b
            other1, other2 = edge_a

        # Draw/read left-to-right for user clarity.
        if p1[0] > p2[0]:
            p1, p2 = p2, p1

        dx_len = float(p2[0]) - float(p1[0])
        dy_len = float(p2[1]) - float(p1[1])
        best_len = math.sqrt(dx_len * dx_len + dy_len * dy_len)

        corners = [c_min_min, c_max_min, c_max_max, c_min_max]
        settings["_auto_scale_red_corners"] = str(corners)
        settings["_auto_scale_red_corner_points"] = corners
        settings["_auto_scale_measurement_method"] = "four-corner top edge"

        if best_len <= 0:
            return 0.0, len(largest), bbox, (p1, p2), "Four-corner top-edge length was zero."

        return best_len, len(largest), bbox, (p1, p2), ""

    except Exception as e4:
        # Fallback: use horizontal width of bbox rather than bbox diagonal.
        p1 = (min_x, min_y)
        p2 = (max_x, min_y)
        best_len = abs(float(max_x) - float(min_x))
        settings["_auto_scale_red_corners"] = str([(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)])
        settings["_auto_scale_red_corner_points"] = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
        settings["_auto_scale_measurement_method"] = "fallback bbox top edge"
        if best_len <= 0:
            return 0.0, len(largest), bbox, (p1, p2), "Fallback top-edge length was zero: " + str(e4)
        return best_len, len(largest), bbox, (p1, p2), "Used fallback bbox top edge because four-corner fit failed: " + str(e4)



def show_auto_scale_preview_crop(imp, bbox, endpoints, blue_bbox, settings, image_name):
    # Opens a cropped preview around the detected red scale line.
    # The detected trace is overlaid in green, with endpoint dots and a bounding box.
    if imp is None or bbox is None:
        return None

    if not settings.get("auto_scale_show_preview", True):
        return None

    preview = None
    try:
        try:
            pad = int(float(settings.get("auto_scale_preview_padding_px", 80)))
        except:
            pad = 80
        if pad < 0:
            pad = 0

        x1, y1, x2, y2 = bbox
        if blue_bbox is not None:
            try:
                bx1, by1, bx2, by2 = blue_bbox
                x1 = min(int(x1), int(bx1))
                y1 = min(int(y1), int(by1))
                x2 = max(int(x2), int(bx2))
                y2 = max(int(y2), int(by2))
            except:
                pass
        w_img = int(imp.getWidth())
        h_img = int(imp.getHeight())

        crop_x = int(x1) - pad
        crop_y = int(y1) - pad
        crop_w = int(x2) - int(x1) + 1 + pad * 2
        crop_h = int(y2) - int(y1) + 1 + pad * 2

        rect = clamp_crop_rect(crop_x, crop_y, crop_w, crop_h, w_img, h_img)
        if rect is None:
            return None

        crop_x, crop_y, crop_w, crop_h = rect

        ip = imp.getProcessor()
        ip.setRoi(int(crop_x), int(crop_y), int(crop_w), int(crop_h))
        crop_ip = ip.crop()

        try:
            zoom_factor = float(settings.get("auto_scale_preview_zoom_factor", 3.0))
        except:
            zoom_factor = 3.0
        if zoom_factor < 1.0:
            zoom_factor = 1.0
        if zoom_factor > 10.0:
            zoom_factor = 10.0

        try:
            zoom_w = int(round(float(crop_w) * zoom_factor))
            zoom_h = int(round(float(crop_h) * zoom_factor))
            if zoom_factor > 1.001 and zoom_w > 1 and zoom_h > 1:
                crop_ip = crop_ip.resize(zoom_w, zoom_h)
        except Exception as e_zoom:
            IJ.log("Could not zoom auto-scale preview crop: " + str(e_zoom))
            zoom_factor = 1.0

        def zcoord(v):
            return int(round(float(v) * float(zoom_factor)))

        preview = ImagePlus("AUTO_SCALE_PREVIEW_" + safe_name(str(image_name)) + "_zoom_" + str(zoom_factor) + "x", crop_ip)

        try:
            if preview.getBitDepth() != 24:
                IJ.run(preview, "RGB Color", "")
        except:
            pass

        pip = preview.getProcessor()

        if blue_bbox is not None:
            try:
                lx1, ly1, lx2, ly2 = blue_bbox
                pip.setColor(Color.orange)
                pip.drawRect(
                    zcoord(int(lx1) - int(crop_x)),
                    zcoord(int(ly1) - int(crop_y)),
                    zcoord(int(lx2) - int(lx1) + 1),
                    zcoord(int(ly2) - int(ly1) + 1)
                )
            except:
                pass

        # Draw four pinned red-line corners, then trace only the top edge used for scale.
        try:
            corner_points = settings.get("_auto_scale_red_corner_points", None)
            if corner_points is not None:
                corner_r = max(4, int(round(4.0 * zoom_factor)))
                pip.setColor(Color.magenta)
                for cp in corner_points:
                    cx = zcoord(int(cp[0]) - int(crop_x))
                    cy = zcoord(int(cp[1]) - int(crop_y))
                    pip.fillOval(cx - corner_r, cy - corner_r, corner_r * 2, corner_r * 2)
        except Exception as e_corner:
            IJ.log("Could not draw auto-scale red corner pins: " + str(e_corner))

        if endpoints is not None:
            try:
                p1, p2 = endpoints
                ax = zcoord(int(p1[0]) - int(crop_x))
                ay = zcoord(int(p1[1]) - int(crop_y))
                bx = zcoord(int(p2[0]) - int(crop_x))
                by = zcoord(int(p2[1]) - int(crop_y))
                try:
                    pip.setLineWidth(max(4, int(round(4.0 * zoom_factor))))
                except:
                    pass
                pip.setColor(Color.green)
                pip.drawLine(ax, ay, bx, by)

                dot_r = max(5, int(round(5.0 * zoom_factor)))
                pip.setColor(Color.cyan)
                pip.fillOval(ax - dot_r, ay - dot_r, dot_r * 2, dot_r * 2)
                pip.fillOval(bx - dot_r, by - dot_r, dot_r * 2, dot_r * 2)

                # No text is drawn on the preview image because it can cover the scale label.
            except Exception as e_end:
                IJ.log("Could not draw auto-scale top-edge trace: " + str(e_end))

        preview.updateAndDraw()
        preview.show()
        try:
            preview.getWindow().toFront()
        except:
            pass
        return preview
    except Exception as e:
        IJ.log("Could not show auto-scale preview crop: " + str(e))
        try:
            if preview is not None:
                preview.changes = False
                preview.close()
        except:
            pass
        return None



def blue_pixel_match(ip, x, y, settings, rgb_buf):
    try:
        blue_min = int(float(settings.get("auto_scale_blue_min", 80)))
    except:
        blue_min = 80
    try:
        blue_dom = float(settings.get("auto_scale_blue_dominance", 1.25))
    except:
        blue_dom = 1.25
    try:
        blue_margin = float(settings.get("auto_scale_blue_margin", 20))
    except:
        blue_margin = 20.0

    try:
        ip.getPixel(int(x), int(y), rgb_buf)
        r = int(rgb_buf[0])
        g = int(rgb_buf[1])
        b = int(rgb_buf[2])
    except:
        try:
            pix = int(ip.getPixel(int(x), int(y)))
            r = (pix >> 16) & 255
            g = (pix >> 8) & 255
            b = pix & 255
        except:
            return False

    # Match older blue dimension labels.
    if b >= blue_min and b > (r * blue_dom + blue_margin) and b > (g * blue_dom + blue_margin):
        return True

    # Also match the newer orange dimension labels.
    try:
        orange_min = int(float(settings.get("auto_scale_orange_min", 90)))
    except:
        orange_min = 90
    try:
        orange_green_min = int(float(settings.get("auto_scale_orange_green_min", 35)))
    except:
        orange_green_min = 35
    try:
        orange_blue_max = int(float(settings.get("auto_scale_orange_blue_max", 170)))
    except:
        orange_blue_max = 170

    # Orange is red-dominant with some green and relatively low blue.
    if r >= orange_min and g >= orange_green_min and b <= orange_blue_max and r > b + 25 and r >= g:
        return True

    return False


def scale_distance_candidate_in_expected_range(value):
    # Expected on-screen scale dimensions are 0.100 to 2.000 mm.
    try:
        v = float(value)
    except:
        return None
    if v >= 0.100 and v <= 2.000:
        return v
    return None


def infer_scale_distance_mm_from_digits(raw_text, reference_mm=None):
    # The dimension label is always between 0.100 and 2.000 mm.
    # If OCR loses the decimal point, try decimal placements/divisions that land in that range.
    if raw_text is None:
        return None, "no text"

    s = str(raw_text).strip()
    if s == "":
        return None, "no text"

    s_norm = s.replace("µ", "u").replace("μ", "u")
    m = re.search(r"([0-9]+(?:\.[0-9]+)?|\.[0-9]+)\s*(mm|millimeter|millimeters|um|micron|microns|u m)?", s_norm, re.I)
    if m is None:
        return None, "no number parsed"

    num_txt = str(m.group(1))
    unit = m.group(2)
    if unit is None:
        unit = "mm"
    unit_l = str(unit).lower().replace(" ", "")

    candidates = []
    try:
        val = float(num_txt)
        if unit_l in ["um", "micron", "microns"]:
            val = val / 1000.0
            candidates.append((val, "parsed as microns and converted to mm"))
        else:
            candidates.append((val, "parsed as mm"))
    except:
        pass

    digits = re.sub(r"[^0-9]", "", num_txt)
    if digits != "":
        try:
            dval = float(digits)
            # Most microscope labels in this workflow are 100-2000 microns,
            # so OCR strings like 500, 0500, 1000, 2000 become 0.500, 0.500, 1.000, 2.000 mm.
            candidates.append((dval / 1000.0, "decimal inferred from expected range: digits/1000"))
            candidates.append((dval / 100.0, "decimal inferred from expected range: digits/100"))
            candidates.append((dval / 10.0, "decimal inferred from expected range: digits/10"))

            # Also try inserting a decimal point at every location.
            for pos in range(1, len(digits)):
                try:
                    cand = float(digits[:pos] + "." + digits[pos:])
                    candidates.append((cand, "decimal point inferred from expected range"))
                except:
                    pass
            try:
                cand0 = float("0." + digits)
                candidates.append((cand0, "leading zero decimal inferred from expected range"))
            except:
                pass
        except:
            pass

    valid = []
    for val, note in candidates:
        try:
            fv = float(val)
            if fv >= 0.100 and fv <= 2.000:
                valid.append((fv, note))
        except:
            pass

    if len(valid) <= 0:
        return None, "number found, but no interpretation was between 0.100 and 2.000 mm"

    if reference_mm is not None:
        try:
            ref = float(reference_mm)
            valid = sorted(valid, key=lambda item: abs(float(item[0]) - ref))
        except:
            pass
    else:
        # Prefer digits/1000 for labels such as 0.500, 1.000, 2.000 if decimal is missing.
        valid = sorted(valid, key=lambda item: (0 if "digits/1000" in item[1] else 1, abs(float(item[0]) - 0.5)))

    return float(valid[0][0]), str(valid[0][1])


def parse_distance_mm_from_blue_text(txt):
    # Best-effort parser with expected range logic.
    # Accepts values like 0.5 mm, .5mm, 500 um, 500 µm, 500 micron.
    # If OCR loses the decimal, strings like 500, 1000, 2000 are interpreted as 0.500, 1.000, 2.000 mm.
    try:
        return infer_scale_distance_mm_from_digits(txt, None)
    except Exception as e:
        return None, "parse failed: " + str(e)



def score_digit_template(bits, templ):
    same = 0
    total = 0
    try:
        for i in range(len(bits)):
            if bits[i] == templ[i]:
                same += 1
            total += 1
        if total <= 0:
            return 0.0
        return float(same) / float(total)
    except:
        return 0.0


def classify_blue_digit_bits(bits):
    # 5x7 crude templates. This is a backup OCR attempt only, not a true OCR engine.
    templates = {
        "0": "11111100011000110001100011000111111",
        "1": "00100011000010000100001000010001110",
        "2": "11111000010000111111100001000011111",
        "3": "11111000010000101111000010000111111",
        "4": "10001100011000111111000010000100001",
        "5": "11111100001000011111000010000111111",
        "6": "11111100001000011111100011000111111",
        "7": "11111000010001000100010000100001000",
        "8": "11111100011000111111100011000111111",
        "9": "11111100011000111111000010000111111"
    }
    best_char = ""
    best_score = 0.0
    for ch in templates.keys():
        sc = score_digit_template(bits, templates[ch])
        if sc > best_score:
            best_score = sc
            best_char = ch
    if best_score < 0.58:
        return "", best_score
    return best_char, best_score


def ocr_blue_label_text_from_bbox(imp, bbox, settings):
    # Very small built-in OCR attempt for blue numeric labels.
    # It segments blue characters and tries to read digits/decimal. If confidence is low,
    # it returns blank and the user-correctable field still appears in the popup.
    if imp is None or bbox is None:
        return "", 0.0, "no orange/blue label bbox"

    if not settings.get("auto_scale_blue_ocr_enabled", False):
        return "", 0.0, "orange/blue label reader disabled"

    try:
        ip = imp.getProcessor()
        x1, y1, x2, y2 = bbox
        x1 = int(max(0, x1))
        y1 = int(max(0, y1))
        x2 = int(min(int(imp.getWidth()) - 1, x2))
        y2 = int(min(int(imp.getHeight()) - 1, y2))
        if x2 <= x1 or y2 <= y1:
            return "", 0.0, "invalid blue bbox"
    except Exception as e:
        return "", 0.0, "could not access bbox: " + str(e)

    rgb = zeros(3, 'i')
    pts = set()
    try:
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                if blue_pixel_match(ip, x, y, settings, rgb):
                    pts.add((x - x1, y - y1))
    except Exception as e2:
        return "", 0.0, "orange/blue reader scan failed: " + str(e2)

    if len(pts) < 5:
        return "", 0.0, "not enough orange/blue pixels for OCR"

    bw = x2 - x1 + 1
    bh = y2 - y1 + 1

    # Column projection to split characters.
    col_counts = []
    for x in range(bw):
        c = 0
        for y in range(bh):
            if (x, y) in pts:
                c += 1
        col_counts.append(c)

    segments = []
    in_seg = False
    sx = 0
    gap = 0
    last_nonzero = 0
    for x in range(bw):
        if col_counts[x] > 0:
            if not in_seg:
                in_seg = True
                sx = x
            gap = 0
            last_nonzero = x
        else:
            if in_seg:
                gap += 1
                if gap >= 2:
                    ex = last_nonzero
                    if ex >= sx:
                        segments.append((sx, ex))
                    in_seg = False
                    gap = 0
    if in_seg:
        segments.append((sx, last_nonzero))

    chars = []
    scores = []
    for sx, ex in segments:
        char_pts = [(x, y) for (x, y) in pts if x >= sx and x <= ex]
        if len(char_pts) <= 0:
            continue
        xs = [p[0] for p in char_pts]
        ys = [p[1] for p in char_pts]
        cx1 = min(xs)
        cx2 = max(xs)
        cy1 = min(ys)
        cy2 = max(ys)
        cw = cx2 - cx1 + 1
        ch = cy2 - cy1 + 1

        # Decimal dot: small, low component.
        if cw <= max(3, int(0.25 * float(bh))) and ch <= max(3, int(0.30 * float(bh))) and cy1 > int(0.45 * float(bh)):
            chars.append(".")
            scores.append(0.9)
            continue

        # Ignore likely letters/units if much wider than expected.
        if ch < 4 or cw < 2:
            continue

        grid = ""
        for gy in range(7):
            yy0 = cy1 + int(round(float(gy) * float(ch) / 7.0))
            yy1 = cy1 + int(round(float(gy + 1) * float(ch) / 7.0)) - 1
            if yy1 < yy0:
                yy1 = yy0
            for gx in range(5):
                xx0 = cx1 + int(round(float(gx) * float(cw) / 5.0))
                xx1 = cx1 + int(round(float(gx + 1) * float(cw) / 5.0)) - 1
                if xx1 < xx0:
                    xx1 = xx0
                hit = False
                for yy in range(yy0, yy1 + 1):
                    for xx in range(xx0, xx1 + 1):
                        if (xx, yy) in pts:
                            hit = True
                            break
                    if hit:
                        break
                grid += "1" if hit else "0"

        ch_read, sc = classify_blue_digit_bits(grid)
        if ch_read != "":
            chars.append(ch_read)
            scores.append(sc)

    raw = "".join(chars)

    # Clean common OCR weirdness.
    if raw.count(".") > 1:
        first = raw.find(".")
        raw = raw[:first + 1] + raw[first + 1:].replace(".", "")

    if raw == "":
        return "", 0.0, "reader found orange/blue pixels but could not classify digits"

    # If no decimal and value is large, it may be a micron label. The parser handles units only if present,
    # so the popup still lets the user correct the actual mm distance.
    conf = 0.0
    try:
        conf = sum(scores) / float(len(scores))
    except:
        conf = 0.0

    return raw, conf, "best-effort built-in orange/blue reader"


def detect_blue_label_region(imp, settings, red_bbox=None):
    # Optional orange/blue label reader. Returns a compact bbox, pixel count,
    # OCR text attempt, parsed distance in mm, and a note. No external OCR engine is required.
    # Default is OFF so the user only sees the cropped scale region and types the distance manually.
    if imp is None:
        return None, 0, "", None, "no image"

    if not settings.get("auto_scale_blue_ocr_enabled", False):
        return None, 0, "", None, "orange/blue label reader disabled"

    try:
        ip = imp.getProcessor()
        w = int(imp.getWidth())
        h = int(imp.getHeight())
    except:
        return None, 0, "", None, "could not read image"

    try:
        pad = int(float(settings.get("auto_scale_blue_search_padding_px", 260)))
    except:
        pad = 260
    if pad < 20:
        pad = 20

    if red_bbox is not None:
        try:
            rx1, ry1, rx2, ry2 = red_bbox
            sx0 = max(0, int(rx1) - pad)
            sy0 = max(0, int(ry1) - pad)
            sx1 = min(w - 1, int(rx2) + pad)
            sy1 = min(h - 1, int(ry2) + pad)
        except:
            sx0, sy0, sx1, sy1 = 0, 0, w - 1, h - 1
    else:
        sx0, sy0, sx1, sy1 = 0, 0, w - 1, h - 1

    rgb = zeros(3, 'i')
    pts = set()
    try:
        for y in range(sy0, sy1 + 1):
            for x in range(sx0, sx1 + 1):
                if blue_pixel_match(ip, x, y, settings, rgb):
                    pts.add((int(x), int(y)))
    except:
        return None, 0, "", None, "orange/blue scan failed"

    if len(pts) <= 0:
        return None, 0, "", None, "no orange/blue label pixels found near the red line"

    # Connected components so random blue noise doesn't make one giant bbox.
    visited = set()
    comps = []
    try:
        for p in pts:
            if p in visited:
                continue
            stack = [p]
            visited.add(p)
            comp = []
            while len(stack) > 0:
                x, y = stack.pop()
                comp.append((x, y))
                for yy in [y - 1, y, y + 1]:
                    for xx in [x - 1, x, x + 1]:
                        if xx == x and yy == y:
                            continue
                        np = (xx, yy)
                        if np in pts and np not in visited:
                            visited.add(np)
                            stack.append(np)
            if len(comp) >= 2:
                xs = [q[0] for q in comp]
                ys = [q[1] for q in comp]
                comps.append({"n": len(comp), "bbox": (min(xs), min(ys), max(xs), max(ys)), "pts": comp})
    except:
        comps = []

    if len(comps) <= 0:
        xs_all = [p[0] for p in pts]
        ys_all = [p[1] for p in pts]
        bbox_all = (min(xs_all), min(ys_all), max(xs_all), max(ys_all))
        ocr_txt, conf, note = ocr_blue_label_text_from_bbox(imp, bbox_all, settings)
        dist, parse_note = parse_distance_mm_from_blue_text(ocr_txt)
        return bbox_all, len(pts), ocr_txt, dist, note + "; " + parse_note

    # Keep components that are reasonably close to the red line and not huge.
    kept = []
    if red_bbox is not None:
        rx1, ry1, rx2, ry2 = red_bbox
        rcx = (float(rx1) + float(rx2)) / 2.0
        rcy = (float(ry1) + float(ry2)) / 2.0
    else:
        rcx = float(w) / 2.0
        rcy = float(h) / 2.0

    for c in comps:
        bx1, by1, bx2, by2 = c["bbox"]
        bw = bx2 - bx1 + 1
        bh = by2 - by1 + 1
        cx = (float(bx1) + float(bx2)) / 2.0
        cy = (float(by1) + float(by2)) / 2.0
        d = math.sqrt((cx - rcx) * (cx - rcx) + (cy - rcy) * (cy - rcy))

        # Blue numeric labels are usually small clusters near the scale line.
        if c["n"] >= 2 and bw <= 220 and bh <= 90 and d <= float(pad) * 1.7:
            kept.append(c)

    if len(kept) <= 0:
        kept = sorted(comps, key=lambda cc: cc["n"], reverse=True)[:8]

    # Combine nearby kept components into the orange/blue label bbox.
    all_pts = []
    for c in kept:
        all_pts.extend(c["pts"])

    if len(all_pts) <= 0:
        return None, 0, "", None, "blue components were found but no label bbox could be built"

    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    pixel_count = len(all_pts)

    ocr_txt, conf, ocr_note = ocr_blue_label_text_from_bbox(imp, bbox, settings)
    dist, parse_note = parse_distance_mm_from_blue_text(ocr_txt)

    note = ocr_note + "; " + parse_note + "; confidence=" + str(conf)
    return bbox, pixel_count, ocr_txt, dist, note




# ======================================================
# SWIFT IMAGING 3.0 .MAGN SCALE BRIDGE
# ======================================================

_SWIFT_MAGN_TABLE_CACHE = {}
_SWIFT_MAGN_MESSAGE_CACHE = set()


def _swift_magn_clear_runtime_metadata(settings):
    for key in [
        "_swift_magn_applied",
        "_swift_magn_table_path",
        "_swift_magn_profile_name",
        "_swift_magn_resolution_pixels_per_meter",
        "_swift_magn_mm_per_pixel",
        "_swift_magn_um_per_pixel",
        "_swift_magn_available_profiles",
        "_effective_scale_source",
        "_effective_report_scale_method"
    ]:
        try:
            if key in settings:
                del settings[key]
        except:
            pass


def _swift_magn_log_once(key, message):
    try:
        cache_key = str(key)
        if cache_key in _SWIFT_MAGN_MESSAGE_CACHE:
            return
        _SWIFT_MAGN_MESSAGE_CACHE.add(cache_key)
    except:
        pass
    try:
        IJ.log(str(message))
    except:
        pass


def parse_swift_magnification_table(table_path):
    """
    Read Swift Imaging 3.0 .magn profiles.

    The tested x64 3.0.29807.20251021 export stores each profile name in a
    64-byte UTF-16LE field followed immediately by an IEEE-754 little-endian
    double. Swift labels that double Resolution; its values are pixels per meter (px/m).
    The parser scans for that record signature instead of relying on a fixed
    record count, so it also handles the table's large unused zero-filled area.
    """
    path = os.path.abspath(str(table_path))
    try:
        mtime = os.path.getmtime(path)
        size = os.path.getsize(path)
    except:
        return []

    cache_key = path + "|" + str(mtime) + "|" + str(size)
    cached = _SWIFT_MAGN_TABLE_CACHE.get(cache_key)
    if cached is not None:
        return [dict(item) for item in cached]

    try:
        f = open(path, "rb")
        data = f.read()
        f.close()
    except Exception as e:
        _swift_magn_log_once("read|" + path, "Could not read Swift magnification table " + path + ": " + str(e))
        return []

    profiles = []
    seen = set()
    limit = len(data) - 72
    if limit < 0:
        return []

    # Name fields begin on a UTF-16 code-unit boundary. A valid field contains
    # printable text followed only by NUL code units, then a plausible double.
    for offset in range(0, limit + 1, 2):
        raw_name = data[offset:offset + 64]
        if len(raw_name) != 64:
            continue
        try:
            full_name = raw_name.decode("utf-16le")
        except:
            continue

        zero_at = full_name.find(u"\x00")
        if zero_at < 0:
            candidate_name = full_name.strip()
            remainder = u""
        else:
            candidate_name = full_name[:zero_at].strip()
            remainder = full_name[zero_at + 1:]

        if candidate_name == "" or len(candidate_name) > 31:
            continue

        printable = True
        for ch in candidate_name:
            try:
                code = ord(ch)
            except:
                printable = False
                break
            if code < 32 or code == 127:
                printable = False
                break
        if not printable:
            continue

        if remainder != "":
            nonzero_tail = False
            for ch2 in remainder:
                if ch2 != u"\x00":
                    nonzero_tail = True
                    break
            if nonzero_tail:
                continue

        try:
            resolution_ppm = float(struct.unpack("<d", data[offset + 64:offset + 72])[0])
        except:
            continue

        try:
            bad_number = math.isnan(resolution_ppm) or math.isinf(resolution_ppm)
        except:
            bad_number = False
        if bad_number or resolution_ppm < 1000.0 or resolution_ppm > 10000000000.0:
            continue

        normalized = re.sub(r"[^a-z0-9]+", "", str(candidate_name).lower())
        if normalized == "":
            continue
        dedupe_key = normalized + "|" + ("%.9f" % resolution_ppm)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        profiles.append({
            "name": str(candidate_name),
            "resolution_pixels_per_meter": resolution_ppm,
            "offset": int(offset),
            "table_path": path
        })

    profiles.sort(key=lambda item: int(item.get("offset", 0)))
    _SWIFT_MAGN_TABLE_CACHE.clear()
    _SWIFT_MAGN_TABLE_CACHE[cache_key] = [dict(item) for item in profiles]
    return profiles


def _swift_magn_case_insensitive_file(folder, filename):
    try:
        direct = os.path.join(folder, filename)
        if os.path.isfile(direct):
            return os.path.abspath(direct)
    except:
        pass
    try:
        target = str(filename).lower()
        for entry in os.listdir(folder):
            if str(entry).lower() == target:
                candidate = os.path.join(folder, entry)
                if os.path.isfile(candidate):
                    return os.path.abspath(candidate)
    except:
        pass
    return ""


def _swift_magn_candidate_paths(image_path, settings):
    filename = str(settings.get("swift_magn_filename", "Imaging.magn")).strip()
    if filename == "":
        filename = "Imaging.magn"

    candidates = []

    def add_candidate(path):
        try:
            p = os.path.abspath(str(path))
        except:
            return
        if p not in candidates:
            candidates.append(p)

    if os.path.isabs(filename):
        add_candidate(filename)
    else:
        try:
            source_dir = os.path.dirname(os.path.abspath(str(image_path)))
        except:
            source_dir = ""
        try:
            parent_levels = int(settings.get("swift_magn_search_parent_levels", 4))
        except:
            parent_levels = 4
        if parent_levels < 0:
            parent_levels = 0
        if parent_levels > 12:
            parent_levels = 12

        folder = source_dir
        for level in range(parent_levels + 1):
            if folder == "":
                break
            found = _swift_magn_case_insensitive_file(folder, filename)
            if found != "":
                add_candidate(found)
            # If the requested default is absent, accept the only .magn file in
            # this folder. This handles renamed Swift exports.
            try:
                magn_files = []
                for entry in os.listdir(folder):
                    candidate = os.path.join(folder, entry)
                    if os.path.isfile(candidate) and str(entry).lower().endswith(".magn"):
                        magn_files.append(candidate)
                if len(magn_files) == 1:
                    add_candidate(magn_files[0])
            except:
                pass
            next_folder = os.path.dirname(folder)
            if next_folder == folder:
                break
            folder = next_folder

        if bool(settings.get("swift_magn_use_bundle_fallback", True)):
            try:
                app_dir = quick_run_app_dir()
                add_candidate(os.path.join(app_dir, "Swift Magnification Tables", filename))
                add_candidate(os.path.join(app_dir, filename))
            except:
                pass

    return candidates


def find_swift_magnification_table(image_path, settings):
    candidates = _swift_magn_candidate_paths(image_path, settings)
    for path in candidates:
        if not os.path.isfile(path):
            continue
        profiles = parse_swift_magnification_table(path)
        if len(profiles) > 0:
            return path, profiles
        _swift_magn_log_once("empty|" + path, "Swift .magn file was found but no valid profiles were decoded: " + str(path))
    return "", []


def _swift_magn_normalized_profile_name(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def select_swift_magnification_profile(profiles, requested_name, image_path):
    if profiles is None or len(profiles) <= 0:
        return None, "No Swift magnification profiles were available."

    requested = str(requested_name).strip()
    requested_norm = _swift_magn_normalized_profile_name(requested)

    if requested_norm not in ["", "auto", "automatic"]:
        for profile in profiles:
            if _swift_magn_normalized_profile_name(profile.get("name", "")) == requested_norm:
                return profile, ""
        available = ", ".join(str(item.get("name", "")) for item in profiles)
        return None, "Requested Swift profile '" + requested + "' was not found. Available profiles: " + available

    if len(profiles) == 1:
        return profiles[0], ""

    # Multiple-profile AUTO: only select when the profile appears as a
    # recognizable token in the image/folder path. This avoids accidental
    # matches such as profile 4X inside an unrelated longer number/string.
    raw_context = str(image_path).lower()
    matches = []
    for profile2 in profiles:
        raw_profile = str(profile2.get("name", "")).strip().lower()
        if raw_profile == "":
            continue
        try:
            token_pattern = r"(^|[^a-z0-9])" + re.escape(raw_profile) + r"([^a-z0-9]|$)"
            if re.search(token_pattern, raw_context) is not None:
                matches.append(profile2)
                continue
        except:
            pass

    if len(matches) == 1:
        return matches[0], ""
    if len(matches) > 1:
        matches.sort(key=lambda item: len(_swift_magn_normalized_profile_name(item.get("name", ""))), reverse=True)
        return matches[0], ""

    available2 = ", ".join(str(item2.get("name", "")) for item2 in profiles)
    return None, (
        "AUTO could not choose among multiple Swift profiles. "
        "Select the objective/profile explicitly on Set Scale, or put 4X/10X "
        "in each image or parent-folder name for a mixed-objective batch. "
        "Available profiles: " + available2
    )


def _swift_magn_image_info_dict(imp):
    values = {}
    if imp is None:
        return values
    try:
        info = imp.getProperty("Info")
    except:
        info = None
    if info is None:
        return values
    try:
        lines = str(info).replace("\r", "\n").split("\n")
    except:
        lines = []
    for line in lines:
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = str(key).strip()
        if key.startswith("GDL_SWIFT_MAGN_"):
            values[key] = str(val).strip()
    return values


def swift_magn_pixels_per_meter_to_scale(resolution_pixels_per_meter):
    """Convert Swift Resolution in pixels per meter (px/m) to physical pixel size."""
    px_per_meter = float(resolution_pixels_per_meter)
    if px_per_meter <= 0:
        raise ValueError("Swift Resolution must be greater than zero pixels per meter")
    meters_per_pixel = 1.0 / px_per_meter
    mm_per_pixel = meters_per_pixel * 1000.0
    um_per_pixel = meters_per_pixel * 1000000.0
    return mm_per_pixel, um_per_pixel


def hydrate_swift_magn_metadata_from_image(imp, settings):
    values = _swift_magn_image_info_dict(imp)
    profile_name = values.get("GDL_SWIFT_MAGN_PROFILE", "")
    if profile_name == "":
        return False
    try:
        resolution_text = values.get("GDL_SWIFT_MAGN_RESOLUTION_PIXELS_PER_METER", values.get("GDL_SWIFT_MAGN_RESOLUTION_PPM", "0"))
        resolution_ppm = float(resolution_text)
        mm_per_pixel = float(values.get("GDL_SWIFT_MAGN_MM_PER_PIXEL", "0"))
        um_per_pixel = float(values.get("GDL_SWIFT_MAGN_UM_PER_PIXEL", "0"))
    except:
        return False
    if resolution_ppm <= 0 or mm_per_pixel <= 0:
        return False

    settings["_swift_magn_applied"] = True
    settings["_swift_magn_table_path"] = values.get("GDL_SWIFT_MAGN_TABLE", "")
    settings["_swift_magn_profile_name"] = profile_name
    settings["_swift_magn_resolution_pixels_per_meter"] = resolution_ppm
    settings["_swift_magn_mm_per_pixel"] = mm_per_pixel
    settings["_swift_magn_um_per_pixel"] = um_per_pixel
    settings["_effective_scale_source"] = "Swift Imaging .magn"
    settings["_effective_report_scale_method"] = "Swift Imaging .magn - " + str(profile_name)
    return True


def _write_swift_magn_metadata_to_image(imp, table_path, profile_name, resolution_ppm, mm_per_pixel, um_per_pixel):
    if imp is None:
        return
    try:
        old_info = imp.getProperty("Info")
    except:
        old_info = None
    kept = []
    if old_info is not None:
        try:
            for line in str(old_info).replace("\r", "\n").split("\n"):
                if not str(line).strip().startswith("GDL_SWIFT_MAGN_"):
                    kept.append(str(line))
        except:
            kept = []
    kept.append("GDL_SWIFT_MAGN_PROFILE=" + str(profile_name))
    kept.append("GDL_SWIFT_MAGN_RESOLUTION_PIXELS_PER_METER=" + str(resolution_ppm))
    # Legacy v194-v195 key retained so older script builds can still read files.
    kept.append("GDL_SWIFT_MAGN_RESOLUTION_PPM=" + str(resolution_ppm))
    kept.append("GDL_SWIFT_MAGN_MM_PER_PIXEL=" + str(mm_per_pixel))
    kept.append("GDL_SWIFT_MAGN_UM_PER_PIXEL=" + str(um_per_pixel))
    kept.append("GDL_SWIFT_MAGN_TABLE=" + str(table_path))
    try:
        imp.setProperty("Info", "\n".join(kept))
    except Exception as e:
        IJ.log("Could not attach Swift scale audit metadata to image: " + str(e))


def apply_swift_magn_scale_to_image(imp, image_path, settings, image_name, step_notes=None, quality_warnings=None):
    if imp is None or not bool(settings.get("swift_magn_scale_enabled", True)):
        return False

    try:
        cal = imp.getCalibration()
    except:
        cal = None

    existing_is_scaled = False
    if cal is not None:
        try:
            existing_is_scaled = not calibration_unit_is_unscaled(cal)
        except:
            existing_is_scaled = False

    if existing_is_scaled and not bool(settings.get("swift_magn_override_existing_scale", False)):
        hydrated = hydrate_swift_magn_metadata_from_image(imp, settings)
        if hydrated:
            msg_existing = (
                "SWIFT .MAGN SCALE RETAINED: " + str(image_name) +
                "; profile=" + str(settings.get("_swift_magn_profile_name", "")) +
                "; scale=" + str(settings.get("_swift_magn_um_per_pixel", "")) + " um/pixel"
            )
            if step_notes is not None:
                step_notes.append(msg_existing)
        return False

    table_path, profiles = find_swift_magnification_table(image_path, settings)
    if table_path == "" or len(profiles) <= 0:
        _swift_magn_log_once(
            "missing|" + os.path.dirname(os.path.abspath(str(image_path))),
            "Swift .magn scale: no readable table found for " + str(image_path) +
            ". Manual/red-line fallback remains available."
        )
        return False

    requested = settings.get("swift_magn_profile_name", "AUTO")
    profile, select_error = select_swift_magnification_profile(profiles, requested, image_path)
    settings["_swift_magn_available_profiles"] = ", ".join(str(item.get("name", "")) for item in profiles)
    if profile is None:
        msg_select = "SWIFT .MAGN SCALE WARNING: " + str(select_error) + "; table=" + str(table_path)
        _swift_magn_log_once("select|" + table_path + "|" + str(requested) + "|" + str(image_path), msg_select)
        if quality_warnings is not None:
            quality_warnings.append(msg_select)
        if step_notes is not None:
            step_notes.append(msg_select)
        return False

    resolution_ppm = float(profile.get("resolution_pixels_per_meter", 0.0))
    if resolution_ppm <= 0:
        return False
    mm_per_pixel, um_per_pixel = swift_magn_pixels_per_meter_to_scale(resolution_ppm)

    # Broad physical sanity guard: 0.0001 um/px through 1000 um/px.
    if um_per_pixel <= 0.0001 or um_per_pixel >= 1000.0:
        msg_sanity = (
            "SWIFT .MAGN SCALE WARNING: decoded profile produced an implausible scale. "
            "Profile=" + str(profile.get("name", "")) +
            "; Resolution=" + str(resolution_ppm) +
            "; calculated um/pixel=" + str(um_per_pixel)
        )
        IJ.log(msg_sanity)
        if quality_warnings is not None:
            quality_warnings.append(msg_sanity)
        if step_notes is not None:
            step_notes.append(msg_sanity)
        return False

    try:
        if cal is None:
            cal = Calibration()
        cal.pixelWidth = float(mm_per_pixel)
        cal.pixelHeight = float(mm_per_pixel)
        try:
            cal.pixelDepth = float(mm_per_pixel)
        except:
            pass
        cal.setUnit("mm")
        imp.setCalibration(cal)
    except Exception as e_apply:
        msg_apply = "Could not apply Swift .magn scale to " + str(image_name) + ": " + str(e_apply)
        IJ.log(msg_apply)
        if quality_warnings is not None:
            quality_warnings.append(msg_apply)
        if step_notes is not None:
            step_notes.append(msg_apply)
        return False

    profile_name = str(profile.get("name", ""))
    _write_swift_magn_metadata_to_image(
        imp, table_path, profile_name, resolution_ppm, mm_per_pixel, um_per_pixel
    )

    settings["_swift_magn_applied"] = True
    settings["_swift_magn_table_path"] = str(table_path)
    settings["_swift_magn_profile_name"] = profile_name
    settings["_swift_magn_resolution_pixels_per_meter"] = resolution_ppm
    settings["_swift_magn_mm_per_pixel"] = mm_per_pixel
    settings["_swift_magn_um_per_pixel"] = um_per_pixel
    settings["_effective_scale_source"] = "Swift Imaging .magn"
    settings["_effective_report_scale_method"] = "Swift Imaging .magn - " + profile_name

    # Populate legacy auto-scale fields used elsewhere in the script.
    settings["_auto_scale_applied"] = True
    settings["_auto_scale_mm_per_pixel"] = mm_per_pixel
    settings["_auto_scale_pixels_per_mm"] = 1.0 / mm_per_pixel
    settings["_auto_scale_detected_pixels"] = "Swift .magn Resolution (pixels per meter)"
    settings["_auto_scale_known_length_mm"] = "Swift .magn profile " + profile_name

    msg = (
        "SWIFT .MAGN SCALE APPLIED: " + str(image_name) +
        "; profile=" + profile_name +
        "; Resolution=" + str(resolution_ppm) + " pixels per meter" +
        "; scale=" + ("%.9f" % um_per_pixel) + " um/pixel" +
        "; scale=" + ("%.12f" % mm_per_pixel) + " mm/pixel" +
        "; table=" + str(table_path)
    )
    IJ.log(msg)
    if step_notes is not None:
        step_notes.append(msg)
    return True


def apply_direct_scale_to_image(imp, settings, image_name, step_notes=None):
    if imp is None:
        return False
    if not settings.get("set_scale_direct_enabled", False):
        return False

    mm_per_pixel = 0.0
    try:
        mm_per_pixel = float(settings.get("set_scale_direct_mm_per_pixel", 0.0))
    except:
        mm_per_pixel = 0.0
    if mm_per_pixel <= 0:
        try:
            px_per_mm = float(settings.get("set_scale_direct_pixels_per_mm", 0.0))
            if px_per_mm > 0:
                mm_per_pixel = 1.0 / px_per_mm
        except:
            mm_per_pixel = 0.0

    if mm_per_pixel <= 0:
        return False

    try:
        cal = imp.getCalibration()
        cal.pixelWidth = float(mm_per_pixel)
        cal.pixelHeight = float(mm_per_pixel)
        cal.setUnit("mm")
        imp.setCalibration(cal)
        msg = "DIRECT SCALE APPLIED: " + str(image_name) + "; scale = " + str(mm_per_pixel) + " mm/pixel; pixels/mm = " + str(1.0 / float(mm_per_pixel))
        IJ.log(msg)
        if step_notes is not None:
            step_notes.append(msg)
        settings["_auto_scale_applied"] = True
        settings["_auto_scale_mm_per_pixel"] = float(mm_per_pixel)
        settings["_auto_scale_pixels_per_mm"] = 1.0 / float(mm_per_pixel)
        settings["_auto_scale_detected_pixels"] = "direct scale"
        settings["_auto_scale_known_length_mm"] = "direct scale"
        return True
    except Exception as e:
        IJ.log("Could not apply direct scale to " + str(image_name) + ": " + str(e))
        return False


def save_scaled_tif_next_to_input(imp, image_path, settings, step_notes=None):
    if imp is None:
        return ""
    if not settings.get("auto_scale_save_tif_enabled", True) and not settings.get("auto_scale_replace_png_with_tif_enabled", False):
        return ""
    try:
        src = str(image_path)
        root, ext = os.path.splitext(src)
        ext_l = str(ext).lower()

        common_batch_dir = str(settings.get("_set_scale_batch_output_dir", "")).strip()
        scaled_file_name = os.path.basename(root) + "_scaled.tif"

        if common_batch_dir != "":
            ensure_dir(common_batch_dir)
            out_path = os.path.join(common_batch_dir, scaled_file_name)
        elif settings.get("auto_scale_save_tif_subfolder_enabled", False):
            out_dir = os.path.join(os.path.dirname(src), "Scaled image")
            ensure_dir(out_dir)
            out_path = os.path.join(out_dir, scaled_file_name)
        else:
            out_path = root + "_scaled.tif"

        FileSaver(imp).saveAsTiff(out_path)
        msg = "Saved calibrated TIFF: " + str(out_path)
        IJ.log(msg)
        if step_notes is not None:
            step_notes.append(msg)
        settings["_auto_scale_saved_tif"] = out_path

        if settings.get("auto_scale_replace_png_with_tif_enabled", False) and common_batch_dir != "":
            msg_no_replace = "Replace PNG/JPG option skipped because calibrated TIFF was saved in a common Scaled image batch folder."
            IJ.log(msg_no_replace)
            if step_notes is not None:
                step_notes.append(msg_no_replace)

        elif settings.get("auto_scale_replace_png_with_tif_enabled", False) and settings.get("auto_scale_save_tif_subfolder_enabled", False):
            msg_no_replace = "Replace PNG/JPG option skipped because calibrated TIFF was saved in a Scaled image subfolder."
            IJ.log(msg_no_replace)
            if step_notes is not None:
                step_notes.append(msg_no_replace)

        if settings.get("auto_scale_replace_png_with_tif_enabled", False) and not settings.get("auto_scale_save_tif_subfolder_enabled", False) and ext_l in [".png", ".jpg", ".jpeg"]:
            try:
                backup_path = root + "_unscaled_original" + ext
                if os.path.exists(backup_path):
                    stamp = SimpleDateFormat("yyyyMMdd_HHmmss").format(Date())
                    backup_path = root + "_unscaled_original_" + str(stamp) + ext
                os.rename(src, backup_path)
                msg_replace = (
                    "Replaced PNG/JPG workflow with calibrated TIFF. "
                    "Original image moved to backup: " + str(backup_path) +
                    "; calibrated TIFF: " + str(out_path)
                )
                IJ.log(msg_replace)
                if step_notes is not None:
                    step_notes.append(msg_replace)
                settings["_auto_scale_replaced_input_backup"] = backup_path
            except Exception as e_replace:
                msg_replace_fail = "Could not move original PNG/JPG to backup after saving calibrated TIFF: " + str(e_replace)
                IJ.log(msg_replace_fail)
                if step_notes is not None:
                    step_notes.append(msg_replace_fail)

        return out_path
    except Exception as e:
        msg2 = "Could not save calibrated TIFF next to input " + str(image_path) + ": " + str(e)
        IJ.log(msg2)
        if step_notes is not None:
            step_notes.append(msg2)
        return ""
