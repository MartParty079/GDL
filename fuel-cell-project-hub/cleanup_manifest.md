# Research Hub cleanup manifest

Audit performed before refactoring. The repository already has one application
entry point (`app/main.py`, invoked by `Start Hub.cmd`) and separate services,
UI, tests, portable configuration, assets and build tooling. No obsolete
`main_old`, `final_final` or abandoned alternate application was found.

| Original location | Destination | Reason | Action |
|---|---|---|---|
| app/services, app/ui | Same | Working launch, authentication, analysis and project functions | Keep; refactor storage integration |
| Local index/file_index.json and cloud/legacy JSON caches | Local SQLite research catalog | One searchable catalog; preserve original provider snapshots | Migrate with backup; keep provider snapshots as transport/offline caches |
| config/project.json and config/history | Local AppData project settings/history | Runtime settings must not modify installed source | Refactor writes; retain older files as migration inputs |
| config/*_defaults.json, software_manifest.json | Same | Portable templates | Keep |
| analysis/gdl/engine | Same | Managed scientific analysis source | Keep |
| tests/fixtures/gdl_legacy_v209 | Same | Intentional legacy duplicate used for package migration regression tests | Keep |
| analysis/gdl/baseline | Same, ignored | Original private scientific baseline with personal paths | Keep local; do not publish |
| .venv, build, dist, .test-state, __pycache__ | Same, ignored | Generated environments, builds and test state | Generated / ignore |
| Research OneDrive folders | Same external locations | Current data and historical reference data | Read-only index; no moves, markers or deletions |
| Personal profiles, Graph authentication caches | Local AppData, ignored | Credentials and machine configuration | Keep private |
| Historical engine Documentation | Same | Scientific change history | Keep; not application prototypes |

No source files or research files need moving or deleting. Database/cache
contents are inspected and imported defensively; unknown/corrupt inputs are
preserved and reported rather than overwritten. New catalog migrations make
database backups. Unavailable records are retained for reconnection.
