# -*- coding: utf-8 -*-
# MODULE 01: Imports, constants, validation, and shared helpers
# Fiji / ImageJ Jython script
# ImageJ -> JMP automation for GDL pore analysis
# FORK: YOURE A BETA - adds Fiji active-window image capture, scale-frame trace, scaled TIFF capture batch, and optional analysis run.
# Added: scrollable tabbed settings popup, batch processing, parameter sweep, JMP EPD descending sort, bounded-scale fixed histograms, separate JMP graph/axis title controls, optional close-all at finish, optional closing of generated JMP windows, compact Word DOCX report creation with lossless PNG embeds, optional scale bar, bad-image checks, average circularity/roundness summary rows, multi-pore manual measurement, and merged manual pore trace workflow, largest-pore guide on trace image, full-image high-difference trace-vs-actual preview, PNG-to-Scaled-image TIFF analysis flow
#
# v107: optional popup portrait, Swing-safe text formatting, and 3-second auto-dismiss.
# v108: adds Threshold % display using the 8-bit 0-255 gray-value range.
# v109: adds selectable gray-value or percent threshold input for normal runs and threshold sweeps.
# v110: adds summary-metric Sweep Until targets with numeric/percent targets and early-stop scope.
# v111: simplifies manual strand confirmation, adds report naming modes, and exports Excel run summaries.
# v112: simplifies Excel export to one main summary sheet and maps threshold percentages through each image histogram.
# v113: uses the original image as the default pore-map background and adds an automatic JMP between-band upper cutoff.
# v114: adds three configurable EPD bands (3-5, 5-7, and 10-12 microns), matching small-pore map groups, and pore-map opacity control.
# v115: replaces the three simultaneous bands with one JMP cutoff preset dropdown plus Custom, and synchronizes the pore-map limit.
# v116: makes the preset dropdown select the delete-EPD cutoff first; the selected 3, 5, or 10 micron delete cutoff automatically updates the between-count band and pore-map limit.
# v117: pore-map presets change only the low-pore highlight; pores above 25 microns are always highlighted separately.
# v118: adds BEAST MODE for thousands of runs, ordered parallel JMP workers, persistent logging/checkpoints, XLS-only output, and configurable ImageJ Set Measurements.
# v119: left-aligns all settings cards/pages, adds a global cancel that stops ImageJ/JMP work, and organizes visible ImageJ/JMP windows.
# v120: BEAST MODE disables JMP graphs/histograms and exports one ordered three-sheet XLSX with all pore data plus run overview/timing.
# v121: BEAST MODE optionally uses persistent parallel Fiji worker instances; workbook overview is aggregate totals plus exceptions only.
# v122: rebuilt on the stable v118 BEAST core; true run-level Fiji scheduling, strict configured Fiji/JMP concurrency, and v120 progress/log/window/workbook behavior.
# v123: streams completed Fiji runs into the bounded JMP pool and optionally creates JMP graphs/histograms in a combined Word report.
# v124: fixes external Fiji worker launch, validates each worker startup, exposes active worker counts, and hardens JMP streaming launch diagnostics.
# v125: moves all native selectors before progress and adds real Fiji/JMP preflight markers.
# v126: auto-detects the running script and current Fiji launcher; removes the parent-script chooser entirely.
# v127: requires a verified Fiji installation launcher, rejects legacy standalone ImageJ, and searches mkime/vgolf user roots.
# v128: removes recursive/classpath Fiji discovery, prioritizes the active Fiji root, and waits the full preflight timeout for detached launchers.
# v129: supports modern Fiji Jaunch (fiji.bat/fiji.exe), current-process launcher detection, and batch-safe worker commands.
# v130: removes external Fiji workers for stability; one active Fiji streams completed runs into a strictly bounded parallel JMP pool.
# v131: adds optional resilient headless Fiji workers using the documented --headless --run path, with automatic controller fallback.
# v132: BEAST MODE launches JMP only when graph/histogram reporting is enabled; Fiji writes EPD directly as the final pore-data column.
# v133: makes external Fiji workers observable and resilient; prefers the attached native Jaunch executable, records every launch attempt, and never fails silently.
# v134: fixes modern Fiji/Jaunch option routing by passing --headless/--run directly (never after --), adds --allow-multiple, and displays/logs the live active Fiji-agent count.
# v135: adds visible Fiji worker mode (default on), limits Fiji preflight to a 15-second total marker budget, and counts only marker-confirmed active agents.
# v138: fixes generated Fiji probe/worker Jython parsing by removing PEP-263 encoding cookies from scripts executed by the SciJava script engine; retains four claim-confirmed Fiji agents and 60-second startup budgets.
# v193: makes the Fiji worker count configurable, assigns every visible worker a deterministic non-overlapping screen tile, moves the BEAST toggle to General + JMP, keeps Sweep visible in Simple mode, and moves Set Scale/Image Capturing to Advanced mode.
# v193 launcher split: Explorer-safe launcher plus companion execfile parts avoids Jython JVM bytecode-size limits; celebration image is reduced.
# v193 worker fix: generated Fiji wrappers load the split companion modules directly from the real launcher folder, independent of wrapper __file__.
# v193 supervised agents: periodic heartbeat files, soft slow-run warnings, runtime relaunch of unfinished jobs, per-run hard timeout, and final controller fallback.
# v193 ordered pipeline: adds a reusable 20-slot ORDER card, merges binary controls into Processing, and supports duplicate operations with independent parameters.
# v195: reads Swift Imaging 3.0 .magn tables, applies pixels-per-meter calibration before crops/sweeps, and records the profile in reports.
# v195 freeze fix: infer finished workers from published runs, bound snapshot finalization, and tolerate partial hist_dir metadata.
# v196: makes Swift Resolution units explicit as pixels per meter (px/m) and Quick Runs persist every current GUI field, including all JMP/Word histogram binning controls.
# v199: supports multiple Swift .magn profiles in one table and populates a 4X/10X objective selector directly from Imaging.magn.
# v209: keeps the user-independent OG heat-map fix and adds real inner-loop work progress so the strict watchdog does not kill legitimate long pore-repair searches.
# v209: adds persistent report-recovery snapshots, reports-only rebuild mode, manual end-of-run summary collection, and partial-report finalization on cancel/failure.
#
# Normal workflow:
# 1. Run this script from Fiji/ImageJ as Jython
# 2. Choose settings in the scrollable popup
# 3. Single mode: select one image + output folder
# 4. Batch mode: select input folder + output folder
# 5. Optional sweep mode: create separate runs for selected parameter combinations
# 6. Script saves ImageJ CSVs/images and creates a JMP Script.jsl for each run
# 7. JMP cleaned table is sorted by epd(mm) descending
# 8. JMP histograms use controlled bin span plus user controls for title, graph size, legend, bins, X axis, Y axis, and optional EPD roundness filtering
# 9. Optional finish toggle closes open ImageJ/Fiji image/result windows
# 10. Optional JMP finish toggle closes the JMP data-table/report windows created by each run
# 11. Optional compact Word report embeds PNG images directly without JPEG conversion or resampling
# 12. BEAST MODE can use observable external Fiji workers with automatic controller fallback; JMP runs only when histogram/Word reporting is enabled.

from ij import IJ, Prefs, WindowManager, ImagePlus, Menus
from ij.io import OpenDialog, DirectoryChooser, FileSaver
from ij.plugin import Duplicator
from ij.plugin.frame import RoiManager
from ij.plugin.filter import RankFilters, ParticleAnalyzer
from ij.measure import ResultsTable, Measurements, Calibration
from ij.process import ImageProcessor, ByteProcessor, Blitter
from ij.gui import GenericDialog, WaitForUserDialog, PolygonRoi, Roi, Wand, Line, Overlay
from java.io import File, FileInputStream, FileOutputStream, ByteArrayInputStream
from java.lang import ProcessBuilder, System, Runnable
from java.text import SimpleDateFormat
from java.util import Date, ArrayList
from java.util.zip import ZipOutputStream, ZipEntry
from javax.imageio import ImageIO
from java.awt import Color, Desktop, Font, Dialog, Image, GraphicsEnvironment
from java.awt.image import BufferedImage
from jarray import zeros, array

# Swing UI imports for scrollable tabbed popup
from javax.swing import JDialog, JFrame, JPanel, JScrollPane, JLabel, JTextField, JCheckBox, JButton, JComboBox, JOptionPane, JTextArea, JProgressBar, UIManager, Timer, ImageIcon, SwingUtilities
from javax.swing import BoxLayout, Box, BorderFactory
from javax.swing.event import DocumentListener
from java.awt import BorderLayout, Dimension, CardLayout, Toolkit
from java.awt.event import WindowAdapter, ActionListener

import os
import math
import time
import csv
import re
import codecs
import random
import base64
import json
import traceback
import struct
import shutil
import cPickle as pickle

# ======================================================
# USER DEFAULTS
# ======================================================
# GDL_User_Defaults.py is executed before this module by every launcher/worker.
for _required_default_name in ["DEFAULTS", "JMP_EXE_DEFAULT", "COMMON_JMP_PATHS",
                               "ALL_REPORTS_FOLDER_MICHELSON", "ALL_REPORTS_FOLDER_VGOLF"]:
    if _required_default_name not in globals():
        raise RuntimeError("GDL_User_Defaults.py was not loaded before the core module: " + _required_default_name)

COLOR_NAME_OPTIONS = ["red", "green", "blue", "yellow", "cyan", "magenta", "orange", "white", "black", "gray", "lightgray", "darkgray", "pink"]

EPD_BETWEEN_PRESET_OPTIONS = [
    "Delete at 3 microns",
    "Delete at 5 microns",
    "Delete at 10 microns",
    "Custom"
]


PROCESS_PIPELINE_OPTIONS = [
    ("none", "None / unused"),
    ("8bit", "Convert to 8-bit"),
    ("median", "Median filter"),
    ("contrast", "Enhance Contrast"),
    ("bandpass", "Bandpass Filter"),
    ("clahe", "CLAHE / Local Contrast"),
    ("minimum", "Minimum filter"),
    ("maximum", "Maximum filter"),
    ("threshold", "Threshold to binary mask"),
    ("despeckle", "Binary: Despeckle"),
    ("fill_holes", "Binary: Fill Holes"),
    ("open", "Binary: Open"),
    ("close", "Binary: Close"),
    ("erode", "Binary: Erode"),
    ("dilate", "Binary: Dilate"),
    ("watershed", "Binary: Watershed")
]
PROCESS_PIPELINE_LABEL_TO_TOKEN = dict((label, token) for token, label in PROCESS_PIPELINE_OPTIONS)
PROCESS_PIPELINE_TOKEN_TO_LABEL = dict(PROCESS_PIPELINE_OPTIONS)
PROCESS_PIPELINE_GRAY_OPERATIONS = ["8bit", "median", "contrast", "bandpass", "clahe", "minimum", "maximum"]
PROCESS_PIPELINE_BINARY_OPERATIONS = ["despeckle", "fill_holes", "open", "close", "erode", "dilate", "watershed"]

# Four explicit ImageJ Enhance Contrast sweep modes. The active contrast step's
# saturated value is preserved in every ON mode.
CONTRAST_SWEEP_MODE_OPTIONS = [
    "Off",
    "Saturated cutoff only",
    "Normalize",
    "Equalize"
]


def contrast_sweep_mode_parameters(mode):
    mode_text = str(mode).strip().lower()
    if mode_text == "normalize":
        return {"enabled": True, "normalize": True, "equalize": False}
    if mode_text == "equalize":
        return {"enabled": True, "normalize": False, "equalize": True}
    if mode_text in ["saturated cutoff only", "saturated", "cutoff only"]:
        return {"enabled": True, "normalize": False, "equalize": False}
    return {"enabled": False, "normalize": False, "equalize": False}


def selected_contrast_sweep_modes(settings):
    selected = []
    if bool(settings.get("sweep_contrast_mode_off", True)):
        selected.append("Off")
    if bool(settings.get("sweep_contrast_mode_saturated", True)):
        selected.append("Saturated cutoff only")
    if bool(settings.get("sweep_contrast_mode_normalize", True)):
        selected.append("Normalize")
    if bool(settings.get("sweep_contrast_mode_equalize", True)):
        selected.append("Equalize")
    return selected


def contrast_mode_label(settings):
    if not bool(settings.get("contrast_enabled", False)):
        return "Off"
    normalize_on = bool(settings.get("contrast_normalize", False))
    equalize_on = bool(settings.get("contrast_equalize", False))
    if normalize_on and equalize_on:
        return "Normalize + Equalize"
    if normalize_on:
        return "Normalize"
    if equalize_on:
        return "Equalize"
    return "Saturated cutoff only"


def ordinal_text(number):
    try:
        n = int(number)
    except:
        n = 0
    if 10 <= (n % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return str(n) + suffix


def pipeline_operation_label(token):
    return PROCESS_PIPELINE_TOKEN_TO_LABEL.get(str(token), str(token))


def default_pipeline_step(token):
    token = str(token).strip().lower()
    base = {"operation": token, "enabled": token not in ["none", "bandpass", "clahe"]}
    if token == "8bit":
        base["enabled"] = bool(DEFAULTS.get("convert_8bit", True))
    elif token == "median":
        base.update({"enabled": bool(DEFAULTS.get("median_enabled", True)), "radius": float(DEFAULTS.get("median_radius", 2.0))})
    elif token == "contrast":
        base.update({
            "enabled": bool(DEFAULTS.get("contrast_enabled", True)),
            "saturated": float(DEFAULTS.get("contrast_saturated", 0.35)),
            "normalize": bool(DEFAULTS.get("contrast_normalize", True)),
            "equalize": bool(DEFAULTS.get("contrast_equalize", True))
        })
    elif token == "bandpass":
        base.update({
            "enabled": bool(DEFAULTS.get("bandpass_enabled", False)),
            "large": float(DEFAULTS.get("bandpass_large", 40.0)),
            "small": float(DEFAULTS.get("bandpass_small", 3.0)),
            "suppress": str(DEFAULTS.get("bandpass_suppress", "None")),
            "tolerance": float(DEFAULTS.get("bandpass_tolerance", 5.0)),
            "autoscale": bool(DEFAULTS.get("bandpass_autoscale", True)),
            "saturate": bool(DEFAULTS.get("bandpass_saturate", False))
        })
    elif token == "clahe":
        base.update({
            "enabled": bool(DEFAULTS.get("clahe_enabled", False)),
            "blocksize": int(DEFAULTS.get("clahe_blocksize", 127)),
            "histogram": int(DEFAULTS.get("clahe_histogram", 256)),
            "maximum": float(DEFAULTS.get("clahe_maximum", 3.0)),
            "fast": bool(DEFAULTS.get("clahe_fast", False))
        })
    elif token == "threshold":
        base["enabled"] = True
    elif token in ["fill_holes", "watershed"]:
        base["enabled"] = True
    elif token in ["minimum", "maximum"]:
        radius_default = float(DEFAULTS.get(token + "_filter_radius", DEFAULTS.get("binary_" + token + "_radius", 0.0)))
        base.update({"enabled": True, "radius": radius_default if radius_default > 0 else 1.0})
    elif token in PROCESS_PIPELINE_BINARY_OPERATIONS:
        iteration_default = int(DEFAULTS.get("binary_" + token + "_iterations", 0))
        base.update({"enabled": True, "iterations": iteration_default if iteration_default > 0 else 1})
    return base


def normalize_pipeline_steps(raw_steps, fallback_settings=None):
    steps = []
    if isinstance(raw_steps, basestring):
        try:
            decoded = json.loads(str(raw_steps))
            if isinstance(decoded, list):
                raw_steps = decoded
            else:
                raw_steps = []
        except:
            raw_steps = []
    if not isinstance(raw_steps, list):
        raw_steps = []
    allowed = set(PROCESS_PIPELINE_TOKEN_TO_LABEL.keys())
    for index, raw in enumerate(raw_steps):
        if isinstance(raw, dict):
            token = str(raw.get("operation", "none")).strip().lower()
            source = dict(raw)
        else:
            token = str(raw).strip().lower()
            source = {}
        if token not in allowed or token == "none":
            continue
        step = default_pipeline_step(token)
        for key in source.keys():
            step[key] = source[key]
        step["operation"] = token
        step["slot"] = int(source.get("slot", index + 1))
        steps.append(step)
    if len(steps) == 0:
        order_text = ""
        if fallback_settings is not None:
            order_text = str(fallback_settings.get("process_pipeline_order", ""))
        if order_text.strip() == "":
            order_text = str(DEFAULTS.get("process_pipeline_order", "8bit,median,contrast,bandpass,clahe,threshold"))
        for index, token in enumerate(order_text.replace(";", ",").split(",")):
            token = str(token).strip().lower()
            if token in allowed and token != "none":
                step = default_pipeline_step(token)
                step["slot"] = index + 1
                steps.append(step)
    return steps


def pipeline_steps_from_settings(settings):
    return normalize_pipeline_steps(settings.get("process_pipeline_steps", []), settings)


def validate_processing_pipeline_steps(steps):
    normalized = normalize_pipeline_steps(steps)
    threshold_positions = [i for i, step in enumerate(normalized) if step.get("operation") == "threshold" and bool(step.get("enabled", True))]
    if len(threshold_positions) != 1:
        raise Exception("ORDER must contain exactly one enabled Threshold to binary mask step.")
    threshold_index = threshold_positions[0]
    for i, step in enumerate(normalized):
        if not bool(step.get("enabled", True)):
            continue
        token = str(step.get("operation", ""))
        if token in PROCESS_PIPELINE_BINARY_OPERATIONS and i < threshold_index:
            raise Exception(ordinal_text(step.get("slot", i + 1)) + " step " + pipeline_operation_label(token) + " must be after Threshold.")
        if token in PROCESS_PIPELINE_GRAY_OPERATIONS and i > threshold_index:
            raise Exception(ordinal_text(step.get("slot", i + 1)) + " step " + pipeline_operation_label(token) + " must be before Threshold.")
    return normalized


def processing_pipeline_summary(settings):
    parts = []
    for index, step in enumerate(pipeline_steps_from_settings(settings)):
        token = str(step.get("operation", ""))
        if not bool(step.get("enabled", True)):
            state = "OFF"
        else:
            state = "ON"
        detail = ""
        if token in ["median", "minimum", "maximum"]:
            detail = " radius=" + str(step.get("radius", ""))
        elif token in ["despeckle", "open", "close", "erode", "dilate"]:
            detail = " iterations=" + str(step.get("iterations", ""))
        elif token == "contrast":
            detail = " saturated=" + str(step.get("saturated", "")) + ", normalize=" + str(step.get("normalize", False)) + ", equalize=" + str(step.get("equalize", False))
        elif token == "bandpass":
            detail = " large=" + str(step.get("large", "")) + ", small=" + str(step.get("small", ""))
        elif token == "clahe":
            detail = " block=" + str(step.get("blocksize", "")) + ", max=" + str(step.get("maximum", ""))
        parts.append(ordinal_text(step.get("slot", index + 1)) + " " + pipeline_operation_label(token) + " [" + state + "]" + detail)
    return " | ".join(parts)


def sync_legacy_processing_settings(settings):
    steps = pipeline_steps_from_settings(settings)
    settings["process_pipeline_steps"] = steps
    settings["process_pipeline_order"] = ",".join(str(step.get("operation", "")) for step in steps)
    gray_order = []
    binary_order = []
    first = {}
    for step in steps:
        token = str(step.get("operation", ""))
        if token in PROCESS_PIPELINE_GRAY_OPERATIONS:
            gray_order.append(token)
        if token in PROCESS_PIPELINE_BINARY_OPERATIONS:
            binary_order.append(token)
        if token not in first and bool(step.get("enabled", True)):
            first[token] = step
    settings["process_order"] = ",".join(gray_order)
    settings["convert_8bit"] = bool(first.get("8bit", {}).get("enabled", False))
    median = first.get("median", {})
    settings["median_enabled"] = bool(median.get("enabled", False))
    settings["median_radius"] = float(median.get("radius", settings.get("median_radius", DEFAULTS.get("median_radius", 2.0))))
    contrast = first.get("contrast", {})
    settings["contrast_enabled"] = bool(contrast.get("enabled", False))
    settings["contrast_saturated"] = float(contrast.get("saturated", settings.get("contrast_saturated", DEFAULTS.get("contrast_saturated", 0.35))))
    settings["contrast_normalize"] = bool(contrast.get("normalize", settings.get("contrast_normalize", True)))
    settings["contrast_equalize"] = bool(contrast.get("equalize", settings.get("contrast_equalize", True)))
    bandpass = first.get("bandpass", {})
    settings["bandpass_enabled"] = bool(bandpass.get("enabled", False))
    settings["bandpass_large"] = float(bandpass.get("large", settings.get("bandpass_large", DEFAULTS.get("bandpass_large", 40.0))))
    settings["bandpass_small"] = float(bandpass.get("small", settings.get("bandpass_small", DEFAULTS.get("bandpass_small", 3.0))))
    settings["bandpass_suppress"] = str(bandpass.get("suppress", settings.get("bandpass_suppress", "None")))
    settings["bandpass_tolerance"] = float(bandpass.get("tolerance", settings.get("bandpass_tolerance", 5.0)))
    settings["bandpass_autoscale"] = bool(bandpass.get("autoscale", settings.get("bandpass_autoscale", True)))
    settings["bandpass_saturate"] = bool(bandpass.get("saturate", settings.get("bandpass_saturate", False)))
    clahe = first.get("clahe", {})
    settings["clahe_enabled"] = bool(clahe.get("enabled", False))
    settings["clahe_blocksize"] = int(clahe.get("blocksize", settings.get("clahe_blocksize", DEFAULTS.get("clahe_blocksize", 127))))
    settings["clahe_histogram"] = int(clahe.get("histogram", settings.get("clahe_histogram", DEFAULTS.get("clahe_histogram", 256))))
    settings["clahe_maximum"] = float(clahe.get("maximum", settings.get("clahe_maximum", DEFAULTS.get("clahe_maximum", 3.0))))
    settings["clahe_fast"] = bool(clahe.get("fast", settings.get("clahe_fast", False)))
    settings["binary_enabled"] = any(bool(step.get("enabled", True)) and str(step.get("operation", "")) in PROCESS_PIPELINE_BINARY_OPERATIONS for step in steps)
    settings["binary_operation_order"] = ",".join(binary_order)
    for token in ["fill_holes", "watershed"]:
        settings["binary_" + token] = bool(first.get(token, {}).get("enabled", False))
    for token in ["despeckle", "open", "close", "erode", "dilate"]:
        settings["binary_" + token + "_iterations"] = int(first.get(token, {}).get("iterations", 0))
    for token in ["minimum", "maximum"]:
        radius_value = float(first.get(token, {}).get("radius", 0.0))
        settings[token + "_filter_radius"] = radius_value
        settings["binary_" + token + "_radius"] = radius_value  # legacy saved-setting compatibility
    return settings


def apply_pipeline_sweep_overrides(settings, overrides):
    steps = [dict(step) for step in pipeline_steps_from_settings(settings)]
    mapping = {
        "contrast_enabled": ("contrast", "enabled"),
        "median_radius": ("median", "radius"),
        "bandpass_large": ("bandpass", "large"),
        "bandpass_small": ("bandpass", "small"),
        "clahe_blocksize": ("clahe", "blocksize"),
        "clahe_maximum": ("clahe", "maximum"),
        "binary_fill_holes": ("fill_holes", "enabled"),
        "binary_watershed": ("watershed", "enabled"),
        "binary_despeckle_iterations": ("despeckle", "iterations"),
        "binary_open_iterations": ("open", "iterations"),
        "binary_close_iterations": ("close", "iterations"),
        "binary_erode_iterations": ("erode", "iterations"),
        "binary_dilate_iterations": ("dilate", "iterations"),
        "binary_minimum_radius": ("minimum", "radius"),
        "binary_maximum_radius": ("maximum", "radius")
    }
    for override_key in mapping.keys():
        if override_key not in overrides:
            continue
        token, param = mapping[override_key]
        value = overrides[override_key]
        if param == "enabled":
            value = bool(int(value))
        for step in steps:
            if str(step.get("operation", "")) == token:
                step[param] = value
                if param in ["radius", "iterations"]:
                    step["enabled"] = float(value) > 0
    if "contrast_mode" in overrides:
        contrast_values = contrast_sweep_mode_parameters(overrides["contrast_mode"])
        for step in steps:
            if str(step.get("operation", "")) == "contrast":
                step["enabled"] = contrast_values["enabled"]
                step["normalize"] = contrast_values["normalize"]
                step["equalize"] = contrast_values["equalize"]
    if "binary_enabled" in overrides:
        binary_on = bool(int(overrides["binary_enabled"]))
        for step in steps:
            if str(step.get("operation", "")) in PROCESS_PIPELINE_BINARY_OPERATIONS:
                step["enabled"] = binary_on
    settings["process_pipeline_steps"] = steps
    return sync_legacy_processing_settings(settings)

# Sweep-until metrics mirror the final JMP summary plus the raw ImageJ summary fields.
SWEEP_UNTIL_METRIC_OPTIONS = [
    "Original pore count",
    "Count EPD <= small cutoff",
    "Summary pore count",
    "Count EPD > cutoff 1",
    "Count EPD > cutoff 2",
    "Count EPD between low and high",
    "Count circularity < cutoff",
    "Average EPD (mm)",
    "Max EPD (mm)",
    "Area %",
    "Total Area (mm^2)",
    "Solidity",
    "% EPD <= small cutoff",
    "% EPD > cutoff 1",
    "% EPD > cutoff 2",
    "% EPD between low and high",
    "% circularity < cutoff",
    "Average circularity",
    "Average roundness",
    "Image total area (mm^2)",
    "Original Area %",
    "Original Total Area (mm^2)",
    "Original Solidity"
]

SWEEP_UNTIL_OPERATOR_OPTIONS = [
    "Is above",
    "Is below",
    "Is equal to",
    "Is at or above",
    "Is at or below"
]

SWEEP_UNTIL_STOP_SCOPE_OPTIONS = [
    "Current image/crop only",
    "Entire batch"
]

# COMMON_JMP_PATHS is defined in GDL_User_Defaults.py.



# ======================================================
# PORTABLE QUICK RUN HELPERS
# ======================================================

QUICK_RUN_SLOT_COUNT = 5
QUICK_RUN_FOLDER_NAME = "Quick Runs"
QUICK_RUN_FILE_PATTERN = re.compile(r"^quick run([1-5])-\((.*)\)\.json$", re.IGNORECASE)
QUICK_RUN_PROCESSING_KEYS = set([
    "process_pipeline_steps", "process_pipeline_order", "process_pipeline_slot_count", "process_order",
    "convert_8bit", "median_enabled", "median_radius", "contrast_enabled", "contrast_saturated",
    "contrast_normalize", "contrast_equalize", "bandpass_enabled", "bandpass_large", "bandpass_small",
    "bandpass_suppress", "bandpass_tolerance", "bandpass_autoscale", "bandpass_saturate",
    "clahe_enabled", "clahe_blocksize", "clahe_histogram", "clahe_maximum", "clahe_fast",
    "binary_enabled", "binary_fill_holes", "binary_watershed", "binary_despeckle_iterations",
    "binary_open_iterations", "binary_close_iterations", "binary_erode_iterations",
    "binary_dilate_iterations", "binary_minimum_radius", "binary_maximum_radius",
    "binary_operation_order", "minimum_filter_radius", "maximum_filter_radius"
])


def quick_run_app_dir():
    candidates = []
    try:
        candidates.append(str(globals().get("GDL_APP_DIR", "")))
    except:
        pass
    try:
        launcher_path = str(globals().get("GDL_APP_LAUNCHER_PATH", ""))
        if launcher_path != "":
            candidates.append(os.path.dirname(os.path.abspath(launcher_path)))
    except:
        pass
    try:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))
    except:
        pass
    candidates.append(os.getcwd())
    for candidate in candidates:
        try:
            if candidate is not None and str(candidate).strip() != "" and os.path.isdir(str(candidate)):
                return os.path.abspath(str(candidate))
        except:
            pass
    return os.getcwd()


def quick_run_html_text(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def quick_run_safe_file_name(name):
    text = str(name).strip()
    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if text == "":
        text = "Unnamed"
    return text[:80]


def quick_run_gui_snapshot(fields, display_name):
    """Stable snapshot of editable GUI values for change-only save prompts."""
    captured = {"quick_run_name": str(display_name).strip(), "fields": {}}
    for key in sorted([str(item) for item in fields.keys()]):
        if key.startswith("_"):
            continue
        component = fields.get(key)
        if component is None:
            continue
        try:
            if isinstance(component, JCheckBox):
                value = bool(component.isSelected())
            elif isinstance(component, JComboBox):
                value = str(component.getSelectedItem())
            elif isinstance(component, JTextField):
                value = str(component.getText())
            else:
                continue
            captured["fields"][key] = value
        except Exception:
            pass
    return json.dumps(captured, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def quick_run_capture_all_settings(fields, parsed_settings=None):
    """
    Build a portable Quick Run from the *entire current GUI*, then merge in
    normalized/runtime settings collected by the Run button.

    Earlier versions saved only the parsed settings dictionary. That meant a
    GUI control could participate in change detection but still be omitted from
    the portable Quick Run if its parser was missing or renamed. v196 makes the
    GUI itself the source of truth for Quick Run persistence. This explicitly
    covers all histogram/Word-report binning controls as well as future text,
    checkbox, and combo-box fields without maintaining a second hand-written
    save list.
    """
    captured = {}
    if isinstance(parsed_settings, dict):
        for key in parsed_settings.keys():
            captured[str(key)] = quick_run_portable_value(parsed_settings[key])

    gui_count = 0
    for key in sorted([str(item) for item in fields.keys()]):
        if key.startswith("_"):
            continue
        component = fields.get(key)
        if component is None:
            continue
        try:
            if isinstance(component, JCheckBox):
                value = bool(component.isSelected())
            elif isinstance(component, JComboBox):
                selected = component.getSelectedItem()
                value = "" if selected is None else str(selected)
            elif isinstance(component, JTextField):
                value = str(component.getText())
            else:
                # Keep the persistence layer forward-compatible with simple
                # Swing value components that may be added later.
                try:
                    value = component.getValue()
                except:
                    continue
            captured[key] = quick_run_portable_value(value)
            gui_count += 1
        except Exception as quick_capture_error:
            try:
                IJ.log("Quick Run could not capture field " + str(key) + ": " + str(quick_capture_error))
            except:
                pass

    captured["quick_run_saved_gui_field_count"] = int(gui_count)
    captured["quick_run_save_schema"] = "v196-all-gui-settings"
    return captured


def quick_run_storage_dir():
    """Return the dedicated portable Quick Runs folder, creating it as needed."""
    folder = os.path.join(quick_run_app_dir(), QUICK_RUN_FOLDER_NAME)
    try:
        if not os.path.isdir(folder):
            os.makedirs(folder)
    except:
        pass
    return folder


def migrate_legacy_quick_run_files():
    """Move older root-level Quick Run JSON files into the dedicated folder."""
    app_dir = quick_run_app_dir()
    storage_dir = quick_run_storage_dir()
    if os.path.abspath(app_dir) == os.path.abspath(storage_dir):
        return
    try:
        names = list(os.listdir(app_dir))
    except:
        names = []
    for file_name in names:
        if QUICK_RUN_FILE_PATTERN.match(str(file_name)) is None:
            continue
        source = os.path.join(app_dir, str(file_name))
        target = os.path.join(storage_dir, str(file_name))
        if not os.path.isfile(source):
            continue
        try:
            if os.path.isfile(target):
                source_mtime = os.path.getmtime(source)
                target_mtime = os.path.getmtime(target)
                if source_mtime > target_mtime:
                    os.remove(target)
                    os.rename(source, target)
                    IJ.log("Moved newer legacy Quick Run into Quick Runs folder: " + str(target))
                else:
                    os.remove(source)
                    IJ.log("Removed older duplicate root-level Quick Run: " + str(source))
            else:
                os.rename(source, target)
                IJ.log("Moved legacy Quick Run into Quick Runs folder: " + str(target))
        except Exception as migration_error:
            IJ.log("Could not migrate legacy Quick Run " + str(source) + ": " + str(migration_error))


def quick_run_target_path(slot, name):
    slot_number = max(1, min(QUICK_RUN_SLOT_COUNT, int(slot)))
    return os.path.join(quick_run_storage_dir(), "quick run" + str(slot_number) + "-(" + quick_run_safe_file_name(name) + ").json")


def quick_run_files_for_slot(slot):
    slot_number = int(slot)
    found = []
    migrate_legacy_quick_run_files()
    root_dir = quick_run_storage_dir()
    try:
        for file_name in os.listdir(root_dir):
            match = QUICK_RUN_FILE_PATTERN.match(str(file_name))
            if match is None or int(match.group(1)) != slot_number:
                continue
            path = os.path.join(root_dir, str(file_name))
            if os.path.isfile(path):
                found.append(path)
    except Exception as e:
        IJ.log("Could not scan Quick Run files: " + str(e))
    try:
        found.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    except:
        found.sort()
    return found


def load_quick_run_file(path, expected_slot=None):
    record = {
        "slot": int(expected_slot) if expected_slot is not None else 0,
        "name": "",
        "path": str(path),
        "settings": None,
        "error": ""
    }
    try:
        reader = codecs.open(str(path), "r", "utf-8")
        try:
            payload = json.loads(reader.read())
        finally:
            reader.close()
        if not isinstance(payload, dict):
            raise RuntimeError("Quick Run file must contain a JSON object")
        raw_settings = payload.get("quick_run_settings", None)
        if not isinstance(raw_settings, dict):
            raise RuntimeError("quick_run_settings must be a JSON object")
        file_slot = int(payload.get("quick_run_slot", record["slot"] if record["slot"] > 0 else 0))
        if record["slot"] <= 0:
            record["slot"] = file_slot
        raw_name = str(payload.get("quick_run_name", "")).strip()
        if raw_name == "":
            match = QUICK_RUN_FILE_PATTERN.match(os.path.basename(str(path)))
            if match is not None:
                raw_name = str(match.group(2)).strip()
        if raw_name == "":
            raw_name = "Quick Run " + str(record["slot"])
        record["name"] = raw_name
        record["settings"] = dict(raw_settings)
        if expected_slot is not None and file_slot not in [0, int(expected_slot)]:
            IJ.log("Quick Run slot metadata mismatch in " + str(path) + "; using filename slot " + str(expected_slot))
        return record
    except Exception as e:
        record["error"] = str(e)
        return record


def discover_quick_runs():
    records = {}
    for slot in range(1, QUICK_RUN_SLOT_COUNT + 1):
        default_record = {
            "slot": slot,
            "name": "Quick Run " + str(slot),
            "path": "",
            "settings": None,
            "error": ""
        }
        files = quick_run_files_for_slot(slot)
        first_error = ""
        chosen = None
        for path in files:
            loaded = load_quick_run_file(path, slot)
            if loaded.get("settings") is not None:
                chosen = loaded
                break
            if first_error == "":
                first_error = str(loaded.get("error", ""))
        if chosen is None:
            if len(files) > 0:
                default_record["path"] = files[0]
                default_record["error"] = first_error
                match = QUICK_RUN_FILE_PATTERN.match(os.path.basename(files[0]))
                if match is not None and str(match.group(2)).strip() != "":
                    default_record["name"] = str(match.group(2)).strip()
            records[slot] = default_record
        else:
            records[slot] = chosen
            if len(files) > 1:
                IJ.log("Multiple Quick Run " + str(slot) + " files found. Loaded newest valid file: " + str(chosen.get("path", "")))
    return records


def quick_run_process_summary(settings):
    try:
        steps = normalize_pipeline_steps(settings.get("process_pipeline_steps", []), settings)
        labels = []
        for step in steps:
            token = str(step.get("operation", "none"))
            if token == "none":
                continue
            label = pipeline_operation_label(token)
            if not bool(step.get("enabled", True)):
                label += " [OFF]"
            labels.append(label)
        if len(labels) <= 0:
            return "No processing pipeline saved"
        text = " > ".join(labels)
        if len(text) > 170:
            text = text[:167] + "..."
        return text
    except Exception as e:
        return "Process summary unavailable: " + str(e)


def quick_run_portable_value(value):
    if value is None or isinstance(value, (bool, int, long, float, basestring)):
        return value
    if isinstance(value, dict):
        out = {}
        for key in value.keys():
            out[str(key)] = quick_run_portable_value(value[key])
        return out
    if isinstance(value, (list, tuple)):
        return [quick_run_portable_value(item) for item in value]
    return str(value)


def quick_run_clean_settings(settings):
    cleaned = {}
    for key in settings.keys():
        key_text = str(key)
        if key_text.startswith("_"):
            continue
        if key_text in ["save_settings_as_default", "save_named_preset", "load_named_preset"]:
            cleaned[key_text] = False
        else:
            cleaned[key_text] = quick_run_portable_value(settings[key])
    return cleaned


def save_quick_run_file(slot, name, settings):
    slot_number = max(1, min(QUICK_RUN_SLOT_COUNT, int(slot)))
    display_name = str(name).strip()
    if display_name == "":
        display_name = "Quick Run " + str(slot_number)
    target = quick_run_target_path(slot_number, display_name)
    temp_path = target + ".tmp"
    cleaned = quick_run_clean_settings(settings)
    payload = {
        "quick_run_format_version": 2,
        "quick_run_slot": slot_number,
        "quick_run_name": display_name,
        "quick_run_settings": cleaned
    }
    writer = None
    try:
        writer = codecs.open(temp_path, "w", "utf-8")
        writer.write(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))
        writer.write(u"\n")
    finally:
        if writer is not None:
            writer.close()
    if os.path.isfile(target):
        os.remove(target)
    os.rename(temp_path, target)
    for old_path in quick_run_files_for_slot(slot_number):
        try:
            if os.path.abspath(old_path) != os.path.abspath(target):
                os.remove(old_path)
        except Exception as cleanup_error:
            IJ.log("Could not remove older Quick Run file " + str(old_path) + ": " + str(cleanup_error))
    IJ.log("Saved portable Quick Run " + str(slot_number) + ": " + str(target))
    return target


def set_quick_run_component_value(component, value):
    if component is None:
        return False
    try:
        if isinstance(component, JCheckBox):
            if isinstance(value, basestring):
                component.setSelected(pref_text_to_bool(value, component.isSelected()))
            else:
                component.setSelected(bool(value))
            return True
        if isinstance(component, JComboBox):
            wanted = str(value)
            selected = False
            for index in range(component.getItemCount()):
                item = component.getItemAt(index)
                if str(item) == wanted:
                    component.setSelectedIndex(index)
                    selected = True
                    break
            if not selected:
                for index in range(component.getItemCount()):
                    item = component.getItemAt(index)
                    if str(item).lower() == wanted.lower():
                        component.setSelectedIndex(index)
                        selected = True
                        break
            return selected
        if isinstance(component, JTextField):
            component.setText("" if value is None else str(value))
            return True
    except Exception as e:
        IJ.log("Could not apply Quick Run GUI value: " + str(e))
    return False


def apply_quick_run_settings_to_fields(fields, saved_settings, processing_panel):
    merged = dict(DEFAULTS)
    if isinstance(saved_settings, dict):
        for key in saved_settings.keys():
            merged[str(key)] = saved_settings[key]

    def apply_non_pipeline_values():
        for key in sorted(merged.keys()):
            if key in QUICK_RUN_PROCESSING_KEYS or str(key).startswith("pipeline_") or str(key).startswith("_"):
                continue
            component = fields.get(key)
            if component is not None:
                set_quick_run_component_value(component, merged[key])

    apply_non_pipeline_values()

    steps = normalize_pipeline_steps(merged.get("process_pipeline_steps", []), merged)
    combos = fields.get("_pipeline_order_combos", [])
    slot_count = len(combos)
    slot_steps = {}
    next_free = 1
    for index, step in enumerate(steps):
        try:
            slot_number = int(step.get("slot", index + 1))
        except:
            slot_number = index + 1
        if slot_number < 1 or slot_number > slot_count or slot_number in slot_steps:
            while next_free in slot_steps and next_free <= slot_count:
                next_free += 1
            slot_number = next_free
        if slot_number >= 1 and slot_number <= slot_count:
            slot_steps[slot_number] = dict(step)

    fields["_quick_run_loading"] = True
    try:
        for slot_number in range(1, slot_count + 1):
            token = str(slot_steps.get(slot_number, {}).get("operation", "none"))
            combo = combos[slot_number - 1]
            set_quick_run_component_value(combo, pipeline_operation_label(token))
    finally:
        fields["_quick_run_loading"] = False

    cache = {}
    for slot_number in sorted(slot_steps.keys()):
        step = slot_steps[slot_number]
        prefix = pipeline_slot_prefix(slot_number)
        for key in step.keys():
            if str(key) in ["operation", "slot"]:
                continue
            cache[prefix + str(key)] = quick_run_portable_value(step[key])
    # Remove stale dynamic components before rebuilding. Otherwise the Processing
    # page snapshot overwrites the just-loaded Quick Run values with the old GUI.
    clear_dynamic_pipeline_field_keys(fields)
    try:
        processing_panel.removeAll()
    except:
        pass
    fields["_pipeline_value_cache"] = dict(cache)
    build_dynamic_processing_page(processing_panel, fields)

    # A second pass restores fields that may have been changed by combo-box listeners.
    apply_non_pipeline_values()
    try:
        processing_panel.revalidate()
        processing_panel.repaint()
    except:
        pass
    return steps


# ======================================================
# SAVED DEFAULT SETTINGS HELPERS
# ======================================================

SETTINGS_PREF_PREFIX = "GDL_ImageJ_JMP_Report."

def bool_to_pref_text(value):
    if bool(value):
        return "true"
    return "false"

def pref_text_to_bool(value, fallback):
    try:
        s = str(value).strip().lower()
        if s in ["true", "1", "yes", "y", "on"]:
            return True
        if s in ["false", "0", "no", "n", "off"]:
            return False
    except:
        pass
    return bool(fallback)

def load_saved_defaults_into_defaults():
    try:
        for key in list(DEFAULTS.keys()):
            # Do not make the "save default" checkbox sticky.
            if key in ["save_settings_as_default", "save_named_preset", "load_named_preset"]:
                continue

            default_value = DEFAULTS[key]
            pref_key = SETTINGS_PREF_PREFIX + str(key)

            try:
                if isinstance(default_value, bool):
                    raw = Prefs.get(pref_key, bool_to_pref_text(default_value))
                    DEFAULTS[key] = pref_text_to_bool(raw, default_value)
                elif isinstance(default_value, int) and not isinstance(default_value, bool):
                    raw = Prefs.get(pref_key, str(default_value))
                    DEFAULTS[key] = int(float(str(raw)))
                elif isinstance(default_value, float):
                    raw = Prefs.get(pref_key, str(default_value))
                    DEFAULTS[key] = float(str(raw))
                else:
                    DEFAULTS[key] = str(Prefs.get(pref_key, str(default_value)))
            except:
                DEFAULTS[key] = default_value

    except Exception as e:
        IJ.log("Could not load saved GDL defaults: " + str(e))


def preset_pref_prefix(name):
    safe = safe_name(str(name))
    if safe == "":
        safe = "default"
    return SETTINGS_PREF_PREFIX + "preset." + safe + "."

def save_named_preset(settings, preset_name):
    try:
        if preset_name is None or str(preset_name).strip() == "":
            IJ.log("Named preset was not saved because no preset name was entered.")
            return

        prefix = preset_pref_prefix(preset_name)
        for key in settings.keys():
            if key in ["save_settings_as_default", "save_named_preset", "load_named_preset"]:
                continue

            value = settings[key]
            if isinstance(value, bool):
                Prefs.set(prefix + str(key), bool_to_pref_text(value))
            else:
                Prefs.set(prefix + str(key), str(value))

        try:
            Prefs.savePreferences()
        except:
            pass

        IJ.log("Saved named preset: " + str(preset_name))
    except Exception as e:
        IJ.log("Could not save named preset: " + str(e))

def load_named_preset_into_settings(settings, preset_name):
    try:
        if preset_name is None or str(preset_name).strip() == "":
            IJ.log("Named preset was not loaded because no preset name was entered.")
            return settings

        prefix = preset_pref_prefix(preset_name)
        out = dict(settings)

        for key in DEFAULTS.keys():
            if key in ["save_settings_as_default", "save_named_preset", "load_named_preset"]:
                continue

            default_value = DEFAULTS[key]
            current_value = out.get(key, default_value)
            raw = Prefs.get(prefix + str(key), None)

            if raw is None:
                continue

            try:
                if isinstance(default_value, bool):
                    out[key] = pref_text_to_bool(raw, current_value)
                elif isinstance(default_value, int) and not isinstance(default_value, bool):
                    out[key] = int(float(str(raw)))
                elif isinstance(default_value, float):
                    out[key] = float(str(raw))
                else:
                    out[key] = str(raw)
            except:
                out[key] = current_value

        out["preset_name"] = str(preset_name)
        out["load_named_preset"] = False
        IJ.log("Loaded named preset: " + str(preset_name))
        return out

    except Exception as e:
        IJ.log("Could not load named preset: " + str(e))
        return settings


def save_settings_as_defaults(settings):
    try:
        for key in settings.keys():
            # Do not make the "save default" checkbox sticky.
            if key in ["save_settings_as_default", "save_named_preset", "load_named_preset"]:
                continue

            value = settings[key]
            pref_key = SETTINGS_PREF_PREFIX + str(key)

            if isinstance(value, bool):
                Prefs.set(pref_key, bool_to_pref_text(value))
            else:
                Prefs.set(pref_key, str(value))

        try:
            Prefs.savePreferences()
        except:
            pass

        IJ.log("Saved current GDL ImageJ/JMP settings as defaults for next run.")

    except Exception as e:
        IJ.log("Could not save GDL settings as defaults: " + str(e))


# ======================================================
# DEFAULT SETTINGS
# ======================================================
# DEFAULTS is defined in Defaults and Other Stuff/GDL_User_Defaults.py.
if "DEFAULTS" not in globals():
    raise RuntimeError("Missing DEFAULTS. Keep Defaults and Other Stuff beside RUN IN FIJI.py.")


IMAGE_EXTENSIONS = [".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp", ".gif"]

# ======================================================
# BASIC HELPERS
# ======================================================

def safe_name(name):
    bad = ['\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ']
    out = str(name)
    for b in bad:
        out = out.replace(b, "_")
    return out

def short_safe_name(name, max_len):
    # Keeps generated batch paths below Windows/JMP path limits.
    # JMP can fail to open CSVs when full paths are near/over 260 characters.
    s = safe_name(name)
    try:
        max_len = int(max_len)
    except:
        max_len = 32

    if max_len < 8:
        max_len = 8

    if len(s) <= max_len:
        return s

    head_len = int(max_len * 0.65)
    tail_len = max_len - head_len - 1
    if tail_len < 4:
        tail_len = 4
        head_len = max_len - tail_len - 1

    return s[:head_len] + "_" + s[-tail_len:]

def ultra_short_run_id(base_name, run_label, run_counter_hint):
    b = short_safe_name(base_name, 18)
    l = short_safe_name(run_label, 16)
    if l == "" or l == "normal":
        l = "normal"
    return b + "_R" + str(run_counter_hint) + "_" + l


def save_fiji_log_file(output_root, errors=None, stage="", filename="Fiji_Log.txt", settings=None):
    """Persist the current ImageJ/Fiji Log window text for post-run debugging."""
    try:
        if settings is not None and not bool(settings.get("save_fiji_log_enabled", True)):
            return ""
        if output_root in [None, ""]:
            return ""
        ensure_dir(output_root)
        log_path = os.path.join(str(output_root), str(filename))
        lines = []
        lines.append("YOURE A BETA v209 Fiji/ImageJ Log")
        lines.append("Saved: " + time.strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("Stage: " + str(stage))
        lines.append("Output root: " + str(output_root))
        lines.append("")
        lines.append("===== FIJI / IMAGEJ LOG =====")
        try:
            current_log = IJ.getLog()
        except Exception as e_get_log:
            current_log = "Could not read IJ.getLog(): " + str(e_get_log)
        if current_log in [None, ""]:
            current_log = "[ImageJ Log window was empty.]"
        lines.append(str(current_log))
        lines.append("")
        lines.append("===== COLLECTED ERRORS =====")
        if errors is None or len(errors) == 0:
            lines.append("[No collected errors.] ")
        else:
            for index in range(len(errors)):
                lines.append(str(index + 1) + ". " + str(errors[index]))
        with codecs.open(log_path, "w", "utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        IJ.log("Fiji log saved: " + log_path)
        return log_path
    except Exception as e_save_log:
        try:
            IJ.log("Could not save Fiji log file: " + str(e_save_log))
        except:
            pass
        return ""

def preferred_gdl_work_zone_directory():
    candidates = [
        r"C:/Fixture/GDL",
        r"C:/Fixture/GDL"
    ]
    for candidate in candidates:
        try:
            if File(candidate).isDirectory():
                return candidate
        except:
            pass
    return ""


def set_gdl_file_chooser_start_directory():
    start_dir = preferred_gdl_work_zone_directory()
    if start_dir == "":
        return ""
    try:
        OpenDialog.setDefaultDirectory(start_dir)
    except:
        pass
    try:
        DirectoryChooser.setDefaultDirectory(start_dir)
    except:
        pass
    return start_dir


def ensure_dir(path):
    f = File(path)
    if not f.exists():
        f.mkdirs()

def csv_escape(value):
    s = str(value)
    s = s.replace('"', '""')
    if "," in s or '"' in s or "\n" in s or "\r" in s:
        s = '"' + s + '"'
    return s

def fmt_num(value, decimals):
    try:
        if value is None:
            return ""
        f = float(value)
        if math.isnan(f):
            return ""
        return ("%." + str(decimals) + "f") % f
    except:
        return csv_escape(value)

def write_csv(path, headers, rows, decimals):
    f = open(path, "w")
    f.write(",".join([csv_escape(h) for h in headers]) + "\n")

    for row in rows:
        out = []
        for v in row:
            if isinstance(v, int) or isinstance(v, float):
                out.append(fmt_num(v, decimals))
            else:
                out.append(csv_escape(v))
        f.write(",".join(out) + "\n")

    f.close()

def unit_to_mm_factor(unit):
    if unit is None:
        return 1.0

    u = str(unit).lower()
    u = u.replace("µ", "u")
    u = u.replace("μ", "u")
    u = u.strip()

    if u in ["mm", "millimeter", "millimeters"]:
        return 1.0
    if u in ["um", "micron", "microns", "micrometer", "micrometers"]:
        return 0.001
    if u in ["nm", "nanometer", "nanometers"]:
        return 0.000001
    if u in ["cm", "centimeter", "centimeters"]:
        return 10.0
    if u in ["m", "meter", "meters"]:
        return 1000.0

    return 1.0

def get_headings(rt):
    heads = rt.getHeadings()
    return [str(h) for h in heads]

def rt_value(rt, heading, row):
    try:
        return rt.getValue(heading, row)
    except:
        return None

def jsl_path(path):
    return str(path).replace("\\", "/").replace('"', '\\"')

def jsl_string(value):
    # Escape user-entered strings before placing them inside generated JMP/JSL quotes.
    return str(value).replace("\\", "\\\\").replace('"', '\\"')

def is_image_file(path):
    lower = str(path).lower()
    for ext in IMAGE_EXTENSIONS:
        if lower.endswith(ext):
            return True
    return False

def is_tif_image(path):
    lower = str(path).lower()
    return lower.endswith(".tif") or lower.endswith(".tiff")

def warn_if_non_tif_images(images):
    try:
        non_tif = []
        for p in images:
            if not is_tif_image(p):
                non_tif.append(os.path.basename(str(p)))

        if len(non_tif) > 0:
            msg = "Warning: one or more selected images are not .tif/.tiff files.\n\n"
            msg += "The script can still run, but calibrated scale/metadata and image quality may be less reliable.\n\n"
            msg += "Non-TIF images found:\n"

            max_show = 12
            for i in range(min(len(non_tif), max_show)):
                msg += "- " + str(non_tif[i]) + "\n"

            if len(non_tif) > max_show:
                msg += "... plus " + str(len(non_tif) - max_show) + " more\n"

            IJ.showMessage("Non-TIF Image Warning", msg)
    except Exception as e:
        IJ.log("Could not show non-TIF warning: " + str(e))

def collect_images(folder, include_subfolders):
    found = []
    if include_subfolders:
        for root, dirs, files in os.walk(folder):
            files.sort()
            for fn in files:
                p = os.path.join(root, fn)
                if is_image_file(p):
                    found.append(p)
    else:
        for fn in sorted(os.listdir(folder)):
            p = os.path.join(folder, fn)
            if os.path.isfile(p) and is_image_file(p):
                found.append(p)
    return found

def find_jmp_exe(settings):
    p = settings.get("jmp_exe", "")
    if p is not None and str(p).strip() != "":
        if File(str(p)).exists():
            return str(p)

    for p2 in COMMON_JMP_PATHS:
        if File(p2).exists():
            return p2

    # Install layouts vary between JMP, JMP Pro, and JMP Student releases.
    # Perform a bounded fallback scan instead of silently leaving the JMP queue idle.
    roots = ["C:/Program Files/JMP", "C:/Program Files/SAS", "C:/Program Files"]
    for root in roots:
        try:
            if not os.path.isdir(root):
                continue
            root_depth = str(root).replace("\\", "/").count("/")
            for walk_root, dirs, files in os.walk(root):
                depth = str(walk_root).replace("\\", "/").count("/") - root_depth
                if depth > 5:
                    dirs[:] = []
                    continue
                lower_root = str(walk_root).lower()
                if "jmp" not in lower_root and root != "C:/Program Files":
                    continue
                for filename in files:
                    if str(filename).lower() == "jmp.exe":
                        candidate = os.path.join(walk_root, filename)
                        if File(candidate).exists():
                            return candidate
        except:
            pass
    return ""

def parse_bool_checkbox(cb):
    return bool(cb.isSelected())

def parse_text(tf):
    return str(tf.getText()).strip()

def parse_float_field(tf, label):
    txt = parse_text(tf)
    try:
        return float(txt)
    except:
        raise Exception("Invalid number for " + label + ": " + txt)

def parse_int_field(tf, label):
    txt = parse_text(tf)
    try:
        return int(float(txt))
    except:
        raise Exception("Invalid integer for " + label + ": " + txt)

def bool_to_text(v):
    if v:
        return "true"
    return "false"


def mark_beast_worker_content_progress(stage, detail=""):
    """Touch the worker's *content* progress marker, separate from heartbeat.

    v209 dynamic-agent invariant: heartbeat proves JVM/thread liveness only. This marker
    is advanced by real processing milestones and throttled inner-loop work tokens.
    The v209 controller supervises one exact run per process and uses this marker only
    as a secondary stall signal; failed runs are requeued independently.
    """
    try:
        cfg = globals().get("BEAST_FIJI_WORKER_CONFIG", None)
        if cfg is None:
            return
        progress_path = str(cfg.get("progress_path", "") or "").strip()
        if progress_path == "":
            return
        worker_id = int(cfg.get("worker_id", 0))
        text = ("worker_id=" + str(worker_id) + ";stage=" + str(stage) +
                ";time=" + str(time.time()) + ";detail=" + str(detail).replace("\n", " ").replace(";", ","))
        pf = open(progress_path, "w")
        try:
            pf.write(text)
        finally:
            pf.close()
    except:
        # Progress instrumentation must never break image analysis.
        pass


_BEAST_BUSY_PROGRESS_LAST_AT = 0.0
_BEAST_BUSY_PROGRESS_SEQUENCE = 0

def mark_beast_worker_busy_progress(stage, detail="", min_interval_sec=15.0, force=False):
    """Report measurable inner-loop advancement without hammering the disk.

    Callers pass changing work coordinates (parent/radius/row/candidate/etc.). The
    marker is written at most once per ``min_interval_sec`` unless ``force`` is
    requested. If a Java/Fiji primitive itself freezes, this function is never
    reached again and the strict content watchdog can still restart the worker.
    """
    global _BEAST_BUSY_PROGRESS_LAST_AT, _BEAST_BUSY_PROGRESS_SEQUENCE
    try:
        cfg = globals().get("BEAST_FIJI_WORKER_CONFIG", None)
        if cfg is None:
            return
        progress_path = str(cfg.get("progress_path", "") or "").strip()
        if progress_path == "":
            return
        now_value = time.time()
        interval = max(1.0, float(min_interval_sec))
        if (not bool(force)) and now_value - float(_BEAST_BUSY_PROGRESS_LAST_AT) < interval:
            return
        _BEAST_BUSY_PROGRESS_LAST_AT = now_value
        _BEAST_BUSY_PROGRESS_SEQUENCE += 1
        busy_detail = ("seq=" + str(_BEAST_BUSY_PROGRESS_SEQUENCE) +
                       ",work=" + str(detail).replace("\n", " ").replace(";", ","))
        mark_beast_worker_content_progress(str(stage), busy_detail)
    except:
        pass


def beast_jmp_histograms_enabled(settings):
    """BEAST MODE uses JMP only when histogram/graph Word output is requested."""
    try:
        if not bool(settings.get("beast_mode_enabled", False)):
            return True
        return bool(settings.get("beast_create_graph_word_report", False))
    except:
        return False


def run_image_outputs_enabled(settings):
    """Suppress image writes only when BEAST truly has no visual/report output.

    v209: external workers intentionally set create_word_report=False so they do not
    each build DOCX files. That worker-local flag must NOT suppress the images that
    the controller later needs for BEAST Word reports. BEAST report grouping is
    independent from JMP graph generation, so honor the single word_report_mode selection directly.
    """
    try:
        if not bool(settings.get("beast_mode_enabled", False)):
            return True
        graph_output = bool(settings.get("beast_create_graph_word_report", False))
        normal_word_output = bool(settings.get("create_word_report", False))
        beast_word_mode = str(settings.get("word_report_mode", settings.get("beast_word_report_mode", "No Word reports")) or "No Word reports").strip().lower()
        beast_word_output = beast_word_mode not in ["", "no word reports", "none", "off", "disabled"]
        return graph_output or normal_word_output or beast_word_output
    except:
        return True


def pore_epd_mm_from_area_mm2(area_mm2):
    try:
        area_value = float(area_mm2)
        if area_value > 0.0:
            return math.sqrt((4.0 * area_value) / math.pi)
    except:
        pass
    return 0.0


def resolve_epd_between_high_mm(low_mm, manual_high_mm, auto_enabled, offset_um):
    """Return the effective JMP between-band upper cutoff in millimeters."""
    try:
        low_value = float(low_mm)
    except:
        low_value = 0.0
    try:
        manual_value = float(manual_high_mm)
    except:
        manual_value = low_value
    try:
        offset_value = float(offset_um)
    except:
        offset_value = 2.0

    if low_value < 0.0:
        low_value = 0.0
    if manual_value < 0.0:
        manual_value = 0.0
    if offset_value < 0.0:
        offset_value = 0.0

    if bool(auto_enabled):
        return low_value + (offset_value / 1000.0)
    return manual_value


def resolve_epd_between_preset(preset_name, custom_low_mm, custom_high_mm):
    """Return low, high, and source text for the delete-EPD preset.

    The preset starts with the delete cutoff and automatically derives the active
    between-count band and pore-map upper limit. Legacy v115 labels are accepted
    so previously saved presets still load correctly.
    """
    preset = str(preset_name).strip()
    preset_values = {
        "Delete at 3 microns": (0.003, 0.005),
        "Delete at 5 microns": (0.005, 0.007),
        "Delete at 10 microns": (0.010, 0.012),
        # Backward compatibility with v115 saved preferences.
        "3-5 microns": (0.003, 0.005),
        "5-7 microns": (0.005, 0.007),
        "10-12 microns": (0.010, 0.012)
    }

    if preset in preset_values:
        low_value, high_value = preset_values[preset]
        return float(low_value), float(high_value), "Delete preset: " + preset

    try:
        low_value = float(custom_low_mm)
    except:
        low_value = 0.0
    try:
        high_value = float(custom_high_mm)
    except:
        high_value = low_value

    if low_value < 0.0:
        low_value = 0.0
    if high_value < 0.0:
        high_value = 0.0
    if high_value < low_value:
        temp_value = low_value
        low_value = high_value
        high_value = temp_value

    return float(low_value), float(high_value), "Custom"


def threshold_compact_number(value):
    try:
        f = float(value)
        if abs(f - round(f)) < 0.000000001:
            return str(int(round(f)))
        return ("%.6f" % f).rstrip("0").rstrip(".")
    except:
        return str(value)


def threshold_mode_is_gray(force_8bit=True):
    try:
        if isinstance(force_8bit, bool):
            return bool(force_8bit)
    except:
        pass
    try:
        s = str(force_8bit).strip().lower()
        if s in ["false", "0", "no", "off", "percent", "%"]:
            return False
        if s in ["true", "1", "yes", "on", "gray", "grey"]:
            return True
    except:
        pass
    return bool(force_8bit)


def threshold_input_mode_label(force_8bit=True):
    if threshold_mode_is_gray(force_8bit):
        return "8-bit gray values (0-255)"
    return "Cumulative image-histogram percentile (0-100%)"


def threshold_value_percent(value):
    """Legacy linear 0-255 display helper; histogram-aware percentages are calculated per image."""
    try:
        return (float(value) / 255.0) * 100.0
    except:
        return None


def threshold_percent_gray_value(value):
    """Legacy fallback only. Percent-mode processing uses the actual image histogram instead."""
    try:
        return (float(value) / 100.0) * 255.0
    except:
        return None


def threshold_input_to_gray(value, force_8bit=True):
    """Return a gray input directly. Percent inputs need an image histogram and therefore return None here."""
    try:
        v = float(value)
    except:
        return None

    if not threshold_mode_is_gray(force_8bit):
        return None

    if v < 0.0:
        v = 0.0
    if v > 255.0:
        v = 255.0
    return float(v)


def threshold_input_to_percent(value, force_8bit=True):
    """Return a requested histogram percentile. Gray-input histogram percent is calculated per image."""
    try:
        v = float(value)
    except:
        return None

    if threshold_mode_is_gray(force_8bit):
        return None

    if v < 0.0:
        v = 0.0
    if v > 100.0:
        v = 100.0
    return float(v)


def threshold_histogram_counts_from_processor(ip):
    try:
        histogram = ip.getHistogram()
        counts = []
        for i in range(256):
            counts.append(int(histogram[i]))
        return counts
    except:
        counts = [0] * 256
        try:
            pixels = ip.getPixels()
            for raw_value in pixels:
                v = int(raw_value)
                if v < 0:
                    v = v + 256
                if v < 0:
                    v = 0
                if v > 255:
                    v = 255
                counts[v] = counts[v] + 1
        except:
            pass
        return counts


def threshold_histogram_percentile_to_gray(histogram, percent_value):
    try:
        p = float(percent_value)
    except:
        return None
    if p < 0.0:
        p = 0.0
    if p > 100.0:
        p = 100.0

    total = 0
    for count in histogram:
        total = total + int(count)
    if total <= 0:
        return None

    if p <= 0.0:
        for i in range(len(histogram)):
            if int(histogram[i]) > 0:
                return float(i)
        return 0.0
    if p >= 100.0:
        for i in range(len(histogram) - 1, -1, -1):
            if int(histogram[i]) > 0:
                return float(i)
        return 255.0

    target = (p / 100.0) * float(total)
    cumulative = 0.0
    for i in range(len(histogram)):
        cumulative = cumulative + float(histogram[i])
        if cumulative >= target:
            return float(i)
    return 255.0


def threshold_histogram_boundary_percent(histogram, gray_value, include_gray):
    try:
        gray = int(math.floor(float(gray_value)))
    except:
        return None
    if gray < 0:
        gray = 0
    if gray > 255:
        gray = 255

    total = 0
    for count in histogram:
        total = total + int(count)
    if total <= 0:
        return None

    last_index = gray if include_gray else gray - 1
    if last_index < 0:
        return 0.0
    cumulative = 0
    for i in range(0, min(255, last_index) + 1):
        cumulative = cumulative + int(histogram[i])
    return (float(cumulative) / float(total)) * 100.0


def threshold_limits_from_processor(ip, threshold_min, threshold_max, force_8bit=True):
    histogram = threshold_histogram_counts_from_processor(ip)
    gray_mode = threshold_mode_is_gray(force_8bit)

    if gray_mode:
        lower = threshold_input_to_gray(threshold_min, True)
        upper = threshold_input_to_gray(threshold_max, True)
    else:
        lower = threshold_histogram_percentile_to_gray(histogram, threshold_min)
        upper = threshold_histogram_percentile_to_gray(histogram, threshold_max)

    if lower is None or upper is None:
        return None
    if upper < lower:
        temp = lower
        lower = upper
        upper = temp

    lower_percent = threshold_histogram_boundary_percent(histogram, lower, False)
    upper_percent = threshold_histogram_boundary_percent(histogram, upper, True)
    selected_percent = None
    if lower_percent is not None and upper_percent is not None:
        selected_percent = max(0.0, upper_percent - lower_percent)

    total_pixels = 0
    for count in histogram:
        total_pixels = total_pixels + int(count)

    return {
        "lower_gray": float(lower),
        "upper_gray": float(upper),
        "lower_histogram_percent": lower_percent,
        "upper_histogram_percent": upper_percent,
        "selected_histogram_percent": selected_percent,
        "total_pixels": total_pixels,
        "histogram": histogram
    }


def threshold_value_with_equivalent(value, force_8bit=True):
    if threshold_mode_is_gray(force_8bit):
        return threshold_compact_number(value) + " gray (histogram % calculated from each image)"
    return threshold_compact_number(value) + "% cumulative histogram percentile"


def threshold_range_with_percent(threshold_min, threshold_max, force_8bit=True):
    """Describe selected threshold units without inventing a gray/percent conversion before an image is loaded."""
    if threshold_mode_is_gray(force_8bit):
        return (
            threshold_compact_number(threshold_min) + " to " + threshold_compact_number(threshold_max) +
            " gray values; actual cumulative histogram % is calculated per image"
        )
    return (
        threshold_compact_number(threshold_min) + "% to " + threshold_compact_number(threshold_max) +
        "% of the cumulative preprocessed-image histogram; gray cutoffs are calculated per image"
    )


def threshold_sweep_range_with_percent(start, end, step, force_8bit=True):
    if threshold_mode_is_gray(force_8bit):
        return (threshold_compact_number(start) + " to " + threshold_compact_number(end) +
                " gray by " + threshold_compact_number(step) +
                "; histogram % calculated per image")
    return (threshold_compact_number(start) + "% to " + threshold_compact_number(end) +
            "% by " + threshold_compact_number(step) +
            " cumulative-histogram percentage points; gray cutoffs calculated per image")



def sweep_until_metric_is_percent(metric_name):
    name = str(metric_name).strip()
    if name.startswith("%"):
        return True
    if name in ["Area %", "Original Area %"]:
        return True
    return False


def parse_sweep_until_target(raw_value, metric_name):
    """Parse a number or a value ending in %. Percent symbols are valid for percent metrics."""
    txt = str(raw_value).strip()
    if txt == "":
        raise Exception("Enter a Sweep Until target value.")

    had_percent = txt.endswith("%")
    if had_percent:
        txt = txt[:-1].strip()
        if not sweep_until_metric_is_percent(metric_name):
            raise Exception("A % target can only be used with a percentage summary metric.")

    txt = txt.replace(",", "")
    try:
        return float(txt), had_percent
    except:
        raise Exception("Invalid Sweep Until target value: " + str(raw_value))


def sweep_until_find_heading(headings, candidates):
    try:
        lower_map = {}
        for heading in headings:
            lower_map[str(heading).strip().lower()] = str(heading)
        for candidate in candidates:
            key = str(candidate).strip().lower()
            if key in lower_map:
                return lower_map[key]
    except:
        pass
    return ""


def sweep_until_mean(values):
    usable = []
    for value in values:
        try:
            f = float(value)
            if not math.isnan(f):
                usable.append(f)
        except:
            pass
    if len(usable) <= 0:
        return 0.0
    return sum(usable) / float(len(usable))


def build_sweep_until_metrics(rt, area_to_mm2, image_total_area_mm2, settings):
    """Calculate the immediate ImageJ equivalents of all selectable final-summary metrics."""
    headings = get_headings(rt)
    circ_heading = sweep_until_find_heading(headings, ["Circularity", "Circ", "Circ."])
    round_heading = sweep_until_find_heading(headings, ["Roundness", "Round"])
    solidity_heading = sweep_until_find_heading(headings, ["Solidity", "Solid"])

    records = []
    try:
        original_count = int(rt.size())
    except:
        original_count = 0

    for row_index in range(original_count):
        area_raw = rt_value(rt, "Area", row_index)
        try:
            area_mm2 = float(area_raw) * float(area_to_mm2)
        except:
            area_mm2 = 0.0

        epd_mm = 0.0
        if area_mm2 > 0.0:
            epd_mm = math.sqrt((area_mm2 * 4.0) / math.pi)

        circ = None
        roundness = None
        solidity = None
        if circ_heading != "":
            circ = rt_value(rt, circ_heading, row_index)
        if round_heading != "":
            roundness = rt_value(rt, round_heading, row_index)
        if solidity_heading != "":
            solidity = rt_value(rt, solidity_heading, row_index)

        records.append({
            "area": area_mm2,
            "epd": epd_mm,
            "circ": circ,
            "round": roundness,
            "solidity": solidity
        })

    small_cutoff = float(settings.get("small_epd_cutoff", 0.0))
    cutoff_1 = float(settings.get("epd_cutoff_1", 0.0))
    cutoff_2 = float(settings.get("epd_cutoff_2", 0.0))
    between_low = float(settings.get("epd_between_low", 0.003))
    between_high = float(settings.get("epd_between_high", 0.005))
    circ_cutoff = float(settings.get("circ_cutoff", 0.0))

    small_records = [record for record in records if float(record["epd"]) <= small_cutoff]
    cleaned = [record for record in records if float(record["epd"]) > small_cutoff]

    summary_count = len(cleaned)
    count_above_1 = len([record for record in cleaned if float(record["epd"]) > cutoff_1])
    count_above_2 = len([record for record in cleaned if float(record["epd"]) > cutoff_2])
    # Count from all detected pores so the 3-5 micron preset remains available even
    # when the cleaned-table cutoff removes pores at or below 5 microns.
    count_between = len([record for record in records if float(record["epd"]) >= between_low and float(record["epd"]) < between_high])

    count_circ_below = 0
    for record in cleaned:
        try:
            if record["circ"] is not None and float(record["circ"]) < circ_cutoff:
                count_circ_below += 1
        except:
            pass

    cleaned_epds = [record["epd"] for record in cleaned]
    cleaned_areas = [record["area"] for record in cleaned]
    cleaned_circs = [record["circ"] for record in cleaned if record["circ"] is not None]
    cleaned_rounds = [record["round"] for record in cleaned if record["round"] is not None]
    cleaned_solidities = [record["solidity"] for record in cleaned if record["solidity"] is not None]

    total_area = sum([float(value) for value in cleaned_areas]) if len(cleaned_areas) > 0 else 0.0
    original_total_area = sum([float(record["area"]) for record in records]) if len(records) > 0 else 0.0

    try:
        image_area = float(image_total_area_mm2)
    except:
        image_area = 0.0

    area_percent = 0.0
    original_area_percent = 0.0
    if image_area > 0.0:
        area_percent = (total_area / image_area) * 100.0
        original_area_percent = (original_total_area / image_area) * 100.0

    pct_small = (float(len(small_records)) / float(original_count) * 100.0) if original_count > 0 else 0.0
    pct_above_1 = (float(count_above_1) / float(summary_count) * 100.0) if summary_count > 0 else 0.0
    pct_above_2 = (float(count_above_2) / float(summary_count) * 100.0) if summary_count > 0 else 0.0
    pct_between = (float(count_between) / float(original_count) * 100.0) if original_count > 0 else 0.0
    pct_circ_below = (float(count_circ_below) / float(summary_count) * 100.0) if summary_count > 0 else 0.0

    return {
        "Original pore count": float(original_count),
        "Count EPD <= small cutoff": float(len(small_records)),
        "Summary pore count": float(summary_count),
        "Count EPD > cutoff 1": float(count_above_1),
        "Count EPD > cutoff 2": float(count_above_2),
        "Count EPD between low and high": float(count_between),
        "Count circularity < cutoff": float(count_circ_below),
        "Average EPD (mm)": sweep_until_mean(cleaned_epds),
        "Max EPD (mm)": max(cleaned_epds) if len(cleaned_epds) > 0 else 0.0,
        "Area %": area_percent,
        "Total Area (mm^2)": total_area,
        "Solidity": sweep_until_mean(cleaned_solidities),
        "% EPD <= small cutoff": pct_small,
        "% EPD > cutoff 1": pct_above_1,
        "% EPD > cutoff 2": pct_above_2,
        "% EPD between low and high": pct_between,
        "% circularity < cutoff": pct_circ_below,
        "Average circularity": sweep_until_mean(cleaned_circs),
        "Average roundness": sweep_until_mean(cleaned_rounds),
        "Image total area (mm^2)": image_area,
        "Original Area %": original_area_percent,
        "Original Total Area (mm^2)": original_total_area,
        "Original Solidity": sweep_until_mean([record["solidity"] for record in records if record["solidity"] is not None])
    }


def evaluate_sweep_until_condition(run_result, settings):
    evaluation = {
        "enabled": bool(settings.get("sweep_enabled", False) and settings.get("sweep_until_enabled", False)),
        "metric": str(settings.get("sweep_until_metric", "")),
        "operator": str(settings.get("sweep_until_operator", "")),
        "target_raw": str(settings.get("sweep_until_target_value", "")),
        "target": None,
        "actual": None,
        "met": False,
        "available": False,
        "message": ""
    }

    if not evaluation["enabled"]:
        return evaluation

    metric = evaluation["metric"]
    metrics = run_result.get("sweep_until_metrics", {})
    if metric not in metrics:
        evaluation["message"] = "Sweep Until metric was unavailable: " + metric
        return evaluation

    try:
        target, had_percent = parse_sweep_until_target(evaluation["target_raw"], metric)
        actual = float(metrics[metric])
        tolerance = abs(float(settings.get("sweep_until_equal_tolerance", 0.0001)))
    except Exception as e:
        evaluation["message"] = str(e)
        return evaluation

    operator = evaluation["operator"]
    met = False
    if operator == "Is above":
        met = actual > target
    elif operator == "Is below":
        met = actual < target
    elif operator == "Is equal to":
        met = abs(actual - target) <= tolerance
    elif operator == "Is at or above":
        met = actual >= target
    elif operator == "Is at or below":
        met = actual <= target
    else:
        evaluation["message"] = "Unknown Sweep Until operator: " + operator
        return evaluation

    evaluation["target"] = target
    evaluation["actual"] = actual
    evaluation["available"] = True
    evaluation["met"] = bool(met)
    unit_suffix = "%" if sweep_until_metric_is_percent(metric) else ""
    evaluation["message"] = (
        metric + " = " + threshold_compact_number(actual) + unit_suffix +
        "; target " + operator.lower() + " " + threshold_compact_number(target) + unit_suffix
    )
    return evaluation

# ======================================================
# GLOBAL RUN CONTROL + WINDOW LAYOUT
# ======================================================

RUN_CONTROL = {
    "cancel_requested": False,
    "cancel_reason": "",
    "active_processes": [],
    "last_jmp_tile_time": 0.0
}


def reset_global_run_control():
    RUN_CONTROL["cancel_requested"] = False
    RUN_CONTROL["cancel_reason"] = ""
    RUN_CONTROL["active_processes"] = []
    RUN_CONTROL["last_jmp_tile_time"] = 0.0
    try:
        IJ.resetEscape()
    except:
        pass


def global_cancel_requested():
    return bool(RUN_CONTROL.get("cancel_requested", False))


def raise_if_cancel_requested(context):
    if global_cancel_requested():
        raise Exception("Canceled by user during " + str(context) + ".")


def register_active_process(process):
    if process is None:
        return
    try:
        if process not in RUN_CONTROL["active_processes"]:
            RUN_CONTROL["active_processes"].append(process)
    except:
        pass


def unregister_active_process(process):
    if process is None:
        return
    try:
        RUN_CONTROL["active_processes"].remove(process)
    except:
        pass


def request_global_cancel(reason):
    if global_cancel_requested():
        return
    RUN_CONTROL["cancel_requested"] = True
    RUN_CONTROL["cancel_reason"] = str(reason)
    IJ.log("GLOBAL CANCEL REQUESTED: " + str(reason))
    IJ.showStatus("Cancel requested - stopping ImageJ and JMP workers...")

    # Ask the currently running ImageJ command to stop at its next interruptible point.
    try:
        IJ.setKeyDown(27)  # Escape key
    except:
        pass

    # Immediately terminate every JMP process launched and registered by this script.
    for proc in list(RUN_CONTROL.get("active_processes", [])):
        try:
            destroy_process_safely(proc, True)
        except:
            try:
                proc.destroy()
            except:
                pass


def left_align_component_tree(component):
    if component is None:
        return
    try:
        component.setAlignmentX(0.0)
    except:
        pass
    try:
        children = component.getComponents()
        if children is not None:
            for child in children:
                left_align_component_tree(child)
    except:
        pass


def place_progress_dialog(dialog):
    if dialog is None:
        return
    # Never keep the progress window always-on-top. Native Open/Directory dialogs can
    # otherwise become impossible to click when Windows gives the progress dialog focus.
    try:
        dialog.setAlwaysOnTop(False)
    except:
        pass
    try:
        screen = Toolkit.getDefaultToolkit().getScreenSize()
        width = int(dialog.getWidth()) if int(dialog.getWidth()) > 0 else 720
        x = max(20, int(screen.width) - width - 30)
        dialog.setLocation(int(x), 35)
    except:
        try:
            dialog.setLocation(700, 35)
        except:
            try:
                dialog.setLocationRelativeTo(None)
            except:
                pass


def organize_open_imagej_windows(progress_ui=None):
    """Tile ImageJ image windows while keeping the progress window visible at upper-left."""
    try:
        image_windows = WindowManager.getImageWindows()
        if image_windows is None or len(image_windows) <= 0:
            return
        screen = Toolkit.getDefaultToolkit().getScreenSize()
        reserve_left = 650
        reserve_right = 760 if progress_ui is not None else 20
        x0 = reserve_left
        y0 = 130
        avail_w = max(420, int(screen.width) - x0 - reserve_right)
        avail_h = max(320, int(screen.height) - y0 - 70)
        count = len(image_windows)
        cols = int(math.ceil(math.sqrt(float(count))))
        if cols < 1:
            cols = 1
        rows = int(math.ceil(float(count) / float(cols)))
        cell_w = max(300, int(avail_w / cols))
        cell_h = max(240, int(avail_h / rows))
        i = 0
        for win in image_windows:
            col = i % cols
            row = i // cols
            x = x0 + col * cell_w
            y = y0 + row * cell_h
            try:
                win.setBounds(int(x), int(y), int(cell_w - 10), int(cell_h - 10))
            except:
                try:
                    win.setLocation(int(x), int(y))
                except:
                    pass
            i += 1
    except:
        pass


def maybe_tile_visible_jmp_windows(settings, force=False):
    """Best-effort Windows-only tiling of visible JMP instance main windows."""
    try:
        if not bool(settings.get("beast_organize_windows_enabled", True)):
            return
        if not bool(settings.get("beast_organize_jmp_windows_enabled", False)):
            return
        if os.name != "nt":
            return
        now = time.time()
        if not force and now - float(RUN_CONTROL.get("last_jmp_tile_time", 0.0)) < 3.0:
            return
        RUN_CONTROL["last_jmp_tile_time"] = now

        ps = (
            "$code='using System; using System.Runtime.InteropServices; public static class BeastWin32 { "
            "[DllImport(\"user32.dll\")] public static extern bool MoveWindow(IntPtr hWnd,int X,int Y,int W,int H,bool repaint); }'; "
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -TypeDefinition $code -ErrorAction SilentlyContinue; "
            "$p=@(Get-Process | Where-Object {$_.ProcessName -like 'jmp*' -and $_.MainWindowHandle -ne 0} | Sort-Object Id); "
            "$n=$p.Count; if($n -gt 0){$wa=[System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea; "
            "$top=[int]($wa.Top+[Math]::Min(420,[Math]::Floor($wa.Height*0.45))); $left=[int]($wa.Left+[Math]::Floor($wa.Width*0.50)); "
            "$avail=[int][Math]::Max(420,$wa.Right-$left); $availH=[int][Math]::Max(260,$wa.Bottom-$top); "
            "$cols=[int][Math]::Ceiling([Math]::Sqrt([double]$n)); $rows=[int][Math]::Ceiling([double]$n/$cols); "
            "$w=[int][Math]::Max(180,[Math]::Floor($avail/$cols)); $h=[int][Math]::Max(100,[Math]::Floor($availH/$rows)); "
            "for($i=0;$i -lt $n;$i++){$c=$i%$cols; $r=[int][Math]::Floor($i/$cols); "
            "[BeastWin32]::MoveWindow($p[$i].MainWindowHandle,$left+$c*$w,$top+$r*$h,$w,$h,$true) | Out-Null}}"
        )
        cmd = ArrayList()
        cmd.add("powershell.exe")
        cmd.add("-NoProfile")
        cmd.add("-ExecutionPolicy")
        cmd.add("Bypass")
        cmd.add("-WindowStyle")
        cmd.add("Hidden")
        cmd.add("-Command")
        cmd.add(ps)
        ProcessBuilder(cmd).start()
    except Exception as e:
        IJ.log("Could not organize JMP windows: " + str(e))



def maybe_tile_visible_fiji_worker_windows(settings, force=False):
    """Best-effort Windows tiling for external Fiji BEAST worker main windows."""
    try:
        if not bool(settings.get("beast_organize_windows_enabled", True)):
            return
        if not bool(settings.get("beast_show_fiji_worker_windows", True)):
            return
        if os.name != "nt":
            return
        now = time.time()
        last_time = float(RUN_CONTROL.get("last_fiji_tile_time", 0.0))
        if not force and now - last_time < 3.0:
            return
        RUN_CONTROL["last_fiji_tile_time"] = now
        ps = (
            "$code='using System; using System.Runtime.InteropServices; public static class BeastFijiWin32 { "
            "[DllImport(\"user32.dll\")] public static extern bool MoveWindow(IntPtr hWnd,int X,int Y,int W,int H,bool repaint); }'; "
            "Add-Type -AssemblyName System.Windows.Forms; Add-Type -TypeDefinition $code -ErrorAction SilentlyContinue; "
            "$p=@(Get-Process | Where-Object {$_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like 'Fiji BEAST Worker *'} | Sort-Object Id); "
            "$n=$p.Count; if($n -gt 0){$wa=[System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea; "
            "$top=[int]($wa.Top+[Math]::Min(420,[Math]::Floor($wa.Height*0.45))); $left=$wa.Left; "
            "$avail=[int][Math]::Max(420,[Math]::Floor($wa.Width*0.50)); $availH=[int][Math]::Max(260,$wa.Bottom-$top); "
            "$cols=[int][Math]::Ceiling([Math]::Sqrt([double]$n)); $rows=[int][Math]::Ceiling([double]$n/$cols); "
            "$w=[int][Math]::Max(180,[Math]::Floor($avail/$cols)); $h=[int][Math]::Max(100,[Math]::Floor($availH/$rows)); "
            "for($i=0;$i -lt $n;$i++){$c=$i%$cols; $r=[int][Math]::Floor($i/$cols); "
            "[BeastFijiWin32]::MoveWindow($p[$i].MainWindowHandle,$left+$c*$w,$top+$r*$h,$w,$h,$true) | Out-Null}}"
        )
        cmd = ArrayList()
        cmd.add("powershell.exe")
        cmd.add("-NoProfile")
        cmd.add("-ExecutionPolicy")
        cmd.add("Bypass")
        cmd.add("-WindowStyle")
        cmd.add("Hidden")
        cmd.add("-Command")
        cmd.add(ps)
        ProcessBuilder(cmd).start()
    except Exception as e:
        IJ.log("Could not organize Fiji worker windows: " + str(e))


def place_current_fiji_worker_window(worker_id, worker_count):
    """Place this visible Fiji worker in a deterministic, non-overlapping tile.

    The right side of the primary screen is reserved for the persistent GDL
    progress window. Each worker ID maps to one stable grid cell, so repeated
    controller tiling cannot shuffle workers on top of one another.
    """
    try:
        frame = IJ.getInstance()
        if frame is None:
            return False
        worker_id = max(1, int(worker_id))
        worker_count = max(1, int(worker_count))
        screen = Toolkit.getDefaultToolkit().getScreenSize()
        screen_w = max(800, int(screen.width))
        screen_h = max(600, int(screen.height))
        reserve_right = min(520, max(360, int(screen_w * 0.25)))
        left = 8
        top = 35
        avail_w = max(420, screen_w - reserve_right - left - 12)
        avail_h = max(320, screen_h - top - 45)
        cols = max(1, int(math.ceil(math.sqrt(float(worker_count)))))
        rows = max(1, int(math.ceil(float(worker_count) / float(cols))))
        cell_w = max(220, int(avail_w / cols))
        cell_h = max(180, int(avail_h / rows))
        index = min(worker_count - 1, worker_id - 1)
        col = index % cols
        row = index // cols
        x = left + col * cell_w
        y = top + row * cell_h
        width = max(210, cell_w - 8)
        height = max(170, cell_h - 8)
        frame.setBounds(int(x), int(y), int(width), int(height))
        return True
    except Exception as e:
        try:
            IJ.log("Could not place Fiji worker window: " + str(e))
        except:
            pass
        return False


# ======================================================
# SCROLLABLE SETTINGS POPUP
# ======================================================

def page_panel():
    p = JPanel()
    p.setLayout(BoxLayout(p, BoxLayout.Y_AXIS))
    p.setAlignmentX(0.0)
    p.setBorder(BorderFactory.createEmptyBorder(6, 6, 6, 6))
    p.setBackground(Color(250, 250, 250))
    return p

def add_text_row(page, label, default_value, width):
    row = JPanel(BorderLayout(8, 0))
    row.setMaximumSize(Dimension(820, 30))
    row.setAlignmentX(0.0)
    row.setOpaque(False)

    lab = JLabel(label)
    lab.setPreferredSize(Dimension(220, 22))
    row.add(lab, BorderLayout.WEST)

    tf = JTextField(str(default_value), width)
    row.add(tf, BorderLayout.CENTER)

    page.add(row)
    page.add(Box.createVerticalStrut(2))
    return tf

def parse_color_name(name, fallback):
    if name is None:
        return fallback
    n = str(name).strip().lower()
    color_map = {
        "red": Color.red,
        "green": Color.green,
        "blue": Color.blue,
        "yellow": Color.yellow,
        "cyan": Color.cyan,
        "magenta": Color.magenta,
        "orange": Color.orange,
        "white": Color.white,
        "black": Color.black,
        "gray": Color.gray,
        "grey": Color.gray,
        "lightgray": Color.lightGray,
        "lightgrey": Color.lightGray,
        "darkgray": Color.darkGray,
        "darkgrey": Color.darkGray,
        "pink": Color.pink,
    }
    return color_map.get(n, fallback)

def get_setting_color(settings, key, fallback):
    try:
        return parse_color_name(settings.get(key, ""), fallback)
    except:
        return fallback


def apply_nimbus_look_and_feel():
    try:
        for info in UIManager.getInstalledLookAndFeels():
            if str(info.getName()) == "Nimbus":
                UIManager.setLookAndFeel(info.getClassName())
                break
    except Exception as e:
        IJ.log("Could not apply Nimbus look and feel: " + str(e))


class SimpleDocListener(DocumentListener):
    def __init__(self, fn):
        self.fn = fn
    def insertUpdate(self, event):
        self.fn()
    def removeUpdate(self, event):
        self.fn()
    def changedUpdate(self, event):
        self.fn()


def style_dialog_button(btn, primary=False):
    try:
        btn.setFocusPainted(False)
    except:
        pass
    try:
        btn.setPreferredSize(Dimension(150, 34))
    except:
        pass
    try:
        if primary:
            btn.setBackground(Color(70, 130, 180))
            btn.setForeground(Color.white)
        else:
            btn.setBackground(Color(235, 235, 235))
    except:
        pass


def style_nav_button(btn):
    try:
        btn.setFocusPainted(False)
        btn.setHorizontalAlignment(2)
        btn.setMaximumSize(Dimension(170, 30))
        btn.setPreferredSize(Dimension(170, 30))
        btn.setBackground(Color(238, 242, 248))
        btn.setBorder(BorderFactory.createCompoundBorder(
            BorderFactory.createLineBorder(Color(180, 195, 215)),
            BorderFactory.createEmptyBorder(8, 12, 8, 12)
        ))
    except:
        pass


def select_nav_button_style(button_map, active_name):
    try:
        for name in button_map.keys():
            btn = button_map[name]
            if name == active_name:
                btn.setBackground(Color(210, 230, 250))
                btn.setBorder(BorderFactory.createCompoundBorder(
                    BorderFactory.createLineBorder(Color(90, 140, 200), 2),
                    BorderFactory.createEmptyBorder(5, 9, 5, 9)
                ))
            else:
                style_nav_button(btn)
    except:
        pass


def set_component_value(comp, value):
    try:
        if isinstance(comp, JCheckBox):
            comp.setSelected(bool(value))
            return
    except:
        pass
    try:
        if isinstance(comp, JTextField):
            comp.setText(str(value))
            return
    except:
        pass
    try:
        if isinstance(comp, JComboBox):
            comp.setSelectedItem(value)
            return
    except:
        pass


def field_text_value(comp):
    try:
        if isinstance(comp, JCheckBox):
            return bool(comp.isSelected())
    except:
        pass
    try:
        if isinstance(comp, JTextField):
            return str(comp.getText()).strip()
    except:
        pass
    try:
        if isinstance(comp, JComboBox):
            return str(comp.getSelectedItem())
    except:
        pass
    return ""


def set_validation_state(comp, state, tooltip_text=None):
    try:
        if state == "bad":
            comp.setBackground(Color(255, 220, 220))
        elif state == "warn":
            comp.setBackground(Color(255, 245, 200))
        else:
            comp.setBackground(Color.white)
    except:
        pass
    if tooltip_text is not None:
        try:
            comp.setToolTipText(tooltip_text)
        except:
            pass


def validate_gui_fields(fields):
    issues = []
    def check_float(name, min_v=None, max_v=None, warn_only=False):
        comp = fields.get(name)
        if comp is None:
            return
        txt = field_text_value(comp)
        try:
            val = float(str(txt))
            state = "ok"
            msg = None
            if min_v is not None and val < min_v:
                state = "warn" if warn_only else "bad"
                msg = name + " is below the recommended minimum of " + str(min_v)
            if max_v is not None and val > max_v:
                state = "warn" if warn_only else "bad"
                msg = name + " is above the recommended maximum of " + str(max_v)
            set_validation_state(comp, state, msg)
            if msg is not None:
                issues.append(msg)
        except:
            set_validation_state(comp, "bad", "Enter a valid number for " + str(name))
            issues.append("Invalid number for " + str(name))

    threshold_gray_mode = threshold_mode_is_gray(field_text_value(fields.get("threshold_force_8bit_numbers")))
    threshold_input_limit = 255 if threshold_gray_mode else 100
    check_float("threshold_min", 0, threshold_input_limit)
    check_float("threshold_max", 0, threshold_input_limit)
    threshold_range_field_names = []
    threshold_step_field_names = []
    if field_text_value(fields.get("sweep_enabled")):
        sweep_all_thresholds = field_text_value(fields.get("sweep_all_listed"))
        if sweep_all_thresholds or field_text_value(fields.get("sweep_threshold_min")):
            threshold_range_field_names.extend(["sweep_threshold_min_start", "sweep_threshold_min_end"])
            threshold_step_field_names.append("sweep_threshold_min_step")
        if sweep_all_thresholds or field_text_value(fields.get("sweep_threshold_max")):
            threshold_range_field_names.extend(["sweep_threshold_max_start", "sweep_threshold_max_end"])
            threshold_step_field_names.append("sweep_threshold_max_step")
    if field_text_value(fields.get("auto_threshold_fit_enabled")):
        if field_text_value(fields.get("auto_threshold_fit_sweep_min")):
            threshold_range_field_names.extend(["auto_threshold_fit_min_start", "auto_threshold_fit_min_end"])
            threshold_step_field_names.append("auto_threshold_fit_min_step")
        if field_text_value(fields.get("auto_threshold_fit_sweep_max")):
            threshold_range_field_names.extend(["auto_threshold_fit_max_start", "auto_threshold_fit_max_end"])
            threshold_step_field_names.append("auto_threshold_fit_max_step")
    for threshold_field_name in threshold_range_field_names:
        check_float(threshold_field_name, 0, threshold_input_limit)
    for threshold_step_field_name in threshold_step_field_names:
        check_float(threshold_step_field_name, None, threshold_input_limit, True)
    if field_text_value(fields.get("sweep_until_enabled")):
        target_comp = fields.get("sweep_until_target_value")
        metric_name = field_text_value(fields.get("sweep_until_metric"))
        try:
            parse_sweep_until_target(field_text_value(target_comp), metric_name)
            set_validation_state(target_comp, "ok", "Number accepted; a trailing % is accepted for percentage metrics.")
        except Exception as e_target:
            set_validation_state(target_comp, "bad", str(e_target))
            issues.append(str(e_target))
        check_float("sweep_until_equal_tolerance", 0, None, True)
    check_float("auto_scale_known_length_mm", 0.000001, None, True)
    check_float("auto_scale_min_component_pixels", 1, None, True)
    check_float("auto_scale_preview_padding_px", 0, None, True)
    check_float("auto_scale_preview_zoom_factor", 1, 10, True)
    check_float("auto_scale_blue_search_padding_px", 20, None, True)
    check_float("set_scale_direct_mm_per_pixel", 0, None, True)
    check_float("set_scale_direct_pixels_per_mm", 0, None, True)
    check_float("median_radius", 0, 100, True)
    for pipeline_key in fields.keys():
        key_text = str(pipeline_key)
        if key_text.startswith("pipeline_") and key_text.endswith("_radius"):
            check_float(pipeline_key, 0, 100, True)
        elif key_text.startswith("pipeline_") and key_text.endswith("_iterations"):
            check_float(pipeline_key, 0, 100, True)
    check_float("crop_count", 0, 200, True)
    check_float("image_capture_count", 1, 1000, True)
    check_float("image_capture_scale_known_length_mm", 0.000001, None, True)
    check_float("particle_count_high_limit", 1, None, True)
    check_float("report_scale_bar_length_mm", 0.000001, None, True)
    if field_text_value(fields.get("large_pore_repair_enabled")):
        check_float("large_pore_repair_min_parent_area_px", 1, None)
        check_float("large_pore_repair_largest_pore_limit", 1, 500, True)
        check_float("large_pore_repair_min_child_area_px", 1, None)
        check_float("large_pore_repair_min_smaller_child_fraction", 0.0, 0.49)
        check_float("large_pore_repair_max_larger_child_fraction", 0.51, 1.0)
        check_float("large_pore_repair_min_closing_radius_px", 1, 100, True)
        check_float("large_pore_repair_max_closing_radius_px", 1, 100, True)
        check_float("large_pore_repair_radius_step_px", 1, 100, True)
        check_float("large_pore_repair_min_area_px", 1, None)
        check_float("large_pore_repair_max_area_px", 1, None)
        check_float("large_pore_repair_max_fraction_of_parent", 0.000001, 0.25, True)
        check_float("large_pore_repair_max_span_px", 1, None)
        check_float("large_pore_repair_crop_margin_px", 0, None, True)
        check_float("large_pore_repair_max_repairs_per_image", 1, 100, True)
        if field_text_value(fields.get("large_pore_repair_largest_rescue_enabled")):
            check_float("large_pore_repair_largest_rescue_parent_limit", 1, 100, True)
            check_float("large_pore_repair_largest_rescue_min_radius_px", 1, 100, True)
            check_float("large_pore_repair_largest_rescue_max_radius_px", 1, 100, True)
            check_float("large_pore_repair_largest_rescue_max_area_px", 1, None)
            check_float("large_pore_repair_largest_rescue_max_fraction_of_parent", 0.000001, 0.25, True)
            check_float("large_pore_repair_largest_rescue_max_span_px", 1, None)
            check_float("large_pore_repair_largest_rescue_min_smaller_child_fraction", 0.0, 0.49)
            check_float("large_pore_repair_largest_rescue_max_larger_child_fraction", 0.51, 1.0)
            check_float("large_pore_repair_largest_rescue_max_repairs_per_image", 1, 20, True)
        if field_text_value(fields.get("large_pore_repair_green_target_enabled")):
            check_float("large_pore_repair_green_target_min_parent_area_px", 1, None, True)
            check_float("large_pore_repair_green_target_max_parent_area_px", 1, None, True)
            check_float("large_pore_repair_green_target_parent_limit", 1, 1000, True)
            check_float("large_pore_repair_green_target_min_radius_px", 1, 100, True)
            check_float("large_pore_repair_green_target_max_radius_px", 1, 100, True)
            check_float("large_pore_repair_green_target_min_area_px", 1, None, True)
            check_float("large_pore_repair_green_target_max_area_px", 1, None, True)
            check_float("large_pore_repair_green_target_min_fraction_of_parent", 0.0, 0.49)
            check_float("large_pore_repair_green_target_max_fraction_of_parent", 0.000001, 0.50, True)
            check_float("large_pore_repair_green_target_min_span_px", 1, None, True)
            check_float("large_pore_repair_green_target_max_span_px", 1, None, True)
            check_float("large_pore_repair_green_target_min_mean_thickness_px", 0.1, None)
            check_float("large_pore_repair_green_target_max_mean_thickness_px", 0.1, None)
            check_float("large_pore_repair_green_target_min_child_area_px", 1, None, True)
            check_float("large_pore_repair_green_target_min_smaller_child_fraction", 0.0, 0.49)
            check_float("large_pore_repair_green_target_max_larger_child_fraction", 0.51, 1.0)
            check_float("large_pore_repair_green_target_max_repairs_per_image", 1, 100, True)
            check_float("large_pore_repair_green_spur_max_repairs_per_image", 1, 20, True)
        if field_text_value(fields.get("large_pore_repair_force_largest_enabled")):
            check_float("large_pore_repair_force_largest_max_radius_px", 1, 100, True)
            check_float("large_pore_repair_force_largest_max_area_px", 1, None)
            check_float("large_pore_repair_force_largest_max_fraction_of_parent", 0.000001, 0.50, True)
            check_float("large_pore_repair_force_largest_max_span_px", 1, None)
            check_float("large_pore_repair_force_largest_min_child_area_px", 1, None)
            check_float("large_pore_repair_force_largest_min_smaller_child_fraction", 0.0, 0.49)
            check_float("large_pore_repair_force_largest_max_larger_child_fraction", 0.51, 1.0)
    check_float("report_main_image_width_in", 0.1, 20, True)
    check_float("small_epd_cutoff", 0, None, True)
    check_float("epd_between_low", 0, None, True)
    check_float("epd_between_high", 0, None, True)
    check_float("report_pore_map_opacity_percent", 0, 100)
    check_float("jmp_hist_graph_width", 100, 4000, True)
    check_float("jmp_hist_graph_height", 100, 4000, True)
    return issues


def gui_summary_text(fields, mode_name):
    try:
        lines = []
        batch_txt = "Batch" if field_text_value(fields.get("batch_enabled")) else "Single"
        if fields.get("image_capture_enabled") is not None and field_text_value(fields.get("image_capture_enabled")):
            lines.append("Mode: YOURE A BETA image capture | " + str(field_text_value(fields.get("image_capture_mode"))))
            lines.append("Capture count: " + str(field_text_value(fields.get("image_capture_count"))) + "; scale distance mm=" + str(field_text_value(fields.get("image_capture_scale_known_length_mm"))))
            lines.append("Live view helper: auto-open=" + ("ON" if field_text_value(fields.get("image_capture_try_open_live_view")) else "OFF") + "; command=" + str(field_text_value(fields.get("image_capture_live_view_command"))))
        else:
            lines.append("Mode: " + batch_txt + " | View: " + str(mode_name))
        lines.append("Crops: count=" + str(field_text_value(fields.get("crop_count"))) + "; mode=" + str(field_text_value(fields.get("crop_mode"))))
        try:
            lines.append("Ordered pipeline: " + pipeline_gui_summary_from_fields(fields))
        except:
            lines.append("Ordered pipeline: open ORDER to configure")
        live_threshold_min = field_text_value(fields.get("threshold_min"))
        live_threshold_max = field_text_value(fields.get("threshold_max"))
        live_force_8bit = field_text_value(fields.get("threshold_force_8bit_numbers"))
        lines.append("Threshold input units: " + threshold_input_mode_label(live_force_8bit))
        lines.append("Threshold: " + threshold_range_with_percent(live_threshold_min, live_threshold_max, live_force_8bit))
        if field_text_value(fields.get("large_pore_repair_enabled")):
            lines.append(
                "Large pore repair: ON | " + str(field_text_value(fields.get("large_pore_repair_mode"))) +
                " | parent >= " + str(field_text_value(fields.get("large_pore_repair_min_parent_area_px"))) +
                " px | inspect " + str(field_text_value(fields.get("large_pore_repair_largest_pore_limit"))) +
                " | max repairs " + str(field_text_value(fields.get("large_pore_repair_max_repairs_per_image"))) +
                " | aggressive rescue " + ("ON" if field_text_value(fields.get("large_pore_repair_largest_rescue_enabled")) else "OFF") +
                " | force largest " + ("ON" if field_text_value(fields.get("large_pore_repair_force_largest_enabled")) else "OFF") +
                " | green-target recursive " + ("ON" if field_text_value(fields.get("large_pore_repair_green_target_enabled")) else "OFF")
            )
        else:
            lines.append("Large pore repair: OFF")
        try:
            live_preset = str(field_text_value(fields.get("epd_between_preset")))
            live_low, live_high, live_source = resolve_epd_between_preset(
                live_preset,
                field_text_value(fields.get("epd_between_low")),
                field_text_value(fields.get("epd_between_high"))
            )
            if live_preset == "Custom":
                live_delete = float(field_text_value(fields.get("small_epd_cutoff")))
            else:
                live_delete = float(live_low)
            lines.append(
                "JMP delete preset: " + live_source + "; delete EPD <= " +
                threshold_compact_number(live_delete * 1000.0) + " um; between count " +
                threshold_compact_number(live_low * 1000.0) + "-" +
                threshold_compact_number(live_high * 1000.0) + " um; pore map low highlight < " +
                threshold_compact_number(live_high * 1000.0) + " um; high highlight always > 25 um"
            )
        except:
            pass
        if field_text_value(fields.get("sweep_enabled")):
            sweep_all_thresholds = field_text_value(fields.get("sweep_all_listed"))
            if sweep_all_thresholds or field_text_value(fields.get("sweep_threshold_min")):
                lines.append(
                    "Threshold min sweep: " + threshold_sweep_range_with_percent(
                        field_text_value(fields.get("sweep_threshold_min_start")),
                        field_text_value(fields.get("sweep_threshold_min_end")),
                        field_text_value(fields.get("sweep_threshold_min_step")),
                        live_force_8bit
                    )
                )
            if sweep_all_thresholds or field_text_value(fields.get("sweep_threshold_max")):
                lines.append(
                    "Threshold max sweep: " + threshold_sweep_range_with_percent(
                        field_text_value(fields.get("sweep_threshold_max_start")),
                        field_text_value(fields.get("sweep_threshold_max_end")),
                        field_text_value(fields.get("sweep_threshold_max_step")),
                        live_force_8bit
                    )
                )
            if sweep_all_thresholds or field_text_value(fields.get("sweep_contrast_enabled")):
                live_contrast_modes = []
                if field_text_value(fields.get("sweep_contrast_mode_off")):
                    live_contrast_modes.append("Off")
                if field_text_value(fields.get("sweep_contrast_mode_saturated")):
                    live_contrast_modes.append("Saturated cutoff only")
                if field_text_value(fields.get("sweep_contrast_mode_normalize")):
                    live_contrast_modes.append("Normalize")
                if field_text_value(fields.get("sweep_contrast_mode_equalize")):
                    live_contrast_modes.append("Equalize")
                lines.append("Enhance Contrast sweep: " + (" + ".join(live_contrast_modes) if len(live_contrast_modes) > 0 else "no modes selected"))
            if field_text_value(fields.get("sweep_until_enabled")):
                lines.append(
                    "Sweep until: " + str(field_text_value(fields.get("sweep_until_metric"))) + " " +
                    str(field_text_value(fields.get("sweep_until_operator"))).lower() + " " +
                    str(field_text_value(fields.get("sweep_until_target_value"))) +
                    "; scope=" + str(field_text_value(fields.get("sweep_until_stop_scope")))
                )
        lines.append("Auto scale unscaled images: " + ("ON" if field_text_value(fields.get("auto_scale_unscaled_enabled")) else "OFF") + "; actual distance default mm=" + str(field_text_value(fields.get("auto_scale_known_length_mm"))))
        lines.append("Set scale only: " + ("ON" if field_text_value(fields.get("set_scale_only_mode")) else "OFF"))
        lines.append(
            "Swift .magn scale: " + ("ON" if field_text_value(fields.get("swift_magn_scale_enabled")) else "OFF") +
            "; file=" + str(field_text_value(fields.get("swift_magn_filename"))) +
            "; profile=" + str(field_text_value(fields.get("swift_magn_profile_name")))
        )
        lines.append("Manual pore trace: " + ("ON" if field_text_value(fields.get("manual_selected_pore_enabled")) else "OFF") + "; count=" + str(field_text_value(fields.get("manual_selected_pore_count"))))
        lines.append("5% auto-fit/redo summary: " + ("ON" if field_text_value(fields.get("auto_threshold_fit_enabled")) else "OFF"))
        if field_text_value(fields.get("beast_mode_enabled")):
            _beast_graphs_on = bool(field_text_value(fields.get("beast_create_graph_word_report")))
            lines.append("BEAST MODE: ON | Fiji workers=" + str(field_text_value(fields.get("beast_fiji_parallel_instances"))) + " | visible=" + str(field_text_value(fields.get("beast_show_fiji_worker_windows"))) + " | marker timeout=" + str(field_text_value(fields.get("beast_fiji_worker_startup_timeout_sec"))) + "s" + " | JMP graphs=" + ("ON" if _beast_graphs_on else "OFF; Fiji EPD to XLSX") + " | Word reports=" + str(field_text_value(fields.get("word_report_mode"))) + (" | JMP workers=" + str(field_text_value(fields.get("beast_jmp_parallel_instances"))) + " | streaming after " + str(field_text_value(fields.get("beast_jmp_start_after_fiji_runs"))) + " Fiji runs" if _beast_graphs_on else ""))
        else:
            lines.append("BEAST MODE: OFF")
        lines.append("Word report mode: " + str(field_text_value(fields.get("word_report_mode"))))
        lines.append("Scale set using: " + str(field_text_value(fields.get("report_scale_method"))))
        lines.append("Imaging software: " + str(field_text_value(fields.get("report_imaging_software"))))
        lines.append("Report file name: " + str(field_text_value(fields.get("report_filename_mode"))))
        lines.append("Excel summary: " + ("ON" if field_text_value(fields.get("export_main_summary_xls")) else "OFF") + "; destination=" + str(field_text_value(fields.get("summary_xls_destination"))))
        lines.append("Batch sweep reports by OG image + full combined: " + ("ON" if field_text_value(fields.get("batch_sweep_reports_by_og_image")) else "OFF"))
        lines.append("Batch sweep summaries to All Reports: " + ("ON" if field_text_value(fields.get("batch_sweep_export_all_summaries_to_all_reports")) else "OFF"))
        lines.append("Batch live image report folders: " + ("ON - strict image-by-image barrier" if field_text_value(fields.get("batch_live_image_report_folders_enabled")) else "OFF"))
        lines.append("Pore map background: " + str(field_text_value(fields.get("report_pore_map_background"))) + "; opacity=" + str(field_text_value(fields.get("report_pore_map_opacity_percent"))) + "%")
        lines.append("Scale bar: " + ("AUTO 1/5 width" if field_text_value(fields.get("report_scale_bar_auto_fit_enabled")) else "FIXED " + str(field_text_value(fields.get("report_scale_bar_length_mm"))) + " mm"))
        lines.append("Segmented overlay export to Images folder: " + ("ON" if field_text_value(fields.get("report_save_segmented_overlay_next_to_word")) else "OFF"))
        lines.append("Segmented overlay fiber color: " + str(field_text_value(fields.get("report_segmented_overlay_fiber_color"))))
        lines.append("Segmented overlay fiber opacity: " + str(field_text_value(fields.get("report_segmented_overlay_fiber_opacity_percent"))) + "%")
        lines.append("Segmented overlay annotation opacity: " + str(field_text_value(fields.get("report_segmented_overlay_annotation_opacity_percent"))) + "%")
        lines.append("Segmented pores overlay opacity: " + str(field_text_value(fields.get("report_segmented_pores_overlay_opacity_percent"))) + "%")
        lines.append("Save Fiji log file: " + ("ON" if field_text_value(fields.get("save_fiji_log_enabled")) else "OFF"))
        lines.append("Warnings: high particles=" + str(field_text_value(fields.get("particle_count_high_limit"))) + "; popup=" + ("ON" if field_text_value(fields.get("popup_warning_summary_enabled")) else "OFF"))
        issues = validate_gui_fields(fields)
        if len(issues) > 0:
            lines.append("")
            lines.append("Validation:")
            for msg in issues[:5]:
                lines.append("- " + str(msg))
        return "\n".join(lines)
    except Exception as e:
        return "Could not build live summary: " + str(e)


def apply_gui_preset(fields, preset_name):
    presets = {
        "Default GDL": {},
        "Fast Batch": {
            "batch_enabled": True,
            "manual_largest_pore_enabled": False,
            "manual_selected_pore_enabled": False,
            "manual_strand_measurement_enabled": False,
            "create_word_report": True,
            "highlight_largest_pore_in_segmented": False,
            "report_all_pore_map_enabled": False,
            "report_launch_all_jmp": True,
            "auto_threshold_fit_enabled": False
        },
        "Manual QA": {
            "batch_enabled": False,
            "manual_largest_pore_enabled": False,
            "manual_selected_pore_enabled": True,
            "manual_strand_measurement_enabled": True,
            "auto_threshold_fit_enabled": True,
            "create_word_report": True,
            "popup_warning_summary_enabled": True
        },
        "Crop Mode": {
            "batch_enabled": True,
            "crop_count": 4,
            "crop_mode": "Manual select",
            "crop_prompt_each_image": True,
            "manual_selected_pore_enabled": True,
            "create_word_report": True
        },
        "High Detail Report": {
            "create_word_report": True,
            "report_all_pore_map_enabled": True,
            "report_scale_bar_enabled": True,
            "manual_largest_pore_enabled": False,
            "manual_selected_pore_enabled": True,
            "highlight_largest_pore_in_segmented": True,
            "report_sweep_comparison_enabled": True
        },
        "No Manual Measurements": {
            "manual_measurements_enabled": False,
            "manual_largest_pore_enabled": False,
            "manual_selected_pore_enabled": False,
            "manual_strand_measurement_enabled": False,
            "auto_threshold_fit_enabled": False
        }
    }
    preset = presets.get(str(preset_name), {})
    for key in preset.keys():
        if key in fields:
            set_component_value(fields[key], preset[key])


def apply_tooltips(fields):
    tips = {
        "batch_enabled": "Process every supported image in a selected folder instead of a single file.",
        "image_capture_enabled": "YOURE A BETA fork: capture frames from the currently active ImageJ image/camera preview window.",
        "image_capture_mode": "Choose whether to stop after saving scaled TIFFs or run the normal analysis from those captured TIFFs.",
        "image_capture_count": "How many sample images to capture after the scale frame is calibrated.",
        "image_capture_scale_known_length_mm": "Known real-world distance for the scale-bar trace used during image capture calibration.",
        "image_capture_batch_name": "Optional startup name. You will still be asked to confirm/name the batch after choosing the output folder.",
        "image_capture_try_open_live_view": "When capture mode starts, try to launch a known ImageJ/Fiji camera/live-view command if one is installed.",
        "image_capture_live_view_command": "Choose a specific Fiji/ImageJ live-view command, or leave Auto to search common camera plugins.",
        "image_capture_show_live_view_directions": "Show the camera/live-view setup directions before the scale-frame capture step.",
        "crop_count": "Set to 0 for no crops. If greater than 0, the script creates crop runs before analysis.",
        "crop_mode": "Manual select lets you draw crop rectangles. Auto cropped grid divides the image automatically.",
        "threshold_max": "Higher threshold max usually increases detected pore area. Its units follow the gray-value/percent checkbox.",
        "threshold_force_8bit_numbers": "Checked: enter 8-bit gray values from 0-255. Unchecked: enter cumulative histogram percentiles from 0-100; each image gets its own gray cutoff from its preprocessed histogram.",
        "large_pore_repair_enabled": "OFF by default. After thresholding, inspect only large white pore components and add conservative black repairs before Analyze Particles.",
        "large_pore_repair_mode": "Review proposals shows each candidate in red on the first threshold pass and replays only approved locations after threshold auto-fit reruns. Automatic conservative accepts every candidate passing all safeguards. BEAST/headless runs use automatic mode.",
        "large_pore_repair_min_parent_area_px": "Only white pore components at or above this pixel area are inspected.",
        "large_pore_repair_min_child_area_px": "After a repair, each of the exactly two resulting pores must exceed this pixel area.",
        "large_pore_repair_max_fraction_of_parent": "Maximum black repair area divided by the original parent pore area.",
        "large_pore_repair_largest_rescue_enabled": "Runs a second, wider search only on the top-ranked large pores. It keeps stricter child-balance limits so the wider bridge does not loosen every pore.",
        "large_pore_repair_largest_rescue_parent_limit": "Only this many largest parent pores are eligible for the wider rescue search.",
        "large_pore_repair_largest_rescue_max_radius_px": "Maximum morphology radius for the top-pore rescue pass. The normal search remains unchanged.",
        "large_pore_repair_largest_rescue_max_fraction_of_parent": "Maximum rescue bridge area divided by the original parent pore area.",
        "large_pore_repair_force_largest_enabled": "v193 force-tests the single largest parent before other repairs and ranks candidates by how evenly they divide the pore.",
        "large_pore_repair_force_largest_max_radius_px": "Maximum closing radius used only for the single largest pore.",
        "large_pore_repair_force_largest_max_fraction_of_parent": "Maximum fraction of the largest parent that the forced repair may convert to black.",
        "large_pore_repair_green_target_enabled": "v193 recursive medium-pore neck detection tuned to the user's green corrections. It can split a chained merged pore more than once.",
        "large_pore_repair_green_target_min_fraction_of_parent": "Rejects tiny morphology specks that are too small relative to the parent pore.",
        "large_pore_repair_green_target_min_mean_thickness_px": "Repair area divided by bounding-box span. This filters isolated dots while retaining elongated green-style neck cuts.",
        "large_pore_repair_green_spur_review_only": "Keeps small-lobe/spur cuts out of automatic and headless runs. They are shown only for manual review.",
        "large_pore_repair_save_red_overlay_png": "Save a separate PNG showing accepted repair locations in red. The standard segmented mask remains black and white.",
        "sweep_threshold_min_start": "Threshold sweeps use the same gray-value or cumulative-histogram-percentile mode selected on the Threshold + Analysis page.",
        "sweep_threshold_max_start": "Threshold sweeps use the same gray-value or cumulative-histogram-percentile mode selected on the Threshold + Analysis page.",
        "sweep_until_enabled": "Stop remaining sweep combinations when the selected summary metric reaches the target condition.",
        "sweep_until_metric": "Choose any final JMP summary metric or raw ImageJ summary metric for the early-stop test.",
        "sweep_until_target_value": "Enter a number. A trailing % is accepted for percentage metrics such as Area %.",
        "sweep_until_equal_tolerance": "Used only for Is equal to. The condition passes when absolute difference is within this tolerance.",
        "sweep_until_stop_scope": "Stop only the current image/crop sweep, or stop every remaining run in the batch.",
        "auto_scale_unscaled_enabled": "For unscaled pixel images, find the red reference line and set the calibration unit to mm before analysis.",
        "auto_scale_known_length_mm": "Known physical length of the red reference line in millimeters.",
        "auto_scale_min_component_pixels": "Minimum size of the detected red connected component before it is accepted as a scale line.",
        "auto_scale_show_preview": "Open a cropped preview around the detected red scale bar and trace the measured line before applying scale.",
        "auto_scale_save_tif_enabled": "Save a calibrated same-name TIFF next to PNG/JPG inputs after scale is applied.",
        "set_scale_only_mode": "Only set calibration and save TIFFs, then stop without analysis/report/JMP.",
        "set_scale_direct_enabled": "Use the manual mm/pixel or pixels/mm fields instead of detecting the red scale line.",
        "auto_scale_preview_padding_px": "Extra pixels around the detected red line in the preview crop.",
        "auto_scale_preview_zoom_factor": "Enlarges the cropped scale-bar preview image so the red line and dimension text are easier to inspect.",
        "auto_scale_save_tif_subfolder_enabled": "Save calibrated TIFFs inside a folder named Scaled image. TIFF files are named original_file_scaled.tif.",
        "auto_scale_replace_png_with_tif_enabled": "After saving the calibrated TIFF, move the original PNG/JPG to a backup name so the calibrated TIFF replaces it for future workflow. Best used when subfolder save is off.",
        "auto_scale_blue_ocr_enabled": "Best-effort built-in reader for the orange/blue distance label. Default is OFF; when off, you just see the cropped scale region and type the actual distance manually.",
        "auto_scale_blue_search_padding_px": "How far from the detected red scale line to search for orange/blue label pixels when the reader is enabled.",
        "manual_selected_pore_enabled": "Single merged manual pore workflow: the largest-pore guide is shown on the same image, but you may trace any pore.",
        "manual_success_popup_show_picture": "Show the portrait on the under-trigger success popup. Uncheck for a smaller text-only popup.",
        "manual_strand_measurement_enabled": "For each strand, select a line ROI and click OK; the next popup shows the measured mm value with Accept and Redo buttons.",
        "auto_threshold_fit_enabled": "After manual selected pore review, opens auto-fit/redo summary only when the selected pore is outside the percent trigger.",
        "report_pore_map_background": "Choose the background under pore-map markers. Original image is the default.",
        "report_pore_map_opacity_percent": "Marker opacity from 0 to 100 percent. Default is 70 percent.",
        "epd_between_preset": "Select the delete-EPD cutoff first: 3, 5, or 10 microns. It automatically sets the matching between-count band and only the low-pore map limit. Pores above 25 microns remain highlighted. Custom enables all manual low limits.",
        "small_epd_cutoff": "Delete EPD values at or below this cutoff. Preset selections set it automatically; Custom makes it editable.",
        "epd_between_low": "Between-count lower cutoff in mm. Presets set it equal to the selected delete cutoff; Custom makes it editable.",
        "epd_between_high": "Between-count upper cutoff in mm. Presets set it 2 microns above the selected delete cutoff; this changes only the low-pore map highlight. Pores above 25 microns remain fixed. Custom makes it editable.",
        "report_scale_bar_auto_fit_enabled": "When checked, use one-fifth of calibrated image width rounded to the nearest 0.05 mm (50 microns).",
        "report_scale_bar_length_mm": "Normal fixed scale-bar length. Default 0.1 mm = 100 microns; ignored when auto-fit is checked.",
        "particle_count_high_limit": "Warn if the detected particle count is above this value.",
        "create_word_report": "Create Word report(s) after the analysis and JMP outputs are ready.",
        "report_save_segmented_overlay_next_to_word": "When checked, save overlay PNGs into the run Images folder only. One overlay recolors black fibers while keeping white pores transparent, and a second pores overlay shows the regular black-and-white segmented image on top of the original image at a configurable opacity. These overlays are not embedded into the Word report.",
        "report_segmented_overlay_fiber_color": "Color used to tint black fiber regions from the segmented image in the exported overlay PNG.",
        "report_segmented_overlay_fiber_opacity_percent": "Opacity of the fiber-color overlay on top of the original image, from 0 to 100 percent.",
        "report_segmented_overlay_annotation_opacity_percent": "Opacity of non-black, non-white segmented annotations preserved over the original image, from 0 to 100 percent.",
        "report_segmented_pores_overlay_opacity_percent": "Opacity used for the black-and-white segmented overlay saved in the Images folder, from 0 to 100 percent.",
        "save_fiji_log_enabled": "Save the complete Fiji/ImageJ Log window text and collected errors as Fiji_Log.txt in the output root.",
        "word_report_mode": "Choose no DOCX, one combined DOCX, one DOCX per original image, one DOCX per processed run, or either individual style plus combined.",
        "beast_word_report_mode": "Legacy BEAST report grouping mirror. v209 uses the Report-card word_report_mode selection for both Normal and BEAST.",
        "swift_magn_scale_enabled": "Read a Swift Imaging 3.0 .magn table and apply its pixels-per-meter calibration before cropping, sweeping, or particle analysis.",
        "swift_magn_filename": "Swift magnification-table filename. The script searches beside each image, then parent folders, then the bundled Swift Magnification Tables folder.",
        "swift_magn_profile_name": "Objective/magnification profile read from the Swift table, such as 4X or 10X. The dropdown is populated from the bundled Imaging.magn table. AUTO uses a single profile or matches the profile token in the image/folder path.",
        "swift_magn_search_parent_levels": "Number of parent folders above the image folder to search for the .magn table.",
        "swift_magn_use_bundle_fallback": "Also search the script bundle's Swift Magnification Tables folder.",
        "swift_magn_override_existing_scale": "Replace a calibration already embedded in the image. Leave off unless the existing scale is known to be wrong.",
        "report_scale_method": "Descriptive label for how image scale was established. Edit report_scale_method_options in GDL_User_Defaults.py to add choices.",
        "report_imaging_software": "Image-acquisition software recorded in reports and manifests. Edit report_imaging_software_options in GDL_User_Defaults.py to add choices.",
        "report_filename_mode": "Choose an automatic image/processing name or enter the report name once after processing.",
        "export_main_summary_xls": "Create a simple Excel-compatible .xls file containing only the main summary sheet, named from the Word report plus _summaries.",
        "summary_xls_destination": "Choose which shared All Reports folder receives the Excel summary. Auto mode checks both configured workstation paths.",
        "summary_xls_custom_folder": "Used only when Excel summary destination is Custom folder.",
        "jmp_exe": "Full path to the JMP executable used when auto-launch is enabled.",
        "beast_mode_enabled": "Generate all ImageJ runs first, then process JMP scripts using a bounded parallel worker pool. Word/manual workflows and JMP graph creation are disabled; one ordered three-sheet XLSX is produced.",
        "beast_jmp_parallel_instances": "Maximum number of separate JMP processes running at once. Default 10; lower this if memory or licensing is constrained.",
        "beast_parallel_fiji_enabled": "Use separate Fiji workers for run-level parallelism. Missing jobs automatically return to the current Fiji instance.",
        "beast_show_fiji_worker_windows": "Show one separate Fiji window per worker. Uncheck for silent headless workers.",
        "beast_jmp_streaming_enabled": "BEAST MODE only: feed completed Fiji runs directly to the JMP worker pool before the remaining Fiji jobs finish.",
        "beast_jmp_start_after_fiji_runs": "Number of completed Fiji runs required before JMP begins. The default is 15; JMP also starts when Fiji finishes even if fewer runs exist.",
        "beast_create_graph_word_report": "BEAST MODE only: this checkbox is the JMP master switch. Checked = run JMP, create histograms/graphs, and build one combined Word report. Unchecked = do not launch JMP; Fiji writes EPD directly into the XLSX pore-data sheet.",
        "beast_fiji_parallel_instances": "Maximum simultaneous Fiji workers. The controller never launches more than this value.",
        "beast_fiji_worker_timeout_sec": "Maximum time for one persistent Fiji worker batch before it is terminated and its assigned runs are listed as exceptions.",
        "beast_fiji_fallback_to_controller": "When a worker fails to launch or finish, rerun its missing jobs in the currently open Fiji instance.",
        "beast_fiji_worker_startup_timeout_sec": "Seconds allowed for each worker to execute its wrapper and create its startup marker. Default: 60.",
        "beast_preflight_enabled": "Before the progress window opens, launch a disposable JMP probe. The current Fiji instance is already running and is not relaunched.",
        "minimum_filter_radius": "ImageJ grayscale Minimum filter radius in pixels. Place this operation before Threshold. Set to 0 to disable.",
        "maximum_filter_radius": "ImageJ grayscale Maximum filter radius in pixels. Place this operation before Threshold. Set to 0 to disable.",
        "binary_minimum_radius": "Legacy alias for the grayscale Minimum filter radius.",
        "binary_maximum_radius": "Legacy alias for the grayscale Maximum filter radius.",
        "beast_preflight_timeout_sec": "Total Fiji preflight marker budget in seconds. Default and maximum used by v193: 60.",
        "beast_jmp_timeout_sec": "Maximum seconds allowed for one JMP run before its process is terminated and the run is logged as failed.",
        "beast_force_close_jmp_after_run": "After JMP writes its completion marker, terminate that exact launched process if it does not exit during the grace period.",
        "beast_organize_windows_enabled": "Keep the progress dialog visible and best-effort tile controller ImageJ and external Fiji worker windows while BEAST MODE runs.",
        "beast_organize_jmp_windows_enabled": "Move JMP windows with PowerShell. Leave this off for stability because moving multiple JMP Home windows during startup can trigger a JMP UI crash.",
        "beast_jmp_safe_launch_enabled": "Keep the configured parallel JMP count, launch without window tiling, and replace only workers that crash or exit early.",
        "beast_jmp_minimized_launch_enabled": "Start each JMP worker minimized through a hidden PowerShell wrapper while preserving an independently monitored worker process.",
        "beast_jmp_isolated_temp_enabled": "Give every JMP run its own TEMP/TMP folder so crash reports and temporary files are isolated from other JMP workers.",
        "beast_jmp_retry_count": "Number of times a JMP run is requeued after an early exit or timeout without the required outputs."
    }
    for key in tips.keys():
        try:
            fields[key].setToolTipText(tips[key])
        except:
            pass


def create_progress_popup(total_runs):
    try:
        dlg = JFrame()
        dlg.setTitle("GDL Processing Progress - restore from taskbar")
        dlg.setSize(560, 245)
        try:
            dlg.setDefaultCloseOperation(0)  # DO_NOTHING_ON_CLOSE
        except:
            pass
        pane = JPanel()
        pane.setLayout(BoxLayout(pane, BoxLayout.Y_AXIS))
        pane.setBorder(BorderFactory.createEmptyBorder(12, 12, 12, 12))
        pane.setAlignmentX(0.0)
        lbl1 = JLabel("Preparing runs...")
        lbl2 = JLabel(" ")
        batch_image_status = JLabel("Batch image status: waiting")
        try:
            batch_image_status.setFont(Font("SansSerif", Font.BOLD, 13))
        except:
            pass
        cancel_note = JLabel("Cancel stops new runs and terminates JMP processes launched by this script.")
        bar = JProgressBar(0, max(1, int(total_runs)))
        bar.setStringPainted(True)
        cancel_button = JButton("CANCEL EVERYTHING")
        style_dialog_button(cancel_button, False)

        def cancel_action(event):
            request_global_cancel("User pressed CANCEL EVERYTHING in the progress window.")
            try:
                cancel_button.setEnabled(False)
                cancel_button.setText("Cancel requested...")
                cancel_note.setText("Stopping at the next safe point. Active JMP processes are being terminated.")
            except:
                pass

        cancel_button.addActionListener(cancel_action)

        class ProgressCloseListener(WindowAdapter):
            def windowClosing(self, event):
                cancel_action(event)

        dlg.addWindowListener(ProgressCloseListener())
        pane.add(lbl1)
        pane.add(Box.createVerticalStrut(8))
        pane.add(lbl2)
        pane.add(Box.createVerticalStrut(6))
        pane.add(batch_image_status)
        pane.add(Box.createVerticalStrut(12))
        pane.add(bar)
        pane.add(Box.createVerticalStrut(10))
        pane.add(cancel_note)
        pane.add(Box.createVerticalStrut(8))
        pane.add(cancel_button)
        dlg.add(pane)
        place_progress_dialog(dlg)
        dlg.setVisible(True)
        try:
            dlg.setAlwaysOnTop(False)
            dlg.setAutoRequestFocus(False)
        except:
            pass
        return {"dialog": dlg, "line1": lbl1, "line2": lbl2, "batch_image_status": batch_image_status, "bar": bar,
                "cancel_button": cancel_button, "cancel_note": cancel_note}
    except Exception as e:
        IJ.log("Could not create fancy progress dialog: " + str(e))
        return None

def update_progress_popup(progress_ui, current_run, total_runs, image_name, extra_text):
    if progress_ui is None:
        return
    try:
        progress_ui["line1"].setText("Run " + str(current_run) + " of " + str(total_runs))
        progress_ui["line2"].setText(str(image_name) + " - " + str(extra_text))
        progress_ui["bar"].setMaximum(max(1, int(total_runs)))
        progress_ui["bar"].setValue(int(current_run))
        progress_ui["bar"].setString(str(current_run) + " / " + str(total_runs))
        if global_cancel_requested():
            progress_ui["line1"].setText("CANCEL REQUESTED - stopping safely")
            progress_ui["line2"].setText(str(RUN_CONTROL.get("cancel_reason", "")))
        organize_open_imagej_windows(progress_ui)
        progress_ui["dialog"].repaint()
    except:
        pass


def close_progress_popup(progress_ui):
    if progress_ui is None:
        return
    try:
        progress_ui["dialog"].dispose()
    except:
        pass


def format_elapsed_seconds(seconds_value):
    try:
        total = int(max(0, float(seconds_value)))
    except:
        total = 0
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    if hours > 0:
        return str(hours) + "h " + str(minutes) + "m " + str(seconds) + "s"
    if minutes > 0:
        return str(minutes) + "m " + str(seconds) + "s"
    return str(seconds) + "s"
