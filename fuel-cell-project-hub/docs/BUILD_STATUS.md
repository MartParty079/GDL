# Current build: research workspace 0.2.0

Microsoft authentication and Graph are retired. The current architecture and
validation are in [research workspace](research_workspace.md) and
[native indexing](native_indexing.md). Entries below are a
historical development record; old package paths and account screens are obsolete.

# Initial build status

Created October 6, 2026 from the provided document pack.

## Verification completed

- Nine service tests passed: revision/restore, local/shared separation, missing configured paths, non-executing detection, launch arguments with spaces, malformed config preservation, bug persistence, resource URI validation, and release repository validation.
- Qt offscreen smoke test passed: first launch, background detection, six pages, settings revision/restore, and local bug report.
- Dashboard screenshot reviewed after loading Windows fonts for offscreen rendering.
- Python source compilation passed.

These checks did not install or launch engineering tools, access university accounts, submit reports, or modify existing project files outside the new app directory.

## Product status

Working source application with a project-local Python environment and double-click launcher. Not yet a packaged production release. Manual software configuration, project links, and dashboard content are required. Release installation/rollback, quick installers, shared requests, multi-user editing, and future research entities remain unimplemented.

The supplied technical framework is treated as design guidance rather than authority to execute installers, create accounts, or change unrelated system settings.

## Teams launch fix

Applied the subsequently authorized Teams work order:

- A common launcher dispatches executable, Windows application protocol, and web targets.
- Teams uses `msteams://` with Test Launch and no executable locator. Launch failures offer download and retry. Teams readiness is verified by explicit launch, not by executing during a scan.
- GitHub web launcher added; GitHub Desktop's existing ID, saved executable paths, and lifecycle overrides remain compatible.
- Old manifest entries default to executable launching. Strict `.exe` and Windows Store alias validation remains intact for executable tools.
- All 23 service/UI regression tests passed, along with the updated desktop smoke test and source compilation.
- A real `msteams://` launch was accepted by Windows outside the restricted test sandbox. The initial in-sandbox attempt returned access denied; no application or system configuration was changed to bypass it.

Launch-control tests mock Windows handoff and browsers; they do not establish that Teams sign-in or a particular Teams window is working. Successful real Windows handoff likewise confirms dispatch only.

## OneDrive / SharePoint storage backbone

Implemented the subsequently authorized storage work order:

- Provider abstraction and `LocalOneDriveProvider`; startup checks the saved root/marker without a full scan.
- Settings Ã¢â€ â€™ Storage with a cancellable root setup wizard, local root persistence, marker validation, missing-folder creation, availability/index summaries, online/local opening, and refresh/rebuild/cancel controls.
- Authoritative shared settings in `.projecthub/project.json`, revision history, relative shared references, and legacy absolute-path migration into local profile overrides. The machine-generated index stays in the local profile.
- Metadata-only recursive indexing with exclusions, OneDrive placeholder flags, change comparison, persistent per-path file IDs, removal tombstones, raw-data modification flags, and atomic writes.
- Directory/explicit-metadata relationships, archive awareness, local aggregate storage activity, malformed-metadata warnings, and preserved last-known relationships.
- Project Ã¢â€ â€™ Files / Data with case-insensitive search, category/relationship/date/archive filters, file/folder opening, relative-path copying, and metadata inspection.
- Provider/schema documentation and a future ingest interface outline. No Microsoft login, Graph, OAuth, content search, data copying, or automatic file reorganization.

Verification: **83 tests run; 81 passed and 2 skipped**, plus the existing desktop smoke test, new storage acceptance smoke test, and source compilation. The acceptance smoke uses isolated temporary data and mocked file-opening calls. Storage and file-browser screenshots were reviewed.

The two skipped live filesystem-link tests could not create Windows symlinks/junctions under current permissions. The simulated name-surrogate boundary test verifies that redirecting paths are rejected while cloud reparse points remain indexable. A real cloud-only dataset was not hydrated or opened during validation; tests verify metadata-only handling and skipped cloud-only relationship JSON.

No real shared project root was selected automatically. Connect the actual library in Settings Ã¢â€ â€™ Storage. Live OneDrive sync state, production multi-user conflict handling, and packaged distribution remain outside this phase.

## Design language and UX

Applied the subsequently authorized design specification to all existing app surfaces. Added centralized theme tokens and reusable components, workspace navigation, responsive dashboard cards, grouped settings, software status groups, a simpler storage summary, sortable file results with persistent filters, loading/empty/error states, expandable technical details, personal update preferences and nonmodal notifications. Shared revision/restore confirmations and Teams/storage behavior are retained.

Visual review caught and corrected clipped dashboard cards at the minimum laptop size and partially hidden file-action buttons at the standard window size. Regression coverage verifies these layouts, correct file opening after sorting, filter preservation, errors and preference/confirmation behavior.

Verification: **101 tests run; 99 passed and 2 skipped**, plus desktop, storage and design-state smoke tests and source compilation. The same two Windows filesystem-link creation tests remain skipped under current permissions. Offscreen screenshots were reviewed at normal and 1024 Ãƒâ€” 700 sizes. Live screen-reader and high-DPI behavior have not been verified.

Future research entity editors, shared requests, AI and release installation remain future milestones. Existing datasets and the real shared library were not modified during this phase.

## GDL v209 integration

Integrated the supplied GDL package into the Hub's existing Python/PySide6 application. Preserved the original source and baseline hashes, all five Quick Run JSON files, Swift table and historical documentation. Added a managed engine manifest and narrowly scoped compatibility edits for paths, session transport, generic report destinations, watchdog identity/stop requests and BEAST worker launch paths. Processing, measurement, JSL and report-generation functions remain unchanged outside those explicit integration boundaries.

Added Project Ã¢â€ â€™ Analysis, Software Ã¢â€ â€™ Open analysis and Settings Ã¢â€ â€™ Analysis Tools. Every dependency/data/runtime path is editable. Fiji/JMP reuse the Software path registry; shared data folders use validated relative references and settings revision history. Sessions/status/logs are local, polling runs in background workers, and failures retain hidden technical details. Monitoring can be stopped cooperatively without force-killing Fiji; processing cancellation remains in the existing Fiji interface.

Added staged ZIP import, saved-source-folder version checking and engine rollback. Incomplete/unsafe/incompatible packages cannot replace the active engine. Default personal Quick Runs survive engine updates. The supplied ZIP was registered in this user's local GDL profile without changing existing path overrides; a read-only source check confirmed the installed v209 matches that ZIP.

Verification: **143 tests run; 141 passed and 2 skipped**, plus desktop, storage, design and GDL offscreen smoke tests and source compilation. Additional checks cover canonical executable paths, writable output, local/shared separation, original Quick Run loading, Swift profile/unit equivalence, unchanged algorithm functions, watchdog crash retry/session identity, BEAST worker transport, stale status rejection, reopened-session polling, output containment, ZIP traversal/incomplete package rejection, source update discovery and rollback. Standard and 1024 Ãƒâ€” 700 GDL screens were visually reviewed.

Fiji and JMP were found on this development machine through read-only detection. **No real Fiji/JMP analysis was launched**, following the user's explicit request. Live Quick Run completion, generated reports, scientific-output equivalence and real watchdog/UI interaction remain unverified. This is an implemented integration with offline validation, not a claim of completed live scientific acceptance. The original shared ZIP and project datasets were not modified.

See `gdl_analysis.md` for normal setup/updates and `gdl-integration-notes.md` for the original path inventory and baseline limits.

## Optional Graph storage and reduced-permission sign-in

Added editable local roots, portable folder mappings, metadata-only Graph browsing, current/legacy separation, classification overrides and offline cached indexes. Legacy source definitions retain permanent reference IDs and remain excluded from current work. Root and cache changes preserve source files.

Basic login requests only User.Read. Own OneDrive requests Files.Read only after its explicit connection action; SharePoint requests Sites.Read.All only after Connect SharePoint. No background refresh opens consent. Optional denial preserves the basic account and displays Admin approval required. Account and cloud panels show separate permission states. Local OneDrive / Files On-Demand and cached metadata remain available, with local fallback even from CloudOnly while cloud permissions are unavailable. Raw OAuth and Graph errors are sanitized, including expandable details.

The supplied Entra registration was changed to localhost Mobile/Desktop redirect with public client flows. Following the reduced-permission request, its configured API permission list was reduced to User.Read only. No university admin consent was granted. Tenant policy may still require approval for basic identity; successful live basic sign-in and real university cloud traversal have not been verified.

Verification: 185 tests run, 183 passed and 2 Windows filesystem-link tests skipped. After the final layout adjustment, all 11 Microsoft UI tests passed again. Source compilation passed. Permission-state UI was reviewed at 1200 Ã— 850 and 1024 Ã— 700 using a simulated account and isolated profile. No Fiji/JMP analysis launched.

The rebuilt Windows onedir package at `dist/windows-basic-login/FuelCellProjectHub` passed its isolated packaged startup check, including MSAL import, all settings tabs, local-root editing, GDL manifest presence and Windows DPAPI round trip. Packaging excludes an incompatible runtime ICU DLL so Qt uses the Windows ICU provider. The prior package under `dist/FuelCellProjectHub` is obsolete; use the rebuilt directory. This verifies package startup, not live university sign-in or cloud indexing.

## GitHub source control and application branding — October 7, 2026

Connected the existing local source to MartParty079/GDL main while preserving
remote history and every working file. The Git root follows the existing remote
layout: repository README plus fuel-cell-project-hub. Added standing AGENTS.md
and CODEX_WORKFLOW.md instructions for pull/test/review/commit/push/verify.

Added source-publication audit and ignore rules for credentials, local profiles,
indexes, runtime, builds and datasets. Removed old compiled caches from tracking
without deleting their working files. Private original GDL baseline remains
ignored locally; the portable managed engine and hash ledger are tracked.
A sanitized legacy source fixture makes public package tests reproducible.
Three comparisons against the privately held original are explicitly skipped
when it is absent. Git attributes preserve engine and fixture bytes/formatting.

Added generated PNG branding and seven-size Windows ICO. QApplication,
HubWindow and PyInstaller share the central resource resolver. Windows startup
sets the desktop taskbar identity. Icon generation prompt is recorded in
assets/README.md. No installer or About dialog exists yet.

Verification: local suite 189 run, 187 passed, 2 Windows filesystem-link skips.
Published-source-only suite 189 run, 184 passed, 5 expected skips (the same two
plus three private-baseline comparisons). Desktop and GDL offscreen smokes
passed. Staged publication audit and whitespace checks passed. The final branded
Windows package passed isolated startup, DPAPI round trip and app/window icon
loading. The executable contains icon resources; package-update adapter is
bundled and the private baseline excluded. No Fiji/JMP analysis launched.

The validated local package is dist/windows-branded-complete/FuelCellProjectHub.
Generated builds stay outside Git. Source publication is separate from a GitHub
Release and does not update installed apps automatically.
