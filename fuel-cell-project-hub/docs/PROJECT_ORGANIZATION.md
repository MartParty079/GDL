# Project organization Beta setup and acceptance

Work order CAP-ORG-2026-10-10 introduces a separate, versioned organization index.
The existing research browser, catalogs, UUIDs and legacy paths remain available;
they are not automatically converted or removed. Use **Project Organization** for
new canonical records. The existing browser remains a compatibility view for the
older catalog, not an alternate editor for these new organization records.

## Safe rollout and root selection

Development and Beta use only their profile-contained sandbox. Do not point them
at the production university project. Project / Settings / Storage / Shared
Storage configures the per-device root; no Windows username is built into records.
An explicitly approved future Stable release can map the existing locally synced
university project. No production migration is performed by this work order.

Sign in as Matthew with the Admin PIN. Open Project Organization, inspect the
displayed root, choose **Preview / initialize**, and review the additive folder
plan. Setup creates only missing folders; it never renames, deletes or moves
existing content. Initialization enrolls this device as the sole organization
index writer. Keep the original `.project_hub` catalog and its history intact.
Earlier Beta mappings and profiles remain in their existing migration backups.
Before setup, existing organization metadata is copied to a local dated backup;
snapshot backups also accompany each publication. Research files are not copied.

There are exactly four organizational categories:

| Category | Root |
| --- | --- |
| Experimental | `01_Experimental` |
| Research | `02_Research` |
| Meetings & Goals | `03_Meetings_and_Goals` |
| Design & Prototyping | `04_Design_and_Prototyping` |

Infrastructure lives under `_System/Organization` and is never a fifth category.
The original app tools, activity reports and compatibility browser are retained.

## Creation, files and revisions

Members use New record or Upload file. A request gets an immutable UUID
immediately. Numeric E/S/P/R/D/MTG identifiers and date-first filenames are
allocated by the Admin writer when Publish requests runs. Offline/disconnected
members therefore see pending requests rather than guessed, potentially colliding
numeric IDs. Create and publish dependencies before choosing them in link fields.
Task IDs also use T####. IDs are never recycled, including after snapshot rollback.

Uploads copy resident files; source bytes remain untouched. Files On-Demand
placeholders must be downloaded explicitly before upload. Checksums and sizes
are verified before canonical publication. Creation date stays fixed on edits.
The original creator comes from the selected profile; uploader and last editor
are separate. The profile roster remains the existing four people; the order
mentions five team members but does not identify a fifth. Admin can add that
person later. The five coordination roles have no people or backups preassigned
and confer no application privileges.

Experiments link permanent sample UUIDs and an exact published procedure revision.
Procedure/design/document edits write a new revision file. Raw content cannot be
replaced through metadata editing. Pore maps, overlays, outlines and derived
exports require the exact raw-file UUID, matching experiment/sample links and a
processing-run ID. Use distinct processing-run IDs for reruns. Metadata edits
retain file identity and original binary paths. Each correction needs a reason;
the snapshot's append-only audit stores actor, UTC time and complete prior/new
values. Details expose linked records and history. Sample history, aliases,
calibration, conditions, units and reference/fabrication metadata are editable.

## Single writer, lag and recovery

`Incoming_Changes/<request-uuid>.json` and `Incoming_Files/<upload-uuid>` carry
independent immutable changes. Members never publish or scan the master. Admin
validates actor, links, checksums and base revision, merges and publishes immutable
`Snapshots` with checksum-backed manifests and prior-pointer `Backups`. Readers
verify checksum/schema/channel before adopting a version and retain last-known-
good data locally. No shared SQLite database is opened.

Refresh / submit pending retries local offline queues. The status displays index
revision, last publication and possible staleness; OneDrive cloud propagation
cannot be proven locally. Pending requests shows accepted/conflicting receipts.
Conflicting edits remain recoverable: refresh, inspect prior/new history and
resubmit a correction with a reason. Request UUIDs make repeat intake idempotent.
Sync conflict manifest copies block publication until the owner compares them.
After comparing a conflicting proposal with the latest audit, use **Resubmit
reviewed request** and enter a reason. It creates a new immutable request against
the current revision. Partial binary uploads retry from verified local bytes with
a new upload UUID, preserving the conflicting original rather than replacing it.

Restore snapshot verifies a saved checksum and publishes a *new* increasing
revision. It preserves files, audit, high-water ID counters and processed request
receipts. It does not erase or replay prior requests. Orphaned immutable files
from interrupted publication remain preserved; retry uses the same contents.
Only the enrolled device publishes, even if another device signs in as Admin.
Never clone a writer profile. Writer transfer requires retiring the old writer
and an owner-reviewed plan; OneDrive does not supply distributed fencing.

Legacy dry run is explicit Admin maintenance. It resumes a checkpointed inventory,
records original paths/names/timestamps and hashes resident files up to 32 MiB.
Large/placeholder files retain null checksums, rather than forced hydration.
After reviewing counts/aliases/sample candidates, accept registration. Creators
remain Unknown; importer identity is separate. Duplicate retries use deterministic
import UUIDs. Legacy locations and binary contents stay intact. Check missing paths
reports missing/possibly unsynchronized, never deleted. No automatic full scan runs
at startup. Incremental intake handles app changes; reconciliation checks registered
paths only. Full inventory reruns remain explicit maintenance.

## Meetings, tasks, research and design

Meeting records offer editable Agenda, Live Minutes and Summary templates, date,
facilitator, note-taker, attendees, decisions, blockers, recording/transcript paths,
reviewer and approval. Manual transcript links are supported; automatic transcription
is unavailable. Create action tasks with one owner, due date, acceptance criterion,
status, optional supporters, meeting/decision links and semester. Unfinished tasks
are referenced on new agendas without duplicating task records. Status history is
audited. The Summary template asks for 3–6 sentences and review within 24–48 hours
is a team procedure, not an automatic quality certification.

Meeting export creates a readable PDF as a pending file proposal; Admin publication
saves it into the meeting's MTG-specific folder with creator/checksum metadata.
The editable source templates remain in meeting fields and immutable revision JSON.
No new DOCX editor or automatic transcription provider is introduced.

Research fields include publication dates separately from registration dates,
DOI/URL, designation/edition, access/license provenance, reviewer and comparability.
No articles or standards are downloaded or redistributed automatically. Bulk/3D
porosity is excluded from direct comparison with 2D apparent surface porosity.
A comparable flag requires 2D metric, definition, method, sample basis, units,
reviewer and rationale; the reviewer remains responsible for scientific validity.

Design records distinguish editable CAD sources, export file UUIDs, manufacturing
process, material, units, dimensions, tolerance and prototype feedback. The order
references an accompanying role-responsibilities document that was not supplied;
the five named domains are implemented without inventing its detailed text.

## Acceptance evidence and limits

`tests/test_organization.py` exercises multiple local clients, unique IDs,
attribution, raw/derived links, exact procedure revisions, stale edits, idempotency,
interrupted publication, rollback, missing paths, offline queue recovery, Admin
writer checks, five blank roles, meeting carry-over and scientific exclusions.
Representative fixtures include Holy GDL, 1344 Pascal and five sample records.
They prove search/migration behavior, not a scan of the live production archive.
The actual legacy inventory must be reviewed in an authorized environment later.

Packaged self-check opens the real Member organization panel against a verified
fixture snapshot. `tools/organization_demo.py` produces representative view
screenshots and a meeting PDF in an ignored QA folder, never production storage.
Release gates, edition isolation and installer preservation tests remain required.
This order publishes Beta only. Stable 0.5.0 and its update assets stay unchanged.
