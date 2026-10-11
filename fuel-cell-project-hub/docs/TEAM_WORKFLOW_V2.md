# Project Home and team workflow — CAP-ORG REV 2.0

Development/Beta implementation, canonical version 0.7.0. This order does not
authorize Stable publication, production OneDrive writes or hosted migrations.

## Audit and migration plan

The 0.6.0 baseline already provided four category records, UUID proposals,
single-device Admin publication, checksum-backed immutable JSON snapshots,
last-known-good reads, monotonic E/S/P/R/D/MTG IDs, provenance, revision-bound
procedures, legacy dry runs, meeting templates/PDFs, local PIN profiles and
weekly activity reports. The old landing page used disconnected project text;
there were no first-class reporting periods, submissions or shared workspaces.
Upload handled one file at a time. Existing software launchers, catalog browsers,
updater choices and protected release workflows are reused.

The implementation extends those Organization records and their existing event
transport; it does not introduce another database or writable OneDrive SQLite.
The established index remains `_System/Organization/published.json`, with
`Snapshots`, `Backups`, `Incoming_Changes`, `Incoming_Files` and import reports in
that same namespace. Folder names are root-relative. Historical `.project_hub`
catalogs and the earlier archive mapping remain intact and are not reimported on
Member startup. No live archive scan/move was performed for this order.

On the enrolled Admin installation, Preview / initialize backs up existing
organization metadata and profiles locally, adds missing directories, retains
all existing IDs/counters and creates stable `_Team_Workspaces/U####_Name`
bindings in the published snapshot. Re-running setup is additive. Display-name
changes retain the original workspace path. Four existing identities remain;
`U0005_Unassigned` reserves a folder for the unnamed fifth student without
inventing an account or role assignment. Add the fifth person through Admin,
then Initialize Shared Workspaces. Departed accounts and files remain recorded.

Existing snapshots retain schema 1 with additive record types/fields. New ID
namespaces are G (goal), BW (reporting period) and DEL (submission); E/S/P/R/D/MTG
are unchanged. Coordinate the writer and reader upgrade before team use: old
Beta clients cannot create/review these new record types. There is no automatic
research relocation or Stable profile migration.

## Design gate and implementation

The actual supplied skill was read from `skills-main.zip`, entry
`skills-main/skills/apple-design/SKILL.md`, name `apple-design`.
SHA-256: `77bb63b7043bb93aca2ff4ab040c249484eef35682bb6ff7163433c31d30adc7`.
The extracted copy is kept only in ignored QA state, not redistributed in Git.
Its web examples were translated to native Qt controls rather than adding a web
framework to this Windows application. Concrete rules applied:

1. Immediate press/focus feedback through native buttons and existing theme.
2. Explicit wayfinding: four named destinations, full submenu text, permanent
   Home access, clear filters and labeled utility/account actions.
3. System typography, weight/size hierarchy and solid, contrasting surfaces.
4. Responsive wrapping controls and resizable dialogs; no input-blocking or
   unnecessary animation, suitable for reduced-motion use.
5. Agency and purpose: upload preview before Apply, safe cancellation/retry,
   explicit recording permission and confirmations for workspace publication.

## User workflows

- Home opens after local sign-in. It reads the published snapshot and shows the
  canonical active goal, owned actions, agenda, configured schedule/deadline,
  active experiment's exact procedure revision and recorded parameters. No
  percentages, inferred attendance or invented measurements. Historical
  procedure links open the selected revision, not a replacement revision.
- Quick Start creates records, uploads files and configures reporting periods.
  New / Revise Procedure allows an existing procedure revision to be selected.
  Quick Open remembers user-local recently opened records. Existing Software
  paths/status remain available; the local resource registry supports categories,
  favorites, executable/document paths and HTTP(S) links without hard-coded
  contributor paths. Nothing launches automatically during QA.
- Settings exposes read-only sync diagnostics, safe same-project root relinking,
  reminder preferences, account controls and software setup. The organization
  mapping is local (`organization_root`), and relinking requires the same project
  UUID and synchronized same-channel team registry. Legacy catalog mappings stay
  separate and preserved. Beta still rejects roots outside its isolated profile.
- Administration contains member management, PIN setup/reset and workspace
  initialization. Organization maintenance retains publishing, legacy preview,
  conflict/audit inspection, reconciliation, archive/restore and rollback. Roles
  start unassigned and never confer Admin privileges.
- Batch intake supports native multi-select, file/folder drop, folder selection,
  contextual metadata defaults and a durable per-user queue. Edit selected
  context before Apply; full filenames/links/creator remain available in the
  preview. Number allocation stays with Admin, so preview names are explicitly
  provisional. Source imports use Copy; no arbitrary source Move is performed.
  Cancellation finishes the current verified file copy, then stops before the
  next file. Successful queued entries are not repeated on Retry. Unavailable
  Files On-Demand content must be downloaded explicitly before upload.
- My Workspace is shared storage, not private storage. Publish / Move into
  Project queues a reviewed destination/link choice. Admin copies and verifies
  bytes, publishes the snapshot, then removes the matching old workspace copy.
  A crash can retain a redundant physical copy, but only one path is authoritative.
  Rollback restores a moved workspace source from its verified canonical bytes.
- Admin configures a semester anchor, number of fourteen-day periods and first
  timezone-qualified deadline. Later spans and deadlines advance fourteen days;
  dates/grace/review are configurable and overlap is rejected. No weekday/cutoff
  is assumed. Due Soon/Overdue uses the configured deadline or grace deadline.
- Individual submissions support in-app content, uploaded artifacts or both.
  Draft → Submitted → Under Review → Accepted / Changes Requested → Resubmitted
  transitions are validated. Only the owner edits contributor content; assigned
  coordination leads or Admin review using their own identity. Accepted versions
  are locked; additions create linked addendums. Review history/times are derived
  from actual actions. Artifacts explicitly linked to a submission move into its
  accepted BW/U folder on acceptance; other evidence remains cross-links. A
  partial artifact move cannot publish half an acceptance.
- Meeting editing separates details, agenda, live notes/explicit attendance and
  summary/approval. Local meeting/deliverable drafts save every five seconds and
  can be recovered; stale revisions require comparison instead of overwrite.
  Save queues the actual change for Admin publication. Generate Draft Summary
  uses entered notes/decisions/actions without a paid or remote AI service.
  Approval records lead/Admin identity and time; original minutes remain intact.
  Audio/video upload requires participant permission; transcript paths must be
  uploaded/synchronized before linking. Automatic transcription remains absent.
- Open actions retain stable task IDs, appear in the next meeting's carried
  actions and on Home. Two-week digests list people/status, canonical goals/tasks,
  blockers and evidence and can export text. Existing weekly contribution PDFs
  remain separate; focused app time is explicitly an estimate, not hours worked.
- Legacy associations are reviewed explicitly through Link Legacy Images. They
  connect a sample, original raw and poremap/overlay/outline records without
  changing names, bytes, Unknown creators or inventing a historical run ID.
  Image selection switches between indexed originals and related outputs.

## Setup and limitations

Install the Beta edition, sign in locally, then have the enrolled PIN-unlocked
Admin use Preview / initialize and Publish requests. Configure actual dates and
assign the five coordination roles only after team discussion. Set Member PINs
through Administration on the designated profile writer. Existing optional-PIN
profiles remain compatible; their new records are explicitly marked selected
profile / PIN not configured, not verified authorship. PINs are app controls,
not protection against people who can edit the underlying OneDrive files.

This work order tests only representative isolated directories. The real shared
OneDrive library, cross-device sync timing, original legacy image correspondence,
and five live students require later owner-led acceptance. A fifth identity and
the separate detailed team roles document were not supplied. No production files
or external account/provider configuration were modified. Default Beta sandboxes
remain disconnected from the live library under repository policy.

No arbitrary legacy file move, embedded Word editing, automatic transcription,
or automatic measurement generation is claimed. PDF meeting export and complete
in-app records are supported; a two-week digest exports text. Long file copies
cancel between files, with feedback explaining that the current copy finishes.
Native light styling and static transitions are used; no new dark theme is added.
Unindexed loose workspace files can be opened in Explorer and registered through
intake; the app lists indexed workspace records rather than scanning on startup.

## Acceptance evidence

Run `tools/run_release_tests.py`, `tools/desktop_entry.py --self-check`,
`tools/team_workflow_demo.py --output <isolated QA directory>` and the existing
Windows Beta workflow. The workflow builds the exact pushed develop commit,
checks packaged startup and disposable install/upgrade preservation, validates
installer/checksum/manifest, then publishes a prerelease. Stable is untouched.

| Revised gate | Evidence / scope |
| --- | --- |
| Member Home/four categories/full navigation | `test_home_member_four_categories_full_navigation_and_settings`; Home screenshots at 1440 and 1024 pixels |
| Actual design skill | Exact entry/hash and applied rules above; screenshot review |
| Quick Start/metadata defaults | Actual Home workflows; defaults-preservation UI test |
| TIFF/PNG/PDF/DOCX/CAD batch, retry/cancel/collisions | Intake tests plus original raw/derived/collision tests; upload screenshot |
| U0001/U0002 workspaces/publication | Workspace rename/future-member and verified publication/rollback tests; fixture directories only |
| Two PIN identities/creator and editor | Cross-user PIN test and Admin PIN hashing/reset regressions |
| Five legacy samples/Holy GDL/1344 Pascal/derived links | Explicit reviewed representative legacy fixture test; original-name/checksum assertions |
| Exact procedure revision/archive/raw preservation | Existing revision/raw immutability tests plus reversible Admin-only archive test |
| Configurable biweekly periods/submissions/review/late state | Consecutive anchor, overlap/deadline, authorization, acceptance-lock/addendum and artifact-transaction tests |
| Meeting notes/attendance/recording/summary/carry-over | Existing meeting tests, permission/synchronized recording test, summary/actions test; meeting screenshot |
| Same canonical goal/task references | Shared goal/task/digest test; no percentage data |
| Admin offline/LKG/parallel/duplicate/incomplete sync | Existing multi-client Organization and SharedIndex regressions |
| Member never rescans | Existing authority-denial/member startup tests; no startup inventory call |
| Usage estimates/explicit attendance | Existing weekly activity and explicit meeting attendance integration tests |
| Beta/Stable/update isolation | Existing edition, installer, release-policy and safe-update regressions; protected workflow unchanged |

Actual pass/fail counts, build SHA, prerelease tag and public assets are reported
after verification. Live OneDrive/team acceptance is deferred rather than marked
passed from fixtures. Stable requires a separate exact-build human approval.
