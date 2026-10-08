Current schema v4 preserves this native index and adds the
[research workspace and explicit object links](research_workspace.md).

# Native GDL research indexing

Microsoft authentication and Graph are intentionally removed. Normal operation
requires neither sign-in nor an internet connection. OneDrive owns cloud storage
and synchronization; Windows exposes local filesystem entries; the Hub owns
metadata, classification, relationships, indexing and search.

## Final architecture

```text
fuel-cell-project-hub/
  app/main.py                       single application entry
  app/indexing/
    scanner.py                      recursive streaming directory discovery
    extractor.py                    bounded resident content and image metadata
    hashing.py                      guarded resident SHA-256
    search.py                       safe prefix queries and SQL filters
    watcher.py                      optional Qt watches and periodic reconciliation
    index_manager.py                schema migration, jobs, metadata, FTS and backups
  app/services/
    project_locations.py            authoritative personal roots and stable projects
    file_classifier.py              extension, path and explicit/manual classification
    research_catalog.py             compatibility facade to the one native index
    storage_settings.py             native configuration and local library adapter
    storage.py                      personal/project JSON persistence and activity
    project_storage.py              optional explicitly managed shared library
    gdl_*.py, path_registry.py       preserved scientific analysis and update tools
  app/ui/
    research_panel.py                roots, indexing, extraction limits, backups/history
    folder_mappings.py              portable local project folder mappings
    storage_panels.py               SQL-paged files, filters, metadata and relationships
    window.py                       dashboard and application integration
  config/indexing_rules.json         portable keyword-to-category defaults
  config/research_defaults.json      portable source folder/name defaults
  analysis/gdl/engine/               preserved managed scientific source
  tests/test_native_index.py         parser, FTS, offline, watcher and incremental tests
  tools/index_research.py            read-only real-source validation
  tools/smoke_research.py            offscreen personal-profile acceptance
  tools/desktop_entry.py             isolated packaged parser/startup self-check
  docs/, assets/, requirements.txt, cleanup_manifest.md
```

The private original scientific baseline, personal profiles, datasets, caches,
backups, logs and builds remain ignored. No second index competes with SQLite:
the old research_catalog import is only a compatibility facade.

## Configuration and research boundaries

ProjectLocations centralizes active, legacy and additional active/reference/archive
sources, shared storage and application-owned database/generated/cache/backups
paths. Personal configuration lives under Local AppData/FuelCellProjectHub, or
FUEL_HUB_DATA_DIR. Typed environment variables are expanded; source roots must
be absolute, direct and non-overlapping. Application-owned folders must be
separate and outside research sources. Source removal hides its records without
deleting its files or historical index entries. Changing projects preserves IDs
and supports selecting the previous project again.

Default current project: GDL Research, folder GDL research - General. Default
legacy project: Previous GDL Research, source Michelson GDL Stuffs, folder
Michelson, Andrew's files - GDL Stuffs. Legacy remains old_test_data/read_only.
Sources receive stable UUIDs and files have internal IDs plus source/path,
size/mtime, inode and optional hash. Resident rename matching uses filesystem
identity when unambiguous. Hash/name/size/time warnings identify potential copies;
they never merge identities or remove data.

Indexing, extraction and search never write research files, create source markers,
execute scripts, evaluate formulas or download cloud content. Import into Current
Project is a separately confirmed exclusive COPY preserving the legacy original.
Folder mapping and manual metadata edits affect application settings/catalog only.
Existing software launchers, Teams URI handling and managed GDL updates remain.
No live Fiji or JMP run is part of this validation.

## SQLite persistence and migrations

The native file-index schema introduced in v3 extends the existing v2 database and retains its
files/metadata/overrides tables and stable IDs. New normalized search/filter
metadata, projects, sources, directories, content_index, FTS5 content_fts,
fts_keys, relationships, index_runs and index_errors provide local indexing.
fts_keys gives each search document a stable rowid for efficient replacements.
The legacy JSON snapshots are preserved privately; they are no longer active
cloud providers or competing native indexes. Removed source/remote snapshots are
not silently relabeled current.

Older schema migration backs up through SQLite's backup API before alteration.
Invalid/newer databases are preserved with an unavailable-index state while the
rest of the app remains usable. Rebuild, search regeneration, relocation and
restore back up first. Relocation refuses another existing catalog. Restore
accepts compatible integrity-checked backups inside the configured backup folder.
Manual overrides and relationships survive scans/rebuilds and backup restoration.

Scans stream filesystem entries, look up known paths in SQL, process bounded
batches and commit every 250 files. They do not build a list of every file or
load document text into UI memory. New/changed/moved/unchanged/missing/unavailable
counts and run errors are persisted. Missing records are retained; inaccessible
subtrees retain unavailable references. Reconciliation happens only after a
source scan completes. Cancellation preserves completed batches and rolls back
the unfinished batch; another refresh reconciles remaining work.

## Index modes, search and metadata

Quick Refresh walks metadata and extracts only changed/newly resident documents
or files whose extraction options changed. Full Scan walks configured sources
and also fills missing small resident hashes within budget. Rebuild Entire Index
intentionally reparses files with a prior backup, retaining manual metadata,
relationships and unavailable history. Rebuild Search Index regenerates FTS from
saved text/metadata without opening research files. Index Selected Folder limits
reconciliation to that subtree. No startup full scan/rebuild occurs. Optional
automatic startup and periodic reconciliation use quick refresh of current roots.

FTS5 searches name, title, tags, category, project/source, relative path, saved
text and manual notes/description. User text becomes quoted prefix tokens joined
with AND; SQL filters are parameterized. Ranking prefers filename exact/substring
matches and weighted relevance, with current research as a tie preference.
Current/legacy/all, project/source, category, type, extension, modified dates,
availability, folder, tags and duplicate filters are supported. Database counts
and LIMIT/OFFSET fetch 200 rows per GUI page. Qt sorting applies within the page
only and is disabled during ranked search. Metadata shows content status,
extracted attributes, a bounded 5,000-character preview and relationships.

Manual category/tags/title/description/notes/favorite edits persist separately and
win over automatic classification. Default keyword rules are editable under
Advanced; rebuild content to apply changed rules to unchanged files. Relationships
include derived_from, related_to, supersedes, previous_version and references.
Find related permits adding relationships to explicitly selected indexed files.

## Extraction limits and availability

| Format | Local extraction |
|---|---|
| TXT/MD/CSV/JSON/Python/MATLAB/XML/YAML and supported script/log text | UTF-8/UTF-16 bounded text; binary content rejected |
| PDF | Title, page count and available text; no rendering; image-only marked OCR required |
| DOCX | Title, paragraphs and bounded table cells |
| XLSX | Workbook/sheet names, used dimensions, bounded headers/labels/text; read-only; formulas/numeric arrays skipped |
| PPTX | Title, slide count and bounded text frames |
| JPG/PNG/TIFF/BMP/GIF | Header dimensions/format; no pixel decoding |
| CAD/proprietary/unknown binaries | Filename, path, type, size/timestamps and source metadata |

Defaults: 16 MB content file size, 200,000 extracted characters, 100 PDF
pages/slides, 2,000 spreadsheet/table cells and 32 MB expanded OOXML/PDF stream
limit. Images use header reads even when pixel data exceeds the content-file
limit. Settings expose common limits and extraction enable/disable. Changing
options reprocesses affected files on their next scan. SHA-256 is limited to
resident files <=1 MB and 32 MB per run; unchanged hashes are reused.

Placeholder detection checks Windows offline/recall attributes before opening
content and again inside extraction/hashing. Online-only entries receive
metadata only; newly resident files become extractable on refresh. Parser failure
records a friendly per-file error and continues the scan. Oversized documents are
marked Partial with the reason; unsupported content retains searchable metadata.
Concurrent size/mtime changes are marked Still syncing and retried on refresh.

Qt directory watching is optional and capped at 512 directories. Events are
debounced; periodic scans recover content changes, deeper folders, missed events
and Windows watch limitations. Watching cannot guarantee every content modification
produces an immediate directory event; the reconciliation interval is authoritative.
Indexing runs on a worker thread. History and structured cache/logs/native-index.jsonl
report jobs, errors, sources and counts; they contain no authentication credentials.

## Removed components and cleanup

Removed microsoft_auth.py, microsoft_graph.py, microsoft_graph_provider.py,
microsoft_panels.py, microsoft_auth.json, configure_microsoft_registration.py,
retired Graph/account tests, obsolete login/import guides and permission screenshots. Removed MSAL and
msal-extensions from dependencies and the development environment; packaging
explicitly excludes them. Useful local folder mappings moved to folder_mappings.py.
Login/cloud panels, account state, permission tiers, token cache usage and Graph
provider selection are absent. Prior implementations remain in Git history;
reference work orders and prior BUILD_STATUS entries are labeled historical.

The feature-owned auth directory was inspected and empty before removal. Personal
configuration was backed up before retiring cloud/account keys; unrelated settings
and credentials were retained. Existing schema v2 records were migrated in place
with a backup. The pre-removal audit and dispositions are in cleanup_manifest.md.

## Remaining limits

The index cannot see cloud files Windows does not expose, replace OneDrive sync,
grant SharePoint permissions, access another user's private cloud files or report
true remote sync completion. Online-only content is not searchable until resident.
Proprietary formats, old DOC/XLS/PPT, encrypted documents and scanned PDFs may
need external tools/OCR. Large documents are intentionally partial; parsers are
bounded by input/text/page/archive limits but are not a process-isolated parser
sandbox. Compressed PDF decompression can transiently exceed the final text cap.
A corrupt parser input records an error rather than aborting the index.

Hash budgets leave large files with provisional duplicate warnings. Cross-volume
moves may be represented as missing plus new files; potential-copy warnings do
not prove identity. Watching is bounded and periodic reconciliation repairs missed
events. SQLite is an application-owned local database, not a shared multi-user
synchronization engine. First migration may take time on a large prior catalog;
normal startup uses the migrated index and never rebuilds it. Backup/restore are
explicit maintenance actions and may take time for a large index. Source pushes
are not releases and do not update previously installed applications.

## Real-source validation, 2026-10-07

The existing 172,283-record index migrated with a SQLite backup, retaining IDs
and manual overrides. Current was scanned first, then legacy, with before/after
size/mtime inventories of both roots. No source files changed; inventory errors
were zero and legacy remained read-only/old_test_data.

| Metric | Result |
|---|---:|
| Current discovered / indexed | 5 / 5 |
| Legacy discovered / indexed | 172,278 / 172,278 |
| Content-indexed documents | 94 (93 complete, 1 partial) |
| Metadata-only entries | 172,189 |
| Online-only entries | 172,181 |
| Image-header metadata | 3 |
| Resident unsupported files | 4 |
| Duplicate warnings | 114,497 |
| Current scan errors | 0 |
| Legacy scan errors | 1 |
| Source metadata changes | 0 |

The single error is a resident JPEG with an invalid, UTF-8-reencoded JPEG header.
Pillow correctly reports UnidentifiedImageError. Its metadata remains searchable;
its original was not repaired, replaced or removed. The legacy validation command
returned exit code 1 to report Completed with Errors, rather than claiming an
error-free scan. The native service continued through every remaining file.

All requested searches were exercised separately against current and legacy:

| Query | Current matches | Legacy matches |
|---|---:|---:|
| GDL | 5 | 172,278 |
| microscopy | 0 | 0 |
| pore diameter | 0 | 8 |
| equivalent pore diameter | 0 | 0 |
| porosity | 0 | 5 |
| roundness | 0 | 4,130 |
| solidity | 0 | 8 |
| fiber diameter | 0 | 1 |
| water intrusion | 0 | 0 |
| compression | 0 | 3 |
| pressure film | 0 | 0 |
| ASTM | 0 | 0 |
| ImageJ | 0 | 11,521 |
| laser | 0 | 2 |
| Python | 0 | 11,288 |
| syringe | 0 | 0 |

These are filename/metadata plus available saved text matches, not a claim that
online-only document contents were searched. A zero count does not establish
that a term is absent from cloud-only content. GDL matches include project/source
metadata. Duplicate warnings are mostly filename collisions across historical
folders, not proof that 114,497 files can be removed.

Real-catalog SQL checks loaded <=200 result rows per page. Measured local calls:
summary 1.03 s, distinct filter values 3.45 s, legacy page 0.77 s, ranked GDL search
1.06 s. Personal-profile offscreen smoke passed all six pages and current/legacy/
combined counts in 25.1 s, including repeated rendering and screenshot capture;
this is not a single startup-time measurement. No external applications launched.

The app-owned personal configuration was backed up before retirement. The empty
feature auth folder was removed, obsolete account/cloud keys were removed, and
other settings remained. Managed analysis source was unchanged. No authentication
repair, university permission change or cloud API call was performed.

## Final verification and package

Full unittest suite: 185 run, 183 passed, two existing Windows filesystem-link
skips. Native fixtures cover parsers, safe ranked FTS, manual overrides, SQL
pagination, relationships, offline startup, no placeholder reads, changed options,
search-only regeneration, backup/restore, cancellation with committed batches,
additional source types, unavailable logs and watch debounce/reconciliation.

The final Windows onedir build at dist/windows-native-complete/FuelCellProjectHub
passed its isolated packaged startup and all local-parser fixture checks. It has
seven settings groups, default current research, working branding, native content
search and no authentication client. Retired modules, registration configuration
and managed-engine bytecode caches are excluded. The portable startup report is
[packaged-startup-check.json](packaged-startup-check.json). No Fiji/JMP launched.
Keep the entire onedir folder with its executable. Earlier package directories
are obsolete. This is a local validated package, not a published GitHub Release.

An attempted overwrite of an earlier generated build hit Windows access denial
on a generated cache directory. The final build used a fresh output directory
and excludes those engine caches; its build and self-check succeeded.

The staged source publication audit and final whitespace review passed; only
application source, portable assets/templates, tests and documentation are published.
