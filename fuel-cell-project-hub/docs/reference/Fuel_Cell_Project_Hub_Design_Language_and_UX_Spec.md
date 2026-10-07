# Fuel Cell Project Hub
## Design Language & UX Specification for Codex

**Document purpose:**  
This document defines the visual design system, interaction patterns, loading behavior, error handling, and UX standards for the Fuel Cell Project Hub desktop application.

The goal is to make the application feel polished, calm, modern, and consistent. The reference direction is a clean Apple-inspired productivity interface: bright, restrained, spacious, rounded, highly readable, and practical. Avoid sci-fi/HUD clutter, excessive gradients, glowing effects, or decorative UI that competes with the project content.

This specification should be treated as the default design language for all new UI work unless a later project decision explicitly overrides it.

---

# 1. Design Goals

The application should feel:

- modern
- calm
- precise
- lightweight
- polished
- consistent
- professional
- easy to understand without training
- fast even when background work is occurring
- visually similar across all sections of the application

The interface should communicate engineering information clearly without looking like engineering software from 2004.

The app should favor:
- simple layouts
- short labels
- obvious hierarchy
- predictable navigation
- progressive disclosure
- strong empty states
- clear feedback
- low cognitive load

Avoid:
- dense dashboards
- tiny text
- excessive borders
- excessive status labels
- deep nested menus
- large decorative HUD graphics
- neon glow
- unnecessary modal dialogs
- repeated confirmation prompts
- raw traceback errors
- ambiguous loading states

---

# 2. Core Visual Direction

## 2.1 Overall appearance

Use a bright, Apple-inspired desktop interface.

Primary characteristics:

- off-white application background
- white cards
- soft gray separators
- subtle shadows
- rounded corners
- clean sans-serif typography
- soft blue accent
- green for success/healthy
- amber for warnings
- red only for destructive/error states
- generous whitespace
- minimal visual noise

The interface should feel more like a polished modern productivity application than a technical dashboard.

---

# 3. Color System

Use semantic color tokens rather than hardcoded colors scattered throughout the application.

Suggested tokens:

```text
BACKGROUND_PRIMARY      #F5F6F8
BACKGROUND_SECONDARY    #FFFFFF
BACKGROUND_TERTIARY     #F1F3F6

TEXT_PRIMARY            #111827
TEXT_SECONDARY          #5F6B7A
TEXT_MUTED              #8A94A3
TEXT_DISABLED           #B5BCC6

ACCENT_PRIMARY          #0A84FF
ACCENT_HOVER            #0077ED
ACCENT_SOFT             #EAF4FF

SUCCESS                 #18A558
SUCCESS_SOFT            #EAF8F0

WARNING                 #D98A00
WARNING_SOFT            #FFF6E2

ERROR                   #D92D20
ERROR_SOFT              #FDECEC

BORDER_LIGHT            #E4E8ED
BORDER_MEDIUM           #D5DAE1

SHADOW                   rgba(15, 23, 42, 0.08)
```

Do not use color as the only indication of state.

Example:

Bad:
- green dot only

Good:
- green dot + "Connected"

---

# 4. Typography

Use a clean system sans-serif style.

Preferred font stack conceptually:

```text
Segoe UI
Inter
SF Pro / system equivalent
Arial fallback
```

For the current Windows/PySide6 app, use Segoe UI where available.

Suggested text scale:

```text
App title             28–32 px / semibold
Page title            24–28 px / semibold
Section title         18–20 px / semibold
Card title            15–17 px / semibold
Body                  13–14 px / regular
Secondary             12–13 px / regular
Caption               11–12 px / regular
Button                 13–14 px / medium/semibold
```

Rules:

- Use sentence case, not ALL CAPS, except very small metadata labels if justified.
- Never mix several font sizes inside one small card unless needed.
- Do not use bold for everything.
- Prefer semibold for titles and normal weight for content.
- Keep line lengths reasonable.
- Avoid long paragraphs inside dashboard cards.

---

# 5. Spacing System

Use a consistent spacing scale.

```text
4 px
8 px
12 px
16 px
20 px
24 px
32 px
40 px
48 px
```

Recommended defaults:

```text
Page outer margin      24–32 px
Card padding           20–24 px
Card-to-card gap       16 px
Section gap            24–32 px
Button internal pad    8–12 px vertical, 14–18 px horizontal
Form row gap           12–16 px
```

Do not manually invent spacing on each screen.

---

# 6. Corner Radius

Use rounded corners consistently.

Suggested values:

```text
Small control          6–8 px
Buttons / inputs       8–10 px
Cards                  12–16 px
Large hero panels      16–20 px
Pills / badges         full / capsule
```

Avoid mixing square and heavily rounded elements on the same screen.

---

# 7. Shadows and Borders

Prefer subtle shadows and light borders.

Cards should use either:

```text
1 px light border
```

or:

```text
very soft drop shadow
```

not both aggressively.

Example shadow:

```text
0 4px 18px rgba(15, 23, 42, 0.06)
```

No glowing outlines.

No thick neon borders.

No heavy black outlines.

---

# 8. Main Application Structure

The primary application layout should follow:

```text
Top Navigation
-------------------------------------------------
Dashboard | Activity | Software | Project | Bugs | Settings

Dashboard Workspace
-------------------------------------------------
Left Sidebar       Main Content
```

Top navigation is global.

Left sidebar is shown in the project/dashboard workspace.

Recommended left sidebar items:

```text
Overview
Files & Data
Samples
Experiments
Procedures
Reports
```

Quick-access items may appear below:

```text
Shared Storage
Project Calendar
Team Members
AI Assistant
```

Do not overcrowd the sidebar.

---

# 9. Dashboard Layout

The Dashboard should use compact, clean cards.

Recommended content hierarchy:

## Top section

A compact hero/header card containing:

```text
Fuel Cell Project Hub
short project subtitle
current project status
```

This should not consume half the screen.

Do not use unnecessary decorative 3D imagery unless it is subtle.

## Primary cards

```text
Primary Goal
Current Plan / Next Steps
Storage / Index Status
Software Status
Project Shortcuts
Upcoming Meeting
Recent Changes
```

Optional later:

```text
Team Activity
Experiment Summary
Simple Analytics
```

The dashboard must not become a dump for every metric in the application.

---

# 10. Card Design

Cards should contain:

```text
Icon or small visual indicator
Title
Optional secondary action
Content
```

Example:

```text
Storage / Index Status                   View details

OneDrive / SharePoint       Connected
Files indexed               1,248
Last refresh                10:32 PM
Storage used                18.8 GB
```

Avoid overusing large numbers.

Avoid putting several unrelated concepts in the same card.

---

# 11. Buttons

Buttons should have three main variants.

## Primary

Used for the main action.

Example:

```text
Connect Storage
Save Changes
Create Experiment
```

Visual style:
- blue background
- white text
- rounded
- no gradient

## Secondary

Used for normal actions.

Example:

```text
Open Folder
Refresh
Locate Application
```

Visual style:
- white/light gray background
- subtle border
- dark text

## Destructive

Example:

```text
Delete Permanently
Reset Project
```

Visual style:
- red only when truly destructive

Do not use red for ordinary cancellation.

---

# 12. Inputs

Inputs should be visually calm.

Use:

- clear label above or to the left
- placeholder only as supplemental guidance
- light border
- rounded corners
- obvious focus state
- validation below the field

Example:

```text
Local Synced Folder
C:\Users\...\Fuel Cell Capstone

Connected successfully.
```

Avoid giant form pages.

Group related settings.

---

# 13. Toggle Controls

Use toggles for persistent on/off settings.

Example:

```text
Automatically post major dashboard changes     [ ON ]
Check GitHub for updates at startup             [ ON ]
```

Do not use checkboxes for obvious preference switches.

Use checkboxes for multi-selection.

---

# 14. Dropdowns

Use dropdowns when selecting from a known set.

Examples:

```text
Procedure Version
Software Lifecycle
Resource Category
```

Dropdowns should not contain dozens of unrelated actions.

If more than ~10–15 options exist, add search.

---

# 15. Tables

Use tables only when tabular comparison is useful.

Examples:

```text
Files
Samples
Experiments
Runs
```

Tables should:

- support sorting
- support filtering
- have consistent row height
- use subtle separators
- avoid full grid borders
- highlight row hover
- support keyboard navigation later

Do not put every dashboard concept into a table.

---

# 16. Loading States

Loading behavior is mandatory.

The app should never display a blank area while waiting unless the task completes almost instantly.

## 16.1 Skeleton loading

Use gray placeholder/skeleton boxes while data loads.

Examples:

```text
████████████████
██████████
████████████████████
```

Skeletons should roughly match the shape of the real content.

For cards:

```text
[ gray title bar      ]
[ gray content line   ]
[ gray content line   ]
```

For tables:

```text
[ header placeholders ]
[ row placeholder     ]
[ row placeholder     ]
[ row placeholder     ]
```

Use soft neutral gray.

Recommended:

```text
Base skeleton          #E8EBEF
Highlight              #F3F5F7
```

If practical, use a subtle shimmer animation.

Do not make shimmer distracting.

---

# 17. Loading Rules

Use skeletons for:

- dashboard data
- OneDrive file index
- experiment lists
- sample lists
- software detection
- activity history
- GitHub update checks

Use a spinner only for:

- short button actions
- small local actions
- compact inline processes

Use progress indicators for:

- long index rebuild
- large imports
- exports
- large scans

Example:

```text
Indexing project files…
1,248 files scanned
```

Do not show an indefinite spinner for a process where progress can reasonably be estimated.

---

# 18. Background Work

Long operations must run off the UI thread.

Examples:

- OneDrive scans
- file indexing
- software detection
- GitHub release checks
- report generation
- large exports

The app must remain interactive.

The user should still be able to navigate elsewhere unless the operation requires exclusive access.

---

# 19. Optimistic and Immediate Feedback

When an action is accepted, give immediate visible feedback.

Example:

User clicks:

```text
Refresh Index
```

Immediately change to:

```text
Refreshing…
```

Then:

```text
Index refreshed
312 files updated
```

Do not wait silently.

---

# 20. Success Feedback

Use subtle success messages.

Preferred:

- small toast
- status line
- inline success label

Example:

```text
✓ Project settings saved
```

Avoid success modal dialogs unless the completion is important.

Do not require the user to click "OK" for every successful action.

---

# 21. Error Handling Philosophy

Errors must be:

- human-readable
- actionable
- calm
- specific
- recoverable when possible

Never expose raw Python tracebacks to normal users.

Bad:

```text
OSError: [WinError 123] The filename, directory name, or volume label syntax is incorrect
```

Good:

```text
Project folder could not be opened.

The saved OneDrive path is no longer available.

[ Locate Folder ]
[ Retry ]
```

---

# 22. Error Structure

Every user-facing error should ideally contain:

```text
What happened
Why it probably happened
What the user can do next
```

Example:

```text
OneDrive project folder is unavailable.

The folder may have been moved, renamed, or OneDrive may not be running.

[ Locate Again ]
[ Open OneDrive ]
[ Cancel ]
```

---

# 23. Error Severity Levels

Use:

## Info

Example:
```text
No experiments have been created yet.
```

## Warning

Example:
```text
3 required applications are missing.
```

## Error

Example:
```text
The project index could not be written.
```

## Critical

Use very rarely.

Example:
```text
Project metadata is corrupted and cannot be loaded safely.
```

Avoid treating recoverable situations as critical.

---

# 24. Error Presentation

Use inline errors whenever possible.

Use toast notifications for temporary failures.

Use modal dialogs only when:

- the user must make a decision
- continuing would cause data loss
- a destructive action needs confirmation
- the current operation cannot continue

Do not throw modals at the user for every minor problem.

---

# 25. Empty States

Every major page must have a designed empty state.

Example:

```text
No experiments yet

Create an experiment when you're ready to begin a test run.

[ Create Experiment ]
```

Do not show empty tables with nothing but column headings.

Examples requiring empty states:

- no experiments
- no samples
- no procedures
- no recent activity
- no bugs
- no indexed files
- no search results
- no software updates

---

# 26. Search UX

Search should:

- update quickly
- show clear empty state
- allow clearing easily
- preserve filters where sensible

Example:

```text
No files match "S-103"

Try another search or clear filters.
```

Use a clear X button inside the search field.

---

# 27. Filters

Filters should be visible but compact.

Example:

```text
[ Type ▾ ] [ Experiment ▾ ] [ Sample ▾ ] [ Date ▾ ] [ Include Archived ]
```

Provide:

```text
Clear filters
```

when any filter is active.

Do not hide basic filtering behind deep menus.

---

# 28. Navigation Behavior

Global top tabs:

```text
Dashboard
Activity
Software
Project
Bugs
Settings
```

When returning to Dashboard:

- default to Overview
- later allow optional "restore previous page" setting

Selected nav state must always be obvious.

Avoid changing navigation behavior unpredictably.

---

# 29. Project Sidebar

The project sidebar should only appear in project/dashboard workspace.

Suggested:

```text
Overview
Files & Data
Samples
Experiments
Procedures
Reports
```

Each entry should have:

- small simple icon
- label
- selected highlight

Selected highlight:
- light blue fill
- blue icon/text

No heavy border glow.

---

# 30. Icons

Use one icon family consistently.

Prefer line-style icons.

Examples conceptually similar to:

- Fluent
- SF Symbols style
- Lucide
- Feather

Do not mix highly detailed, filled, and cartoonish icons.

Icons should support labels, not replace them.

---

# 31. Status Indicators

Status pills should be compact.

Examples:

```text
Connected
Installed
Missing
Running
Planned
Complete
Reviewed
```

Use:

- green = healthy/success
- blue = active/neutral
- amber = attention
- red = error/destructive
- gray = inactive

Do not create a different color for every status.

---

# 32. Animations

Animations should be subtle and short.

Recommended durations:

```text
Hover              100–150 ms
Page transition    150–220 ms
Card reveal        150–220 ms
Toast              180–250 ms
Skeleton shimmer   slow/subtle
```

Avoid:
- bouncing
- spinning decorative objects
- long fades
- flashy transitions

Function first.

---

# 33. Toast Notifications

Use toast notifications for:

- save success
- index refresh complete
- resource added
- app update available
- background operation failed

Example:

```text
Index refreshed
312 files updated
```

Toasts should dismiss automatically after a few seconds unless action is needed.

---

# 34. Confirmations

Use confirmation only for actions with meaningful impact.

Require confirmation for:

- delete permanently
- team-wide setting changes
- restore previous settings
- destructive reset
- moving/removing major project structures

Do not confirm:

- opening files
- launching software
- refreshing index
- changing tabs
- applying harmless filters

---

# 35. Destructive Confirmation Pattern

Example:

```text
Delete this resource permanently?

This removes the resource from the Project Hub.
It does not delete the linked OneDrive file.

[ Cancel ]
[ Delete Resource ]
```

The destructive button should be visually distinct.

---

# 36. Settings UX

Settings should be divided into sections.

Recommended:

```text
General
Storage
Software
Project Resources
Updates
Activity
Advanced
```

Avoid one gigantic settings form.

Each section should have:
- heading
- short explanation
- related controls only

---

# 37. Settings Save Behavior

For normal personal settings:
- save immediately when practical

For project-wide settings:
- use Apply button
- show confirmation:

```text
Apply these settings to the entire team?
```

Maintain version history as already planned.

---

# 38. Software Setup UX

On first launch:

```text
Welcome to Fuel Cell Project Hub
```

Then:

```text
Checking your system…
```

Use skeleton/loading indicators.

After detection:

```text
Ready
Microsoft Teams
Python
Excel

Needs Setup
JMP
Swift Imaging
```

Offer:

```text
[ Set Up Missing Software ]
[ Continue Anyway ]
```

Required software remains visible until configured.

Optional software belongs in the Software page, not the startup blocker.

---

# 39. Software Cards

Each software card should show:

```text
Application Name
Status
Optional version
Optional path
```

Actions:

```text
Launch
Locate
Install Guide
```

Only show actions that apply.

Do not show "Locate Application" for URI-based software like Teams.

---

# 40. Storage UX

Storage is a primary feature.

The Storage page/card should clearly show:

```text
OneDrive / SharePoint
Connected

Files indexed      1,248
Last refresh       10:32 PM
Indexed size       18.8 GB
```

Actions:

```text
Open Folder
Open Online
Refresh Index
```

Advanced actions:

```text
Rebuild Index
Change Folder
```

Keep advanced actions visually secondary.

---

# 41. File Browser UX

The Files & Data page should feel like a lightweight Finder/File Explorer plus metadata.

Layout:

```text
Search
Filters
---------------------------------
File list/table
---------------------------------
Optional details pane
```

Rows should show:

```text
Name
Type
Experiment
Sample
Modified
Size
```

Do not show every metadata field in the main table.

Details can go in a side pane or dialog.

---

# 42. Sample UX

Sample page cards/list should prioritize:

```text
Display Name
Permanent Sample ID
Material
Manufacturer
Current State
New / Used
```

Selecting a sample should show:

```text
Overview
Experiment History
Files
State History
Edit Log
```

History should be chronological.

---

# 43. Experiment UX

Experiment page should prioritize:

```text
Experiment Name
Permanent ID
Procedure Version
Sample
Status
Runs
```

Use simple status:

```text
Planned
Ready
Running
Data Collected
Analyzed
Complete
```

Reviewed should remain a separate optional check.

---

# 44. Procedure UX

Procedure templates should show:

```text
Procedure Name
Permanent ID
Version
Status
Owner
```

Statuses:

```text
Draft / Planned
Active
Retired
```

Active procedures may receive suggestions/comments but should not be directly rewritten by normal users.

---

# 45. Activity UX

Activity feed should be chronological.

Filters:

```text
All
Updates
Requests
Area
Person
```

Do not use comment threads inside Activity.

Discussion remains in Discord or Teams.

Posts may be edited, but must show:

```text
Edited
```

with edit timestamp preserved in audit log.

---

# 46. Bug UX

Bug report creation should capture automatically:

- app version
- user/profile
- timestamp
- current page
- relevant software status

User should only need to provide:

```text
Title
What happened
Expected behavior
Optional steps to reproduce
```

Bug status:

```text
Open
Investigating
Fixed
Closed
```

---

# 47. Update UX

On startup, check GitHub in the background.

If updates exist:

```text
Update available
```

Do not download automatically.

Show:

```text
App update
Script updates

☑ Analysis Script
☑ Imaging Script
☑ Report Generator

[ Update Checked ]
```

All selected by default.

Allow rollback later as planned.

---

# 48. Accessibility

At minimum:

- adequate contrast
- keyboard focus visible
- controls usable with keyboard
- labels not dependent on icon-only meaning
- status not color-only
- minimum comfortable click targets
- avoid tiny text
- avoid extremely light gray text

Aim for roughly 40 px minimum interactive target height where practical.

---

# 49. Responsive Desktop Behavior

This is a desktop app, but different laptop screen sizes must be supported.

Recommended minimum window:

```text
1024 x 700
```

Preferred:

```text
1280 x 800+
```

At smaller widths:

- cards stack
- analytics move below main cards
- avoid horizontal clipping
- sidebar may compact later

Do not design only for a 4K monitor.

---

# 50. PySide6 Implementation Guidance

Create reusable components rather than styling each page individually.

Recommended reusable classes/components:

```text
AppCard
PrimaryButton
SecondaryButton
DestructiveButton
StatusPill
SectionHeader
SkeletonCard
EmptyState
Toast
SearchField
FilterBar
ErrorBanner
InlineMessage
LoadingOverlay
```

Centralize visual tokens.

Example:

```python
class Theme:
    BG_PRIMARY = "#F5F6F8"
    CARD = "#FFFFFF"
    TEXT_PRIMARY = "#111827"
    TEXT_SECONDARY = "#5F6B7A"
    ACCENT = "#0A84FF"
    BORDER = "#E4E8ED"
```

Do not scatter raw color strings through UI code.

---

# 51. Component State Requirements

Every interactive component should support relevant states.

Buttons:

```text
normal
hover
pressed
disabled
loading
```

Inputs:

```text
normal
focused
disabled
error
success where useful
```

Cards:

```text
normal
loading
empty
error
```

Tables:

```text
loading
populated
empty
filtered-empty
error
```

---

# 52. Skeleton Component Standard

Create reusable skeleton components.

Example:

```text
SkeletonLine(width=0.7)
SkeletonLine(width=0.45)
SkeletonBlock(height=80)
SkeletonTable(rows=6)
```

The app should not implement skeletons independently on every page.

---

# 53. Error Component Standard

Create reusable:

```text
ErrorBanner
InlineError
ErrorStateCard
```

Example error card:

```text
Storage unavailable

The shared OneDrive folder could not be found.

[ Locate Folder ]
[ Retry ]
```

---

# 54. Empty-State Component Standard

Reusable empty state:

```text
Icon
Title
Description
Primary action
Optional secondary action
```

Example:

```text
No indexed files

Connect project storage and build the index to begin.

[ Connect Storage ]
```

---

# 55. Toast System

Create a centralized toast/notification manager.

Suggested categories:

```text
success
info
warning
error
```

Avoid page-specific custom notification code.

---

# 56. Consistent Wording

Use consistent terminology everywhere.

Preferred terms:

```text
Project
Sample
Experiment
Run
Procedure
File
Storage
Index
Software
Resource
Activity
Bug
```

Do not alternate:

```text
test / experiment
item / sample / specimen
folder / directory
```

unless technically necessary.

For GDL materials, "Sample" can display as "Sample" while technical metadata may refer to specimen if needed.

---

# 57. Action Wording

Use verb-first buttons.

Good:

```text
Open Folder
Refresh Index
Add Resource
Create Experiment
Save Changes
Locate Application
```

Bad:

```text
Folder
Index
Resource Management
Okay
Proceed
```

---

# 58. Date and Time Formatting

Use readable local formatting.

Example:

```text
Oct 6, 2026
10:42 PM
```

or:

```text
Oct 6, 2026 · 10:42 PM
```

Avoid raw ISO timestamps in normal UI.

Raw timestamps may remain in logs/export files.

---

# 59. Number Formatting

Examples:

```text
1,248 files
18.8 GB
67%
4 experiments
```

Avoid:

```text
1248
18.834720 GB
0.670000
```

---

# 60. Performance Perception

Fast UX matters even when actual work takes time.

Principles:

- render page shell immediately
- load data afterward
- use skeletons
- update cards independently
- do not block full page because one service is slow
- cache safe local metadata where appropriate
- show last known value while refreshing when useful

Example:

```text
Files indexed
1,248
Refreshing…
```

is better than replacing the entire card with blank content.

---

# 61. Partial Failure Handling

If one service fails, the rest of the dashboard should still work.

Example:

GitHub unavailable:

```text
GitHub status unavailable
Retry
```

while:
- Storage still loads
- Software status still loads
- Goals still load

Avoid all-or-nothing page rendering.

---

# 62. Offline Behavior

When internet access is unavailable:

- local OneDrive-synced files should still be accessible if present
- local index should still work
- GitHub checks should show unavailable
- Teams/Discord links may fail normally
- dashboard should not collapse

Display:

```text
Offline
Cloud services temporarily unavailable
```

without treating the entire app as broken.

---

# 63. Data Safety UX

When editing project-wide data:

- avoid accidental overwrites
- preserve revisions
- show meaningful confirmation
- use append-only logs where defined
- rely on OneDrive/SharePoint versioning for files

The UI should never imply that the Hub provides file backups if it does not.

---

# 64. Visual Density Rule

When in doubt, remove something.

A dashboard should not show every metric.

Prefer:

```text
7 useful cards
```

over:

```text
20 tiny widgets
```

Important information should be visible.

Detailed information should live one click deeper.

---

# 65. Dashboard Priority

Above the fold should answer:

```text
What are we doing?
What comes next?
Is storage working?
Are required tools ready?
Where do I go?
```

If the dashboard answers those five questions quickly, it is doing its job.

---

# 66. Reference Dashboard Composition

Recommended initial dashboard:

```text
---------------------------------------------------
Hero / Project Summary
---------------------------------------------------

Primary Goal        Current Plan        Status

Storage             Software            Shortcuts

Upcoming Meeting    Recent Changes
---------------------------------------------------
```

Optional right-side analytics should only appear if useful and if space permits.

Do not reserve a permanent giant analytics column.

---

# 67. UX Acceptance Criteria

The design implementation is successful when:

1. A new user can understand the Dashboard without explanation.
2. Storage connection state is obvious.
3. Missing required software is obvious but not obnoxious.
4. Long operations show skeletons/progress instead of blank areas.
5. A failure never exposes raw Python errors to normal users.
6. Empty pages provide a clear next action.
7. Buttons and labels use consistent wording.
8. Page layouts use consistent spacing and card styles.
9. The UI remains responsive while indexing/scanning.
10. One failing service does not break unrelated UI.
11. Project-wide destructive changes require confirmation.
12. Normal actions do not require unnecessary confirmation.
13. Navigation always shows the current location.
14. UI components look like parts of one product.
15. The app remains usable on normal laptop displays.

---

# 68. Scope Rule for Codex

When implementing a new feature:

1. Reuse existing design components first.
2. Add a new reusable component only if needed.
3. Do not create a unique visual style for one page.
4. Add loading, empty, error, and success states as part of the feature.
5. Ensure background work does not block the UI.
6. Use consistent terminology.
7. Add tests for behavior, not just the happy path.
8. Do not redesign unrelated screens unless necessary.

A feature is not complete if only the successful loaded state exists.

Every data-driven feature should account for:

```text
loading
loaded
empty
error
offline/unavailable where relevant
```

---

# 69. Final Design Principle

The Fuel Cell Project Hub should feel like a quiet, competent engineering assistant.

The interface should not demand attention.

It should make the current state of the project obvious, make the next action easy, and get out of the way.

Polish comes from consistency, spacing, feedback, and predictable behavior, not from adding more visual effects.
