# Changelog

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
