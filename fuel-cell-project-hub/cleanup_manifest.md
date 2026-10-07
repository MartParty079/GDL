# Research Hub cleanup manifest

## Native indexing work order — audit before removal

| Original location | Destination | Reason | Action |
|---|---|---|---|
| app/services/microsoft_auth.py, microsoft_graph.py, microsoft_graph_provider.py | Git history | Authentication and remote enumeration intentionally retired | REMOVE |
| app/ui/microsoft_panels.py | Git history; local folder mapping moved into storage panels | Remove login/cloud screens; retain useful local mappings | REMOVE / REFACTOR |
| config/microsoft_auth.json; tools/configure_microsoft_registration.py | Git history | No registration, permissions or sign-in required | REMOVE |
| tests/test_graph_storage.py, test_microsoft_ui.py | Git history | Retired feature tests; replace with native/offline acceptance tests | REMOVE |
| requirements.txt; packaging spec and startup self-check | Same | Remove MSAL; bundle local parsers and test native operation | REFACTOR |
| app/services/research_catalog.py | project_locations.py plus app/indexing | Preserve configuration and safe file operations; replace RAM-wide scans/search with streaming SQLite/FTS service | REFACTOR |
| Existing SQLite v2 index and personal configuration | Configured local backup directory | Preserve data before v3 migration and obsolete-setting retirement | KEEP / MIGRATE |
| Personal auth directory | Inspected empty; removed empty directory after configuration backup | No active token cache; do not alter other software's credentials | REVIEW / REMOVE |
| docs/reference, old feature documentation and permission screenshots | Git history / clearly historical reference | Prior work remains recoverable; current README describes native system | ARCHIVE / REFACTOR |
| Research sources, scientific engine, user reports | Same | Protected experimental data and working scientific functionality | KEEP |

The prior 172,283-record catalog was migrated in place to schema v3 with a
SQLite backup. The native architecture reuses that database, without creating
a second competing index. Research source directories remain read-only during
scanning, content extraction and search.

## Completed native cleanup

- Retained unchanged: 153 tracked application files, including managed analysis,
  sanitized scientific fixtures, portable resources and historical work orders.
- Refactored: 26 existing tracked files.
- Added: 12 native service, configuration, UI, test and architecture files.
- Removed: 12 obsolete authentication/Graph implementation, tests, registration
  artifacts, guides and permission screenshots; recoverable in Git history.
- No additional prototype archive was needed; no experimental data was moved.
- Removed dependencies: MSAL and msal-extensions. Added bounded local parsers.
- Preserved the private original GDL baseline locally and ignored.
- Migrated 172,283 catalog records with backup. Read-only source verification found
  zero size/mtime changes. One corrupt resident JPEG was retained as metadata.

## Historical earlier cleanup audit (superseded)

Audit performed before the previous refactor. The repository already has one application
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
