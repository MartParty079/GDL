# Technical Framework - Fuel Cell Project Hub

**Audience:** Codex / Claude Code / developers

## Principle
Build a thin orchestration layer. Do not recreate GitHub, SharePoint, Teams, Discord, Office, or engineering applications. Own discovery, launching, config, status, metadata, updates, and indexes.

## Suggested V0.1 stack
- Python + PySide6
- PyInstaller
- JSON shared configuration/indexes
- Local per-user JSON under AppData for executable paths
- GitHub for source, scripts, releases
- SharePoint/OneDrive for project files and large data

## Repository layout
```text
fuel-cell-project-hub/
├── app/
│   ├── main.py
│   ├── ui/
│   ├── services/
│   └── models/
├── config/
│   ├── software_manifest.json
│   ├── project_defaults.json
│   └── links.json
├── scripts/
│   ├── imaging/
│   ├── analysis/
│   ├── jsl/
│   ├── excel_word_generation/
│   └── utilities/
├── docs/
├── tests/
└── build/release tooling
```

## Critical config rule
Never hard-code application paths. Shared config describes software; local config stores the resolved executable path for each user.

## Startup flow
1. Load shared and local config.
2. Scan required software.
3. If missing, show setup helper.
4. Quick install where reliable.
5. Manual links for licensed/manual tools.
6. Re-scan.
7. Locate Application fallback.
8. Validate and store path locally.
9. Continue with warning if incomplete.

## Navigation
Top: Dashboard | Activity | Software | Project | Bugs | Settings.
Future dashboard workspace can show left project sidebar for Samples / Experiments / Procedures. Home returns to overview in V0.1.

## Updates
- Lightweight GitHub version check at startup.
- Notify, never auto-download.
- Checklist of updates, checked by default.
- Update Checked action.
- Keep previous version for rollback.
- Prefer approved releases/tags over raw main.

## Settings
- Personal: paths/local preferences/setup state.
- Project: software lifecycle, links, automation toggles, dashboard behavior.
- Team-wide changes require Apply + confirmation.
- Project setting versions are restorable.

## Future data model
```text
Sample
  permanent_id
  display_name
  aliases[]
  material/manufacturer/specs/thickness
  origin_state: new|used
  current_state
  experiment_links[]
  append_only_log[]

Procedure
  permanent_id
  display_name
  version
  state: planned|draft|active|retired
  structured_steps[]
  suggestion_log[]

Experiment
  permanent_id
  display_name
  sample_id
  procedure_id + version
  status: planned|ready|running|data_collected|analyzed|complete
  reviewed: bool
  run_ids[]
  edit_log[]

Run
  id: <experiment_id>-R01
  run_number
  stage gates
  parameters/overrides
  deviation_notes
  failure_or_issue_note
  file_links
```

## Storage layout
```text
Project Root
├── 00_Project_Admin
├── 01_References
├── 02_Design
├── 03_Experiments
│   └── E-...
│       ├── metadata.json
│       ├── procedure_reference.json
│       ├── runs/R01/{pre_imaging,test_data,video,post_imaging,notes}
│       └── results
├── 04_Reports
├── 05_Procurement
├── 06_AI_Context
├── 07_Exports
└── 99_Archive
```
Store files once and generate alternate views from indexes.

## Guardrails for coding agents
- Do not expand V0.1 into a LIMS.
- No hard-coded usernames, paths, or credentials.
- No secrets in Git.
- Separate shared state from per-user state.
- IDs define relationships; display names are presentation only.
- Never put large raw data in GitHub.
- Preserve IDs and audit history across schema migrations.
- Use toggles for later automations.

## Build order
1. Shell/navigation
2. Manifest + local config
3. Detection/launcher
4. Setup helper
5. Dashboard
6. GitHub update checker
7. Settings/version history
8. Bug reporting
9. Activity/requests
10. Package and test V0.1
11. Then multi-user + project-data modules
