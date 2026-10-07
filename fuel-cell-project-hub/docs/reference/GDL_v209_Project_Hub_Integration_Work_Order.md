# WORK ORDER: Integrate and Refactor YOURE A BETA GDL Analysis v209 into Fuel Cell Project Hub

## 1. Objective

Integrate the existing **YOURE A BETA GDL Analysis v209** package into the Fuel Cell Project Hub so it behaves like a first-class analysis tool rather than a separate loose folder of scripts.

The current analysis package is mature and feature-rich, so this work order must **preserve its working image-processing, JMP, report-generation, BEAST, Quick Run, Swift magnification, and watchdog behavior** while cleaning up how it is launched, configured, located, and connected to project storage.

The main goals are:

1. Launch the GDL analysis pipeline directly from Fuel Cell Project Hub.
2. Remove user-specific hardcoded file paths.
3. Make all machine-dependent paths editable from the Hub UI.
4. Centralize path detection and configuration.
5. Use the Hub's OneDrive/SharePoint project storage as the preferred project data source/output location.
6. Keep the existing Fiji/Jython analysis engine intact unless a change is necessary for integration.
7. Clean up the launcher/configuration architecture without performing a risky 29,000-line rewrite.
8. Add clear status, error handling, logging, and configuration validation.
9. Make the analysis package portable between team members.
10. Preserve compatibility with existing Quick Runs and analysis behavior.

---

# 2. Current Package Review

The supplied v209 package contains roughly **29,000 lines of Python/Jython code** across the launcher, defaults, Fiji runner, and analysis modules.

Important existing pieces include:

```text
YOURE_A_BETA_v209/
├── RUN IN FIJI.py
├── LAUNCH SCRIPT.bat
├── GDL_code/
│   ├── 01_Core_Imports_Helpers.py
│   ├── 02_User_Interface_Pages.py
│   ├── 03_User_Interface_Settings.py
│   ├── 04_Image_Processing_Sweeps.py
│   ├── 05_Reports_Manual_Tools_Pore_Maps.py
│   ├── 06A_Large_Pore_Repair.py
│   ├── 06B_Fiber_Fixer.py
│   ├── 06_Threshold_Analysis_JMP.py
│   ├── 07_Run_Engine_Exports.py
│   ├── 08_Workbook_JMP_Launch_Helpers.py
│   └── 09_BEAST_Workers_Main.py
├── Quick Runs/
├── Swift Magnification Tables/
├── Defaults and Other Stuff/
│   ├── GDL_Analysis_Launcher_v209.py
│   ├── GDL_User_Defaults.py
│   ├── startup_paths.ini
│   └── watchdog files/logs
└── Documentation/
```

The package already has useful path override concepts in:

```text
startup_paths.ini
```

including:

```text
FIJI_LAUNCHER
JMP_EXECUTABLE
MODULE_FOLDER
DEFAULT_OUTPUT_FOLDER
EXTRA_USER_ROOTS
SHOW_PATH_DIALOG
```

However, path handling is still fragmented and contains machine-specific defaults.

Examples currently hardcoded in `GDL_User_Defaults.py` include paths for:

```text
C:\Users\mkime\...
C:\Users\vgolf\...
```

and named shared/report folders tied to specific users.

Additional user-specific paths also exist inside analysis modules, including preferred work-zone paths and Fiji search roots.

These must be removed from shared analysis defaults.

---

# 3. Important Refactoring Principle

## Do NOT rewrite the analysis engine into the Hub UI.

The current Fiji/Jython analysis pipeline contains substantial working logic and should remain isolated as the **analysis engine**.

Fuel Cell Project Hub should become the:

```text
configuration layer
launcher
path manager
job creator
status viewer
log viewer
project-storage bridge
```

The v209 code remains responsible for:

```text
image processing
Fiji operations
threshold analysis
pore measurements
fiber fixer
large pore repair
JMP generation/launching
Excel generation
Word report generation
BEAST workers
Quick Runs
Swift magnification logic
```

This separation reduces regression risk.

---

# 4. Target Architecture

Use the following architecture:

```text
Fuel Cell Project Hub
        │
        ├── Analysis Settings
        │      ├── Fiji path
        │      ├── JMP path
        │      ├── Analysis engine path
        │      ├── Quick Run folder
        │      ├── Swift table folder
        │      ├── Input folder
        │      └── Output folder
        │
        ├── GDL Analysis Page
        │      ├── Launch Analysis
        │      ├── Open Quick Runs
        │      ├── View Logs
        │      └── Status
        │
        ▼
Hub Analysis Adapter
        │
        ├── validates configuration
        ├── builds launch/session config
        ├── launches watchdog/engine
        ├── tracks status
        └── reports results
        │
        ▼
YOURE A BETA GDL Analysis Engine
        │
        ├── Fiji
        ├── JMP
        ├── Excel/Word exports
        └── project output
```

---

# 5. Repository Location

Move or copy the analysis package into a clear managed location inside the project repository.

Recommended:

```text
fuel-cell-project-hub/
├── app/
├── config/
├── analysis/
│   └── gdl/
│       ├── engine/
│       ├── quick_runs/
│       ├── swift_magnification/
│       ├── resources/
│       └── docs/
└── tests/
```

Suggested mapping:

```text
RUN IN FIJI.py
→ analysis/gdl/engine/run_in_fiji.py

GDL_code/
→ analysis/gdl/engine/modules/

Quick Runs/
→ analysis/gdl/quick_runs/

Swift Magnification Tables/
→ analysis/gdl/swift_magnification/

GDL_Analysis_Launcher_v209.py
→ analysis/gdl/engine/launcher.py

GDL_User_Defaults.py
→ analysis/gdl/engine/defaults.py
```

However, avoid renaming files immediately if Fiji/Jython imports or `execfile()` assumptions would break.

A safe first phase may preserve filenames and only relocate the package.

---

# 6. Preserve Legacy Compatibility First

Before cleanup, establish a compatibility baseline.

Codex must:

1. Run the existing package unchanged.
2. Record the current launch behavior.
3. Verify at least one known Quick Run.
4. Verify Fiji launch.
5. Verify JMP detection/launch.
6. Verify an output folder is produced.
7. Verify reports still generate.
8. Verify watchdog status behavior.
9. Run existing integration-test instructions where practical.
10. Commit this state before structural refactoring.

Do not perform cleanup until a baseline exists.

---

# 7. Remove Hardcoded User Paths

Remove shared defaults tied to named Windows users.

Examples that must no longer exist as normal runtime defaults:

```text
C:\Users\mkime\...
C:\Users\vgolf\...
```

including:

- Fiji launcher paths
- extra user roots
- GDL work-zone paths
- Andrew/Michelson report locations
- vgolf report locations
- user-specific OneDrive paths

Shared code may contain generic Windows install locations such as:

```text
C:\Program Files\JMP\
C:\Program Files\SAS\
```

for bounded application detection.

User home paths must instead be dynamically discovered or configured.

---

# 8. Central Path Configuration

Create one canonical path configuration model for the GDL analysis integration.

Recommended fields:

```json
{
  "fiji_executable": "",
  "jmp_executable": "",
  "analysis_engine_root": "",
  "module_folder": "",
  "quick_run_folder": "",
  "swift_magnification_folder": "",
  "default_input_folder": "",
  "default_output_folder": "",
  "report_output_folder": "",
  "temp_work_folder": "",
  "extra_search_roots": []
}
```

Do not maintain separate competing path values in several files unless required for backward compatibility.

---

# 9. Local vs Shared Configuration

Machine-specific executable paths must remain local.

Store in:

```text
%LOCALAPPDATA%\FuelCellProjectHub\
```

Examples:

```text
Fiji executable
JMP executable
local analysis engine path
local temp folder
extra search roots
```

Project-relative data paths may be shared.

Examples:

```text
Quick Run folder
project input folder
project output folder
report folder
Swift magnification table folder
```

when those live under the shared OneDrive project root.

Never store another user's absolute OneDrive path in shared configuration.

---

# 10. Path Resolution Rules

Use the following precedence for each configurable path:

```text
1. Explicit local user override
2. Project-relative configured path
3. Valid auto-detected path
4. Bundled/default relative location
5. Missing / needs configuration
```

Do not silently replace an explicit valid user-selected path.

---

# 11. Editable Paths UI

Add a dedicated section:

```text
Settings
→ Analysis Tools
→ GDL Analysis
```

Provide editable rows for:

```text
Fiji
JMP
Analysis Engine
Module Folder
Quick Run Folder
Swift Magnification Folder
Default Input Folder
Default Output Folder
Report Output Folder
Temporary Work Folder
```

Each row should show:

```text
Label
Current Path
Status
[ Browse ]
[ Auto Detect ]
[ Reset ]
[ Open ]
```

Example:

```text
Fiji
C:\Users\Matthew\Fiji\fiji-windows-x64.exe
✓ Ready

[ Browse ] [ Auto Detect ] [ Open ]
```

---

# 12. Path Types

The path manager must distinguish:

```text
Executable
Folder
File
Project-relative folder
```

Example definitions:

```text
Fiji                  Executable
JMP                   Executable
Analysis Engine       Folder
Module Folder         Folder
Quick Run Folder      Folder
Swift Table Folder    Folder
Input Folder          Folder
Output Folder         Folder
```

Use the correct file/folder chooser.

---

# 13. Path Validation

Validation must check more than simple existence.

## Fiji

Verify:

- selected file exists
- supported executable/launcher name
- likely Fiji/ImageJ installation structure exists

Expected nearby folders may include:

```text
jars
plugins
```

## JMP

Verify:

- selected file exists
- executable is `jmp.exe` or expected equivalent

## Engine

Verify required files exist:

```text
RUN IN FIJI.py
GDL_code or configured module folder
defaults/config files
```

## Module folder

Verify required module filenames exist.

## Output/Input folders

Verify:

- folder exists or may be safely created
- writable where required

Show a clear status:

```text
Ready
Missing
Invalid
Not Writable
Needs Setup
```

---

# 14. Auto Detection

Create reusable detection functions.

## Fiji detection

Search:

```text
user-configured location
Windows App Paths if available
PATH
common user folders
Program Files
bounded local user directories
```

Do not search entire drives.

Remove hardcoded named-user directories.

Use dynamic values such as:

```python
Path.home()
LOCALAPPDATA
PROGRAMFILES
PROGRAMFILES(X86)
```

## JMP detection

Keep the useful bounded search of:

```text
C:\Program Files\JMP
C:\Program Files\SAS
```

and known JMP edition/version patterns.

Do not rely only on JMP 19 Student Edition.

---

# 15. Editable Path UX

Path fields must not require users to manually edit INI/Python files.

Users should never need to open:

```text
startup_paths.ini
GDL_User_Defaults.py
```

just to configure applications.

The Hub UI is the primary path configuration interface.

Legacy files may remain behind the scenes for compatibility.

---

# 16. Path Status on Startup

The Hub's software/system setup should show GDL analysis dependencies.

Example:

```text
GDL Analysis

Fiji                Ready
JMP                 Ready
Analysis Engine      Ready
Output Folder        Ready

[ Launch Analysis ]
```

If one is missing:

```text
GDL Analysis needs setup

JMP executable could not be found.

[ Locate JMP ]
```

Do not expose a raw configuration-file error.

---

# 17. Analysis Page

Add a project workspace page:

```text
Analysis
```

or under:

```text
Software → GDL Analysis
```

Recommended page sections:

### Analysis Status

```text
Engine Version      v209
Fiji                Ready
JMP                 Ready
Storage             Connected
Last Run            ...
```

### Actions

```text
[ Launch GDL Analysis ]
[ Open Input Folder ]
[ Open Output Folder ]
[ Quick Runs ]
[ View Logs ]
[ Settings ]
```

### Recent Runs

Later:

```text
Run
Date
Input
Output
Status
Duration
```

---

# 18. Hub-to-Engine Adapter

Create a dedicated service, for example:

```text
app/services/gdl_analysis.py
```

Responsibilities:

```text
validate_paths()
build_session_config()
launch_analysis()
read_status()
stop_analysis()
open_logs()
resolve_output()
```

Do not put Fiji launch logic directly into `window.py`.

---

# 19. Launch Configuration File

Instead of forcing the analysis engine to infer everything from hardcoded globals, have the Hub generate a launch/session configuration.

Recommended temporary/session JSON:

```json
{
  "session_id": "...",
  "fiji_executable": "...",
  "jmp_executable": "...",
  "module_folder": "...",
  "quick_run_folder": "...",
  "swift_magnification_folder": "...",
  "input_folder": "...",
  "output_folder": "...",
  "project_root": "...",
  "launched_by_project_hub": true
}
```

The engine should read this when launched from the Hub.

---

# 20. Configuration Transport

Preferred transport:

```text
temporary session JSON + environment variable pointing to it
```

Example:

```text
GDL_SESSION_CONFIG=C:\...\gdl_session_123.json
```

This is cleaner than constructing long command-line argument strings.

Continue supporting legacy standalone configuration when no Hub session config exists.

---

# 21. Backward Compatibility

If the GDL engine is started outside the Hub:

```text
LAUNCH SCRIPT.bat
```

or:

```text
RUN IN FIJI.py
```

it should continue working during the transition.

Configuration precedence:

```text
Hub session config
→ local Hub GDL settings
→ startup_paths.ini legacy override
→ auto detection/defaults
```

Later, legacy startup path editing can be retired after the Hub workflow is proven.

---

# 22. Output Integration with OneDrive Project Storage

The preferred default output location should come from the Hub's shared project storage.

Recommended logical target:

```text
05_Processed_Data/
```

or experiment/run-specific folders later.

Do not hardcode personal report folders.

Initial configuration may allow:

```text
Project Default Output
Custom Output
Ask Every Run
```

---

# 23. Output Folder Modes

Provide an option:

```text
Output location mode
```

Values:

```text
Project default
Remember last folder
Custom configured folder
Ask when analysis starts
```

Default should eventually be:

```text
Project default
```

once OneDrive storage is established.

---

# 24. Input Folder Modes

Provide:

```text
Input location mode
```

Options:

```text
Choose at launch
Project Files & Data
Remember last folder
Configured folder
```

Do not force users to edit script code.

---

# 25. Report Destination Cleanup

The current script contains named destination choices associated with specific users.

Replace these concepts:

```text
Michelson/Andrew All Reports folder
vgolf/OneDrive All Reports folder
```

with generic destinations:

```text
Project Reports folder
Run output folder
Custom folder
Manual selection
All configured report destinations
```

Any old Quick Run containing legacy destination names should be migrated or mapped safely.

---

# 26. Quick Run Preservation

Do not break existing Quick Run JSON files.

The integration must:

- load all five current Quick Run slots
- preserve current names
- preserve saved processing settings
- preserve Swift objective/profile selection
- preserve JMP/Word settings
- support existing JSON format
- migrate only when necessary

Add schema/version metadata to future Quick Runs if not already available.

---

# 27. Quick Run Location

Quick Runs should have a configurable folder.

Preferred default:

```text
analysis/gdl/quick_runs
```

or a project-relative shared location.

The Hub should expose:

```text
[ Open Quick Runs ]
```

and later:

```text
Quick Run Manager
```

Do not hardcode only the folder beside the script.

---

# 28. Swift Magnification Tables

The Swift magnification table location must also be configurable.

Keep current behavior:

```text
search beside image
search parent directories
use configured/bundled fallback
```

Add a configured fallback location from the Hub.

Display it under Analysis Settings.

---

# 29. Default Settings Cleanup

Split configuration responsibilities.

Current `GDL_User_Defaults.py` mixes:

```text
machine paths
application metadata
algorithm defaults
UI defaults
report defaults
BEAST defaults
```

Refactor gradually.

Target structure:

```text
analysis_defaults.py
path_defaults.py
runtime_config.py
```

or equivalent.

Do not perform this split until tests cover current behavior.

Path defaults must contain no named-user paths.

Algorithm defaults may remain shared.

---

# 30. Preserve Jython Compatibility

The Fiji engine appears to rely on Jython/Python 2-compatible syntax and `execfile()`.

Do not casually modernize engine files to Python 3 syntax.

Hub-side code may use modern Python 3.

Maintain a clear boundary:

```text
Hub = Python 3 / PySide6
Engine = Fiji/Jython-compatible
```

Any shared JSON must use structures readable by both environments.

---

# 31. Clean Launcher Architecture

Current launch responsibilities are split between:

```text
LAUNCH SCRIPT.bat
GDL_Analysis_Launcher_v209.py
RUN IN FIJI.py
```

Refactor toward:

```text
Hub
→ GDLAnalysisService
→ launcher.py
→ Fiji
→ RUN IN FIJI.py
```

Keep `LAUNCH SCRIPT.bat` only as a legacy/manual fallback.

Do not require the `.bat` when launched from the Hub.

---

# 32. Watchdog Preservation

The v209 watchdog is important and must be retained.

Hub integration should consume watchdog status rather than replace it prematurely.

Statuses should map to Hub UI:

```text
STARTING
RUNNING
COMPLETED
CANCELED
FAILED
RESTARTING
```

Display user-friendly equivalents:

```text
Starting Fiji…
Running analysis…
Completed
Canceled
Analysis failed
Restarting Fiji…
```

---

# 33. Watchdog Files

Move watchdog state/logs out of the distributed code directory if practical.

Preferred local runtime location:

```text
%LOCALAPPDATA%\FuelCellProjectHub\gdl\runtime\
```

Example:

```text
watchdog_status_<session>.json
watchdog.log
```

Do not commit machine-generated watchdog files to GitHub.

---

# 34. Logging

Create a clean logging hierarchy.

Recommended:

```text
%LOCALAPPDATA%\FuelCellProjectHub\logs\
    hub.log
    gdl_launcher.log
    gdl_watchdog.log
```

Per-run logs may also be stored in the analysis output folder.

The Hub should provide:

```text
[ View Latest Log ]
[ Open Log Folder ]
```

---

# 35. Remove Runtime Artifacts from Source Control

Do not commit:

```text
Fiji Watchdog Log*.txt
Fiji Watchdog Status*.json
__pycache__
temporary outputs
generated reports
worker temp directories
```

Update `.gitignore`.

---

# 36. Error Handling

The user must not receive raw traceback dialogs from the Hub.

Example:

Bad:

```text
FileNotFoundError: ...
```

Good:

```text
JMP could not be launched.

The configured JMP executable no longer exists.

[ Locate JMP ]
[ Auto Detect ]
[ Cancel ]
```

Keep raw traceback in logs for debugging.

---

# 37. Analysis Error Mapping

Map known failures.

Examples:

### Fiji missing

```text
Fiji is not configured.
```

### JMP missing

```text
JMP is required for the selected analysis/report mode but could not be found.
```

### Module folder invalid

```text
The GDL analysis engine is incomplete.
9 required module files were expected; 1 is missing.
```

### Output unavailable

```text
The selected output folder is not writable.
```

### OneDrive disconnected

```text
Project storage is currently unavailable.
Choose another output folder or reconnect OneDrive.
```

---

# 38. Loading UX

Follow the Fuel Cell Project Hub design-language specification.

When validating dependencies:

```text
gray skeleton rows
```

When launching:

```text
Starting analysis…
```

When waiting on Fiji:

```text
Starting Fiji…
```

When running:

```text
GDL analysis is running
```

Do not freeze the Hub while analysis runs.

---

# 39. Analysis Run Card

When active, show:

```text
GDL Analysis

Status       Running
Started      10:42 PM
Input        Sample Batch 03
Output       05_Processed_Data/...
Fiji         Running
JMP Workers  4 active
```

Actions:

```text
[ Open Output Folder ]
[ View Log ]
[ Stop Analysis ]
```

Only expose information reliably available from the engine.

---

# 40. Background Process Management

Launch the external analysis process from a worker/service layer.

Do not block the PySide6 main thread.

Track:

```text
PID
session ID
start time
status file
log file
```

Stopping analysis must use the existing safe shutdown/watchdog behavior where possible.

Avoid blind `taskkill` from Hub code unless the launcher already requires it.

---

# 41. Existing Fiji Force-Close Behavior

The current launcher intentionally force-closes existing Fiji/ImageJ instances.

This is dangerous enough to require clear UX.

Before launching from the Hub:

```text
GDL Analysis requires a clean Fiji session.

Any currently open Fiji/ImageJ windows may be closed by the analysis launcher.
Save unrelated Fiji work before continuing.

[ Cancel ]
[ Launch Analysis ]
```

Allow a future setting to suppress this warning once users understand the behavior.

---

# 42. App Software Integration

The Hub already tracks software paths.

Reuse that software registry.

Do not create an entirely separate Fiji/JMP path system if the Hub's Software page already knows their executable paths.

Preferred:

```text
Software registry
       ↓
GDL Analysis Settings
```

GDL settings may override paths only when necessary.

Single source of truth should be favored.

---

# 43. Canonical Path Registry

Create one canonical service such as:

```text
PathRegistry
```

Responsibilities:

```python
get_fiji()
set_fiji()
get_jmp()
set_jmp()
get_project_root()
get_gdl_engine()
get_output_root()
validate()
```

Both Software UI and GDL analysis adapter should use it.

Avoid duplicate path caches.

---

# 44. Editable File Paths

Every external dependency path must be editable from the Hub.

At minimum:

```text
Fiji executable
JMP executable
GDL engine root
module folder
Quick Runs
Swift magnification table/folder
input folder
output folder
reports folder
temporary/runtime folder
```

Each must support:

```text
Browse
Paste/edit
Auto Detect where meaningful
Open
Reset to Default
```

Path changes should be validated before Apply.

---

# 45. Settings History

Project-wide/shared analysis configuration should use Hub settings revision history.

Machine-local executable path changes may be logged locally.

Example activity entries:

```text
GDL Fiji path updated
GDL JMP path auto-detected
GDL output folder changed
GDL analysis engine updated to v209
```

Do not log sensitive full local paths into shared team activity unless desired.

---

# 46. Path Portability

If a configured folder is inside the OneDrive project root, save its relative project path.

Example:

Local:

```text
C:\Users\Matthew\OneDrive...\Fuel Cell Capstone\05_Processed_Data
```

Shared:

```text
05_Processed_Data
```

Resolve it per machine at runtime.

External executables remain absolute local paths.

---

# 47. Long Path Handling

The current engine already warns about long output paths affecting JMP.

Preserve and improve this behavior.

Before run:

- estimate resolved output path length
- warn if likely unsafe for JMP
- recommend a shorter configured output location

Do not silently relocate outputs.

Example:

```text
This output path may be too long for JMP.

Consider using:
C:\GDL_OUT

[ Change Output Folder ]
[ Continue Anyway ]
```

---

# 48. Analysis Engine Version

Expose engine version through a machine-readable source.

Example:

```json
{
  "engine": "YOURE A BETA GDL Analysis",
  "version": "209"
}
```

Do not parse the version only from filenames.

Hub should display:

```text
GDL Analysis Engine v209
```

---

# 49. Analysis Package Manifest

Add:

```text
analysis/gdl/manifest.json
```

Example:

```json
{
  "id": "gdl_analysis",
  "name": "GDL Analysis",
  "version": "209",
  "entrypoint": "RUN IN FIJI.py",
  "launcher": "Defaults and Other Stuff/GDL_Analysis_Launcher_v209.py",
  "module_folder": "GDL_code",
  "quick_run_folder": "Quick Runs",
  "swift_folder": "Swift Magnification Tables",
  "requires": ["fiji", "jmp"]
}
```

This removes knowledge of package layout from UI code.

---

# 50. Module Manifest

The required GDL module list should have one canonical source.

Currently the list appears in defaults and runner logic.

Move toward manifest-driven validation.

Example:

```json
"modules": [
  "01_Core_Imports_Helpers.py",
  "02_User_Interface_Pages.py",
  ...
]
```

For backward compatibility, the engine can still expose `CODE_MODULE_FILES`.

Do not maintain several manually duplicated module lists long term.

---

# 51. Clean Naming

Do not rename the scientific algorithm/UI labels unnecessarily.

However, code-facing identifiers should become descriptive.

Examples:

```text
gdl_analysis
gdl_engine
quick_runs
swift_magnification
runtime_config
```

The display name may remain:

```text
YOURE A BETA GDL Analysis v209
```

or later be rebranded separately.

---

# 52. UI Duplication Strategy

The existing GDL analysis itself contains a substantial Fiji/Swing UI.

Do not try to reproduce every processing setting in the Hub immediately.

Phase 1:

```text
Hub launches and manages existing GDL UI.
```

Phase 2:

```text
Hub can choose Quick Run and paths before launch.
```

Phase 3:

```text
selected high-value settings may move into Hub.
```

This avoids building two full settings systems at once.

---

# 53. Hub Launch Modes

Provide:

```text
Open Full GDL Analysis
```

which launches the existing Fiji UI.

Later optionally provide:

```text
Run Quick Configuration
```

where Hub chooses a saved Quick Run and launches more directly.

Do not implement headless execution until the existing engine has a stable external job interface.

---

# 54. Job/Run Metadata

When launched from Hub, generate a metadata record.

Example:

```json
{
  "session_id": "GDL-20261007-001",
  "engine_version": "209",
  "started": "...",
  "input_folder": "...relative if project...",
  "output_folder": "...relative if project...",
  "quick_run": "",
  "status": "RUNNING"
}
```

Store local runtime state and optionally a run record in the project later.

---

# 55. Status Polling

Hub should poll the existing watchdog status file at a reasonable interval such as:

```text
1–2 seconds
```

Do not hammer the filesystem.

Update only the active run UI.

---

# 56. Completion Handling

On completion:

```text
Analysis completed
```

Show:

```text
[ Open Output Folder ]
[ View Report ]
[ View Log ]
```

where available.

Do not assume a specific report exists unless confirmed.

---

# 57. Failed Run Handling

On failure:

```text
GDL Analysis failed
```

Show the cleaned watchdog message.

Actions:

```text
[ View Details ]
[ Open Log ]
[ Retry ]
```

"View Details" may reveal technical traceback text in a developer/details panel, not the main error.

---

# 58. Config Migration

Migrate values from:

```text
startup_paths.ini
```

the first time Hub integration runs.

If valid values exist:

```text
FIJI_LAUNCHER
JMP_EXECUTABLE
MODULE_FOLDER
DEFAULT_OUTPUT_FOLDER
EXTRA_USER_ROOTS
```

offer/import them into Hub local GDL configuration.

Do not overwrite existing Hub settings.

After migration, retain the legacy file for standalone compatibility.

---

# 59. Legacy User Defaults Migration

Do NOT import named-user fallback paths from `GDL_User_Defaults.py` as shared settings.

Only migrate paths that:

- exist on the current machine
- are clearly intended for the current user
- pass validation

Prefer auto-detection over importing stale machine-specific defaults.

---

# 60. Report Folder Migration

Legacy named destinations should map to generic configuration.

Example mapping:

```text
Michelson/Andrew All Reports folder
→ Custom legacy report folder

vgolf/OneDrive All Reports folder
→ Custom legacy report folder
```

Do not keep user names as permanent UI choices.

---

# 61. Remove Manual BAT Editors from Normal Workflow

The following may remain for legacy use:

```text
EDIT STARTUP PATHS.bat
EDIT USER DEFAULTS.bat
```

but the README should mark them:

```text
Legacy / advanced configuration
```

Normal users configure paths in Fuel Cell Project Hub.

---

# 62. Documentation Cleanup

Create concise documentation:

```text
docs/gdl_analysis.md
```

Sections:

```text
Overview
Dependencies
Launch from Project Hub
Path Configuration
Quick Runs
Output Locations
Fiji Warning
JMP Requirements
Troubleshooting
Legacy Standalone Launch
```

Do not make users read dozens of version-specific patch-note files to understand setup.

Keep historical docs archived.

---

# 63. Source Cleanup

Do not perform cosmetic rewriting across all 29k lines.

Target cleanup to:

```text
path handling
configuration
launcher duplication
runtime artifacts
hardcoded users
dead compatibility paths where proven safe
error handling boundaries
```

Avoid changing algorithms solely for style.

---

# 64. Git Cleanup

Add/update `.gitignore` for:

```text
__pycache__/
*.pyc
Fiji Watchdog Log*.txt
Fiji Watchdog Status*.json
*.tmp
runtime/
logs/
generated reports
temporary worker files
```

Do not ignore bundled reference resources or Quick Run templates intentionally stored in Git.

---

# 65. Tests: Path Configuration

Add tests for:

1. Fiji configured path
2. invalid Fiji path
3. Fiji auto-detection
4. JMP configured path
5. JMP auto-detection
6. invalid JMP path
7. engine root validation
8. missing module detection
9. Quick Run folder validation
10. Swift table folder validation
11. output folder writable
12. input folder existence
13. relative OneDrive path resolution
14. local absolute executable paths remain local
15. path reset/default behavior

---

# 66. Tests: Launch Adapter

Add tests for:

1. build session config
2. launch command construction
3. environment variable injection
4. watchdog status polling
5. STARTING state
6. RUNNING state
7. COMPLETED state
8. CANCELED state
9. FAILED state
10. missing status file handling
11. stale session status ignored
12. launch process failure
13. clean user-facing error mapping

Use mocked processes where actual Fiji/JMP execution is not appropriate.

---

# 67. Tests: Legacy Compatibility

Verify:

- standalone launcher still starts
- startup_paths.ini still works outside Hub
- existing Quick Runs load
- current Swift magnification table loads
- JMP script generation remains unchanged
- report generation behavior remains unchanged
- BEAST settings remain unchanged
- watchdog restart logic remains functional

---

# 68. Tests: Real Machine Validation

On the actual development machine verify:

```text
Hub detects Fiji
Hub detects JMP
Hub validates v209 engine
Hub launches the analysis
Existing GDL UI appears
One known analysis completes
JMP launches when required
Output appears in selected folder
Watchdog state is reflected in Hub
Logs are accessible
```

Do this before declaring integration complete.

---

# 69. UX Requirements

Follow the existing Project Hub Design Language & UX Specification.

Specifically:

- Apple-inspired clean UI
- skeleton placeholders while validating paths
- no frozen UI
- consistent buttons
- status pills
- inline path errors
- calm empty states
- actionable errors
- soft toast on successful path change
- minimal modal use

Example path card:

```text
JMP

C:\Program Files\JMP\JMPSTUDENT\19\jmp.exe
● Ready

[ Open ]   [ Browse ]   [ Auto Detect ]
```

---

# 70. Acceptance Criteria

The integration is complete when this exact workflow works:

1. Open Fuel Cell Project Hub.
2. Open Software or Analysis Settings.
3. See GDL Analysis v209.
4. Fiji is auto-detected or can be selected with Browse.
5. JMP is auto-detected or can be selected with Browse.
6. Every relevant path can be manually edited.
7. Invalid paths show useful inline errors.
8. Select a default input/output location.
9. Open the GDL Analysis page.
10. Click `Launch GDL Analysis`.
11. Hub creates a session configuration.
12. Hub launches the existing v209 watchdog/engine.
13. Existing Fiji GDL UI opens.
14. Hub shows `Starting` then `Running`.
15. Existing analysis behavior is preserved.
16. JMP still launches when required.
17. Output is written to the configured location.
18. Hub detects completion.
19. Hub offers `Open Output Folder` and `View Log`.
20. No `mkime` or `vgolf` hardcoded user path is required for normal operation.
21. A second team member can configure their own paths without modifying source code.
22. Existing Quick Runs remain usable.

---

# 71. Non-Goals

Do NOT attempt in this work order:

- rewrite the 29k-line analysis engine
- convert all Jython code to Python 3
- replace Fiji
- replace JMP
- reproduce every Fiji settings screen in PySide6
- redesign pore/fiber algorithms
- modify scientific results unless required by a verified bug
- implement headless cloud processing
- implement Microsoft Graph
- implement multi-user database synchronization
- rewrite Word/Excel export architecture
- remove BEAST functionality
- remove the watchdog

These can be separate future projects.

---

# 72. Recommended Implementation Phases

## Phase 1 — Baseline and Package Integration

- Add package to repo
- Add manifest
- Add `.gitignore`
- Confirm existing launch
- Preserve current functionality

## Phase 2 — Path Registry

- Centralize Fiji/JMP/engine/input/output paths
- Remove named-user hardcoded paths
- Add local path storage
- Add validation and auto-detection

## Phase 3 — Hub UI

- Add GDL settings page/card
- Add editable path controls
- Add status/loading/error states
- Add Analysis page

## Phase 4 — Launch Adapter

- Build session JSON
- launch watchdog
- monitor status
- expose logs
- completion/error handling

## Phase 5 — OneDrive Integration

- default project-relative input/output paths
- report location cleanup
- relative path resolution

## Phase 6 — Legacy Migration

- import `startup_paths.ini`
- map legacy report destinations
- preserve Quick Runs
- update docs

## Phase 7 — Tests and Cleanup

- automated tests
- real machine validation
- regression testing
- documentation

---

# 73. Recommended New Files

Suggested additions:

```text
app/services/gdl_analysis.py
app/services/path_registry.py

analysis/gdl/manifest.json

config/gdl_defaults.json

tests/test_gdl_paths.py
tests/test_gdl_adapter.py
tests/test_gdl_config.py

docs/gdl_analysis.md
```

Reuse existing Hub storage/settings services where appropriate.

Do not duplicate project storage logic.

---

# 74. Recommended Runtime Files

Store locally:

```text
%LOCALAPPDATA%\FuelCellProjectHub\gdl\
├── config.json
├── runtime\
├── logs\
└── sessions\
```

Example session:

```text
sessions/GDL-20261007-001.json
```

Do not store local executable paths in GitHub.

---

# 75. Final Architectural Rule

There should be three clean layers:

```text
Fuel Cell Project Hub UI
        ↓
Hub GDL Adapter / Path Registry
        ↓
Existing v209 Fiji/Jython Analysis Engine
```

The Hub should know **how to configure, launch, monitor, and organize** the analysis.

The Hub should not need to know the internal image-processing implementation.

The analysis engine should not need to know which Windows user is running it.

That separation is the core of this refactor.

---

# 76. Codex Instruction

Before modifying code, inspect the entire supplied v209 package and identify:

- all hardcoded absolute paths
- all path discovery logic
- all configuration file readers/writers
- all environment variables
- all launcher entry points
- all output/report path decisions
- all Quick Run path assumptions
- all Swift magnification path assumptions
- all watchdog status/log locations

Create a concise inventory in the implementation notes before changing behavior.

Then implement the work order incrementally.

Do not delete legacy behavior until the replacement path has been tested.

Do not perform broad algorithm refactoring as part of this task.

Scientific behavior preservation is higher priority than cosmetic code cleanup.
