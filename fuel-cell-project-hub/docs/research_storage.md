# Research storage and cleanup

## Architecture and repository

```text
Capstone/
  AGENTS.md, README.md, .gitignore, .gitattributes
  fuel-cell-project-hub/
    app/main.py                    application entry point
    app/services/
      research_catalog.py          personal locations, projects, SQLite, read-only indexing
      storage_settings.py          storage orchestration and provider adapters
      storage.py                   personal/project persistence and activity
      project_storage.py           explicit shared-library provider
      microsoft_*.py               optional delegated Microsoft access
      gdl_*.py, path_registry.py    managed analysis, updates and launch configuration
    app/ui/                        research settings, files, dashboard and existing tools
    config/                        portable defaults and manifests
    analysis/gdl/engine/           managed scientific source
    analysis/gdl/baseline/         private original, ignored
    assets/                        shared icon and branding
    tests/                         isolated fixture tests; no destructive real-source tests
    tools/                         audit, build, index and offscreen validation
    docs/, cleanup_manifest.md
    .venv/, build/, dist/, .test-state/  generated and ignored
```

No obsolete application entry points required archiving. Scientific engine
history and intentional migration fixtures remain in place. See
`cleanup_manifest.md` for the pre-refactor audit and dispositions. Source code
and research datasets were not moved or deleted.

`ProjectLocations` is the authority for active project, multiple legacy sources,
shared storage, catalog, generated output, temporary/cache and backups. Portable
folder/name defaults are in `config/research_defaults.json`; machine values are
under `local.json > project_locations` in the personal data directory. The data
directory is Local AppData/FuelCellProjectHub, or an explicitly supplied
`FUEL_HUB_DATA_DIR`. Projects have stable IDs, names, roots, type, created date
and active state. Changing roots creates a new project, retaining previous
records; the GUI can select a previous project again. A remapped source retains
its identity when selected explicitly.

`ResearchCatalog` owns the combined SQLite index. Providers retain their JSON
transport/offline snapshots; they are imported with backups, never blindly
deleted. Unmatched snapshots are retained without mislabeling another project
as current. Existing local cache migration maps the previous root to its
configured current/legacy source. Subsequent provider refreshes are ingested
through StorageSettings. Offline records remain available. SQLite migrations
back up an existing older schema; newer schemas and corrupt databases are
preserved with a friendly unavailable state. Rebuild and catalog relocation
also back up first. Relocation refuses to overwrite another catalog.

File metadata includes stable ID, full/relative paths, extension/document type,
size, created/modified/index times, source/project, research category,
subcategory, tags/title/notes, resident hash where practical, parent folder,
availability, dataset status and read-only state. File IDs survive detected
renames/moves inside a source using filesystem identity. An unavailable inode
falls back to a source-specific relative-path ID; names alone are never IDs.
Manual metadata is a separate table and wins over inference and rebuilds.

## Safe indexing and duplicates

Recursive scanning uses directory metadata, excludes application/cache/source
control internals and refuses filesystem redirects. It never writes markers,
reorganizes directories or copies datasets. Scans compare size/mtime and avoid
unchanged hashing. Full scans hash resident files up to 1 MB, within 32 MB per
run; Quick Refresh never opens contents. Online-only attributes are checked
before reads. OneDrive remains responsible for availability and sync. Missing,
deleted/moved and inaccessible references remain visible; explicit opens show
“File currently unavailable locally” when content is missing or online-only.

Exact duplicate means matching SHA-256; likely duplicate means matching name,
size and modified date without confirmed matching hashes. Same filename /
different contents means differing sizes or known differing hashes. Warnings
count affected files, not unique duplicate groups or reclaimable bytes. There
is no automatic deletion. Partial hash coverage is intentional.

Legacy sources always carry `source_type=legacy`, `dataset_status=old_test_data`
and `read_only=true`. The current source uses `source_type=active` and
`dataset_status=current`. The explicit import action is copy-only, validates
source/target containment, refuses online-only contents, avoids collisions and
never changes the legacy original. Script opening is blocked; inspect code
through its containing folder instead.

Index workers report scanned/new/updated/unchanged/current/legacy/duplicate/
unsupported/error/unavailable counts. Cancellation before commit preserves the
previous catalog. Structured JSONL logs under cache/logs record startup,
migrations, project selection, index start/completion/cancellation/failure,
missing-reference counts and metadata changes, without Graph tokens or raw
authentication responses. Microsoft sign-in is independent; User.Read basic
login does not request Sites.Read.All. Files.Read and SharePoint indexing remain
explicit opt-ins, with friendly admin-approval states and local fallback.

## Real validation on October 7, 2026

Both configured real sources were readable. The previous local cache had
incorrectly presented Michelson as current; its 172,278 records were backed up
and migrated into the legacy source without changing the external marker.

| Result | Count |
|---|---:|
| Current files | 5 |
| Legacy files | 172,278 |
| Combined searchable files | 172,283 |
| Files with duplicate warnings | 114,497 |
| Matching-hash files | 8 |
| Likely-duplicate files | 1,040 |
| Same-name files with differing size/hash evidence | 113,449 |
| Unsupported content types (metadata indexed) | 19,904 |
| Indexing errors | 0 |
| Unavailable references in this run | 0 |
| Changes in before/after file size + modification-time inventory | 0 |

The migration scan found 5 new files and updated 172,278 records to the new
schema/source metadata. Current-only, legacy-only and combined search counts
were checked, and every locally indexed legacy record had the required status.
Read-only before/after inventories had zero inventory errors in both sources.
An offscreen real-profile smoke exercised all six application pages and laptop
layouts with 200-row pagination. No Fiji or external application was launched.
Private path-level validation results are stored in the personal data directory
as `research-validation.json`, not committed to Git.

The complete regression suite ran 214 tests: 212 passed and two existing
Windows filesystem-link tests were explicitly skipped. New tests cover personal
configuration, missing paths, project changes, current/legacy migration,
hashing, duplicates, incremental updates, rename identity, manual overrides,
database backup/relocation, unavailable OneDrive files, corrupt records,
copy-only import, protected research roots, background indexing and pagination.
Python compilation and whitespace checks passed.

## Running and rebuilding

Install and launch using the README's virtual-environment instructions or
`Start Hub.cmd`. Save locations in Settings > Storage. Use Index Everything
initially; Quick Refresh for metadata changes; Rebuild Index for reclassification
and resident rehashing. Rebuild retains source records and manual metadata and
backs up first. Index Selected Folder scans a current-project subfolder without
marking other folders missing. Files remain at their source locations.

For a read-only command-line validation after configuration:

```powershell
.\.venv\Scripts\python.exe tools/index_research.py --verify-sources
.\.venv\Scripts\python.exe tools/smoke_research.py
```

The optional CLI `--configure-defaults`, `--active-root` and `--legacy-root`
change personal configuration and back up the previous profile. Never run
configuration options accidentally against a different user's profile.
Unit/UI tests use temporary directories. Source publication follows
`docs/CODEX_WORKFLOW.md`: tests, applicable smoke checks, explicit staging,
source audit, normal commit/push to main and SHA verification. Source pushes
do not update installed packages or create a release.

## Remaining technical debt

- Graph JSON snapshots remain transport caches for existing providers; SQLite
  is the combined catalog. Graph delta refresh and SQL-native paginated search
  remain future work. Results are paginated in Qt while metadata search uses
  an in-memory catalog, so very large libraries still have an initial load cost.
- Hashes cover bounded small resident files. Large/online-only research files
  need an explicit future hashing workflow for exhaustive duplicate verification.
- Filesystem identity may change after OneDrive resync or cross-source moves;
  references then receive new source/path IDs and old records remain visible.
- Categories are conservative path/extension inference with manual overrides;
  there is no PDF text extraction, semantic content search or automated sync-state
  measurement. Unsupported extensions are metadata references, not parsed data.
- Existing team settings, shared-library initialization and cloud setup are
  retained under their existing settings groups. The research section is coherent
  without rewriting working launch/authentication/scientific functions.
- Explicit analysis path overrides retain priority. Default research output
  and reports use application-owned generated storage, with temporary work in
  the configured cache. Review older overrides before launching scientific work.
- No installer, new release or live Fiji scientific run is part of this cleanup.
