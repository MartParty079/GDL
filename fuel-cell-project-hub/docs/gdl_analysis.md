# GDL Analysis in Project Hub

## Overview

Project Hub now manages YOURE A BETA GDL Analysis v209. The existing Fiji/Jython interface still controls image processing, Quick Runs, Swift scaling, BEAST, JMP and report generation. The Hub supplies paths, launch/session configuration, watchdog status, logs, engine ZIP updates and rollback.

The supplied original package is preserved under `analysis/gdl/baseline`; the integrated copy is under `analysis/gdl/engine`. Existing filenames and module execution order are retained. A machine-readable manifest describes the engine. The original shared ZIP is read only and has not been changed.

## Dependencies

Fiji needs a supported Windows executable and nearby `jars` and `plugins` folders. Modern `fiji-windows-x64.exe` and legacy ImageJ launchers are supported. JMP uses `jmp.exe`, with bounded detection across JMP/JMP Pro/Student editions. Fiji and JMP share the Hub's Software path registry; no second executable path cache is maintained. Both applications were found on this machine by a read-only check.

## Launch from Project Hub

1. Restart the Hub with `Start Hub.cmd`.
2. Open **Settings → Analysis Tools**. Review Fiji, JMP, engine, modules, Quick Runs, Swift tables, input, output, reports and temporary work folders.
3. Choose input and output modes, then **Apply analysis settings**. Shared folder changes require team confirmation and create a settings revision. Executable and external paths remain local.
4. Open **Project → Analysis**, or use **Open analysis** on the Software page.
5. Click **Launch GDL Analysis**, choose folders when requested, and review the clean-Fiji warning. The Hub starts the existing watchdog without the BAT file.
6. Use the normal Fiji settings/Quick Run interface. The Hub reports Starting, Running, Restarting, Completed, Canceled or Failed from session-specific watchdog metadata.
7. Open the output folder or session log from the Analysis page. A generated report action appears only when a DOCX is actually found under the completed run's `Word_Report` folder.

The first live Fiji analysis has deliberately not been run, at the user's request. Real image-processing results, generated Word/JMP output and UI behavior inside Fiji still need a known-image acceptance run. Offline checks do not establish scientific equivalence.

## Updating the script in the app

The supplied v209 ZIP is registered in this user's local profile as the update source. **Check for engine updates** scans its parent folder for GDL ZIPs and reads their declared engine versions without executing them. When a newer version is found, **Install available update** appears. If the same ZIP changes, the Hub prompts you to import/review it. **Import / update ZIP** also lets you choose a different package; its folder becomes the new saved update source.

Import a complete original GDL package from the trusted project source. ZIP import validates paths, version/module metadata, eleven modules, all five bundled Quick Run slots and the Swift table. Compatibility edits are checked against known integration boundaries. A changed/unsupported boundary rejects the package before replacing the active engine. New scientific versions may require an adapter review when their configuration or launcher architecture changes.

Successful imports activate a separate version directory and retain the previous engine. **Roll back engine** switches back without deleting data or changing configured folders. Active watchdog sessions block updates and rollback. Updates are never installed automatically. Source ZIPs, data, installed Fiji/JMP applications and the previous package are not modified.

## Path configuration and portability

Every external path supports editing/paste, Browse, Open folder and Reset. Executables also support Auto detect; other rows offer Use default. Blank edited fields reset to defaults after Apply. Invalid edited paths show inline errors and are not saved. Auto detection never replaces an explicit saved path without the user's action.

Resolution is local override → configured project-relative path → detected dependency → bundled/default location → Needs setup. Folders saved inside a connected project library become relative references when the sharing checkbox is selected. Absolute executable, engine, runtime and external folder paths remain in `%LOCALAPPDATA%/FuelCellProjectHub/`. A disconnected shared folder fails clearly; the adapter does not silently select a different output.

Input modes: Choose at launch, Project Files & Data, Remember last folder, Configured folder. Output modes: Project default, Remember last folder, Custom configured folder, Ask when analysis starts. The default project targets are `04_Raw_Data`, `05_Processed_Data` and `07_Reports`. Output/report/runtime folders are created and checked for writability only when launching. In single-image, capture and report-recovery modes, the existing Fiji selections/processing controls remain available.

## Quick Runs and Swift tables

All five supplied JSON slots retain their original names and processing settings. Legacy report destination names map to generic choices in memory; template JSON is not rewritten. The Hub does not reproduce processing settings or implement headless Quick Run execution.

Before the first launch or engine update, default Quick Runs are copied to the user's local `gdl/quick_runs` folder. This preserves custom saved slots across updates and rollback. A configured local or shared Quick Run folder takes precedence and is kept. New package templates remain available inside that package; they do not overwrite personal slots.

Swift tables keep the original image-folder → parent-folder → configured/bundled fallback search, objective/profile selection and units. Select another table folder in Analysis Tools when needed.

## Fiji warning and cancellation

The original watchdog intentionally force-closes Fiji/ImageJ before a clean launch and again during crash recovery. The Hub requires a clear launch confirmation. Save unrelated Fiji work first.

**Stop watchdog monitoring** writes a cooperative stop request. It disables automatic relaunch and leaves Fiji open. Cancel processing using the existing Fiji controls so report finalization and worker cleanup can run. The Hub does not force-kill unrelated processes. This is a monitoring stop, not a guarantee that image processing has stopped.

## JMP and report destinations

The Hub checks JMP executable paths and warns before launch when estimated output paths may become too long. Existing engine path warnings remain. Choose a shorter configured output when necessary; the Hub does not relocate results silently. Generic summary destinations replace workstation names: Project Reports folder, Run output folder, Custom folder, Manual selection and All configured report destinations. The configured Reports folder receives shared summaries; run-specific Word reports retain the existing engine output structure.

## Logs and troubleshooting

Local files live under `%LOCALAPPDATA%/FuelCellProjectHub/gdl/`:

```text
config.json           # personal paths, modes and package source
last_session.json     # latest local session record
sessions/             # launch JSON with engine version and selected paths
runtime/<session>/    # session status and cooperative stop request
logs/                 # launcher stdout/stderr and watchdog log
packages/             # separately staged/activated engine versions
quick_runs/           # personal copies of default slots
```

The Hub passes session JSON through `GDL_SESSION_CONFIG`; a fixed session ID is retained across watchdog retries. Polling occurs every two seconds in background workers. Stale session IDs are ignored. Completed output references are accepted only within the selected output parent. Failures show recovery guidance; technical details are expandable and logs are available in the app. A corrupt GDL settings file is preserved and blocks GDL writes while the other Hub pages remain usable.

Use **Validate paths** when a dependency or folder becomes unavailable. Reconnect project storage if necessary. **Import legacy path overrides** reads valid `startup_paths.ini` values without overwriting existing Hub overrides or importing named-user fallback defaults. The legacy INI remains unchanged.

## Legacy standalone launch

The integrated package retains `LAUNCH SCRIPT.bat` and `RUN IN FIJI.py`. With no Hub session, local Hub overrides take precedence over legacy INI overrides, followed by portable defaults/detection. Existing standalone Fiji input/output dialogs remain. `EDIT STARTUP PATHS.bat` and `EDIT USER DEFAULTS.bat` are legacy/advanced configuration; ordinary path setup belongs in the Hub.

## Verification

Run the normal suite and `tests/smoke_gdl_ui.py`. Tests mock external launches, preserve all template JSON, compare unchanged algorithm functions, run the original Quick Run loader and Swift parser, exercise watchdog restart/stop/session identity, validate portable paths and test update/rollback/rejection. Offscreen screenshots cover standard and 1024 × 700 windows. See `gdl-integration-notes.md` for the inventory and baseline limits.
