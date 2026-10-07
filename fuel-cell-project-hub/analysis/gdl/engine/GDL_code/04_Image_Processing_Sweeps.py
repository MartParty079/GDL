# -*- coding: utf-8 -*-
# MODULE 04: Ordered image processing, sweeps, and DOCX primitives


def apply_preferred_scale_to_image(imp, image_path, settings, image_name, step_notes=None, quality_warnings=None):
    """
    Scale priority for every source image, crop source, PNG conversion, and run:
      1. Swift Imaging 3.0 .magn table
      2. Manual direct scale
      3. Existing red-reference-line workflow

    The scale is applied before crops and sweep duplicates are created.
    """
    try:
        _swift_magn_clear_runtime_metadata(settings)
    except:
        pass

    # Rehydrate audit metadata from a previously saved calibrated TIFF/crop.
    try:
        hydrate_swift_magn_metadata_from_image(imp, settings)
    except:
        pass

    try:
        if apply_swift_magn_scale_to_image(
            imp, image_path, settings, image_name, step_notes, quality_warnings
        ):
            return True
    except Exception as e_swift_scale:
        msg_swift = "SWIFT .MAGN SCALE WARNING: " + str(e_swift_scale)
        IJ.log(msg_swift)
        if step_notes is not None:
            step_notes.append(msg_swift)
        if quality_warnings is not None:
            quality_warnings.append(msg_swift)

    try:
        if settings.get("set_scale_direct_enabled", False):
            if apply_direct_scale_to_image(imp, settings, image_name, step_notes):
                return True
    except Exception as e_direct_scale:
        IJ.log("Direct scale fallback failed for " + str(image_name) + ": " + str(e_direct_scale))

    return confirm_and_apply_auto_scale_from_red_line(
        imp, settings, image_name, step_notes, quality_warnings
    )


def run_set_scale_only_mode(images, settings):
    saved = []
    skipped = []

    # If batch set-scale saving to the scaled image folder is enabled, save all calibrated TIFFs in one common folder.
    settings["_set_scale_batch_output_dir"] = ""
    try:
        if settings.get("auto_scale_save_tif_subfolder_enabled", False) and len(images) > 1:
            first_parent = os.path.dirname(str(images[0]))
            parent_name = os.path.basename(first_parent)
            if parent_name == "":
                parent_name = "scaled_batch"
            batch_dir = os.path.join(first_parent, "Scaled image")
            ensure_dir(batch_dir)
            settings["_set_scale_batch_output_dir"] = batch_dir
    except Exception as e_batch_dir:
        IJ.log("Could not prepare common scaled batch folder: " + str(e_batch_dir))
        settings["_set_scale_batch_output_dir"] = ""

    for image_path in images:
        imp = None
        try:
            imp = IJ.openImage(image_path)
            if imp is None:
                skipped.append(str(image_path) + " - could not open")
                continue
            image_name = File(image_path).getName()
            imp.setTitle(short_safe_name(os.path.splitext(image_name)[0], 18) + "_set_scale_only")
            step_notes = []
            scaled = apply_preferred_scale_to_image(
                imp, image_path, settings, image_name, step_notes, []
            )
            if scaled:
                tif_path = save_scaled_tif_next_to_input(imp, image_path, settings, step_notes)
                if tif_path != "":
                    saved.append(tif_path)
                else:
                    skipped.append(str(image_path) + " - scale applied but TIFF save was skipped/failed")
            else:
                skipped.append(str(image_path) + " - no scale applied")
        except Exception as e:
            skipped.append(str(image_path) + " - " + str(e))
        finally:
            try:
                if imp is not None:
                    imp.changes = False
                    imp.close()
            except:
                pass

    msg = "Set scale only complete.\n\nSaved calibrated TIFFs: " + str(len(saved))
    for p in saved[:12]:
        msg += "\n- " + str(p)
    if len(saved) > 12:
        msg += "\n... plus " + str(len(saved) - 12) + " more"
    if len(skipped) > 0:
        msg += "\n\nSkipped/failed: " + str(len(skipped))
        for s in skipped[:12]:
            msg += "\n- " + str(s)
        if len(skipped) > 12:
            msg += "\n... plus " + str(len(skipped) - 12) + " more"
    IJ.log(msg)
    try:
        IJ.showMessage("Set Scale Only", msg)
    except:
        pass


def is_png_image(path):
    try:
        return str(path).lower().endswith(".png")
    except:
        return False


def warn_if_png_images(images):
    try:
        pngs = []
        for p in images:
            if is_png_image(p):
                pngs.append(os.path.basename(str(p)))

        if len(pngs) <= 0:
            return

        msg = "PNG images detected after selection.\n\n"
        msg += "The script will scale each PNG, save calibrated TIFFs in a folder named Scaled image, and run normal analysis from those TIFF files.\n"
        msg += "This keeps the report and saved image names tied to the calibrated TIFF workflow.\n\n"
        msg += "PNG images found:\n"
        max_show = 20
        for i in range(min(len(pngs), max_show)):
            msg += "- " + str(pngs[i]) + "\n"
        if len(pngs) > max_show:
            msg += "... plus " + str(len(pngs) - max_show) + " more\n"

        IJ.showMessage("PNG Scale Workflow", msg)
    except Exception as e:
        IJ.log("Could not show PNG scale workflow warning: " + str(e))


def prepare_png_inputs_for_scaled_analysis(images, settings):
    """
    v89 PNG workflow:
    - After input selection, all PNG images are calibrated and saved as TIFFs inside a common Scaled image folder.
    - The returned image list replaces each PNG path with its calibrated TIFF path, so analysis/crops/reporting run from TIFFs.
    """
    try:
        png_paths = []
        for p in images:
            if is_png_image(p):
                png_paths.append(p)
        if len(png_paths) <= 0:
            return images
    except:
        return images

    out_images = []
    scaled_paths = {}
    skipped = []

    old_batch_dir = str(settings.get("_set_scale_batch_output_dir", ""))
    try:
        first_parent = os.path.dirname(str(png_paths[0]))
        common_dir = os.path.join(first_parent, "Scaled image")
        ensure_dir(common_dir)
        settings["_set_scale_batch_output_dir"] = common_dir
        settings["auto_scale_save_tif_enabled"] = True
        settings["auto_scale_save_tif_subfolder_enabled"] = True
        settings["auto_scale_replace_png_with_tif_enabled"] = False

        for image_path in png_paths:
            imp = None
            try:
                imp = IJ.openImage(image_path)
                if imp is None:
                    skipped.append(str(image_path) + " - could not open")
                    continue
                image_name = File(image_path).getName()
                imp.setTitle(short_safe_name(os.path.splitext(image_name)[0], 18) + "_png_scale_to_tif")
                step_notes = []
                scaled = apply_preferred_scale_to_image(
                    imp, image_path, settings, image_name, step_notes, []
                )
                if scaled:
                    tif_path = save_scaled_tif_next_to_input(imp, image_path, settings, step_notes)
                    if tif_path is not None and str(tif_path).strip() != "":
                        scaled_paths[str(image_path)] = str(tif_path)
                        IJ.log("PNG analysis input replaced with calibrated TIFF: " + str(image_path) + " -> " + str(tif_path))
                    else:
                        skipped.append(str(image_path) + " - scale applied but TIFF save failed")
                else:
                    skipped.append(str(image_path) + " - no scale applied")
            except Exception as e_one:
                skipped.append(str(image_path) + " - " + str(e_one))
            finally:
                try:
                    if imp is not None:
                        imp.changes = False
                        imp.close()
                except:
                    pass

        for p in images:
            out_images.append(scaled_paths.get(str(p), p))

        msg = "PNG-to-TIFF scale preparation complete.\n\n"
        msg += "Scaled TIFFs saved: " + str(len(scaled_paths)) + "\n"
        msg += "Folder: " + str(common_dir) + "\n\n"
        if len(scaled_paths) > 0:
            msg += "Normal analysis will use the calibrated TIFF paths."
        if len(skipped) > 0:
            msg += "\n\nSkipped/failed PNGs: " + str(len(skipped))
            for item in skipped[:12]:
                msg += "\n- " + str(item)
            if len(skipped) > 12:
                msg += "\n... plus " + str(len(skipped) - 12) + " more"
        IJ.log(msg)
        try:
            IJ.showMessage("PNG Scale Preparation", msg)
        except:
            pass
        return out_images

    except Exception as e:
        IJ.log("Could not prepare PNG inputs for scaled analysis: " + str(e))
        return images
    finally:
        try:
            settings["_set_scale_batch_output_dir"] = old_batch_dir
        except:
            pass


def confirm_and_apply_auto_scale_from_red_line(imp, settings, image_name, step_notes=None, quality_warnings=None):
    if imp is None:
        return False

    if not settings.get("auto_scale_unscaled_enabled", False):
        return False

    try:
        cal = imp.getCalibration()
    except:
        cal = None

    if cal is None:
        return False

    if not calibration_unit_is_unscaled(cal):
        return False

    pix_len, comp_pixels, bbox, endpoints, err = detect_red_scale_line_pixels(imp, settings)
    if pix_len <= 0:
        msg = "AUTO SCALE WARNING: red scale line could not be detected for " + str(image_name) + ". " + str(err)
        IJ.log(msg)
        if step_notes is not None:
            step_notes.append(msg)
        if quality_warnings is not None:
            quality_warnings.append(msg)
        try:
            JOptionPane.showMessageDialog(None, msg, "Auto Scale Warning", JOptionPane.WARNING_MESSAGE)
        except:
            pass
        return False

    try:
        known_default = float(settings.get("auto_scale_known_length_mm", 0.5))
    except:
        known_default = 0.5
    if known_default <= 0:
        known_default = 0.5

    blue_bbox, blue_pixels, blue_ocr_text, blue_ocr_mm, blue_read_note = detect_blue_label_region(imp, settings, bbox)
    blue_read_mm = known_default
    if blue_ocr_mm is not None:
        try:
            if float(blue_ocr_mm) >= 0.100 and float(blue_ocr_mm) <= 2.000:
                blue_read_mm = float(blue_ocr_mm)
        except:
            blue_read_mm = known_default

    preview_imp = None
    try:
        preview_imp = show_auto_scale_preview_crop(imp, bbox, endpoints, blue_bbox, settings, image_name)
    except Exception as e_preview:
        IJ.log("Could not open auto-scale preview crop: " + str(e_preview))

    # Show the preview image as its own zoomed ImageJ window.
    # If the orange/blue reader is OFF, first ask only for the real scale distance.
    # Then show a clean summary popup with OK / Change / Cancel.
    pix_len_user = pix_len
    known_mm_user = blue_read_mm
    blue_text_user = str(blue_ocr_text)
    mm_per_pixel = 0.0
    known_mm_final = 0.0

    reader_enabled = False
    try:
        reader_enabled = bool(settings.get("auto_scale_blue_ocr_enabled", False))
    except:
        reader_enabled = False

    if not reader_enabled:
        gd_dist = GenericDialog("Set Scale Distance - " + str(image_name))
        gd_dist.addMessage(
            "The cropped scale preview image is open separately.\n"
            "Inspect the red/orange scale line, then enter the actual line distance.\n\n"
            "Measured red top-edge trace = " + str(pix_len) + " pixels\n"
            "Measurement method = " + str(settings.get("_auto_scale_measurement_method", "")) + "\n"
            "Expected actual distance range: 0.100 to 2.000 mm"
        )
        gd_dist.addNumericField("Actual scale-line distance, mm", float(known_default), 9)
        gd_dist.showDialog()

        if gd_dist.wasCanceled():
            msg_cancel_dist = "AUTO SCALE: user canceled distance entry for " + str(image_name) + ". Image remains unscaled."
            IJ.log(msg_cancel_dist)
            if step_notes is not None:
                step_notes.append(msg_cancel_dist)
            try:
                if preview_imp is not None:
                    preview_imp.changes = False
                    preview_imp.close()
            except:
                pass
            return False

        known_mm_user = gd_dist.getNextNumber()
        if known_mm_user < 0.100 or known_mm_user > 2.000:
            parsed_mm, parsed_note = parse_distance_mm_from_blue_text(str(known_mm_user))
            if parsed_mm is not None and parsed_mm >= 0.100 and parsed_mm <= 2.000:
                known_mm_user = parsed_mm
            else:
                known_mm_user = known_default

    while True:
        if pix_len_user <= 0:
            pix_len_user = pix_len

        if known_mm_user < 0.100 or known_mm_user > 2.000:
            if reader_enabled:
                parsed_mm, parsed_note = parse_distance_mm_from_blue_text(blue_text_user)
            else:
                parsed_mm, parsed_note = parse_distance_mm_from_blue_text(str(known_mm_user))
            if parsed_mm is not None and parsed_mm >= 0.100 and parsed_mm <= 2.000:
                known_mm_user = parsed_mm
            else:
                known_mm_user = known_default

        mm_per_pixel = float(known_mm_user) / float(pix_len_user)
        known_mm_final = float(known_mm_user)
        px_per_mm_confirm = 0.0
        if mm_per_pixel > 0:
            px_per_mm_confirm = 1.0 / float(mm_per_pixel)

        reader_state = "OFF"
        if reader_enabled:
            reader_state = "ON"

        summary_msg = (
            "The cropped scale preview image is open separately.\n"
            "Choose OK to apply this scale, or Change to edit the distance.\n\n"
            "Image: " + str(image_name) + "\n"
            "Measured red top-edge trace: " + str(pix_len_user) + " pixels\n"
            "Measurement method: " + str(settings.get("_auto_scale_measurement_method", "")) + "\n"
            "Pinned red corners: " + str(settings.get("_auto_scale_red_corners", "")) + "\n"
            "Pixel units: pixels\n"
            "Actual distance to use: " + str(known_mm_final) + " mm  (expected 0.100 to 2.000 mm)\n"
            "Calculated scale: " + str(mm_per_pixel) + " mm/pixel\n"
            "Calculated scale: " + str(px_per_mm_confirm) + " pixels/mm\n\n"
            "Reader: " + str(reader_state)
        )

        if reader_enabled:
            summary_msg += (
                "\nOrange/blue reader text: " + str(blue_text_user) +
                "\nReader note: " + str(blue_read_note) +
                "\nOrange/blue bbox: " + str(blue_bbox)
            )
        else:
            summary_msg += "\nDistance was entered manually because the orange/blue reader is OFF."

        summary_msg += (
            "\n\nRed bbox: " + str(bbox) +
            "\nEndpoints: " + str(endpoints)
        )

        options_scale = ["OK / Apply Scale", "Change Values", "Cancel"]
        choice_scale = JOptionPane.showOptionDialog(
            None,
            summary_msg,
            "Set Scale Summary",
            JOptionPane.YES_NO_CANCEL_OPTION,
            JOptionPane.QUESTION_MESSAGE,
            None,
            options_scale,
            options_scale[0]
        )

        if choice_scale == 0:
            break

        if choice_scale == 1:
            gd_change = GenericDialog("Change Set Scale Values - " + str(image_name))
            if reader_enabled:
                gd_change.addMessage(
                    "The cropped preview image should still be open.\n"
                    "Edit the pixel length, OCR text, or actual distance, then click OK.\n"
                    "Scale will be recalculated and shown again."
                )
                gd_change.addNumericField("Measured red top-edge trace length, pixels", float(pix_len_user), 3)
                gd_change.addStringField("Orange/blue reader text attempt; optional", str(blue_text_user), 20)
                gd_change.addNumericField("Actual distance to use, mm; expected 0.100 to 2.000", float(known_mm_user), 9)
                gd_change.showDialog()

                if gd_change.wasCanceled():
                    continue

                pix_len_user = gd_change.getNextNumber()
                try:
                    blue_text_user = gd_change.getNextString()
                except:
                    blue_text_user = str(blue_text_user)
                known_mm_user = gd_change.getNextNumber()
            else:
                gd_change.addMessage(
                    "The cropped preview image should still be open.\n"
                    "Edit only the actual distance, then click OK.\n"
                    "Scale will be recalculated and shown again.\n\n"
                    "Measured red top-edge trace = " + str(pix_len_user) + " pixels"
                )
                gd_change.addNumericField("Actual scale-line distance, mm", float(known_mm_user), 9)
                gd_change.showDialog()

                if gd_change.wasCanceled():
                    continue

                known_mm_user = gd_change.getNextNumber()

            if pix_len_user <= 0:
                pix_len_user = pix_len
            if known_mm_user < 0.100 or known_mm_user > 2.000:
                if reader_enabled:
                    parsed_mm, parsed_note = parse_distance_mm_from_blue_text(blue_text_user)
                else:
                    parsed_mm, parsed_note = parse_distance_mm_from_blue_text(str(known_mm_user))
                if parsed_mm is not None and parsed_mm >= 0.100 and parsed_mm <= 2.000:
                    known_mm_user = parsed_mm
                else:
                    known_mm_user = known_default
            continue

        msg_cancel2 = "AUTO SCALE: user canceled set scale summary for " + str(image_name) + ". Image remains unscaled."
        IJ.log(msg_cancel2)
        if step_notes is not None:
            step_notes.append(msg_cancel2)
        try:
            if preview_imp is not None:
                preview_imp.changes = False
                preview_imp.close()
        except:
            pass
        return False

    if mm_per_pixel <= 0:
        msg_bad = "AUTO SCALE WARNING: calculated scale was invalid for " + str(image_name) + ". Image remains unscaled."
        IJ.log(msg_bad)
        if step_notes is not None:
            step_notes.append(msg_bad)
        if quality_warnings is not None:
            quality_warnings.append(msg_bad)
        try:
            if preview_imp is not None:
                preview_imp.changes = False
                preview_imp.close()
        except:
            pass
        return False

    try:
        cal.pixelWidth = float(mm_per_pixel)
        cal.pixelHeight = float(mm_per_pixel)
        cal.setUnit("mm")
        imp.setCalibration(cal)

        settings["_auto_scale_applied"] = True
        settings["_auto_scale_detected_pixels"] = float(pix_len_user)
        settings["_auto_scale_known_length_mm"] = float(known_mm_final)
        settings["_auto_scale_mm_per_pixel"] = float(mm_per_pixel)
        settings["_auto_scale_pixels_per_mm"] = 1.0 / float(mm_per_pixel)
        settings["_auto_scale_component_pixels"] = int(comp_pixels)
        settings["_auto_scale_bbox"] = str(bbox)
        settings["_auto_scale_endpoints"] = str(endpoints)
        settings["_auto_scale_red_corners"] = str(settings.get("_auto_scale_red_corners", ""))
        settings["_auto_scale_measurement_method"] = str(settings.get("_auto_scale_measurement_method", ""))
        settings["_auto_scale_blue_bbox"] = str(blue_bbox)
        settings["_auto_scale_blue_pixels"] = int(blue_pixels)
        settings["_auto_scale_blue_ocr_text"] = str(blue_text_user)
        settings["_auto_scale_blue_ocr_note"] = str(blue_read_note)

        msg_ok = (
            "AUTO SCALE APPLIED: " + str(image_name) +
            "; red line pixels = " + str(pix_len_user) +
            "; known length mm = " + str(known_mm_final) +
            "; scale = " + str(mm_per_pixel) + " mm/pixel" +
            "; pixels/mm = " + str(1.0 / float(mm_per_pixel))
        )
        IJ.log(msg_ok)
        if step_notes is not None:
            step_notes.append(msg_ok)
        try:
            if preview_imp is not None:
                preview_imp.changes = False
                preview_imp.close()
        except:
            pass
        return True
    except Exception as e4:
        msg_fail = "AUTO SCALE WARNING: could not apply scale for " + str(image_name) + ": " + str(e4)
        IJ.log(msg_fail)
        if step_notes is not None:
            step_notes.append(msg_fail)
        if quality_warnings is not None:
            quality_warnings.append(msg_fail)
        try:
            if preview_imp is not None:
                preview_imp.changes = False
                preview_imp.close()
        except:
            pass
        return False


# ======================================================
# CROP HELPERS
# ======================================================

def clamp_crop_rect(x, y, w, h, image_w, image_h):
    try:
        x = int(round(float(x)))
        y = int(round(float(y)))
        w = int(round(float(w)))
        h = int(round(float(h)))
        image_w = int(image_w)
        image_h = int(image_h)
    except:
        return None

    if x < 0:
        w = w + x
        x = 0
    if y < 0:
        h = h + y
        y = 0
    if x >= image_w:
        x = image_w - 1
    if y >= image_h:
        y = image_h - 1
    if x + w > image_w:
        w = image_w - x
    if y + h > image_h:
        h = image_h - y

    if w < 2 or h < 2:
        return None

    return (x, y, w, h)


def save_crop_from_rect(imp, rect, crop_dir, base_safe, crop_num):
    x, y, w, h = rect
    crop_tif = os.path.join(crop_dir, base_safe + "_crop_" + str(crop_num) + ".tif")
    crop_png = os.path.join(crop_dir, base_safe + "_crop_" + str(crop_num) + ".png")

    crop_imp = None
    try:
        ip = imp.getProcessor()
        ip.setRoi(int(x), int(y), int(w), int(h))
        crop_ip = ip.crop()
        crop_imp = ImagePlus(base_safe + "_crop_" + str(crop_num), crop_ip)

        try:
            cal = imp.getCalibration().copy()
            crop_imp.setCalibration(cal)
        except:
            try:
                crop_imp.setCalibration(imp.getCalibration())
            except:
                pass

        FileSaver(crop_imp).saveAsTiff(crop_tif)
        FileSaver(crop_imp).saveAsPng(crop_png)
        return crop_tif, crop_png
    except Exception as e:
        IJ.log("Could not save crop #" + str(crop_num) + ": " + str(e))
        return "", ""
    finally:
        try:
            if crop_imp is not None:
                crop_imp.changes = False
                crop_imp.close()
        except:
            pass


def auto_crop_rects(image_w, image_h, crop_count):
    rects = []
    try:
        crop_count = int(crop_count)
    except:
        crop_count = 0
    if crop_count <= 0:
        return rects

    cols = int(math.ceil(math.sqrt(float(crop_count))))
    if cols < 1:
        cols = 1
    rows = int(math.ceil(float(crop_count) / float(cols)))
    if rows < 1:
        rows = 1

    idx = 0
    for rr in range(rows):
        for cc in range(cols):
            if idx >= crop_count:
                break
            x0 = int(round((float(cc) / float(cols)) * float(image_w)))
            x1 = int(round((float(cc + 1) / float(cols)) * float(image_w)))
            y0 = int(round((float(rr) / float(rows)) * float(image_h)))
            y1 = int(round((float(rr + 1) / float(rows)) * float(image_h)))
            rect = clamp_crop_rect(x0, y0, x1 - x0, y1 - y0, image_w, image_h)
            if rect is not None:
                rects.append(rect)
            idx = idx + 1
    return rects


def draw_crop_overview(imp, crop_infos, crop_dir, base_safe):
    overview_png = os.path.join(crop_dir, base_safe + "_crop_regions_on_original.png")
    overview_tif = os.path.join(crop_dir, base_safe + "_crop_regions_on_original.tif")

    display = None
    try:
        display = Duplicator().run(imp)
        display.setTitle(base_safe + "_crop_regions_on_original")
        try:
            if display.getBitDepth() != 24:
                IJ.run(display, "RGB Color", "")
        except:
            pass

        ip = display.getProcessor()
        try:
            ip.setLineWidth(4)
        except:
            pass

        for info in crop_infos:
            rect = info.get("rect", None)
            if rect is None:
                continue
            x, y, w, h = rect
            crop_num = info.get("crop_index", "")
            try:
                ip.setColor(Color.yellow)
                ip.drawRect(int(x), int(y), int(w), int(h))
                ip.setColor(Color.black)
                ip.drawString("Crop " + str(crop_num), int(x) + 8, max(16, int(y) + 18))
                ip.setColor(Color.yellow)
                ip.drawString("Crop " + str(crop_num), int(x) + 7, max(15, int(y) + 17))
            except:
                pass

        FileSaver(display).saveAsTiff(overview_tif)
        FileSaver(display).saveAsPng(overview_png)
        return overview_png, overview_tif

    except Exception as e:
        IJ.log("Could not create crop overview image: " + str(e))
        return "", ""
    finally:
        try:
            if display is not None:
                display.changes = False
                display.close()
        except:
            pass


def prompt_crop_options_for_image(image_name, default_count, default_mode):
    try:
        gd = GenericDialog("Crop Options - " + str(image_name))
        gd.addMessage(
            "Choose crop settings for this image.\n\n"
            "Set crop count to 0 to process the full original image without crops."
        )
        gd.addNumericField("Number of crop regions for this image", int(default_count), 0)
        try:
            gd.addChoice("Crop mode", ["Manual select", "Auto cropped grid"], str(default_mode))
        except:
            pass
        gd.showDialog()
        if gd.wasCanceled():
            return int(default_count), str(default_mode)
        count = int(gd.getNextNumber())
        if count < 0:
            count = 0
        try:
            mode = str(gd.getNextChoice())
        except:
            mode = str(default_mode)
        return count, mode
    except Exception as e:
        IJ.log("Could not show per-image crop options dialog: " + str(e))
        return int(default_count), str(default_mode)


def build_crop_input_items(images, output_root, settings):
    crop_count = 0
    try:
        crop_count = int(settings.get("crop_count", 0))
    except:
        crop_count = 0

    if crop_count <= 0:
        items = []
        for img in images:
            items.append({"path": img, "crop_meta": {}})
        return items

    crop_mode = str(settings.get("crop_mode", "Manual select"))
    crop_root = os.path.join(output_root, "Crops")
    ensure_dir(crop_root)

    items_out = []

    for image_path in images:
        imp = None
        try:
            image_file = File(image_path)
            image_name = image_file.getName()
            base_name = os.path.splitext(image_name)[0]
            base_safe = short_safe_name(base_name, 18)
            crop_dir = os.path.join(crop_root, base_safe)
            ensure_dir(crop_dir)

            imp = IJ.openImage(image_path)
            if imp is None:
                IJ.log("Could not open image for cropping: " + str(image_path))
                continue

            imp.setTitle(base_safe + "_crop_source_original")
            image_w = imp.getWidth()
            image_h = imp.getHeight()

            # If the source image is unscaled and has a red reference line, set the mm scale before saving crops.
            # The saved crop images inherit this calibration.
            try:
                did_scale_for_crop_source = apply_preferred_scale_to_image(
                    imp, image_path, settings, image_name, None, None
                )
                if did_scale_for_crop_source:
                    save_scaled_tif_next_to_input(imp, image_path, settings, None)
            except Exception as e_auto_crop_scale:
                IJ.log("Could not run auto-scale before cropping: " + str(e_auto_crop_scale))

            current_crop_count = crop_count
            current_crop_mode = crop_mode

            if settings.get("crop_prompt_each_image", False) and crop_count > 0:
                current_crop_count, current_crop_mode = prompt_crop_options_for_image(image_name, crop_count, crop_mode)

            if current_crop_count <= 0:
                items_out.append({"path": image_path, "crop_meta": {}})
                continue

            crop_infos = []

            if current_crop_mode == "Auto cropped grid":
                rects = auto_crop_rects(image_w, image_h, current_crop_count)
                for i in range(len(rects)):
                    crop_num = i + 1
                    rect = rects[i]
                    crop_tif, crop_png = save_crop_from_rect(imp, rect, crop_dir, base_safe, crop_num)
                    if crop_tif != "":
                        crop_infos.append({
                            "crop_index": crop_num,
                            "crop_total": current_crop_count,
                            "rect": rect,
                            "crop_tif": crop_tif,
                            "crop_png": crop_png
                        })
            else:
                try:
                    imp.show()
                except:
                    pass

                for i in range(current_crop_count):
                    crop_num = i + 1
                    WaitForUserDialog(
                        "Manual Crop " + str(crop_num) + " of " + str(current_crop_count),
                        "Draw a rectangular or square ROI for crop #" + str(crop_num) + " on the open original image.\n\n"
                        "Leave the crop ROI selected, then click OK.\n\n"
                        "The script will crop the ROI bounds and later show all crop regions on the original image in the report."
                    ).show()

                    roi = imp.getRoi()
                    if roi is None:
                        IJ.log("No ROI selected for crop #" + str(crop_num) + ". Skipping this crop.")
                        continue

                    b = roi.getBounds()
                    rect = clamp_crop_rect(b.x, b.y, b.width, b.height, image_w, image_h)
                    if rect is None:
                        IJ.log("Invalid ROI bounds for crop #" + str(crop_num) + ". Skipping this crop.")
                        continue

                    crop_tif, crop_png = save_crop_from_rect(imp, rect, crop_dir, base_safe, crop_num)
                    if crop_tif != "":
                        crop_infos.append({
                            "crop_index": crop_num,
                            "crop_total": current_crop_count,
                            "rect": rect,
                            "crop_tif": crop_tif,
                            "crop_png": crop_png
                        })

            overview_png, overview_tif = draw_crop_overview(imp, crop_infos, crop_dir, base_safe)

            for info in crop_infos:
                rect = info.get("rect", (0, 0, 0, 0))
                x, y, w, h = rect
                crop_label = "Crop " + str(info.get("crop_index", "")) + " of " + str(len(crop_infos))
                crop_region_text = crop_label + ": x=" + str(x) + ", y=" + str(y) + ", width=" + str(w) + ", height=" + str(h) + " px"
                items_out.append({
                    "path": info.get("crop_tif", ""),
                    "crop_meta": {
                        "crop_enabled": True,
                        "crop_mode": current_crop_mode,
                        "crop_source_image": image_path,
                        "crop_source_name": image_name,
                        "crop_index": info.get("crop_index", ""),
                        "crop_total": len(crop_infos),
                        "crop_region_text": crop_region_text,
                        "crop_rect_x": x,
                        "crop_rect_y": y,
                        "crop_rect_w": w,
                        "crop_rect_h": h,
                        "crop_overview_png": overview_png,
                        "crop_overview_tif": overview_tif
                    }
                })

        except Exception as e:
            IJ.log("Could not create crops for image " + str(image_path) + ": " + str(e))
        finally:
            try:
                if imp is not None:
                    imp.changes = False
                    imp.close()
            except:
                pass

    if len(items_out) <= 0:
        IJ.log("Crop count was greater than zero, but no valid crops were created. Falling back to original images.")
        for img in images:
            items_out.append({"path": img, "crop_meta": {}})

    return items_out


# ======================================================
# SWEEP HELPERS
# ======================================================

def numeric_range(start, end, step):
    vals = []

    start = float(start)
    end = float(end)
    step = float(step)

    if step == 0:
        vals.append(start)
        return vals

    # Make step sign match direction
    if end < start and step > 0:
        step = -step
    if end > start and step < 0:
        step = -step

    v = start
    guard = 0
    tolerance = abs(step) / 1000000.0

    if step > 0:
        while v <= end + tolerance and guard < 10000:
            vals.append(v)
            v = v + step
            guard = guard + 1
    else:
        while v >= end - tolerance and guard < 10000:
            vals.append(v)
            v = v + step
            guard = guard + 1

    return vals

def build_sweep_combinations(settings):
    if not settings["sweep_enabled"]:
        return [({}, "normal")]

    sweep_candidates = [
        "threshold_min",
        "threshold_max",
        "contrast_mode",
        "median_radius",
        "bandpass_large",
        "bandpass_small",
        "clahe_blocksize",
        "clahe_maximum",
        "binary_enabled",
        "binary_fill_holes",
        "binary_watershed",
        "binary_despeckle_iterations",
        "binary_open_iterations",
        "binary_close_iterations",
        "binary_erode_iterations",
        "binary_dilate_iterations",
        "binary_minimum_radius",
        "binary_maximum_radius"
    ]

    active = []

    for nm in sweep_candidates:
        if nm == "contrast_mode":
            contrast_modes = selected_contrast_sweep_modes(settings)
            use_it = bool(settings.get("sweep_contrast_enabled", False)) and len(contrast_modes) > 0
            if settings.get("sweep_all_listed", False):
                use_it = len(contrast_modes) > 0
        else:
            use_it = settings.get("sweep_" + nm, False)
            if settings.get("sweep_all_listed", False):
                use_it = True

        # Do not sweep disabled processing features unless sweep_all_listed is checked intentionally.
        # Thresholds are always valid.
        if nm == "median_radius" and not settings.get("median_enabled", False) and not settings.get("sweep_all_listed", False):
            use_it = False
        if nm in ["bandpass_large", "bandpass_small"] and not settings.get("bandpass_enabled", False) and not settings.get("sweep_all_listed", False):
            use_it = False
        if nm in ["clahe_blocksize", "clahe_maximum"] and not settings.get("clahe_enabled", False) and not settings.get("sweep_all_listed", False):
            use_it = False
        # Explicit binary sweeps are valid. Minimum/Maximum are grayscale filter sweeps and do not enable binary cleanup.

        if use_it:
            if nm == "contrast_mode":
                vals = selected_contrast_sweep_modes(settings)
            else:
                vals = numeric_range(
                    settings["sweep_" + nm + "_start"],
                    settings["sweep_" + nm + "_end"],
                    settings["sweep_" + nm + "_step"]
                )
            integer_sweep_names = [
                "clahe_blocksize", "binary_enabled", "binary_fill_holes", "binary_watershed",
                "binary_despeckle_iterations", "binary_open_iterations", "binary_close_iterations",
                "binary_erode_iterations", "binary_dilate_iterations"
            ]
            if nm in integer_sweep_names:
                vals = [int(round(v)) for v in vals]
            if nm in ["binary_enabled", "binary_fill_holes", "binary_watershed"]:
                vals = [1 if int(v) != 0 else 0 for v in vals]
            active.append((nm, vals))

    if len(active) == 0:
        return [({}, "normal")]

    total = 1
    for nm, vals in active:
        total = total * len(vals)

    if total > int(settings["max_sweep_runs"]):
        raise Exception("Sweep would create " + str(total) + " runs, which is above max_sweep_runs = " + str(settings["max_sweep_runs"]) + ". Increase the limit or reduce ranges.")

    combos = []

    def recurse(idx, current):
        if idx >= len(active):
            parts = []
            for k in sorted(current.keys()):
                parts.append(k + "_" + safe_name(str(current[k])))
            combos.append((dict(current), "sweep_" + "__".join(parts)))
            return

        nm, vals = active[idx]
        for v in vals:
            current[nm] = v
            recurse(idx + 1, current)
        if nm in current:
            del current[nm]

    recurse(0, {})
    return combos

def merged_settings(base_settings, overrides):
    out = dict(base_settings)
    for k in overrides.keys():
        out[k] = overrides[k]
    for bool_key in ["binary_enabled", "binary_fill_holes", "binary_watershed"]:
        if bool_key in overrides:
            out[bool_key] = bool(int(overrides[bool_key]))
    binary_override_present = False
    for k in overrides.keys():
        if str(k).startswith("binary_") and str(k) not in ["binary_enabled", "binary_minimum_radius", "binary_maximum_radius"]:
            binary_override_present = True
            break
    if binary_override_present:
        out["binary_enabled"] = True if "binary_enabled" not in overrides else bool(int(overrides["binary_enabled"]))
    out = apply_pipeline_sweep_overrides(out, overrides)
    return out

# ======================================================
# IMAGE PROCESSING HELPERS
# ======================================================

def parse_process_order(order_text):
    # Legacy compatibility only. New runs use process_pipeline_steps and preserve duplicates.
    raw = str(order_text).replace(";", ",").replace(" ", "")
    return [p for p in raw.split(",") if p in PROCESS_PIPELINE_GRAY_OPERATIONS]


def make_imagej_command_target(imp):
    try:
        WindowManager.setTempCurrentImage(imp)
    except:
        pass
    try:
        win = imp.getWindow()
        if win is not None:
            win.toFront()
    except:
        pass


def run_preprocessing(work, settings, step_notes):
    steps = validate_processing_pipeline_steps(pipeline_steps_from_settings(settings))
    step_notes.append("Preprocessing target image title: " + str(work.getTitle()))
    try:
        work.killRoi()
    except:
        pass
    occurrence_counts = {}
    for pipeline_index, step in enumerate(steps):
        token = str(step.get("operation", ""))
        if token == "threshold":
            step_notes.append(ordinal_text(step.get("slot", pipeline_index + 1)) + " Threshold boundary; binary operations continue after mask creation.")
            break
        if token not in PROCESS_PIPELINE_GRAY_OPERATIONS or not bool(step.get("enabled", True)):
            continue
        occurrence_counts[token] = occurrence_counts.get(token, 0) + 1
        occurrence_label = ordinal_text(step.get("slot", pipeline_index + 1)) + " " + pipeline_operation_label(token) + " occurrence " + str(occurrence_counts[token])
        make_imagej_command_target(work)
        if token == "8bit":
            IJ.run(work, "8-bit", "")
            step_notes.append(occurrence_label)
        elif token == "median":
            radius = max(0.0, float(step.get("radius", 2.0)))
            IJ.run(work, "Median...", "radius=" + str(radius))
            step_notes.append(occurrence_label + ": radius=" + str(radius))
        elif token == "contrast":
            opts = "saturated=" + str(step.get("saturated", 0.35))
            if bool(step.get("normalize", True)):
                opts += " normalize"
            if bool(step.get("equalize", True)):
                opts += " equalize"
            IJ.run(work, "Enhance Contrast...", opts)
            step_notes.append(occurrence_label + ": " + opts)
        elif token == "bandpass":
            opts = "filter_large=" + str(step.get("large", 40.0))
            opts += " filter_small=" + str(step.get("small", 3.0))
            opts += " suppress=" + str(step.get("suppress", "None"))
            opts += " tolerance=" + str(step.get("tolerance", 5.0))
            if bool(step.get("autoscale", True)):
                opts += " autoscale"
            if bool(step.get("saturate", False)):
                opts += " saturate"
            IJ.run(work, "Bandpass Filter...", opts)
            step_notes.append(occurrence_label + ": " + opts)
        elif token == "clahe":
            opts = "blocksize=" + str(int(step.get("blocksize", 127)))
            opts += " histogram=" + str(int(step.get("histogram", 256)))
            opts += " maximum=" + str(step.get("maximum", 3.0))
            opts += " mask=*None*"
            if bool(step.get("fast", False)):
                opts += " fast_(less_accurate)"
            IJ.run(work, "Enhance Local Contrast (CLAHE)", opts)
            step_notes.append(occurrence_label + ": " + opts)
        elif token in ["minimum", "maximum"]:
            radius = max(0.0, float(step.get("radius", 1.0)))
            if radius > 0.0:
                IJ.run(work, "Minimum..." if token == "minimum" else "Maximum...", "radius=" + str(radius))
                step_notes.append(occurrence_label + ": radius=" + str(radius))
            else:
                step_notes.append(occurrence_label + ": disabled because radius=0")
        try:
            work.updateAndDraw()
        except:
            pass


def pipeline_signature(settings):
    text = processing_pipeline_summary(settings)
    checksum = 0
    for ch in text:
        checksum = ((checksum * 131) + ord(ch)) % 1000000007
    return str(checksum)


def settings_suffix(settings):
    parts = []
    threshold_prefix = "TGray" if threshold_mode_is_gray(settings.get("threshold_force_8bit_numbers", True)) else "TPct"
    parts.append(threshold_prefix + safe_name(str(settings["threshold_min"])) + "_" + safe_name(str(settings["threshold_max"])))
    parts.append("Pipe" + pipeline_signature(settings))
    return "_".join(parts)

# ======================================================
# REPORT / WORD DOCX HELPERS
# ======================================================

EMU_PER_INCH = 914400
TWIPS_PER_INCH = 1440


def docx_twips_from_inches(value, fallback_inches):
    try:
        v = float(value)
    except:
        v = float(fallback_inches)
    if v <= 0:
        v = float(fallback_inches)
    return int(round(v * TWIPS_PER_INCH))


def docx_section_pr_from_page_size(width_in, height_in, margin_in, next_page):
    w = docx_twips_from_inches(width_in, 8.5)
    h = docx_twips_from_inches(height_in, 11.0)
    m = docx_twips_from_inches(margin_in, 0.5)

    orient_attr = ""
    if w > h:
        orient_attr = ' w:orient="landscape"'

    type_xml = ""
    if next_page:
        type_xml = '<w:type w:val="nextPage"/>'

    return '<w:sectPr>' + type_xml + '<w:pgSz w:w="' + str(w) + '" w:h="' + str(h) + '"' + orient_attr + '/><w:pgMar w:top="' + str(m) + '" w:right="' + str(m) + '" w:bottom="' + str(m) + '" w:left="' + str(m) + '" w:header="' + str(m) + '" w:footer="' + str(m) + '" w:gutter="0"/></w:sectPr>'


def docx_body_section_break(settings):
    if settings is None:
        settings = DEFAULTS
    return '<w:p><w:pPr>' + docx_section_pr_from_page_size(
        settings.get("docx_body_page_width_in", DEFAULTS["docx_body_page_width_in"]),
        settings.get("docx_body_page_height_in", DEFAULTS["docx_body_page_height_in"]),
        settings.get("docx_body_margin_in", DEFAULTS["docx_body_margin_in"]),
        True
    ) + '</w:pPr></w:p>'


def docx_summary_final_section_pr(settings):
    if settings is None:
        settings = DEFAULTS
    return docx_section_pr_from_page_size(
        settings.get("docx_summary_page_width_in", DEFAULTS["docx_summary_page_width_in"]),
        settings.get("docx_summary_page_height_in", DEFAULTS["docx_summary_page_height_in"]),
        settings.get("docx_summary_margin_in", DEFAULTS["docx_summary_margin_in"]),
        False
    )


def xml_escape(value):
    if value is None:
        s = ""
    else:
        s = str(value)

    # Strip characters that are illegal in XML 1.0 and can make Word report
    # "unreadable content" even when the visible text looks normal.
    cleaned = []
    for ch in s:
        o = ord(ch)
        if o == 9 or o == 10 or o == 13 or o >= 32:
            cleaned.append(ch)
    s = "".join(cleaned)

    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    s = s.replace('"', "&quot;")
    return s


def path_exists(path):
    try:
        return path is not None and str(path).strip() != "" and File(path).exists()
    except:
        return False


def read_image_size(path):
    try:
        img = ImageIO.read(File(path))
        if img is None:
            return (0, 0)
        return (img.getWidth(), img.getHeight())
    except:
        return (0, 0)


def image_size_text(imp_original, cal, length_to_mm):
    try:
        w_px = int(imp_original.getWidth())
        h_px = int(imp_original.getHeight())
        unit = str(cal.getUnit())
        unit_norm = unit.lower().strip()

        scale_text = "scale: unscaled / px per mm unavailable"
        try:
            px_w_mm = abs(float(cal.pixelWidth) * float(length_to_mm))
            px_h_mm = abs(float(cal.pixelHeight) * float(length_to_mm))
            if px_w_mm > 0 and px_h_mm > 0 and unit_norm not in ["", "pixel", "pixels", "px"]:
                px_per_mm_x = 1.0 / px_w_mm
                px_per_mm_y = 1.0 / px_h_mm
                if abs(px_per_mm_x - px_per_mm_y) <= max(0.000001, abs(px_per_mm_x) * 0.001):
                    scale_text = "scale: %.6g px/mm" % px_per_mm_x
                else:
                    scale_text = "scale: %.6g x %.6g px/mm" % (px_per_mm_x, px_per_mm_y)
        except:
            scale_text = "scale: unscaled / px per mm unavailable"

        # Compact format keeps the final summary comparison table from becoming too wide,
        # while still listing calibrated dimensions, area, pixel dimensions, and scale for each image.
        if length_to_mm != 1.0 or unit_norm == "mm":
            w_mm = float(w_px) * float(cal.pixelWidth) * float(length_to_mm)
            h_mm = float(h_px) * float(cal.pixelHeight) * float(length_to_mm)
            area_mm2 = w_mm * h_mm
            return ("%.4gx%.4g mm; %.4g mm^2; %dx%d px; %s" % (w_mm, h_mm, area_mm2, w_px, h_px, scale_text))
        else:
            area_px2 = int(w_px) * int(h_px)
            return ("%dx%d px; %d px^2; %s" % (w_px, h_px, area_px2, scale_text))
    except:
        try:
            w_px = int(imp_original.getWidth())
            h_px = int(imp_original.getHeight())
            area_px2 = int(w_px) * int(h_px)
            return ("%dx%d px; %d px^2; scale: unscaled / px per mm unavailable" % (w_px, h_px, area_px2))
        except:
            return "Unknown size; scale: unavailable"


def value_to_microns(mm_value):
    try:
        return float(mm_value) * 1000.0
    except:
        return 0.0


def format_micron_label(mm_value):
    um = value_to_microns(mm_value)
    if abs(um - int(round(um))) < 0.000001:
        return str(int(round(um))) + " microns"
    return ("%.3f microns" % um)


def manual_strand_accept_redo(title, message):
    # Strand workflow intentionally uses only Accept and Redo. Closing the popup means Redo.
    try:
        options = ["Accept", "Redo"]
        choice = JOptionPane.showOptionDialog(
            None,
            str(message),
            str(title),
            JOptionPane.YES_NO_OPTION,
            JOptionPane.QUESTION_MESSAGE,
            None,
            options,
            options[0]
        )
        if choice == 0:
            return "accept"
        return "redo"
    except Exception as e:
        IJ.log("Strand Accept/Redo dialog failed; accepting measurement: " + str(e))
        return "accept"


def manual_measurement_accept_redo_cancel(title, message):
    # Returns: "accept", "redo", or "cancel".
    # Uses real dialog buttons so a bad manual ROI can be remeasured without rerunning the script.
    try:
        options = ["Accept", "Redo", "Cancel"]
        choice = JOptionPane.showOptionDialog(
            None,
            str(message),
            str(title),
            JOptionPane.YES_NO_CANCEL_OPTION,
            JOptionPane.QUESTION_MESSAGE,
            None,
            options,
            options[0]
        )

        if choice == 1:
            return "redo"
        if choice == 2 or choice == JOptionPane.CLOSED_OPTION:
            return "cancel"
        return "accept"
    except Exception as e:
        IJ.log("Custom Accept/Redo/Cancel dialog failed; using fallback confirm dialog: " + str(e))
        try:
            choice2 = JOptionPane.showConfirmDialog(
                None,
                str(message) + "\n\nYes = Redo, No = Accept, Cancel = Cancel",
                str(title),
                JOptionPane.YES_NO_CANCEL_OPTION
            )
            if choice2 == JOptionPane.YES_OPTION:
                return "redo"
            if choice2 == JOptionPane.CANCEL_OPTION or choice2 == JOptionPane.CLOSED_OPTION:
                return "cancel"
            return "accept"
        except Exception as e2:
            IJ.log("Fallback manual measurement dialog failed; accepting measurement: " + str(e2))
            return "accept"



def roi_tool_name(roi):
    # Record the Fiji/ImageJ tracing/selection tool used for manual measurements.
    # Main report labels use practical names: rectangle/square, freehand, line, polygon, etc.
    if roi is None:
        return "None"

    try:
        t = int(roi.getType())
    except:
        t = None

    try:
        type_str = str(roi.getTypeAsString())
    except:
        type_str = ""

    try:
        if t == Roi.RECTANGLE:
            return "Rectangle / square"
        if t == Roi.OVAL:
            return "Oval"
        if t == Roi.POLYGON:
            return "Polygon"
        if t == Roi.FREEROI:
            return "Freehand"
        if t == Roi.TRACED_ROI:
            return "Traced/freehand"
        if t == Roi.LINE:
            return "Line"
        if t == Roi.POLYLINE:
            return "Segmented line"
        if t == Roi.FREELINE:
            return "Freehand line"
        if t == Roi.ANGLE:
            return "Angle line"
        if t == Roi.POINT:
            return "Point"
        if t == Roi.COMPOSITE:
            return "Composite"
    except:
        pass

    if type_str is not None and str(type_str).strip() != "":
        return str(type_str)

    return "Unknown"


def scale_bar_label_text(mm_value):
    try:
        mm = float(mm_value)
    except:
        mm = 0.0
    if mm <= 0:
        return ""

    um = mm * 1000.0
    if um < 1000.0:
        if abs(um - int(round(um))) < 0.000001:
            return str(int(round(um))) + " um"
        return ("%.4g um" % um)

    if abs(mm - int(round(mm))) < 0.000001:
        return str(int(round(mm))) + " mm"
    return ("%.4g mm" % mm)


def round_scale_bar_to_increment(value, increment):
    try:
        value = float(value)
        increment = float(increment)
    except:
        return 0.0
    if value <= 0 or increment <= 0:
        return 0.0
    return math.floor((value / increment) + 0.5) * increment


def auto_fit_scale_bar_length_mm(imp, pixel_w_mm, settings):
    try:
        image_width_mm = float(imp.getWidth()) * float(pixel_w_mm)
    except:
        return 0.0

    try:
        fraction = float(settings.get("report_scale_bar_target_fraction", 0.2))
    except:
        fraction = 0.2
    if fraction <= 0:
        fraction = 0.2

    try:
        increment_mm = float(settings.get("report_scale_bar_round_to_mm", 0.05))
    except:
        increment_mm = 0.05
    if increment_mm <= 0:
        increment_mm = 0.05

    target_mm = image_width_mm * fraction
    rounded_mm = round_scale_bar_to_increment(target_mm, increment_mm)
    if rounded_mm <= 0:
        rounded_mm = target_mm
    return rounded_mm


def add_scale_bar_to_image(imp, cal, length_to_mm, settings):
    if imp is None or not settings.get("report_scale_bar_enabled", False):
        return False

    try:
        pixel_w_mm = float(cal.pixelWidth) * float(length_to_mm)
    except:
        pixel_w_mm = 0.0
    if pixel_w_mm <= 0:
        return False

    auto_fit_enabled = bool(settings.get("report_scale_bar_auto_fit_enabled", False))
    if auto_fit_enabled:
        bar_length_mm = auto_fit_scale_bar_length_mm(imp, pixel_w_mm, settings)
    else:
        try:
            bar_length_mm = float(settings.get("report_scale_bar_length_mm", 0.1))
        except:
            bar_length_mm = 0.1
    if bar_length_mm <= 0:
        return False

    try:
        bar_thickness = int(settings.get("report_scale_bar_thickness_px", 8))
    except:
        bar_thickness = 8
    if bar_thickness < 1:
        bar_thickness = 1

    try:
        margin_px = int(settings.get("report_scale_bar_margin_px", 20))
    except:
        margin_px = 20
    if margin_px < 0:
        margin_px = 0

    w = int(imp.getWidth())
    h = int(imp.getHeight())
    x = max(4, margin_px)
    available_px = w - x - max(4, margin_px)
    if available_px < 1:
        return False

    bar_px = int(round(bar_length_mm / pixel_w_mm))
    if bar_px < 1:
        return False

    # Keep the label physically truthful. If a fixed bar cannot fit, use the
    # largest valid bar that fits and update its physical label accordingly.
    if bar_px > available_px:
        bar_px = available_px
        bar_length_mm = float(bar_px) * pixel_w_mm

    try:
        if imp.getBitDepth() != 24:
            IJ.run(imp, "RGB Color", "")
    except:
        pass

    ip = imp.getProcessor()
    color = get_setting_color(settings, "report_scale_bar_color", Color.white)
    ip.setColor(color)

    y = max(bar_thickness + 4, h - margin_px - bar_thickness)
    try:
        ip.fillRect(x, y, bar_px, bar_thickness)
    except:
        return False

    if settings.get("report_scale_bar_label_enabled", True):
        label = scale_bar_label_text(bar_length_mm)
        if label != "":
            try:
                font_size_px = int(settings.get("report_scale_bar_font_size_px", 18))
            except:
                font_size_px = 18
            if font_size_px < 6:
                font_size_px = 6
            try:
                ip.setFont(Font("SansSerif", Font.BOLD, font_size_px))
            except:
                pass
            text_y = y - max(6, int(round(float(font_size_px) * 0.35)))
            if text_y < font_size_px + 2:
                text_y = y + bar_thickness + font_size_px + 4
            try:
                text_color = get_setting_color(settings, "report_scale_bar_text_color", color)
            except:
                text_color = color
            try:
                outline_color = get_setting_color(settings, "report_scale_bar_text_outline_color", Color.black)
            except:
                outline_color = Color.black
            try:
                if settings.get("report_scale_bar_text_outline_enabled", True):
                    ip.setColor(outline_color)
                    for ox, oy in [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]:
                        ip.drawString(label, int(x) + int(ox), int(text_y) + int(oy))
                ip.setColor(text_color)
                ip.drawString(label, x, text_y)
            except:
                pass

    try:
        settings["_last_scale_bar_length_mm"] = float(bar_length_mm)
        settings["_last_scale_bar_length_px"] = int(bar_px)
        settings["_last_scale_bar_auto_fit"] = bool(auto_fit_enabled)
    except:
        pass

    imp.updateAndDraw()
    return True

def add_scale_bar_to_saved_file(image_path, cal, length_to_mm, settings):
    if image_path is None or str(image_path).strip() == "":
        return False
    if not os.path.exists(image_path):
        return False

    imp = None
    try:
        imp = IJ.openImage(image_path)
        if imp is None:
            return False
        ok = add_scale_bar_to_image(imp, cal, length_to_mm, settings)
        if not ok:
            return False

        lower = str(image_path).lower()
        saver = FileSaver(imp)
        if lower.endswith(".png"):
            saver.saveAsPng(image_path)
        elif lower.endswith(".tif") or lower.endswith(".tiff"):
            saver.saveAsTiff(image_path)
        else:
            saver.saveAsPng(image_path)
        return True
    except Exception as e:
        IJ.log("Could not add scale bar to image " + str(image_path) + ": " + str(e))
        return False
    finally:
        try:
            if imp is not None:
                imp.changes = False
                imp.close()
        except:
            pass


def detect_bad_image_issues(image_path, imp_original, cal, length_to_mm, image_total_area_mm2, particle_count):
    issues = []

    try:
        w_px = int(imp_original.getWidth())
        h_px = int(imp_original.getHeight())
    except:
        w_px = 0
        h_px = 0

    if w_px <= 0 or h_px <= 0:
        issues.append("Image width or height is zero/invalid.")
    elif (w_px * h_px) < 10000:
        issues.append("Image is very small; results may be unreliable.")

    ext = str(os.path.splitext(str(image_path))[1]).lower()
    if ext not in [".tif", ".tiff"]:
        issues.append("Input image is not TIFF. Check that file format/compression are appropriate.")

    unit = ""
    if cal is not None:
        try:
            unit = str(cal.getUnit()).strip().lower()
        except:
            unit = ""

    unit_norm = str(unit).replace("µ", "u").replace("μ", "u").strip().lower()
    if unit_norm in ["", "pixel", "pixels", "px"]:
        issues.append("Image is not scaled in mm: calibration unit is pixel/blank. Set the image scale before trusting mm^2 or EPD(mm) values.")
    elif unit_norm not in ["mm", "millimeter", "millimeters"]:
        issues.append("Image calibration unit is '" + str(unit) + "', not mm. The script will convert recognized units to mm, but verify the scale.")

    try:
        if float(cal.pixelWidth) <= 0 or float(cal.pixelHeight) <= 0:
            issues.append("Pixel calibration width/height is zero or negative.")
    except:
        issues.append("Pixel calibration width/height could not be read.")

    try:
        if float(image_total_area_mm2) <= 0:
            issues.append("Calculated image area is zero or invalid.")
    except:
        issues.append("Calculated image area could not be determined.")

    try:
        if int(particle_count) <= 0:
            issues.append("No pores were detected by Analyze Particles.")
    except:
        issues.append("Particle count could not be determined.")

    status = "PASS"
    if len(issues) > 0:
        status = "CHECK"

    return status, issues


def scale_sanity_issues_for_image(imp_original, cal, length_to_mm, image_total_area_mm2, settings):
    issues = []
    if not settings.get("scale_sanity_warning_enabled", True):
        return issues

    try:
        unit = str(cal.getUnit()).strip()
    except:
        unit = ""
    unit_norm = str(unit).replace("µ", "u").replace("μ", "u").strip().lower()

    if unit_norm in ["", "pixel", "pixels", "px"]:
        issues.append("Scale sanity warning: image is not scaled in mm; calibration unit is pixel/blank.")
    elif unit_norm not in ["mm", "millimeter", "millimeters"]:
        issues.append("Scale sanity warning: calibration unit is '" + str(unit) + "', not mm. Verify conversion to mm.")

    try:
        area_mm2 = float(image_total_area_mm2)
        min_area = float(settings.get("scale_sanity_min_image_area_mm2", 0.000001))
        max_area = float(settings.get("scale_sanity_max_image_area_mm2", 1000.0))
        if area_mm2 > 0 and area_mm2 < min_area:
            issues.append("Scale sanity warning: image area is very small (" + str(area_mm2) + " mm^2; minimum warning limit " + str(min_area) + " mm^2).")
        if area_mm2 > max_area:
            issues.append("Scale sanity warning: image area is very large (" + str(area_mm2) + " mm^2; maximum warning limit " + str(max_area) + " mm^2).")
    except:
        pass

    try:
        px_w_mm = abs(float(cal.pixelWidth) * float(length_to_mm))
        px_h_mm = abs(float(cal.pixelHeight) * float(length_to_mm))
        min_px = float(settings.get("scale_sanity_min_pixel_size_mm", 0.000001))
        max_px = float(settings.get("scale_sanity_max_pixel_size_mm", 1.0))
        if px_w_mm > 0 and px_w_mm < min_px:
            issues.append("Scale sanity warning: pixel width is very small (" + str(px_w_mm) + " mm/pixel; minimum warning limit " + str(min_px) + ").")
        if px_h_mm > 0 and px_h_mm < min_px:
            issues.append("Scale sanity warning: pixel height is very small (" + str(px_h_mm) + " mm/pixel; minimum warning limit " + str(min_px) + ").")
        if px_w_mm > max_px:
            issues.append("Scale sanity warning: pixel width is very large (" + str(px_w_mm) + " mm/pixel; maximum warning limit " + str(max_px) + ").")
        if px_h_mm > max_px:
            issues.append("Scale sanity warning: pixel height is very large (" + str(px_h_mm) + " mm/pixel; maximum warning limit " + str(max_px) + ").")
    except:
        pass

    return issues


def particle_count_limit_issues(particle_count, settings):
    issues = []
    if not settings.get("particle_count_sanity_enabled", True):
        return issues

    try:
        count = int(particle_count)
        limit = int(settings.get("particle_count_high_limit", 5000))
    except:
        return issues

    if limit < 1:
        limit = 5000

    if count > limit:
        issues.append("Particle-count warning: detected " + str(count) + " particles, which is above the warning limit of " + str(limit) + ".")

    return issues


def particle_count_change_issue(before_count, after_count, settings, threshold_before, threshold_after):
    if not settings.get("particle_count_sanity_enabled", True):
        return ""

    try:
        before_count = int(before_count)
        after_count = int(after_count)
        limit = float(settings.get("particle_count_change_warning_percent", 50.0))
    except:
        return ""

    if limit < 0:
        limit = 50.0

    if before_count == after_count:
        return ""

    if before_count <= 0:
        change_percent = 100.0
    else:
        change_percent = (abs(float(after_count) - float(before_count)) / float(before_count)) * 100.0

    if change_percent > limit:
        return (
            "Particle-count warning: threshold max step changed particle count from " +
            str(before_count) + " to " + str(after_count) + " (" +
            format_docx_number(change_percent, 3) + "% change; warning limit " +
            str(limit) + "%). Threshold max " + str(threshold_before) + " -> " + str(threshold_after) + "."
        )

    return ""


def calibrated_to_pixel_x(cal, x_value):
    try:
        return int(round(cal.getRawX(float(x_value))))
    except:
        try:
            return int(round((float(x_value) - cal.xOrigin) / cal.pixelWidth))
        except:
            return int(round(float(x_value)))


def calibrated_to_pixel_y(cal, y_value):
    try:
        return int(round(cal.getRawY(float(y_value))))
    except:
        try:
            return int(round((float(y_value) - cal.yOrigin) / cal.pixelHeight))
        except:
            return int(round(float(y_value)))


def draw_marker(ip, x, y, radius, color):
    try:
        ip.setColor(color)
        d = int(radius) * 2
        ip.drawOval(int(x) - int(radius), int(y) - int(radius), d, d)
        ip.drawLine(int(x) - int(radius), int(y), int(x) + int(radius), int(y))
        ip.drawLine(int(x), int(y) - int(radius), int(x), int(y) + int(radius))
    except:
        pass



def draw_solid_dot(ip, x, y, radius, color):
    try:
        ip.setColor(color)
        d = int(radius) * 2
        ip.fillOval(int(x) - int(radius), int(y) - int(radius), d, d)
    except:
        pass


def draw_solid_dot_alpha(ip, x, y, radius, color, opacity_percent):
    """Blend a filled circular marker onto an RGB ImageProcessor."""
    try:
        opacity = float(opacity_percent) / 100.0
    except:
        opacity = 0.5
    if opacity < 0.0:
        opacity = 0.0
    if opacity > 1.0:
        opacity = 1.0

    try:
        cx = int(round(float(x)))
        cy = int(round(float(y)))
        rad = int(round(float(radius)))
        if rad < 1:
            rad = 1
        w = int(ip.getWidth())
        h = int(ip.getHeight())
        fr = int(color.getRed())
        fg = int(color.getGreen())
        fb = int(color.getBlue())

        y0 = max(0, cy - rad)
        y1 = min(h - 1, cy + rad)
        x0 = max(0, cx - rad)
        x1 = min(w - 1, cx + rad)
        r2 = rad * rad

        for py in range(y0, y1 + 1):
            dy = py - cy
            for px in range(x0, x1 + 1):
                dx = px - cx
                if (dx * dx + dy * dy) > r2:
                    continue
                bg = int(ip.getPixel(px, py))
                br = (bg >> 16) & 255
                bgc = (bg >> 8) & 255
                bb = bg & 255
                nr = int(round((1.0 - opacity) * br + opacity * fr))
                ng = int(round((1.0 - opacity) * bgc + opacity * fg))
                nb = int(round((1.0 - opacity) * bb + opacity * fb))
                ip.putPixel(px, py, (nr << 16) | (ng << 8) | nb)
    except Exception as e:
        IJ.log("Could not draw transparent pore-map marker: " + str(e))



def find_nearest_foreground_pixel(ip, start_x, start_y, foreground_value, max_radius):
    try:
        w = ip.getWidth()
        h = ip.getHeight()
        x0 = int(start_x)
        y0 = int(start_y)
        if x0 < 0:
            x0 = 0
        if y0 < 0:
            y0 = 0
        if x0 >= w:
            x0 = w - 1
        if y0 >= h:
            y0 = h - 1

        if ip.getPixel(x0, y0) == foreground_value:
            return x0, y0

        radius = 1
        while radius <= int(max_radius):
            y_min = max(0, y0 - radius)
            y_max = min(h - 1, y0 + radius)
            x_min = max(0, x0 - radius)
            x_max = min(w - 1, x0 + radius)

            for y in range(y_min, y_max + 1):
                for x in range(x_min, x_max + 1):
                    if ip.getPixel(x, y) == foreground_value:
                        return x, y
            radius = radius + 1
    except:
        pass
    return None, None


def flood_fill_component_on_display(mask_ip, display_ip, seed_x, seed_y, foreground_value, fill_color):
    filled_count = 0
    try:
        w = mask_ip.getWidth()
        h = mask_ip.getHeight()
        sx = int(seed_x)
        sy = int(seed_y)
        if sx < 0 or sy < 0 or sx >= w or sy >= h:
            return 0
        if mask_ip.getPixel(sx, sy) != foreground_value:
            return 0

        visited = set()
        stack = [(sx, sy)]
        display_ip.setColor(fill_color)

        while len(stack) > 0:
            x, y = stack.pop()
            key = (x, y)
            if key in visited:
                continue
            visited.add(key)

            if x < 0 or y < 0 or x >= w or y >= h:
                continue
            if mask_ip.getPixel(x, y) != foreground_value:
                continue

            display_ip.drawPixel(x, y)
            filled_count = filled_count + 1

            stack.append((x - 1, y))
            stack.append((x + 1, y))
            stack.append((x, y - 1))
            stack.append((x, y + 1))
            stack.append((x - 1, y - 1))
            stack.append((x + 1, y - 1))
            stack.append((x - 1, y + 1))
            stack.append((x + 1, y + 1))
    except Exception as e:
        IJ.log("Could not flood fill largest pore component: " + str(e))
    return filled_count





def find_ranked_pore_from_results(rt, cal, area_to_mm2, rank_zero_based):
    ranked = []

    try:
        rows = rt.size()
        for r in range(rows):
            area_raw = rt_value(rt, "Area", r)
            if area_raw is None:
                continue

            pore_area_mm2 = float(area_raw) * area_to_mm2
            if pore_area_mm2 <= 0:
                continue

            x_px = 0
            y_px = 0
            x_val = rt_value(rt, "X", r)
            y_val = rt_value(rt, "Y", r)
            if x_val is not None and y_val is not None:
                x_px = calibrated_to_pixel_x(cal, x_val)
                y_px = calibrated_to_pixel_y(cal, y_val)

            epd_mm = 0.0
            if pore_area_mm2 > 0:
                epd_mm = math.sqrt((pore_area_mm2 * 4.0) / math.pi)

            ranked.append((pore_area_mm2, r, epd_mm, x_px, y_px, float(area_raw)))

        ranked.sort(reverse=True)

        idx = int(rank_zero_based)
        if idx < 0:
            idx = 0
        if idx >= len(ranked):
            return -1, 0.0, 0, 0, 0.0, 0.0

        pore_area_mm2, row_idx, epd_mm, x_px, y_px, area_raw = ranked[idx]
        return row_idx, epd_mm, x_px, y_px, pore_area_mm2, area_raw

    except Exception as e:
        IJ.log("Could not find ranked pore from results: " + str(e))
        return -1, 0.0, 0, 0, 0.0, 0.0


def find_largest_pore_from_results(rt, cal, area_to_mm2):
    return find_ranked_pore_from_results(rt, cal, area_to_mm2, 0)


def make_original_largest_pore_circle_image(imp_original, mask, rt, cal, area_to_mm2, settings, image_dir, base_safe, rank_zero_based=0):
    rank_num = int(rank_zero_based) + 1
    suffix = ""
    if rank_num > 1:
        suffix = "_rank_" + str(rank_num)

    circled_png = os.path.join(image_dir, base_safe + suffix + "_manual_measure_largest_pore_circled_original.png")
    circled_tif = os.path.join(image_dir, base_safe + suffix + "_manual_measure_largest_pore_circled_original.tif")

    largest_row, largest_epd_mm, x_px, y_px, largest_area_mm2, area_raw = find_ranked_pore_from_results(rt, cal, area_to_mm2, rank_zero_based)

    if largest_row < 0:
        return "", "", -1, 0.0, 0.0

    try:
        display = Duplicator().run(imp_original)
        display.setTitle(base_safe + suffix + "_manual_measure_largest_pore_circled_original")

        try:
            if display.getBitDepth() != 24:
                IJ.run(display, "RGB Color", "")
        except:
            pass

        ip = display.getProcessor()

        guide_drawn = False
        try:
            # Draw the ranked largest-pore guide directly from the segmented mask pixels.
            # This avoids the ROI/Wand fallback that was producing a circle.
            guide_drawn = draw_dilated_component_outline_on_ip(
                mask,
                ip,
                x_px,
                y_px,
                settings,
                40,
                settings.get("guide_outline_extra_pixels", 10.0),
                get_setting_color(settings, "guide_largest_outline_color", Color.red),
                settings.get("guide_outline_line_width", 1)
            )

            # Fallback only: ROI Manager offset outline. No circle fallback.
            if not guide_drawn:
                roi_fallback = get_roi_from_manager_by_index(int(largest_row))
                if roi_fallback is not None:
                    offset_roi = make_offset_roi_from_roi(
                        roi_fallback,
                        settings.get("guide_outline_extra_pixels", 10.0)
                    )
                    if offset_roi is not None:
                        guide_drawn = draw_roi_outline(
                            ip,
                            offset_roi,
                            get_setting_color(settings, "guide_largest_outline_color", Color.red),
                            settings.get("guide_outline_line_width", 1)
                        )

            if not guide_drawn:
                IJ.log("Largest-pore guide: no outline was drawn. Circle fallback is disabled.")

        except Exception as e:
            IJ.log("Could not draw ranked largest-pore offset outline guide: " + str(e))
            guide_drawn = False

        # Do not draw a text label on the manual-largest-pore guide.
        # The offset outline alone is used so the label does not cover the pore being measured.

        FileSaver(display).saveAsTiff(circled_tif)
        FileSaver(display).saveAsPng(circled_png)

        try:
            display.show()
        except:
            pass

    except Exception as e:
        IJ.log("Could not create manual ranked largest-pore guide image: " + str(e))
        return "", "", largest_row + 1, largest_epd_mm, largest_area_mm2

    return circled_png, circled_tif, largest_row + 1, largest_epd_mm, largest_area_mm2


def manual_largest_pore_entry_from_circled_image(imp_original, mask, rt, cal, area_to_mm2, settings, image_dir, base_safe, image_name, rank_zero_based=0):
    if not settings.get("manual_largest_pore_enabled", False):
        return None, None, "", "", -1, 0.0, 0.0, "None"

    rank_num = int(rank_zero_based) + 1
    suffix = ""
    if rank_num > 1:
        suffix = "_rank_" + str(rank_num)

    circled_png, circled_tif, analysis_largest_pore_id, analysis_largest_epd_mm, analysis_largest_area_mm2 = make_original_largest_pore_circle_image(
        imp_original, mask, rt, cal, area_to_mm2, settings, image_dir, base_safe, rank_zero_based
    )

    circled_title = base_safe + suffix + "_manual_measure_largest_pore_circled_original"

    while True:
        WaitForUserDialog(
            "Manual Largest Pore Measurement " + str(rank_num),
            "A copy of the unfiltered original image is open with largest pore rank #" + str(rank_num) + " marked using a larger, outward-offset pore-shaped outline.\n\n"
            "Do NOT use Analyze > Measure here.\n\n"
            "Instead:\n"
            "1. Use the freehand/selection tool to outline the pore inside the larger offset marker directly on the open image.\n"
            "2. Leave that ROI selected.\n"
            "3. Click OK here.\n\n"
            "The script will read the selected ROI area automatically.\n\n"
            "If the ROI/area is wrong, click Redo on the next dialog and remeasure."
        ).show()

        manual_area_raw = 0.0
        manual_roi_tool = "None"

        try:
            measure_imp = WindowManager.getImage(circled_title)
            if measure_imp is None:
                measure_imp = WindowManager.getCurrentImage()

            if measure_imp is not None:
                roi = measure_imp.getRoi()
                if roi is not None:
                    manual_roi_tool = roi_tool_name(roi)
                    stats = measure_imp.getStatistics(Measurements.AREA)
                    manual_area_raw = float(stats.area)
                    IJ.log("Manual ROI area read automatically from selected ROI: " + str(manual_area_raw))
                    IJ.log("Manual largest pore tracing tool rank #" + str(rank_num) + ": " + str(manual_roi_tool))
                else:
                    IJ.log("No ROI selected on manual largest-pore image rank #" + str(rank_num) + ".")
        except Exception as e:
            IJ.log("Could not automatically read manual ROI area: " + str(e))
            manual_area_raw = 0.0

        gd_area = GenericDialog("Confirm Manual Largest Pore Area #" + str(rank_num))

        gd_area.addMessage(
            "Manual ROI area was read from the selected outline.\n"
            "You can accept it or type a corrected value.\n\n"
            "Largest pore rank: #" + str(rank_num) + "\n"
            "Analysis pore ID: " + str(analysis_largest_pore_id) + "\n"
            "Analysis pore area: " + str(analysis_largest_area_mm2) + " mm^2\n"
            "Tracing tool used: " + str(manual_roi_tool) + "\n\n"
            "After clicking OK, choose Accept, Redo, or Cancel."
        )
        gd_area.addNumericField("Manual largest pore area #" + str(rank_num), manual_area_raw, 9)

        gd_area.showDialog()

        if gd_area.wasCanceled():
            IJ.log("Manual largest pore entry canceled for: " + str(image_name) + " rank #" + str(rank_num))
            return None, None, circled_png, circled_tif, analysis_largest_pore_id, analysis_largest_epd_mm, analysis_largest_area_mm2, manual_roi_tool

        manual_area_raw = gd_area.getNextNumber()

        if manual_area_raw <= 0:
            decision_bad = manual_measurement_accept_redo_cancel(
                "Invalid Manual Largest Pore Area #" + str(rank_num),
                "The manual largest pore area is zero or invalid.\n\n"
                "Click Redo to reselect/retrace the ROI, or Cancel to skip this measurement."
            )
            if decision_bad == "redo":
                continue
            IJ.log("Invalid manual largest pore area entered for: " + str(image_name) + " rank #" + str(rank_num))
            return None, None, circled_png, circled_tif, analysis_largest_pore_id, analysis_largest_epd_mm, analysis_largest_area_mm2, manual_roi_tool

        manual_area_mm2 = float(manual_area_raw) * area_to_mm2
        manual_epd_mm = math.sqrt((manual_area_mm2 * 4.0) / math.pi)

        decision = manual_measurement_accept_redo_cancel(
            "Use Manual Largest Pore Measurement #" + str(rank_num) + "?",
            "Manual largest pore rank #" + str(rank_num) + " area:\n"
            "Raw ROI area = " + str(manual_area_raw) + "\n"
            "Manual area = " + str(manual_area_mm2) + " mm^2\n"
            "Tracing tool used = " + str(manual_roi_tool) + "\n\n"
            "Analysis pore ID = " + str(analysis_largest_pore_id) + "\n"
            "Analysis area = " + str(analysis_largest_area_mm2) + " mm^2\n\n"
            "Accept this measurement, Redo it, or Cancel/skip it."
        )

        if decision == "redo":
            IJ.log("Redo requested for manual largest pore measurement rank #" + str(rank_num))
            continue
        if decision == "cancel":
            IJ.log("Manual largest pore measurement skipped after redo dialog for: " + str(image_name) + " rank #" + str(rank_num))
            return None, None, circled_png, circled_tif, analysis_largest_pore_id, analysis_largest_epd_mm, analysis_largest_area_mm2, manual_roi_tool

        IJ.log("Manual largest pore for " + str(image_name) + " rank #" + str(rank_num))
        IJ.log("Manual area raw = " + str(manual_area_raw))
        IJ.log("Manual area mm^2 = " + str(manual_area_mm2))
        IJ.log("Manual EPD mm = " + str(manual_epd_mm))
        IJ.log("Manual tracing tool = " + str(manual_roi_tool))

        return manual_area_mm2, manual_epd_mm, circled_png, circled_tif, analysis_largest_pore_id, analysis_largest_epd_mm, analysis_largest_area_mm2, manual_roi_tool


def find_analysis_pore_matching_manual_roi(rt, cal, area_to_mm2, roi, roi_center_x_px, roi_center_y_px, manual_area_raw):
    # Matching method:
    # Only accept an automated particle if its centroid is inside the manual selected ROI.
    # The old nearest-centroid fallback is intentionally removed because it could silently
    # match the wrong pore. If no centroid is inside the selected ROI, the manual selection
    # workflow shows an error and lets the user reselect/retrace the pore.

    best_inside_row = -1
    best_inside_score = None
    best_nearest_dist2 = None
    best_epd_mm = 0.0
    best_area_mm2 = 0.0
    match_method = "no centroid inside manual ROI"

    manual_area_mm2 = 0.0
    try:
        manual_area_mm2 = float(manual_area_raw) * area_to_mm2
    except:
        manual_area_mm2 = 0.0

    if roi is None:
        return -1, 0.0, 0.0, None, "no ROI selected"

    try:
        rows = rt.size()
        for r in range(rows):
            x_val = rt_value(rt, "X", r)
            y_val = rt_value(rt, "Y", r)
            area_raw = rt_value(rt, "Area", r)

            if x_val is None or y_val is None or area_raw is None:
                continue

            x_px = calibrated_to_pixel_x(cal, x_val)
            y_px = calibrated_to_pixel_y(cal, y_val)

            dx = float(x_px) - float(roi_center_x_px)
            dy = float(y_px) - float(roi_center_y_px)
            dist2 = dx * dx + dy * dy
            if best_nearest_dist2 is None or dist2 < best_nearest_dist2:
                best_nearest_dist2 = dist2

            inside = False
            try:
                inside = roi.contains(int(round(x_px)), int(round(y_px)))
            except:
                inside = False

            if inside:
                area_mm2 = float(area_raw) * area_to_mm2

                # Primary score: area agreement.
                # Tiny distance term breaks ties without overpowering area matching.
                if manual_area_mm2 > 0:
                    area_score = abs(area_mm2 - manual_area_mm2) / manual_area_mm2
                else:
                    area_score = 0.0

                score = area_score + (dist2 * 0.000001)

                if best_inside_score is None or score < best_inside_score:
                    best_inside_score = score
                    best_inside_row = r

        if best_inside_row >= 0:
            area_raw_chosen = rt_value(rt, "Area", best_inside_row)
            if area_raw_chosen is not None:
                best_area_mm2 = float(area_raw_chosen) * area_to_mm2
                if best_area_mm2 > 0:
                    best_epd_mm = math.sqrt((best_area_mm2 * 4.0) / math.pi)

            match_method = "centroid inside manual ROI"
            IJ.log("Manual selected pore matched by: " + match_method)
            IJ.log("Matched analysis pore ID: " + str(best_inside_row + 1))
            return best_inside_row, best_epd_mm, best_area_mm2, best_nearest_dist2, match_method

        IJ.log("Manual selected pore match error: no automated centroid was inside the manual ROI.")
        return -1, 0.0, 0.0, best_nearest_dist2, "no centroid inside manual ROI"

    except Exception as e:
        IJ.log("Could not match manual selected pore to analysis row: " + str(e))
        return -1, 0.0, 0.0, best_nearest_dist2, "match error: " + str(e)






def get_component_roi_from_mask(mask, x_px, y_px, settings, search_radius):
    """
    Trace the actual connected component in the segmented mask near x_px/y_px.
    This is used for the largest-pore manual guide so the prompt/report shows
    an offset pore outline instead of falling back to a circle.
    """
    if mask is None:
        return None

    mask_copy = None
    try:
        mask_copy = Duplicator().run(mask)
        try:
            if mask_copy.getBitDepth() != 8:
                IJ.run(mask_copy, "8-bit", "")
        except:
            pass

        mask_ip = mask_copy.getProcessor()

        if settings.get("black_background", True):
            foreground_value = 255
        else:
            foreground_value = 0

        seed_x, seed_y = find_nearest_foreground_pixel(
            mask_ip,
            int(round(x_px)),
            int(round(y_px)),
            foreground_value,
            int(search_radius)
        )

        if seed_x is None or seed_y is None:
            return None

        try:
            from ij.gui import Wand, PolygonRoi, Roi
            wand = Wand(mask_ip)

            try:
                # Trace the component at this exact gray value.
                wand.autoOutline(int(seed_x), int(seed_y), foreground_value, foreground_value)
            except:
                # Fallback for older ImageJ Wand API.
                wand.autoOutline(int(seed_x), int(seed_y))

            if wand.npoints is None or wand.npoints < 3:
                return None

            return PolygonRoi(wand.xpoints, wand.ypoints, wand.npoints, Roi.TRACED_ROI)
        except Exception as e:
            IJ.log("Could not trace largest-pore component outline with Wand: " + str(e))
            return None

    except Exception as e:
        IJ.log("Could not get component ROI from mask: " + str(e))
        return None

    finally:
        try:
            if mask_copy is not None:
                mask_copy.close()
        except:
            pass




def draw_dilated_component_outline_on_ip(mask, display_ip, x_px, y_px, settings, search_radius, dilation_pixels, color, line_width):
    """
    Draw an outward/larger outline for the segmented component nearest x_px/y_px.
    This does NOT use ImageJ ROI Manager or Wand. It works directly from mask pixels:
    - find foreground seed near centroid
    - flood fill that connected component
    - dilate the pixel set outward by dilation_pixels
    - draw the border of the dilated set on display_ip
    """
    if mask is None or display_ip is None:
        return False

    mask_copy = None
    try:
        mask_copy = Duplicator().run(mask)
        try:
            if mask_copy.getBitDepth() != 8:
                IJ.run(mask_copy, "8-bit", "")
        except:
            pass

        mask_ip = mask_copy.getProcessor()
        w = mask_ip.getWidth()
        h = mask_ip.getHeight()

        if settings.get("black_background", True):
            foreground_value = 255
        else:
            foreground_value = 0

        seed_x, seed_y = find_nearest_foreground_pixel(
            mask_ip,
            int(round(x_px)),
            int(round(y_px)),
            foreground_value,
            int(search_radius)
        )

        if seed_x is None or seed_y is None:
            IJ.log("Largest-pore guide: no foreground seed found near largest pore centroid.")
            return False

        # Flood fill the actual component into a set.
        component = set()
        stack = [(int(seed_x), int(seed_y))]

        while len(stack) > 0:
            x, y = stack.pop()
            key = (x, y)

            if key in component:
                continue
            if x < 0 or y < 0 or x >= w or y >= h:
                continue
            if mask_ip.getPixel(x, y) != foreground_value:
                continue

            component.add(key)

            stack.append((x - 1, y))
            stack.append((x + 1, y))
            stack.append((x, y - 1))
            stack.append((x, y + 1))
            stack.append((x - 1, y - 1))
            stack.append((x + 1, y - 1))
            stack.append((x - 1, y + 1))
            stack.append((x + 1, y + 1))

        if len(component) < 3:
            IJ.log("Largest-pore guide: component too small to outline.")
            return False

        # Dilate outward by repeated 8-neighbor expansion.
        dilated = component
        steps = int(round(float(dilation_pixels)))
        if steps < 0:
            steps = 0

        for i in range(steps):
            new_set = set(dilated)
            for (x, y) in dilated:
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        nx = x + dx
                        ny = y + dy
                        if nx >= 0 and ny >= 0 and nx < w and ny < h:
                            new_set.add((nx, ny))
            dilated = new_set

        # Border = dilated pixels with at least one neighbor outside the dilated set.
        border = []
        for (x, y) in dilated:
            edge = False
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx = x + dx
                    ny = y + dy
                    if nx < 0 or ny < 0 or nx >= w or ny >= h or (nx, ny) not in dilated:
                        edge = True
                        break
                if edge:
                    break
            if edge:
                border.append((x, y))

        if len(border) < 3:
            IJ.log("Largest-pore guide: border too small to draw.")
            return False

        display_ip.setColor(color)

        try:
            lw = int(line_width)
        except:
            lw = 1
        if lw < 1:
            lw = 1

        r = int(max(0, math.floor((float(lw) - 1.0) / 2.0)))

        for (x, y) in border:
            if r <= 0:
                display_ip.drawPixel(int(x), int(y))
            else:
                # Small square brush for visible line thickness.
                for yy in range(int(y) - r, int(y) + r + 1):
                    if yy < 0 or yy >= h:
                        continue
                    for xx in range(int(x) - r, int(x) + r + 1):
                        if xx < 0 or xx >= w:
                            continue
                        display_ip.drawPixel(int(xx), int(yy))

        IJ.log("Largest-pore guide: drew direct dilated pixel outline. Component pixels=" + str(len(component)) + ", border pixels=" + str(len(border)) + ", dilation=" + str(steps))
        return True

    except Exception as e:
        IJ.log("Could not draw direct dilated component outline: " + str(e))
        return False

    finally:
        try:
            if mask_copy is not None:
                mask_copy.close()
        except:
            pass


def get_dilated_component_roi_from_mask(mask, x_px, y_px, settings, search_radius, dilation_pixels):
    """
    Build a ROI by:
    1. finding the segmented pore component nearest the analysis centroid,
    2. copying only that component into a blank mask,
    3. dilating the component outward by dilation_pixels,
    4. tracing the outside of the dilated component.

    This guarantees the manual guide outline is larger than the pore.
    """
    if mask is None:
        return None

    mask_copy = None
    component_imp = None

    try:
        mask_copy = Duplicator().run(mask)
        try:
            if mask_copy.getBitDepth() != 8:
                IJ.run(mask_copy, "8-bit", "")
        except:
            pass

        mask_ip = mask_copy.getProcessor()
        w = mask_ip.getWidth()
        h = mask_ip.getHeight()

        if settings.get("black_background", True):
            foreground_value = 255
        else:
            foreground_value = 0

        seed_x, seed_y = find_nearest_foreground_pixel(
            mask_ip,
            int(round(x_px)),
            int(round(y_px)),
            foreground_value,
            int(search_radius)
        )

        if seed_x is None or seed_y is None:
            return None

        component_ip = ByteProcessor(w, h)
        component_ip.setValue(0)
        component_ip.fill()

        sx = int(seed_x)
        sy = int(seed_y)
        stack = [(sx, sy)]
        visited = set()

        while len(stack) > 0:
            x, y = stack.pop()
            key = (x, y)
            if key in visited:
                continue
            visited.add(key)

            if x < 0 or y < 0 or x >= w or y >= h:
                continue

            if mask_ip.getPixel(x, y) != foreground_value:
                continue

            component_ip.putPixel(x, y, 255)

            stack.append((x - 1, y))
            stack.append((x + 1, y))
            stack.append((x, y - 1))
            stack.append((x, y + 1))
            stack.append((x - 1, y - 1))
            stack.append((x + 1, y - 1))
            stack.append((x - 1, y + 1))
            stack.append((x + 1, y + 1))

        # Dilate the isolated pore outward. This is the true offset step.
        dilations = int(round(float(dilation_pixels)))
        if dilations < 0:
            dilations = 0

        for i in range(dilations):
            try:
                component_ip.dilate()
            except:
                break

        component_imp = ImagePlus("largest_pore_dilated_component", component_ip)

        try:
            from ij.gui import Wand, PolygonRoi, Roi
            wand = Wand(component_ip)

            # Use the original seed. Since the component was dilated, this seed
            # remains inside the component.
            try:
                wand.autoOutline(int(seed_x), int(seed_y), 255, 255)
            except:
                wand.autoOutline(int(seed_x), int(seed_y))

            if wand.npoints is None or wand.npoints < 3:
                return None

            return PolygonRoi(wand.xpoints, wand.ypoints, wand.npoints, Roi.TRACED_ROI)

        except Exception as e:
            IJ.log("Could not trace dilated largest-pore component outline: " + str(e))
            return None

    except Exception as e:
        IJ.log("Could not build dilated component ROI from mask: " + str(e))
        return None

    finally:
        try:
            if mask_copy is not None:
                mask_copy.close()
        except:
            pass
        try:
            if component_imp is not None:
                component_imp.close()
        except:
            pass


def get_roi_manager_any():
    try:
        rm = RoiManager.getInstance()
        if rm is not None:
            return rm
    except:
        pass

    try:
        rm = RoiManager.getInstance2()
        if rm is not None:
            return rm
    except:
        pass

    return None


def get_roi_from_manager_by_index(index_zero_based):
    try:
        rm = get_roi_manager_any()
        if rm is None:
            return None

        count = rm.getCount()
        if count <= 0:
            return None

        idx = int(index_zero_based)

        # Best case: Analyze Particles "add" produced ROIs in the same row order as Results.
        if idx >= 0 and idx < count:
            return rm.getRoi(idx)

        return None
    except:
        return None


def make_offset_roi_from_roi(roi, extra_pixels):
    """
    Create an enlarged ROI by scaling the original ROI outward from its centroid.
    The scale factor is chosen so the average radius increases by about extra_pixels.
    This is for display/guide use.
    """
    if roi is None:
        return None

    poly = None
    try:
        poly = roi.getInterpolatedPolygon()
    except:
        try:
            poly = roi.getPolygon()
        except:
            poly = None

    if poly is None:
        return None

    try:
        n = int(poly.npoints)
    except:
        return None

    if n < 3:
        return None

    xs = []
    ys = []
    for i in range(n):
        try:
            xs.append(float(poly.xpoints[i]))
            ys.append(float(poly.ypoints[i]))
        except:
            return None

    cx = sum(xs) / float(len(xs))
    cy = sum(ys) / float(len(ys))

    radii = []
    for i in range(len(xs)):
        dx = xs[i] - cx
        dy = ys[i] - cy
        radii.append(math.sqrt(dx * dx + dy * dy))

    if len(radii) == 0:
        return None

    avg_r = sum(radii) / float(len(radii))
    if avg_r <= 0:
        avg_r = 1.0

    scale = (avg_r + float(extra_pixels)) / avg_r

    from ij.gui import PolygonRoi, Roi
    from jarray import array

    new_x = []
    new_y = []
    for i in range(len(xs)):
        dx = xs[i] - cx
        dy = ys[i] - cy
        new_x.append(cx + dx * scale)
        new_y.append(cy + dy * scale)

    try:
        return PolygonRoi(array(new_x, 'f'), array(new_y, 'f'), len(new_x), Roi.POLYGON)
    except:
        return None


def draw_roi_outline(ip, roi, color, line_width):
    if roi is None:
        return False
    try:
        ip.setColor(color)
        try:
            ip.setLineWidth(int(line_width))
        except:
            pass
        ip.draw(roi)
        return True
    except:
        return False


def make_segmented_highlight_with_selected_pore(mask, rt, cal, area_to_mm2, settings, selected_roi, image_dir, base_safe):
    """
    Build the segmented image used in the report after the selected-pore percent
    difference reaches the auto-fit/redo trigger:
    - automated largest pore filled yellow
    - user-selected pore shown as a green offset outline, not a fill
    """
    out_png = os.path.join(image_dir, base_safe + "_segmented_with_manual_pores.png")
    out_tif = os.path.join(image_dir, base_safe + "_segmented_with_manual_pores.tif")

    if mask is None:
        return "", ""

    try:
        display = Duplicator().run(mask)
        display.setTitle(base_safe + "_segmented_with_manual_pores")
        try:
            IJ.run(display, "RGB Color", "")
        except:
            pass

        mask_for_fill = Duplicator().run(mask)
        try:
            if mask_for_fill.getBitDepth() != 8:
                IJ.run(mask_for_fill, "8-bit", "")
        except:
            pass

        ip = display.getProcessor()
        mask_ip = mask_for_fill.getProcessor()

        if settings.get("black_background", True):
            foreground_value = 255
        else:
            foreground_value = 0

        # Fill the automated largest pore.
        try:
            largest_row, largest_epd_mm, x_px, y_px, largest_area_mm2, area_raw = find_largest_pore_from_results(rt, cal, area_to_mm2)
            if largest_row >= 0:
                seed_x, seed_y = find_nearest_foreground_pixel(mask_ip, x_px, y_px, foreground_value, 25)
                if seed_x is not None and seed_y is not None:
                    flood_fill_component_on_display(mask_ip, ip, seed_x, seed_y, foreground_value, get_setting_color(settings, "segmented_largest_fill_color", Color.yellow))
                else:
                    pass

                try:
                    ip.setColor(get_setting_color(settings, "guide_largest_outline_color", Color.red))
                    label_x = min(max(2, int(x_px) + 14), max(2, display.getWidth() - 160))
                    label_y = max(16, int(y_px) - 12)
                    ip.drawString("Largest pore", int(label_x), int(label_y))
                except:
                    pass
        except Exception as e:
            IJ.log("Could not fill automated largest pore on segmented image: " + str(e))

        # Outline the user-selected pore only when this high-difference guide is created.
        if selected_roi is not None:
            try:
                selected_offset_roi = make_offset_roi_from_roi(selected_roi, settings.get("guide_outline_extra_pixels", 10.0))
                drawn_selected = False
                if selected_offset_roi is not None:
                    drawn_selected = draw_roi_outline(
                        ip,
                        selected_offset_roi,
                        get_setting_color(settings, "guide_selected_outline_color", Color.green),
                        settings.get("guide_outline_line_width", 1)
                    )
                if not drawn_selected:
                    draw_roi_outline(
                        ip,
                        selected_roi,
                        get_setting_color(settings, "guide_selected_outline_color", Color.green),
                        settings.get("guide_outline_line_width", 1)
                    )

                try:
                    b = selected_roi.getBounds()
                    label_x = min(max(2, int(b.x + b.width + 8)), max(2, display.getWidth() - 170))
                    label_y = max(16, int(b.y) - 6)
                    ip.setColor(get_setting_color(settings, "guide_selected_outline_color", Color.green))
                    ip.drawString("Selected pore", label_x, label_y)
                except:
                    pass
            except Exception as e:
                IJ.log("Could not outline selected pore on segmented image: " + str(e))

        FileSaver(display).saveAsTiff(out_tif)
        FileSaver(display).saveAsPng(out_png)

        try:
            display.close()
        except:
            pass
        try:
            mask_for_fill.close()
        except:
            pass

        return out_png, out_tif
    except Exception as e:
        IJ.log("Could not make segmented manual-pore highlight image: " + str(e))
        return "", ""


def add_selected_pore_marker_to_largest_guide(guide_png_path, image_dir, base_safe, roi, settings):
    combined_png = os.path.join(image_dir, base_safe + "_manual_combined_largest_and_selected_markers.png")
    combined_tif = os.path.join(image_dir, base_safe + "_manual_combined_largest_and_selected_markers.tif")

    if guide_png_path is None or str(guide_png_path).strip() == "":
        return "", ""

    if roi is None:
        return "", ""

    try:
        display = IJ.openImage(guide_png_path)
        if display is None:
            return "", ""

        display.setTitle(base_safe + "_manual_combined_largest_and_selected_markers")
        try:
            if display.getBitDepth() != 24:
                IJ.run(display, "RGB Color", "")
        except:
            pass

        ip = display.getProcessor()

        drawn = False

        # Prefer an offset outline for the manually selected pore so it shows location
        # without covering the pore itself.
        try:
            selected_offset_roi = make_offset_roi_from_roi(roi, settings.get("guide_outline_extra_pixels", 10.0))
            if selected_offset_roi is not None:
                drawn = draw_roi_outline(ip, selected_offset_roi, get_setting_color(settings, "guide_selected_outline_color", Color.green), settings.get("guide_outline_line_width", 1))
            if not drawn:
                drawn = draw_roi_outline(ip, roi, get_setting_color(settings, "guide_selected_outline_color", Color.green), settings.get("guide_outline_line_width", 1))
        except:
            drawn = False

        # Fallback to a circle if ROI outline drawing is not possible.
        if not drawn:
            try:
                b = roi.getBounds()
                cx = float(b.x) + float(b.width) / 2.0
                cy = float(b.y) + float(b.height) / 2.0
                selected_radius_px = int(math.ceil(((float(b.width) / 2.0) ** 2 + (float(b.height) / 2.0) ** 2) ** 0.5 + float(settings.get("guide_outline_extra_pixels", 10.0))))
                if selected_radius_px < 18:
                    selected_radius_px = 18

                ip.setColor(get_setting_color(settings, "guide_selected_outline_color", Color.green))
                try:
                    ip.setLineWidth(settings.get("guide_outline_line_width", 1))
                except:
                    pass
                ip.drawOval(int(round(cx)) - selected_radius_px, int(round(cy)) - selected_radius_px, selected_radius_px * 2, selected_radius_px * 2)
            except:
                pass

        try:
            b = roi.getBounds()
            label_x = min(max(2, int(b.x + b.width + 8)), max(2, display.getWidth() - 170))
            label_y = max(16, int(b.y) - 6)
            ip.setColor(get_setting_color(settings, "guide_selected_outline_color", Color.green))
            ip.drawString("Selected pore", label_x, label_y)
        except:
            pass

        FileSaver(display).saveAsTiff(combined_tif)
        FileSaver(display).saveAsPng(combined_png)

        try:
            display.close()
        except:
            pass

        return combined_png, combined_tif

    except Exception as e:
        IJ.log("Could not add selected pore marker to largest-pore guide image: " + str(e))
        return "", ""



def roi_length_mm_from_roi(roi, cal, length_to_mm):
    if roi is None:
        return 0.0

    points_x = []
    points_y = []

    try:
        poly = roi.getFloatPolygon()
        n = int(poly.npoints)
        for i in range(n):
            points_x.append(float(poly.xpoints[i]))
            points_y.append(float(poly.ypoints[i]))
    except:
        try:
            poly = roi.getPolygon()
            n = int(poly.npoints)
            for i in range(n):
                points_x.append(float(poly.xpoints[i]))
                points_y.append(float(poly.ypoints[i]))
        except:
            points_x = []
            points_y = []

    if len(points_x) >= 2:
        total_mm = 0.0
        for i in range(1, len(points_x)):
            dx_px = points_x[i] - points_x[i - 1]
            dy_px = points_y[i] - points_y[i - 1]

            dx_unit = dx_px * cal.pixelWidth
            dy_unit = dy_px * cal.pixelHeight

            length_original_units = math.sqrt(dx_unit * dx_unit + dy_unit * dy_unit)
            total_mm = total_mm + (length_original_units * length_to_mm)

        return total_mm

    try:
        length_px = float(roi.getLength())
        pixel_size_mm = ((float(cal.pixelWidth) + float(cal.pixelHeight)) / 2.0) * length_to_mm
        return length_px * pixel_size_mm
    except:
        return 0.0
