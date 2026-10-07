# Product Requirements Document - Fuel Cell Project Hub

**Date:** October 6, 2026

## Product summary
A lightweight Windows desktop hub for launching software, scripts, repositories, shared storage, and collaboration tools used by the fuel-cell capstone team. It starts as a single-machine launcher/dashboard and grows into a project operations layer.

## Goals
- One unified place to start project work.
- Reduce setup/path friction.
- Keep goals, plan, agenda, and major changes visible.
- Centralize links to GitHub, SharePoint/OneDrive, Teams, Discord, reports, and active work.
- Preserve traceability and future handoff.

## V0.1 requirements
- Unified launcher.
- Installed/missing software detection; path/version where easy.
- First-run setup with auto-scan, install links, manual path selection, and re-scan.
- Dashboard cards: goals, plan, agenda, major changes, software summary, project shortcuts.
- Project access: main GitHub repo button + useful sublinks.
- Settings with team-wide confirmation and version history/restore.
- GitHub app/script update check at startup; notify only; selectable updates; rollback.
- Bug reports with automatic context capture.

## V0.1 non-goals
AI integration, advanced graphs, full sample/experiment/procedure management, custom chat/storage, automatic report writing in the core app, mandatory Microsoft login, and guaranteed multi-user deployment.

## Software lifecycle
Required | Optional | Retired. Retired software keeps historical installer/version/license info and can be reactivated as Optional.

## Activity / Requests
- Whole-project chronological feed.
- Filter by Update/Request, area, and person.
- Request status: Open | Accepted | Rejected | Completed.
- Mention popups are dismissible.
- No discussion threads; use Discord/Teams.

## Bugs
Open | Investigating | Fixed | Closed. Auto-capture app/script version, user/profile, timestamp, and context. Project lead decides whether to promote to GitHub.

## Future entities
### Sample
Permanent ID, editable display name/aliases, manufacturer/material/specs/thickness, new/used origin, current state, experiment links, append-only history.

### Procedure
Permanent ID + display name, versioned structured steps, states Planned/Draft | Active | Retired. Suggestions allowed on active procedures; procedure engineer owns official revisions.

### Experiment
Permanent ID + display name, one sample, selected procedure version, multiple runs. Status: Planned | Ready | Running | Data Collected | Analyzed | Complete, plus Reviewed checkbox.

### Run
`<experiment_id>-R01`, etc. Keep failed runs. Free-text failure/issue note initially.

## Procedure rules
- New experiments default to latest active procedure.
- Old experiments remain pinned to original version.
- Reassigning an old experiment requires reason, user, timestamp, audit entry.
- Stage-gate confirmations, not every micro-step.
- Deviations are documented and may proceed.

## Storage/index rules
- GitHub: code/scripts/releases.
- SharePoint/OneDrive: project files, large data, images/video, reports, archive.
- Store once by experiment; use indexes for alternate views.
- JSON indexes first; SQLite later if needed.
- Sample/experiment logs append-only.
- File recovery uses SharePoint/OneDrive version history; app logs who/when/why edits occurred.

## ID pattern
- `P-YYYYMMDD-X` procedure
- `E-YYYYMMDD-X` experiment
- `S-YYYYMMDD-X` sample
- `<experiment_id>-R01` run

Display names are editable; IDs never change. Legacy names can be aliases.

## Roadmap
- **V0.1:** single-machine launcher/dashboard/setup/update/bugs/settings.
- **V0.2:** reliable four-person deployment, profiles/Microsoft login/shared state.
- **V0.3:** samples/procedures/experiments/runs/activity/audit/indexes.
- **Later:** report/analysis scripts, Teams integration, automation, export/handoff, optional AI, SQLite migration.
