# Fuel Cell Project Hub - Development Reference

## North Star
One unified desktop app that the team opens first. It launches the tools, shows current project state, and points to the right files/repositories without becoming another storage silo.

## V0.1
- Windows desktop app on project lead machine
- Dashboard | Activity | Software | Project | Bugs | Settings
- Clean dashboard cards
- Required software detection/setup
- Launch all core tools
- GitHub update notification + selective updates + rollback
- Bug reports
- Settings + history

## Not yet
AI, full experiment tracking, advanced graphs, complex roles, custom storage/chat, SQLite.

## Future rules
- Permanent IDs, editable display names.
- P = Procedure, E = Experiment, S = Sample.
- Runs = experiment ID + R01/R02.
- One sample per experiment, multiple runs.
- Samples may be used in multiple experiments.
- Procedures are versioned and experiments pin a version.
- Audit logs append-only.
- Store files once by experiment; filter with JSON indexes.

## Status values
- Software: Required | Optional | Retired
- Experiment: Planned | Ready | Running | Data Collected | Analyzed | Complete + Reviewed
- Procedure: Planned/Draft | Active | Retired
- Request: Open | Accepted | Rejected | Completed
- Bug: Open | Investigating | Fixed | Closed

## Architecture
```text
Desktop Hub
  ├── local user config
  ├── shared JSON config/indexes
  ├── GitHub
  ├── SharePoint/OneDrive
  ├── Teams
  └── Discord
```

## Releases
- V0.1: single-machine launcher/dashboard/setup/update/bugs
- V0.2: four-person deployment + profiles/login/shared state
- V0.3: samples/procedures/experiments/runs/activity/audit

## Scope check
If a feature does not improve launching, locating, organizing, or tracing project work, it probably belongs in another tool or a later release.
