# Design system and UX implementation

Applied the authorized Design Language and UX Spec to the existing PySide6 application. The source specification is archived under `docs/reference/Fuel_Cell_Project_Hub_Design_Language_and_UX_Spec.md`.

## Shared components

`app/ui/theme.py` owns semantic colors, typography, borders, radii, focus, disabled, hover and selected states. The interface uses an off-white workspace, white cards, blue actions, restrained status colors and Segoe UI. Primary buttons use a darker blue for readable white text.

`app/ui/components.py` supplies buttons, cards, section headers, one SVG line-icon family, status pills, search inputs, switches, responsive card grids, skeletons, empty states, inline errors and one timed toast manager per window. Technical errors remain available behind Show details. Dates are formatted in the user's local timezone. Standard Qt widgets provide keyboard navigation and accessible control names.

## Existing workflows

- Global navigation retains Dashboard, Activity, Software, Project, Bugs and Settings. Dashboard and Project add workspace navigation for Overview, Files & Data, Reports, Resources and Shared storage.
- Dashboard cards cover goals, plan, storage, software, shortcuts, meeting notes and changes. Missing content offers the corresponding setup action.
- Settings groups General, Storage, Software, Project resources, Updates and History. Shared changes and restore retain explicit team confirmation and revision history. The update startup switch is personal and saves immediately.
- Software groups tools needing setup, ready tools and optional/retired tools. Teams keeps its explicit protocol test and download/retry recovery.
- Storage surfaces availability, last indexing time, counts and size. Refresh runs in the background, reports progress, supports cancellation and preserves known data. Less common actions and indexing warnings are expandable.
- Files & Data supports search, sortable columns, basic and expanded filters, clear filters and actionable empty states. Filters survive refresh and ordinary navigation. Sorted selections resolve by stored relative path, preserving the correct file-open target.
- Recoverable errors appear inline with human-readable recovery instructions. Update checks and launch/index results use nonmodal feedback. Bug reporting includes expected behavior and optional reproduction steps.

## Layout and verification

The minimum window is 1024 × 700. Dashboard cards use two columns when space allows and one below the workspace breakpoint. Layout minimum sizes prevent content clipping; long pages scroll. File actions fit the standard 1280 × 850 window, while large tables scroll internally.

Run `tests/smoke_ui.py`, `tests/smoke_storage_ui.py` and `tests/smoke_design_ui.py` for isolated offscreen acceptance flows and screenshots. Preview PNGs in this directory cover dashboard, storage, files, laptop, loading, empty, error and settings states. These fixtures contain temporary data rather than the real shared library.

Future sample, experiment, procedure, request, AI and update-install screens described in the specification are outside the current application's implemented functionality. This phase establishes reusable components for those future screens; it does not invent records or enable those modules.
