# -*- coding: utf-8 -*-
# MODULE 06A: Conservative large-pore repair helpers
# Loaded before threshold analysis so analyze_threshold_source can call these functions.
# ======================================================
# CONSERVATIVE LARGE-PORE REPAIR
# ======================================================

def large_pore_pixel_image(title, ip):
    imp = ImagePlus(title, ip)
    cal = Calibration()
    cal.pixelWidth = 1.0
    cal.pixelHeight = 1.0
    cal.pixelDepth = 1.0
    cal.setUnit("pixel")
    imp.setCalibration(cal)
    return imp


def large_pore_count_white_in_roi(ip, roi):
    bounds = roi.getBounds()
    total = 0
    for y in range(bounds.y, bounds.y + bounds.height):
        if (y - bounds.y) % 32 == 0:
            mark_beast_worker_busy_progress("LARGE_PORE_ROI_SCAN", "row=" + str(y - bounds.y) + "/" + str(bounds.height), 15.0)
        for x in range(bounds.x, bounds.x + bounds.width):
            if roi.contains(x, y) and ip.get(x, y) > 127:
                total += 1
    return total


def large_pore_parent_rois(ip, minimum_area, include_edges):
    work_ip = ip.duplicate()
    work_ip.setThreshold(255, 255, ImageProcessor.NO_LUT_UPDATE)
    work_imp = large_pore_pixel_image("temporary_large_pore_parents", work_ip)
    manager = RoiManager(False)
    ParticleAnalyzer.setRoiManager(manager)
    table = ResultsTable()
    options = ParticleAnalyzer.ADD_TO_MANAGER
    if not include_edges:
        options = options | ParticleAnalyzer.EXCLUDE_EDGE_PARTICLES
    analyzer = ParticleAnalyzer(options, Measurements.AREA | Measurements.RECT, table, float(minimum_area), float("inf"))
    analyzer.analyze(work_imp)
    parents = []
    for roi in manager.getRoisAsArray():
        area = large_pore_count_white_in_roi(ip, roi)
        if area >= int(minimum_area):
            parents.append((area, roi.clone()))
    parents.sort(key=lambda item: item[0], reverse=True)
    try:
        manager.reset()
        manager.close()
        ParticleAnalyzer.setRoiManager(None)
    except:
        pass
    return parents


def large_pore_crop_parent(global_ip, parent_roi, margin):
    bounds = parent_roi.getBounds()
    crop_x = max(0, bounds.x - int(margin))
    crop_y = max(0, bounds.y - int(margin))
    crop_x2 = min(global_ip.getWidth(), bounds.x + bounds.width + int(margin))
    crop_y2 = min(global_ip.getHeight(), bounds.y + bounds.height + int(margin))
    crop_width = crop_x2 - crop_x
    crop_height = crop_y2 - crop_y
    local_ip = ByteProcessor(crop_width, crop_height)
    local_ip.setValue(0)
    local_ip.fill()
    for local_y in range(crop_height):
        if local_y % 32 == 0:
            mark_beast_worker_busy_progress("LARGE_PORE_CROP_SCAN", "row=" + str(local_y) + "/" + str(crop_height), 15.0)
        global_y = crop_y + local_y
        for local_x in range(crop_width):
            global_x = crop_x + local_x
            if parent_roi.contains(global_x, global_y) and global_ip.get(global_x, global_y) > 127:
                local_ip.set(local_x, local_y, 255)
    return local_ip, crop_x, crop_y


def large_pore_roi_points(candidate_ip, roi):
    bounds = roi.getBounds()
    points = []
    for y in range(bounds.y, bounds.y + bounds.height):
        if (y - bounds.y) % 32 == 0:
            mark_beast_worker_busy_progress("LARGE_PORE_CANDIDATE_SCAN", "row=" + str(y - bounds.y) + "/" + str(bounds.height), 15.0)
        for x in range(bounds.x, bounds.x + bounds.width):
            if roi.contains(x, y) and candidate_ip.get(x, y) > 127:
                points.append((x, y))
    return points


def large_pore_candidate_components(candidate_ip, minimum_area, maximum_area):
    work_ip = candidate_ip.duplicate()
    work_ip.setThreshold(255, 255, ImageProcessor.NO_LUT_UPDATE)
    work_imp = large_pore_pixel_image("temporary_large_pore_candidates", work_ip)
    manager = RoiManager(False)
    ParticleAnalyzer.setRoiManager(manager)
    table = ResultsTable()
    options = ParticleAnalyzer.ADD_TO_MANAGER | ParticleAnalyzer.EXCLUDE_EDGE_PARTICLES
    analyzer = ParticleAnalyzer(options, Measurements.AREA | Measurements.RECT, table, float(minimum_area), float(maximum_area))
    analyzer.analyze(work_imp)
    components = []
    for roi in manager.getRoisAsArray():
        points = large_pore_roi_points(candidate_ip, roi)
        area = len(points)
        if area >= int(minimum_area) and area <= int(maximum_area):
            components.append((area, points, roi.clone()))
    components.sort(key=lambda item: item[0])
    try:
        manager.reset()
        manager.close()
        ParticleAnalyzer.setRoiManager(None)
    except:
        pass
    return components


def large_pore_white_component_areas(ip):
    work_ip = ip.duplicate()
    work_ip.setThreshold(255, 255, ImageProcessor.NO_LUT_UPDATE)
    work_imp = large_pore_pixel_image("temporary_large_pore_split_test", work_ip)
    table = ResultsTable()
    analyzer = ParticleAnalyzer(0, Measurements.AREA, table, 1.0, float("inf"))
    analyzer.analyze(work_imp)
    areas = []
    for row in range(table.getCounter()):
        try:
            areas.append(int(round(table.getValue("Area", row))))
        except:
            pass
    areas.sort(reverse=True)
    return areas


def large_pore_apply_black_points(ip, points):
    for x, y in points:
        ip.set(x, y, 0)


def large_pore_point_span(points):
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return max(max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)


def large_pore_translate_roi(local_roi, offset_x, offset_y):
    translated = local_roi.clone()
    bounds = translated.getBounds()
    translated.setLocation(bounds.x + int(offset_x), bounds.y + int(offset_y))
    return translated


def large_pore_style_roi(roi, fill_overlay, preview=False):
    styled = roi.clone()
    styled.setStrokeColor(Color.red)
    styled.setStrokeWidth(2.0)
    if preview or fill_overlay:
        styled.setFillColor(Color(255, 0, 0, 105 if preview else 90))
    return styled


def large_pore_rebuild_overlay(mask, accepted_overlay, preview_roi=None):
    combined = Overlay()
    try:
        for roi in accepted_overlay.toArray():
            combined.add(roi)
    except:
        pass
    if preview_roi is not None:
        combined.add(preview_roi)
    mask.setOverlay(combined)
    mask.updateAndDraw()


def large_pore_write_csv(path, repairs):
    writer_file = None
    try:
        writer_file = open(path, "wb")
        writer = csv.writer(writer_file)
        writer.writerow(["Repair", "Search profile", "Parent rank", "Parent area px", "Closing radius px", "Repair area px", "Repair percent parent", "Repair span px", "Larger child px", "Smaller child px", "Smaller child percent"])
        for index, repair in enumerate(repairs):
            writer.writerow([
                index + 1,
                repair.get("search_profile", "Standard"),
                repair.get("parent_rank", ""),
                repair.get("parent_area", ""),
                repair.get("radius", ""),
                repair.get("repair_area", ""),
                repair.get("repair_fraction", 0.0) * 100.0,
                repair.get("repair_span", ""),
                repair.get("larger_child", ""),
                repair.get("smaller_child", ""),
                repair.get("smaller_fraction", 0.0) * 100.0
            ])
        return path
    except Exception as e:
        IJ.log("Could not save large-pore repair CSV: " + str(e))
        return ""
    finally:
        if writer_file is not None:
            try:
                writer_file.close()
            except:
                pass


def apply_conservative_large_pore_repair(mask, settings, image_dir, base_safe):
    result = {
        "enabled": bool(settings.get("large_pore_repair_enabled", False)),
        "mode_requested": str(settings.get("large_pore_repair_mode", "Review proposals")),
        "mode_used": "Off",
        "accepted_count": 0,
        "largest_rescue_accepted_count": 0,
        "green_target_accepted_count": 0,
        "green_spur_accepted_count": 0,
        "green_target_parent_count": 0,
        "reviewed_count": 0,
        "proposal_count": 0,
        "repaired_pixels": 0,
        "parent_count": 0,
        "repairs": [],
        "red_overlay_png": "",
        "repair_mask_tif": "",
        "repair_csv": "",
        "review_canceled": False
    }
    if not result["enabled"]:
        return result
    if not settings.get("black_background", True):
        IJ.log("Large Pore Repair skipped: black fibers / white pores are required.")
        result["mode_used"] = "Skipped: incompatible polarity"
        return result

    corrected_ip = mask.getProcessor().convertToByte(False)
    corrected_ip.threshold(127)
    mask.setProcessor(mask.getTitle(), corrected_ip)

    minimum_parent_area = max(1, int(settings.get("large_pore_repair_min_parent_area_px", 10000)))
    parent_limit = max(1, int(settings.get("large_pore_repair_largest_pore_limit", 25)))
    minimum_child_area = max(1, int(settings.get("large_pore_repair_min_child_area_px", 2000)))
    minimum_smaller_fraction = max(0.0, min(0.49, float(settings.get("large_pore_repair_min_smaller_child_fraction", 0.15))))
    maximum_larger_fraction = max(0.51, min(1.0, float(settings.get("large_pore_repair_max_larger_child_fraction", 0.85))))
    minimum_radius = max(1, int(settings.get("large_pore_repair_min_closing_radius_px", 1)))
    maximum_radius = max(minimum_radius, int(settings.get("large_pore_repair_max_closing_radius_px", 10)))
    radius_step = max(1, int(settings.get("large_pore_repair_radius_step_px", 1)))
    minimum_repair_area = max(1, int(settings.get("large_pore_repair_min_area_px", 2)))
    maximum_repair_area = max(minimum_repair_area, int(settings.get("large_pore_repair_max_area_px", 150)))
    maximum_repair_fraction = max(0.000001, float(settings.get("large_pore_repair_max_fraction_of_parent", 0.01)))
    maximum_repair_span = max(1, int(settings.get("large_pore_repair_max_span_px", 25)))
    crop_margin = max(0, int(settings.get("large_pore_repair_crop_margin_px", 12)))
    maximum_repairs = max(1, int(settings.get("large_pore_repair_max_repairs_per_image", 5)))

    largest_rescue_enabled = bool(settings.get("large_pore_repair_largest_rescue_enabled", True))
    largest_rescue_parent_limit = max(1, int(settings.get("large_pore_repair_largest_rescue_parent_limit", 3)))
    largest_rescue_min_radius = max(1, int(settings.get("large_pore_repair_largest_rescue_min_radius_px", 8)))
    largest_rescue_max_radius = max(largest_rescue_min_radius, int(settings.get("large_pore_repair_largest_rescue_max_radius_px", 18)))
    largest_rescue_max_area = max(minimum_repair_area, int(settings.get("large_pore_repair_largest_rescue_max_area_px", 500)))
    largest_rescue_max_fraction = max(0.000001, float(settings.get("large_pore_repair_largest_rescue_max_fraction_of_parent", 0.02)))
    largest_rescue_max_span = max(1, int(settings.get("large_pore_repair_largest_rescue_max_span_px", 50)))
    largest_rescue_min_smaller_fraction = max(0.0, min(0.49, float(settings.get("large_pore_repair_largest_rescue_min_smaller_child_fraction", 0.25))))
    largest_rescue_max_larger_fraction = max(0.51, min(1.0, float(settings.get("large_pore_repair_largest_rescue_max_larger_child_fraction", 0.75))))
    largest_rescue_max_repairs = max(1, int(settings.get("large_pore_repair_largest_rescue_max_repairs_per_image", 2)))

    force_largest_enabled = bool(settings.get("large_pore_repair_force_largest_enabled", True))
    force_largest_max_radius = max(1, int(settings.get("large_pore_repair_force_largest_max_radius_px", 48)))
    force_largest_max_area = max(minimum_repair_area, int(settings.get("large_pore_repair_force_largest_max_area_px", 8000)))
    force_largest_max_fraction = max(0.000001, float(settings.get("large_pore_repair_force_largest_max_fraction_of_parent", 0.30)))
    force_largest_max_span = max(1, int(settings.get("large_pore_repair_force_largest_max_span_px", 220)))
    force_largest_min_child_area = max(1, int(settings.get("large_pore_repair_force_largest_min_child_area_px", 500)))
    force_largest_min_smaller_fraction = max(0.0, min(0.49, float(settings.get("large_pore_repair_force_largest_min_smaller_child_fraction", 0.05))))
    force_largest_max_larger_fraction = max(0.51, min(1.0, float(settings.get("large_pore_repair_force_largest_max_larger_child_fraction", 0.95))))

    green_target_enabled = bool(settings.get("large_pore_repair_green_target_enabled", True))
    green_target_min_parent_area = max(1, int(settings.get("large_pore_repair_green_target_min_parent_area_px", 2000)))
    green_target_max_parent_area = max(green_target_min_parent_area, int(settings.get("large_pore_repair_green_target_max_parent_area_px", 18000)))
    green_target_parent_limit = max(1, int(settings.get("large_pore_repair_green_target_parent_limit", 180)))
    green_target_min_radius = max(1, int(settings.get("large_pore_repair_green_target_min_radius_px", 2)))
    green_target_max_radius = max(green_target_min_radius, int(settings.get("large_pore_repair_green_target_max_radius_px", 10)))
    green_target_min_area = max(1, int(settings.get("large_pore_repair_green_target_min_area_px", 100)))
    green_target_max_area = max(green_target_min_area, int(settings.get("large_pore_repair_green_target_max_area_px", 2500)))
    green_target_min_fraction = max(0.0, float(settings.get("large_pore_repair_green_target_min_fraction_of_parent", 0.02)))
    green_target_max_fraction = max(green_target_min_fraction, float(settings.get("large_pore_repair_green_target_max_fraction_of_parent", 0.18)))
    green_target_min_span = max(1, int(settings.get("large_pore_repair_green_target_min_span_px", 18)))
    green_target_max_span = max(green_target_min_span, int(settings.get("large_pore_repair_green_target_max_span_px", 165)))
    green_target_min_mean_thickness = max(0.1, float(settings.get("large_pore_repair_green_target_min_mean_thickness_px", 2.5)))
    green_target_max_mean_thickness = max(green_target_min_mean_thickness, float(settings.get("large_pore_repair_green_target_max_mean_thickness_px", 30.0)))
    green_target_min_child_area = max(1, int(settings.get("large_pore_repair_green_target_min_child_area_px", 400)))
    green_target_min_smaller_fraction = max(0.0, min(0.49, float(settings.get("large_pore_repair_green_target_min_smaller_child_fraction", 0.12))))
    green_target_max_larger_fraction = max(0.51, min(1.0, float(settings.get("large_pore_repair_green_target_max_larger_child_fraction", 0.82))))
    green_target_max_repairs = max(1, int(settings.get("large_pore_repair_green_target_max_repairs_per_image", 30)))

    green_spur_enabled = bool(settings.get("large_pore_repair_green_spur_enabled", True))
    green_spur_review_only = bool(settings.get("large_pore_repair_green_spur_review_only", True))
    green_spur_max_repairs = max(1, int(settings.get("large_pore_repair_green_spur_max_repairs_per_image", 5)))

    include_edges = bool(settings.get("large_pore_repair_include_edge_pores", False))
    fill_overlay = bool(settings.get("large_pore_repair_fill_red_overlay", False))
    show_overlay = bool(settings.get("large_pore_repair_show_red_overlay", True))

    requested_review = str(result["mode_requested"]).lower().startswith("review")
    forced_automatic = bool(settings.get("beast_mode_enabled", False))
    try:
        if GraphicsEnvironment.isHeadless():
            forced_automatic = True
    except:
        pass
    review_consumed = bool(settings.get("_large_pore_repair_review_consumed", False))
    review_allowed = requested_review and not forced_automatic and not review_consumed
    replay_reviewed_decisions = requested_review and not forced_automatic and review_consumed
    if review_allowed:
        settings["_large_pore_repair_review_consumed"] = True
        result["mode_used"] = "Review proposals"
    elif replay_reviewed_decisions:
        result["mode_used"] = "Replay reviewed decisions"
    else:
        result["mode_used"] = "Automatic conservative" if requested_review else str(result["mode_requested"])

    reviewed_accepted_centers = settings.get("_large_pore_repair_review_accepted_centers", [])
    if not isinstance(reviewed_accepted_centers, list):
        reviewed_accepted_centers = []
    reviewed_rejected_centers = settings.get("_large_pore_repair_review_rejected_centers", [])
    if not isinstance(reviewed_rejected_centers, list):
        reviewed_rejected_centers = []

    repair_mask_ip = ByteProcessor(corrected_ip.getWidth(), corrected_ip.getHeight())
    repair_mask_ip.setValue(255)
    repair_mask_ip.fill()
    accepted_overlay = Overlay()

    parents = large_pore_parent_rois(corrected_ip, minimum_parent_area, include_edges)[:parent_limit]
    result["parent_count"] = len(parents)
    IJ.log("Large Pore Repair: inspecting " + str(len(parents)) + " parent pores; mode=" + str(result["mode_used"]))
    if force_largest_enabled:
        IJ.log(
            "v193 Forced Largest Pore: rank 1 first; radius 1-" + str(force_largest_max_radius) +
            " px; max area=" + str(force_largest_max_area) +
            " px; max span=" + str(force_largest_max_span) +
            " px; max fraction=" + str(force_largest_max_fraction)
        )
    if largest_rescue_enabled:
        IJ.log(
            "Aggressive Largest-Pore Rescue: top " + str(largest_rescue_parent_limit) +
            " pores; radius " + str(largest_rescue_min_radius) + "-" + str(largest_rescue_max_radius) +
            " px; max area=" + str(largest_rescue_max_area) +
            " px; max span=" + str(largest_rescue_max_span) +
            " px; max accepted=" + str(largest_rescue_max_repairs)
        )

    if green_target_enabled:
        IJ.log(
            "v193 Green-Target Multi-Neck: parent " + str(green_target_min_parent_area) +
            "-" + str(green_target_max_parent_area) +
            " px; first " + str(green_target_parent_limit) +
            "; radius " + str(green_target_min_radius) +
            "-" + str(green_target_max_radius) +
            " px; recursive max repairs=" + str(green_target_max_repairs)
        )

    if review_allowed:
        try:
            mask.show()
            mask.setActivated()
        except:
            pass

    for parent_index in range(len(parents)):
        if result["accepted_count"] >= maximum_repairs or result["review_canceled"]:
            break
        raise_if_cancel_requested("large-pore repair")
        parent_area, parent_roi = parents[parent_index]
        mark_beast_worker_busy_progress(
            "LARGE_PORE_PARENT_SEARCH",
            "parent=" + str(parent_index + 1) + "/" + str(len(parents)) +
            ",area=" + str(parent_area) + ",accepted=" + str(result["accepted_count"]),
            10.0
        )

        rescue_available_for_parent = (
            largest_rescue_enabled and
            parent_index < largest_rescue_parent_limit and
            result["largest_rescue_accepted_count"] < largest_rescue_max_repairs
        )
        force_available_for_parent = force_largest_enabled and parent_index == 0

        effective_max_radius = maximum_radius
        if rescue_available_for_parent:
            effective_max_radius = max(effective_max_radius, largest_rescue_max_radius)
        if force_available_for_parent:
            effective_max_radius = max(effective_max_radius, force_largest_max_radius)

        local_parent_ip, crop_x, crop_y = large_pore_crop_parent(
            corrected_ip,
            parent_roi,
            crop_margin + effective_max_radius + 2
        )

        search_profiles = []

        if force_available_for_parent:
            search_profiles.append({
                "name": "v193 forced largest pore",
                "priority": -2,
                "is_rescue": True,
                "balance_first": True,
                "minimum_radius": 1,
                "maximum_radius": force_largest_max_radius,
                "radius_step": 1,
                "maximum_area": force_largest_max_area,
                "maximum_fraction": force_largest_max_fraction,
                "maximum_span": force_largest_max_span,
                "minimum_child_area": force_largest_min_child_area,
                "minimum_smaller_fraction": force_largest_min_smaller_fraction,
                "maximum_larger_fraction": force_largest_max_larger_fraction
            })

        if rescue_available_for_parent:
            search_profiles.append({
                "name": "Aggressive largest-pore rescue",
                "priority": -1,
                "is_rescue": True,
                "balance_first": True,
                "minimum_radius": largest_rescue_min_radius,
                "maximum_radius": largest_rescue_max_radius,
                "radius_step": radius_step,
                "maximum_area": largest_rescue_max_area,
                "maximum_fraction": largest_rescue_max_fraction,
                "maximum_span": largest_rescue_max_span,
                "minimum_child_area": minimum_child_area,
                "minimum_smaller_fraction": largest_rescue_min_smaller_fraction,
                "maximum_larger_fraction": largest_rescue_max_larger_fraction
            })

        search_profiles.append({
            "name": "Standard",
            "priority": 0,
            "is_rescue": False,
            "balance_first": False,
            "minimum_radius": minimum_radius,
            "maximum_radius": maximum_radius,
            "radius_step": radius_step,
            "maximum_area": maximum_repair_area,
            "maximum_fraction": maximum_repair_fraction,
            "maximum_span": maximum_repair_span,
            "minimum_child_area": minimum_child_area,
            "minimum_smaller_fraction": minimum_smaller_fraction,
            "maximum_larger_fraction": maximum_larger_fraction
        })

        proposals = []

        for search_profile in search_profiles:
            radius = int(search_profile["minimum_radius"])
            while radius <= int(search_profile["maximum_radius"]):
                mark_beast_worker_busy_progress(
                    "LARGE_PORE_RADIUS_SEARCH",
                    "parent=" + str(parent_index + 1) +
                    ",profile=" + str(search_profile["name"]) +
                    ",radius=" + str(radius) + "/" + str(search_profile["maximum_radius"]),
                    12.0
                )
                local_fiber_ip = local_parent_ip.duplicate()
                local_fiber_ip.invert()
                closed_fiber_ip = local_fiber_ip.duplicate()
                rank_filter = RankFilters()
                rank_filter.rank(closed_fiber_ip, float(radius), RankFilters.MAX)
                rank_filter.rank(closed_fiber_ip, float(radius), RankFilters.MIN)
                candidate_ip = closed_fiber_ip.duplicate()
                candidate_ip.copyBits(local_fiber_ip, 0, 0, Blitter.SUBTRACT)
                candidate_ip.threshold(0)
                components = large_pore_candidate_components(
                    candidate_ip,
                    minimum_repair_area,
                    int(search_profile["maximum_area"])
                )

                for candidate_index, candidate_tuple in enumerate(components):
                    candidate_area, local_points, local_roi = candidate_tuple
                    if candidate_index == 0 or candidate_index % 8 == 0:
                        mark_beast_worker_busy_progress(
                            "LARGE_PORE_CANDIDATE_TEST",
                            "parent=" + str(parent_index + 1) +
                            ",radius=" + str(radius) +
                            ",candidate=" + str(candidate_index + 1) + "/" + str(len(components)),
                            12.0
                        )
                    repair_fraction = float(candidate_area) / float(parent_area)
                    if repair_fraction > float(search_profile["maximum_fraction"]):
                        continue

                    repair_span = large_pore_point_span(local_points)
                    if repair_span > int(search_profile["maximum_span"]):
                        continue

                    trial_ip = local_parent_ip.duplicate()
                    large_pore_apply_black_points(trial_ip, local_points)
                    child_areas = large_pore_white_component_areas(trial_ip)
                    if len(child_areas) != 2:
                        continue

                    larger_child = child_areas[0]
                    smaller_child = child_areas[1]
                    profile_minimum_child_area = int(search_profile.get("minimum_child_area", minimum_child_area))
                    if larger_child < profile_minimum_child_area or smaller_child < profile_minimum_child_area:
                        continue

                    smaller_fraction = float(smaller_child) / float(parent_area)
                    larger_fraction = float(larger_child) / float(parent_area)
                    if smaller_fraction < float(search_profile["minimum_smaller_fraction"]):
                        continue
                    if larger_fraction > float(search_profile["maximum_larger_fraction"]):
                        continue

                    global_points = [(x + crop_x, y + crop_y) for x, y in local_points]
                    global_roi = large_pore_translate_roi(local_roi, crop_x, crop_y)
                    center_x = sum(point[0] for point in global_points) / float(len(global_points))
                    center_y = sum(point[1] for point in global_points) / float(len(global_points))

                    proposals.append({
                        "search_profile": str(search_profile["name"]),
                        "profile_priority": int(search_profile["priority"]),
                        "balance_first": bool(search_profile.get("balance_first", False)),
                        "is_rescue": bool(search_profile["is_rescue"]),
                        "parent_rank": parent_index + 1,
                        "parent_area": parent_area,
                        "radius": radius,
                        "repair_area": candidate_area,
                        "repair_fraction": repair_fraction,
                        "repair_span": repair_span,
                        "larger_child": larger_child,
                        "smaller_child": smaller_child,
                        "larger_fraction": larger_fraction,
                        "smaller_fraction": smaller_fraction,
                        "center_x": center_x,
                        "center_y": center_y,
                        "global_points": global_points,
                        "global_roi": global_roi
                    })

                radius += int(search_profile["radius_step"])

        result["proposal_count"] += len(proposals)
        proposals.sort(
            key=lambda item: (
                item.get("profile_priority", 0),
                abs(0.5 - float(item["smaller_fraction"])) if item.get("balance_first", False) else 1.0,
                float(item["repair_fraction"]) if item.get("balance_first", False) else float(item["repair_area"]),
                item["repair_area"],
                item["radius"]
            )
        )

        deduplicated_proposals = []
        for proposal in proposals:
            duplicate = False
            for existing in deduplicated_proposals:
                dx = float(proposal["center_x"]) - float(existing["center_x"])
                dy = float(proposal["center_y"]) - float(existing["center_y"])
                if math.sqrt(dx * dx + dy * dy) <= 3.0:
                    duplicate = True
                    break
            if not duplicate:
                deduplicated_proposals.append(proposal)
        proposals = deduplicated_proposals

        accepted_for_parent = False
        for proposal in proposals:
            apply_proposal = True
            if replay_reviewed_decisions:
                apply_proposal = False
                match_tolerance = max(6.0, float(maximum_repair_span) / 2.0)
                for approved_center in reviewed_accepted_centers:
                    try:
                        dx = float(proposal["center_x"]) - float(approved_center[0])
                        dy = float(proposal["center_y"]) - float(approved_center[1])
                        if math.sqrt(dx * dx + dy * dy) <= match_tolerance:
                            apply_proposal = True
                            break
                    except:
                        pass
                if not apply_proposal:
                    continue
            if review_allowed:
                result["reviewed_count"] += 1
                preview_roi = large_pore_style_roi(proposal["global_roi"], True, True)
                large_pore_rebuild_overlay(mask, accepted_overlay, preview_roi)
                review = GenericDialog("Review large-pore repair")
                review.addMessage(
                    "Large parent pore " + str(parent_index + 1) + " of " + str(len(parents)) + "\n" +
                    "Search profile: " + str(proposal.get("search_profile", "Standard")) + "\n" +
                    "Parent area: " + str(parent_area) + " px\n\n" +
                    "Proposed BLACK repair:\n" +
                    "  Area: " + str(proposal["repair_area"]) + " px (" + ("%.3f" % (proposal["repair_fraction"] * 100.0)) + "% of parent)\n" +
                    "  Span: " + str(proposal["repair_span"]) + " px\n" +
                    "  Closing radius: " + str(proposal["radius"]) + " px\n\n" +
                    "Resulting pores: " + str(proposal["larger_child"]) + " px and " + str(proposal["smaller_child"]) + " px\n\n" +
                    "The RED proposal becomes a black repair if accepted."
                )
                review.addCheckbox("Apply this black repair", True)
                review.showDialog()
                if review.wasCanceled():
                    result["review_canceled"] = True
                    large_pore_rebuild_overlay(mask, accepted_overlay, None)
                    break
                apply_proposal = review.getNextBoolean()
            if apply_proposal:
                large_pore_apply_black_points(corrected_ip, proposal["global_points"])
                large_pore_apply_black_points(repair_mask_ip, proposal["global_points"])
                mask.setProcessor(mask.getTitle(), corrected_ip)
                if show_overlay:
                    accepted_overlay.add(large_pore_style_roi(proposal["global_roi"], fill_overlay, False))
                large_pore_rebuild_overlay(mask, accepted_overlay, None)
                result["accepted_count"] += 1
                if proposal.get("is_rescue", False):
                    result["largest_rescue_accepted_count"] += 1
                result["repaired_pixels"] += int(proposal["repair_area"])
                clean_record = dict(proposal)
                clean_record.pop("global_points", None)
                clean_record.pop("global_roi", None)
                result["repairs"].append(clean_record)
                if review_allowed:
                    reviewed_accepted_centers.append((proposal["center_x"], proposal["center_y"]))
                    settings["_large_pore_repair_review_accepted_centers"] = reviewed_accepted_centers
                accepted_for_parent = True
                mark_beast_worker_busy_progress(
                    "LARGE_PORE_REPAIR_ACCEPTED",
                    "parent=" + str(parent_index + 1) +
                    ",profile=" + str(proposal.get("search_profile", "Standard")) +
                    ",accepted=" + str(result["accepted_count"]),
                    1.0,
                    True
                )
                IJ.log(
                    "Large Pore Repair accepted: profile=" + str(proposal.get("search_profile", "Standard")) +
                    "; parent rank " + str(parent_index + 1) +
                    "; repair=" + str(proposal["repair_area"]) +
                    " px; children=" + str(proposal["larger_child"]) +
                    "/" + str(proposal["smaller_child"]) + " px"
                )
                break
            else:
                if review_allowed:
                    reviewed_rejected_centers.append((proposal["center_x"], proposal["center_y"]))
                    settings["_large_pore_repair_review_rejected_centers"] = reviewed_rejected_centers
                large_pore_rebuild_overlay(mask, accepted_overlay, None)
        if result["review_canceled"]:
            break

    # ------------------------------------------------------------------
    # v193 recursive green-target medium-pore pass
    # ------------------------------------------------------------------
    if green_target_enabled and not result["review_canceled"]:
        initial_green_parents = large_pore_parent_rois(
            corrected_ip,
            green_target_min_parent_area,
            include_edges
        )

        green_queue = []
        green_initial_rank = 0
        for green_parent_area, green_parent_roi in initial_green_parents:
            if green_parent_area > green_target_max_parent_area:
                continue
            green_initial_rank += 1
            green_queue.append((
                green_parent_area,
                green_parent_roi.clone(),
                green_initial_rank,
                0
            ))
            if len(green_queue) >= green_target_parent_limit:
                break

        result["green_target_parent_count"] = len(green_queue)
        IJ.log(
            "v193 Green-Target: queued " + str(len(green_queue)) +
            " initial medium parent pores."
        )

        while (
            len(green_queue) > 0 and
            result["green_target_accepted_count"] < green_target_max_repairs and
            not result["review_canceled"]
        ):
            raise_if_cancel_requested("v193 green-target pore repair")

            green_parent_area, green_parent_roi, green_parent_rank, green_depth = green_queue.pop(0)
            mark_beast_worker_busy_progress(
                "GREEN_TARGET_PARENT_SEARCH",
                "rank=" + str(green_parent_rank) +
                ",depth=" + str(green_depth) +
                ",area=" + str(green_parent_area) +
                ",queue_remaining=" + str(len(green_queue)) +
                ",accepted=" + str(result["green_target_accepted_count"]) +
                "/" + str(green_target_max_repairs),
                10.0
            )

            # A child from a previous recursive split may be outside the
            # configured range after pixel rounding.
            if (
                green_parent_area < green_target_min_parent_area or
                green_parent_area > green_target_max_parent_area
            ):
                continue

            green_local_ip, green_crop_x, green_crop_y = large_pore_crop_parent(
                corrected_ip,
                green_parent_roi,
                crop_margin + green_target_max_radius + 3
            )

            green_profiles = [{
                "name": "v193 green-target multi-neck",
                "priority": 0,
                "is_spur": False,
                "minimum_radius": green_target_min_radius,
                "maximum_radius": green_target_max_radius,
                "minimum_area": green_target_min_area,
                "maximum_area": green_target_max_area,
                "minimum_fraction": green_target_min_fraction,
                "maximum_fraction": green_target_max_fraction,
                "minimum_span": green_target_min_span,
                "maximum_span": green_target_max_span,
                "minimum_mean_thickness": green_target_min_mean_thickness,
                "maximum_mean_thickness": green_target_max_mean_thickness,
                "minimum_child_area": green_target_min_child_area,
                "minimum_smaller_fraction": green_target_min_smaller_fraction,
                "maximum_larger_fraction": green_target_max_larger_fraction
            }]

            spur_profile_allowed = (
                green_spur_enabled and
                result["green_spur_accepted_count"] < green_spur_max_repairs and
                (
                    not green_spur_review_only or
                    review_allowed or
                    replay_reviewed_decisions
                )
            )

            if spur_profile_allowed:
                green_profiles.append({
                    "name": "v193 review-only tiny spur",
                    "priority": 1,
                    "is_spur": True,
                    "minimum_radius": 2,
                    "maximum_radius": 5,
                    "minimum_area": 50,
                    "maximum_area": 350,
                    "minimum_fraction": 0.005,
                    "maximum_fraction": 0.06,
                    "minimum_span": 12,
                    "maximum_span": 45,
                    "minimum_mean_thickness": 2.0,
                    "maximum_mean_thickness": 20.0,
                    "minimum_child_area": 100,
                    "minimum_smaller_fraction": 0.015,
                    "maximum_larger_fraction": 0.985
                })

            green_proposals = []

            for green_profile in green_profiles:
                green_radius = int(green_profile["minimum_radius"])

                while green_radius <= int(green_profile["maximum_radius"]):
                    mark_beast_worker_busy_progress(
                        "GREEN_TARGET_RADIUS_SEARCH",
                        "rank=" + str(green_parent_rank) +
                        ",depth=" + str(green_depth) +
                        ",profile=" + str(green_profile["name"]) +
                        ",radius=" + str(green_radius) + "/" + str(green_profile["maximum_radius"]),
                        12.0
                    )
                    green_fiber_ip = green_local_ip.duplicate()
                    green_fiber_ip.invert()

                    green_closed_ip = green_fiber_ip.duplicate()
                    green_rank_filter = RankFilters()
                    green_rank_filter.rank(
                        green_closed_ip,
                        float(green_radius),
                        RankFilters.MAX
                    )
                    green_rank_filter.rank(
                        green_closed_ip,
                        float(green_radius),
                        RankFilters.MIN
                    )

                    green_candidate_ip = green_closed_ip.duplicate()
                    green_candidate_ip.copyBits(
                        green_fiber_ip,
                        0,
                        0,
                        Blitter.SUBTRACT
                    )
                    green_candidate_ip.threshold(0)

                    green_components = large_pore_candidate_components(
                        green_candidate_ip,
                        int(green_profile["minimum_area"]),
                        int(green_profile["maximum_area"])
                    )

                    for green_candidate_index, green_candidate_tuple in enumerate(green_components):
                        green_candidate_area, green_local_points, green_local_roi = green_candidate_tuple
                        if green_candidate_index == 0 or green_candidate_index % 8 == 0:
                            mark_beast_worker_busy_progress(
                                "GREEN_TARGET_CANDIDATE_TEST",
                                "rank=" + str(green_parent_rank) +
                                ",radius=" + str(green_radius) +
                                ",candidate=" + str(green_candidate_index + 1) + "/" + str(len(green_components)),
                                12.0
                            )
                        green_fraction = (
                            float(green_candidate_area) /
                            float(green_parent_area)
                        )

                        if green_fraction < float(green_profile["minimum_fraction"]):
                            continue
                        if green_fraction > float(green_profile["maximum_fraction"]):
                            continue

                        green_span = large_pore_point_span(green_local_points)

                        if green_span < int(green_profile["minimum_span"]):
                            continue
                        if green_span > int(green_profile["maximum_span"]):
                            continue

                        green_mean_thickness = (
                            float(green_candidate_area) /
                            float(max(1, green_span))
                        )

                        if green_mean_thickness < float(green_profile["minimum_mean_thickness"]):
                            continue
                        if green_mean_thickness > float(green_profile["maximum_mean_thickness"]):
                            continue

                        green_trial_ip = green_local_ip.duplicate()
                        large_pore_apply_black_points(
                            green_trial_ip,
                            green_local_points
                        )
                        green_child_areas = large_pore_white_component_areas(
                            green_trial_ip
                        )

                        # Central safeguard remains exact two-child topology.
                        if len(green_child_areas) != 2:
                            continue

                        green_larger_child = green_child_areas[0]
                        green_smaller_child = green_child_areas[1]

                        if (
                            green_larger_child < int(green_profile["minimum_child_area"]) or
                            green_smaller_child < int(green_profile["minimum_child_area"])
                        ):
                            continue

                        green_smaller_fraction = (
                            float(green_smaller_child) /
                            float(green_parent_area)
                        )
                        green_larger_fraction = (
                            float(green_larger_child) /
                            float(green_parent_area)
                        )

                        if green_smaller_fraction < float(green_profile["minimum_smaller_fraction"]):
                            continue
                        if green_larger_fraction > float(green_profile["maximum_larger_fraction"]):
                            continue

                        green_global_points = [
                            (x + green_crop_x, y + green_crop_y)
                            for x, y in green_local_points
                        ]
                        green_global_roi = large_pore_translate_roi(
                            green_local_roi,
                            green_crop_x,
                            green_crop_y
                        )
                        green_center_x = (
                            sum(point[0] for point in green_global_points) /
                            float(len(green_global_points))
                        )
                        green_center_y = (
                            sum(point[1] for point in green_global_points) /
                            float(len(green_global_points))
                        )

                        green_proposals.append({
                            "search_profile": str(green_profile["name"]),
                            "profile_priority": int(green_profile["priority"]),
                            "is_rescue": False,
                            "is_green_target": True,
                            "is_green_spur": bool(green_profile["is_spur"]),
                            "parent_rank": green_parent_rank,
                            "parent_area": green_parent_area,
                            "recursive_depth": green_depth,
                            "radius": green_radius,
                            "repair_area": green_candidate_area,
                            "repair_fraction": green_fraction,
                            "repair_span": green_span,
                            "mean_thickness": green_mean_thickness,
                            "larger_child": green_larger_child,
                            "smaller_child": green_smaller_child,
                            "larger_fraction": green_larger_fraction,
                            "smaller_fraction": green_smaller_fraction,
                            "center_x": green_center_x,
                            "center_y": green_center_y,
                            "local_points": green_local_points,
                            "global_points": green_global_points,
                            "global_roi": green_global_roi
                        })

                    green_radius += 1

            result["proposal_count"] += len(green_proposals)

            # The annotated green cuts were consistently the smallest radius
            # that produced a valid two-child split. Prefer that geometry,
            # then the smaller bridge fraction, then a balanced result.
            green_proposals.sort(
                key=lambda item: (
                    item.get("profile_priority", 0),
                    item["radius"],
                    item["repair_fraction"],
                    abs(0.5 - float(item["smaller_fraction"])),
                    item["repair_area"]
                )
            )

            green_deduplicated = []
            for green_proposal in green_proposals:
                green_duplicate = False
                for green_existing in green_deduplicated:
                    green_dx = (
                        float(green_proposal["center_x"]) -
                        float(green_existing["center_x"])
                    )
                    green_dy = (
                        float(green_proposal["center_y"]) -
                        float(green_existing["center_y"])
                    )
                    if math.sqrt(
                        green_dx * green_dx +
                        green_dy * green_dy
                    ) <= 3.0:
                        green_duplicate = True
                        break
                if not green_duplicate:
                    green_deduplicated.append(green_proposal)

            green_proposals = green_deduplicated
            green_accepted_for_parent = False

            for green_proposal in green_proposals:
                green_apply = True

                if replay_reviewed_decisions:
                    green_apply = False
                    green_match_tolerance = max(
                        6.0,
                        float(green_target_max_span) / 2.0
                    )
                    for green_approved_center in reviewed_accepted_centers:
                        try:
                            green_dx = (
                                float(green_proposal["center_x"]) -
                                float(green_approved_center[0])
                            )
                            green_dy = (
                                float(green_proposal["center_y"]) -
                                float(green_approved_center[1])
                            )
                            if math.sqrt(
                                green_dx * green_dx +
                                green_dy * green_dy
                            ) <= green_match_tolerance:
                                green_apply = True
                                break
                        except:
                            pass
                    if not green_apply:
                        continue

                if review_allowed:
                    result["reviewed_count"] += 1
                    green_preview_roi = large_pore_style_roi(
                        green_proposal["global_roi"],
                        True,
                        True
                    )
                    large_pore_rebuild_overlay(
                        mask,
                        accepted_overlay,
                        green_preview_roi
                    )

                    green_review = GenericDialog(
                        "Review v193 green-target repair"
                    )
                    green_review.addMessage(
                        "Profile: " + str(green_proposal["search_profile"]) + "\n" +
                        "Recursive depth: " + str(green_proposal["recursive_depth"]) + "\n" +
                        "Parent area: " + str(green_parent_area) + " px\n\n" +
                        "Proposed BLACK repair:\n" +
                        "  Radius: " + str(green_proposal["radius"]) + " px\n" +
                        "  Area: " + str(green_proposal["repair_area"]) + " px\n" +
                        "  Fraction: " + ("%.3f" % (green_proposal["repair_fraction"] * 100.0)) + "%\n" +
                        "  Span: " + str(green_proposal["repair_span"]) + " px\n" +
                        "  Mean thickness: " + ("%.2f" % green_proposal["mean_thickness"]) + " px\n\n" +
                        "Resulting pores: " +
                        str(green_proposal["larger_child"]) + " px and " +
                        str(green_proposal["smaller_child"]) + " px\n\n" +
                        "If accepted, the resulting child pores are checked again for additional green-style necks."
                    )
                    green_review.addCheckbox(
                        "Apply this black repair",
                        True
                    )
                    green_review.showDialog()

                    if green_review.wasCanceled():
                        result["review_canceled"] = True
                        large_pore_rebuild_overlay(
                            mask,
                            accepted_overlay,
                            None
                        )
                        break

                    green_apply = green_review.getNextBoolean()

                if green_apply:
                    large_pore_apply_black_points(
                        corrected_ip,
                        green_proposal["global_points"]
                    )
                    large_pore_apply_black_points(
                        repair_mask_ip,
                        green_proposal["global_points"]
                    )
                    large_pore_apply_black_points(
                        green_local_ip,
                        green_proposal["local_points"]
                    )

                    mask.setProcessor(mask.getTitle(), corrected_ip)

                    if show_overlay:
                        accepted_overlay.add(
                            large_pore_style_roi(
                                green_proposal["global_roi"],
                                fill_overlay,
                                False
                            )
                        )
                    large_pore_rebuild_overlay(
                        mask,
                        accepted_overlay,
                        None
                    )

                    result["accepted_count"] += 1
                    result["green_target_accepted_count"] += 1
                    if green_proposal.get("is_green_spur", False):
                        result["green_spur_accepted_count"] += 1
                    result["repaired_pixels"] += int(
                        green_proposal["repair_area"]
                    )

                    green_clean_record = dict(green_proposal)
                    green_clean_record.pop("local_points", None)
                    green_clean_record.pop("global_points", None)
                    green_clean_record.pop("global_roi", None)
                    result["repairs"].append(green_clean_record)

                    if review_allowed:
                        reviewed_accepted_centers.append((
                            green_proposal["center_x"],
                            green_proposal["center_y"]
                        ))
                        settings[
                            "_large_pore_repair_review_accepted_centers"
                        ] = reviewed_accepted_centers

                    # Recursively queue both resulting children if they are
                    # still within the configured medium-parent range.
                    green_children = large_pore_parent_rois(
                        green_local_ip,
                        1,
                        True
                    )
                    green_child_queue_items = []

                    for green_child_area, green_child_local_roi in green_children:
                        if green_child_area < green_target_min_parent_area:
                            continue
                        if green_child_area > green_target_max_parent_area:
                            continue

                        green_child_global_roi = large_pore_translate_roi(
                            green_child_local_roi,
                            green_crop_x,
                            green_crop_y
                        )
                        green_child_queue_items.append((
                            green_child_area,
                            green_child_global_roi,
                            green_parent_rank,
                            green_depth + 1
                        ))

                    green_child_queue_items.sort(
                        key=lambda item: item[0],
                        reverse=True
                    )
                    for green_child_item in reversed(
                        green_child_queue_items
                    ):
                        green_queue.insert(0, green_child_item)

                    green_accepted_for_parent = True
                    mark_beast_worker_busy_progress(
                        "GREEN_TARGET_REPAIR_ACCEPTED",
                        "rank=" + str(green_parent_rank) +
                        ",depth=" + str(green_depth) +
                        ",accepted=" + str(result["green_target_accepted_count"]) +
                        "/" + str(green_target_max_repairs),
                        1.0,
                        True
                    )
                    IJ.log(
                        "v193 Green-Target accepted: profile=" +
                        str(green_proposal["search_profile"]) +
                        "; parent=" + str(green_parent_area) +
                        " px; radius=" + str(green_proposal["radius"]) +
                        " px; repair=" + str(green_proposal["repair_area"]) +
                        " px; children=" +
                        str(green_proposal["larger_child"]) + "/" +
                        str(green_proposal["smaller_child"]) + " px"
                    )
                    break

                else:
                    if review_allowed:
                        reviewed_rejected_centers.append((
                            green_proposal["center_x"],
                            green_proposal["center_y"]
                        ))
                        settings[
                            "_large_pore_repair_review_rejected_centers"
                        ] = reviewed_rejected_centers
                    large_pore_rebuild_overlay(
                        mask,
                        accepted_overlay,
                        None
                    )

            if result["review_canceled"]:
                break

    mask.setProcessor(mask.getTitle(), corrected_ip)
    if show_overlay:
        large_pore_rebuild_overlay(mask, accepted_overlay, None)
    else:
        try:
            mask.setOverlay(None)
        except:
            pass

    if result["accepted_count"] > 0 and run_image_outputs_enabled(settings):
        if bool(settings.get("large_pore_repair_save_red_overlay_png", True)):
            overlay_path = os.path.join(image_dir, base_safe + "_large_pore_repairs_red.png")
            flat = None
            try:
                flat = mask.flatten()
                FileSaver(flat).saveAsPng(overlay_path)
                if os.path.isfile(overlay_path):
                    result["red_overlay_png"] = overlay_path
            except Exception as e:
                IJ.log("Could not save large-pore red overlay PNG: " + str(e))
            finally:
                try:
                    if flat is not None:
                        flat.changes = False
                        flat.close()
                except:
                    pass
        if bool(settings.get("large_pore_repair_save_mask", False)):
            repair_mask_path = os.path.join(image_dir, base_safe + "_large_pore_repair_mask.tif")
            repair_imp = ImagePlus(base_safe + "_large_pore_repair_mask", repair_mask_ip)
            try:
                repair_imp.setCalibration(mask.getCalibration().copy())
                FileSaver(repair_imp).saveAsTiff(repair_mask_path)
                if os.path.isfile(repair_mask_path):
                    result["repair_mask_tif"] = repair_mask_path
            except Exception as e:
                IJ.log("Could not save large-pore repair mask: " + str(e))
            finally:
                try:
                    repair_imp.changes = False
                    repair_imp.close()
                except:
                    pass
        if bool(settings.get("large_pore_repair_save_csv", True)):
            csv_path = os.path.join(image_dir, base_safe + "_large_pore_repairs.csv")
            result["repair_csv"] = large_pore_write_csv(csv_path, result["repairs"])

    IJ.log(
        "Large Pore Repair complete: accepted=" + str(result["accepted_count"]) +
        "; largest-pore rescue accepted=" + str(result["largest_rescue_accepted_count"]) +
        "; v193 green-target accepted=" + str(result["green_target_accepted_count"]) +
        "; tiny-spur accepted=" + str(result["green_spur_accepted_count"]) +
        "; repaired pixels=" + str(result["repaired_pixels"]) +
        "; proposals=" + str(result["proposal_count"])
    )
    return result

