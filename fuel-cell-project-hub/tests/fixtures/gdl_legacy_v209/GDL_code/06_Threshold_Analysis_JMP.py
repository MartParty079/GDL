# -*- coding: utf-8 -*-
# MODULE 06: Threshold/particle analysis, JMP script, and Word report assembly

# v201: strand heat maps belong to the original input image, not to a segmentation run.
# Cache them by original-image identity so sweeps/crops/report permutations reuse one map.
STRAND_HEAT_MAP_BY_OG_CACHE = {}


def choose_segmented_overlay_source(run):
    selected_path = str(run.get("segmented_selected_png", "")).strip()
    normal_path = str(run.get("segmented_png", "")).strip()
    if selected_path != "" and os.path.exists(selected_path):
        return selected_path
    if normal_path != "" and os.path.exists(normal_path):
        return normal_path
    if selected_path != "":
        return selected_path
    return normal_path


def choose_original_overlay_source(run):
    candidates = [
        str(run.get("starting_png", "")).strip(),
        str(run.get("original_png", "")).strip(),
        str(run.get("image_path", "")).strip()
    ]
    for candidate in candidates:
        if candidate != "" and os.path.exists(candidate):
            return candidate
    for candidate in candidates:
        if candidate != "":
            return candidate
    return ""


def _blend_component(base_component, over_component, alpha_fraction):
    try:
        value = int(round((float(base_component) * (1.0 - alpha_fraction)) + (float(over_component) * alpha_fraction)))
    except:
        value = int(over_component)
    if value < 0:
        value = 0
    if value > 255:
        value = 255
    return value


def signed_java_argb(alpha, red, green, blue):
    value = ((int(alpha) & 255) << 24) | ((int(red) & 255) << 16) | ((int(green) & 255) << 8) | (int(blue) & 255)
    if value > 2147483647:
        value = value - 4294967296
    return value


def overlay_png_decodes(path):
    if path in [None, ""] or not os.path.exists(path):
        return False
    try:
        test_image = ImageIO.read(File(path))
        return test_image is not None and int(test_image.getWidth()) > 0 and int(test_image.getHeight()) > 0
    except:
        return False


def rainbow_color_for_intensity(gray_value):
    try:
        t = float(gray_value) / 255.0
    except:
        t = 0.0
    if t < 0.0:
        t = 0.0
    if t > 1.0:
        t = 1.0

    stops = [
        (0.0, (128, 0, 128)),   # purple
        (0.2, (0, 0, 255)),     # blue
        (0.4, (0, 255, 255)),   # cyan
        (0.6, (0, 255, 0)),     # green
        (0.8, (255, 255, 0)),   # yellow
        (1.0, (255, 0, 0))      # red
    ]

    for idx in range(len(stops) - 1):
        p0, c0 = stops[idx]
        p1, c1 = stops[idx + 1]
        if t <= p1 or idx == len(stops) - 2:
            if p1 <= p0:
                frac = 0.0
            else:
                frac = (t - p0) / float(p1 - p0)
            if frac < 0.0:
                frac = 0.0
            if frac > 1.0:
                frac = 1.0
            r = int(round(c0[0] + (c1[0] - c0[0]) * frac))
            g = int(round(c0[1] + (c1[1] - c0[1]) * frac))
            b = int(round(c0[2] + (c1[2] - c0[2]) * frac))
            return (r, g, b)
    return (255, 0, 0)


def create_strand_heat_map_png(source_path, output_path):
    """Create the rainbow map using Fiji's own image decoder first.

    v202: ImageIO.read() alone can fail on TIFF/microscope formats that Fiji itself
    opens successfully, and that difference can vary by user/Fiji/JRE install.
    Always ask Fiji/ImageJ to decode the source first, then obtain a BufferedImage
    for the existing deterministic rainbow mapping. ImageIO remains only a fallback.
    """
    from java.awt.image import BufferedImage

    if source_path in [None, ""] or not os.path.exists(source_path):
        return ""

    source_imp = None
    image = None
    try:
        try:
            source_imp = IJ.openImage(str(source_path))
            if source_imp is not None:
                image = source_imp.getBufferedImage()
        except Exception as e_fiji_decode:
            IJ.log("Rainbow heat map Fiji decoder warning for " + str(source_path) + ": " + str(e_fiji_decode))
            image = None

        if image is None:
            try:
                image = ImageIO.read(File(source_path))
            except Exception as e_imageio_decode:
                IJ.log("Rainbow heat map ImageIO fallback warning for " + str(source_path) + ": " + str(e_imageio_decode))
                image = None

        if image is None:
            raise Exception("Neither Fiji IJ.openImage nor ImageIO could decode the heat-map source.")

        width = int(image.getWidth())
        height = int(image.getHeight())
        if width <= 0 or height <= 0:
            raise Exception("Invalid heat-map source dimensions: " + str(width) + " x " + str(height))

        out = BufferedImage(width, height, BufferedImage.TYPE_INT_RGB)
        mark_beast_worker_content_progress("HEAT_MAP_DECODED", str(width) + "x" + str(height))
        progress_row_step = max(32, int(height / 16) if height > 0 else 32)
        for y in range(height):
            if y == 0 or y % progress_row_step == 0:
                mark_beast_worker_content_progress("HEAT_MAP_RENDERING", str(y) + "/" + str(height))
            for x in range(width):
                rgb = int(image.getRGB(x, y))
                red = (rgb >> 16) & 255
                green = (rgb >> 8) & 255
                blue = rgb & 255
                gray = int(round((float(red) + float(green) + float(blue)) / 3.0))
                rr, gg, bb = rainbow_color_for_intensity(gray)
                out.setRGB(x, y, (int(rr) << 16) | (int(gg) << 8) | int(bb))

        ensure_dir(os.path.dirname(output_path))
        wrote = ImageIO.write(out, "png", File(output_path))
        if not bool(wrote) or not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
            raise Exception("PNG writer did not produce a valid heat-map file: " + str(output_path))
        mark_beast_worker_content_progress("HEAT_MAP_FILE_WRITTEN", str(output_path))
        return output_path
    finally:
        try:
            if source_imp is not None:
                source_imp.changes = False
                source_imp.close()
        except:
            pass


def strand_heat_map_original_source(run):
    """Return the true original-image source used for the pre-segmentation heat map."""
    candidates = [
        str(run.get("crop_source_image", "") or "").strip(),
        str(run.get("image_path", "") or "").strip(),
        str(run.get("starting_png", "") or "").strip(),
        str(run.get("original_png", "") or "").strip()
    ]
    for candidate in candidates:
        if candidate != "" and os.path.exists(candidate):
            return candidate
    for candidate in candidates:
        if candidate != "":
            return candidate
    return ""


def strand_heat_map_original_key(run):
    source_path = strand_heat_map_original_source(run)
    if source_path != "":
        try:
            key = os.path.normcase(os.path.abspath(source_path))
            if os.path.exists(source_path):
                key += "|" + str(os.path.getmtime(source_path)) + "|" + str(os.path.getsize(source_path))
            return key
        except:
            return source_path.lower()
    return str(run.get("og_image_name", run.get("image_name", "Unknown image"))).strip().lower()


def strand_heat_map_original_stem(run):
    name = str(run.get("og_image_name", "") or "").strip()
    if name == "":
        source_path = strand_heat_map_original_source(run)
        try:
            name = os.path.basename(source_path)
        except:
            name = source_path
    if name == "":
        name = str(run.get("base_safe", "Original_Image") or "Original_Image")
    try:
        name = os.path.splitext(os.path.basename(name))[0]
    except:
        pass
    safe_stem = safe_name(str(name))
    if safe_stem == "":
        safe_stem = "Original_Image"
    return short_safe_name(safe_stem, 120)


def _heat_map_short_hash(text):
    try:
        import hashlib
        return hashlib.md5(str(text).encode("utf-8")).hexdigest()[:8]
    except:
        try:
            return ("%08x" % (abs(hash(str(text))) & 0xffffffff))[:8]
        except:
            return "heatmap"


def safe_strand_heat_map_output_path(target_dir, run, max_windows_path=238):
    """Keep the requested OG-name convention unless Windows path length requires shortening."""
    ensure_dir(target_dir)
    suffix = "_rainbow_heat_map.png"
    stem = strand_heat_map_original_stem(run)
    candidate = os.path.join(target_dir, stem + suffix)
    try:
        candidate_abs = os.path.abspath(candidate)
    except:
        candidate_abs = candidate

    # Old Windows/Jython/Java combinations can still fail near MAX_PATH even when
    # Fiji itself opens the input. Leave margin for Java/OneDrive temporary handling.
    if len(candidate_abs) > int(max_windows_path):
        try:
            dir_abs = os.path.abspath(target_dir)
        except:
            dir_abs = str(target_dir)
        room = int(max_windows_path) - len(dir_abs) - 1 - len(suffix) - 9
        room = max(12, min(72, int(room)))
        stem = short_safe_name(stem, room) + "_" + _heat_map_short_hash(strand_heat_map_original_key(run))
        candidate = os.path.join(target_dir, stem + suffix)
    return candidate


def ensure_strand_heat_map_for_run(run, settings):
    """Create/reuse one rainbow heat map for the true original image.

    v201 invariant: this visualization is pre-segmentation and keyed by the OG image,
    so every sweep/crop run referring to that original receives the same map path.
    """
    include_in_report = bool(settings.get("report_include_strand_heat_map", True))
    save_image = bool(settings.get("report_save_strand_heat_map", True))
    if (not include_in_report) and (not save_image):
        return ""

    existing = str(run.get("strand_heat_map_png", "") or "").strip()
    if existing != "" and os.path.exists(existing):
        try:
            STRAND_HEAT_MAP_BY_OG_CACHE[strand_heat_map_original_key(run)] = existing
        except:
            pass
        return existing

    cache_key = strand_heat_map_original_key(run)
    cached = str(STRAND_HEAT_MAP_BY_OG_CACHE.get(cache_key, "") or "").strip()
    if cached != "" and os.path.exists(cached):
        run["strand_heat_map_png"] = cached
        return cached

    source_path = strand_heat_map_original_source(run)
    if source_path in [None, ""] or not os.path.exists(source_path):
        return ""

    image_dir = str(run.get("image_dir", "") or "").strip()
    if image_dir == "":
        image_dir = os.path.dirname(source_path)

    fallback_dir = str(run.get("heat_map_fallback_dir", "") or "").strip()
    if fallback_dir == "":
        run_dir = str(run.get("run_dir", "") or "").strip()
        if run_dir != "":
            fallback_dir = os.path.join(os.path.dirname(run_dir), "Heat Maps")

    target_dirs = []
    for candidate_dir in [image_dir, fallback_dir]:
        if candidate_dir not in [None, ""] and candidate_dir not in target_dirs:
            target_dirs.append(candidate_dir)

    last_error = None
    generated = ""
    for target_dir in target_dirs:
        try:
            output_path = safe_strand_heat_map_output_path(target_dir, run)
            generated = create_strand_heat_map_png(source_path, output_path)
            if generated != "":
                if os.path.normcase(os.path.abspath(target_dir)) != os.path.normcase(os.path.abspath(image_dir)):
                    IJ.log("Rainbow heat map used short-path fallback folder: " + str(target_dir))
                break
        except Exception as e_generate:
            last_error = e_generate
            IJ.log("Rainbow heat map output attempt failed in " + str(target_dir) + ": " + str(e_generate))
            generated = ""

    if generated == "" and last_error is not None:
        raise last_error

    run["strand_heat_map_png"] = generated
    if generated != "":
        STRAND_HEAT_MAP_BY_OG_CACHE[cache_key] = generated
        IJ.log("Pre-segmentation strand rainbow heat map ready for OG image: " + str(run.get("og_image_name", "")) + " -> " + generated)
    return generated


def save_overlay_with_buffered_image(output_path, original_path, segmented_path, settings, context_label):
    from java.awt.image import BufferedImage

    orig = ImageIO.read(File(original_path))
    seg = ImageIO.read(File(segmented_path))
    if orig is None or seg is None:
        raise Exception("ImageIO returned None for one or both overlay sources.")

    width = min(int(orig.getWidth()), int(seg.getWidth()))
    height = min(int(orig.getHeight()), int(seg.getHeight()))
    if width <= 0 or height <= 0:
        raise Exception("Invalid overlay dimensions: " + str(width) + " x " + str(height))

    IJ.log("Overlay source dimensions (" + str(context_label) + "): original=" + str(orig.getWidth()) + "x" + str(orig.getHeight()) + "; segmented=" + str(seg.getWidth()) + "x" + str(seg.getHeight()) + "; output=" + str(width) + "x" + str(height))

    overlay_color = get_setting_color(settings, "report_segmented_overlay_fiber_color", Color.red)
    fiber_alpha = max(0.0, min(1.0, float(settings.get("report_segmented_overlay_fiber_opacity_percent", 70.0)) / 100.0))
    annotation_alpha = max(0.0, min(1.0, float(settings.get("report_segmented_overlay_annotation_opacity_percent", 85.0)) / 100.0))

    result = BufferedImage(width, height, BufferedImage.TYPE_INT_ARGB)
    dark_count = 0
    white_count = 0
    annotation_count = 0

    for y in range(height):
        for x in range(width):
            base_rgb = int(orig.getRGB(x, y))
            base_r = (base_rgb >> 16) & 255
            base_g = (base_rgb >> 8) & 255
            base_b = base_rgb & 255

            seg_rgb = int(seg.getRGB(x, y))
            seg_a = (seg_rgb >> 24) & 255
            seg_r = (seg_rgb >> 16) & 255
            seg_g = (seg_rgb >> 8) & 255
            seg_b = seg_rgb & 255

            out_r = base_r
            out_g = base_g
            out_b = base_b

            if seg_a > 0:
                if seg_r >= 245 and seg_g >= 245 and seg_b >= 245:
                    white_count = white_count + 1
                elif seg_r <= 25 and seg_g <= 25 and seg_b <= 25:
                    dark_count = dark_count + 1
                    out_r = _blend_component(base_r, overlay_color.getRed(), fiber_alpha)
                    out_g = _blend_component(base_g, overlay_color.getGreen(), fiber_alpha)
                    out_b = _blend_component(base_b, overlay_color.getBlue(), fiber_alpha)
                else:
                    annotation_count = annotation_count + 1
                    out_r = _blend_component(base_r, seg_r, annotation_alpha)
                    out_g = _blend_component(base_g, seg_g, annotation_alpha)
                    out_b = _blend_component(base_b, seg_b, annotation_alpha)

            result.setRGB(x, y, signed_java_argb(255, out_r, out_g, out_b))

    wrote = bool(ImageIO.write(result, "png", File(output_path)))
    IJ.log("Overlay BufferedImage classification (" + str(context_label) + "): dark/fiber=" + str(dark_count) + "; white/transparent=" + str(white_count) + "; colored annotations=" + str(annotation_count) + "; ImageIO writer returned=" + str(wrote))
    if not wrote or not overlay_png_decodes(output_path):
        raise Exception("BufferedImage overlay PNG failed post-save decode verification.")
    return output_path


def save_overlay_with_imagej_fallback(output_path, original_path, segmented_path, settings, context_label):
    original_imp = None
    segmented_imp = None
    original_rgb = None
    segmented_rgb = None
    output_imp = None
    try:
        original_imp = IJ.openImage(original_path)
        segmented_imp = IJ.openImage(segmented_path)
        if original_imp is None or segmented_imp is None:
            raise Exception("IJ.openImage could not open one or both overlay sources.")

        original_rgb = Duplicator().run(original_imp)
        segmented_rgb = Duplicator().run(segmented_imp)
        IJ.run(original_rgb, "RGB Color", "")
        IJ.run(segmented_rgb, "RGB Color", "")

        width = min(int(original_rgb.getWidth()), int(segmented_rgb.getWidth()))
        height = min(int(original_rgb.getHeight()), int(segmented_rgb.getHeight()))
        output_imp = IJ.createImage("segmented_overlay_fallback", "RGB black", width, height, 1)

        base_ip = original_rgb.getProcessor()
        seg_ip = segmented_rgb.getProcessor()
        out_ip = output_imp.getProcessor()
        overlay_color = get_setting_color(settings, "report_segmented_overlay_fiber_color", Color.red)
        fiber_alpha = max(0.0, min(1.0, float(settings.get("report_segmented_overlay_fiber_opacity_percent", 70.0)) / 100.0))
        annotation_alpha = max(0.0, min(1.0, float(settings.get("report_segmented_overlay_annotation_opacity_percent", 85.0)) / 100.0))

        dark_count = 0
        white_count = 0
        annotation_count = 0
        for y in range(height):
            for x in range(width):
                base_rgb = int(base_ip.getPixel(x, y))
                base_r = (base_rgb >> 16) & 255
                base_g = (base_rgb >> 8) & 255
                base_b = base_rgb & 255
                seg_rgb = int(seg_ip.getPixel(x, y))
                seg_r = (seg_rgb >> 16) & 255
                seg_g = (seg_rgb >> 8) & 255
                seg_b = seg_rgb & 255

                out_r = base_r
                out_g = base_g
                out_b = base_b
                if seg_r >= 245 and seg_g >= 245 and seg_b >= 245:
                    white_count = white_count + 1
                elif seg_r <= 25 and seg_g <= 25 and seg_b <= 25:
                    dark_count = dark_count + 1
                    out_r = _blend_component(base_r, overlay_color.getRed(), fiber_alpha)
                    out_g = _blend_component(base_g, overlay_color.getGreen(), fiber_alpha)
                    out_b = _blend_component(base_b, overlay_color.getBlue(), fiber_alpha)
                else:
                    annotation_count = annotation_count + 1
                    out_r = _blend_component(base_r, seg_r, annotation_alpha)
                    out_g = _blend_component(base_g, seg_g, annotation_alpha)
                    out_b = _blend_component(base_b, seg_b, annotation_alpha)
                out_ip.putPixel(x, y, ((out_r & 255) << 16) | ((out_g & 255) << 8) | (out_b & 255))

        saved = bool(FileSaver(output_imp).saveAsPng(output_path))
        IJ.log("Overlay ImageJ fallback classification (" + str(context_label) + "): dark/fiber=" + str(dark_count) + "; white/transparent=" + str(white_count) + "; colored annotations=" + str(annotation_count) + "; FileSaver returned=" + str(saved))
        if not saved or not overlay_png_decodes(output_path):
            raise Exception("ImageJ fallback overlay PNG failed post-save decode verification.")
        return output_path
    finally:
        for close_imp in [output_imp, segmented_rgb, original_rgb, segmented_imp, original_imp]:
            try:
                if close_imp is not None:
                    close_imp.changes = False
                    close_imp.close()
            except:
                pass


def save_segmented_overlay_png(output_path, run, settings, context_label):
    if not settings.get("report_save_segmented_overlay_next_to_word", True):
        IJ.log("Segmented overlay disabled by setting for " + str(context_label) + ".")
        return ""

    original_path = choose_original_overlay_source(run)
    segmented_path = choose_segmented_overlay_source(run)
    ensure_dir(os.path.dirname(output_path))

    IJ.log("Segmented overlay request (" + str(context_label) + ")")
    IJ.log("  original source: " + str(original_path) + "; exists=" + str(os.path.exists(original_path) if original_path != "" else False))
    IJ.log("  segmented source: " + str(segmented_path) + "; exists=" + str(os.path.exists(segmented_path) if segmented_path != "" else False))
    IJ.log("  output target: " + str(output_path))

    if original_path == "" or segmented_path == "":
        IJ.log("Segmented overlay skipped: missing source path.")
        return ""
    if not os.path.exists(original_path) or not os.path.exists(segmented_path):
        IJ.log("Segmented overlay skipped: source file missing.")
        return ""

    if overlay_png_decodes(output_path):
        IJ.log("Segmented overlay already exists and decodes: " + output_path)
        return output_path

    try:
        result_path = save_overlay_with_buffered_image(output_path, original_path, segmented_path, settings, context_label)
        IJ.log("Segmented overlay verified using BufferedImage engine: " + result_path)
        return result_path
    except Exception as buffered_error:
        IJ.log("BufferedImage overlay engine failed: " + str(buffered_error))
        IJ.log(traceback.format_exc())

    try:
        result_path = save_overlay_with_imagej_fallback(output_path, original_path, segmented_path, settings, context_label)
        IJ.log("Segmented overlay verified using ImageJ fallback engine: " + result_path)
        return result_path
    except Exception as fallback_error:
        IJ.log("ImageJ fallback overlay engine failed: " + str(fallback_error))
        IJ.log(traceback.format_exc())
        return ""


def save_segmented_overlay_in_images(run, settings):
    if not settings.get("report_save_segmented_overlay_next_to_word", True):
        return ""
    image_dir = str(run.get("image_dir", ""))
    base_safe = str(run.get("base_safe", "run"))
    if image_dir.strip() == "":
        IJ.log("Segmented overlay Images-folder export skipped: image_dir is blank.")
        return ""
    overlay_path = os.path.join(image_dir, base_safe + "_segmented_overlay.png")
    return save_segmented_overlay_png(overlay_path, run, settings, "run Images folder")


def copy_verified_overlay(source_path, target_path):
    try:
        if source_path in [None, ""] or not overlay_png_decodes(source_path):
            return ""
        ensure_dir(os.path.dirname(target_path))
        with open(source_path, "rb") as source_handle:
            data = source_handle.read()
        with open(target_path, "wb") as target_handle:
            target_handle.write(data)
        if overlay_png_decodes(target_path):
            IJ.log("Segmented overlay copied and verified: " + target_path)
            return target_path
        IJ.log("Segmented overlay copy failed decode verification: " + target_path)
        return ""
    except Exception as copy_error:
        IJ.log("Could not copy segmented overlay: " + str(copy_error))
        IJ.log(traceback.format_exc())
        return ""


def save_segmented_overlay_next_to_report(report_dir, report_name_base, run, run_num, settings):
    if not settings.get("report_save_segmented_overlay_next_to_word", True):
        return ""
    image_base = short_safe_name(os.path.splitext(os.path.basename(str(run.get("image_path", run.get("image_name", "run")))))[0], 80)
    if image_base == "":
        image_base = "run" + str(run_num)
    overlay_name = short_safe_name(str(report_name_base) + "_Run" + str(run_num) + "_" + image_base + "_segmented_overlay", 180) + ".png"
    overlay_path = os.path.join(report_dir, overlay_name)

    existing_images_overlay = str(run.get("segmented_overlay_png", ""))
    copied = copy_verified_overlay(existing_images_overlay, overlay_path)
    if copied != "":
        return copied
    return save_segmented_overlay_png(overlay_path, run, settings, "Word_Report folder")


def save_pores_overlay_with_buffered_image(output_path, original_path, segmented_path, settings, context_label):
    from java.awt.image import BufferedImage

    orig = ImageIO.read(File(original_path))
    seg = ImageIO.read(File(segmented_path))
    if orig is None or seg is None:
        raise Exception("ImageIO returned None for one or both black/white overlay sources.")

    width = min(int(orig.getWidth()), int(seg.getWidth()))
    height = min(int(orig.getHeight()), int(seg.getHeight()))
    if width <= 0 or height <= 0:
        raise Exception("Invalid black/white overlay dimensions: " + str(width) + " x " + str(height))

    pores_alpha = max(0.0, min(1.0, float(settings.get("report_segmented_pores_overlay_opacity_percent", 30.0)) / 100.0))
    annotation_alpha = pores_alpha
    result = BufferedImage(width, height, BufferedImage.TYPE_INT_ARGB)
    pore_count = 0
    dark_count = 0
    annotation_count = 0

    for y in range(height):
        for x in range(width):
            base_rgb = int(orig.getRGB(x, y))
            base_r = (base_rgb >> 16) & 255
            base_g = (base_rgb >> 8) & 255
            base_b = base_rgb & 255

            seg_rgb = int(seg.getRGB(x, y))
            seg_a = (seg_rgb >> 24) & 255
            seg_r = (seg_rgb >> 16) & 255
            seg_g = (seg_rgb >> 8) & 255
            seg_b = seg_rgb & 255

            out_r = base_r
            out_g = base_g
            out_b = base_b

            if seg_a > 0:
                if seg_r >= 245 and seg_g >= 245 and seg_b >= 245:
                    pore_count = pore_count + 1
                elif seg_r <= 25 and seg_g <= 25 and seg_b <= 25:
                    dark_count = dark_count + 1
                else:
                    annotation_count = annotation_count + 1
                out_r = _blend_component(base_r, seg_r, pores_alpha)
                out_g = _blend_component(base_g, seg_g, pores_alpha)
                out_b = _blend_component(base_b, seg_b, pores_alpha)

            result.setRGB(x, y, signed_java_argb(255, out_r, out_g, out_b))

    wrote = bool(ImageIO.write(result, "png", File(output_path)))
    IJ.log("Black/white segmented overlay BufferedImage classification (" + str(context_label) + "): white/pore=" + str(pore_count) + "; dark/background=" + str(dark_count) + "; colored annotations=" + str(annotation_count) + "; ImageIO writer returned=" + str(wrote))
    if not wrote or not overlay_png_decodes(output_path):
        raise Exception("BufferedImage black/white overlay PNG failed post-save decode verification.")
    return output_path


def save_pores_overlay_with_imagej_fallback(output_path, original_path, segmented_path, settings, context_label):
    original_imp = None
    segmented_imp = None
    original_rgb = None
    segmented_rgb = None
    output_imp = None
    try:
        original_imp = IJ.openImage(original_path)
        segmented_imp = IJ.openImage(segmented_path)
        if original_imp is None or segmented_imp is None:
            raise Exception("IJ.openImage could not open one or both black/white overlay sources.")

        original_rgb = Duplicator().run(original_imp)
        segmented_rgb = Duplicator().run(segmented_imp)
        IJ.run(original_rgb, "RGB Color", "")
        IJ.run(segmented_rgb, "RGB Color", "")

        width = min(int(original_rgb.getWidth()), int(segmented_rgb.getWidth()))
        height = min(int(original_rgb.getHeight()), int(segmented_rgb.getHeight()))
        output_imp = IJ.createImage("segmented_bw_overlay_fallback", "RGB black", width, height, 1)

        base_ip = original_rgb.getProcessor()
        seg_ip = segmented_rgb.getProcessor()
        out_ip = output_imp.getProcessor()
        pores_alpha = max(0.0, min(1.0, float(settings.get("report_segmented_pores_overlay_opacity_percent", 30.0)) / 100.0))
        annotation_alpha = pores_alpha
        pore_count = 0
        dark_count = 0
        annotation_count = 0
        for y in range(height):
            for x in range(width):
                base_rgb = int(base_ip.getPixel(x, y))
                base_r = (base_rgb >> 16) & 255
                base_g = (base_rgb >> 8) & 255
                base_b = base_rgb & 255
                seg_rgb = int(seg_ip.getPixel(x, y))
                seg_r = (seg_rgb >> 16) & 255
                seg_g = (seg_rgb >> 8) & 255
                seg_b = seg_rgb & 255

                out_r = base_r
                out_g = base_g
                out_b = base_b
                if seg_r >= 245 and seg_g >= 245 and seg_b >= 245:
                    pore_count = pore_count + 1
                elif seg_r <= 25 and seg_g <= 25 and seg_b <= 25:
                    dark_count = dark_count + 1
                else:
                    annotation_count = annotation_count + 1
                out_r = _blend_component(base_r, seg_r, pores_alpha)
                out_g = _blend_component(base_g, seg_g, pores_alpha)
                out_b = _blend_component(base_b, seg_b, pores_alpha)
                out_ip.putPixel(x, y, ((out_r & 255) << 16) | ((out_g & 255) << 8) | (out_b & 255))

        saved = bool(FileSaver(output_imp).saveAsPng(output_path))
        IJ.log("Black/white segmented overlay ImageJ fallback classification (" + str(context_label) + "): white/pore=" + str(pore_count) + "; dark/background=" + str(dark_count) + "; colored annotations=" + str(annotation_count) + "; FileSaver returned=" + str(saved))
        if not saved or not overlay_png_decodes(output_path):
            raise Exception("ImageJ fallback black/white overlay PNG failed post-save decode verification.")
        return output_path
    finally:
        for close_imp in [output_imp, segmented_rgb, original_rgb, segmented_imp, original_imp]:
            try:
                if close_imp is not None:
                    close_imp.changes = False
                    close_imp.close()
            except:
                pass


def save_segmented_pores_overlay_png(output_path, run, settings, context_label):
    if not settings.get("report_save_segmented_overlay_next_to_word", True):
        IJ.log("Segmented black/white overlay disabled by setting for " + str(context_label) + ".")
        return ""

    original_path = choose_original_overlay_source(run)
    segmented_path = choose_segmented_overlay_source(run)
    ensure_dir(os.path.dirname(output_path))

    IJ.log("Segmented black/white overlay request (" + str(context_label) + ")")
    IJ.log("  original source: " + str(original_path) + "; exists=" + str(os.path.exists(original_path) if original_path != "" else False))
    IJ.log("  segmented source: " + str(segmented_path) + "; exists=" + str(os.path.exists(segmented_path) if segmented_path != "" else False))
    IJ.log("  output target: " + str(output_path))

    if original_path == "" or segmented_path == "":
        IJ.log("Segmented black/white overlay skipped: missing source path.")
        return ""
    if not os.path.exists(original_path) or not os.path.exists(segmented_path):
        IJ.log("Segmented black/white overlay skipped: source file missing.")
        return ""

    if overlay_png_decodes(output_path):
        IJ.log("Segmented black/white overlay already exists and decodes: " + output_path)
        return output_path

    try:
        result_path = save_pores_overlay_with_buffered_image(output_path, original_path, segmented_path, settings, context_label)
        IJ.log("Segmented black/white overlay verified using BufferedImage engine: " + result_path)
        return result_path
    except Exception as buffered_error:
        IJ.log("BufferedImage black/white overlay engine failed: " + str(buffered_error))
        IJ.log(traceback.format_exc())

    try:
        result_path = save_pores_overlay_with_imagej_fallback(output_path, original_path, segmented_path, settings, context_label)
        IJ.log("Segmented black/white overlay verified using ImageJ fallback engine: " + result_path)
        return result_path
    except Exception as fallback_error:
        IJ.log("ImageJ fallback black/white overlay engine failed: " + str(fallback_error))
        IJ.log(traceback.format_exc())
        return ""


def save_segmented_pores_overlay_in_images(run, settings):
    if not settings.get("report_save_segmented_overlay_next_to_word", True):
        return ""
    image_dir = str(run.get("image_dir", ""))
    base_safe = str(run.get("base_safe", "run"))
    if image_dir.strip() == "":
        IJ.log("Segmented black/white overlay Images-folder export skipped: image_dir is blank.")
        return ""
    overlay_path = os.path.join(image_dir, base_safe + "_segmented_pores_overlay.png")
    return save_segmented_pores_overlay_png(overlay_path, run, settings, "run Images folder")

def create_word_report(output_root, results, settings, report_name_base=None, report_output_dir=None):
    global DOCX_REPORT_DECIMALS
    try:
        DOCX_REPORT_DECIMALS = int(settings.get("docx_report_decimals", DEFAULTS["docx_report_decimals"]))
    except:
        DOCX_REPORT_DECIMALS = DEFAULTS["docx_report_decimals"]

    if report_output_dir is None or str(report_output_dir).strip() == "":
        report_dir = os.path.join(output_root, "Word_Report")
    else:
        report_dir = str(report_output_dir)
    ensure_dir(report_dir)

    if report_name_base is None or str(report_name_base).strip() == "":
        report_name_base = auto_report_base_name(results, settings)
    report_name_base = short_safe_name(str(report_name_base), 180)
    if report_name_base == "":
        report_name_base = "GDL_Report"
    report_path = unique_report_path(os.path.join(report_dir, report_name_base + ".docx"))

    # Refresh run paths for JMP files in case they were created after ImageJ processing.
    # v195 also tolerates canceled/failed records that have no run_dir or hist_dir.
    for run in results:
        refresh_jmp_output_paths(run)
        final_summary_path = str(run.get("final_summary_csv", ""))
        run["summary_rows_for_report"] = read_jmp_summary_for_report(final_summary_path) if final_summary_path != "" else []

    # Overlays are saved during the Fiji run in each run's Images folder only; they are not embedded into the Word report.
    # v201: strand heat maps should already be attached to run records before preprocessing/segmentation.
    # This refresh is only a recovery path for old/checkpoint records, and reuses the OG-image cache.
    for overlay_index in range(len(results)):
        overlay_run = results[overlay_index]
        if str(overlay_run.get("segmented_overlay_png", "")).strip() == "":
            overlay_run["segmented_overlay_png"] = save_segmented_overlay_in_images(overlay_run, settings)
        if str(overlay_run.get("segmented_pores_overlay_png", "")).strip() == "":
            overlay_run["segmented_pores_overlay_png"] = save_segmented_pores_overlay_in_images(overlay_run, settings)
        try:
            overlay_run["strand_heat_map_png"] = ensure_strand_heat_map_for_run(overlay_run, settings)
        except Exception as heat_map_error:
            overlay_run["strand_heat_map_png"] = ""
            IJ.log("WARNING: strand rainbow heat map could not be created for " + str(overlay_run.get("base_safe", "")) + ": " + str(heat_map_error))
        overlay_run["segmented_overlay_report_png"] = ""

    report_media_temp_dir = ""
    if no_lossless_report_images_enabled(settings):
        report_media_temp_dir = os.path.join(report_dir, ".YOURE_A_BETA_TEMP_JPEG_" + str(int(time.time() * 1000)))
        ensure_dir(report_media_temp_dir)
    media, rels = collect_report_images_and_rels(results, settings, report_media_temp_dir)

    body = []
    title = settings.get("report_title", "GDL Image Analysis Report")
    if title is None or str(title).strip() == "":
        title = "GDL Image Analysis Report"

    body.append(docx_para(title, bold=True, size=28, align="center"))

    sample_name = settings.get("report_sample_name", "")
    if sample_name is None or str(sample_name).strip() == "":
        if len(results) > 0:
            sample_name = os.path.splitext(os.path.basename(str(results[0].get("image_path", "Sample"))))[0]
        else:
            sample_name = "Sample"

    body.append(docx_para("Sample Used- " + str(sample_name), bold=True, size=22))
    report_scale_method = str(settings.get("report_scale_method", "Needle scale"))
    if len(results) > 0:
        report_scale_method = str(results[0].get("report_scale_method", report_scale_method))
        unique_scale_methods = []
        for scale_run in results:
            scale_text = str(scale_run.get("report_scale_method", report_scale_method))
            if scale_text not in unique_scale_methods:
                unique_scale_methods.append(scale_text)
        if len(unique_scale_methods) > 1:
            report_scale_method = "Multiple methods; see image sections"
    report_imaging_software = str(settings.get("report_imaging_software", "Swift Imaging 3.0"))
    body.append(docx_para("Scale set using- " + report_scale_method, bold=True, size=20))
    body.append(docx_para("Imaging software- " + report_imaging_software, bold=True, size=20))
    if len(results) == 1:
        body.append(docx_para(
            "Image details- " + str(results[0].get("sample_size_text", "Unknown")) +
            "; Threshold- " + threshold_range_for_run(results[0]) +
            "; Scale method- " + str(results[0].get("report_scale_method", report_scale_method)) +
            "; Imaging software- " + str(results[0].get("report_imaging_software", report_imaging_software)),
            bold=True,
            size=22
        ))
    elif len(results) > 1:
        body.append(docx_para("Batch report: image details are listed for each image section and in the complete summary table.", bold=True, size=20))
        for j in range(len(results)):
            body.append(docx_para(
                "Image " + str(j + 1) + " details- " + str(results[j].get("sample_size_text", "Unknown")) +
                "; Threshold- " + threshold_range_for_run(results[j]) +
                "; Scale method- " + str(results[j].get("report_scale_method", report_scale_method)) +
                "; Imaging software- " + str(results[j].get("report_imaging_software", report_imaging_software)),
                size=18
            ))

    # One pre-segmentation heat map per original image in each DOCX.
    # A combined/by-image report can contain many sweep runs for one OG image; do not repeat its heat map.
    report_heat_map_seen_og = {}

    for i in range(len(results)):
        run = results[i]
        run_num = i + 1

        if i > 0:
            append_docx_page_break(body)

        body.append(docx_para(report_run_title(run_num, run, len(results)), bold=False, size=22))
        body.append(docx_para(
            "Image details- " + str(run.get("sample_size_text", "Unknown")) +
            "; Threshold- " + threshold_range_for_run(run) +
            "; Scale method- " + str(run.get("report_scale_method", report_scale_method)) +
            "; Imaging software- " + str(run.get("report_imaging_software", report_imaging_software)),
            bold=True,
            size=20
        ))
        if run.get("crop_enabled", False):
            body.append(docx_para("Crop source image- " + str(run.get("crop_source_name", "")), bold=True, size=18))
            body.append(docx_para("Crop mode- " + str(run.get("crop_mode", "")) + "; " + str(run.get("crop_region_text", "")), size=18))
            if run.get("rel_crop_overview", "") != "":
                body.append(docx_para("Crop regions shown on original image:", bold=True, size=18))
                body.append(docx_image(run["rel_crop_overview"], run["crop_overview_png"], settings["report_pore_map_width_in"], run_num * 10 + 19))
        if settings.get("bad_image_detection_enabled", True):
            body.append(docx_para("Bad image check- " + str(run.get("bad_image_status", "PASS")), bold=True, size=18))
            for bad_issue in run.get("bad_image_issues", []):
                body.append(docx_para("- " + str(bad_issue), size=16))

        if run.get("auto_threshold_fit_enabled", False):
            body.append(docx_para("Manual selected-pore threshold adjustment:", bold=True, size=18))
            if run.get("auto_threshold_fit_triggered", False):
                auto_rows = [[
                    "Initial threshold max (selected units)",
                    "Normal manual area",
                    "Normal table area",
                    "Normal % diff",
                    "Adjustment",
                    "Final threshold max (selected units)",
                    "Final table area",
                    "Final % diff"
                ], [
                    run.get("auto_threshold_fit_threshold_before", ""),
                    run.get("auto_threshold_fit_manual_area_mm2", ""),
                    run.get("auto_threshold_fit_normal_table_area_mm2", ""),
                    run.get("auto_threshold_fit_normal_area_percent_diff", ""),
                    run.get("auto_threshold_fit_direction", ""),
                    run.get("auto_threshold_fit_threshold_after", ""),
                    run.get("auto_threshold_fit_final_table_area_mm2", ""),
                    run.get("auto_threshold_fit_final_area_percent_diff", "")
                ]]
                body.append(docx_table(auto_rows, 14))
            else:
                diff_txt = str(run.get("auto_threshold_fit_normal_area_percent_diff", ""))
                if diff_txt == "":
                    diff_txt = "not available"
                body.append(docx_para("Normal selected-pore percent difference: " + diff_txt + "%. No +/-5 threshold step was applied.", size=16))

        manual_section_start = len(body)

        largest_entries = run.get("manual_largest_pore_entries", [])
        if settings.get("manual_largest_pore_enabled", False):
            if largest_entries is not None and len(largest_entries) > 0:
                body.append(docx_para("Manual largest pore area measurements:", bold=True, size=20))
                table_rows = [["Rank", "Analysis pore ID", "Analysis area (mm^2)", "Manual area (mm^2)", "Tracing tool"]]
                for le in largest_entries:
                    table_rows.append([
                        le.get("rank", ""),
                        le.get("pore_id", ""),
                        le.get("analysis_area_mm2", ""),
                        le.get("manual_area_mm2", ""),
                        le.get("trace_tool", "")
                    ])
                body.append(docx_table(table_rows, 14))
            elif run.get("manual_largest_pore_area_mm2", None) not in [None, ""]:
                body.append(docx_para("Manual largest pore area: " + clean_report_table_cell(run.get("manual_largest_pore_area_mm2", "")) + " mm^2", bold=True, size=20))
                body.append(docx_para("Analysis largest pore area: " + clean_report_table_cell(run.get("analysis_largest_pore_area_mm2", "")) + " mm^2", size=18))

            guide_rel = run.get("rel_manual_largest_pore", "")
            guide_path = run.get("manual_largest_pore_circled_png", "")
            guide_caption = "Manual measurement guide: unfiltered original image with a largest pore shown using an offset outline."

            if run.get("rel_manual_combined_guide", "") != "":
                guide_rel = run.get("rel_manual_combined_guide", "")
                guide_path = run.get("manual_combined_guide_png", "")
                guide_caption = "Manual measurement guide: unfiltered original image with the selected pore green offset outline because the 5% auto-fit/redo trigger was reached."

            if guide_rel != "":
                body.append(docx_para(guide_caption, italic=True, size=16))
                body.append(docx_image(guide_rel, guide_path, settings["report_main_image_width_in"] * 1.35, run_num * 10 + 8))

        selected_entries = run.get("manual_selected_pore_entries", [])
        if settings.get("manual_selected_pore_enabled", False):
            if selected_entries is not None and len(selected_entries) > 0:
                body.append(docx_para("Manual user-selected pore area measurements:", bold=True, size=20))
                table_rows = [["#", "Matched pore ID", "Table area used (mm^2)", "Manual area (mm^2)", "Initial % diff", "Final/used % diff", "Tracing tool", "Match method"]]
                for se in selected_entries:
                    final_pct = se.get("final_area_percent_diff", se.get("normal_area_percent_diff", ""))
                    final_area = se.get("final_table_area_mm2", se.get("table_area_mm2", ""))
                    final_id = se.get("final_pore_id", se.get("pore_id", ""))
                    final_method = se.get("final_match_method", se.get("match_method", ""))
                    table_rows.append([
                        se.get("index", ""),
                        final_id,
                        final_area,
                        se.get("manual_area_mm2", ""),
                        se.get("normal_area_percent_diff", ""),
                        final_pct,
                        se.get("trace_tool", ""),
                        final_method
                    ])
                body.append(docx_table(table_rows, 14))
            elif run.get("manual_selected_pore_area_mm2", None) not in [None, ""]:
                body.append(docx_para("Manual selected pore area: " + clean_report_table_cell(run.get("manual_selected_pore_area_mm2", "")) + " mm^2", bold=True, size=20))
                body.append(docx_para("Matched analysis pore ID: " + clean_report_table_cell(run.get("manual_selected_pore_id", "")) + "; table area: " + clean_report_table_cell(run.get("manual_selected_table_area_mm2", "")) + " mm^2; method: " + str(run.get("manual_selected_match_method", "")) + "; tracing tool: " + str(run.get("manual_selected_trace_tool", "")), size=18))

        segmented_rel = run.get("rel_segmented", "")
        segmented_path = run.get("segmented_png", "")
        segmented_caption = "Segmented image"
        if run.get("rel_segmented_selected", "") != "":
            segmented_rel = run.get("rel_segmented_selected", "")
            segmented_path = run.get("segmented_selected_png", "")
            segmented_caption = "Segmented image with selected pore green outline because the 5% auto-fit/redo trigger was reached"

        if settings.get("manual_strand_measurement_enabled", False):
            strand_lengths = run.get("manual_strand_lengths_mm", [])
            if strand_lengths is not None and len(strand_lengths) > 0:
                body.append(docx_para("Manual Strand Measurements:", bold=True, size=20))
                for si in range(len(strand_lengths)):
                    strand_tool = ""
                    try:
                        strand_tool = str(run.get("manual_strand_trace_tools", [])[si])
                    except:
                        strand_tool = ""
                    if strand_tool != "":
                        body.append(docx_para("Strand #" + str(si + 1) + " - " + format_docx_number(strand_lengths[si], settings.get("docx_report_decimals", DOCX_REPORT_DECIMALS)) + " mm; tracing tool: " + strand_tool, size=18))
                    else:
                        body.append(docx_para("Strand #" + str(si + 1) + " - " + format_docx_number(strand_lengths[si], settings.get("docx_report_decimals", DOCX_REPORT_DECIMALS)) + " mm", size=18))
            else:
                body.append(docx_para("Manual Strand Measurements: none recorded.", italic=True, size=18))

        manual_measurement_section_enabled = (len(body) > manual_section_start)
        if manual_measurement_section_enabled:
            append_docx_page_break(body)

        # v201: insert the OG-image heat map before segmentation imagery, exactly once per OG image in this report.
        heat_map_key = strand_heat_map_original_key(run)
        show_og_heat_map = (
            bool(settings.get("report_include_strand_heat_map", True)) and
            run.get("rel_strand_heat_map", "") != "" and
            not bool(report_heat_map_seen_og.get(heat_map_key, False))
        )
        if show_og_heat_map:
            body.append(docx_para("Original Image Rainbow Heat Map (Pre-Segmentation)", bold=True, size=18, align="center"))
            body.append(docx_image(run["rel_strand_heat_map"], run.get("strand_heat_map_png", ""), settings["report_pore_map_width_in"], run_num * 100 + 21))
            body.append(docx_para("One brightness heat map for this original image, generated before preprocessing/segmentation. Darkest intensity = purple; brightest intensity = red.", italic=True, size=16, align="center"))
            report_heat_map_seen_og[heat_map_key] = True

        main_images = [
            ("Original input image", run.get("rel_original", ""), run.get("starting_png", "")),
            (segmented_caption, segmented_rel, segmented_path),
            ("Numbered pore outlines", run.get("rel_outlines", ""), run.get("outlines_png", ""))
        ]
        body.append(docx_compact_three_image_table(main_images, settings["report_main_image_width_in"], run_num * 100 + 1))

        body.append(docx_para("Process steps:", size=22))
        steps = build_process_steps_for_report(run)
        for step in steps:
            body.append(docx_para("    " + step, size=20))

        append_docx_page_break(body)
        body.append(docx_para("Results:", size=22))
        summary_rows = run.get("summary_rows_for_report", [])
        if len(summary_rows) > 0:
            table_rows = [["Metric", "Value"]]
            for sr in summary_rows:
                if len(sr) >= 2:
                    table_rows.append([pretty_summary_metric_name(sr[0]), sr[1]])
                else:
                    table_rows.append(sr)
            body.append(docx_table(table_rows, 16))
        else:
            body.append(docx_para("JMP final summary CSV not found yet: " + str(run.get("final_summary_csv", ""))))

        if settings.get("flag_weird_pores_enabled", False):
            weird_rows = run.get("weird_pore_rows", [])
            body.append(docx_para("Flagged Weird / Outlier Pores:", bold=True, size=20))
            if weird_rows is not None and len(weird_rows) > 0:
                table_rows = [["Pore ID", "EPD mm", "Area mm^2", "Circularity", "Roundness", "X", "Y", "Reason"]]
                for wr in weird_rows:
                    table_rows.append(wr)
                body.append(docx_table(table_rows, 14))
            else:
                body.append(docx_para("No pores matched the weird/outlier criteria.", italic=True, size=18))

        append_docx_page_break(body)
        body.append(docx_para("Histograms:", size=22))
        # Keep the same general style as the provided report: stacked histograms on one page.
        hist_added = False
        for key in ["hist_epd_png", "hist_round_png", "hist_circ_png"]:
            rel_key = "rel_" + key.replace("_png", "").replace("hist_", "hist_")
            # Explicit mapping avoids rel_key mistakes.
        if run.get("rel_hist_epd", "") != "":
            body.append(docx_para("EPD Distribution [mm] - cleaned pores after small-pore cutoff", bold=True, size=18))
            body.append(docx_image(run["rel_hist_epd"], run["hist_epd_png"], settings["report_hist_image_width_in"], run_num * 10 + 4))
            if settings.get("jmp_epd_show_cutoff_lines", False):
                cutoff_caption = ("Cutoff lines: red = pores at or below " + format_micron_label(run.get("small_epd_cutoff", settings.get("small_epd_cutoff", 0.005))) +
                                  "; blue = pores above " + format_micron_label(run.get("epd_cutoff_1", settings.get("epd_cutoff_1", 0.1))) +
                                  "; green = pores above " + format_micron_label(run.get("epd_cutoff_2", settings.get("epd_cutoff_2", 0.025))) + ".")
                body.append(docx_para(cutoff_caption, italic=True, size=16, align="center"))
            hist_added = True
        if run.get("rel_hist_round", "") != "":
            body.append(docx_para("Roundness Distribution", bold=True, size=18))
            body.append(docx_image(run["rel_hist_round"], run["hist_round_png"], settings["report_hist_image_width_in"], run_num * 10 + 5))
            hist_added = True
        if run.get("rel_hist_circ", "") != "":
            body.append(docx_para("Circularity Distribution", bold=True, size=18))
            body.append(docx_image(run["rel_hist_circ"], run["hist_circ_png"], settings["report_hist_image_width_in"], run_num * 10 + 6))
            hist_added = True
        if not hist_added:
            body.append(docx_para("JMP histogram images not found yet in: " + str(run.get("hist_dir", ""))))

        append_docx_page_break(body)
        if run.get("rel_pore_map", "") != "":
            body.append(docx_image(run["rel_pore_map"], run["pore_map_png"], settings["report_pore_map_width_in"], run_num * 10 + 7))
            cap = ("Pore Map from cleaned pore data - " + str(run.get("pore_map_below_1_count", 0)) +
                   " pores above " + pore_map_micron_text(run.get("small_epd_cutoff", settings.get("small_epd_cutoff", 0.0))) +
                   " and below " + pore_map_micron_text(run.get("epd_between_high", 0.005)) +
                   "; " + str(run.get("pore_map_high_count", 0)) + " cleaned pores above 25 um" +
                   "; marker opacity " + threshold_compact_number(run.get("report_pore_map_opacity_percent", 70.0)) + "%")
            body.append(docx_para(cap, italic=True, size=18, align="center"))
        else:
            body.append(docx_para("Pore map image missing: " + str(run.get("pore_map_png", ""))))

        if run.get("rel_all_pore_map", "") != "":
            body.append(docx_image(run["rel_all_pore_map"], run["all_pore_map_png"], settings["report_pore_map_width_in"], run_num * 10 + 17))
            all_cap = "All-Pore Centroid EPD Map - " + str(run.get("all_pore_map_count", 0)) + " pores shown"
            if run.get("all_pore_map_min_epd_mm", 0) not in [None, ""] and run.get("all_pore_map_max_epd_mm", 0) not in [None, ""]:
                all_cap += "; EPD range " + format_docx_number(run.get("all_pore_map_min_epd_mm", 0), settings.get("docx_report_decimals", DOCX_REPORT_DECIMALS))
                all_cap += " to " + format_docx_number(run.get("all_pore_map_max_epd_mm", 0), settings.get("docx_report_decimals", DOCX_REPORT_DECIMALS)) + " mm"
            body.append(docx_para(all_cap, italic=True, size=18, align="center"))

    add_sweep_comparison_section(body, results, settings)

    if len(results) > 0:
        append_docx_section_break(body, settings)
        body.append(docx_para("Complete Summary Comparison:", bold=True, size=22))

        if settings.get("manual_largest_pore_enabled", False) or settings.get("manual_selected_pore_enabled", False):
            manual_compare_rows = build_manual_largest_pore_comparison_rows(results)
            if len(manual_compare_rows) > 1:
                body.append(docx_para("Manual Pore Area Comparison:", bold=True, size=20))
                body.append(docx_table(manual_compare_rows, 16))

        body.append(docx_para("Each row compares the JMP final summary values for one run.", size=18))
        comparison_rows = build_combined_summary_table_rows(results)
        if len(comparison_rows) > 1:
            body.append(docx_table(comparison_rows, 16))
        else:
            body.append(docx_para("No JMP summary tables were available to compare."))

    sect = docx_summary_final_section_pr(settings)

    document_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    document_xml += '<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:w10="urn:schemas-microsoft-com:office:word" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" mc:Ignorable="w14 wp14">'
    document_xml += '<w:body>' + "".join(body) + sect + '</w:body></w:document>'

    rels_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    rels_xml += '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    for rel_id, target in rels:
        rels_xml += '<Relationship Id="' + rel_id + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="' + target + '"/>'
    rels_xml += '<Relationship Id="rIdSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>'
    rels_xml += '</Relationships>'

    content_types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    content_types += '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    content_types += '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    content_types += '<Default Extension="xml" ContentType="application/xml"/>'
    content_types += '<Default Extension="png" ContentType="image/png"/>'
    content_types += '<Default Extension="jpg" ContentType="image/jpeg"/>'
    content_types += '<Default Extension="jpeg" ContentType="image/jpeg"/>'
    content_types += '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    content_types += '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
    content_types += '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
    content_types += '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
    content_types += '</Types>'

    root_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    root_rels += '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    root_rels += '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    root_rels += '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
    root_rels += '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
    root_rels += '</Relationships>'

    core_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    core_xml += '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    core_xml += '<dc:title>' + xml_escape(title) + '</dc:title><dc:creator>ImageJ JMP Report Script</dc:creator><cp:lastModifiedBy>ImageJ JMP Report Script</cp:lastModifiedBy></cp:coreProperties>'

    app_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    app_xml += '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>ImageJ/Fiji</Application></Properties>'

    # Full-lossless mode tells Word not to auto-compress pictures. In lossy-report
    # mode the media has already been converted to JPEG, so Word may use its normal handling.
    settings_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    if no_lossless_report_images_enabled(settings):
        settings_xml += '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"></w:settings>'
    else:
        settings_xml += '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:doNotAutoCompressPictures/></w:settings>'

    fos = FileOutputStream(report_path)
    zos = ZipOutputStream(fos)
    try:
        zip_writestr(zos, "[Content_Types].xml", content_types)
        zip_writestr(zos, "_rels/.rels", root_rels)
        zip_writestr(zos, "docProps/core.xml", core_xml)
        zip_writestr(zos, "docProps/app.xml", app_xml)
        zip_writestr(zos, "word/document.xml", document_xml)
        zip_writestr(zos, "word/settings.xml", settings_xml)
        zip_writestr(zos, "word/_rels/document.xml.rels", rels_xml)
        for media_name, media_path in media:
            zip_writefile(zos, "word/media/" + media_name, media_path)
    finally:
        zos.close()
        fos.close()
        if report_media_temp_dir != "":
            temp_paths = []
            for media_name, media_path in media:
                try:
                    if str(media_path).startswith(str(report_media_temp_dir)):
                        temp_paths.append(str(media_path))
                except:
                    pass
            cleanup_temp_report_jpegs(temp_paths, report_media_temp_dir)

    return report_path


def jmp_expected_outputs_exist(run):
    return (
        path_exists(run.get("final_summary_csv", "")) and
        path_exists(run.get("hist_epd_png", "")) and
        path_exists(run.get("hist_round_png", "")) and
        path_exists(run.get("hist_circ_png", "")) and
        path_exists(run.get("jmp_done_file", ""))
    )


def refresh_jmp_output_paths(run):
    # Partial/canceled worker records may legitimately have no output directory.
    # Keep export/report generation alive instead of raising KeyError: hist_dir.
    run_dir = str(run.get("run_dir", "") or "").strip()
    hist_dir = str(run.get("hist_dir", "") or "").strip()
    if hist_dir == "" and run_dir != "":
        hist_dir = os.path.join(run_dir, "Histograms")
        run["hist_dir"] = hist_dir
    if run_dir == "":
        run["final_summary_csv"] = str(run.get("final_summary_csv", "") or "")
        run["raw_all_pores_csv"] = str(run.get("raw_all_pores_csv", "") or "")
        run["cleaned_pores_csv"] = str(run.get("cleaned_pores_csv", "") or "")
        run["jmp_done_file"] = str(run.get("jmp_done_file", "") or "")
        run["hist_epd_png"] = str(run.get("hist_epd_png", "") or "")
        run["hist_round_png"] = str(run.get("hist_round_png", "") or "")
        run["hist_circ_png"] = str(run.get("hist_circ_png", "") or "")
        return
    run["final_summary_csv"] = os.path.join(run_dir, "Final_Summary.csv")
    run["raw_all_pores_csv"] = os.path.join(run_dir, "Raw_with_epd_all_detected_for_audit.csv")
    run["cleaned_pores_csv"] = os.path.join(run_dir, "EPD_Cleaned.csv")
    run["jmp_done_file"] = os.path.join(run_dir, "JMP_DONE.txt")
    run["hist_epd_png"] = os.path.join(hist_dir, "Histogram_EPD_Distribution_mm.png") if hist_dir != "" else ""
    run["hist_round_png"] = os.path.join(hist_dir, "Roundness_Distribution.png") if hist_dir != "" else ""
    run["hist_circ_png"] = os.path.join(hist_dir, "Circularity_Distribution.png") if hist_dir != "" else ""


def wait_for_single_jmp_output_for_report(run, settings):
    refresh_jmp_output_paths(run)
    timeout = int(settings.get("report_wait_timeout_sec", 180))
    start = time.time()

    while True:
        refresh_jmp_output_paths(run)
        if jmp_expected_outputs_exist(run):
            return True
        if timeout <= 0:
            return False
        elapsed = time.time() - start
        if elapsed > timeout:
            return False
        IJ.showStatus("Waiting for JMP report output for " + str(run.get("run_label", "run")) + "... " + str(int(elapsed)) + " s")
        time.sleep(2.0)

def launch_all_jmp_scripts_for_report(results, settings):
    # Sequential launching is slower, but it prevents sweep runs from reusing the wrong JMP window/table
    # and makes the report gather the correct summary/histograms for each run folder.
    if not settings.get("report_launch_all_jmp", True):
        IJ.log("Report requested, but report JMP launching is disabled. Report will include any JMP outputs already present.")
        return 0

    jmp_exe = find_jmp_exe(settings)
    if jmp_exe == "":
        IJ.log("JMP executable not found. Report will include any JMP outputs already present.")
        return 0

    launched = 0
    for run in results:
        refresh_jmp_output_paths(run)
        if jmp_expected_outputs_exist(run):
            IJ.log("JMP outputs already found for report run: " + str(run.get("run_label", "")))
            continue
        try:
            cmd = ArrayList()
            cmd.add(jmp_exe)
            cmd.add(run["jsl_file"])
            report_proc = ProcessBuilder(cmd).start()
            register_active_process(report_proc)
            launched = launched + 1
            IJ.log("Launched JMP for report run: " + str(run.get("run_label", "")) + " / " + run["jsl_file"])

            # Wait for this run before launching the next one. This is the key sweep-report fix.
            if settings.get("report_wait_for_jmp", True):
                ok = wait_for_single_jmp_output_for_report(run, settings)
                if ok:
                    IJ.log("JMP outputs ready for report run: " + str(run.get("run_label", "")))
                else:
                    IJ.log("Timed out waiting for JMP outputs for report run: " + str(run.get("run_label", "")))
            else:
                time.sleep(0.75)
            unregister_active_process(report_proc)
        except Exception as e:
            IJ.log("Could not launch JMP script for report: " + str(run.get("jsl_file", "")) + " / " + str(e))
    return launched

def wait_for_jmp_outputs_for_report(results, settings):
    if not settings.get("report_wait_for_jmp", True):
        return

    for run in results:
        refresh_jmp_output_paths(run)

    timeout = int(settings.get("report_wait_timeout_sec", 180))
    start = time.time()

    while True:
        all_done = True
        for run in results:
            refresh_jmp_output_paths(run)
            if not jmp_expected_outputs_exist(run):
                all_done = False
                break

        if all_done:
            IJ.log("All expected JMP outputs found for report.")
            return

        if timeout <= 0:
            return

        elapsed = time.time() - start
        if elapsed > timeout:
            IJ.log("Timed out waiting for JMP outputs. Report will include missing-output placeholders.")
            return

        IJ.showStatus("Waiting for JMP report outputs... " + str(int(elapsed)) + " s")
        time.sleep(2.0)

# ======================================================
# JMP SCRIPT GENERATOR
# ======================================================

def create_jmp_script(jsl_file, pore_csv, imagej_summary_csv, run_dir, hist_dir, base_safe, settings):
    jsl_template = r'''
Names Default To Here( 1 );

// ======================================================
// AUTO-GENERATED JMP SCRIPT FROM FIJI / IMAGEJ
// This file is the script JMP should run.
// Cleaned table is sorted by epd(mm) descending.
// ======================================================

filePath = "__PORE_CSV__";
summaryFilePath = "__IMAGEJ_SUMMARY_CSV__";
outDir = "__RUN_DIR__/";
histDir = "__HIST_DIR__/";

epdColName = "epd(mm)";

smallEPDCutoff = __SMALL_EPD__;
epdCutoff1 = __EPD_CUTOFF_1__;
epdCutoff2 = __EPD_CUTOFF_2__;
epdBetweenLowSetting = __EPD_BETWEEN_LOW__;
epdBetweenHighSetting = __EPD_BETWEEN_HIGH__;
epdBetweenLow = Min( epdBetweenLowSetting, epdBetweenHighSetting );
epdBetweenHigh = Max( epdBetweenLowSetting, epdBetweenHighSetting );
circCutoff = __CIRC_CUTOFF__;

histMaxBins = __HIST_MAX_BINS__;
histAutoBinning = __HIST_AUTO_BINNING__;
histEPDBins = __HIST_EPD_BINS__;
histEPDMajorTick = __HIST_EPD_MAJOR_TICK__;
histEPDXMinorTicks = __HIST_EPD_X_MINOR_TICKS__;
histEPDYMinorTicks = __HIST_EPD_Y_MINOR_TICKS__;
histRoundBins = __HIST_ROUND_BINS__;
histRoundXMinorTicks = __HIST_ROUND_X_MINOR_TICKS__;
histRoundYMinorTicks = __HIST_ROUND_Y_MINOR_TICKS__;
histCircBins = __HIST_CIRC_BINS__;
histCircXMinorTicks = __HIST_CIRC_X_MINOR_TICKS__;
histCircYMinorTicks = __HIST_CIRC_Y_MINOR_TICKS__;
histAxisPadPercent = __HIST_AXIS_PAD_PERCENT__;
showEPDCutoffLines = __SHOW_EPD_CUTOFF_LINES__;
histGraphWidth = __HIST_GRAPH_WIDTH__;
histGraphHeight = __HIST_GRAPH_HEIGHT__;
histShowLegend = __HIST_SHOW_LEGEND__;
histShowGraphTitles = __HIST_SHOW_GRAPH_TITLES__;
histShowAxisTitles = __HIST_SHOW_AXIS_TITLES__;
histEPDXAxisTitle = "__HIST_EPD_X_AXIS_TITLE__";
histEPDYAxisTitle = "__HIST_EPD_Y_AXIS_TITLE__";
histRoundXAxisTitle = "__HIST_ROUND_X_AXIS_TITLE__";
histRoundYAxisTitle = "__HIST_ROUND_Y_AXIS_TITLE__";
histCircXAxisTitle = "__HIST_CIRC_X_AXIS_TITLE__";
histCircYAxisTitle = "__HIST_CIRC_Y_AXIS_TITLE__";
histTrimTrailingZeros = __HIST_TRIM_TRAILING_ZEROS__;
epdAxisMinSetting = __HIST_EPD_X_MIN__;
epdAxisMaxSetting = __HIST_EPD_X_MAX__;
epdYAxisMaxSetting = __HIST_EPD_Y_MAX__;
epdYAxisMajorTick = __HIST_EPD_Y_MAJOR_TICK__;
roundAxisMinSetting = __HIST_ROUND_X_MIN__;
roundAxisMaxSetting = __HIST_ROUND_X_MAX__;
roundXAxisMajorTick = __HIST_ROUND_X_MAJOR_TICK__;
roundYAxisMaxSetting = __HIST_ROUND_Y_MAX__;
roundYAxisMajorTick = __HIST_ROUND_Y_MAJOR_TICK__;
circAxisMinSetting = __HIST_CIRC_X_MIN__;
circAxisMaxSetting = __HIST_CIRC_X_MAX__;
circXAxisMajorTick = __HIST_CIRC_X_MAJOR_TICK__;
circYAxisMaxSetting = __HIST_CIRC_Y_MAX__;
circYAxisMajorTick = __HIST_CIRC_Y_MAJOR_TICK__;
epdHistRoundFilterEnabled = __HIST_EPD_ROUND_FILTER_ENABLED__;
epdHistRoundFilterMin = __HIST_EPD_ROUND_FILTER_MIN__;
summaryUseAllDetected = __SUMMARY_USE_ALL_DETECTED__;
closeJMPWindowsWhenFinished = __CLOSE_JMP_WINDOWS__;
beastExitJMPWhenDone = __BEAST_EXIT_JMP__;
beastDisableGraphs = __BEAST_DISABLE_GRAPHS__;

possibleAreaCols = {"Pore Area", "Area", "Pore area", "area"};
possibleCircCols = {"Circularity", "Circ.", "Circ", "circularity"};
possibleRoundCols = {"Roundness", "Round", "roundness", "round"};

possibleAreaPercentCols = {"Area %", "%Area", "% Area", "Area%", "Percent Area", "Area Percent", "Area Fraction"};
possibleTotalAreaCols = {"Total Area", "TotalArea", "Total area", "Area Total"};
possibleImageTotalAreaCols = {"Image Total Area", "ImageTotalArea", "Image total area", "Total Image Area", "Image Area"};
possibleSolidityCols = {"Solidity", "Mean Solidity", "Average Solidity", "Avg Solidity", "Solidity Mean"};

If( !beastDisableGraphs,
	Create Directory( histDir );
);

// ======================================================
// HELPER FUNCTIONS
// ======================================================

normalizeName = Function( {txt},
	{out},

	out = Lowercase( Char( txt ) );

	out = Substitute(
		out,
		" ", "",
		"_", "",
		"-", "",
		".", "",
		"(", "",
		")", "",
		"%", "percent"
	);

	Return( out );
);

isUnitScaleHistogramColumn = Function( {columnName},
	{n},

	n = normalizeName( columnName );

	// These ImageJ shape columns are naturally bounded from 0 to 1.
	// Their histogram-only helper columns are clamped into 0..1 and exact 1.0 values
	// are nudged just inside the final bin so JMP does not make or clip an overflow bin.
	If(
		n == "circularity" |
		n == "circ" |
		n == "roundness" |
		n == "round" |
		n == "solidity",
		Return( 1 )
	);

	Return( 0 );
);

isEPDHistogramColumn = Function( {columnName},
	{n},

	n = normalizeName( columnName );

	If(
		n == normalizeName( epdColName ) |
		n == "epdmm" |
		n == "equivalentporediametermm",
		Return( 1 )
	);

	Return( 0 );
);

makeUnitScaleHistogramColumn = Function( {dataTable, sourceColumnName, histColumnName},
	{existingNames},

	Current Data Table( dataTable );

	existingNames = dataTable << Get Column Names( "String" );

	If( Contains( existingNames, histColumnName ),
		dataTable << Delete Columns( histColumnName )
	);

	dataTable << New Column(
		histColumnName,
		Numeric,
		Continuous,
		Format( "Fixed Dec", 20, 9 ),
		Set Each Value(
			If( Is Missing( As Column( sourceColumnName ) ),
				.,
				Min( 0.999999999, Max( 0, As Column( sourceColumnName ) ) )
			)
		)
	);

	Return( histColumnName );
);

findColumn = Function( {dataTable, possibleNames},
	{existingNames, i, j, wantedName, actualName, wantedNorm, actualNorm},

	existingNames = dataTable << Get Column Names( "String" );

	For( i = 1, i <= N Items( possibleNames ), i++,
		wantedName = possibleNames[i];

		If( Contains( existingNames, wantedName ),
			Return( wantedName )
		);
	);

	For( i = 1, i <= N Items( possibleNames ), i++,
		wantedNorm = normalizeName( possibleNames[i] );

		For( j = 1, j <= N Items( existingNames ), j++,
			actualName = existingNames[j];
			actualNorm = normalizeName( actualName );

			If( actualNorm == wantedNorm,
				Return( actualName )
			);
		);
	);

	Return( "" );
);

getFirstNumericValue = Function( {dataTable, columnName},
	{r, rawVal, txtVal, numVal},

	For( r = 1, r <= N Rows( dataTable ), r++,

		rawVal = Column( dataTable, columnName )[r];

		If( !Is Missing( rawVal ),

			If( Is Number( rawVal ),
				Return( rawVal );
			,
				txtVal = Char( rawVal );

				txtVal = Substitute(
					txtVal,
					"%", "",
					",", "",
					" ", ""
				);

				numVal = Num( txtVal );

				If( !Is Missing( numVal ),
					Return( numVal )
				);
			);
		);
	);

	Return( . );
);

// ======================================================
// OPEN IMAGEJ CSV FILES
// ======================================================

If( !File Exists( filePath ),
	Throw( "Pore results CSV does not exist or path is too long for JMP: " || filePath )
);

If( !File Exists( summaryFilePath ),
	Throw( "ImageJ summary CSV does not exist or path is too long for JMP: " || summaryFilePath )
);

dt = Open( filePath, Invisible );

If( Is Empty( dt ),
	Throw( "Could not open ImageJ pore results CSV. Path length = " || Char( Length( filePath ) ) || " : " || filePath )
);

dtImageJSummary = Open( summaryFilePath, Invisible );

If( Is Empty( dtImageJSummary ),
	Throw( "Could not open ImageJ summary CSV. Path length = " || Char( Length( summaryFilePath ) ) || " : " || summaryFilePath )
);

// ======================================================
// FIND COLUMNS
// ======================================================

areaColName = findColumn( dt, possibleAreaCols );
circColName = findColumn( dt, possibleCircCols );
roundColName = findColumn( dt, possibleRoundCols );
solidityDataColName = findColumn( dt, possibleSolidityCols );

If( areaColName == "",
	Throw( "Could not find pore area column." )
);

If( circColName == "",
	Throw( "Could not find circularity column." )
);

If( roundColName == "",
	Throw( "Could not find roundness column." )
);

If( solidityDataColName == "",
	Throw( "Could not find solidity column in ImageJ pore results CSV." )
);

areaPercentColName = findColumn( dtImageJSummary, possibleAreaPercentCols );
totalAreaColName = findColumn( dtImageJSummary, possibleTotalAreaCols );
imageTotalAreaColName = findColumn( dtImageJSummary, possibleImageTotalAreaCols );
solidityColName = findColumn( dtImageJSummary, possibleSolidityCols );

If( areaPercentColName == "",
	Throw( "Could not find Area % column in ImageJ summary CSV." )
);

If( totalAreaColName == "",
	Throw( "Could not find Total Area column in ImageJ summary CSV." )
);

If( imageTotalAreaColName == "",
	Throw( "Could not find Image Total Area column in ImageJ summary CSV." )
);

If( solidityColName == "",
	Throw( "Could not find Solidity column in ImageJ summary CSV." )
);

// ImageJ summary values are read for image total area only; final report metrics are recomputed from dtClean.
imageTotalAreaValue = getFirstNumericValue( dtImageJSummary, imageTotalAreaColName );
areaPercentValue = .;
totalAreaValue = .;
solidityValue = .;

// ======================================================
// CREATE / REPLACE epd(mm)
// Formula: sqrt((pore area * 4) / pi)
// ======================================================

currentColNames = dt << Get Column Names( "String" );

If( Contains( currentColNames, epdColName ),
	dt << Delete Columns( epdColName )
);

dt << New Column(
	epdColName,
	Numeric,
	Continuous,
	Format( "Fixed Dec", 20, 9 ),
	Set Each Value(
		Sqrt( (As Column( areaColName ) * 4) / Pi() )
	)
);

// Raw all-detected table is retained only for audit/debug.
// Main reported data is EPD_Cleaned.* after the small-EPD cutoff is applied.
dt << Save( outDir || "Raw_with_epd_all_detected_for_audit.jmp" );
dt << Save( outDir || "Raw_with_epd_all_detected_for_audit.csv" );

// ======================================================
// MAKE CLEAN COPY
// ======================================================

dtClean = dt << Subset(
	All Rows,
	Selected Columns( 0 ),
	Output Table( "EPD_Cleaned" )
);

Current Data Table( dtClean );

originalN = N Rows( dtClean );

// ======================================================
// COUNT AND DELETE epd(mm) <= cutoff
// ======================================================

rowsSmallEPD = dtClean << Get Rows Where(
	As Column( epdColName ) <= smallEPDCutoff
);

nSmallEPD = N Rows( rowsSmallEPD );

If( nSmallEPD > 0,
	dtClean << Delete Rows( rowsSmallEPD )
);

// ======================================================
// SORT CLEANED TABLE BY epd(mm) DESCENDING
// ======================================================

If( N Rows( dtClean ) > 0,
	dtClean << Sort(
		By( As Column( epdColName ) ),
		Order( Descending ),
		Replace Table
	)
);

keptN = N Rows( dtClean );

// ======================================================
// SUMMARY SOURCE TABLE
// ======================================================

dtSummary = dtClean;
summaryN = keptN;
summarySourceNote = "Summary/data/histograms use cleaned table after deleting small EPDs.";
summaryUseAllDetected = 0;

Current Data Table( dtSummary );

// Recompute final summary area %, total pore area, and solidity from the cleaned table.
// The raw ImageJ summary values are not used for final report data except image total area.
totalAreaValue = Col Sum( As Column( areaColName ) );
solidityValue = Col Mean( As Column( solidityDataColName ) );
areaPercentValue = 0;
If( !Is Missing( imageTotalAreaValue ) & imageTotalAreaValue > 0,
	areaPercentValue = (totalAreaValue / imageTotalAreaValue) * 100;
);

// ======================================================
// COUNTS FOR SELECTED SUMMARY SOURCE
// ======================================================

rowsEPDAbove01 = dtSummary << Get Rows Where(
	As Column( epdColName ) > epdCutoff1
);

nEPDAbove01 = N Rows( rowsEPDAbove01 );

rowsEPDAbove0025 = dtSummary << Get Rows Where(
	As Column( epdColName ) > epdCutoff2
);

nEPDAbove0025 = N Rows( rowsEPDAbove0025 );

rowsEPDBetween = dt << Get Rows Where(
	As Column( epdColName ) >= epdBetweenLow & As Column( epdColName ) < epdBetweenHigh
);

nEPDBetween = N Rows( rowsEPDBetween );

rowsCircBelow015 = dtSummary << Get Rows Where(
	As Column( circColName ) < circCutoff
);

nCircBelow015 = N Rows( rowsCircBelow015 );

epdAvg = Col Mean( As Column( epdColName ) );
circAvg = Col Mean( As Column( circColName ) );
roundAvg = Col Mean( As Column( roundColName ) );
epdMax = Col Max( As Column( epdColName ) );

// ======================================================
// PERCENTAGES ABOVE / BELOW CUTOFFS
// ======================================================

pctSmallEPDBelow = 0;
If( originalN > 0,
	pctSmallEPDBelow = (nSmallEPD / originalN) * 100;
);

pctEPDAbove01 = 0;
pctEPDAbove0025 = 0;
pctEPDBetween = 0;
pctCircBelow015 = 0;

If( summaryN > 0,
	pctEPDAbove01 = (nEPDAbove01 / summaryN) * 100;
	pctEPDAbove0025 = (nEPDAbove0025 / summaryN) * 100;
	pctCircBelow015 = (nCircBelow015 / summaryN) * 100;
);

If( originalN > 0,
	pctEPDBetween = (nEPDBetween / originalN) * 100;
);

// ======================================================
// FINAL SUMMARY TABLE
// ======================================================

summary = New Table(
	"__BASE_SAFE___Final_Summary",
	Add Rows( 19 ),

	New Column( "Metric", Character, Nominal ),
	New Column( "Value", Numeric, Continuous, Format( "Fixed Dec", 20, 9 ) ),
	New Column( "Notes", Character, Nominal )
);

Column( summary, "Metric" )[1] = "Original pore count";
Column( summary, "Value" )[1] = originalN;
Column( summary, "Notes" )[1] = "Before deleting small EPDs";

Column( summary, "Metric" )[2] = "Count epd(mm) <= " || Char( smallEPDCutoff );
Column( summary, "Value" )[2] = nSmallEPD;
Column( summary, "Notes" )[2] = "Deleted cutoff: epd(mm) <= " || Char( smallEPDCutoff );

Column( summary, "Metric" )[3] = "Summary pore count";
Column( summary, "Value" )[3] = summaryN;
Column( summary, "Notes" )[3] = summarySourceNote;

Column( summary, "Metric" )[4] = "Count epd(mm) > " || Char( epdCutoff1 );
Column( summary, "Value" )[4] = nEPDAbove01;
Column( summary, "Notes" )[4] = "Cutoff 1: " || Char( epdCutoff1 );

Column( summary, "Metric" )[5] = "Count epd(mm) > " || Char( epdCutoff2 );
Column( summary, "Value" )[5] = nEPDAbove0025;
Column( summary, "Notes" )[5] = "Cutoff 2: " || Char( epdCutoff2 );

Column( summary, "Metric" )[6] = "Count epd(mm) between " || Char( epdBetweenLow ) || " and < " || Char( epdBetweenHigh );
Column( summary, "Value" )[6] = nEPDBetween;
Column( summary, "Notes" )[6] = "All detected pores; lower inclusive, upper exclusive";

Column( summary, "Metric" )[7] = "Count circularity < " || Char( circCutoff );
Column( summary, "Value" )[7] = nCircBelow015;
Column( summary, "Notes" )[7] = "Circularity cutoff: " || Char( circCutoff );

Column( summary, "Metric" )[8] = "Average epd(mm)";
Column( summary, "Value" )[8] = epdAvg;
Column( summary, "Notes" )[8] = "Mean EPD after cleaning";

Column( summary, "Metric" )[9] = "Max epd(mm)";
Column( summary, "Value" )[9] = epdMax;
Column( summary, "Notes" )[9] = "Maximum EPD after cleaning";

Column( summary, "Metric" )[10] = "Area %";
Column( summary, "Value" )[10] = areaPercentValue;
Column( summary, "Notes" )[10] = "Computed from cleaned EPD table divided by total image area";

Column( summary, "Metric" )[11] = "Total Area";
Column( summary, "Value" )[11] = totalAreaValue;
Column( summary, "Notes" )[11] = "Sum of pore area from cleaned EPD table";

Column( summary, "Metric" )[12] = "Solidity";
Column( summary, "Value" )[12] = solidityValue;
Column( summary, "Notes" )[12] = "Mean solidity from cleaned EPD table";

Column( summary, "Metric" )[13] = "% epd(mm) <= " || Char( smallEPDCutoff );
Column( summary, "Value" )[13] = pctSmallEPDBelow;
Column( summary, "Notes" )[13] = "Percent of original pore count at or below small-EPD delete cutoff";

Column( summary, "Metric" )[14] = "% epd(mm) > " || Char( epdCutoff1 );
Column( summary, "Value" )[14] = pctEPDAbove01;
Column( summary, "Notes" )[14] = "Percent of cleaned-table pores above EPD cutoff 1";

Column( summary, "Metric" )[15] = "% epd(mm) > " || Char( epdCutoff2 );
Column( summary, "Value" )[15] = pctEPDAbove0025;
Column( summary, "Notes" )[15] = "Percent of cleaned-table pores above EPD cutoff 2";

Column( summary, "Metric" )[16] = "% epd(mm) between " || Char( epdBetweenLow ) || " and < " || Char( epdBetweenHigh );
Column( summary, "Value" )[16] = pctEPDBetween;
Column( summary, "Notes" )[16] = "Percent of all detected pores in selected EPD band";

Column( summary, "Metric" )[17] = "% circularity < " || Char( circCutoff );
Column( summary, "Value" )[17] = pctCircBelow015;
Column( summary, "Notes" )[17] = "Percent of cleaned-table pores below circularity cutoff";

Column( summary, "Metric" )[18] = "Average circularity";
Column( summary, "Value" )[18] = circAvg;
Column( summary, "Notes" )[18] = "Mean circularity from cleaned EPD table";

Column( summary, "Metric" )[19] = "Average roundness";
Column( summary, "Value" )[19] = roundAvg;
Column( summary, "Notes" )[19] = "Mean roundness from cleaned EPD table";

summary << Save( outDir || "Final_Summary.jmp" );
summary << Save( outDir || "Final_Summary.csv" );

dtClean << Save( outDir || "EPD_Cleaned.jmp" );
dtClean << Save( outDir || "EPD_Cleaned.csv" );

// ======================================================
// GRAPH BUILDER HISTOGRAM FUNCTION
// ======================================================

saveGraphBuilderHistogram = Function( {dataTable, columnName, saveName, graphTitle, xAxisTitle, yAxisTitle, requestedBins, xMinSetting, xMaxSetting, xMajorTickSetting, xMinorTickSetting, yMaxSetting, yMajorTickSetting, yMinorTickSetting},
	{gb, reportObj, colRef, histColName, graphDisplayTitle, xAxisDisplayTitle, yAxisDisplayTitle, axisMin, axisMax, axisRange, axisPad, binWidth, binOrigin, axisObj, yAxisObj, frameObj, unitScaleColumn, epdColumn, majorInc, xMinorTicks, yMinorTicks, activeBins},

	Current Data Table( dataTable );

	activeBins = requestedBins;
	If( Is Missing( activeBins ) | activeBins < 1,
		activeBins = histMaxBins
	);
	If( activeBins < 1,
		activeBins = 1
	);

	unitScaleColumn = isUnitScaleHistogramColumn( columnName );
	epdColumn = isEPDHistogramColumn( columnName );

	If( unitScaleColumn == 1,
		// Circularity and roundness are naturally 0..1, but JMP can create an overflow bin
		// for exact 1.0 values. Use a temporary histogram-only column where values are
		// clamped into 0..1 and exact 1.0 is nudged just inside the final bin.
		// Pick a clean temporary column name for the X-axis label.
		// ImageJ may name circularity as "Circularity", "Circ.", or "Circ".
		// The old Contains("circularity") check treated "Circ." as roundness,
		// which made circularity and roundness histograms share the same label.
		If(
			normalizeName( columnName ) == "circularity" |
			normalizeName( columnName ) == "circ",
			histColName = "Circularity Ratio";
		,
			histColName = "Roundness Ratio";
		);
		makeUnitScaleHistogramColumn( dataTable, columnName, histColName );
		colRef = Column( dataTable, histColName );

		axisMin = 0;
		axisMax = 1;
		axisRange = 1;
		binOrigin = 0;

		binWidth = 1 / activeBins;

		// Labels stay readable while optional fixed Bin Span controls the actual bin span.
		majorInc = 0.1;
		xMinorTicks = 4;
	,
		If( epdColumn == 1,
			histColName = "EPD [mm]";
			dataTable << New Column(
				histColName,
				Numeric,
				Continuous,
				Formula( As Column( columnName ) )
			);
			dataTable << Run Formulas;
			Try( Column( dataTable, histColName ) << Delete Formula );
			colRef = Column( dataTable, histColName );
		,
			colRef = Column( dataTable, columnName );
		);

		axisMin = Col Min( As Column( columnName ) );
		axisMax = Col Max( As Column( columnName ) );

		If( Is Missing( axisMin ) | Is Missing( axisMax ),
			axisMin = 0;
			axisMax = 1;
		);

		// EPD cannot be negative. Force the X axis and bin origin to exactly 0.
		// This makes 0 appear at the histogram origin even when the smallest measured pore is > 0.
		If( epdColumn == 1,
			axisMin = 0
		);

		axisRange = axisMax - axisMin;

		If( axisRange <= 0,
			axisPad = Max( Abs( axisMin ) * 0.05, 0.000001 );
			axisMin = axisMin - axisPad;
			axisMax = axisMax + axisPad;
			If( epdColumn == 1,
				axisMin = 0
			);
			axisRange = axisMax - axisMin;
		);

		axisPad = axisRange * histAxisPadPercent / 100;
		If( epdColumn == 1,
			// Keep 0 exactly at the lower-left corner of the EPD histogram.
			// Do not apply any left-side padding; only extend the right side if requested.
			axisMin = 0;
			axisMax = axisMax + axisPad;
		,
			axisMin = axisMin - axisPad;
			axisMax = axisMax + axisPad;
		);
		axisRange = axisMax - axisMin;

		If( epdColumn == 1,
			binOrigin = 0;
		,
			binOrigin = axisMin;
		);
		binWidth = axisRange / activeBins;

		// Use a clean axis increment for EPD so the 0 tick stays visually anchored
		// at the lower-left corner. If the user provides a custom major tick spacing,
		// use it directly; otherwise fall back to automatic clean ticks.
		If( epdColumn == 1,
			If( histEPDMajorTick > 0,
				majorInc = histEPDMajorTick;
				xMinorTicks = 4;
			,
				If( axisMax <= 0.005,
					majorInc = 0.001;
					xMinorTicks = 4;
				,
					If( axisMax <= 0.02,
						majorInc = 0.002;
						xMinorTicks = 4;
					,
						If( axisMax <= 0.06,
							majorInc = 0.01;
							xMinorTicks = 4;
						,
							majorInc = 0.02;
							xMinorTicks = 4;
						);
					);
				);
			);
		,
			majorInc = binWidth;
			xMinorTicks = 4;
		);
	);

	// Apply user-entered axis controls. X max of 0 means auto; Y max of 0 means auto.
	// X min is always honored so EPD can stay anchored at 0 like the reference histogram.
	If( !Is Missing( xMinSetting ) & xMinSetting >= 0,
		axisMin = xMinSetting
	);
	If( !Is Missing( xMaxSetting ) & xMaxSetting > 0,
		axisMax = xMaxSetting
	);
	If( axisMax <= axisMin,
		axisMax = axisMin + Max( Abs( axisMin ) * 0.05, 0.000001 )
	);
	axisRange = axisMax - axisMin;
	binOrigin = axisMin;
	binWidth = axisRange / activeBins;

	If( !Is Missing( xMajorTickSetting ) & xMajorTickSetting > 0,
		majorInc = xMajorTickSetting
	);
	If( !Is Missing( xMinorTickSetting ) & xMinorTickSetting >= 0,
		xMinorTicks = xMinorTickSetting
	);
	If( !Is Missing( yMinorTickSetting ) & yMinorTickSetting >= 0,
		yMinorTicks = yMinorTickSetting
	,
		yMinorTicks = 4
	);

	If( binWidth <= 0 | Is Missing( binWidth ),
		binWidth = 1 / histMaxBins
	);

	graphDisplayTitle = graphTitle;
	If( !histShowGraphTitles,
		graphDisplayTitle = ""
	);

	xAxisDisplayTitle = xAxisTitle;
	yAxisDisplayTitle = yAxisTitle;
	If( !histShowAxisTitles,
		xAxisDisplayTitle = "";
		yAxisDisplayTitle = "";
	);

	gb = Eval(
		Eval Expr(
			dataTable << Graph Builder(
				Size( Expr( histGraphWidth ), Expr( histGraphHeight ) ),
				Show Control Panel( 0 ),
				Show Legend( Expr( histShowLegend ) ),

				Variables(
					X( Expr( colRef ) )
				),

				Elements(
					Histogram( X, Legend( Expr( histShowLegend ) ) )
				),

				SendToReport(
					// Use the actual Graph Builder text boxes, not the OutlineBox title.
					// This keeps graph title, X-axis title, and Y-axis title independent.
					Dispatch(
						{},
						"graph title",
						TextEditBox,
						{Set Text( Expr( graphDisplayTitle ) )}
					),
					Dispatch(
						{},
						"X title",
						TextEditBox,
						{Set Text( Expr( xAxisDisplayTitle ) )}
					),
					Dispatch(
						{},
						"Y title",
						TextEditBox,
						{Set Text( Expr( yAxisDisplayTitle ) )}
					)
				)
			)
		)
	);

	reportObj = gb << Report;

	Wait( 0.2 );

	// Hard-set the X axis after graph creation.
	// Shape histograms are always forced to exactly 0..1.
	// EPD histograms are forced to start at exactly 0.
	Try(
		axisObj = reportObj[AxisBox( 1 )];

		axisObj << Min( axisMin );
		axisObj << Max( axisMax );
		axisObj << Inc( majorInc );
		axisObj << Minor Ticks( xMinorTicks );

		If( histShowAxisTitles,
			Try( axisObj << Show Title( 1 ) );
			Try( axisObj << Set Title( xAxisDisplayTitle ) );
		,
			Try( axisObj << Show Title( 0 ) );
		);

		If( histTrimTrailingZeros,
			// Best format removes trailing zeros, so ticks show 0.01 instead of 0.010000.
			Try( axisObj << Format( "Best", 12 ) );
		,
			If( epdColumn == 1,
				Try( axisObj << Format( "Fixed Dec", 12, 6 ) );
			);
		);

		If( epdColumn == 1 & showEPDCutoffLines,
			// Keep only the colored cutoff lines. Their meanings are stated in the Word-report caption.
			Try( axisObj << Add Ref Line( smallEPDCutoff, "Solid", "Red", "", 1 ) );
			Try( axisObj << Add Ref Line( epdCutoff1, "Solid", "Blue", "", 1 ) );
			Try( axisObj << Add Ref Line( epdCutoff2, "Solid", "Green", "", 1 ) );
		);
	);

	// Optional Y-axis controls. A max or major tick of 0 leaves JMP in automatic mode.
	Try(
		yAxisObj = reportObj[AxisBox( 2 )];
		If( !Is Missing( yMaxSetting ) & yMaxSetting > 0,
			yAxisObj << Min( 0 );
			yAxisObj << Max( yMaxSetting );
		);
		If( !Is Missing( yMajorTickSetting ) & yMajorTickSetting > 0,
			yAxisObj << Inc( yMajorTickSetting );
		);
		Try( yAxisObj << Minor Ticks( yMinorTicks ) );
		If( histShowAxisTitles,
			Try( yAxisObj << Show Title( 1 ) );
			Try( yAxisObj << Set Title( yAxisDisplayTitle ) );
		,
			Try( yAxisObj << Show Title( 0 ) );
		);
	);

	// Optional fixed bin span. When auto binning is enabled, leave JMP's histogram binning automatic.
	// Shape histograms still keep the axis at 0..1, but bin breaks are automatic unless this option is turned off.
	If( !histAutoBinning,
		Try(
			frameObj = reportObj[FrameBox( 1 )];
			frameObj << DispatchSeg( Hist Seg( 1 ), Bin Span( binWidth, binOrigin ) );
		);
	);

	Wait( 0.5 );

	reportObj << Save Picture(
		histDir || saveName || ".png",
		"PNG"
	);

	gb << Close Window;

	// Remove temporary helper columns so the cleaned JMP table stays clean.
	If( unitScaleColumn == 1 | epdColumn == 1,
		Try( dataTable << Delete Columns( histColName ) )
	);
);

// ======================================================
// OPTIONAL EPD HISTOGRAM ROUNDNESS FILTER
// ======================================================

dtEPDHist = dtClean;

If( !beastDisableGraphs,
	
	If( epdHistRoundFilterEnabled,
		rowsEPDHist = dtClean << Get Rows Where(
			As Column( roundColName ) >= epdHistRoundFilterMin
		);
		dtEPDHist = dtClean << Subset(
			Rows( rowsEPDHist ),
			Selected Columns( 0 ),
			Invisible,
			Output Table( "EPD_Histogram_Filtered" )
		);
	);
	
	// ======================================================
	// MAKE GRAPH BUILDER HISTOGRAMS
	// ======================================================
	
	saveGraphBuilderHistogram(
		dtEPDHist,
		epdColName,
		"Histogram_EPD_Distribution_mm",
		"__HIST_EPD_TITLE__",
		histEPDXAxisTitle,
		histEPDYAxisTitle,
		histEPDBins,
		epdAxisMinSetting,
		epdAxisMaxSetting,
		histEPDMajorTick,
		histEPDXMinorTicks,
		epdYAxisMaxSetting,
		epdYAxisMajorTick,
		histEPDYMinorTicks
	);
	
	saveGraphBuilderHistogram(
		dtClean,
		circColName,
		"Circularity_Distribution",
		"__HIST_CIRC_TITLE__",
		histCircXAxisTitle,
		histCircYAxisTitle,
		histCircBins,
		circAxisMinSetting,
		circAxisMaxSetting,
		circXAxisMajorTick,
		histCircXMinorTicks,
		circYAxisMaxSetting,
		circYAxisMajorTick,
		histCircYMinorTicks
	);
	
	saveGraphBuilderHistogram(
		dtClean,
		roundColName,
		"Roundness_Distribution",
		"__HIST_ROUND_TITLE__",
		histRoundXAxisTitle,
		histRoundYAxisTitle,
		histRoundBins,
		roundAxisMinSetting,
		roundAxisMaxSetting,
		roundXAxisMajorTick,
		histRoundXMinorTicks,
		roundYAxisMaxSetting,
		roundYAxisMajorTick,
		histRoundYMinorTicks
	);
	
	
);

// ======================================================
// NOTE FILE
// ======================================================

noteText =
"Auto-generated JMP processing notes\!N" ||
"ImageJ pore results CSV: " || filePath || "\!N" ||
"ImageJ summary CSV: " || summaryFilePath || "\!N" ||
"Output folder: " || outDir || "\!N" ||
"Area column used for EPD: " || areaColName || "\!N" ||
"EPD equation: sqrt((pore area * 4) / pi)\!N" ||
"EPD column created: " || epdColName || "\!N" ||
"Deleted EPD cutoff: epd(mm) <= " || Char( smallEPDCutoff ) || "\!N" ||
"Cleaned table sorted by epd(mm) descending; statistics use it, while the selected between-band count uses all detected pores.\!N" ||
"Counted EPD above: " || Char( epdCutoff1 ) || " and " || Char( epdCutoff2 ) || "\!N" ||
"Counted EPD between: " || Char( epdBetweenLow ) || " to < " || Char( epdBetweenHigh ) || "\!N" ||
"Counted circularity below: " || Char( circCutoff ) || "\!N" ||
"Histogram/graph creation disabled: " || Char( beastDisableGraphs ) || "\!N" ||
"EPD histogram uses cleaned data; its X-axis minimum and bin origin are forced to exactly 0 with no left-side padding. Major ticks can be user-set, or automatic when set to 0.\!N" ||
"Circularity and roundness histograms use the cleaned EPD table after deleting small pores.\!N" ||
"Circularity and roundness are forced to a 0..1 X-axis with bin origin 0; exact 1.0 values are kept inside the final bin.\!N" ||
"Circularity histogram bins: " || Char( histCircBins ) || "\!N" ||
"Roundness histogram bins: " || Char( histRoundBins ) || "\!N" ||
"EPD histogram bins: " || Char( histEPDBins ) || "\!N" ||
"Default/fallback histogram bins: " || Char( histMaxBins ) || "\!N" ||
"Histogram image size px: " || Char( histGraphWidth ) || " x " || Char( histGraphHeight ) || "\!N" ||
"Histogram legend shown: " || Char( histShowLegend ) || "\!N" ||
"Histogram graph titles shown: " || Char( histShowGraphTitles ) || "\!N" ||
"Histogram axis titles shown: " || Char( histShowAxisTitles ) || "\!N" ||
"Histogram auto binning: " || Char( histAutoBinning ) || "\!N" ||
"EPD minor ticks X/Y: " || Char( histEPDXMinorTicks ) || "/" || Char( histEPDYMinorTicks ) || "\!N" ||
"Circularity minor ticks X/Y: " || Char( histCircXMinorTicks ) || "/" || Char( histCircYMinorTicks ) || "\!N" ||
"Roundness minor ticks X/Y: " || Char( histRoundXMinorTicks ) || "/" || Char( histRoundYMinorTicks ) || "\!N" ||
"Histogram trailing-zero trimming enabled: " || Char( histTrimTrailingZeros ) || "\!N" ||
"EPD histogram X range: " || Char( epdAxisMinSetting ) || " to " || Char( epdAxisMaxSetting ) || "\!N" ||
"EPD histogram roundness filter enabled: " || Char( epdHistRoundFilterEnabled ) || ", minimum roundness: " || Char( epdHistRoundFilterMin ) || "\!N" ||
"Histogram X-axis padding percent: " || Char( histAxisPadPercent ) || "\!N" ||
"Close generated JMP windows when finished: " || Char( closeJMPWindowsWhenFinished ) || "\!N";

Save Text File( outDir || "__BASE_SAFE___JMP_Processing_Notes.txt", noteText );
Save Text File( outDir || "JMP_DONE.txt", "JMP script completed." );

// ======================================================
// OPTIONAL JMP WINDOW CLEANUP
// ======================================================

If( closeJMPWindowsWhenFinished,
	// Close only the tables/windows created by this generated script.
	// This leaves the JMP application itself open, but without the run windows cluttering the screen.
	If( epdHistRoundFilterEnabled & !beastDisableGraphs,
		Try( Close( dtEPDHist, NoSave ) )
	);
	Try( Close( summary, NoSave ) );
	Try( Close( dtClean, NoSave ) );
	Try( Close( dt, NoSave ) );
	Try( Close( dtImageJSummary, NoSave ) );
,
	Try( Close( dtImageJSummary, NoSave ) );
	dtClean << Show Window;
	summary << Show Window;
);

Print( "Done. Output folder: " || outDir );

// BEAST MODE workers are one-run processes. Exit cleanly after all files are written.
If( beastExitJMPWhenDone,
    Try( Close All( Data Tables, NoSave ) );
    Try( Close All( Reports, NoSave ) );
    Wait( 0.25 );
    Exit( NoSave );
);
'''

    jsl_text = jsl_template
    jsl_text = jsl_text.replace("__PORE_CSV__", jsl_path(pore_csv))
    jsl_text = jsl_text.replace("__IMAGEJ_SUMMARY_CSV__", jsl_path(imagej_summary_csv))
    jsl_text = jsl_text.replace("__RUN_DIR__", jsl_path(run_dir))
    jsl_text = jsl_text.replace("__HIST_DIR__", jsl_path(hist_dir))
    jsl_text = jsl_text.replace("__BASE_SAFE__", base_safe)
    jsl_text = jsl_text.replace("__SMALL_EPD__", str(settings["small_epd_cutoff"]))
    jsl_text = jsl_text.replace("__EPD_CUTOFF_1__", str(settings["epd_cutoff_1"]))
    jsl_text = jsl_text.replace("__EPD_CUTOFF_2__", str(settings["epd_cutoff_2"]))
    jsl_text = jsl_text.replace("__EPD_BETWEEN_LOW__", str(settings.get("epd_between_low", DEFAULTS["epd_between_low"])))
    jsl_text = jsl_text.replace("__EPD_BETWEEN_HIGH__", str(settings.get("epd_between_high", DEFAULTS["epd_between_high"])))
    jsl_text = jsl_text.replace("__CIRC_CUTOFF__", str(settings["circ_cutoff"]))
    jsl_text = jsl_text.replace("__HIST_MAX_BINS__", str(settings["jmp_hist_max_bins"]))
    jsl_text = jsl_text.replace("__HIST_AUTO_BINNING__", "1" if settings.get("jmp_hist_auto_binning", True) else "0")
    jsl_text = jsl_text.replace("__HIST_EPD_BINS__", str(settings.get("jmp_hist_epd_bins", settings["jmp_hist_max_bins"])))
    jsl_text = jsl_text.replace("__HIST_EPD_MAJOR_TICK__", str(settings.get("jmp_hist_epd_major_tick", 0.0)))
    jsl_text = jsl_text.replace("__HIST_EPD_X_MINOR_TICKS__", str(settings.get("jmp_hist_epd_x_minor_ticks", DEFAULTS["jmp_hist_epd_x_minor_ticks"])))
    jsl_text = jsl_text.replace("__HIST_EPD_Y_MINOR_TICKS__", str(settings.get("jmp_hist_epd_y_minor_ticks", DEFAULTS["jmp_hist_epd_y_minor_ticks"])))
    jsl_text = jsl_text.replace("__HIST_ROUND_BINS__", str(settings.get("jmp_hist_round_bins", settings["jmp_hist_max_bins"])))
    jsl_text = jsl_text.replace("__HIST_ROUND_X_MINOR_TICKS__", str(settings.get("jmp_hist_round_x_minor_ticks", DEFAULTS["jmp_hist_round_x_minor_ticks"])))
    jsl_text = jsl_text.replace("__HIST_ROUND_Y_MINOR_TICKS__", str(settings.get("jmp_hist_round_y_minor_ticks", DEFAULTS["jmp_hist_round_y_minor_ticks"])))
    jsl_text = jsl_text.replace("__HIST_CIRC_BINS__", str(settings.get("jmp_hist_circ_bins", settings["jmp_hist_max_bins"])))
    jsl_text = jsl_text.replace("__HIST_CIRC_X_MINOR_TICKS__", str(settings.get("jmp_hist_circ_x_minor_ticks", DEFAULTS["jmp_hist_circ_x_minor_ticks"])))
    jsl_text = jsl_text.replace("__HIST_CIRC_Y_MINOR_TICKS__", str(settings.get("jmp_hist_circ_y_minor_ticks", DEFAULTS["jmp_hist_circ_y_minor_ticks"])))
    jsl_text = jsl_text.replace("__HIST_AXIS_PAD_PERCENT__", str(settings["jmp_hist_axis_pad_percent"]))
    jsl_text = jsl_text.replace("__SHOW_EPD_CUTOFF_LINES__", "1" if settings.get("jmp_epd_show_cutoff_lines", False) else "0")
    jsl_text = jsl_text.replace("__HIST_GRAPH_WIDTH__", str(settings.get("jmp_hist_graph_width", DEFAULTS["jmp_hist_graph_width"])))
    jsl_text = jsl_text.replace("__HIST_GRAPH_HEIGHT__", str(settings.get("jmp_hist_graph_height", DEFAULTS["jmp_hist_graph_height"])))
    jsl_text = jsl_text.replace("__HIST_SHOW_LEGEND__", "1" if settings.get("jmp_hist_show_legend", True) else "0")
    jsl_text = jsl_text.replace("__HIST_SHOW_GRAPH_TITLES__", "1" if settings.get("jmp_hist_show_graph_titles", True) else "0")
    jsl_text = jsl_text.replace("__HIST_SHOW_AXIS_TITLES__", "1" if settings.get("jmp_hist_show_axis_titles", True) else "0")
    jsl_text = jsl_text.replace("__HIST_TRIM_TRAILING_ZEROS__", "1" if settings.get("jmp_hist_trim_trailing_zeros", True) else "0")
    jsl_text = jsl_text.replace("__HIST_EPD_TITLE__", jsl_string(settings.get("jmp_hist_epd_title", DEFAULTS["jmp_hist_epd_title"])))
    jsl_text = jsl_text.replace("__HIST_EPD_X_AXIS_TITLE__", jsl_string(settings.get("jmp_hist_epd_x_axis_title", DEFAULTS["jmp_hist_epd_x_axis_title"])))
    jsl_text = jsl_text.replace("__HIST_EPD_Y_AXIS_TITLE__", jsl_string(settings.get("jmp_hist_epd_y_axis_title", DEFAULTS["jmp_hist_epd_y_axis_title"])))
    jsl_text = jsl_text.replace("__HIST_ROUND_TITLE__", jsl_string(settings.get("jmp_hist_round_title", DEFAULTS["jmp_hist_round_title"])))
    jsl_text = jsl_text.replace("__HIST_ROUND_X_AXIS_TITLE__", jsl_string(settings.get("jmp_hist_round_x_axis_title", DEFAULTS["jmp_hist_round_x_axis_title"])))
    jsl_text = jsl_text.replace("__HIST_ROUND_Y_AXIS_TITLE__", jsl_string(settings.get("jmp_hist_round_y_axis_title", DEFAULTS["jmp_hist_round_y_axis_title"])))
    jsl_text = jsl_text.replace("__HIST_CIRC_TITLE__", jsl_string(settings.get("jmp_hist_circ_title", DEFAULTS["jmp_hist_circ_title"])))
    jsl_text = jsl_text.replace("__HIST_CIRC_X_AXIS_TITLE__", jsl_string(settings.get("jmp_hist_circ_x_axis_title", DEFAULTS["jmp_hist_circ_x_axis_title"])))
    jsl_text = jsl_text.replace("__HIST_CIRC_Y_AXIS_TITLE__", jsl_string(settings.get("jmp_hist_circ_y_axis_title", DEFAULTS["jmp_hist_circ_y_axis_title"])))
    jsl_text = jsl_text.replace("__HIST_EPD_X_MIN__", str(settings.get("jmp_hist_epd_x_min", 0.0)))
    jsl_text = jsl_text.replace("__HIST_EPD_X_MAX__", str(settings.get("jmp_hist_epd_x_max", 0.0)))
    jsl_text = jsl_text.replace("__HIST_EPD_Y_MAX__", str(settings.get("jmp_hist_epd_y_max", 0.0)))
    jsl_text = jsl_text.replace("__HIST_EPD_Y_MAJOR_TICK__", str(settings.get("jmp_hist_epd_y_major_tick", 0.0)))
    jsl_text = jsl_text.replace("__HIST_ROUND_X_MIN__", str(settings.get("jmp_hist_round_x_min", 0.0)))
    jsl_text = jsl_text.replace("__HIST_ROUND_X_MAX__", str(settings.get("jmp_hist_round_x_max", 1.0)))
    jsl_text = jsl_text.replace("__HIST_ROUND_X_MAJOR_TICK__", str(settings.get("jmp_hist_round_x_major_tick", 0.1)))
    jsl_text = jsl_text.replace("__HIST_ROUND_Y_MAX__", str(settings.get("jmp_hist_round_y_max", 0.0)))
    jsl_text = jsl_text.replace("__HIST_ROUND_Y_MAJOR_TICK__", str(settings.get("jmp_hist_round_y_major_tick", 0.0)))
    jsl_text = jsl_text.replace("__HIST_CIRC_X_MIN__", str(settings.get("jmp_hist_circ_x_min", 0.0)))
    jsl_text = jsl_text.replace("__HIST_CIRC_X_MAX__", str(settings.get("jmp_hist_circ_x_max", 1.0)))
    jsl_text = jsl_text.replace("__HIST_CIRC_X_MAJOR_TICK__", str(settings.get("jmp_hist_circ_x_major_tick", 0.1)))
    jsl_text = jsl_text.replace("__HIST_CIRC_Y_MAX__", str(settings.get("jmp_hist_circ_y_max", 0.0)))
    jsl_text = jsl_text.replace("__HIST_CIRC_Y_MAJOR_TICK__", str(settings.get("jmp_hist_circ_y_major_tick", 0.0)))
    jsl_text = jsl_text.replace("__HIST_EPD_ROUND_FILTER_ENABLED__", "1" if settings.get("jmp_epd_hist_round_filter_enabled", True) else "0")
    jsl_text = jsl_text.replace("__HIST_EPD_ROUND_FILTER_MIN__", str(settings.get("jmp_epd_hist_round_filter_min", 0.15)))
    jsl_text = jsl_text.replace("__SUMMARY_USE_ALL_DETECTED__", "0")
    jsl_text = jsl_text.replace("__CLOSE_JMP_WINDOWS__", "1" if settings.get("close_jmp_windows_when_finished", True) else "0")
    jsl_text = jsl_text.replace("__BEAST_EXIT_JMP__", "1" if (settings.get("beast_mode_enabled", False) or settings.get("_parallel_jmp_auto_exit", False) or settings.get("jmp_force_exit_after_run", False)) else "0")
    jsl_text = jsl_text.replace("__BEAST_DISABLE_GRAPHS__", "1" if settings.get("beast_mode_enabled", False) and settings.get("beast_disable_histograms_and_graphs", True) else "0")

    f = open(jsl_file, "w")
    f.write(jsl_text)
    f.close()

# ======================================================
# ONE IMAGE RUN
# ======================================================

def save_starting_image_for_report(image_path, imp_original, image_dir, base_safe, settings=None):
    # Save the true input image for the DOCX report.
    # IMPORTANT: this uses the source file on disk first, not the thresholded ImageJ window.
    # That prevents the report from accidentally showing an inverted mask/segmented LUT as the original.
    start_png = os.path.join(image_dir, base_safe + "_TRUE_ORIGINAL_INPUT_FOR_REPORT.png")
    start_tif = os.path.join(image_dir, base_safe + "_TRUE_ORIGINAL_INPUT_FOR_REPORT.tif")

    saved_png = False

    # Best path: read the original file bytes through ImageIO and write a fresh PNG.
    # This bypasses ImageJ threshold/LUT state completely.
    try:
        source_img = ImageIO.read(File(image_path))
        if source_img is not None:
            ImageIO.write(source_img, "png", File(start_png))
            saved_png = True
            IJ.log("Saved true report original from disk with ImageIO: " + start_png)
    except Exception as e_imgio:
        IJ.log("ImageIO could not save true report original, falling back to ImageJ copy: " + str(e_imgio))

    # Keep a TIFF copy for traceability unless generated-lossless retention is disabled.
    if settings is None or not no_lossless_generated_images_enabled(settings):
        try:
            start_tif_imp = IJ.openImage(image_path)
            if start_tif_imp is None:
                start_tif_imp = Duplicator().run(imp_original)
            FileSaver(start_tif_imp).saveAsTiff(start_tif)
            try:
                start_tif_imp.changes = False
                start_tif_imp.close()
            except:
                pass
        except:
            pass
    else:
        start_tif = ""

    if not saved_png:
        start_imp = None
        try:
            start_imp = IJ.openImage(image_path)
            if start_imp is None:
                start_imp = Duplicator().run(imp_original)

            start_imp.setTitle(base_safe + "_true_original_input_for_report")
            try:
                start_imp.deleteRoi()
            except:
                pass
            try:
                start_imp.setOverlay(None)
            except:
                pass
            try:
                # Reset only display state, not pixel values. This avoids carrying a threshold LUT into the report.
                start_imp.getProcessor().resetThreshold()
            except:
                pass

            rgb_imp = Duplicator().run(start_imp)
            try:
                IJ.run(rgb_imp, "RGB Color", "")
            except:
                pass
            FileSaver(rgb_imp).saveAsPng(start_png)
            try:
                rgb_imp.changes = False
                rgb_imp.close()
            except:
                pass
            saved_png = True
        finally:
            try:
                if start_imp is not None:
                    start_imp.changes = False
                    start_imp.close()
            except:
                pass

    return start_png, start_tif


def apply_numeric_threshold(mask, settings):
    # Gray mode uses the entered 0-255 limits directly.
    # Percent mode maps the entered 0-100 values through the cumulative histogram of the
    # actual preprocessed 8-bit threshold source. It does not derive threshold % from the
    # final binary mask area fraction.
    threshold_gray_mode = settings.get("threshold_force_8bit_numbers", True)

    try:
        if mask.getBitDepth() != 8:
            IJ.run(mask, "8-bit", "")
    except:
        IJ.run(mask, "8-bit", "")

    ip = mask.getProcessor()
    try:
        ip = ip.convertToByte(True)
    except:
        pass

    threshold_info = threshold_limits_from_processor(
        ip,
        settings["threshold_min"],
        settings["threshold_max"],
        threshold_gray_mode
    )
    if threshold_info is None:
        raise Exception("Could not calculate threshold limits from the preprocessed image histogram.")

    lower = float(threshold_info["lower_gray"])
    upper = float(threshold_info["upper_gray"])

    settings["_threshold_actual_min_gray"] = lower
    settings["_threshold_actual_max_gray"] = upper
    settings["_threshold_histogram_min_percent"] = threshold_info.get("lower_histogram_percent", "")
    settings["_threshold_histogram_max_percent"] = threshold_info.get("upper_histogram_percent", "")
    settings["_threshold_histogram_selected_percent"] = threshold_info.get("selected_histogram_percent", "")
    settings["_threshold_histogram_total_pixels"] = threshold_info.get("total_pixels", "")
    settings["_threshold_percent_basis"] = "Cumulative histogram of the preprocessed 8-bit threshold source"

    width = mask.getWidth()
    height = mask.getHeight()
    total = width * height
    src_pixels = ip.getPixels()
    dst_pixels = zeros(total, 'b')

    # Match the original script behavior: with black_background True, thresholded pores/particles
    # are white foreground pixels on a black background. Analyze Particles uses the same preference.
    if settings.get("black_background", True):
        foreground = -1   # 255 as signed byte
        background = 0
    else:
        foreground = 0
        background = -1   # 255 as signed byte

    for idx in range(total):
        v = src_pixels[idx]
        if v < 0:
            v = v + 256
        if float(v) >= lower and float(v) <= upper:
            dst_pixels[idx] = foreground
        else:
            dst_pixels[idx] = background

    bp = ByteProcessor(width, height, dst_pixels, None)
    mask.setProcessor(mask.getTitle(), bp)
    mask.updateAndDraw()

    # Store the numeric limits on the mask itself for visual/debug consistency.
    try:
        if settings.get("black_background", True):
            mask.getProcessor().setThreshold(255, 255, ImageProcessor.NO_LUT_UPDATE)
        else:
            mask.getProcessor().setThreshold(0, 0, ImageProcessor.NO_LUT_UPDATE)
    except:
        pass

    return threshold_info


def threshold_fit_values(start, end, step, max_items):
    vals = numeric_range(start, end, step)
    if len(vals) > int(max_items):
        vals = vals[:int(max_items)]
    return vals


def make_clean_threshold_source(imp_original, base_safe):
    # Legacy helper: duplicate of the original image converted only to 8-bit.
    # Main analysis now uses the preprocessed threshold source instead.
    clean = Duplicator().run(imp_original)
    clean.setTitle(base_safe + "_clean_threshold_source")
    try:
        if clean.getBitDepth() != 8:
            IJ.run(clean, "8-bit", "")
    except:
        try:
            IJ.run(clean, "8-bit", "")
        except:
            pass
    return clean


def roi_center_from_bounds(roi):
    try:
        b = roi.getBounds()
        return float(b.x) + float(b.width) / 2.0, float(b.y) + float(b.height) / 2.0
    except:
        return 0.0, 0.0


def area_percent_difference(manual_area_mm2, table_area_mm2):
    try:
        manual_f = float(manual_area_mm2)
        table_f = float(table_area_mm2)
        if table_f == 0:
            return ""
        return ((manual_f - table_f) / table_f) * 100.0
    except:
        return ""


def auto_threshold_fit_decision(best, normal_diff_percent, direction_text):
    try:
        msg = "Auto threshold fit result\n\n"
        msg += "Normal selected-pore difference = " + str(normal_diff_percent) + " %\n"
        msg += "Direction used = " + str(direction_text) + "\n"
        msg += "Best threshold min/max = " + str(best.get("best_min", "")) + " / " + str(best.get("best_max", "")) + "\n"
        msg += "Fit ROI area difference = " + str(best.get("area_error_percent_signed", "")) + " %\n"
        msg += "IoU = " + str(best.get("iou", "")) + "\n\n"
        msg += "Accept this auto-fit, redo the fit range, enter a threshold manually, or skip auto-fit."

        options = ["Accept", "Redo Range", "Enter Threshold", "Skip"]
        choice = JOptionPane.showOptionDialog(
            None,
            msg,
            "Auto Threshold Fit",
            JOptionPane.YES_NO_CANCEL_OPTION,
            JOptionPane.QUESTION_MESSAGE,
            None,
            options,
            options[0]
        )

        if choice == 1:
            return "redo"
        if choice == 2:
            return "change"
        if choice == 3 or choice == JOptionPane.CLOSED_OPTION:
            return "skip"
        return "accept"
    except Exception as e:
        IJ.log("Auto-fit decision dialog failed, accepting result: " + str(e))
        return "accept"


def prompt_auto_fit_range(settings, current_start, current_end):
    try:
        gd = GenericDialog("Redo Auto Threshold Fit Range")
        gd.addMessage("Enter the threshold-max sweep range. The step remains 5 selected units (gray levels or histogram percentage points).")
        gd.addNumericField("Threshold max start", float(current_start), 1)
        gd.addNumericField("Threshold max end", float(current_end), 1)
        gd.showDialog()
        if gd.wasCanceled():
            return None, None
        return gd.getNextNumber(), gd.getNextNumber()
    except Exception as e:
        IJ.log("Could not read auto-fit redo range: " + str(e))
        return None, None


def prompt_manual_auto_fit_threshold(best):
    try:
        gd = GenericDialog("Enter Auto-Fit Threshold")
        gd.addMessage("Enter the threshold max to use for the final analysis. Threshold min stays unchanged.")
        gd.addNumericField("Threshold min", float(best.get("best_min", 0.0)), 1)
        gd.addNumericField("Threshold max", float(best.get("best_max", 40.0)), 1)
        gd.showDialog()
        if gd.wasCanceled():
            return None, None
        return gd.getNextNumber(), gd.getNextNumber()
    except Exception as e:
        IJ.log("Could not read manual auto-fit threshold: " + str(e))
        return None, None


def threshold_step_adjustment_decision(current_threshold_max, manual_area_mm2, table_area_mm2, percent_diff, trigger_limit, threshold_gray_mode=True):
    try:
        diff_val = float(percent_diff)
    except:
        diff_val = 0.0

    step_units = "gray levels" if threshold_mode_is_gray(threshold_gray_mode) else "percentage points"
    short_units = "gray" if threshold_mode_is_gray(threshold_gray_mode) else "%"
    recommendation = "Accept current threshold"
    if diff_val > 0:
        recommendation = "Recommended: +5 " + step_units + ", because manual area is larger and increasing threshold increases pore area."
    elif diff_val < 0:
        recommendation = "Recommended: -5 " + step_units + ", because manual area is smaller and decreasing threshold decreases pore area."

    try:
        limit_msg = "Warning limit = +/-" + str(trigger_limit) + "%."
    except:
        limit_msg = ""

    msg = (
        "Manual selected-pore threshold check\n\n"
        "Threshold input mode = " + threshold_input_mode_label(threshold_gray_mode) + "\n"
        "Current threshold max = " + threshold_value_with_equivalent(current_threshold_max, threshold_gray_mode) + "\n"
        "Manual selected pore area = " + str(manual_area_mm2) + " mm^2\n"
        "Matched table pore area = " + str(table_area_mm2) + " mm^2\n"
        "Manual - table % difference = " + str(percent_diff) + "%\n"
        + limit_msg + "\n\n"
        + recommendation + "\n\n"
        "Choose Accept to keep this threshold, or step threshold max by exactly +5 or -5 " + step_units + "."
    )

    try:
        options = ["Accept current", "+5 " + short_units, "-5 " + short_units, "Skip adjust"]
        choice = JOptionPane.showOptionDialog(
            None,
            msg,
            "Manual Selected-Pore Threshold Adjustment",
            JOptionPane.YES_NO_CANCEL_OPTION,
            JOptionPane.QUESTION_MESSAGE,
            None,
            options,
            options[0]
        )
        if choice == 1:
            return "plus"
        if choice == 2:
            return "minus"
        if choice == 3:
            return "skip"
        return "accept"
    except Exception as e:
        IJ.log("Threshold step adjustment dialog failed: " + str(e))
        return "accept"


def run_auto_threshold_fit_sweep_from_rois(work, rois, settings, image_dir, base_safe, suffix):
    if rois is None or len(rois) <= 0:
        IJ.log("Auto threshold fit requested, but no user-selected ROIs were provided.")
        return None

    fit_imp = None
    try:
        width = work.getWidth()
        height = work.getHeight()
        pad = int(settings.get("auto_threshold_fit_roi_padding", 10))

        first_bounds = rois[0].getBounds()
        min_x = int(first_bounds.x)
        min_y = int(first_bounds.y)
        max_x = int(first_bounds.x + first_bounds.width)
        max_y = int(first_bounds.y + first_bounds.height)

        for rr in rois:
            b = rr.getBounds()
            min_x = min(min_x, int(b.x))
            min_y = min(min_y, int(b.y))
            max_x = max(max_x, int(b.x + b.width))
            max_y = max(max_y, int(b.y + b.height))

        x0 = int(max(0, min_x - pad))
        y0 = int(max(0, min_y - pad))
        x1 = int(min(width, max_x + pad))
        y1 = int(min(height, max_y + pad))

        if x1 <= x0 or y1 <= y0:
            IJ.log("Auto threshold fit ROI bounds were invalid.")
            return None

        fit_imp = Duplicator().run(work)
        try:
            if fit_imp.getBitDepth() != 8:
                IJ.run(fit_imp, "8-bit", "")
        except:
            IJ.run(fit_imp, "8-bit", "")

        ip = fit_imp.getProcessor()
        try:
            ip = ip.convertToByte(True)
        except:
            pass

        values = []
        manual_flags = []
        manual_pixels = 0

        for yy in range(y0, y1):
            for xx in range(x0, x1):
                v = ip.getPixel(xx, yy)
                if v < 0:
                    v = v + 256

                inside = False
                for rr in rois:
                    try:
                        if bool(rr.contains(xx, yy)):
                            inside = True
                            break
                    except:
                        pass

                if inside:
                    manual_pixels = manual_pixels + 1
                values.append(int(v))
                manual_flags.append(inside)

        if manual_pixels <= 0:
            IJ.log("Auto threshold fit selected ROI set had zero pixels.")
            return None

        max_tests = int(settings.get("auto_threshold_fit_max_tests", 5000))
        fit_step = 5.0

        if settings.get("auto_threshold_fit_sweep_min", False):
            min_values = threshold_fit_values(
                settings.get("auto_threshold_fit_min_start", settings.get("threshold_min", 0)),
                settings.get("auto_threshold_fit_min_end", settings.get("threshold_min", 0)),
                fit_step,
                max_tests
            )
        else:
            min_values = [float(settings.get("threshold_min", 0))]

        if settings.get("auto_threshold_fit_sweep_max", True):
            max_values = threshold_fit_values(
                settings.get("auto_threshold_fit_max_start", settings.get("threshold_max", 40)),
                settings.get("auto_threshold_fit_max_end", settings.get("threshold_max", 40)),
                fit_step,
                max_tests
            )
        else:
            max_values = [float(settings.get("threshold_max", 40))]

        full_histogram = threshold_histogram_counts_from_processor(ip)
        area_penalty = float(settings.get("auto_threshold_fit_area_penalty", 0.25))
        rows = []
        best = None
        tested = 0
        stopped_by_limit = False

        for lo in min_values:
            for hi in max_values:
                if tested >= max_tests:
                    stopped_by_limit = True
                    break

                input_lower = float(lo)
                input_upper = float(hi)
                if input_upper < input_lower:
                    continue

                if threshold_mode_is_gray(settings.get("threshold_force_8bit_numbers", True)):
                    lower = threshold_input_to_gray(input_lower, True)
                    upper = threshold_input_to_gray(input_upper, True)
                else:
                    lower = threshold_histogram_percentile_to_gray(full_histogram, input_lower)
                    upper = threshold_histogram_percentile_to_gray(full_histogram, input_upper)
                if lower is None or upper is None:
                    continue

                tested = tested + 1
                fg_pixels = 0
                intersection = 0

                for i in range(len(values)):
                    is_fg = (float(values[i]) >= lower and float(values[i]) <= upper)
                    if is_fg:
                        fg_pixels = fg_pixels + 1
                        if manual_flags[i]:
                            intersection = intersection + 1

                union = manual_pixels + fg_pixels - intersection
                if union > 0:
                    iou = float(intersection) / float(union)
                else:
                    iou = 0.0

                area_error = abs(float(fg_pixels) - float(manual_pixels)) / float(manual_pixels)
                signed_area_error_percent = ((float(manual_pixels) - float(fg_pixels)) / float(manual_pixels)) * 100.0
                score = (1.0 - iou) + (area_penalty * area_error)

                rows.append([input_lower, input_upper, lower, upper, score, iou, area_error, signed_area_error_percent, manual_pixels, fg_pixels, intersection, union, len(rois)])

                if best is None or score < best["score"]:
                    best = {
                        "best_min": input_lower,
                        "best_max": input_upper,
                        "best_min_gray": lower,
                        "best_max_gray": upper,
                        "score": score,
                        "iou": iou,
                        "area_error": area_error,
                        "area_error_percent_signed": signed_area_error_percent,
                        "manual_pixels": manual_pixels,
                        "fit_pixels": fg_pixels,
                        "intersection_pixels": intersection,
                        "union_pixels": union,
                        "roi_count": len(rois),
                        "step": fit_step,
                        "tested": tested,
                        "stopped_by_limit": stopped_by_limit,
                        "csv": "",
                        "best_mask_png": "",
                        "best_mask_tif": ""
                    }

            if stopped_by_limit:
                break

        if best is None:
            IJ.log("Auto threshold fit did not test any valid threshold combinations.")
            return None

        safe_suffix = str(suffix)
        if safe_suffix != "" and not safe_suffix.startswith("_"):
            safe_suffix = "_" + safe_suffix

        if settings.get("auto_threshold_fit_save_csv", True):
            csv_path = os.path.join(image_dir, base_safe + safe_suffix + "_auto_threshold_fit_sweep.csv")
            write_csv(
                csv_path,
                ["Threshold min selected units", "Threshold max selected units", "Threshold min 8-bit gray", "Threshold max 8-bit gray", "Score", "IoU", "Area error", "Signed area difference percent", "Manual selected ROI pixels", "Fit pixels", "Intersection pixels", "Union pixels", "User selected ROI count"],
                rows,
                settings.get("csv_decimals", 9)
            )
            best["csv"] = csv_path

        if settings.get("auto_threshold_fit_save_best_mask", True):
            best_mask = Duplicator().run(work)
            best_mask.setTitle(base_safe + safe_suffix + "_auto_threshold_fit_best_mask")
            local_settings = dict(settings)
            local_settings["threshold_min"] = best["best_min"]
            local_settings["threshold_max"] = best["best_max"]
            apply_numeric_threshold(best_mask, local_settings)

            best_tif = os.path.join(image_dir, base_safe + safe_suffix + "_auto_threshold_fit_best_mask.tif")
            best_png = os.path.join(image_dir, base_safe + safe_suffix + "_auto_threshold_fit_best_mask.png")
            if run_image_outputs_enabled(settings):
                FileSaver(best_mask).saveAsTiff(best_tif)
                FileSaver(best_mask).saveAsPng(best_png)
            else:
                best_tif = ""
                best_png = ""
            best["best_mask_tif"] = best_tif
            best["best_mask_png"] = best_png

            try:
                best_mask.changes = False
                best_mask.close()
            except:
                pass

        IJ.log("Auto threshold fit used user-selected ROI count = " + str(best["roi_count"]))
        IJ.log("Auto threshold fit threshold step = " + str(best["step"]) + " selected units")
        IJ.log("Auto threshold fit input mode = " + threshold_input_mode_label(settings.get("threshold_force_8bit_numbers", True)))
        IJ.log("Auto threshold fit best threshold min/max = " + str(best["best_min"]) + " / " + str(best["best_max"]) + "; gray equivalents = " + str(best.get("best_min_gray", "")) + " / " + str(best.get("best_max_gray", "")))
        IJ.log("Auto threshold fit score = " + str(best["score"]) + ", IoU = " + str(best["iou"]) + ", signed area difference % = " + str(best["area_error_percent_signed"]))

        return best

    except Exception as e:
        IJ.log("Auto threshold fit from selected ROIs failed: " + str(e))
        return None

    finally:
        try:
            if fit_imp is not None:
                fit_imp.changes = False
                fit_imp.close()
        except:
            pass


def run_auto_threshold_fit_sweep(work, settings, image_dir, base_safe):
    if not settings.get("auto_threshold_fit_enabled", False):
        return None

    fit_title = base_safe + "_auto_threshold_fit_trace_selected_pores"
    fit_display = None
    rois = []

    try:
        fit_display = Duplicator().run(work)
        fit_display.setTitle(fit_title)
        fit_display.show()

        roi_count = int(settings.get("auto_threshold_fit_roi_count", 1))
        if roi_count < 1:
            roi_count = 1

        for roi_i in range(roi_count):
            pore_num = roi_i + 1
            WaitForUserDialog(
                "Auto Threshold Fit - Trace User Selected Pore " + str(pore_num) + " of " + str(roi_count),
                "Trace the boundary of user-selected pore #" + str(pore_num) + " on the displayed preprocessed threshold-source image.\n\n"
                "Use the freehand/selection tool. Leave the ROI selected, then click OK.\n\n"
                "Auto-fit uses ONLY the pore ROI(s) you trace here. It does not use the automated largest pore unless you manually trace that pore.\n\n"
                "The script sweeps threshold values in steps of 5 and picks the result whose thresholded pixels match your selected ROI(s) best."
            ).show()

            roi_current = fit_display.getRoi()
            if roi_current is None:
                IJ.log("Auto threshold fit: no ROI selected for user-selected pore #" + str(pore_num) + ".")
                continue

            try:
                rois.append(roi_current.clone())
            except:
                rois.append(roi_current)

        if len(rois) <= 0:
            IJ.log("Auto threshold fit was enabled, but no user-selected pore ROIs were selected.")
            return None

        return run_auto_threshold_fit_sweep_from_rois(work, rois, settings, image_dir, base_safe, "")

    except Exception as e:
        IJ.log("Auto threshold fit failed: " + str(e))
        return None

    finally:
        try:
            if fit_display is not None:
                fit_display.changes = False
                fit_display.close()
        except:
            pass



def build_set_measurements_options(settings):
    # Macro tokens follow ImageJ Analyze > Set Measurements.
    # Required core fields are forced so downstream EPD/centroid/shape workflows stay valid.
    mapping = [
        ("measure_area", "area"),
        ("measure_mean", "mean"),
        ("measure_std_dev", "standard"),
        ("measure_mode", "modal"),
        ("measure_min_max", "min"),
        ("measure_centroid", "centroid"),
        ("measure_center_of_mass", "center"),
        ("measure_perimeter", "perimeter"),
        ("measure_bounding_rect", "bounding"),
        ("measure_fit_ellipse", "fit"),
        ("measure_shape_descriptors", "shape"),
        ("measure_feret", "feret's"),
        ("measure_integrated_density", "integrated"),
        ("measure_median", "median"),
        ("measure_skewness", "skewness"),
        ("measure_kurtosis", "kurtosis"),
        ("measure_area_fraction", "area_fraction"),
        ("measure_stack_position", "stack"),
        ("measure_limit_to_threshold", "limit")
    ]
    required = ["measure_area", "measure_centroid", "measure_perimeter", "measure_fit_ellipse", "measure_shape_descriptors"]
    options = []
    for key, token in mapping:
        enabled = bool(settings.get(key, False))
        if key in required:
            enabled = True
        if enabled:
            options.append(token)
    options.append("redirect=None")
    options.append("decimal=" + str(settings.get("imagej_results_precision", 9)))
    return " ".join(options)


def apply_binary_cleanup(mask, settings):
    steps = validate_processing_pipeline_steps(pipeline_steps_from_settings(settings))
    threshold_seen = False
    applied = []
    occurrence_counts = {}
    for pipeline_index, step in enumerate(steps):
        token = str(step.get("operation", ""))
        if token == "threshold":
            threshold_seen = True
            continue
        if not threshold_seen or token not in PROCESS_PIPELINE_BINARY_OPERATIONS or not bool(step.get("enabled", True)):
            continue
        occurrence_counts[token] = occurrence_counts.get(token, 0) + 1
        label = ordinal_text(step.get("slot", pipeline_index + 1)) + " " + pipeline_operation_label(token) + " occurrence " + str(occurrence_counts[token])
        if token in ["fill_holes", "watershed"]:
            count = 1
        else:
            count = max(0, int(step.get("iterations", 0)))
        command_names = {
            "despeckle": "Despeckle", "fill_holes": "Fill Holes", "open": "Open",
            "close": "Close-", "erode": "Erode", "dilate": "Dilate", "watershed": "Watershed"
        }
        for iteration in range(count):
            raise_if_cancel_requested("ordered binary " + token)
            make_imagej_command_target(mask)
            IJ.run(mask, command_names[token], "")
            applied.append(label + (" iteration " + str(iteration + 1) if count > 1 else ""))
    if len(applied) > 0:
        IJ.log("Ordered binary processing applied: " + ", ".join(applied))
    return applied




def analyze_threshold_source(threshold_source, settings, image_dir, base_safe):
    # Threshold/analyze the chosen threshold source and save the standard output names.
    # Re-running this after auto-fit overwrites the segmented/outlines images so the final report uses final thresholds.
    mask = Duplicator().run(threshold_source)
    mask.setTitle(base_safe + "_segmented_mask")

    Prefs.blackBackground = settings["black_background"]
    apply_numeric_threshold(mask, settings)
    apply_binary_cleanup(mask, settings)
    mark_beast_worker_content_progress("BINARY_MASK_READY", str(base_safe))

    try:
        mark_beast_worker_content_progress("FIBER_FIXER_START", str(base_safe))
        settings["_fiber_fixer_result"] = apply_fiber_fixer(mask, threshold_source, settings, image_dir, base_safe)
        mark_beast_worker_content_progress("FIBER_FIXER_COMPLETE", str(base_safe))
    except Exception as fiber_fixer_error:
        if global_cancel_requested():
            raise
        IJ.log("Fiber Fixer failed nonfatally: " + str(fiber_fixer_error))
        settings["_fiber_fixer_result"] = {
            "enabled": bool(settings.get("fiber_fixer_enabled", False)),
            "applied": False,
            "applied_pixel_count": 0,
            "wire_pixel_count": 0,
            "error": str(fiber_fixer_error)
        }

    settings["_large_pore_repair_analysis_pass"] = int(settings.get("_large_pore_repair_analysis_pass", 0)) + 1
    try:
        mark_beast_worker_content_progress("LARGE_PORE_REPAIR_START", str(base_safe))
        settings["_large_pore_repair_result"] = apply_conservative_large_pore_repair(mask, settings, image_dir, base_safe)
        mark_beast_worker_content_progress("LARGE_PORE_REPAIR_COMPLETE", str(base_safe))
    except Exception as large_pore_error:
        if global_cancel_requested():
            raise
        IJ.log("Large Pore Repair failed nonfatally: " + str(large_pore_error))
        settings["_large_pore_repair_result"] = {
            "enabled": bool(settings.get("large_pore_repair_enabled", False)),
            "mode_used": "Failed nonfatally",
            "accepted_count": 0,
            "repaired_pixels": 0,
            "repairs": [],
            "error": str(large_pore_error)
        }

    segmented_tif = os.path.join(image_dir, base_safe + "_segmented_mask.tif")
    segmented_png = os.path.join(image_dir, base_safe + "_segmented_mask.png")

    if run_image_outputs_enabled(settings):
        if not no_lossless_generated_images_enabled(settings):
            FileSaver(mask).saveAsTiff(segmented_tif)
        else:
            segmented_tif = ""
        FileSaver(mask).saveAsPng(segmented_png)
        mark_beast_worker_content_progress("SEGMENTED_IMAGE_WRITTEN", str(segmented_png))
    else:
        segmented_tif = ""
        segmented_png = ""

    IJ.run("Clear Results")

    try:
        ResultsTable.setPrecision(int(settings["imagej_results_precision"]))
    except:
        pass

    set_measurements_options = build_set_measurements_options(settings)
    IJ.log("Set Measurements options: " + set_measurements_options)
    IJ.run("Set Measurements...", set_measurements_options)

    size_range = str(settings["particle_size_min"]) + "-" + str(settings["particle_size_max"])
    circ_range = str(settings["particle_circ_min"]) + "-" + str(settings["particle_circ_max"])

    old_image_ids = WindowManager.getIDList()
    old_ids = []
    if old_image_ids is not None:
        for oid in old_image_ids:
            old_ids.append(int(oid))

    analyze_options = "size=" + size_range + " circularity=" + circ_range + " show=Outlines display clear summarize"
    if settings.get("particle_include_holes", False):
        analyze_options += " include"
    if settings.get("particle_exclude_edges", False):
        analyze_options += " exclude"

    IJ.log("Analyze Particles options: " + analyze_options)
    mark_beast_worker_content_progress("ANALYZE_PARTICLES_START", str(base_safe))

    IJ.run(
        mask,
        "Analyze Particles...",
        analyze_options
    )

    rt = ResultsTable.getResultsTable()
    particle_count = rt.size()
    mark_beast_worker_content_progress("ANALYZE_PARTICLES_COMPLETE", str(particle_count))

    outlines_tif = os.path.join(image_dir, base_safe + "_numbered_outlines.tif")
    outlines_png = os.path.join(image_dir, base_safe + "_numbered_outlines.png")

    outline = None
    new_image_ids = WindowManager.getIDList()
    if new_image_ids is not None:
        for nid in new_image_ids:
            img_id = int(nid)
            if img_id not in old_ids:
                candidate = WindowManager.getImage(img_id)
                if candidate is not None:
                    title = str(candidate.getTitle()).lower()
                    if "drawing" in title or "outline" in title:
                        outline = candidate
                        break
        if outline is None:
            for nid in new_image_ids:
                img_id = int(nid)
                if img_id not in old_ids:
                    candidate = WindowManager.getImage(img_id)
                    if candidate is not None:
                        outline = candidate
                        break

    if outline is None:
        outline = IJ.createImage(base_safe + "_numbered_outlines", "8-bit white", mask.getWidth(), mask.getHeight(), 1)
    else:
        outline.setTitle(base_safe + "_numbered_outlines")

    if run_image_outputs_enabled(settings):
        if not no_lossless_generated_images_enabled(settings):
            FileSaver(outline).saveAsTiff(outlines_tif)
        else:
            outlines_tif = ""
        FileSaver(outline).saveAsPng(outlines_png)
    else:
        outlines_tif = ""
        outlines_png = ""

    return mask, segmented_tif, segmented_png, outline, outlines_tif, outlines_png, rt, particle_count


def build_weird_pore_rows(rt, cal, area_to_mm2, settings):
    rows = []
    if not settings.get("flag_weird_pores_enabled", False):
        return rows

    headings = get_headings(rt)
    circ_heading = find_heading_case_insensitive(headings, ["Circularity", "Circ", "Circ."])
    round_heading = find_heading_case_insensitive(headings, ["Roundness", "Round"])

    epd_high = float(settings.get("flag_weird_epd_above", 0.1))
    circ_low = float(settings.get("flag_weird_circularity_below", 0.15))
    round_low = float(settings.get("flag_weird_roundness_below", 0.15))
    round_high = float(settings.get("flag_weird_roundness_above", 0.95))

    try:
        rows_n = rt.size()
    except:
        rows_n = 0

    for r in range(rows_n):
        reasons = []
        area_raw = rt_value(rt, "Area", r)
        if area_raw is None:
            continue

        area_mm2 = float(area_raw) * area_to_mm2
        epd_mm = 0.0
        if area_mm2 > 0:
            epd_mm = math.sqrt((area_mm2 * 4.0) / math.pi)

        # Weird/outlier table follows the same cleaned-EPD rule as the JMP summaries/histograms.
        if epd_mm <= float(settings.get("small_epd_cutoff", 0.003)):
            continue

        circ = None
        if circ_heading != "":
            circ = rt_value(rt, circ_heading, r)

        roundness = None
        if round_heading != "":
            roundness = rt_value(rt, round_heading, r)

        if epd_mm > epd_high:
            reasons.append("EPD > " + str(epd_high) + " mm")

        try:
            if circ is not None and float(circ) < circ_low:
                reasons.append("Circularity < " + str(circ_low))
        except:
            pass

        try:
            if roundness is not None and float(roundness) < round_low:
                reasons.append("Roundness < " + str(round_low))
            if roundness is not None and float(roundness) > round_high:
                reasons.append("Roundness > " + str(round_high))
        except:
            pass

        if len(reasons) > 0:
            x_val = rt_value(rt, "X", r)
            y_val = rt_value(rt, "Y", r)
            rows.append([r + 1, epd_mm, area_mm2, "" if circ is None else circ, "" if roundness is None else roundness, "" if x_val is None else x_val, "" if y_val is None else y_val, "; ".join(reasons)])

    return rows
