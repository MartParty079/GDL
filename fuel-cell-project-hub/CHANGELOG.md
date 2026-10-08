# Changelog

## 0.4.2 — 2026-10-08

- Identity-bound shared OneDrive mapping with a pinned project identifier.
- Single authority publishes verified closed native-index snapshots; readers never rebuild.
- Idempotent pending jobs, cancellation recovery and retained revisions.
- Preserve catalog records without moving the legacy archive; portable references show migration pending.
- Persistent research records and generated outputs stay in the shared project.

## 0.4.1 — 2026-10-08

- Development/Beta work order only: separate app/installer/profile/protocol and prerelease update channels; Stable 0.4.0 remains unchanged.
- Beta uses an isolated local research sandbox and refuses production Supabase; a separate Beta backend can be configured later.
- Development defaults to develop, with automatic Beta builds and an explicit tested-commit production approval gate.
- Update Now with graceful task handling and durable Update on Next Open retries.
- Safe update choices, recoverable editor drafts and startup installation before background work.

## 0.4.0 — 2026-10-08

- Publish the production Windows release with shared meetings, weekly contribution reports and legacy sample intelligence.
- Stable GitHub release, Windows installer and SHA-256 update verification.
- Fix index completion status when classification metadata contains nested values.

## 0.3.3 — 2026-10-08

- Measurable active sessions, shared meetings and per-person weekly contribution reports
- Added Meetings with explicit profile/guest attendance, shared recording links, transcript imports and revision history, notes, action items and research relationships.
- Added My Weekly Activity and administrator team reports with PDF/CSV exports and Generate All Team Reports.
- Added measured Hub-only sessions with a 15-minute idle cutoff, focus exclusion and durable idempotent sync; merged overlapping intervals in reports.
- Added protected Supabase meeting/session tables and transactional meeting saves with conflict detection. File attribution comes from explicit app actions, never automatic scanner discovery.
- Local speech model generation is not bundled; editable TXT/MD/DOCX/extractable PDF transcript import is available.

## 0.3.2 — 2026-10-08

- Sample relationships, image categories and families, advanced filters and research spacing

## 0.3.1 — 2026-10-08

- Added Tarleton Microsoft desktop sign-in, structured version history and administration version status.
- Browser PKCE sign-in with per-user desktop callback and password fallback.
- Append-only version history, bump utility and release consistency checks.
- Improved installation status and activity authentication context.
- Fixed restored navigation/details widths when older saved layouts contained zero-width panels.

## 0.3.0 — 2026-10-08

- Added email/password team login with Windows-encrypted saved sessions, invitations and password recovery.
- Added server-checked Admin users, activity, installations and system views; protected the last administrator.
- Added bounded account activity retries; research content and machine paths stay local.
- Added a per-user Windows installer, stable release build workflow and checksum-verified updates.
- Fixed spaced searches for legacy filenames such as HolyGDL; preserved the current and legacy index.
- Audited Teams controls: only production app launch/resource behavior was present; no manual test panel remains.

# GDL Research Hub version history

## 0.2.0

- Added a resizable research workspace with samples, experiments, file previews,
  image galleries, research timelines, favorites and recent items.
- Added flexible experimental conditions and result metrics, bulk file metadata
  editing, explicit association suggestions and metadata revision history.
- Added resident-only cached thumbnails, image viewing and comparison, rendered
  PDF pages, bounded spreadsheet previews and document/code text previews.
- Added database-wide file sorting, combined filters, logical and folder views.
- Added Windows document associations, Explorer selection and safe script editing.
- Preserved the native file index, source locations and separate legacy references.

## 0.1.0-dev

- Introduced the local research catalog, incremental metadata indexing, FTS search,
  content extraction, source configuration, backups and Files On-Demand handling.
- Removed Microsoft authentication and Graph dependencies.
- Integrated the managed GDL analysis engine and local software configuration.
