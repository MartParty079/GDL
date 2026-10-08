# GDL Research Hub

A native Windows research management app for the fuel-cell capstone. Built from the supplied document pack; reference Markdown is preserved in `docs/reference/`.

Development uses **GDL Research Hub Beta** on `develop`, with a separate installer,
local profile, research sandbox and prerelease update channel. Beta currently runs
locally without connecting to production Supabase. Stable remains on `main` and
requires an explicit approved Production Release Order. See
[Beta/Stable separation](docs/beta_stable_editions.md) and
[development workflow](docs/CODEX_WORKFLOW.md).

## Team accounts and Windows distribution

The application supports approved Tarleton Microsoft and email/password accounts. Saved
sessions are encrypted for the Windows user. Administrators receive users,
activity, installations and system views; privileged changes are checked by
the hosted backend. Local SQLite and OneDrive remain the research backbone.

Windows users install `GDLResearchHub-Setup.exe`; Python, Git and developer
configuration are unnecessary. Updates use verified stable GitHub release
installers. See [accounts and distribution](docs/accounts_and_distribution.md)
for setup, security, acceptance results and current limits. See
[production integration](docs/production_integration.md) for the latest work order,
desktop callback, version history and release acceptance status. The canonical
version is in app/version.py; version_history.json retains prior work orders.

## Research workspace

Open the Project workspace for Samples, Experiments, Images, Data, Reports,
Timeline, Files and Legacy. Resizable navigation and details panes provide
resident-only previews, Windows file actions, database-wide sorting and explicit
metadata associations without moving research files. Click the version in the
header for About and version history. See [workspace guide](docs/research_workspace.md)
and [CHANGELOG.md](CHANGELOG.md) for behavior, verification and current limits.

## Native research indexing

A previously validated account can use local research offline for up to
24 hours, with an OFFLINE indicator and queued activity. First login requires
connectivity. Microsoft provides identity through Supabase; Graph is not used for storage. OneDrive handles synchronization; Windows provides the folders;
the Hub owns its local catalog, content search and research metadata.

Use **Settings > Storage > Project** to configure **GDL Research** (current)
and **Previous GDL Research**, source **Michelson GDL Stuffs** (read-only
Legacy / Old Test Data). Add or remove legacy roots using one path per line.
**Add current / reference / archive source** supports additional sources.
Changing projects preserves prior identities and catalog records. Disconnected
sources retain their last known references. Saving locations creates no source
markers and does not move or reorganize research files.

**Storage** edits application-owned database, generated output, cache and backup
folders. Environment variables in typed paths are expanded. Personal values
stay in Local AppData or `FUEL_HUB_DATA_DIR`; source defaults are portable.

**Indexing** provides **Quick Refresh**, **Full Scan**, **Rebuild Search Index**,
**Rebuild Entire Index**, **Index Current Project**, **Index Legacy Data** and
**Index Selected Folder**, with background execution and cancellation. Set
content size/text/page/cell limits, disable extraction, or enable watching and
periodic reconciliation. Startup never starts a full rebuild. **Advanced**
provides backup/restore, index history, keyword classification rules and portable
folder mappings. Rebuilds and migrations back up first and preserve manual edits.

**Project > Files & Data** defaults to current research. Choose Old Test Data
or All Sources, search filenames and resident document text, and filter by
category, extension, document type, dates, project/source, availability, folder,
tags and duplicates. SQLite FTS5 ranks results and retrieves only 200 rows per
page. **Edit Metadata**, **Toggle favorite**, and **Find related** change the
catalog only. **Import into Current Project** explicitly copies a selected
resident legacy file, preserving its original and avoiding overwrites.

Text, PDF, DOCX, XLSX and PPTX receive bounded local extraction; image headers
provide dimensions and format. Online-only files receive metadata without
opening their content. Proprietary formats remain metadata-only; image-only
PDFs are marked OCR required. Hashing uses SHA-256 for resident files up to
1 MB within a 32 MB run budget. Duplicate warnings are review aids and never
cause deletion. OneDrive cloud files absent from Windows cannot be indexed.

See [native architecture, migration, validation and limits](docs/native_indexing.md),
[storage configuration](docs/storage_configuration.md), and the
[cleanup manifest](cleanup_manifest.md).

## Open the app

Double-click **Start Hub.cmd** in this folder once the environment is installed. On first launch the Software page scans your computer. Use **Locate application** for executable tools it cannot find, or follow the vendor installation guide. Teams uses **Test Launch** with `msteams://`; it never requires a Teams executable path. **Continue anyway** opens the dashboard; missing required tools keep a warning visible at startup.

Open **Settings Ã¢â€ â€™ Storage** to select your locally synced project folder. Use **General** for goals, plan, meeting notes, and decisions; **Project resources** for the repository and resource links; **Software** for shared tool requirements; and **History** to review or restore settings revisions. **Updates** contains a personal startup-check switch and the public release repository. File/folder shortcuts use paths relative to your selected project root; online shortcuts use http/https URLs. Agenda notes are manually maintained; the shared agenda button opens your existing document. No live Teams/Word content synchronization is implemented.

## Advanced shared-library setup

The marker-based wizard below remains available under **Settings > Storage >
Advanced shared setup** for explicitly managed shared libraries. It is separate
from the read-only research configuration above; do not use it to initialize
the current or legacy research folders merely to index them.

Project files and large datasets live in the shared **SharePoint / OneDrive project library**. Each user syncs that library locally and selects their local synced project root once. **OneDrive/SharePoint owns the files; Fuel Cell Project Hub indexes and organizes references to them.**

Shared metadata uses relative paths, such as `03_Experiments/E-20261010-A/R03/video.mp4`. Absolute Windows paths belong only in the local profile. The same relative reference resolves against each user's own synced root.

1. Open **Settings Ã¢â€ â€™ Storage Ã¢â€ â€™ Locate Synced Folder**.
2. Select the project folder; the wizard validates access and the project marker. An unrelated, unmarked folder requires explicit confirmation. System roots and your home root are rejected.
3. Review missing standard folders. Optionally check **Create missing standard folders when I finish setup**, or use **Create Missing Folders** later. Nothing is renamed, moved, or deleted.
4. Finish to create the project marker if needed, save the root locally, and build the initial background index. Cancel before Finish leaves storage unchanged.
5. Open **Project Ã¢â€ â€™ Files & Data** using the workspace sidebar. Search names, relative paths, categories, or sample/experiment/run/procedure IDs. Filter by type, experiment, sample, or archive status; **More filters** reveals run, procedure, and modified dates. Click a column heading to sort. Filters persist across refreshes and workspace navigation; **Clear filters** resets them. **Reports** opens the file browser filtered to reports.
6. Select a result and use **Open**, **Open Containing Folder**, **Copy Relative Path**, or **View Metadata**.

**Refresh Index** walks directory metadata, compares relative paths, size, and modified timestamps, retains IDs for known paths, and records additions/modifications/removals. **Rebuild Index** performs a complete metadata rescan while retaining known IDs and deletion history. No full scan runs automatically at startup. **Cancel indexing** preserves the previous index until the scan commits.

OneDrive Files On-Demand is supported without reading dataset contents or hashing files. Cloud-only images, videos, spreadsheets, and other data are indexed from directory metadata; opening a file explicitly lets Windows hydrate it normally. Small local `experiment.json`, `run.json`, `sample.json`, `procedure.json`, and `metadata.json` files supply relationships. Cloud-only, linked, malformed, unsupported-schema, or oversized metadata is skipped with warnings. Shared project configuration itself is read to connect the project.

Files inside `99_Archive` are indexed and hidden by default; choose **Include Archived** to find them. Removed files remain as unavailable records in the local cache, with removal events and summary counts; recovery belongs to OneDrive/SharePoint. Raw-data records show whether their size or timestamp changed after initial indexing. Stable IDs are guaranteed for a persistent relative path; automatic rename/move identity matching is not implemented.

The UI reports local folder availability, not OneDrive's cloud sync completion. If the root or marker becomes unavailable, use **Locate Again** or **Open OneDrive**; the rest of the hub remains usable. Index warnings are available under Storage. Code-executing file formats require **Open Containing Folder** so you can explicitly choose an editor or tool.

`ProjectStorageProvider` retains the explicit local shared-library contract.
Native research storage uses the single SQLite catalog described above. See
[shared-library schema](docs/STORAGE_SCHEMA.md) for the optional marker workflow.

## GDL analysis and engine updates

YOURE A BETA GDL Analysis v209 is integrated under **Project Ã¢â€ â€™ Analysis** and **Settings Ã¢â€ â€™ Analysis Tools**. Configure paths, launch the existing Fiji interface, view watchdog status/logs, and import newer GDL ZIPs without replacing script folders manually. **Check for engine updates** searches the registered source folder; compatible updates retain the previous engine for rollback and preserve personal Quick Runs.

The existing launcher can close open Fiji/ImageJ windows, so every real launch requires a warning confirmation. No real Fiji analysis was launched during this integration, as requested. See the [GDL setup and update guide](docs/gdl_analysis.md) for paths, output modes, cancellation and validation limits.

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
- Shared light design system with blue accents, line icons, consistent cards and status pills, workspace sidebars, grouped settings, loading placeholders, actionable empty states, inline errors with expandable details, and timed notifications. Layout supports laptop windows from 1024 Ãƒâ€” 700. See [design implementation notes](docs/DESIGN_SYSTEM.md).
- Background scans using configured paths, Windows App Paths, PATH, and bounded common install locations. Scanning never executes applications or installers.
- Required/Optional/Retired tool lifecycle, local executable overrides, manual executable selection, re-scan, and launch.
- Launch types: `exe`, `uri`, and `url`. Teams uses the Windows `msteams://` protocol; GitHub opens in a browser, and GitHub Desktop retains its optional executable launcher. Old manifest entries with no launch type still default to `exe`.
- Teams starts as **Needs test**. **Test Launch** marks it **Available** once Windows accepts the protocol request, or offers the Teams download page and Retry on failure. Acceptance confirms Windows dispatched the request; it cannot confirm sign-in or the resulting Teams window. URI launch results survive re-scans during the current session and are re-tested after restarting. No scanning of protected WindowsApps directories occurs.
- Python opens the configured interpreter in a console. Git opens a terminal in the project folder with the configured Git directory on PATH.
- Project links and folder/document launching; fixed dashboard cards without invented progress or project data.
- Explicit confirmation for project settings, revision history, and restore that preserves the previous state.
- Local activity, local bug reports with automatic context, status editing, and explicit JSON export. Reports are never automatically posted.
- Background GitHub release checks with a personal startup preference, manual retry, and nonmodal update notices. Releases open only when requested; no automatic download or installation.
- Synced storage setup, missing-folder validation/creation, local background indexing, incremental change records, searchable files, archive awareness, and directory/metadata relationship inference.

## Data and configuration

- `config/software_manifest.json`: shared tool metadata and vendor guides; no user paths.
- `config/project_defaults.json`: initial empty project configuration.
- `config/project.json` and `config/history/`: fallback project settings/history before storage is connected.
- `<synced root>/.projecthub/project.json`: authoritative shared project marker and settings once connected; schema version 1.
- `<synced root>/.projecthub/history/`: settings revisions created on Apply/Restore for a connected project.
- `%LOCALAPPDATA%/FuelCellProjectHub/`: machine-specific paths, setup state, local activity, and bugs.
- `%LOCALAPPDATA%/FuelCellProjectHub/index/file_index.json`: this user's generated file index; never written into the shared project library.
- `FUEL_HUB_DATA_DIR` can override local state for testing or a portable profile.

JSON writes replace files atomically and reject non-JSON values. Invalid core app configuration stops startup without overwriting the file. Invalid storage metadata or cache shows an error without blocking unrelated hub features; corrupt caches are preserved rather than automatically deleted. Restore valid JSON or select a fresh local profile to recover a corrupt cache.

Each machine builds its own index, avoiding multi-user index writes. Shared settings detect edits since connection and require reconnection before overwriting newer settings; this is not a distributed lock. Coordinate shared settings edits and rely on OneDrive/SharePoint version history for sync conflicts. Legacy absolute folder shortcuts are preserved in local profile overrides and omitted from future shared writes. Existing historical files are not rewritten automatically.

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
.\.venv\Scripts\python.exe tests\smoke_storage_ui.py
.\.venv\Scripts\python.exe tests\smoke_design_ui.py
.\.venv\Scripts\python.exe tests\smoke_gdl_ui.py
```

The smoke test uses Qt's offscreen platform and isolated temporary state. It exercises startup, scanning, every page, a settings revision, a bug report, and screenshots the dashboard for review.

The storage smoke test exercises the setup wizard, folder creation, background indexing, `S-001` search, Video filtering, and opening/copying relative references in an isolated project fixture. It renders Storage and Files / Data for visual review. Test file-open actions are mocked; no fixture files are launched externally.

The design smoke test renders loading, empty, inline-error, grouped-settings, and minimum laptop states using isolated temporary state. Behavioral tests cover sorting/open-target integrity, preserved filters, shared-setting confirmation, personal preferences, and visible laptop controls.

The GDL smoke test verifies editable analysis paths, dependency validation, Analysis navigation, standard/laptop layouts and simulated launch/status/stop. GDL tests also exercise package updates/rollback, preserved Quick Runs and Swift units, watchdog retry/session identity and rejection of unsafe or incomplete ZIPs. Fiji/JMP launches are mocked.

## Remaining milestones

This starts V0.1; it is not a completed packaged release.

1. Confirm detection on the actual installed Swift, JMP, Office, and SolidWorks versions. Portable executable software may require manual path selection; Teams instead requires a registered URI handler.
2. Add approved quick-install flows, version detection, and a reliable packaged `.exe` with PyInstaller.
3. Implement selective app/script updates with signed/verified release assets, backup, and rollback. Current checks support public GitHub releases only.
4. Add request handling and coordinated shared editing in later versions. Sample/procedure/experiment management remains future work; this version indexes their file relationships only. Automatic agenda synchronization and AI remain outside this build.

Installer buttons currently open official vendor pages; they do not install anything. Retiring a tool preserves its metadata and configured path and disables launching it.
