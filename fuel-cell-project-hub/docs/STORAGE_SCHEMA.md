# Storage schema and architecture

## Ownership

SharePoint/Teams document library → OneDrive sync → local synced root → `LocalOneDriveProvider` → metadata index/search/UI.

The library owns all data files. The hub owns lightweight metadata, relationships, project configuration, launching, and local caches. No data files are copied into the app. All shared file references are normalized forward-slash relative paths. Absolute paths, executable paths, and caches are machine-local.

## Provider contract

`ProjectStorageProvider` defines listing, item lookup, opening files/folders, existence, refresh/rebuild, availability, folder validation/creation, shared project read/save/history, and summary operations. The UI calls the contract; filesystem traversal and boundary checks live in `LocalOneDriveProvider`. The setup factory currently creates a local provider. A future Microsoft Graph provider can implement the same contract without changing the file browser.

## Project marker (schema version 1)

Located at `.projecthub/project.json`:

```json
{
  "schema_version": 1,
  "project_id": "persistent-generated-identifier",
  "project_name": "Fuel Cell Capstone",
  "settings": {
    "schema_version": 1,
    "goal": "",
    "storage": {
      "project_name": "Fuel Cell Capstone",
      "online_url": "https://tenant.sharepoint.com/sites/project/library"
    },
    "links": {
      "Reports": "07_Reports",
      "Meeting agenda": "00_Project_Admin/agenda.docx"
    }
  }
}
```

The app fills omitted setting fields from defaults. Existing minimal version-1 markers with only `project_name` are accepted; their local cache uses the local root as its identity fallback. Newly created markers always receive a persistent `project_id`. Unknown marker schema versions are rejected without rewriting files. Future schema changes need explicit migrations.

Settings changes create `.projecthub/history/<revision-id>.json` with timestamp, profile, reason, and previous/next settings. Revisions contain no local project root. Shared writes check that the settings still match the connection snapshot; reconnect after another user's edit. Sync concurrency still requires coordinated edits.

Other future shared metadata may live in `.projecthub/samples.json`, `experiments.json`, `procedures.json`, `schema.json`, and `migrations/`. These entity registries are not authored by this phase.

## Local profile

`%LOCALAPPDATA%/FuelCellProjectHub/local.json`:

```json
{
  "local_project_root": "C:/Users/TeamMember/OneDrive - University/Fuel Cell Capstone",
  "paths": {},
  "setup_complete": true,
  "local_resource_paths": {}
}
```

Legacy `project_folder` and absolute document shortcuts migrate to `local_project_folder` and `local_resource_paths` before new shared writes. New shared path fields reject absolute paths and traversal. The app does not rewrite old historical revisions.

## Local index (schema version 1)

`%LOCALAPPDATA%/FuelCellProjectHub/index/file_index.json` contains `schema_version`, project identity, `last_index_time` (UTC ISO 8601), `next_id`, `records`, latest change counts, warnings, and file change events.

Each record contains:

```json
{
  "id": "FILE-000001",
  "relative_path": "03_Experiments/E-20261010-A/R03/video.mp4",
  "name": "video.mp4",
  "extension": ".mp4",
  "size": 120,
  "modified": "2026-10-06T20:42:00+00:00",
  "modified_ns": 1791319320000000000,
  "category": "Video",
  "archived": false,
  "experiment_id": "E-20261010-A",
  "run_id": "E-20261010-A-R03",
  "sample_id": "S-001",
  "procedure_id": "P-001",
  "procedure_version": "2.1",
  "state": "active",
  "first_indexed": "2026-10-06T20:42:00+00:00",
  "modified_after_initial_index": false,
  "raw_data": false,
  "cloud_placeholder": true
}
```

Missing files become `state: "unavailable"` with `unavailable_since`. Unreadable directories preserve old records with `scan_unverified: true`, so permissions failures are not reported as deletions. Reappearing files at the same relative path retain their ID. Rebuild also preserves these IDs and historical modifications. Renames/moves get new relative-path identities; no hashing or heuristic identity matching is performed.

The local cache is scoped to its project identity. Connecting another project cannot show the previous project's records. This initial version maintains one active project cache per profile; switching projects and rebuilding replaces that active cache.

## Relationship metadata

Recognized small JSON files in a file's directory or ancestors: `experiment.json`, `run.json`, `sample.json`, `procedure.json`, `metadata.json`. Records can provide `experiment_id`, `run_id`, `sample_id`, `procedure_id`, and `procedure_version`; an experiment may alternatively include `procedure: {"id": "P-001", "version": "2.1"}`. String fields override inferred directory IDs. Deeper folders override ancestor metadata. `run_id: "R03"` resolves to `<experiment_id>-R03`.

Metadata is read only if local, non-linked, and at most 1 MB. Missing schema versions are treated as the initial metadata format; explicit unknown versions are skipped with a warning. Malformed metadata preserves last-known relationships for previously indexed files. Indexing is not document-content search and does not parse Word/PDF/Excel.

Directories such as `E-20261010-A/R03/S-001` infer experiment, run, and sample relationships. `P-...` directories infer procedures. Sample IDs can span many experiments through metadata references, without file duplication. No entity-editing or experiment-creation workflow is implemented.

## Indexing and boundaries

Both Refresh and Rebuild enumerate directory metadata to discover changes; incremental Refresh compares size, modified timestamp, and relative path. Unchanged files retain first-indexed and identity fields. Rebuild recomputes classifications/relationships and retains history. Startup loads the cache and validates the root/marker without scanning all project files.

Excluded directories: `.projecthub`, `.git`, `__pycache__`, `.venv`, `venv`, `node_modules`, and common application/test caches. Office lock files and `.tmp`, `.part`, `.crdownload` files are omitted. `99_Archive` is included with archive flags. Folder context overrides extension classification for procedures, reports, and references.

Symlinks and name-surrogate reparse points (including junctions) are excluded. OneDrive cloud reparse points are not excluded simply because they are reparse points. All opening operations validate the marker, normalized relative path, each existing path component, and root containment before handing a path to Windows. Executable/script/shortcut installer formats use the containing-folder workflow instead of direct execution.

Dataset contents are never read for indexing. Windows file attributes flag cloud placeholders; attribute detection does not decide whether a normal file can be indexed. User-initiated opening permits normal OneDrive hydration. Small app-owned marker/settings data is read to connect the project. Background workers support cancellation before atomic cache commit. A disconnect, changed project identity, malformed cache, or cancellation leaves the prior index untouched.

File modifications/removals are stored as local index events; Activity receives aggregated storage events instead of one entry per scanned file. The hub does not replicate cloud version history or provide a recycle bin.

## Future ingest design

Later work may introduce `DataIngestService` with `create_experiment_folder`, `register_file`, `register_run`, and `associate_sample`. It should accept permanent IDs and relative paths, delegate storage to the provider, and require an explicit operation before writing or moving data. No ingest implementation, automatic folder organization, Graph, login, or OAuth is included now.
