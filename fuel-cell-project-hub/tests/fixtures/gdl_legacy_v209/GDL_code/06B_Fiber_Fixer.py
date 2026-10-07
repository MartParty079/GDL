# YOURE A BETA GDL Analysis v193 - Fiber Fixer
#
# A fixed fiber wireframe is generated ONCE per selected input before sweep
# combinations begin. The source is the original/crop image converted to 8-bit,
# using an absolute pore threshold of 0-40; the complementary black phase is
# treated as the intact fiber network. That fiber phase is skeletonized and
# expanded to a 3-pixel-wide network. The same cached network
# is burned into every higher-threshold segmented mask for that input.

import hashlib


def build_fiber_fixer_default_result(settings):
    return {
        "enabled": bool(settings.get("fiber_fixer_enabled", False)),
        "applied": False,
        "threshold_max_used": settings.get("fiber_fixer_absolute_threshold_max", 40),
        "wire_width_px": settings.get("fiber_fixer_wire_width_px", 3),
        "applied_pixel_count": 0,
        "wire_pixel_count": 0,
        "source_image_path": "",
        "internal_white_wireframe_tif": "",
        "wireframe_mask_tif": "",
        "wireframe_mask_png": "",
        "preview_overlay_tif": "",
        "preview_overlay_png": "",
        "error": ""
    }


def _fiber_fixer_normalized_path(path):
    try:
        return os.path.normcase(os.path.abspath(str(path)))
    except:
        return str(path)


def _fiber_fixer_cache_key(path):
    normalized = _fiber_fixer_normalized_path(path)
    try:
        digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()[:10]
    except:
        digest = str(abs(hash(normalized)))
    base = short_safe_name(os.path.splitext(os.path.basename(str(path)))[0], 40)
    return base + "_" + digest


def _fiber_fixer_cache_paths(image_path, output_root):
    cache_dir = os.path.join(output_root, "Fiber Fixer Masks")
    ensure_dir(cache_dir)
    key = _fiber_fixer_cache_key(image_path)
    return {
        "cache_dir": cache_dir,
        "internal_white_wireframe_tif": os.path.join(cache_dir, key + "_fiber_wireframe_internal_white.tif"),
        "wireframe_mask_tif": os.path.join(cache_dir, key + "_fiber_wireframe_mask.tif"),
        "wireframe_mask_png": os.path.join(cache_dir, key + "_fiber_wireframe_mask.png"),
        "preview_overlay_tif": os.path.join(cache_dir, key + "_fiber_wireframe_preview.tif"),
        "preview_overlay_png": os.path.join(cache_dir, key + "_fiber_wireframe_preview.png")
    }


def _fiber_fixer_count_white_pixels(imp):
    ip = imp.getProcessor()
    width = imp.getWidth()
    height = imp.getHeight()
    total = 0
    for yy in range(height):
        if yy % 64 == 0:
            mark_beast_worker_busy_progress("FIBER_FIXER_PIXEL_COUNT", "row=" + str(yy) + "/" + str(height), 15.0)
        for xx in range(width):
            if ip.get(xx, yy) > 127:
                total += 1
    return total


def _fiber_fixer_make_threshold40_fiber_binary(source_imp, threshold_max):
    fibers = Duplicator().run(source_imp)
    fibers.setTitle(source_imp.getTitle() + "_fiber_threshold_40")
    try:
        if fibers.getBitDepth() != 8:
            IJ.run(fibers, "8-bit", "")
    except:
        IJ.run(fibers, "8-bit", "")

    ip = fibers.getProcessor()
    ip.setThreshold(0, int(threshold_max), ImageProcessor.NO_LUT_UPDATE)
    old_black_background = Prefs.blackBackground
    try:
        # Selected dark fibers become WHITE foreground on BLACK background.
        Prefs.blackBackground = True
        IJ.run(fibers, "Convert to Mask", "")
    finally:
        Prefs.blackBackground = old_black_background

    # The 0-40 selected phase is the dark pore phase. Convert the complementary
    # black phase into WHITE foreground so Skeletonize traces the complete fiber
    # network rather than the pore centers.
    white_count = _fiber_fixer_count_white_pixels(fibers)
    total_pixels = fibers.getWidth() * fibers.getHeight()
    if white_count > int(total_pixels * 0.60):
        # Safety for a reversed Convert-to-Mask preference: restore pores white.
        IJ.run(fibers, "Invert", "")
    IJ.run(fibers, "Invert", "")
    return fibers


def _fiber_fixer_make_three_pixel_wireframe(fiber_binary_imp):
    wire = Duplicator().run(fiber_binary_imp)
    wire.setTitle(fiber_binary_imp.getTitle() + "_skeleton_3px")
    old_black_background = Prefs.blackBackground
    try:
        Prefs.blackBackground = True
        IJ.run(wire, "Skeletonize", "")
        # A one-pixel skeleton dilated once becomes approximately 3 pixels wide.
        IJ.run(wire, "Dilate", "")
    finally:
        Prefs.blackBackground = old_black_background
    return wire


def _fiber_fixer_visible_black_mask(white_wire_imp, title):
    out = Duplicator().run(white_wire_imp)
    out.setTitle(title)
    IJ.run(out, "Invert", "")
    return out


def _fiber_fixer_preview_on_original(source_imp, white_wire_imp, title):
    preview = Duplicator().run(source_imp)
    preview.setTitle(title)
    try:
        IJ.run(preview, "RGB Color", "")
    except:
        pass
    rgb = preview.getProcessor()
    rgb.setColor(Color.red)
    wire_ip = white_wire_imp.getProcessor()
    width = preview.getWidth()
    height = preview.getHeight()
    for yy in range(height):
        if yy % 64 == 0:
            mark_beast_worker_busy_progress("FIBER_FIXER_PREVIEW", "row=" + str(yy) + "/" + str(height), 15.0)
        for xx in range(width):
            if wire_ip.get(xx, yy) > 127:
                rgb.drawPixel(xx, yy)
    return preview


def _fiber_fixer_existing_cache_entry(image_path, output_root):
    paths = _fiber_fixer_cache_paths(image_path, output_root)
    if os.path.exists(paths["internal_white_wireframe_tif"]):
        result = build_fiber_fixer_default_result({})
        result.update(paths)
        result["source_image_path"] = str(image_path)
        result["threshold_max_used"] = 40
        result["wire_width_px"] = 3
        result["applied"] = False
        return result
    return None


def prepare_fiber_fixer_for_image(image_path, output_root, settings):
    if not bool(settings.get("fiber_fixer_enabled", False)):
        return build_fiber_fixer_default_result(settings)

    cache = settings.get("_fiber_fixer_pre_sweep_cache", None)
    if cache is None or not isinstance(cache, dict):
        cache = {}
        settings["_fiber_fixer_pre_sweep_cache"] = cache

    normalized_path = _fiber_fixer_normalized_path(image_path)
    if normalized_path in cache:
        return cache[normalized_path]

    existing = _fiber_fixer_existing_cache_entry(image_path, output_root)
    if existing is not None:
        cache[normalized_path] = existing
        return existing

    result = build_fiber_fixer_default_result(settings)
    result["source_image_path"] = str(image_path)
    source = None
    fiber_binary = None
    wire = None
    visible = None
    preview = None
    try:
        source = IJ.openImage(str(image_path))
        if source is None:
            raise Exception("Could not open Fiber Fixer source image: " + str(image_path))

        threshold_max = int(settings.get("fiber_fixer_absolute_threshold_max", 40))
        threshold_max = max(0, min(255, threshold_max))
        result["threshold_max_used"] = threshold_max
        result["wire_width_px"] = 3

        paths = _fiber_fixer_cache_paths(image_path, output_root)
        result.update(paths)

        fiber_binary = _fiber_fixer_make_threshold40_fiber_binary(source, threshold_max)
        wire = _fiber_fixer_make_three_pixel_wireframe(fiber_binary)
        result["wire_pixel_count"] = _fiber_fixer_count_white_pixels(wire)

        # Internal white-on-black mask is used for fast burn-in during every run.
        FileSaver(wire).saveAsTiff(result["internal_white_wireframe_tif"])

        visible = _fiber_fixer_visible_black_mask(wire, "Fiber Fixer wireframe mask")
        FileSaver(visible).saveAsTiff(result["wireframe_mask_tif"])
        FileSaver(visible).saveAsPng(result["wireframe_mask_png"])

        if bool(settings.get("fiber_fixer_save_preview_overlay", True)):
            preview = _fiber_fixer_preview_on_original(source, wire, "Fiber Fixer pre-sweep preview")
            FileSaver(preview).saveAsTiff(result["preview_overlay_tif"])
            FileSaver(preview).saveAsPng(result["preview_overlay_png"])

        cache[normalized_path] = result
        IJ.log(
            "Fiber Fixer pre-sweep mask prepared: image=" + str(image_path) +
            "; threshold=0-" + str(threshold_max) +
            "; wire width=3 px" +
            "; wire pixels=" + str(result["wire_pixel_count"]) +
            "; mask=" + str(result["wireframe_mask_png"])
        )
        return result
    except Exception as e:
        result["error"] = str(e)
        cache[normalized_path] = result
        IJ.log("Fiber Fixer pre-sweep preparation failed: " + str(e))
        return result
    finally:
        for imp in [source, fiber_binary, wire, visible, preview]:
            try:
                if imp is not None:
                    imp.changes = False
                    imp.close()
            except:
                pass


def prepare_fiber_fixer_before_sweeps(input_items, output_root, settings):
    if not bool(settings.get("fiber_fixer_enabled", False)):
        return
    if settings.get("_fiber_fixer_pre_sweep_cache", None) is None:
        settings["_fiber_fixer_pre_sweep_cache"] = {}
    IJ.showStatus("Fiber Fixer: building fixed threshold-40 masks before sweeps...")
    for item in input_items:
        if global_cancel_requested():
            raise Exception("Canceled while preparing Fiber Fixer masks.")
        image_path = item.get("path", "") if isinstance(item, dict) else str(item)
        if image_path != "":
            prepare_fiber_fixer_for_image(image_path, output_root, settings)
    IJ.showStatus("Fiber Fixer pre-sweep masks ready.")


def _fiber_fixer_apply_wireframe(main_mask_imp, white_wire_imp):
    if (
        main_mask_imp.getWidth() != white_wire_imp.getWidth() or
        main_mask_imp.getHeight() != white_wire_imp.getHeight()
    ):
        raise Exception(
            "Fiber Fixer mask size does not match segmented image: " +
            str(white_wire_imp.getWidth()) + "x" + str(white_wire_imp.getHeight()) +
            " versus " + str(main_mask_imp.getWidth()) + "x" + str(main_mask_imp.getHeight())
        )
    main_ip = main_mask_imp.getProcessor()
    wire_ip = white_wire_imp.getProcessor()
    width = main_mask_imp.getWidth()
    height = main_mask_imp.getHeight()
    changed = 0
    for yy in range(height):
        if yy % 64 == 0:
            mark_beast_worker_busy_progress("FIBER_FIXER_APPLY", "row=" + str(yy) + "/" + str(height), 15.0)
        for xx in range(width):
            if wire_ip.get(xx, yy) > 127 and main_ip.get(xx, yy) != 0:
                main_ip.set(xx, yy, 0)
                changed += 1
    main_mask_imp.updateAndDraw()
    return changed


def apply_fiber_fixer(mask, threshold_source, settings, image_dir, base_safe):
    result = build_fiber_fixer_default_result(settings)
    if not bool(settings.get("fiber_fixer_enabled", False)):
        return result

    image_path = settings.get("_fiber_fixer_current_image_path", "")
    output_root = settings.get("_fiber_fixer_output_root", "")
    wire = None
    try:
        cached = prepare_fiber_fixer_for_image(image_path, output_root, settings)
        result.update(cached)
        internal_path = result.get("internal_white_wireframe_tif", "")
        if internal_path == "" or not os.path.exists(internal_path):
            raise Exception("Cached Fiber Fixer wireframe was not created.")
        wire = IJ.openImage(internal_path)
        if wire is None:
            raise Exception("Could not open cached Fiber Fixer wireframe: " + internal_path)
        result["applied_pixel_count"] = _fiber_fixer_apply_wireframe(mask, wire)
        result["applied"] = result["applied_pixel_count"] > 0
        IJ.log(
            "Fiber Fixer applied cached pre-sweep mask: threshold=0-" +
            str(result.get("threshold_max_used", 40)) +
            "; width=3 px" +
            "; changed pixels=" + str(result["applied_pixel_count"])
        )
    except Exception as e:
        result["error"] = str(e)
        IJ.log("Fiber Fixer failed nonfatally: " + str(e))
    finally:
        try:
            if wire is not None:
                wire.changes = False
                wire.close()
        except:
            pass
    return result
