# Shared OneDrive project — Development/Beta

Beta now maps the existing `GDL research - General` project. Stable installations,
main and production Supabase remain unchanged. This explicit amendment replaces
the previous Beta sandbox-only research path rule; it does not authorize a
Stable release or any production backend writes.

Startup checks the saved root, OneDriveCommercial/OneDrive, then the current
Windows user's university OneDrive folder. Missing or invalid identity opens
folder selection. A missing folder never causes automatic project creation.
The Beta bootstrap pins the owner-verified project UUID, so even a new user's
first selection rejects an unrelated identity with the same folder name.
The owner must explicitly enroll an existing project using its shared identity
inside `.project_hub/identity.json`; reconnecting checks the saved project UUID.
Drive/item fields are reserved for verified identifiers when available. No
Graph access or folder-name inference supplies project identity.

## Authoritative storage and distribution

The existing NativeIndex schema, classifiers, sample intelligence and research
workspace remain the only index architecture. The configured authority prepares
SQLite changes in disposable local cache, closes and validates the database,
publishes `index/revisions/<uuid>.sqlite3` and its SHA-256, then atomically writes
`index/project_manifest.json` last. Every old committed snapshot is retained.
Clients verify integrity and read immutable snapshots through SQLite mode=ro.
The local verified copy is disposable distribution cache, not a project master;
deleting it causes download from the shared project, never a client rebuild.
Snapshot checksums are rechecked when a local cached file changes or at restart.
Conflicted identity, manifest, control-folder or snapshot copies require owner
review. Incomplete sync retains the last verified revision.

Shared settings/history, specimen records, classification changes, meetings
journals, generated thumbnails, GDL session metadata, activity and contributions,
recoverable research drafts and index logs stay under the project root.
Local storage holds root/source mappings, secure auth sessions, personal UI
preferences, update controls, installed software paths and disposable caches.
Old local research databases are preserved as migration sources, never deleted
or used as a second writable master after mapping the shared project.

Normal users submit uniquely named pending jobs. Allowlisted research edits are
applied by the authority using isolated job copies and a transactional applied
job ledger in the published snapshot. Jobs remain on disk for recovery; retry
cannot duplicate an applied edit. Standard users never scan on startup or from
automatic reconciliation. They poll for new published revisions. Manual scan
requests enqueue work for the authority. The authority performs incremental
scans when opened/requested; it need not remain continuously online.

## Authority and recovery

Enrollment requires explicit project-owner approval and saves this installation's
authority identifier locally. Edition status never grants a backend admin role.
A local operating-system file lock prevents simultaneous publishers on the
configured device. The lock is not synchronized and is not distributed fencing.

OneDrive file ACLs and the single-device procedure govern this offline mode.
It is not server authorization against malicious members who can edit control
files. No production Supabase credentials are loaded. A future separate Beta
Supabase project can provide server roles and coordination through the existing
account configuration; backend administration stays disabled until configured.

Transfer/recovery must first retire the old publisher: close/uninstall it or
revoke its shared-folder write access, confirm it cannot resume offline writes,
and resolve synchronization conflicts. On the new owner device, use:

```
python tools/configure_shared_project.py --root <synced-project-folder> --transfer-authority --confirm-owner --confirm-old-device-retired
```

This records authority history and rotates the authority ID. There is no
automatic timeout takeover: offline OneDrive cannot safely prove another device
is retired. Never clone the authority's local profile onto a reader machine.
Use Restore Index to publish a verified previous snapshot as a new revision.
Keep old snapshots/backups until their replacement is verified on clients.

## Validated catalog-only migration plan

The administrator approved retaining the previous catalog without moving archive
files. The old catalog contains 172,284 file records and 11 research objects;
its legacy archive is outside the fixed shared root. Migration opens the source
read-only, takes a consistent SQLite backup into disposable cache, checks
integrity, verifies file/object/override/relationship counts, preserves IDs,
rewrites machine-specific source/file paths to portable references, and publishes
the closed snapshot. The source database and every research file remain intact.
The original current-project UUID becomes the explicitly stored shared identity.
`index/legacy_manifest.json` records the once-only import and validated counts.

Legacy sources map to `Legacy Data` inside the shared project. Missing archive
folders produce disconnected/migration-pending references, not invented file
availability. The index remains searchable while file links are unavailable.
Placing original archive files there requires a separate owner-approved migration
plan covering shared ownership/permissions, OneDrive availability, counts,
relative paths, byte integrity and rollback. This work order performs no move,
rename, delete or duplication of research files and does not migrate classmates.

Automated acceptance uses distinct Alice/Bob Windows-style home/AppData mappings
and synchronized project copies; it does not create new Windows login accounts.
Coverage includes new-reader startup without indexing, publication/reload,
queued edits/retries, incomplete/conflicted sync, cancellation, source identity,
concurrent local publisher rejection and catalog migration preservation.
