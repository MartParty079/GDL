# Fuel Cell Project Hub

An initial Windows desktop app for the fuel-cell capstone. Built from the supplied document pack; reference Markdown is preserved in `docs/reference/`.

## Open the app

Double-click **Start Hub.cmd** in this folder once the environment is installed. On first launch the Software page scans your computer. Use **Locate application** for executable tools it cannot find, or follow the vendor installation guide. Teams uses **Test Launch** with `msteams://`; it never requires a Teams executable path. **Continue anyway** opens the dashboard; missing required tools keep a warning visible at startup.

Open **Settings** to enter the team's real goals, plan, agenda notes, decisions, GitHub repository, project folder, and shared resource links. Agenda notes are manually maintained; the shared agenda button opens your existing document. No live Teams/Word content synchronization is implemented.

## Development setup

Python 3.11 or later is recommended. PySide6 supplies the Qt runtime with its pip package: [official Qt installation guide](https://doc.qt.io/qtforpython-6/gettingstarted.html).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.main
```

If Python is not on PATH, use your Python executable's full path for the first command. Run from this directory. The runtime bundled with Codex can also create the environment, but it is not a prerequisite for future distribution.

## Implemented in this first development version

- Dashboard, Activity, Software, Project, Bugs, and Settings navigation.
- Background scans using configured paths, Windows App Paths, PATH, and bounded common install locations. Scanning never executes applications or installers.
- Required/Optional/Retired tool lifecycle, local executable overrides, manual executable selection, re-scan, and launch.
- Launch types: `exe`, `uri`, and `url`. Teams uses the Windows `msteams://` protocol; GitHub opens in a browser, and GitHub Desktop retains its optional executable launcher. Old manifest entries with no launch type still default to `exe`.
- Teams starts as **Needs test**. **Test Launch** marks it **Available** once Windows accepts the protocol request, or offers the Teams download page and Retry on failure. Acceptance confirms Windows dispatched the request; it cannot confirm sign-in or the resulting Teams window. URI launch results survive re-scans during the current session and are re-tested after restarting. No scanning of protected WindowsApps directories occurs.
- Python opens the configured interpreter in a console. Git opens a terminal in the project folder with the configured Git directory on PATH.
- Project links and folder/document launching; fixed dashboard cards without invented progress or project data.
- Explicit confirmation for project settings, revision history, and restore that preserves the previous state.
- Local activity, local bug reports with automatic context, status editing, and explicit JSON export. Reports are never automatically posted.
- Background GitHub latest-release checks at startup when a public release repository is configured; notifications only. No download or installation.

## Data and configuration

- `config/software_manifest.json`: shared tool metadata and vendor guides; no user paths.
- `config/project_defaults.json`: initial empty project configuration.
- `config/project.json`: saved project settings, created on Apply.
- `config/history/`: immutable settings revisions created on Apply/Restore.
- `%LOCALAPPDATA%/FuelCellProjectHub/`: machine-specific paths, setup state, local activity, and bugs.
- `FUEL_HUB_DATA_DIR` can override local state for testing or a portable profile.

JSON writes replace files atomically. Invalid JSON stops startup without overwriting the file. This is a **single-user development app**; concurrent shared editing is not supported. Keep project config/history with your backed-up project folder. The app doesn't create or move experimental data.

Manifest launch configuration:

```json
{"id":"teams","name":"Microsoft Teams","launch_type":"uri","launch_target":"msteams://"}
```

```json
{"id":"github_web","name":"GitHub","launch_type":"url","launch_target":"https://github.com/"}
```

Add the existing `category`, `lifecycle`, `url` (installation guide), and `note` fields when adding a full manifest entry. Executable entries use `launch_type: "exe"` plus detection metadata; resolved paths remain in the local profile. Saved legacy Teams executable paths are ignored and preserved, without altering other applications' paths or lifecycle settings.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tests\smoke_ui.py
```

The smoke test uses Qt's offscreen platform and isolated temporary state. It exercises startup, scanning, every page, a settings revision, a bug report, and screenshots the dashboard for review.

## Remaining milestones

This starts V0.1; it is not a completed packaged release.

1. Confirm detection on the actual installed Swift, JMP, Office, and SolidWorks versions. Portable executable software may require manual path selection; Teams instead requires a registered URI handler.
2. Add approved quick-install flows, version detection, and a reliable packaged `.exe` with PyInstaller.
3. Implement selective app/script updates with signed/verified release assets, backup, and rollback. Current checks support public GitHub releases only.
4. Add request handling and team synchronization in later versions. Samples, procedures, experiments, automatic agenda synchronization, Microsoft login, and AI are out of this first build.

Installer buttons currently open official vendor pages; they do not install anything. Retiring a tool preserves its metadata and configured path and disables launching it.
