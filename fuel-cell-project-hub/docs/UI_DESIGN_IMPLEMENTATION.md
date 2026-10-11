# Structured Sidebar implementation — Beta handoff

Owner selection (2026-10-11): **Structured Sidebar — persistent category rail and focused work area**.
Candidate canonical version: **0.8.0**. Branch: `codex/ui-structured-sidebar`.
The owner approved all four reported hardening fixes with “fix all” on 2026-10-11.
This work targets Beta only. Stable 0.5.0 and its user data remain unchanged.
The Windows Beta workflow assigns the final prerelease sequence and verifies
installer/startup/public assets for the pushed source commit.

## Implemented composition and reuse

The four-category rail persists across the existing native Qt screens. Home
contains Quick Start, authoritative goal/procedure/deadline/meeting/task context,
repository health, activity filters and recent records/resources. Utilities remain
separate. The original tab indices and handlers are preserved behind the rail;
Files & Analysis, software, activity, bug reports, participation and Settings are
reachable. Member controls remain restricted and Admin still requires its PIN.

| Before | After | Why |
| --- | --- | --- |
| Home-only category buttons and crowded header | Persistent category rail, breadcrumbs and About/Updates menu | Keep orientation while using a workflow |
| Quick actions below several sections | Quick Start near the top, wrapping native controls | Reach common operations without hunting |
| Unsorted positional record selection | Sortable table with UUID-based selection and refresh restoration | Sorting must not edit or display the wrong record |
| Long table strings cut off without common behavior | Middle elision, full-value tooltips, read-only detail pane | Preserve distinguishing filename suffixes and readable metadata |
| One light stylesheet | Local system/light/dark choice and 100–200% text preference | Improve readability without changing shared project data |

Shared tokens: Segoe UI, 13px body / 16px section / 24px heading at 100%;
600 weight for hierarchy; 8/16/24 spacing; 8px control and 14px card radii;
solid neutral surfaces, one blue accent, semantic status colors; explicit focus
borders. Responsive context grids choose 1–3 columns. Native menus anchor to
controls; navigation/filtering have zero animation duration. High contrast
bypasses custom color QSS in favor of native controls; see verification limits.

Component map:

- `app/ui/navigation.py`: persistent rail and header, existing routes and account menu.
- `app/ui/home_layout.py`: selected Home composition; `home.py` retains business handlers.
- `app/ui/workspace_components.py`: responsive cards, text context, full-value table delegate.
- `app/ui/theme.py`, `appearance.py`: shared tokens and local appearance preferences.
- `organization.py`, `intake.py`: wrapping commands, headings and table browsing.
- `local_accounts.py`: installs the shell after existing role-bound panels are ready.
- `tests/test_sidebar_ui.py`: route/permission, UUID selection, local appearance and keyboard regressions.
- `tools/ui_design_fixture.py`, `ui_design_qa.py`: isolated development stress data and native picker.

No new dependencies, backend, storage schema, migration, ID changes or raw-data
renames. PySide6 remains the UI library. The disposable HTML prototype picker
was removed after promotion; its source is recoverable at commit
`813239d2c8c14af48cd217f09b856963a25390d1`. Historical alternatives/evidence
remain documented in UI_DESIGN_PROTOTYPES.md and ignored local screenshots.

## Exact skills and applied rules

Verified archive SHA-256:
`1e98d7a92ed11053d2dc8652bb739be0b1c0ed5ca6e463d4a08a2d7b002014d6`.
No declared skill bundle version exists; content hashes identify the loaded version.
Each entry is under `.test-state/ui-design-skills/skills-main/skills/<name>/SKILL.md`;
manifest.json records its exact absolute local path. Earlier hashes and detailed
rule mappings are in UI_DESIGN_PROTOTYPES.md.

| Skill | Rules actually applied | Affected components/evidence |
| --- | --- | --- |
| apple-design | Wayfinding; immediate feedback; system type; resizable grouping; solid surfaces | Persistent rail, native focus, wrapping Quick Start, context grids, screenshots |
| emil-design-eng | Deliberate hierarchy/spacing; reuse primitives; avoid high-frequency animation; restrained accent | Before/After/Why table above, theme tokens, native tables and dialogs |
| prototype | Three functional directions; exact picker; owner selection first; remove disposable surface after promotion | Owner selection, historical commit and screenshot evidence |
| pick-ui-library | Inventory installed primitives; select only a concrete missing need; prefer reuse | Qt menus, table delegate, grids; no web library added |
| break-ui | Plausible schema-shaped fixtures; change data boundary; dev-only toggle; empty/one/huge states; report before fixing | ui_design_qa.py, evidence.json and findings below |
| review-animations | Audit frequency; remove unnecessary movement; check keyboard actions; reduced-motion compatibility | Native static navigation/filters/buttons, motion verdict below |

New entry hashes: break-ui
`e7eec1d70ac56a04255e9c0dbe98084ea3d544cc04aaad34f32c95d6fa9dff5e`;
review-animations
`6ff590d29e436766135aa3d137be1fac2a867165c7257fc315b189361f1873af`.
Support documents read: break-ui/CATALOG.md and review-animations/STANDARDS.md.
Animate was not invoked because no added movement was justified. Sonner, Swift,
Expo and mobile-native skills do not fit the native Windows stack. Existing
ToastManager remains the single toast system.

## Stress field map and boundary

| Rendered value | Source | Contract/limit | Optional / tested edge |
| --- | --- | --- | --- |
| Record title, agenda, outputs, next steps | Organization records and fields | Nonempty title; no maximum title length in submit | Long technical/Unicode titles, optional empty text |
| Person / creator / owner | Local identity registry and record attribution | Existing identity schema; no UI shortening policy | Long realistic name; unassigned owner; preserved creator |
| IDs, UUID, revision | Authoritative record | Service allocated immutable identity / integer revision | 1,000 fixture rows; sorting preserves UUID |
| Dates and units | Goal/period/experiment fields | Existing date validation, engineering units are text | Older missing due date, ISO date/time, µm/pixel and 0.190 mm |
| Category, state, subsection, action labels | Existing enums/routes | Four categories, existing statuses | Empty/one, wrapping 200% controls |
| Filename, extension, destination, linked records | Intake preview / record path | Existing path safety/naming rules; no UI length limit | Long filenames, deep isolated fixture root; seven file types |
| Row counts / queued counts | Table/queue collections | 5,000-file intake guard; records not paginated | Zero, one and 1,000 records; no invented progress |
| Repository status / publication | Organization.status and snapshot metadata | Existing last-known-good snapshot semantics | Offline fixture status; stale visibility finding |
| Images / resources | Existing linked files and configured software | Optional; existing missing-path feedback | Baseline raw/derived regression suite; no external launcher execution |

Data enters through copied service state in a fresh fixture profile. No rendering
markup is edited to manufacture failures. The initial fixture is created through
real submit/publish services, then stress copies are memory-only. Offline display
fixture is a status simulation; actual offline proposal reconciliation remains
covered by the existing service tests. Old metadata deliberately removes a field
to reproduce the requested historical/missing-field scenario.

## Historical stress findings — all four approved and resolved

| # | Severity | Field / worst-case value | What happens | Applied fix location |
| --- | --- | --- | --- | --- |
| 1 | Broken | Historical active goal without due_date | Home reload raises KeyError, leaving a partial dashboard | `app/ui/home.py:63`: tolerate absent historical display fields, show “Not scheduled”; cover period/procedure fallbacks without changing stored records |
| 2 | Broken | 200% text, 1366×768 organization screen | Status, commands, record table and warning overlap; actions/table are unusable | `app/ui/organization.py:203`: scrollable controls/context region and protected minimum record-table area; retain full labels |
| 3 | Ugly | 200% text, Aleksandra Wiśniewska-Kowalczyk — Research Documentation Coordinator | Header account label is clipped and search collapses to an indistinct fragment | `app/ui/navigation.py:70`: responsive second header row, bounded account label with full tooltip/accessibility text; usable search width |
| 4 | Fragile | Offline/possibly stale last-known-good snapshot | Durable status exists in Repository below the fold, while top banner still gives neutral file-access text | `app/ui/home.py:103` and `app/ui/navigation.py:61`: compact persistent shared-index health adjacent to breadcrumbs/notification, preserve full diagnostics below |

Approved decisions applied: preserve full control labels with a scrollable control
region and protected record-table height; responsive two-row header and native
account-label middle elision with full tooltip/accessibility text; persistent
shared-index health banner. Missing historical goal dates display “Not scheduled”;
incomplete periods and unlocked procedure revisions are not presented as configured.
No stored records or schema limits changed. Enlarged table columns account for
header text widths, with horizontal scrolling when needed.

What held up: four category routes; Member restrictions; immediate Quick Start;
empty and one-item descriptions; 1,000-row browsing; middle-truncated intake
names with full preview/tooltips; seven preview types (.tif/.png/.pdf/.docx/
.sldprt/.stl/.3mf); dark solid surfaces and readable native links. Long context
remains reachable with scrollbars. A standalone context component was rendered
at 320px; the full desktop retains its existing 1024px minimum. RTL is not a
supported product mode. Offscreen Chinese glyph fallback rendered missing glyphs;
real Windows font fallback/screen-reader and OS-level high-contrast acceptance
remain open, not claimed passed.

The live development picker uses Demo data / Worst case / Empty / One /
1,000 rows / Offline snapshot / Old metadata. Launch from the app root:
`.venv/Scripts/pythonw.exe -m tools.ui_design_qa`.
Capture repeatable evidence with `--capture`. Packaged/Stable execution is blocked.
The QA picker is not an application entrypoint or shipped UI feature.

## Motion review

| Before | After | Why |
| --- | --- | --- |
| Existing native immediate feedback | Kept immediate for rail, sorting, search, keyboard and batch controls | High-frequency operations must remain interruptible; no movement provides useful spatial information here |
| Disposable picker highlight motion | Picker removed from shipping composition | Its comparison chrome has no purpose in the chosen application |

Accessibility tier: static transitions have the same behavior with reduced motion.
`app/ui/theme.py:48` explicitly records zero added motion duration; navigation and
filter handlers set native state directly. No new property/keyframe/layout
animation is present. Motion-only verdict: **Approve**. All four stress blockers are resolved. Native Windows high-contrast/theme and
screen-reader limitations below remain disclosed; no full WCAG certification is claimed.

## Verification and evidence

Environment: Windows 11 build 26200, Python 3.12.14, locked PySide6 6.11.2,
Qt offscreen, local temporary directories and new isolated fixture profiles.

- Existing release suite: 318 tests in 179.350s, OK, 2 skips. Log:
  `.test-state/ui-sidebar-release-tests.log`.
- Initial focused sidebar/local identity check: 17 tests in 37.507s, OK.
  Log `.test-state/ui-sidebar-focused-tests.log` (3 new + 14 existing tests).
- Current sidebar rerun: 4 tests in 23.219s, OK, including native Space-key
  activation/focus for all four primary workflow dialogs.
  Log `.test-state/ui-sidebar-new-tests.log`. The offscreen test explicitly
  activates its window before sending keys.
- Stress evidence: `.test-state/ui-sidebar-stress/evidence.json`, 1366×768 and
  1920×1080 captures for Demo/Worst/Empty/One/1,000/Offline; dark/200% browser
  and Home; 320px component; seven-type intake preview. Measured reload+event
  processing 19.1–90.5ms for normal states, 128.4–147.6ms for 1,000 fixture
  rows. These are observed timings, not startup/rendering benchmarks.
- Workflow screenshot tour: `.test-state/ui-structured-sidebar/`, real Home,
  small Home, upload, meeting editor, deliverable editor/browser, workspace,
  Admin and Quick Start. Before images: `.test-state/ui-design-baseline/`.
  The final tour also captures actual original/derived image relationships, Research
  and Design navigation under `.test-state/ui-sidebar-final-tour/`.
- Regressions cover actual offline staging/reconciliation, creator attribution,
  duplicate/retry behavior, two identities, agenda/summary and deliverable states,
  Holy GDL / 1344 Pascal and raw/derived links. No live production data touched.
- Native high-contrast custom-color bypass is unit-tested using a mocked OS flag;
  actual Windows contrast-theme, DPI/display scaling and screen-reader checks
  are pending. 200% application text test is not OS DPI certification.

Final hardening evidence:

- `.test-state/ui-sidebar-fixed-tests.log`: 6 tests, 28.411s, OK. Includes missing
  goal/period/procedure fields without snapshot mutation; 200% scrollable controls,
  minimum table height, full accessible account name and visible offline banner.
- `.test-state/ui-sidebar-final-release-tests.log`: 324 tests in 174.123s, OK, 2 skips. This includes the six sidebar/hardening
  regressions and existing data-integrity/workflow/update separation tests.
- `.test-state/ui-sidebar-stress/evidence.json`: all seven states rerun after
  fixes, no reload exceptions. Captures include Old metadata, visible offline
  health and 200% actions after scrolling. Observed reload times 11.4–101.0ms;
  this is fixture event-processing timing, not an application startup benchmark.
- `.test-state/ui-sidebar-final-tour/`: final real workflow screenshot tour;
  `.test-state/ui-sidebar-final-tour.log` is clean. Representative source screenshots
  are local ignored QA artifacts rather than research datasets in Git.

Beta packaging, fresh/upgrade installation, packaged startup and public checksum/
manifest validation run in the Windows Beta workflow for the exact pushed source.
The resulting prerelease is the handoff artifact; a source report alone is not a
publication receipt. No Stable promotion is authorized by this work order.

Rollback: close the development picker and use the unchanged installed Beta if
needed. Beta settings and data remain isolated from Stable; no schema/data
migration occurred. Preserve older research catalogs, fixture evidence and builds.
Before using any older Beta installer on a new profile, retain its local profile
backup; never downgrade or overwrite a newer installation in place.

The required break-ui report/approval gate is complete. Preserve its seven-state
fixture for future regressions. Normal development verification, audit, commit/push
and Beta packaging proceed without another hardening confirmation. The completed
handoff seeks Beta feedback, never production authorization.
