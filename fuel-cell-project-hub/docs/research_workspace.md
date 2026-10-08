# GDL Research Hub 0.2.0

The Hub opens the full-height research workspace. The existing software launcher,
managed GDL analysis tools, project resources and seven settings groups remain
available. Microsoft authentication and Graph remain removed.

## Navigation and workspace

The left navigation contains Overview, Samples, Experiments, Images, Data,
Reports, Timeline, Files, Legacy, Favorites, Recent, Needs review and Folders,
plus Settings, Analysis tools, Resources and Software. A splitter resizes the
navigation, research area and file details. Navigation and Details controls
collapse their panes; sizes and visibility are saved in the personal profile.
The persistent header shows the project, global file search, index availability
and a clickable application version. Press Enter in global search to search all
indexed sources, including linked sample and experiment context.

Blue identifies navigation and primary actions, teal identifies current research
and reports, purple identifies experiments and timelines, indigo identifies data,
and amber identifies legacy references and review. Overview summary cards, object
activity cards, selected rows and filters, hover states, disabled controls,
loading messages and actionable empty/error states share these colors.

## Research objects

Samples have explicit identities and descriptive names, material, manufacturer,
GDL type, batch, thickness with units, received/created dates, status, notes and
tags. Unknown fields stay blank. The sample page contains Overview, Images,
Experiments, Data, Reports, Timeline and Notes. Overview and object cards show
related counts; images, data and reports have embedded scoped file browsers.

Experiments contain a sample association, configurable type, date, operator,
status, description, procedure, equipment, notes and result summary. Conditions
and results are flexible named value/unit/notes entries. The page contains
Overview, Files, Images, Data, Results, Notes and Timeline. Edit object adds or
updates its fields and metrics. Sample and experiment favorites appear alongside
file favorites. Current and legacy objects require distinct identities, even if
their names match. The app rejects inconsistent and cross-origin assignments.

The initial experiment types cover optical microscopy, image analysis,
compression, water intrusion, pressure, flow, laser, calibration, preparation,
validation and other work. The type control accepts additional researcher names.

## Files, reports and data

Files have list, grid and compact views, 200-record SQL pages and database-wide
sorting by name, title, modification, creation, type, size, sample, experiment,
category, current/legacy, recent viewing, recent addition, report version and
status. Search and filters combine origin, sample, experiment, category, modified
date range and quick type/favorite/recent filters. Scopes include current view,
sample, experiment, project, all indexed sources and legacy. Creation and
modification sort use filesystem timestamps, not research dates. For preexisting
records without a first-index event, Recently added falls back to the existing
index observation timestamp; no historic addition date is invented.

Single-click selects details and a preview; list double-click opens the actual
file. Gallery double-click opens the image viewer. Context menus expose preview,
Windows file actions, metadata assignment, favorites, suggestions, relationships,
missing-file location and record retention. Ctrl/Shift selection supports bulk
sample/experiment/category/tag/favorite changes. Checked metadata fields alone
are applied. Appending tags and associations commit atomically after validating
the entire selection. Metadata, report version/status and raw/processed data stage
are saved in SQLite, never written into source files.

Reports display titles, version and report status; Data displays the stage.
Association suggestions match explicit object IDs or names against file paths and
notes and require Accept or a manual change. Suggestions never assign silently.
Favorites includes sample, experiment and file favorites. Recent records file
viewing. Needs review identifies missing sample links, duplicate warnings,
unclassified categories and extraction failures; it is a review aid, not evidence
that a scientific record is incorrect.

Folders uses the indexed directory tree with source selection, clickable
breadcrumbs and folder double-click navigation. Back/Forward preserve scoped
filters, sort, page, selected identities and scroll position. Browsing does not
reorganize folders. Locate updates the original record within its original source,
rejects already indexed targets and clears stale extracted content until indexing
runs again. Hide record only excludes a record from workspace lists; Restore
hidden records reverses it. Keep record leaves it intact. None of these actions
deletes a physical research file.

## Windows integration

`services/file_launcher.py` centralizes explicit native actions. Open File uses
Windows document associations; Show in Folder sends Explorer a separate
`/select,` argument and the full path; Open Folder opens the actual containing
directory; Copy Path copies the full path. The catalog validates configured roots,
relative paths and filesystem redirections before all actions. Missing files
produce an actionable unavailable state. Scripts open in the configured editor
(Settings > General), or Notepad on Windows; they are never run by association.
Executables and shortcuts require inspection in their containing folder. Process
arguments use lists with no command shell. Explicit Open may let OneDrive hydrate
an online-only file. Background gallery and preview reads first reject placeholders.

## Preview and images

The right pane contains metadata, preview status, Open/Show/Copy actions and a
Locate action for missing references. PDF previews use Qt PDF rendering with page
selection, fit-page/width, zoom and an expandable/full-screen viewer. Spreadsheet
previews support XLSX sheet selection and CSV/TSV, up to 250 rows and 100 columns,
with formulas shown as text. DOCX and text/code show bounded readable text; code
uses a monospaced font. Unsupported, unreadable, oversized and online-only files
retain their Open and folder actions.

Images use disposable signature-keyed thumbnails in the application cache.
Thumbnail work runs in background batches of at most 24 visible candidates; no
full-resolution gallery batch is loaded. The viewer supports fit, actual size,
zoom, drag-pan, full screen, previous/next within the loaded result page, metadata
and Windows actions. Select exactly two images for side-by-side comparison; its
toolbar fits and zooms both, and each pane can be panned separately.

Resident preview files are limited to 32 MiB; archive-based documents also have a
32 MiB expanded-content guard. Images are limited to 40 million pixels, and text
previews to 100,000 characters. CSV reads at most 2 MiB. Thumbnails are optional
and may be deleted and regenerated without altering the index or sources.

## Timeline, relationships and schema 4

Schema 4 adds `research_objects`, `research_events`, `workspace_recent`,
`workspace_files`, `workspace_hidden`, `workspace_revisions` and
`research_file_links` to the same catalog. Sample and experiment identities use the existing file
metadata/override fields and explicit links; filename-inferred IDs remain
unconfirmed suggestions. Existing manual overrides seed confirmed links;
records and file content are not duplicated. Flexible
conditions and results are stored in object JSON. Existing file relationships
(`derived_from`, `related_to`, `supersedes`, `previous_version`, `references`)
remain available. The relationship dialog displays related names/identities and
field-by-field metadata revision comparisons; it does not claim to store historical
binary files. Copy file ID helps identify explicit relationship targets.

Project, sample and experiment timelines include object creation, status and note
changes, metadata edits and filesystem index observations. Record research event
adds explicit notes, experiment start/completion, analysis, report revisions and
status observations. Filesystem events are labeled as observations and do not
fabricate experiment or capture dates. Recording events does not launch analysis.

A schema-3 migration first backs up SQLite and adds tables without rebuilding
existing file payloads or FTS content. Validation against the personal catalog
preserved all 172,283 file payloads/identities and content records, with identical
before/after fingerprints and unchanged overrides. Counts remain 5 current files
and 172,278 legacy references. That migration did not read research source files.

## Version, verification and remaining limits

The version changed from **0.1.0-dev to 0.2.0**. `app/version.py` supplies the
header, About/version history, diagnostics and Windows executable version resource.
[CHANGELOG.md](../CHANGELOG.md) is bundled in the package and shown by About.

Final validation: 198 tests ran, 196 passed and two existing Windows filesystem
link tests skipped. The Windows package self-check exited 0; its header, diagnostic,
file and product versions are all 0.2.0.

Verification includes object/association/search/timeline tests, a schema-3
preservation test, mocked Windows association/Explorer/editor calls, bounded
resident preview tests, offscreen sample/experiment flows, and screenshot review
at 1440 x 980 and 1024 x 700. `tools/smoke_workspace.py` uses isolated research
fixtures; `--personal` browses the existing catalog without modifying source files
or launching external programs. The package self-check covers Qt PDF, spreadsheet
and thumbnail support, research objects, content search, version and changelog.
Actual Office/Explorer windows were not opened during automated tests. PDF uses
[Qt's PDF viewer](https://doc.qt.io/qtforpython-6/PySide6/QtPdfWidgets/QPdfView.html).

Remaining limits: image previous/next is bounded to the loaded page; synchronized
comparison panning, drag-and-drop associations, image/code scientific annotation,
OCR, binary report revision storage and arbitrary proprietary-format previews are
not implemented. Conditions and results are edited through Edit object. Research
objects and timelines are local to the selected catalog; multi-user conflict
resolution and automatic completed-GDL-session association are not implemented.
Thumbnail cache cleanup is manual. Old files keep inferred scalar associations
until explicitly linked to registered objects; migration does not invent samples.
This is a local Windows build and source update, not a GitHub Release or an
automatic replacement of an already installed application.
