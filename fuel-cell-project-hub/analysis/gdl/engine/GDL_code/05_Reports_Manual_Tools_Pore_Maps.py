# -*- coding: utf-8 -*-
# MODULE 05: Manual tools, pore maps, report tables, and report helpers


def manual_strand_measurement_entry(imp_original, cal, length_to_mm, settings, image_dir, base_safe, image_name):
    if not settings.get("manual_strand_measurement_enabled", False):
        return [], [], "", ""

    # v193: exactly one strand is selected per original batch image.
    count = 1

    strand_png = os.path.join(image_dir, base_safe + "_manual_strand_measurement_original.png")
    strand_tif = os.path.join(image_dir, base_safe + "_manual_strand_measurement_original.tif")
    strand_title = base_safe + "_manual_strand_measurement_original"

    lengths_mm = []
    trace_tools = []

    try:
        display = Duplicator().run(imp_original)
        display.setTitle(strand_title)
        FileSaver(display).saveAsTiff(strand_tif)
        FileSaver(display).saveAsPng(strand_png)
        display.show()
    except Exception as e:
        IJ.log("Could not open original image for manual strand measurement: " + str(e))
        return [], [], "", ""

    stop_manual_strands = False

    for strand_i in range(count):
        strand_num = strand_i + 1

        while True:
            WaitForUserDialog(
                "Manual Strand Measurement " + str(strand_num) + " of " + str(count),
                "Use the straight line, segmented line, or freehand line tool to trace strand #" + str(strand_num) + ".\n\n"
                "Leave the line ROI selected on the open original image, then click OK.\n\n"
                "The next popup will show the measured length so you can Accept or Redo it."
            ).show()

            length_mm = 0.0
            strand_roi_tool = "None"

            try:
                measure_imp = WindowManager.getImage(strand_title)
                if measure_imp is None:
                    measure_imp = WindowManager.getCurrentImage()

                if measure_imp is not None:
                    roi = measure_imp.getRoi()
                    if roi is not None:
                        strand_roi_tool = roi_tool_name(roi)
                        length_mm = roi_length_mm_from_roi(roi, cal, length_to_mm)
                        IJ.log("Manual strand #" + str(strand_num) + " length mm read automatically: " + str(length_mm))
                        IJ.log("Manual strand #" + str(strand_num) + " tracing tool: " + str(strand_roi_tool))
                    else:
                        IJ.log("No line ROI selected for manual strand #" + str(strand_num))
            except Exception as e:
                IJ.log("Could not read manual strand #" + str(strand_num) + " length: " + str(e))
                length_mm = 0.0

            if length_mm < 0:
                length_mm = 0.0

            decision = manual_strand_accept_redo(
                "Confirm Strand #" + str(strand_num) + " Measurement",
                "Strand #" + str(strand_num) + " measured length = " +
                format_docx_number(length_mm, int(settings.get("imagej_results_precision", 9))) + " mm\n" +
                "Tracing tool used = " + str(strand_roi_tool) + "\n\n" +
                "Accept this measurement or Redo the strand selection."
            )

            if decision == "redo":
                IJ.log("Redo requested for manual strand #" + str(strand_num))
                try:
                    measure_imp = WindowManager.getImage(strand_title)
                    if measure_imp is not None:
                        measure_imp.deleteRoi()
                except:
                    pass
                continue
            lengths_mm.append(float(length_mm))
            trace_tools.append(str(strand_roi_tool))
            break

        if stop_manual_strands:
            break

    return lengths_mm, trace_tools, strand_png, strand_tif


def manual_strand_cache_key(image_path):
    try:
        return os.path.normcase(os.path.abspath(str(image_path)))
    except:
        return str(image_path)


def manual_strand_measurement_once_per_original(imp_original, cal, length_to_mm, settings, image_dir, base_safe, image_name, image_path):
    """Prompt once for an original image, then reuse the accepted strand across all of its runs/sweeps."""
    cache = settings.get("_manual_strand_batch_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        settings["_manual_strand_batch_cache"] = cache

    cache_key = manual_strand_cache_key(image_path)
    cached = cache.get(cache_key, None)
    if isinstance(cached, dict):
        IJ.log("Manual strand measurement reused for original image: " + str(image_path))
        return (
            list(cached.get("lengths_mm", [])),
            list(cached.get("trace_tools", [])),
            str(cached.get("strand_png", "")),
            str(cached.get("strand_tif", "")),
            True
        )

    lengths_mm, trace_tools, strand_png, strand_tif = manual_strand_measurement_entry(
        imp_original, cal, length_to_mm, settings, image_dir, base_safe, image_name
    )
    cache[cache_key] = {
        "lengths_mm": list(lengths_mm),
        "trace_tools": list(trace_tools),
        "strand_png": str(strand_png),
        "strand_tif": str(strand_tif)
    }
    IJ.log("Manual strand measurement stored for reuse across runs of original image: " + str(image_path))
    return lengths_mm, trace_tools, strand_png, strand_tif, False



def manual_selection_match_error_prompt(error_text):
    try:
        msg = (
            "Manual selected pore could not be matched to the automated analysis table.\n\n"
            "Error: " + str(error_text) + "\n\n"
            "The nearest-centroid fallback is disabled so the script does not accidentally match the wrong pore.\n\n"
            "Try selecting/retracing the pore again. Make sure the selected ROI contains the automated pore centroid."
        )
        options = ["Reselect", "Skip this pore"]
        choice = JOptionPane.showOptionDialog(
            None,
            msg,
            "Manual Selection Match Error",
            JOptionPane.YES_NO_OPTION,
            JOptionPane.WARNING_MESSAGE,
            None,
            options,
            options[0]
        )
        if choice == 0:
            return "redo"
        return "cancel"
    except Exception as e:
        IJ.log("Could not show manual selection error prompt: " + str(e))
        return "redo"



def close_image_window_by_title(title):
    try:
        if title is None or str(title).strip() == "":
            return
        imp = WindowManager.getImage(str(title))
        if imp is not None:
            imp.changes = False
            imp.close()
    except Exception as e:
        IJ.log("Could not close preview image window: " + str(e))




def duplicate_full_image_without_roi_crop(source_imp, title):
    """
    Duplicate the full image even when a user ROI is currently selected.
    ImageJ's Duplicator crops to the active ROI, so this temporarily clears
    the ROI, duplicates the full image, then restores the ROI on the source.
    """
    if source_imp is None:
        return None

    saved_roi = None
    had_roi = False
    try:
        saved_roi = source_imp.getRoi()
        if saved_roi is not None:
            had_roi = True
            source_imp.deleteRoi()
    except:
        saved_roi = None
        had_roi = False

    dup = None
    try:
        dup = Duplicator().run(source_imp)
        if title is not None and str(title).strip() != "":
            dup.setTitle(str(title))
    finally:
        try:
            if had_roi and saved_roi is not None:
                source_imp.setRoi(saved_roi)
        except:
            pass

    return dup


def draw_manual_selected_trace_only(ip, selected_roi, settings):
    """Draw only the user trace line, with no crop and no offset clutter."""
    if ip is None or selected_roi is None:
        return False
    try:
        return draw_roi_outline(ip, selected_roi, get_setting_color(settings, "guide_selected_outline_color", Color.green), 1)
    except:
        return False

def draw_manual_selected_trace_and_offset(ip, selected_roi, settings):
    """
    Draw the exact user-traced pore ROI plus the requested 10 px offset guide.
    This is used only in the selected-pore high-difference preview path.
    """
    if ip is None or selected_roi is None:
        return False

    drawn_any = False
    trace_color = get_setting_color(settings, "guide_selected_outline_color", Color.green)

    # Exact pore trace: this shows what the user actually drew.
    try:
        if draw_roi_outline(ip, selected_roi, trace_color, 1):
            drawn_any = True
    except:
        pass

    # Offset guide: fixed at 10 px and 3 px wide for the high-difference check.
    try:
        selected_offset_roi = make_offset_roi_from_roi(selected_roi, 10.0)
        if selected_offset_roi is not None:
            if draw_roi_outline(ip, selected_offset_roi, trace_color, 1):
                drawn_any = True
    except:
        pass

    return drawn_any



def show_modeless_choice_dialog(title, message, button_defs, default_value, image_title=None, width=760, height=430):
    """
    Modeless choice dialog that waits for a button choice without using JOptionPane.showOptionDialog.
    Because it is MODELESS, the user can click the ImageJ image/preview window, zoom, pan,
    and inspect overlays while the script is paused waiting for a decision.

    button_defs = [(button_text, return_value, primary_bool), ...]
    """
    state = {"done": False, "choice": default_value}

    try:
        dlg = JDialog()
        dlg.setTitle(str(title))
        dlg.setModal(False)
        try:
            dlg.setModalityType(Dialog.ModalityType.MODELESS)
        except:
            pass
        try:
            dlg.setAlwaysOnTop(False)
        except:
            pass
        try:
            dlg.setFocusableWindowState(True)
        except:
            pass
        try:
            dlg.setDefaultCloseOperation(0)  # DO_NOTHING_ON_CLOSE
        except:
            pass

        panel = JPanel(BorderLayout(10, 10))
        try:
            panel.setBorder(BorderFactory.createEmptyBorder(12, 12, 12, 12))
        except:
            pass

        msg_text = str(message)
        msg_text += "\n\nThis window is non-blocking. You can leave it open, click the ImageJ preview image, zoom/pan/check the trace, then come back and choose an option."

        msg = JTextArea(msg_text)
        msg.setEditable(False)
        msg.setLineWrap(True)
        msg.setWrapStyleWord(True)
        try:
            msg.setBackground(Color(248, 248, 248))
        except:
            pass
        scroll = JScrollPane(msg)
        try:
            scroll.setPreferredSize(Dimension(int(width), int(height)))
        except:
            scroll.setPreferredSize(Dimension(760, 430))
        panel.add(scroll, BorderLayout.CENTER)

        button_panel = JPanel()

        def choose(value):
            state["choice"] = value
            state["done"] = True
            try:
                dlg.dispose()
            except:
                pass

        for bd in button_defs:
            try:
                text_btn = bd[0]
                value_btn = bd[1]
                primary_btn = bool(bd[2])
            except:
                text_btn = str(bd)
                value_btn = str(bd)
                primary_btn = False
            btn = JButton(str(text_btn))
            try:
                style_dialog_button(btn, primary_btn)
            except:
                pass
            def button_action(event, v=value_btn):
                choose(v)
            btn.addActionListener(button_action)
            button_panel.add(btn)

        panel.add(button_panel, BorderLayout.SOUTH)

        class ModelessChoiceCloseListener(WindowAdapter):
            def windowClosing(self, event):
                choose(default_value)

        dlg.addWindowListener(ModelessChoiceCloseListener())
        dlg.add(panel)
        dlg.pack()

        try:
            screen = Toolkit.getDefaultToolkit().getScreenSize()
            # Put it off to the side so it does not sit directly over the pore trace.
            x = max(20, int(screen.width) - int(width) - 90)
            y = 90
            dlg.setLocation(x, y)
        except:
            try:
                dlg.setLocation(40, 80)
            except:
                pass

        dlg.setVisible(True)

        # Make sure the trace/preview image can be interacted with right away.
        # The dialog stays available but does not own the UI focus like JOptionPane did.
        try:
            if image_title is not None and str(image_title).strip() != "":
                img = WindowManager.getImage(str(image_title))
                if img is not None and img.getWindow() is not None:
                    img.getWindow().toFront()
                    try:
                        img.getCanvas().requestFocus()
                    except:
                        pass
        except:
            pass

        while not state["done"]:
            try:
                IJ.wait(100)
            except:
                time.sleep(0.10)

        return state["choice"]

    except Exception as e:
        IJ.log("Could not show modeless choice dialog " + str(title) + ": " + str(e))
        return default_value


def manual_selected_high_difference_prompt(manual_area_mm2, table_area_mm2, percent_diff, trigger_limit, auto_fit_enabled, match_row, match_method, trace_tool, preview_image_title=None):
    # Returns: "autofit", "redo", "accept", or "cancel".
    # This summary appears only when the selected pore is outside the trigger limit.
    # It is intentionally modeless so the user can click/zoom/pan the preview image before choosing.
    try:
        msg = (
            "Manual selected-pore difference summary\n\n"
            "Matched analysis pore ID = " + str(match_row + 1) + "\n"
            "Manual selected pore area = " + str(manual_area_mm2) + " mm^2\n"
            "Matched table pore area = " + str(table_area_mm2) + " mm^2\n"
            "Manual - table % difference = " + str(percent_diff) + "%\n"
            "Trigger limit = +/-" + str(trigger_limit) + "%\n"
            "Match method = " + str(match_method) + "\n"
            "Tracing tool used = " + str(trace_tool) + "\n\n"
            "The full trace-vs-generated preview image is open.\n"
            "Red outline = automated/generated pore trace from the segmented mask.\n"
            "Green outline = your hand trace drawn over the generated pore trace.\n"
        )

        if auto_fit_enabled:
            msg += "\nChoose Auto-Fit/Adjust to open the threshold adjustment, Reselect to retrace, or Skip / Move On to accept the current threshold."
            return show_modeless_choice_dialog(
                "Manual Selected-Pore Auto-Fit Summary",
                msg,
                [("Auto-Fit/Adjust", "autofit", True), ("Reselect", "redo", False), ("Skip / Move On", "accept", False), ("Cancel", "cancel", False)],
                "cancel",
                preview_image_title,
                820,
                430
            )
        else:
            msg += "\nAuto-fit is disabled. Reselect the pore if the trace is wrong, or Skip / Move On to accept the current threshold."
            return show_modeless_choice_dialog(
                "Manual Selected-Pore Difference Summary",
                msg,
                [("Reselect", "redo", True), ("Skip / Move On", "accept", False), ("Cancel", "cancel", False)],
                "cancel",
                preview_image_title,
                820,
                430
            )

    except Exception as e:
        IJ.log("Could not show manual selected-pore high-difference summary: " + str(e))
        if auto_fit_enabled:
            return "autofit"
        return "accept"


# Embedded right-side image for the under-5% pore-trace celebration popup.
# Cropped from the supplied visual reference so the script remains standalone.
MANUAL_TRACE_CELEBRATION_PHOTO_B64 = None

def close_manual_under_trigger_success_popup(settings):
    try:
        timer = settings.get("_manual_under_trigger_success_popup_timer", None)
    except:
        timer = None
    if timer is not None:
        try:
            timer.stop()
        except:
            pass

    try:
        dlg = settings.get("_manual_under_trigger_success_popup_dialog", None)
    except:
        dlg = None
    if dlg is not None:
        try:
            dlg.dispose()
        except:
            pass

    try:
        settings["_manual_under_trigger_success_popup_dialog"] = None
        settings["_manual_under_trigger_success_popup_timer"] = None
    except:
        pass


class ManualUnderTriggerPopupCloser(ActionListener):
    def __init__(self, dialog_ref, settings_ref):
        self.dialog_ref = dialog_ref
        self.settings_ref = settings_ref

    def actionPerformed(self, event):
        try:
            timer = self.settings_ref.get("_manual_under_trigger_success_popup_timer", None)
            if timer is not None and timer is not event.getSource():
                timer.stop()
        except:
            pass
        try:
            self.dialog_ref.dispose()
        except:
            pass
        try:
            self.settings_ref["_manual_under_trigger_success_popup_dialog"] = None
            self.settings_ref["_manual_under_trigger_success_popup_timer"] = None
        except:
            pass
        try:
            event.getSource().stop()
        except:
            pass


def show_manual_under_trigger_success_popup(percent_diff, trigger_limit, settings, image_title=None):
    """Show a modeless success popup and close it automatically after 3 seconds."""
    try:
        close_manual_under_trigger_success_popup(settings)

        try:
            diff_value = abs(float(percent_diff))
        except:
            diff_value = 0.0
        try:
            limit_value = abs(float(trigger_limit))
        except:
            limit_value = 5.0

        def pretty_percent(value):
            try:
                return ("%.2f" % float(value)).rstrip("0").rstrip(".") + "%"
            except:
                return str(value) + "%"

        show_picture = bool(settings.get("manual_success_popup_show_picture", True))

        dlg = JDialog()
        dlg.setTitle("Great Job!")
        dlg.setModal(False)
        try:
            dlg.setModalityType(Dialog.ModalityType.MODELESS)
        except:
            pass
        try:
            dlg.setAlwaysOnTop(True)
        except:
            pass
        dlg.setDefaultCloseOperation(JDialog.DISPOSE_ON_CLOSE)

        try:
            screen = Toolkit.getDefaultToolkit().getScreenSize()
            if show_picture:
                dlg_w = min(1040, max(820, int(float(screen.width) * 0.68)))
                dlg_h = min(720, max(600, int(float(screen.height) * 0.66)))
            else:
                dlg_w = min(720, max(600, int(float(screen.width) * 0.48)))
                dlg_h = min(700, max(580, int(float(screen.height) * 0.68)))
        except:
            dlg_w = 980 if show_picture else 680
            dlg_h = 680 if show_picture else 640

        root = JPanel(BorderLayout())
        root.setBackground(Color.white)
        root.setBorder(BorderFactory.createLineBorder(Color(190, 190, 190), 1))

        body = JPanel(BorderLayout())
        body.setBackground(Color.white)
        content_h = max(500, dlg_h - 95)
        left_w = int(float(dlg_w) * 0.64) if show_picture else dlg_w - 30

        left = JPanel()
        left.setLayout(BoxLayout(left, BoxLayout.Y_AXIS))
        left.setBackground(Color.white)
        left.setBorder(BorderFactory.createEmptyBorder(22, 24, 16, 24))
        left.setPreferredSize(Dimension(left_w, content_h))

        def centered_label(text_value, font_size, font_style, color_value, height):
            lab = JLabel(str(text_value))
            lab.setHorizontalAlignment(JLabel.CENTER)
            lab.setAlignmentX(0.5)
            lab.setForeground(color_value)
            lab.setFont(Font("SansSerif", font_style, int(font_size)))
            lab.setMaximumSize(Dimension(max(300, left_w - 44), int(height)))
            lab.setPreferredSize(Dimension(max(300, left_w - 44), int(height)))
            left.add(lab)
            return lab

        left.add(Box.createVerticalStrut(6))
        centered_label("CONGRATULATIONS!", 34, Font.BOLD, Color(25, 25, 180), 58)
        left.add(Box.createVerticalStrut(10))
        centered_label("You traced under", 29, Font.BOLD, Color(20, 20, 20), 48)
        centered_label(pretty_percent(limit_value), 72, Font.BOLD, Color(69, 184, 73), 100)
        centered_label("Difference: " + pretty_percent(diff_value), 29, Font.BOLD, Color(36, 122, 53), 56)
        left.add(Box.createVerticalStrut(8))

        divider = JPanel(BorderLayout(10, 0))
        divider.setOpaque(False)
        divider.setMaximumSize(Dimension(max(300, left_w - 70), 32))
        divider.setPreferredSize(Dimension(max(300, left_w - 70), 32))
        line_left = JPanel()
        line_left.setBackground(Color(35, 125, 220))
        line_left.setPreferredSize(Dimension(180, 2))
        line_right = JPanel()
        line_right.setBackground(Color(35, 125, 220))
        line_right.setPreferredSize(Dimension(180, 2))
        star = JLabel("*")
        star.setHorizontalAlignment(JLabel.CENTER)
        star.setForeground(Color(35, 125, 220))
        star.setFont(Font("SansSerif", Font.BOLD, 28))
        divider.add(line_left, BorderLayout.WEST)
        divider.add(star, BorderLayout.CENTER)
        divider.add(line_right, BorderLayout.EAST)
        divider.setAlignmentX(0.5)
        left.add(divider)
        left.add(Box.createVerticalStrut(10))

        centered_label("Excellent work! Your trace is", 25, Font.BOLD, Color(20, 20, 20), 39)
        centered_label("in great agreement with the", 25, Font.BOLD, Color(20, 20, 20), 39)
        centered_label("actual pores.", 25, Font.BOLD, Color(20, 20, 20), 39)
        left.add(Box.createVerticalGlue())
        centered_label("John GDL is proud!  :)", 27, Font.BOLD | Font.ITALIC, Color(25, 25, 180), 56)

        body.add(left, BorderLayout.CENTER if not show_picture else BorderLayout.WEST)

        if show_picture:
            right_w = min(340, max(240, dlg_w - left_w - 15))
            right = JPanel(BorderLayout())
            right.setBackground(Color.white)
            right.setPreferredSize(Dimension(right_w, content_h))
            try:
                buffered = load_gdl_v193_resource_image("manual_trace_celebration_small.jpg")
                scale_x = float(right_w) / float(buffered.getWidth())
                scale_y = float(content_h) / float(buffered.getHeight())
                scale_factor = min(scale_x, scale_y, 1.0)
                draw_w = max(1, int(round(float(buffered.getWidth()) * scale_factor)))
                draw_h = max(1, int(round(float(buffered.getHeight()) * scale_factor)))
                img_label = JLabel(ImageIcon(buffered.getScaledInstance(draw_w, draw_h, Image.SCALE_SMOOTH)))
                img_label.setHorizontalAlignment(JLabel.CENTER)
                img_label.setVerticalAlignment(JLabel.CENTER)
                right.add(img_label, BorderLayout.CENTER)
            except Exception as e_img:
                IJ.log("Could not load celebration popup image: " + str(e_img))
            body.add(right, BorderLayout.CENTER)

        root.add(body, BorderLayout.CENTER)

        footer = JPanel()
        footer.setBackground(Color(248, 248, 248))
        footer.setBorder(BorderFactory.createCompoundBorder(
            BorderFactory.createMatteBorder(1, 0, 0, 0, Color(220, 220, 220)),
            BorderFactory.createEmptyBorder(10, 10, 10, 10)
        ))
        ok_button = JButton("OK")
        ok_button.setFont(Font("SansSerif", Font.BOLD, 20))
        ok_button.setPreferredSize(Dimension(145, 44))
        ok_button.setFocusPainted(False)
        ok_button.addActionListener(ManualUnderTriggerPopupCloser(dlg, settings))
        footer.add(ok_button)
        root.add(footer, BorderLayout.SOUTH)

        dlg.setContentPane(root)
        dlg.setSize(dlg_w, dlg_h)
        dlg.setLocationRelativeTo(None)

        class ManualUnderTriggerCloseListener(WindowAdapter):
            def windowClosing(self, event):
                try:
                    timer = settings.get("_manual_under_trigger_success_popup_timer", None)
                    if timer is not None:
                        timer.stop()
                except:
                    pass
                try:
                    settings["_manual_under_trigger_success_popup_dialog"] = None
                    settings["_manual_under_trigger_success_popup_timer"] = None
                except:
                    pass
            def windowClosed(self, event):
                self.windowClosing(event)

        dlg.addWindowListener(ManualUnderTriggerCloseListener())
        settings["_manual_under_trigger_success_popup_dialog"] = dlg
        dlg.setVisible(True)
        try:
            dlg.toFront()
            ok_button.requestFocusInWindow()
        except:
            pass

        try:
            timer = Timer(3000, ManualUnderTriggerPopupCloser(dlg, settings))
            timer.setRepeats(False)
            settings["_manual_under_trigger_success_popup_timer"] = timer
            timer.start()
        except Exception as e_timer:
            IJ.log("Could not start manual trace success popup timer: " + str(e_timer))

    except Exception as e:
        IJ.log("Could not show manual trace success popup: " + str(e))

def show_manual_selected_centroid_preview(measure_imp, selected_roi, mask, rt, match_row, cal, settings, base_safe, image_dir=""):
    # Popup-only full-image preview: automated/generated pore trace first, then the user's trace over it.
    # Important: this must duplicate the full image. ImageJ Duplicator crops when an ROI is active.
    # This preview is not added to the Word report.
    preview = None
    try:
        if measure_imp is None or selected_roi is None or match_row < 0:
            return "continue"

        x_val = rt_value(rt, "X", match_row)
        y_val = rt_value(rt, "Y", match_row)
        if x_val is None or y_val is None:
            return "continue"

        x_px = calibrated_to_pixel_x(cal, x_val)
        y_px = calibrated_to_pixel_y(cal, y_val)

        inside = False
        try:
            inside = selected_roi.contains(int(round(x_px)), int(round(y_px)))
        except:
            inside = False

        preview_title = base_safe + "_manual_pore_generated_trace_with_user_trace_over_5pct"
        preview = duplicate_full_image_without_roi_crop(measure_imp, preview_title)
        if preview is None:
            return "continue"

        try:
            if preview.getBitDepth() != 24:
                IJ.run(preview, "RGB Color", "")
        except:
            pass

        ip = preview.getProcessor()

        actual_drawn = False
        try:
            # Draw the automated/generated pore trace first. The user trace is drawn after this
            # so the green hand trace is visible on top instead of being hidden.
            actual_drawn = draw_dilated_component_outline_on_ip(
                mask,
                ip,
                x_px,
                y_px,
                settings,
                40,
                0.0,
                Color.red,
                1
            )
        except Exception as e_actual_trace:
            IJ.log("Could not draw actual matched automated pore trace in high-difference preview: " + str(e_actual_trace))

        user_drawn = False
        try:
            user_drawn = draw_manual_selected_trace_only(ip, selected_roi, settings)
        except Exception as e_user_trace:
            IJ.log("Could not draw user manual selected pore trace in high-difference preview: " + str(e_user_trace))

        try:
            # Matched automated pore centroid marker: red filled dot, 4 px diameter.
            # This replaces the older cross/label marker so the trace overlay stays clean.
            marker_color = Color.red
            marker_text = "Matched centroid shown as 4 px red dot"
            draw_solid_dot(ip, x_px, y_px, 2, marker_color)
        except:
            marker_text = "Centroid preview"

        try:
            preview.show()
            settings["_manual_selected_trace_preview_title"] = preview.getTitle()
        except:
            pass

        try:
            if image_dir is not None and str(image_dir).strip() != "":
                preview_png = os.path.join(str(image_dir), base_safe + "_manual_pore_generated_trace_with_user_trace_over_5pct.png")
                FileSaver(preview).saveAsPng(preview_png)
                settings["_manual_selected_trace_preview_png"] = preview_png
        except Exception as e_save_preview:
            IJ.log("Could not save manual trace-vs-generated preview PNG: " + str(e_save_preview))

        # Do not show a separate Continue/Reselect popup here. The preview image stays open,
        # and the next/only high-difference summary asks whether to Auto-Fit, Reselect,
        # Skip / Move On, or Cancel. This avoids two back-to-back popups.
        IJ.log("Manual pore trace-vs-generated preview is open for high-difference review. " +
               "Actual generated trace drawn: " + str(actual_drawn) +
               "; user trace drawn: " + str(user_drawn) +
               "; " + str(marker_text))
        try:
            if preview.getWindow() is not None:
                preview.getWindow().toFront()
        except:
            pass
        return "continue"

    except Exception as e:
        IJ.log("Could not show manual selected-pore generated-trace preview: " + str(e))
        return "continue"
    finally:
        # Do not close the preview here. For >5% differences it must stay open
        # behind the auto-fit/redo summary so the user can inspect the trace.
        pass



def wait_for_manual_pore_trace_nonmodal(title, message, image_title=None):
    """
    True modeless trace-control window for manual pore selection.
    This intentionally avoids WaitForUserDialog because that dialog is modal and
    prevents the user from clicking back into the ImageJ image to zoom/pan.
    Returns "ok" or "cancel".
    """
    state = {"done": False, "choice": "ok"}

    try:
        dlg = JDialog()
        dlg.setTitle(title)
        dlg.setModal(False)
        try:
            dlg.setModalityType(Dialog.ModalityType.MODELESS)
        except:
            pass
        try:
            dlg.setAlwaysOnTop(False)
        except:
            pass
        try:
            dlg.setFocusableWindowState(True)
        except:
            pass

        panel = JPanel(BorderLayout(8, 8))
        try:
            panel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10))
        except:
            pass

        msg = JTextArea(str(message))
        msg.setEditable(False)
        msg.setLineWrap(True)
        msg.setWrapStyleWord(True)
        try:
            msg.setBackground(Color(250, 250, 250))
        except:
            pass
        scroll = JScrollPane(msg)
        scroll.setPreferredSize(Dimension(560, 250))
        panel.add(scroll, BorderLayout.CENTER)

        button_panel = JPanel()
        ok_btn = JButton("Continue after tracing")
        cancel_btn = JButton("Cancel / skip")
        try:
            style_dialog_button(ok_btn, True)
            style_dialog_button(cancel_btn, False)
        except:
            pass

        def ok_action(event):
            state["choice"] = "ok"
            state["done"] = True
            try:
                dlg.dispose()
            except:
                pass

        def cancel_action(event):
            state["choice"] = "cancel"
            state["done"] = True
            try:
                dlg.dispose()
            except:
                pass

        ok_btn.addActionListener(ok_action)
        cancel_btn.addActionListener(cancel_action)
        button_panel.add(ok_btn)
        button_panel.add(cancel_btn)
        panel.add(button_panel, BorderLayout.SOUTH)

        class ManualTraceCloseListener(WindowAdapter):
            def windowClosing(self, event):
                state["choice"] = "cancel"
                state["done"] = True
                try:
                    dlg.dispose()
                except:
                    pass

        dlg.addWindowListener(ManualTraceCloseListener())
        dlg.add(panel)
        dlg.pack()

        # Put the control panel to the side instead of centered on the image.
        try:
            screen = Toolkit.getDefaultToolkit().getScreenSize()
            dlg.setLocation(max(20, int(screen.width) - 650), 80)
        except:
            try:
                dlg.setLocation(40, 80)
            except:
                pass

        dlg.setVisible(True)

        # Immediately hand focus back to the real ImageJ image window.
        try:
            if image_title is not None and str(image_title).strip() != "":
                img = WindowManager.getImage(str(image_title))
                if img is not None and img.getWindow() is not None:
                    img.getWindow().toFront()
                    img.getCanvas().requestFocus()
        except:
            pass

        # Wait without using WaitForUserDialog. IJ.wait gives AWT/Swing time to process,
        # so image zoom/pan/ROI edits remain responsive while the script is paused here.
        while not state["done"]:
            try:
                IJ.wait(100)
            except:
                time.sleep(0.10)

        return state["choice"]

    except Exception as e:
        # Do NOT fall back to WaitForUserDialog here because that is the exact modal
        # dialog that blocks zooming/panning. If the floating control cannot be made,
        # cancel gracefully instead of trapping the user in a modal popup.
        IJ.log("Could not show true modeless manual pore trace control; canceling this manual trace step: " + str(e))
        try:
            IJ.showMessage("Manual Pore Trace Control Error", "The non-blocking trace control could not be opened. This manual trace step will be skipped instead of opening a blocking popup.\n\n" + str(e))
        except:
            pass
        return "cancel"

def manual_selected_pore_entry(imp_original, mask, rt, cal, area_to_mm2, settings, image_dir, base_safe, image_name, largest_guide_png_path=""):
    if not settings.get("manual_selected_pore_enabled", False):
        return None, None, -1, 0.0, 0.0, "", "", "", "", None, "None"

    # Close the prior under-5% congrats popup as soon as the next manual trace is ready.
    close_manual_under_trigger_success_popup(settings)

    selected_png = os.path.join(image_dir, base_safe + "_manual_pore_trace_original.png")
    selected_tif = os.path.join(image_dir, base_safe + "_manual_pore_trace_original.tif")
    trace_title = base_safe + "_manual_pore_trace_original"
    combined_png = ""
    combined_tif = ""

    try:
        display = duplicate_full_image_without_roi_crop(imp_original, trace_title)
        if display is None:
            raise Exception("Could not duplicate original image for manual trace display")
        # Do not filter/preprocess this image. This is a direct original-image display copy.
        try:
            if display.getBitDepth() != 24:
                IJ.run(display, "RGB Color", "")
        except:
            pass

        try:
            largest_row, largest_epd_mm, guide_x_px, guide_y_px, largest_area_mm2, largest_area_raw = find_largest_pore_from_results(rt, cal, area_to_mm2)
            if largest_row >= 0 and mask is not None:
                guide_drawn = draw_dilated_component_outline_on_ip(
                    mask,
                    display.getProcessor(),
                    guide_x_px,
                    guide_y_px,
                    settings,
                    40,
                    10.0,
                    get_setting_color(settings, "guide_largest_outline_color", Color.green),
                    settings.get("guide_outline_line_width", 1)
                )
                if guide_drawn:
                    IJ.log("Manual pore trace guide: largest pore offset outline drawn on the same image. The user may trace this pore or any other pore.")
                else:
                    IJ.log("Manual pore trace guide: could not draw largest-pore guide; user can still trace any pore.")
        except Exception as e_guide:
            IJ.log("Could not draw largest-pore guide on manual trace image: " + str(e_guide))

        FileSaver(display).saveAsTiff(selected_tif)
        FileSaver(display).saveAsPng(selected_png)
        display.show()
    except Exception as e:
        IJ.log("Could not open original image for manual pore trace measurement: " + str(e))
        return None, None, -1, 0.0, 0.0, "", "", "", "", None, "None"

    while True:
        trace_wait_choice = wait_for_manual_pore_trace_nonmodal(
            "Manual Pore Trace Measurement",
            "The original image is open in a normal ImageJ window with the automated largest pore shown as an outward 10 px guide outline.\n\n"
            "You are NOT locked into this control window. Click the ImageJ image window and zoom/pan normally before tracing.\n\n"
            "Zoom/pan options:\n"
            "- Mouse wheel / trackpad zoom if your Fiji setup supports it.\n"
            "- + and - keys, or the ImageJ magnifying glass tool.\n"
            "- Spacebar/hand tool to pan, depending on your Fiji setup.\n\n"
            "Then trace the guided largest pore OR any other pore on the same image.\n"
            "Leave the ROI selected and click Continue after tracing here.\n\n"
            "The script will read the selected ROI, match it to the generated pore trace, and only show the >5% comparison if needed.",
            trace_title
        )

        if trace_wait_choice == "cancel":
            IJ.log("Manual selected pore measurement canceled before ROI read for: " + str(image_name))
            return None, None, -1, 0.0, 0.0, selected_png, "manual trace canceled", combined_png, combined_tif, None, "None"

        manual_area_raw = 0.0
        roi_center_x = None
        roi_center_y = None
        selected_roi = None
        selected_roi_tool = "None"

        try:
            measure_imp = WindowManager.getImage(trace_title)
            if measure_imp is None:
                measure_imp = WindowManager.getCurrentImage()

            if measure_imp is not None:
                roi = measure_imp.getRoi()
                if roi is not None:
                    selected_roi = roi
                    selected_roi_tool = roi_tool_name(roi)
                    stats = measure_imp.getStatistics(Measurements.AREA + Measurements.CENTROID)
                    manual_area_raw = float(stats.area)

                    # Use ROI bounds for the matching center because ROI bounds are in raw pixel coordinates.
                    # ImageJ statistics centroids may be calibrated coordinates, which can cause wrong matching.
                    b = roi.getBounds()
                    roi_center_x = float(b.x) + float(b.width) / 2.0
                    roi_center_y = float(b.y) + float(b.height) / 2.0

                    IJ.log("Manual selected ROI area read automatically: " + str(manual_area_raw))
                    IJ.log("Manual selected ROI tracing tool: " + str(selected_roi_tool))
                    IJ.log("Manual selected ROI matching center, pixels: " + str(roi_center_x) + ", " + str(roi_center_y))
                else:
                    IJ.log("No ROI selected on manual selected pore image.")
        except Exception as e:
            IJ.log("Could not read selected manual pore ROI: " + str(e))
            manual_area_raw = 0.0

        if roi_center_x is None or roi_center_y is None:
            roi_center_x = 0.0
            roi_center_y = 0.0

        if selected_roi is not None:
            match_row, table_epd_mm, table_area_mm2, dist2, match_method = find_analysis_pore_matching_manual_roi(
                rt, cal, area_to_mm2, selected_roi, roi_center_x, roi_center_y, manual_area_raw
            )
        else:
            match_row = -1
            table_epd_mm = 0.0
            table_area_mm2 = 0.0
            dist2 = None
            match_method = "no ROI selected"

        if match_row < 0:
            err_text = str(match_method)
            if selected_roi is None:
                err_text = "No ROI was selected."
            elif str(match_method).strip() == "":
                err_text = "No automated pore centroid was inside the selected ROI."
            decision_match_error = manual_selection_match_error_prompt(err_text)
            if decision_match_error == "redo":
                IJ.log("Manual selected pore match error; user chose to reselect. Error: " + str(err_text))
                continue
            IJ.log("Manual selected pore skipped after match error: " + str(err_text))
            return None, None, -1, 0.0, 0.0, selected_png, err_text, combined_png, combined_tif, selected_roi, selected_roi_tool

        if manual_area_raw <= 0:
            decision_bad = manual_measurement_accept_redo_cancel(
                "Invalid Manual Selected Pore Area",
                "The manual selected pore area is zero or invalid.\n\n"
                "Click Redo to reselect/retrace the ROI, or Cancel to skip this measurement."
            )
            if decision_bad == "redo":
                continue
            IJ.log("Invalid manual selected pore area entered for: " + str(image_name))
            return None, None, match_row + 1, table_epd_mm, table_area_mm2, selected_png, match_method, combined_png, combined_tif, selected_roi, selected_roi_tool

        manual_area_mm2 = float(manual_area_raw) * area_to_mm2
        manual_epd_mm = math.sqrt((manual_area_mm2 * 4.0) / math.pi)
        manual_selected_percent_diff = area_percent_difference(manual_area_mm2, table_area_mm2)

        try:
            trigger_limit = float(settings.get("auto_threshold_fit_trigger_percent_diff", 5.0))
        except:
            trigger_limit = 5.0
        if trigger_limit < 0:
            trigger_limit = 0.0

        try:
            manual_selected_abs_diff = abs(float(manual_selected_percent_diff))
        except:
            manual_selected_abs_diff = 0.0

        high_diff = manual_selected_abs_diff >= trigger_limit
        settings["_manual_selected_pore_high_diff_choice"] = "below_trigger"

        if high_diff:
            settings["_manual_selected_trace_preview_title"] = ""
            # Use the clean original image for the comparison preview, not the guided manual-trace window.
            # This avoids carrying the startup largest-pore guide into the trace-vs-generated comparison.
            preview_imp = imp_original

            preview_decision = show_manual_selected_centroid_preview(preview_imp, selected_roi, mask, rt, match_row, cal, settings, base_safe, image_dir)
            if preview_decision == "redo":
                close_image_window_by_title(settings.get("_manual_selected_trace_preview_title", ""))
                IJ.log("Manual selected-pore high-difference preview requested reselection for: " + str(image_name))
                continue

            # No separate cropped/combined guide image is created here.
            # The high-difference preview is the full same trace image with user trace vs actual automated pore outline.
            high_decision = manual_selected_high_difference_prompt(
                manual_area_mm2,
                table_area_mm2,
                manual_selected_percent_diff,
                trigger_limit,
                settings.get("auto_threshold_fit_enabled", False),
                match_row,
                match_method,
                selected_roi_tool,
                settings.get("_manual_selected_trace_preview_title", "")
            )
            settings["_manual_selected_pore_high_diff_choice"] = high_decision
            close_image_window_by_title(settings.get("_manual_selected_trace_preview_title", ""))

            if high_decision == "redo":
                IJ.log("Redo requested from selected-pore high-difference summary for: " + str(image_name))
                continue
            if high_decision == "cancel":
                IJ.log("Manual selected pore measurement skipped from high-difference summary for: " + str(image_name))
                return None, None, match_row + 1, table_epd_mm, table_area_mm2, selected_png, match_method, combined_png, combined_tif, selected_roi, selected_roi_tool

            IJ.log("Manual selected pore is outside +/-" + str(trigger_limit) + "% and was accepted for follow-up/auto-fit check. Difference = " + str(manual_selected_percent_diff) + "%")
        else:
            IJ.log("Manual selected pore is within +/-" + str(trigger_limit) + "% of matched analysis pore; moving on without auto-fit/redo summary. Difference = " + str(manual_selected_percent_diff) + "%")
            show_manual_under_trigger_success_popup(manual_selected_percent_diff, trigger_limit, settings, trace_title)

        IJ.log("Manual selected pore for " + str(image_name))
        IJ.log("Manual selected area raw = " + str(manual_area_raw))
        IJ.log("Manual selected area mm^2 = " + str(manual_area_mm2))
        IJ.log("Manual selected EPD mm = " + str(manual_epd_mm))
        IJ.log("Nearest analysis pore ID = " + str(match_row + 1))
        IJ.log("Nearest analysis area mm^2 = " + str(table_area_mm2))
        IJ.log("Manual selected tracing tool = " + str(selected_roi_tool))

        return manual_area_mm2, manual_epd_mm, match_row + 1, table_epd_mm, table_area_mm2, selected_png, match_method, combined_png, combined_tif, selected_roi, selected_roi_tool


def make_segmented_highlight_with_largest_pore(mask, rt, cal, area_to_mm2, settings, image_dir, base_safe):
    if not run_image_outputs_enabled(settings):
        return "", "", -1, 0.0
    highlight_png = os.path.join(image_dir, base_safe + "_segmented_mask_largest_pore_highlight.png")
    highlight_tif = os.path.join(image_dir, base_safe + "_segmented_mask_largest_pore_highlight.tif")

    if not settings.get("highlight_largest_pore_in_segmented", False):
        return "", "", -1, 0.0

    largest_row = -1
    largest_area_mm2 = -1.0
    largest_epd_mm = 0.0
    filled_pixels = 0

    try:
        rows = rt.size()
        for r in range(rows):
            area_raw = rt_value(rt, "Area", r)
            if area_raw is None:
                continue
            pore_area_mm2 = float(area_raw) * area_to_mm2
            if pore_area_mm2 > largest_area_mm2:
                largest_area_mm2 = pore_area_mm2
                largest_row = r

        if largest_row < 0:
            return "", "", -1, 0.0

        x_val = rt_value(rt, "X", largest_row)
        y_val = rt_value(rt, "Y", largest_row)
        if x_val is None or y_val is None:
            return "", "", largest_row + 1, 0.0

        largest_epd_mm = math.sqrt((largest_area_mm2 * 4.0) / math.pi)
        x_px = calibrated_to_pixel_x(cal, x_val)
        y_px = calibrated_to_pixel_y(cal, y_val)

        # Use the binary segmented mask to identify the largest pore component,
        # then flood-fill that pore yellow on an RGB copy for the report.
        mask_for_fill = Duplicator().run(mask)
        try:
            if mask_for_fill.getBitDepth() != 8:
                IJ.run(mask_for_fill, "8-bit", "")
        except:
            pass
        mask_ip = mask_for_fill.getProcessor()

        display = Duplicator().run(mask)
        display.setTitle(base_safe + "_segmented_mask_largest_pore_highlight")
        IJ.run(display, "RGB Color", "")
        display_ip = display.getProcessor()

        if settings.get("black_background", True):
            foreground_value = 255
        else:
            foreground_value = 0

        seed_x, seed_y = find_nearest_foreground_pixel(mask_ip, x_px, y_px, foreground_value, 25)
        if seed_x is not None and seed_y is not None:
            filled_pixels = flood_fill_component_on_display(mask_ip, display_ip, seed_x, seed_y, foreground_value, get_setting_color(settings, "segmented_largest_fill_color", Color.yellow))

            # Filled highlight only on the segmented image. No outline/cross marker here.
            try:
                display_ip.setColor(get_setting_color(settings, "guide_largest_outline_color", Color.red))
                label_x = min(max(2, x_px + 10), max(2, display.getWidth() - 120))
                label_y = max(14, y_px - 10)
                display_ip.drawString("Largest pore", int(label_x), int(label_y))
            except:
                pass
        else:
            # Fallback if no suitable seed pixel is found.
            draw_solid_dot(display_ip, x_px, y_px, 12, get_setting_color(settings, "segmented_largest_fill_color", Color.yellow))
            try:
                display_ip.setColor(get_setting_color(settings, "guide_largest_outline_color", Color.red))
                label_x = min(max(2, x_px + 16), max(2, display.getWidth() - 120))
                label_y = max(14, y_px - 16)
                display_ip.drawString("Largest pore", int(label_x), int(label_y))
            except:
                pass

        FileSaver(display).saveAsTiff(highlight_tif)
        FileSaver(display).saveAsPng(highlight_png)

        try:
            display.close()
        except:
            pass
        try:
            mask_for_fill.close()
        except:
            pass

    except Exception as e:
        IJ.log("Could not highlight largest pore on segmented image: " + str(e))
        return "", "", -1, 0.0

    return highlight_png, highlight_tif, largest_row + 1, largest_epd_mm



def pore_map_micron_text(mm_value):
    try:
        return threshold_compact_number(float(mm_value) * 1000.0) + " um"
    except:
        return str(mm_value) + " mm"


def draw_pore_map_legend(ip, settings, below_count, high_count):
    try:
        upper_limit = float(settings.get("epd_between_high", 0.005))
        high_limit = float(settings.get("report_pore_map_high_cutoff", 0.025))
        low_radius = int(settings.get("report_pore_map_low_marker_radius", 8))
        high_radius = int(settings.get("report_pore_map_high_marker_radius", 14))
        opacity = float(settings.get("report_pore_map_opacity_percent", 70.0))
        low_color = get_setting_color(settings, "pore_map_low_color", Color.cyan)
        high_color = Color.red

        ip.setColor(Color.white)
        ip.fillRect(8, 8, 620, 88)
        ip.setColor(Color.black)
        ip.drawRect(8, 8, 620, 88)

        draw_solid_dot_alpha(ip, 24, 24, low_radius, low_color, opacity)
        ip.setColor(Color.black)
        ip.drawString("Cleaned low EPD > " + pore_map_micron_text(settings.get("small_epd_cutoff", 0.0)) + " and < " + pore_map_micron_text(upper_limit) + "; count = " + str(below_count), 44, 29)

        draw_solid_dot_alpha(ip, 24, 49, high_radius, high_color, opacity)
        ip.setColor(Color.black)
        ip.drawString("High EPD > " + pore_map_micron_text(high_limit) + "; count = " + str(high_count) + " (always shown)", 44, 54)

        ip.drawString("Delete preset changes low limit only; small/large radii = " + str(low_radius) + "/" + str(high_radius) +
                      " px; opacity = " + threshold_compact_number(opacity) + "%", 18, 80)
    except Exception as e:
        IJ.log("Could not draw pore map legend: " + str(e))


def gray_color(gray_value):
    try:
        g = int(round(float(gray_value)))
    except:
        g = 128
    if g < 0:
        g = 0
    if g > 255:
        g = 255
    return Color(g, g, g)


def draw_all_pore_map_legend(ip, all_count, min_epd_mm, max_epd_mm, settings):
    try:
        ip.setColor(Color.white)
        ip.fillRect(8, 8, 520, 86)
        ip.setColor(Color.black)
        ip.drawRect(8, 8, 520, 86)

        y1 = 28
        y2 = 52
        y3 = 76

        min_rad = int(settings.get("report_all_pore_map_min_radius_px", 2))
        style = str(settings.get("report_all_pore_map_style", "EPD-sized red markers on white"))

        if style == "EPD-sized grayscale markers":
            gray_min = int(settings.get("report_all_pore_map_gray_min", 60))
            gray_max = int(settings.get("report_all_pore_map_gray_max", 220))
            draw_solid_dot(ip, 24, y1 - 5, max(min_rad, 3), gray_color(gray_min))
            ip.setColor(Color.black)
            ip.drawString("All pores shown; marker diameter scales with EPD and gray level maps EPD.", 44, y1)
            ip.drawString("Gray range: " + str(gray_min) + " to " + str(gray_max) + "; pores plotted = " + str(all_count), 44, y2)
        elif style == "Fixed 6 px red hue by EPD":
            draw_solid_dot(ip, 24, y1 - 5, 3, Color.red)
            ip.setColor(Color.black)
            ip.drawString("All pores shown with fixed 6 px markers; red hue intensity maps EPD.", 44, y1)
            ip.drawString("Pores plotted = " + str(all_count), 44, y2)
        else:
            draw_solid_dot(ip, 24, y1 - 5, max(min_rad, 3), Color.red)
            ip.setColor(Color.black)
            ip.drawString("All pores shown; red marker diameter scales with EPD.", 44, y1)
            ip.drawString("Pores plotted = " + str(all_count) + "; red markers on a white background.", 44, y2)

        ip.drawString("EPD range in map: " + format_docx_number(min_epd_mm, 6) + " to " + format_docx_number(max_epd_mm, 6) + " mm", 18, y3)
    except Exception as e:
        IJ.log("Could not draw all-pore map legend: " + str(e))



def duplicate_pore_map_background(original_imp, mask, settings, title_text):
    """Create the selected pore-map background; original image is the default."""
    background_mode = str(settings.get("report_pore_map_background", "Original image"))
    source_imp = mask
    if background_mode == "Original image" and original_imp is not None:
        source_imp = original_imp

    pore_map = Duplicator().run(source_imp)
    pore_map.setTitle(str(title_text))
    IJ.run(pore_map, "RGB Color", "")

    if background_mode == "White background":
        try:
            ip = pore_map.getProcessor()
            ip.setColor(Color.white)
            ip.fillRect(0, 0, pore_map.getWidth(), pore_map.getHeight())
        except:
            pass

    return pore_map




def no_lossless_report_images_enabled(settings):
    try:
        return bool(settings.get("no_lossless_images_at_all", False) or settings.get("no_lossless_images_in_reports", False))
    except:
        return False


def no_lossless_generated_images_enabled(settings):
    try:
        return bool(settings.get("no_lossless_images_at_all", False) or settings.get("dont_save_lossless_generated_images", False))
    except:
        return False


def convert_image_file_to_jpeg(source_path, target_path):
    """Convert a saved visualization to JPEG, with ImageJ fallback for TIFFs."""
    if source_path in [None, ""] or target_path in [None, ""]:
        return ""
    source_file = File(str(source_path))
    if not source_file.exists() or not source_file.isFile():
        return ""
    parent = os.path.dirname(str(target_path))
    if parent not in [None, ""]:
        ensure_dir(parent)
    # Never trust a JPEG left from an earlier interrupted/reused output folder.
    # Remove it first so successful verification always refers to this conversion.
    try:
        if os.path.isfile(str(target_path)):
            os.remove(str(target_path))
    except:
        pass

    # Fast Java ImageIO path for PNG/JPEG-compatible sources. Alpha is flattened
    # onto white so annotations do not gain a black background in JPEG.
    try:
        image = ImageIO.read(source_file)
        if image is not None and image.getWidth() > 0 and image.getHeight() > 0:
            rgb = BufferedImage(int(image.getWidth()), int(image.getHeight()), BufferedImage.TYPE_INT_RGB)
            graphics = rgb.createGraphics()
            try:
                graphics.setColor(Color.white)
                graphics.fillRect(0, 0, int(image.getWidth()), int(image.getHeight()))
                graphics.drawImage(image, 0, 0, None)
            finally:
                graphics.dispose()
            wrote = bool(ImageIO.write(rgb, "jpg", File(str(target_path))))
            if wrote:
                out_file = File(str(target_path))
                if out_file.exists() and out_file.length() > 64:
                    return str(target_path)
    except Exception as e_imgio_jpeg:
        IJ.log("ImageIO JPEG conversion fallback needed for " + str(source_path) + ": " + str(e_imgio_jpeg))

    # Fiji/ImageJ can open generated TIFFs that the JVM ImageIO plugins may not.
    # Use ImageJ's JPEG writer as a compatibility fallback.
    fallback_imp = None
    try:
        fallback_imp = IJ.openImage(str(source_path))
        if fallback_imp is None:
            return ""
        try:
            if fallback_imp.getBitDepth() != 24:
                IJ.run(fallback_imp, "RGB Color", "")
        except:
            pass
        IJ.saveAs(fallback_imp, "Jpeg", str(target_path))
        out_file = File(str(target_path))
        if out_file.exists() and out_file.length() > 64:
            return str(target_path)
    except Exception as e_imagej_jpeg:
        IJ.log("ImageJ JPEG conversion failed for " + str(source_path) + ": " + str(e_imagej_jpeg))
    finally:
        try:
            if fallback_imp is not None:
                fallback_imp.changes = False
                fallback_imp.close()
        except:
            pass
    return ""


def cleanup_temp_report_jpegs(paths, temp_dir):
    for path in paths:
        try:
            if path not in [None, ""] and os.path.isfile(str(path)):
                os.remove(str(path))
        except:
            pass
    try:
        if temp_dir not in [None, ""] and os.path.isdir(str(temp_dir)):
            os.rmdir(str(temp_dir))
    except:
        pass


def replace_paths_recursively(value, replacements):
    try:
        if isinstance(value, dict):
            for key in list(value.keys()):
                value[key] = replace_paths_recursively(value[key], replacements)
            return value
        if isinstance(value, list):
            for i in range(len(value)):
                value[i] = replace_paths_recursively(value[i], replacements)
            return value
        if isinstance(value, tuple):
            return tuple([replace_paths_recursively(v, replacements) for v in value])
        text = str(value)
        if text in replacements:
            return replacements[text]
    except:
        pass
    return value


def apply_generated_image_storage_policy(results, settings):
    """Replace generated run PNG/TIFF visual files with JPEG after reports/exports finish.

    Calibrated input/capture/Scaled image/crop TIFFs live outside per-run Images/Histograms
    folders and are intentionally excluded. Lossless files are only removed after a
    replacement JPEG is verified.
    """
    stats = {"enabled": False, "jpeg_created": 0, "lossless_removed": 0, "failed": 0}
    if not no_lossless_generated_images_enabled(settings):
        return stats
    stats["enabled"] = True
    folders = []
    for run in results:
        for key in ["image_dir", "hist_dir"]:
            folder = str(run.get(key, "") or "").strip()
            if folder != "" and os.path.isdir(folder) and folder not in folders:
                folders.append(folder)

    replacements = {}
    for folder in folders:
        try:
            names = list(os.listdir(folder))
        except:
            names = []
        stems = {}
        for name in names:
            low = str(name).lower()
            if not (low.endswith(".png") or low.endswith(".tif") or low.endswith(".tiff")):
                continue
            full = os.path.join(folder, name)
            stem = os.path.splitext(name)[0]
            stems.setdefault(stem, []).append(full)

        for stem in stems.keys():
            source_files = stems[stem]
            png_source = ""
            tif_source = ""
            for source in source_files:
                low = str(source).lower()
                if low.endswith(".png"):
                    png_source = source
                elif tif_source == "" and (low.endswith(".tif") or low.endswith(".tiff")):
                    tif_source = source
            source_for_jpeg = png_source if png_source != "" else tif_source
            jpeg_path = os.path.join(folder, stem + ".jpg")
            converted = convert_image_file_to_jpeg(source_for_jpeg, jpeg_path)
            if converted == "":
                stats["failed"] += 1
                continue
            stats["jpeg_created"] += 1
            for source in source_files:
                replacements[str(source)] = str(converted)
                try:
                    os.remove(source)
                    stats["lossless_removed"] += 1
                except Exception as e_remove:
                    IJ.log("Could not remove lossless generated image " + str(source) + ": " + str(e_remove))

    for run in results:
        replace_paths_recursively(run, replacements)

    IJ.log("Lossless generated-image cleanup: JPEG created=" + str(stats["jpeg_created"]) +
           "; PNG/TIFF removed=" + str(stats["lossless_removed"]) +
           "; conversion failures=" + str(stats["failed"]))
    return stats


def saved_image_file_ready(path, require_decodable_png=False):
    try:
        if path in [None, ""]:
            return False
        f = File(str(path))
        if not f.exists() or not f.isFile() or f.length() <= 64:
            return False
        if require_decodable_png:
            image = ImageIO.read(f)
            if image is None or image.getWidth() <= 0 or image.getHeight() <= 0:
                return False
        return True
    except:
        return False


def save_pore_map_files_verified(imp, png_path, tif_path, label_text):
    """Save both pore-map formats and verify them before returning paths."""
    try:
        parent = os.path.dirname(str(png_path))
        if parent not in [None, ""]:
            File(parent).mkdirs()
    except:
        pass

    png_ok = saved_image_file_ready(png_path, True)
    tif_ok = saved_image_file_ready(tif_path, False)

    for attempt in range(1, 5):
        try:
            saver = FileSaver(imp)
            if not tif_ok:
                saver.saveAsTiff(str(tif_path))
            if not png_ok:
                saver.saveAsPng(str(png_path))
        except Exception as e_save:
            IJ.log(str(label_text) + " save attempt " + str(attempt) + " raised: " + str(e_save))

        tif_ok = saved_image_file_ready(tif_path, False)
        png_ok = saved_image_file_ready(png_path, True)
        if png_ok and tif_ok:
            break

        IJ.log(str(label_text) + " save verification retry " + str(attempt) +
               ": PNG=" + str(png_ok) + "; TIFF=" + str(tif_ok))
        try:
            time.sleep(0.20 * attempt)
        except:
            pass

    final_png = str(png_path) if png_ok else ""
    final_tif = str(tif_path) if tif_ok else ""
    if final_png == "":
        IJ.log(str(label_text) + " PNG was not created after verified retries: " + str(png_path))
    else:
        IJ.log(str(label_text) + " PNG verified: " + str(final_png))
    if final_tif == "":
        IJ.log(str(label_text) + " TIFF was not created after verified retries: " + str(tif_path))
    else:
        IJ.log(str(label_text) + " TIFF verified: " + str(final_tif))
    return final_png, final_tif


def recover_report_png_from_tif(png_path, tif_path, label_text):
    """Recover a missing report PNG from its verified TIFF counterpart."""
    if saved_image_file_ready(png_path, True):
        return str(png_path)
    if not saved_image_file_ready(tif_path, False):
        return ""

    recovery_imp = None
    try:
        recovery_imp = IJ.openImage(str(tif_path))
        if recovery_imp is None:
            return ""
        for attempt in range(1, 4):
            try:
                FileSaver(recovery_imp).saveAsPng(str(png_path))
            except Exception as e_recover:
                IJ.log(str(label_text) + " PNG recovery attempt " + str(attempt) + " raised: " + str(e_recover))
            if saved_image_file_ready(png_path, True):
                IJ.log(str(label_text) + " PNG recovered from TIFF for report: " + str(png_path))
                return str(png_path)
            try:
                time.sleep(0.20 * attempt)
            except:
                pass
    except Exception as e:
        IJ.log(str(label_text) + " PNG recovery failed: " + str(e))
    finally:
        try:
            if recovery_imp is not None:
                recovery_imp.close()
        except:
            pass
    return ""

def cleaned_pore_rows_for_maps(rt, cal, area_to_mm2, settings):
    """
    Return only pore rows present in the cleaned dataset.

    This uses the same strict rule as All Pore Data:
        EPD > small_epd_cutoff
    """
    cleaned_rows = []
    delete_cutoff = float(settings.get("small_epd_cutoff", 0.0))
    rows = rt.size()

    for r in range(rows):
        area_raw = rt_value(rt, "Area", r)
        x_val = rt_value(rt, "X", r)
        y_val = rt_value(rt, "Y", r)

        if area_raw is None or x_val is None or y_val is None:
            continue

        pore_area_mm2 = float(area_raw) * area_to_mm2
        if pore_area_mm2 <= 0:
            continue

        epd_mm = math.sqrt((pore_area_mm2 * 4.0) / math.pi)
        if epd_mm <= delete_cutoff:
            continue

        x_px = calibrated_to_pixel_x(cal, x_val)
        y_px = calibrated_to_pixel_y(cal, y_val)
        cleaned_rows.append((r, x_px, y_px, epd_mm, pore_area_mm2))

    return cleaned_rows


def make_pore_map(original_imp, mask, rt, cal, area_to_mm2, settings, image_dir, base_safe):
    if not run_image_outputs_enabled(settings):
        return "", "", 0, 0, 0

    pore_map_png = os.path.join(image_dir, base_safe + "_pore_map.png")
    pore_map_tif = os.path.join(image_dir, base_safe + "_pore_map.tif")

    delete_cutoff = float(settings.get("small_epd_cutoff", 0.0))
    low_upper_limit = float(settings.get("epd_between_high", 0.005))
    high_lower_limit = float(settings.get("report_pore_map_high_cutoff", 0.025))
    low_marker_radius = int(settings.get("report_pore_map_low_marker_radius", 8))
    high_marker_radius = int(settings.get("report_pore_map_high_marker_radius", 14))
    opacity = float(settings.get("report_pore_map_opacity_percent", 70.0))
    low_color = get_setting_color(settings, "pore_map_low_color", Color.cyan)
    high_color = Color.red
    below_count = 0
    high_count = 0

    try:
        pore_map = duplicate_pore_map_background(original_imp, mask, settings, base_safe + "_pore_map")
        ip = pore_map.getProcessor()

        # Both low and high markers come from the same cleaned population used
        # by All Pore Data: EPD must be strictly greater than the cutoff.
        cleaned_rows = cleaned_pore_rows_for_maps(rt, cal, area_to_mm2, settings)
        for source_row, x_px, y_px, epd, pore_area_mm2 in cleaned_rows:
            if epd > high_lower_limit:
                high_count = high_count + 1
                draw_solid_dot_alpha(ip, x_px, y_px, high_marker_radius, high_color, opacity)
            elif epd < low_upper_limit:
                below_count = below_count + 1
                draw_solid_dot_alpha(ip, x_px, y_px, low_marker_radius, low_color, opacity)

        if settings.get("report_pore_map_show_legend", True):
            draw_pore_map_legend(ip, settings, below_count, high_count)

        pore_map_png, pore_map_tif = save_pore_map_files_verified(
            pore_map, pore_map_png, pore_map_tif, "Cleaned-data pore map"
        )

        try:
            pore_map.close()
        except:
            pass

    except Exception as e:
        IJ.log("Could not make cleaned-data pore map: " + str(e))
        pore_map_png = ""
        pore_map_tif = ""
        try:
            pore_map.close()
        except:
            pass

    return pore_map_png, pore_map_tif, below_count, high_count, 0


def make_all_pore_map(original_imp, mask, rt, cal, area_to_mm2, settings, image_dir, base_safe):
    if not run_image_outputs_enabled(settings):
        return "", "", 0, 0.0, 0.0
    all_pore_map_png = os.path.join(image_dir, base_safe + "_all_pore_map.png")
    all_pore_map_tif = os.path.join(image_dir, base_safe + "_all_pore_map.tif")

    if not settings.get("report_all_pore_map_enabled", False):
        return "", "", 0, 0.0, 0.0

    delete_cutoff = float(settings["small_epd_cutoff"])
    gray_min = int(settings.get("report_all_pore_map_gray_min", 60))
    gray_max = int(settings.get("report_all_pore_map_gray_max", 220))
    min_radius_px = int(settings.get("report_all_pore_map_min_radius_px", 2))
    if min_radius_px < 1:
        min_radius_px = 1
    style = str(settings.get("report_all_pore_map_style", "EPD-sized red markers on white"))

    all_count = 0
    epd_values = []
    pore_rows = []

    try:
        cleaned_rows = cleaned_pore_rows_for_maps(rt, cal, area_to_mm2, settings)
        for source_row, x_px, y_px, epd_mm, pore_area_mm2 in cleaned_rows:
            pore_rows.append((x_px, y_px, epd_mm))
            epd_values.append(epd_mm)

        if len(pore_rows) <= 0:
            return all_pore_map_png, all_pore_map_tif, 0, 0.0, 0.0

        min_epd = min(epd_values)
        max_epd = max(epd_values)

        pore_map = duplicate_pore_map_background(original_imp, mask, settings, base_safe + "_all_pore_map")
        ip = pore_map.getProcessor()

        # White background is used for the red-marker styles. Grayscale style keeps the current look.
        if style in ["EPD-sized red markers on white", "Fixed 6 px red hue by EPD"]:
            try:
                ip.setColor(Color.white)
                ip.fillRect(0, 0, pore_map.getWidth(), pore_map.getHeight())
            except:
                pass

        for x_px, y_px, epd_mm in pore_rows:
            if max_epd > min_epd:
                norm = (epd_mm - min_epd) / (max_epd - min_epd)
            else:
                norm = 0.5

            if style == "EPD-sized grayscale markers":
                gray_value = gray_max - (norm * (gray_max - gray_min))
                radius_px = epd_mm_to_marker_radius_px(epd_mm, cal, unit_to_mm_factor(cal.getUnit()), min_radius_px)
                fill_color = gray_color(gray_value)
            elif style == "Fixed 6 px red hue by EPD":
                radius_px = 6
                fill_color = red_hue_color(norm)
            else:
                radius_px = epd_mm_to_marker_radius_px(epd_mm, cal, unit_to_mm_factor(cal.getUnit()), min_radius_px)
                fill_color = Color.red

            draw_filled_circle_with_outline(ip, x_px, y_px, radius_px, fill_color, Color.black)
            all_count += 1

        if settings.get("report_all_pore_map_show_legend", True):
            draw_all_pore_map_legend(ip, all_count, min_epd, max_epd, settings)

        all_pore_map_png, all_pore_map_tif = save_pore_map_files_verified(
            pore_map, all_pore_map_png, all_pore_map_tif, "All-pore map"
        )

        try:
            pore_map.close()
        except:
            pass

        return all_pore_map_png, all_pore_map_tif, all_count, min_epd, max_epd

    except Exception as e:
        IJ.log("Could not make all-pore map: " + str(e))
        all_pore_map_png = ""
        all_pore_map_tif = ""
        try:
            pore_map.close()
        except:
            pass

    return all_pore_map_png, all_pore_map_tif, all_count, 0.0, 0.0


def read_csv_rows(path):
    rows = []
    if not path_exists(path):
        return rows
    try:
        f = open(path, "r")
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
        f.close()
    except Exception as e:
        IJ.log("Could not read CSV: " + str(path) + " / " + str(e))
    return rows


def read_jmp_summary_for_report(path):
    out = []
    rows = read_csv_rows(path)
    if len(rows) < 2:
        return out

    header = rows[0]
    metric_i = 0
    value_i = 1
    for i in range(len(header)):
        h = str(header[i]).strip().lower()
        if h == "metric":
            metric_i = i
        if h == "value":
            value_i = i

    for r in rows[1:]:
        if len(r) > max(metric_i, value_i):
            metric = r[metric_i]
            value = r[value_i]
            if str(metric).strip() != "":
                out.append([metric, value])
    return out


def zip_writestr(zos, name, text):
    entry = ZipEntry(name)
    zos.putNextEntry(entry)
    data = text.encode("utf-8")
    zos.write(data, 0, len(data))
    zos.closeEntry()


def zip_writefile(zos, name, path):
    entry = ZipEntry(name)
    zos.putNextEntry(entry)
    fis = FileInputStream(path)
    try:
        buf = zeros(8192, 'b')
        while True:
            n = fis.read(buf)
            if n == -1:
                break
            zos.write(buf, 0, n)
    finally:
        fis.close()
    zos.closeEntry()


def docx_run(text, bold=False, italic=False, size=None):
    rpr = ""
    if bold or italic or size is not None:
        rpr = "<w:rPr>"
        if bold:
            rpr += "<w:b/>"
        if italic:
            rpr += "<w:i/>"
        if size is not None:
            rpr += '<w:sz w:val="' + str(int(size)) + '"/>'
        rpr += "</w:rPr>"
    return '<w:r>' + rpr + '<w:t xml:space="preserve">' + xml_escape(text) + '</w:t></w:r>'


def docx_para(text="", bold=False, italic=False, size=None, align=None):
    ppr = ""
    if align is not None and str(align).strip() != "":
        ppr = '<w:pPr><w:jc w:val="' + str(align) + '"/></w:pPr>'
    return "<w:p>" + ppr + docx_run(text, bold, italic, size) + "</w:p>"


def docx_page_break():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def docx_landscape_section_break(settings=None):
    # End the current body section and let the document-final sectPr make the following
    # complete-summary section use its own page size. Use ONE next-page section break
    # paragraph only; the old two-paragraph section break could create a random blank page in Word.
    return docx_body_section_break(settings)

def docx_fragment_is_break(fragment):
    s = str(fragment)
    return ('w:br w:type="page"' in s) or ('<w:sectPr>' in s) or ('<w:sectPr ' in s)

def append_docx_page_break(body):
    if body is None or len(body) == 0:
        return
    if docx_fragment_is_break(body[-1]):
        return
    body.append(docx_page_break())

def append_docx_section_break(body, settings=None):
    if body is None or len(body) == 0:
        return
    if docx_fragment_is_break(body[-1]):
        return
    body.append(docx_landscape_section_break(settings))



DOCX_REPORT_DECIMALS = 9

def format_docx_number(value, decimals):
    # DOCX decimals now means maximum displayed decimals.
    # Values are rounded to that many decimals, then trailing zeros are removed.
    try:
        d = int(decimals)
    except:
        d = 9
    if d < 0:
        d = 9

    try:
        f = float(str(value).replace(",", ""))
    except:
        return str(value)

    out = ("%." + str(d) + "f") % f

    if "." in out:
        out = out.rstrip("0").rstrip(".")

    if out == "-0":
        out = "0"

    return out


def clean_report_table_cell(value):
    # Format numeric DOCX report table values using the configured DOCX decimal places.
    # This only affects the Word report display. CSV and JMP files use their own settings.
    if value is None:
        return ""

    s = str(value).strip()
    if s == "":
        return s

    lower = s.lower()
    if lower in ["nan", "inf", "infinity", "-inf", "-infinity"]:
        return s

    allowed = "0123456789+-.eE,"
    for ch in s:
        if ch not in allowed:
            return s

    try:
        f = float(s.replace(",", ""))
    except:
        return s

    return format_docx_number(f, DOCX_REPORT_DECIMALS)

def docx_table(rows, table_font_size=None):
    # Highlight EPD summary columns everywhere this generic table builder sees them.
    epd_column_fills = {}
    if rows is not None and len(rows) > 0 and rows[0] is not None:
        for header_index in range(len(rows[0])):
            header_text = str(rows[0][header_index]).strip().lower()
            if header_text in ["average epd (mm)", "mean epd (mm)"]:
                epd_column_fills[header_index] = "EAF2F8"
            elif header_text == "max epd (mm)":
                epd_column_fills[header_index] = "FFF2CC"

    xml = '<w:tbl><w:tblPr><w:tblBorders>'
    xml += '<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    xml += '<w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    xml += '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    xml += '<w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    xml += '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    xml += '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    xml += '</w:tblBorders></w:tblPr>'

    for ri in range(len(rows)):
        xml += '<w:tr>'
        row = rows[ri]
        if row is None or len(row) == 0:
            row = [""]
        for ci in range(len(row)):
            is_header = (ri == 0)
            xml += '<w:tc><w:tcPr><w:tcW w:w="5000" w:type="dxa"/>'
            if ci in epd_column_fills:
                xml += '<w:shd w:val="clear" w:color="auto" w:fill="' + epd_column_fills[ci] + '"/>'
            xml += '</w:tcPr>'
            xml += docx_para(clean_report_table_cell(row[ci]), bold=is_header, size=table_font_size)
            xml += '</w:tc>'
        xml += '</w:tr>'
    xml += '</w:tbl>'
    return xml


def docx_compact_three_image_table(items, image_width_in, image_id_start):
    # items = [(caption, rel_id, image_path), ...]
    # Three side-by-side images keep the run pages compact while preserving the original PNG binaries.
    cell_width = 3600
    xml = '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblLayout w:type="fixed"/>'
    xml += '<w:tblBorders>'
    xml += '<w:top w:val="single" w:sz="4" w:space="0" w:color="D0D0D0"/>'
    xml += '<w:left w:val="single" w:sz="4" w:space="0" w:color="D0D0D0"/>'
    xml += '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="D0D0D0"/>'
    xml += '<w:right w:val="single" w:sz="4" w:space="0" w:color="D0D0D0"/>'
    xml += '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="D0D0D0"/>'
    xml += '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="D0D0D0"/>'
    xml += '</w:tblBorders></w:tblPr>'

    xml += '<w:tr>'
    for i in range(3):
        caption = ""
        if i < len(items):
            caption = items[i][0]
        xml += '<w:tc><w:tcPr><w:tcW w:w="' + str(cell_width) + '" w:type="dxa"/></w:tcPr>'
        xml += docx_para(caption, bold=True, size=18, align="center")
        xml += '</w:tc>'
    xml += '</w:tr>'

    xml += '<w:tr>'
    for i in range(3):
        xml += '<w:tc><w:tcPr><w:tcW w:w="' + str(cell_width) + '" w:type="dxa"/></w:tcPr>'
        if i < len(items):
            caption, rel_id, image_path = items[i]
            if rel_id is not None and str(rel_id).strip() != "":
                xml += docx_image(rel_id, image_path, image_width_in, image_id_start + i)
            else:
                xml += docx_para("Missing", size=16, align="center")
        else:
            # Word requires every table cell to contain at least one block-level element.
            # Empty cells on the last sweep/batch comparison row can corrupt the DOCX.
            xml += docx_para("", size=16, align="center")
        xml += '</w:tc>'
    xml += '</w:tr>'

    xml += '</w:tbl>'
    return xml


def docx_image(rel_id, img_name, width_in, image_id):
    width_px, height_px = read_image_size(img_name)
    if width_px <= 0 or height_px <= 0:
        width_px = 1000
        height_px = 750
    cx = int(float(width_in) * EMU_PER_INCH)
    cy = int(cx * (float(height_px) / float(width_px)))

    xml = '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
    xml += '<wp:inline distT="0" distB="0" distL="0" distR="0">'
    xml += '<wp:extent cx="' + str(cx) + '" cy="' + str(cy) + '"/>'
    xml += '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
    xml += '<wp:docPr id="' + str(image_id) + '" name="Picture ' + str(image_id) + '"/>'
    xml += '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
    xml += '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
    xml += '<pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="' + xml_escape(os.path.basename(str(img_name))) + '"/><pic:cNvPicPr/></pic:nvPicPr>'
    xml += '<pic:blipFill><a:blip r:embed="' + rel_id + '"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
    xml += '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="' + str(cx) + '" cy="' + str(cy) + '"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
    xml += '</pic:pic></a:graphicData></a:graphic>'
    xml += '</wp:inline></w:drawing></w:r></w:p>'
    return xml


def image_ext_for_docx(path):
    low = str(path).lower()
    if low.endswith(".jpg") or low.endswith(".jpeg"):
        return "jpeg"
    return "png"


def build_process_steps_for_report(run):
    steps = []
    n = 1
    for s in run.get("step_notes", []):
        steps.append(str(n) + ". " + str(s))
        n = n + 1
    steps.append(str(n) + ". Threshold = " + threshold_range_with_percent(
        run.get("threshold_min", ""),
        run.get("threshold_max", ""),
        run.get("threshold_force_8bit_numbers", True)
    ) + " (inclusive pixel mask)")
    n = n + 1
    if run.get("large_pore_repair_enabled", False):
        steps.append(
            str(n) + ". Conservative large-pore repair before Analyze Particles: " +
            str(run.get("large_pore_repair_accepted_count", 0)) + " accepted; " +
            str(run.get("large_pore_repair_largest_rescue_accepted_count", 0)) + " from v193 aggressive/forced largest-pore search; " +
            str(run.get("large_pore_repair_green_target_accepted_count", 0)) + " from recursive green-target search; " +
            str(run.get("large_pore_repair_green_spur_accepted_count", 0)) + " tiny-spur cuts; " +
            str(run.get("large_pore_repair_repaired_pixels", 0)) + " pixels changed to black; mode=" +
            str(run.get("large_pore_repair_mode_used", run.get("large_pore_repair_mode", "")))
        )
        n = n + 1
    steps.append(str(n) + ". Count and remove pores at or below " + format_micron_label(run["small_epd_cutoff"]))
    n = n + 1
    steps.append(str(n) + ". JMP delete-cutoff preset: " + str(run.get("epd_between_preset", "Custom")) +
                 "; count and calculate percent from " + str(run.get("epd_between_low", "")) +
                 " mm to below " + str(run.get("epd_between_high", "")) + " mm")
    n = n + 1
    steps.append(str(n) + ". Compile data")
    return steps


def report_run_title(index, run, total_runs=1):
    # Use the image name as the primary run title.
    # Add Run # only when needed for batch/sweep reports.
    try:
        image_name = os.path.basename(str(run.get("image_path", "")))
        if image_name is None or str(image_name).strip() == "":
            image_name = str(run.get("base_safe", "Image"))
    except:
        image_name = "Image"

    label = str(image_name)

    run_label = ""
    try:
        run_label = str(run.get("run_label", ""))
    except:
        run_label = ""

    needs_run_number = False
    try:
        if int(total_runs) > 1:
            needs_run_number = True
    except:
        needs_run_number = False

    if run_label not in ["", "None", "normal"]:
        needs_run_number = True

    if needs_run_number:
        extra = "Run #" + str(index)
        if run_label not in ["", "None", "normal"]:
            extra = extra + " - " + run_label
        label = label + " (" + extra + ")"

    return label


def collect_report_images_and_rels(results, settings=None, report_temp_dir=None):
    media = []
    rels = []
    # Jython 2 does not support nonlocal, so use lists for mutable counters.
    counter = [1]
    # v201: reuse one DOCX relationship for repeated references to the same source file.
    # This is especially important for the one-per-OG pre-segmentation heat map shared by sweep runs.
    source_rel_cache = {}

    def add(path):
        if not path_exists(path):
            return ""
        original_media_path = str(path)
        try:
            cache_key = os.path.normcase(os.path.abspath(original_media_path))
        except:
            cache_key = original_media_path
        if cache_key in source_rel_cache:
            return source_rel_cache[cache_key]
        media_path = original_media_path
        if settings is not None and no_lossless_report_images_enabled(settings):
            low = media_path.lower()
            if not (low.endswith(".jpg") or low.endswith(".jpeg")):
                if report_temp_dir in [None, ""]:
                    return ""
                ensure_dir(report_temp_dir)
                temp_jpg = os.path.join(str(report_temp_dir), "docx_image_" + str(counter[0]) + ".jpg")
                converted = convert_image_file_to_jpeg(media_path, temp_jpg)
                if converted != "":
                    media_path = converted
                else:
                    IJ.log("WARNING: lossy report conversion failed; using original image for this media item: " + str(path))
        ext = image_ext_for_docx(media_path)
        media_name = "image" + str(counter[0]) + "." + ext
        rel_id = "rId" + str(counter[0])
        media.append((media_name, media_path))
        rels.append((rel_id, "media/" + media_name))
        source_rel_cache[cache_key] = rel_id
        counter[0] = counter[0] + 1
        return rel_id

    for run in results:
        run["rel_original"] = add(run.get("starting_png", ""))
        run["rel_crop_overview"] = add(run.get("crop_overview_png", ""))
        run["rel_segmented"] = add(run.get("segmented_png", ""))
        run["rel_outlines"] = add(run.get("outlines_png", ""))
        run["rel_hist_epd"] = add(run.get("hist_epd_png", ""))
        run["rel_hist_round"] = add(run.get("hist_round_png", ""))
        run["rel_hist_circ"] = add(run.get("hist_circ_png", ""))

        run["pore_map_png"] = recover_report_png_from_tif(
            run.get("pore_map_png", ""),
            run.get("pore_map_tif", ""),
            "Cleaned-data pore map"
        )
        run["all_pore_map_png"] = recover_report_png_from_tif(
            run.get("all_pore_map_png", ""),
            run.get("all_pore_map_tif", ""),
            "All-pore map"
        )
        run["rel_pore_map"] = add(run.get("pore_map_png", ""))
        run["rel_all_pore_map"] = add(run.get("all_pore_map_png", ""))
        run["rel_manual_largest_pore"] = add(run.get("manual_largest_pore_circled_png", ""))
        run["rel_manual_selected_pore"] = add(run.get("manual_selected_pore_png", ""))
        run["rel_manual_combined_guide"] = add(run.get("manual_combined_guide_png", ""))
        run["rel_segmented_selected"] = add(run.get("segmented_selected_png", ""))
        run["rel_segmented_overlay"] = ""
        run["rel_manual_strand"] = add(run.get("manual_strand_png", ""))
        run["rel_strand_heat_map"] = add(run.get("strand_heat_map_png", ""))

    return media, rels



def threshold_range_for_run(run):
    selected_text = threshold_range_with_percent(
        run.get("threshold_min", ""),
        run.get("threshold_max", ""),
        run.get("threshold_force_8bit_numbers", True)
    )
    min_gray = run.get("threshold_min_gray", "")
    max_gray = run.get("threshold_max_gray", "")
    min_percent = run.get("threshold_min_percent", "")
    max_percent = run.get("threshold_max_percent", "")
    actual_parts = []
    if min_gray not in [None, ""] and max_gray not in [None, ""]:
        actual_parts.append("actual gray " + ("%.2f" % float(min_gray)) + " to " + ("%.2f" % float(max_gray)))
    if min_percent not in [None, ""] and max_percent not in [None, ""]:
        actual_parts.append("cumulative histogram " + ("%.2f" % float(min_percent)) + "% to " + ("%.2f" % float(max_percent)) + "%")
    if len(actual_parts) > 0:
        return selected_text + "; " + "; ".join(actual_parts)
    return selected_text


def report_parameter_columns_for_run(run):
    """
    Return the compact fields used by the combined Word/legacy summary.

    Intentionally omitted from this summary:
      Run label; ImageJ/JMP status fields; selected-unit threshold min/max;
      include holes; exclude edges; auto-fit status; binary enabled/fill/watershed;
      histogram percent inside threshold; EPD-between high; pore-map background;
      and pore-map opacity.
    """
    cols = []
    cols.append(("OG image name", str(run.get("og_image_name", run.get("image_name", "")))))
    cols.append(("Scale set using", str(run.get("report_scale_method", "Needle scale"))))
    cols.append(("Imaging software", str(run.get("report_imaging_software", "Swift Imaging 3.0"))))
    if str(run.get("swift_magn_profile_name", "")).strip() != "":
        cols.append(("Swift magnification profile", str(run.get("swift_magn_profile_name", ""))))
        cols.append(("Swift Resolution (pixels per meter, px/m)", str(run.get("swift_magn_resolution_pixels_per_meter", ""))))
        cols.append(("Applied pixel size (um/pixel)", str(run.get("swift_magn_um_per_pixel", ""))))

    mean_8bit = run.get("original_8bit_mean_gray", "")
    if mean_8bit in [None, ""]:
        mean_8bit_text = ""
    else:
        try:
            mean_8bit_text = "%.6f" % float(mean_8bit)
        except:
            mean_8bit_text = str(mean_8bit)
    cols.append(("Original 8-bit mean gray value before processing (0-255)", mean_8bit_text))

    threshold_gray_mode = run.get("threshold_force_8bit_numbers", True)
    threshold_min_gray = run.get("threshold_min_gray", "")
    threshold_max_gray = run.get("threshold_max_gray", "")
    threshold_min_percent = run.get("threshold_min_percent", "")
    threshold_max_percent = run.get("threshold_max_percent", "")

    cols.append(("Threshold input mode", threshold_input_mode_label(threshold_gray_mode)))
    cols.append(("Threshold min (8-bit gray)", "" if threshold_min_gray in [None, ""] else ("%.2f" % float(threshold_min_gray))))
    cols.append(("Threshold max (8-bit gray)", "" if threshold_max_gray in [None, ""] else ("%.2f" % float(threshold_max_gray))))
    cols.append(("Threshold min cumulative histogram (%)", "" if threshold_min_percent in [None, ""] else ("%.2f" % float(threshold_min_percent))))
    cols.append(("Threshold max cumulative histogram (%)", "" if threshold_max_percent in [None, ""] else ("%.2f" % float(threshold_max_percent))))

    cols.append(("Circularity cutoff", str(run.get("circ_cutoff", ""))))
    cols.append(("JMP delete cutoff preset", str(run.get("epd_between_preset", "Custom"))))
    cols.append(("EPD between low (mm)", str(run.get("epd_between_low", ""))))
    cols.append(("Pore map low count", str(run.get("pore_map_low_count", 0))))
    cols.append(("Pore map fixed >25 um count", str(run.get("pore_map_high_count", 0))))

    if run.get("large_pore_repair_enabled", False):
        cols.append(("Large pore repair mode", str(run.get("large_pore_repair_mode_used", run.get("large_pore_repair_mode", "")))))
        cols.append(("Large pore repairs accepted", str(run.get("large_pore_repair_accepted_count", 0))))
        cols.append(("v193 aggressive/forced largest-pore repairs", str(run.get("large_pore_repair_largest_rescue_accepted_count", 0))))
        cols.append(("v193 green-target recursive repairs", str(run.get("large_pore_repair_green_target_accepted_count", 0))))
        cols.append(("v193 tiny-spur repairs", str(run.get("large_pore_repair_green_spur_accepted_count", 0))))
        cols.append(("Large pore repaired pixels", str(run.get("large_pore_repair_repaired_pixels", 0))))

    if run.get("median_enabled", False):
        cols.append(("Median radius (px)", str(run.get("median_radius", ""))))

    if run.get("bandpass_enabled", False):
        cols.append(("Bandpass large (px)", str(run.get("bandpass_large", ""))))
        cols.append(("Bandpass small (px)", str(run.get("bandpass_small", ""))))

    if run.get("clahe_enabled", False):
        cols.append(("CLAHE block size (px)", str(run.get("clahe_blocksize", ""))))
        cols.append(("CLAHE max slope", str(run.get("clahe_maximum", ""))))

    # These fields are candidates only. build_combined_summary_table_rows()
    # includes them only when the operation is active and its value varies.
    cols.append(("Binary despeckle iterations", str(run.get("binary_despeckle_iterations", 0))))
    cols.append(("Binary open iterations", str(run.get("binary_open_iterations", 0))))
    cols.append(("Binary close iterations", str(run.get("binary_close_iterations", 0))))
    cols.append(("Binary erode iterations", str(run.get("binary_erode_iterations", 0))))
    cols.append(("Binary dilate iterations", str(run.get("binary_dilate_iterations", 0))))
    cols.append(("Minimum grayscale filter radius (px)", str(run.get("binary_minimum_radius", 0.0))))
    cols.append(("Maximum grayscale filter radius (px)", str(run.get("binary_maximum_radius", 0.0))))
    cols.append(("Binary operation order", str(run.get("binary_operation_order", ""))))

    if run.get("sweep_until_enabled", False):
        cols.append(("Sweep Until metric", str(run.get("sweep_until_metric", ""))))
        cols.append(("Sweep Until condition", str(run.get("sweep_until_operator", ""))))
        cols.append(("Sweep Until target", str(run.get("sweep_until_target_value", ""))))
        cols.append(("Sweep Until actual", str(run.get("sweep_until_actual_value", ""))))
        cols.append(("Sweep Until reached", str(run.get("sweep_until_condition_met", False))))

    return cols


REPORT_DYNAMIC_ACTIVE_PARAMETER_KEYS = {
    "Binary despeckle iterations": ("binary_despeckle_iterations", "number"),
    "Binary open iterations": ("binary_open_iterations", "number"),
    "Binary close iterations": ("binary_close_iterations", "number"),
    "Binary erode iterations": ("binary_erode_iterations", "number"),
    "Binary dilate iterations": ("binary_dilate_iterations", "number"),
    "Minimum grayscale filter radius (px)": ("binary_minimum_radius", "number"),
    "Maximum grayscale filter radius (px)": ("binary_maximum_radius", "number"),
    "Binary operation order": ("binary_operation_order", "order")
}


def normalized_report_compare_value(value):
    try:
        number = float(value)
        return "N:" + ("%.12g" % number)
    except:
        return "T:" + str(value).strip()


def dynamic_report_parameter_labels(results):
    """
    Binary iteration/filter/order columns are useful only when they are both:
      1. active in at least one run, and
      2. changed between runs.
    """
    visible = {}
    for label in REPORT_DYNAMIC_ACTIVE_PARAMETER_KEYS.keys():
        key, value_type = REPORT_DYNAMIC_ACTIVE_PARAMETER_KEYS[label]
        values = []
        active = False

        for run in results:
            value = run.get(key, "")
            values.append(normalized_report_compare_value(value))

            if value_type == "number":
                try:
                    if float(value) > 0.0:
                        active = True
                except:
                    pass
            else:
                order_text = str(value).strip()
                if order_text not in ["", "None", "none"]:
                    try:
                        if bool(run.get("binary_enabled", False)):
                            active = True
                    except:
                        active = True

        if active and len(set(values)) > 1:
            visible[label] = True

    return visible


def pretty_summary_metric_name(metric):
    s = str(metric)

    replacements = {
        "epd(mm)": "EPD (mm)",
        "Count epd(mm)": "Count EPD (mm)",
        "Average epd(mm)": "Average EPD (mm)",
        "Max epd(mm)": "Max EPD (mm)",
        "Average circularity": "Average Circularity",
        "Average roundness": "Average Roundness"
    }

    for old in replacements.keys():
        s = s.replace(old, replacements[old])

    return s


def build_combined_summary_table_rows(results):
    metric_order = []
    parameter_order = []
    dynamic_visible = dynamic_report_parameter_labels(results)

    for run in results:
        for label, value in report_parameter_columns_for_run(run):
            if label in REPORT_DYNAMIC_ACTIVE_PARAMETER_KEYS and not dynamic_visible.get(label, False):
                continue
            if label not in parameter_order:
                parameter_order.append(label)

        for sr in run.get("summary_rows_for_report", []):
            if len(sr) >= 2:
                metric = pretty_summary_metric_name(str(sr[0]))
                if metric not in metric_order:
                    metric_order.append(metric)

    # Keep image identity fields first, then all threshold fields.
    identity_parameters = []
    threshold_parameters = []
    other_parameters = []
    for parameter in parameter_order:
        if parameter in [
            "OG image name",
            "Scale set using",
            "Original 8-bit mean gray value before processing (0-255)"
        ]:
            identity_parameters.append(parameter)
        elif str(parameter).startswith("Threshold "):
            threshold_parameters.append(parameter)
        else:
            other_parameters.append(parameter)

    # Average and maximum EPD belong immediately after the threshold columns.
    epd_metrics = []
    for metric in ["Average EPD (mm)", "Max EPD (mm)"]:
        if metric in metric_order:
            epd_metrics.append(metric)

    remaining_metrics = []
    for metric in metric_order:
        if metric not in epd_metrics:
            remaining_metrics.append(metric)

    rows = []
    header = ["Run Order", "Image"]
    header.extend(identity_parameters)
    header.extend(threshold_parameters)
    header.extend(epd_metrics)
    header.extend(other_parameters)
    header.extend(remaining_metrics)
    rows.append(header)

    for i in range(len(results)):
        run = results[i]

        run_map = {}
        for sr in run.get("summary_rows_for_report", []):
            if len(sr) >= 2:
                run_map[pretty_summary_metric_name(str(sr[0]))] = str(sr[1])

        param_map = {}
        for label, value in report_parameter_columns_for_run(run):
            param_map[label] = value

        try:
            image_value = os.path.basename(str(run.get("image_path", run.get("image_name", ""))))
        except:
            image_value = str(run.get("image_name", ""))

        row = [
            run.get("run_order_index", i + 1),
            image_value
        ]

        for parameter in identity_parameters:
            row.append(param_map.get(parameter, ""))

        for parameter in threshold_parameters:
            row.append(param_map.get(parameter, ""))

        for metric in epd_metrics:
            row.append(run_map.get(metric, ""))

        for parameter in other_parameters:
            row.append(param_map.get(parameter, ""))

        for metric in remaining_metrics:
            row.append(run_map.get(metric, ""))

        rows.append(row)

    return rows


def build_manual_largest_pore_comparison_rows(results):
    rows = [[
        "Image",
        "Manual type",
        "Match method",
        "Matched analysis pore ID",
        "Analysis/Table Area (mm^2)",
        "Manual Area (mm^2)",
        "Tracing tool",
        "Manual - Table (mm^2)",
        "% Difference"
    ]]

    for i in range(len(results)):
        run = results[i]

        entries = []

        largest_entries = run.get("manual_largest_pore_entries", [])
        if largest_entries is not None and len(largest_entries) > 0:
            for le in largest_entries:
                entries.append([
                    "Automated largest pore #" + str(le.get("rank", "")),
                    "ranked largest analysis row",
                    le.get("pore_id", ""),
                    le.get("analysis_area_mm2", ""),
                    le.get("manual_area_mm2", ""),
                    le.get("trace_tool", "")
                ])
        else:
            manual_largest_area = run.get("manual_largest_pore_area_mm2", None)
            if manual_largest_area not in [None, ""]:
                entries.append([
                    "Automated largest pore",
                    "automated largest analysis row",
                    run.get("analysis_largest_pore_id", ""),
                    run.get("analysis_largest_pore_area_mm2", ""),
                    manual_largest_area,
                    run.get("manual_largest_pore_trace_tool", "")
                ])

        selected_entries = run.get("manual_selected_pore_entries", [])
        if selected_entries is not None and len(selected_entries) > 0:
            for se in selected_entries:
                entries.append([
                    "User selected pore #" + str(se.get("index", "")),
                    se.get("final_match_method", se.get("match_method", "")),
                    se.get("final_pore_id", se.get("pore_id", "")),
                    se.get("final_table_area_mm2", se.get("table_area_mm2", "")),
                    se.get("manual_area_mm2", ""),
                    se.get("trace_tool", "")
                ])
        else:
            manual_selected_area = run.get("manual_selected_pore_area_mm2", None)
            if manual_selected_area not in [None, ""]:
                entries.append([
                    "User selected pore",
                    run.get("auto_threshold_fit_final_match_method", run.get("manual_selected_match_method", "")),
                    run.get("auto_threshold_fit_result", {}).get("final_pore_id", run.get("manual_selected_pore_id", "")) if run.get("auto_threshold_fit_result", None) is not None else run.get("manual_selected_pore_id", ""),
                    run.get("auto_threshold_fit_final_table_area_mm2", run.get("manual_selected_table_area_mm2", "")),
                    manual_selected_area,
                    run.get("manual_selected_trace_tool", "")
                ])

        for entry in entries:
            manual_type = entry[0]
            match_method = entry[1]
            pore_id = entry[2]
            table_area = entry[3]
            manual_area = entry[4]
            trace_tool = ""
            if len(entry) > 5:
                trace_tool = entry[5]

            diff_text = ""
            pct_text = ""

            try:
                manual_f = float(manual_area)
                table_f = float(table_area)
                diff = manual_f - table_f
                diff_text = str(diff)
                if table_f != 0:
                    pct_text = str((diff / table_f) * 100.0)
            except:
                pass

            rows.append([
                report_run_title(i + 1, run, len(results)),
                manual_type,
                match_method,
                pore_id,
                table_area,
                manual_area,
                trace_tool,
                diff_text,
                pct_text
            ])

    return rows


def add_sweep_comparison_section(body, results, settings):
    try:
        if not settings.get("report_sweep_comparison_enabled", False):
            return
        if len(results) <= 1:
            return

        items = []
        for i in range(len(results)):
            run = results[i]
            rel = run.get("rel_segmented_selected", "")
            path = run.get("segmented_selected_png", "")
            if rel == "":
                rel = run.get("rel_segmented", "")
                path = run.get("segmented_png", "")

            if rel == "":
                continue

            caption = report_run_title(i + 1, run, len(results))
            items.append((caption, rel, path))

        # Do not create a page break or blank comparison page if no comparison images exist.
        if len(items) == 0:
            return

        append_docx_page_break(body)
        body.append(docx_para("Sweep / Batch Image Comparison:", bold=True, size=22))

        chunk = []
        image_id = 7000
        for item in items:
            chunk.append(item)
            if len(chunk) == 3:
                body.append(docx_compact_three_image_table(chunk, settings["report_main_image_width_in"], image_id))
                image_id = image_id + 10
                chunk = []

        if len(chunk) > 0:
            body.append(docx_compact_three_image_table(chunk, settings["report_main_image_width_in"], image_id))
    except Exception as e:
        body.append(docx_para("Could not create sweep comparison section: " + str(e), italic=True, size=18))



def compact_report_name_number(value):
    try:
        f = float(value)
        if abs(f - round(f)) < 0.000000001:
            return str(int(round(f)))
        return ("%.4f" % f).rstrip("0").rstrip(".")
    except:
        return safe_name(str(value))


def report_run_identity_suffix(run, index_value):
    try:
        image_stem = os.path.splitext(os.path.basename(str(run.get("image_name", run.get("image_path", "Image")))))[0]
    except:
        image_stem = "Image"
    label = str(run.get("run_label", ""))
    if label not in ["", "None", "normal"]:
        suffix = safe_name(label)
    else:
        suffix = safe_name(image_stem)
    if suffix == "":
        suffix = "Run_" + str(index_value)
    return short_safe_name(suffix, 80)


def auto_report_base_name(results, settings):
    source = settings
    if results is not None and len(results) > 0:
        source = results[0]

    image_stem = "GDL_Report"
    try:
        if results is not None and len(results) > 0:
            image_stem = os.path.splitext(os.path.basename(str(results[0].get("image_name", results[0].get("image_path", "GDL_Report")))))[0]
    except:
        image_stem = "GDL_Report"

    tokens = [safe_name(image_stem)]

    try:
        distinct_images = []
        for run in results:
            nm = str(run.get("image_name", run.get("image_path", "")))
            if nm not in distinct_images:
                distinct_images.append(nm)
        if len(distinct_images) > 1:
            tokens.append("Batch" + str(len(distinct_images)))
    except:
        pass

    if source.get("median_enabled", False):
        tokens.append("Median" + compact_report_name_number(source.get("median_radius", "")))
    if source.get("contrast_enabled", False):
        tokens.append("Contrast")
    if source.get("bandpass_enabled", False):
        tokens.append(
            "Bandpass" + compact_report_name_number(source.get("bandpass_large", "")) +
            "-" + compact_report_name_number(source.get("bandpass_small", ""))
        )
    if source.get("clahe_enabled", False):
        tokens.append("CLAHE" + compact_report_name_number(source.get("clahe_blocksize", "")))

    sweep_tokens = []
    if settings.get("sweep_enabled", False):
        if settings.get("sweep_all_listed", False) or settings.get("sweep_threshold_min", False) or settings.get("sweep_threshold_max", False):
            sweep_tokens.append("Threshold")
        if settings.get("sweep_all_listed", False) or settings.get("sweep_contrast_enabled", False):
            sweep_tokens.append("ContrastModes")
        if settings.get("sweep_all_listed", False) or settings.get("sweep_median_radius", False):
            sweep_tokens.append("Median")
        if settings.get("sweep_all_listed", False) or settings.get("sweep_bandpass_large", False) or settings.get("sweep_bandpass_small", False):
            sweep_tokens.append("Bandpass")
        if settings.get("sweep_all_listed", False) or settings.get("sweep_clahe_blocksize", False) or settings.get("sweep_clahe_maximum", False):
            sweep_tokens.append("CLAHE")
        if len(sweep_tokens) == 0:
            sweep_tokens.append("Parameters")
        tokens.append("Sweep" + "-".join(sweep_tokens))
    else:
        threshold_mode_gray = source.get("threshold_force_8bit_numbers", settings.get("threshold_force_8bit_numbers", True))
        threshold_min_value = source.get("threshold_min", settings.get("threshold_min", ""))
        threshold_max_value = source.get("threshold_max", settings.get("threshold_max", ""))
        unit_suffix = "Gray" if threshold_mode_is_gray(threshold_mode_gray) else "Pct"
        tokens.append(
            "Threshold" + compact_report_name_number(threshold_min_value) +
            "-" + compact_report_name_number(threshold_max_value) + unit_suffix
        )

    try:
        if int(settings.get("crop_count", 0)) > 0:
            tokens.append("Crops" + str(int(settings.get("crop_count", 0))))
    except:
        pass

    cleaned = []
    for token in tokens:
        t = safe_name(str(token)).strip("_")
        if t != "":
            cleaned.append(t)
    if len(cleaned) == 0:
        cleaned = ["GDL_Report"]
    return short_safe_name("_".join(cleaned), 180)


def resolve_report_base_name(results, settings):
    existing = str(settings.get("_resolved_report_base_name", "")).strip()
    if existing != "":
        return existing

    default_name = auto_report_base_name(results, settings)
    mode = str(settings.get("report_filename_mode", "Auto name: image + processing steps"))
    chosen = default_name

    if mode == "Ask me for report name after processing":
        try:
            entered = JOptionPane.showInputDialog(
                None,
                "Enter the Word report file name.\n\nThe extension is added automatically.",
                default_name
            )
            if entered is not None and str(entered).strip() != "":
                chosen = str(entered).strip()
        except Exception as e:
            IJ.log("Could not ask for Word report file name; using automatic name: " + str(e))

    low = chosen.lower()
    if low.endswith(".docx"):
        chosen = chosen[:-5]
    elif low.endswith(".xls"):
        chosen = chosen[:-4]
    elif low.endswith(".xlsx"):
        chosen = chosen[:-5]

    chosen = short_safe_name(chosen, 180)
    if chosen == "":
        chosen = default_name
    settings["_resolved_report_base_name"] = chosen
    return chosen


def unique_report_path(path):
    if not path_exists(path):
        return path
    root, ext = os.path.splitext(path)
    index_value = 2
    while index_value < 10000:
        candidate = root + "_" + str(index_value) + ext
        if not path_exists(candidate):
            return candidate
        index_value = index_value + 1
    stamp = SimpleDateFormat("yyyyMMdd_HHmmss").format(Date())
    return root + "_" + stamp + ext
