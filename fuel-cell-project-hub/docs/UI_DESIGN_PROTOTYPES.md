# Home design exploration — owner selection gate

Status: phases 0–1 only, development branch `codex/ui-design-prototypes`, based
on tested `develop` commit `38262ac8384a8d9342b99ae88de68341af98eb99`.
The application remains 0.7.0; installed Beta remains 0.7.0-beta.10 and Stable
remains 0.5.0. No app source, version metadata, dependencies or shipping
entrypoints change during exploration. A version increment and Beta build follow
selection and integration. No production publication is authorized.

## Repository and baseline audit

The real Windows app uses Python/PySide6 6.11.2 widgets, a QMainWindow shell,
QTabWidget routes, Qt stylesheets and Segoe UI. There is no React frontend,
package.json, web dev server, Swift or Expo runtime. The locked build environment
already includes Qt WebEngine/WebChannel through PySide6 Addons; they are used
only to render the specified picker chrome, never the candidate Home layouts.
The unnamed browser profile is memory-only and blocks non-local requests.

Reusable components include Button, AppCard, StatusPill, InlineMessage,
EmptyState, FlowLayout, ResponsiveCards, native menus/dialogs/tables and one
ToastManager. Theme already defines light surfaces, accent/semantic colors,
8/16/24 spacing and 8/14 radii. Sizes and font weights remain scattered in
individual screens. Dark mode, Windows high-contrast adaptation and consistent
text scaling need later measured work; they are not claimed complete here.

Home currently has correct category/data contracts and working shortcuts but
many equally prominent controls, extensive scrolling and internal card scroll
areas. The existing Organization form/browser, intake queue, PIN identity,
software launchers, shared JSON snapshots and submission/meeting services are
reused unchanged. No new storage schema, permanent ID or migration is needed.

| Before | After in isolated prototypes | Why |
| --- | --- | --- |
| Equal emphasis for categories, utilities and secondary actions | Distinct category navigation, utilities and secondary tools | Makes the four main areas easier to identify |
| Long sequence of equally weighted Home sections | Three different hierarchies with priority/meeting/deadline context first | Lets the owner compare information architecture |
| Large fixed cards and many rows of controls | More compact cards, tool tabs and wrapping commands | Improves use of a 1366×768 workspace |
| Plain browser-blue record links | Restrained existing blue accent in native rich text | Keeps real linked records visually coherent |
| All workflows share one layout direction | Horizontal, sidebar and command/worklist directions | A meaningful composition choice rather than three color variations |

Baseline evidence: `.test-state/ui-design-baseline/` contains fresh actual app
screenshots. `.test-state/ui-baseline-tests.log` records 18 passing team/Home
smoke tests. The base commit previously passed 318 release regressions and
packaged/installer checks; no unchanged tests are presented as new prototype
acceptance.

## Verified skills and rules

Authoritative archive: `skills-main.zip`, SHA-256
`1e98d7a92ed11053d2dc8652bb739be0b1c0ed5ca6e463d4a08a2d7b002014d6`.
The bundle has no declared version number, so content hashes identify the exact
version. Its verified local copies live under
`fuel-cell-project-hub/.test-state/ui-design-skills/skills-main/skills/`.
`manifest.json` one directory above `skills-main` records exact absolute source
paths and hashes. No mutable network install was used and no third-party skill
source is redistributed through Git.

| Invoked skill / source entry | SHA-256 |
| --- | --- |
| `apple-design/SKILL.md` | `77bb63b7043bb93aca2ff4ab040c249484eef35682bb6ff7163433c31d30adc7` |
| `emil-design-eng/SKILL.md` | `ffbe68e6007fb42cb8149f089b400a1ca007d59ba23e8948e2be4476f3175939` |
| `prototype/SKILL.md` | `bba39c955eb1871c5a02733976ceec5d0324198e0812e667604756489c89f7b9` |
| `prototype/PICKER.md` support document | `31a55eec94715cc79942e91e172e539e3031dcd5e2e5ee7c1446cf2caee960a6` |
| `pick-ui-library/SKILL.md` | `675fdce308683256ed617351a9b74d23457a5fbd0a562d9831b9c764b8c5e682` |

Applied Apple rules: immediate press/focus feedback; consistent wayfinding;
system typography and hierarchy; resizable layouts; user control through real
existing preview, cancel and recovery flows. These affect native Home controls,
category navigation and workflow entrypoints.

Applied Emil rules: deliberate spacing and shared local tokens; no decorative
animation for frequent keyboard/filter/variant actions; immediate button states;
cohesive accent/neutral surfaces; Before/After review tables. The candidates
remain static, with no interaction blocked by transitions.

Applied prototype rules: named divergent layout axes; one full-size variant at a
time; real forms and canonical data; exact supplied picker markup/CSS/reference
wiring; explicit owner selection before integration. Only names and the allowed
static-comparison replay omission differ in the picker. A Qt bridge renders the
native counterpart when the prescribed mount function runs. Keys 1–3/arrows
switch, R remounts, inputs/modifiers are excluded, URL selection survives reload,
and one item has aria-current. Variant swaps have no transition. The supplied
picker alone has its 250 ms highlight motion and reduced-motion CSS.

`pick-ui-library` was explicitly invoked for accessible picker/navigation/table
primitives. Its curated libraries target the web, not Qt. Existing native Qt
controls cover those needs outside that list; no library is installed or replaced.
Sonner is inapplicable to this stack; the app's existing single ToastManager stays.
`break-ui`, `animate` and `review-animations` are deferred to the specified later
hardening phase, rather than falsely claimed as invoked. Swift/Expo/mobile skills
are inapplicable. No extra motion is proposed for filtering or bulk work.

## Candidate composition and component map

| Variant | Axis | Strength | Cost |
| --- | --- | --- | --- |
| Quiet Workspace | Horizontal navigation / balanced context grid | Familiar overview with all main shortcuts together | More scrolling as context grows |
| Structured Sidebar | Persistent category rail / focused work area | Clear location and room for related context | Uses horizontal space, especially in narrow windows |
| Command Center | Compact commands / searchable canonical worklist | Efficient for frequent work across records | Less approachable for new users; some actions use the command selector |

`common.py` supplies local tokens, context cards, utility/Quick Start controls and
activity/recent/resource tabs. The three separate variant modules arrange those
components differently. Existing HomePanel methods implement actual forms,
navigation, pending events, settings, workspaces and digests. Command Center adds
a native sortable/filterable worklist with full-value tooltips and linked UUIDs.

Prototype tokens: spacing 4/8/12/16/24/32; Segoe UI 12/13/14/18/24; radii 6/10;
neutral background #F5F6F8, surface #FFFFFF, text #17212F, muted #526174,
border #D5DCE5, accent/focus #0067C0. Native surfaces are opaque with no shadows
or animation; responsive FlowLayout wraps controls. These are candidate tokens,
not a change to the shipping Theme. Engineering values and units are unchanged.

## Run, evidence and limitations

From the app directory:

```powershell
./tools/Preview-Home-Layouts.ps1
# Explicit fixture Admin mode, not live administrator access:
./tools/Preview-Home-Layouts.ps1 -Role admin
# Repeat the native smoke/screenshots:
./.venv/Scripts/python.exe -m tools.ui_prototypes.run --capture .test-state/ui-home-prototypes
```

The verified archive defaults to the Windows user's Downloads folder. An explicit
`--skills-archive` may point to the supplied verified copy. The tool verifies the
picker SHA before using it. Output/state must be under ignored `.test-state`.
Every run creates a new profile and local research sandbox. It accepts no live
shared root. Member is the default role; explicit Admin mode has fixture PINs
only. Exports are confined to the QA directory. External software launches are
deliberately replaced with a clearly labeled availability check in this harness;
shipping launchers are unchanged. No Fiji, external identity or hosted backend
is used. No full library inventory runs on Member startup.

`.test-state/ui-home-prototypes/evidence.json` records the actual named Windows
environment, Python version, screenshots and per-variant capture-plus-smoke
timings (not performance benchmarks). Screenshots cover 1366×768 and 1920×1080.
The console_errors field contains picker JavaScript errors; the offscreen GPU
backend may emit GLES fallback warnings separately in the native process log.
Those are an offscreen environment limitation, not hidden console results.

| Gate | Evidence / status |
| --- | --- |
| Fresh baseline Home/team behavior | PASS: 18 baseline tests; before screenshots |
| Four categories and real category routes, all three variants | Native harness assertions and screenshots |
| Existing experiment/sample/deliverable/upload forms | Each opens and cancels in all variants; no fake success |
| Two representative screen sizes / no horizontal scroll | Six native screenshots plus scrollbar assertions |
| Command filtering | Actual canonical worklist query assertion |
| Picker keyboard/input exclusions/reload/aria-current | Native QTest and browser DOM assertions |
| Native record/data integrity | Existing services reused; fixture-only scope; no app-source diff |
| Full keyboard audit, 200%, contrast, dark appearance | DEFERRED: phase 4 after layout selection |
| 1,000+ rows, extreme filenames/offline stress via break-ui | DEFERRED: phase 4 after selection |
| All-screen polish / before-after tour / new Beta installer | DEFERRED: phases 2–5 after selection |
| Live OneDrive / five-person acceptance | Not performed; no production write authorization |

Generated evidence is authoritative for final prototype pass/fail; a missing
evidence.json means the harness did not complete. Sources are limited to
`tools/ui_prototypes/`, `tools/Preview-Home-Layouts.ps1` and this report. Nothing
in app imports the harness, and neither release workflow is changed.

Rollback: close the picker; installed Beta/Stable remain untouched. No profile
migration occurred. After selection, implement only that chosen direction in
development, remove the disposable harness unless the owner asks to retain it,
then complete phases 2–5 and publish a tested Beta. No owner choice is inferred
from the initially displayed or last-previewed candidate.
