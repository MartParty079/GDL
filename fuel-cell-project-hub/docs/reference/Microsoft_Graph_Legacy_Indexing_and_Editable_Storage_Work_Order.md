# WORK ORDER: Microsoft Login + Graph Cloud Indexing + Legacy Data Classification + Editable Storage Paths
## Fuel Cell Project Hub

## 1. Objective

Add Microsoft account authentication and Microsoft Graph support to Fuel Cell Project Hub so the app can connect to university Microsoft 365 storage, index previous OneDrive/SharePoint project data without downloading all file contents, classify that indexed data into the correct application categories, and clearly separate or label the imported material as **Old Test Data / Legacy Project Data**.

This work order also fixes a current usability problem: the user must be able to change and reconfigure the local shared-storage path, cloud storage reference, and related project storage locations from the app at any time.

This work order combines:

1. Microsoft sign-in
2. secure Microsoft Graph authentication
3. SharePoint/OneDrive project discovery
4. metadata-only cloud indexing
5. hybrid local/cloud storage support
6. automatic file classification
7. sample/experiment/run/procedure relationship inference
8. dedicated handling of legacy/old test data
9. editable local shared-storage configuration
10. editable cloud storage configuration
11. clear UI separation between current project data and historical imported data
12. clean error handling, loading states, and offline behavior

The project should support indexing old data without forcing every file to download locally.

---

# 2. Core User Goal

The intended user experience is:

Open Fuel Cell Project Hub
→ Sign in with Microsoft
→ Connect university OneDrive/SharePoint
→ Select a previous project folder
→ Choose "Import as Old Test Data"
→ App scans cloud metadata only
→ Files are classified into app categories
→ Historical data becomes searchable and filterable
→ No bulk download occurs

The user should also be able to go to Storage Settings at any time and change:

- local synced project folder
- shared local storage path
- current-project storage root
- old-test-data local cache location
- Microsoft cloud project/library connection
- default input folder
- default output folder
- archive folder
- reports folder

No path should be permanently locked after first setup.

---

# 3. Core Architectural Rule

Use three clean layers:

Fuel Cell Project Hub UI
        ↓
Microsoft Auth + Graph Services
        ↓
Project Storage + Indexing + Classification

The UI must not directly:
- handle raw OAuth tokens
- call Graph endpoints
- parse cloud file structures
- perform file classification logic

Use services/providers.

---

# 4. Storage Modes

Support three conceptual storage modes:

## Local Only

Uses locally synced OneDrive/SharePoint folders.

## Cloud Only

Uses Microsoft Graph metadata and web URLs without downloading files.

## Hybrid

Uses Graph for cloud metadata and stable IDs while using local files when they are available.

Preferred long-term default:

Hybrid

Legacy project imports may initially operate in:

Cloud Only

to avoid downloading historical data.

---

# 5. Editable Storage Is Mandatory

The application must provide a real storage-management interface.

Do not treat the first selected storage path as permanent.

Users must be able to edit storage configuration later without modifying JSON, INI files, Python source, or registry values manually.

Add:

Settings
→ Storage

This page is the authoritative UI for changing storage.

---

# 6. Storage Settings UI

Create a dedicated Storage settings page with separate sections.

## Current Project Storage

Fields:

Project Name
Local Shared Storage Folder
Online SharePoint / OneDrive URL
Storage Mode
Project Root Status

Actions:

[ Browse ]
[ Change Folder ]
[ Open Folder ]
[ Open Online ]
[ Validate ]
[ Reset ]

## Project Data Folders

Editable relative paths:

Procedures Folder
Samples Folder
Experiments Folder
Raw Data Folder
Processed Data Folder
Analysis Folder
Reports Folder
Reference Folder
Exports Folder
Archive Folder

Actions per row:

[ Browse ]
[ Reset to Default ]
[ Open ]

## Legacy / Old Test Data

Fields:

Legacy Index Cache Location
Legacy Project Metadata Location
Optional Local Legacy Storage Root

Actions:

[ Browse ]
[ Open ]
[ Reset ]

## Microsoft Cloud Storage

Fields:

Connected Account
Site
Document Library
Project Folder
Cloud Storage Status

Actions:

[ Connect ]
[ Change ]
[ Disconnect ]
[ Open Online ]
[ Test Connection ]

---

# 7. Local Shared Storage Path

The local shared-storage path must be editable.

Store the user's local project root in local machine state only.

Example:

{
  "local_project_root": "C:\\Users\\Matthew\\OneDrive - University\\Fuel Cell Capstone"
}

Do not store this absolute path in shared project metadata.

If the user changes the local shared-storage path:

1. validate the new folder
2. check for project marker
3. show what will change
4. update local path
5. rebuild or refresh local index as needed
6. preserve shared project metadata
7. do not move files automatically

---

# 8. Change Storage Folder Workflow

When the user clicks:

Change Folder

show:

Select Local Shared Storage Folder

After selection, validate:

- folder exists
- folder is readable
- folder is writable where required
- folder is not system root
- folder is not arbitrary user home root
- folder contains expected project marker or known folders, if available

Then show:

New Project Storage Found

Path:
C:\...

Status:
Valid project structure

[ Cancel ]
[ Use This Folder ]

If it is an empty folder:

This folder does not appear to contain a Fuel Cell Project Hub structure.

[ Cancel ]
[ Initialize Project Here ]

Never silently initialize unrelated folders.

---

# 9. Storage Reconfiguration Safety

Changing the local path must not:

- delete files
- move files
- rename files
- erase cloud configuration
- erase project metadata
- erase old test data records

It only changes the local storage mapping.

---

# 10. Relative Path Rule

Shared project references must remain relative.

Example:

05_Processed_Data/Experiment_A/results.xlsx

not:

C:\Users\Matthew\OneDrive - University\Fuel Cell Capstone\05_Processed_Data\Experiment_A\results.xlsx

At runtime:

absolute_path = local_project_root + relative_path

This is mandatory for portability across team members.

---

# 11. Local vs Shared Configuration

Store locally:

local_project_root
local legacy cache location
local software paths
auth token cache
machine-specific temp folders

Store as shared project metadata:

cloud site ID
cloud drive ID
cloud root item ID
project-relative folder structure
legacy project definitions
classification rules
shared resource definitions

Never synchronize machine-specific absolute paths.

---

# 12. Storage Status

Storage settings should show clear status.

Examples:

Local Shared Storage
Connected

Cloud Storage
Connected

Legacy Cache
Ready

or:

Local Shared Storage
Needs Attention

The saved folder is no longer available.

[ Locate Again ]

---

# 13. Storage Dashboard Summary

The main dashboard may show a compact storage card:

Storage

Local       Connected
Cloud       Connected
Files       1,248 indexed
Last Sync   10:42 PM

Actions:

[ Open ]
[ Manage Storage ]

Do not put every path on the dashboard.

---

# 14. Microsoft Authentication Method

Use Microsoft Authentication Library (MSAL) for Python.

Preferred:

MSAL Public Client Application

Use the official Microsoft desktop/native browser sign-in flow.

Do not:
- collect Microsoft passwords
- embed a custom password form
- ship a client secret in the app

Authentication must use Microsoft's official sign-in experience.

---

# 15. Microsoft Entra Application Registration

Create or use an application registration named:

Fuel Cell Project Hub

Recommended type:

Public client / native desktop application

Do not use a confidential client secret.

Configuration should support:

{
  "client_id": "",
  "tenant_id": "",
  "authority_mode": "organizations"
}

Use a tenant-specific authority later if the university environment requires it.

---

# 16. Microsoft Graph Permissions

Start with the minimum delegated permissions required.

Suggested initial permissions:

User.Read
Files.Read
Sites.Read.All

Do not request:
- mail
- calendar
- Teams chat
- write permissions

unless separately approved and required.

Potential later permissions:

Files.ReadWrite
Sites.ReadWrite.All

These are outside the scope of this work order.

---

# 17. Admin Consent Handling

Some university tenants may require admin approval for SharePoint permissions.

The app must handle this cleanly.

Example:

Microsoft access requires university approval.

Your account signed in successfully, but the requested SharePoint access has not been approved by your organization.

[ Continue with Local Storage ]
[ View Details ]

Do not crash the application.

---

# 18. Microsoft Authentication Service

Create:

app/services/microsoft_auth.py

Responsibilities:

sign_in()
sign_out()
get_account()
get_access_token()
refresh_token()
get_connection_status()
clear_cached_session()

Do not put authentication logic in window.py.

---

# 19. Microsoft Graph Service

Create:

app/services/microsoft_graph.py

Responsibilities:

get_me()
list_drives()
list_sites()
list_document_libraries()
list_children()
get_drive_item()
get_item_metadata()
get_item_web_url()

Later:

delta queries

Keep raw Graph request handling isolated here.

---

# 20. Token Storage

Never store raw access or refresh tokens in:

- project.json
- OneDrive shared folders
- GitHub
- plain-text config
- activity history

Use MSAL token cache.

Protect local cache with:

Windows Credential Manager
or
DPAPI-protected local storage

Preferred local location:

%LOCALAPPDATA%\FuelCellProjectHub\auth\

Authentication data must never sync through OneDrive.

---

# 21. Authentication States

Support:

Signed Out
Signing In
Connected
Token Expired
Needs Consent
Unavailable
Error

The UI must show these states clearly.

---

# 22. Microsoft Account Settings UI

Add:

Settings
→ Microsoft Account

Signed-out state:

Microsoft Account
Not connected

Connect your Microsoft 365 account to browse approved OneDrive and SharePoint project files.

[ Sign in with Microsoft ]

Connected state:

Microsoft Account
Connected

Display Name
Email / UPN
Organization / Tenant

Actions:

[ Test Connection ]
[ Reconnect ]
[ Sign Out ]

---

# 23. First-Launch Behavior

Microsoft sign-in must be optional.

The user must still be able to continue with:

Local Storage

The app should not become unusable if:
- Graph access is blocked
- university consent is delayed
- internet is unavailable

---

# 24. Identity

After login, retrieve:

Display Name
User Principal Name
Microsoft User ID
Tenant ID

Use Microsoft User ID as the stable identifier where appropriate.

Do not rely on email alone as permanent identity.

---

# 25. Activity Attribution

Once Microsoft identity is available, activity events may record:

user_id
display_name
timestamp

Example:

Matthew Kime imported legacy GDL project data.

If the user is signed out:

Local User

may be used temporarily.

---

# 26. Storage Provider Architecture

Extend:

ProjectStorageProvider

with:

LocalOneDriveProvider
MicrosoftGraphProvider

The UI should not care which provider is active.

Suggested provider methods:

list_items()
get_item()
get_metadata()
open_item()
refresh()
exists()
get_children()

---

# 27. MicrosoftGraphProvider

Create:

app/services/storage/microsoft_graph_provider.py

Responsibilities:

connect()
list_children()
get_item()
get_metadata()
open_item()
refresh()

For cloud-only files:

open_item()

should initially open the Microsoft web URL.

Do not download files automatically.

---

# 28. Connect Microsoft Storage

Add:

Settings
→ Storage
→ Connect Microsoft Storage

Flow:

Sign in
→ Choose SharePoint site
→ Choose document library
→ Choose project folder
→ Save reference

Do not require manual entry of:
- site ID
- drive ID
- item ID

---

# 29. Change Microsoft Storage

The Microsoft cloud storage connection must also be editable.

Add:

[ Change Cloud Storage ]

Flow:

Current connection shown
→ Browse sites/libraries again
→ Select replacement
→ Validate access
→ Confirm change

Changing cloud storage must not erase local project files.

Show confirmation if the change affects the active project source.

---

# 30. Stable Cloud References

Store:

{
  "provider": "microsoft_graph",
  "site_id": "...",
  "drive_id": "...",
  "root_item_id": "...",
  "web_url": "..."
}

Stable Graph IDs must be primary.

Do not store only a URL or display name.

---

# 31. Metadata-Only Cloud Indexing

The indexer must be able to recursively scan cloud project structure using Graph metadata without downloading file contents.

For each item, retrieve only available metadata such as:

name
item_id
parent_id
drive_id
size
created date
modified date
web URL
folder/file type
relative path

Do not:
- download file contents
- hash file contents
- inspect image pixels
- inspect PDF contents
- open Excel files
- read video metadata

during initial indexing.

---

# 32. Cloud File Record

Graph-backed file records should support:

{
  "provider": "microsoft_graph",
  "drive_id": "",
  "item_id": "",
  "parent_id": "",
  "name": "",
  "relative_path": "",
  "extension": "",
  "size": 0,
  "created": "",
  "modified": "",
  "web_url": "",
  "availability": "cloud_only",
  "category": "",
  "sub_category": "",
  "experiment_id": "",
  "run_id": "",
  "sample_id": "",
  "procedure_id": "",
  "data_origin": "legacy",
  "legacy_project_id": "",
  "legacy_note": ""
}

---

# 33. Legacy / Old Test Data Rule

Any project imported from a previous OneDrive/SharePoint location using the legacy import workflow must be explicitly identified as:

Old Test Data

Internally:

data_origin = "legacy"

This is mandatory.

Historical test data must never silently appear as current project data.

---

# 34. Legacy Project Record

Create a permanent record for each imported historical project.

Example:

{
  "legacy_project_id": "LEG-2026-001",
  "display_name": "Previous GDL Project",
  "source": "Microsoft Graph",
  "site_id": "...",
  "drive_id": "...",
  "root_item_id": "...",
  "imported_on": "...",
  "imported_by": "...",
  "note": "Old test data imported for reference and comparison.",
  "read_only_reference": true
}

Use permanent IDs.

Suggested prefix:

LEG-

---

# 35. Import Old Project Workflow

Add:

Project
→ Files & Data
→ Add Previous Project

or:

Settings
→ Storage
→ Add Previous Project

Flow:

1. Select Microsoft storage source.
2. Browse to old project folder.
3. Show confirmation screen.
4. Require or prefill a legacy note.
5. Import cloud metadata.
6. Classify indexed files.
7. Save legacy project record.
8. Display under Old Test Data.

Confirmation:

Import as Old Test Data

This project will be indexed for reference and comparison.
Its files will not be treated as current experimental data.

Default note:
Historical project data imported for reference only.

[ Cancel ]
[ Import Old Test Data ]

---

# 36. Legacy Data Separation

Old test data should be logically separated in the app.

Preferred:

Files & Data
├── Current Project
└── Old Test Data

or filters:

[ Current ]
[ Old Test Data ]
[ All ]

Do not physically move or duplicate legacy cloud files.

Separation is metadata/index-driven.

---

# 37. Visual Legacy Indicator

Every legacy item should display a subtle indicator.

Examples:

Old Test Data
Legacy
Historical

Use neutral gray or amber.

Do not use red unless there is an error.

---

# 38. Legacy Note

Each imported old project must include a project-level note.

Default:

Historical project data imported for reference and comparison. Do not treat as current project test results.

Allow editing this note later.

---

# 39. Read-Only Reference Behavior

For the first implementation, legacy cloud projects should be treated as read-only references inside the Hub.

The Hub may:

- index
- search
- categorize
- open
- reference
- compare

The Hub should not automatically:

- rename
- move
- delete
- reorganize
- overwrite

legacy cloud files.

---

# 40. Classification Pipeline

After indexing, every file must pass through a classification pipeline.

Classification order:

1. manual override
2. explicit metadata
3. known project folder context
4. known filename/path patterns
5. file extension
6. fallback to Other

Do not move the underlying file.

Classification modifies only index metadata.

---

# 41. Top-Level App Categories

Use these initial categories:

Image
Video
Sensor Data
Spreadsheet
Document
Procedure
Report
Code
CAD
Configuration
Reference
Other

Allow expansion later.

---

# 42. Folder Context Overrides

Folder meaning should override generic extension classification when it provides stronger meaning.

Examples:

01_Procedures/*.docx
→ Procedure

07_Reports/*.pdf
→ Report

04_Raw_Data/*.csv
→ Sensor Data

08_Reference/*.pdf
→ Reference

*.tif
→ Image

*.mp4
→ Video

A PDF inside Procedures should be Procedure, not generic Document.

---

# 43. Subcategories

Support subcategories where useful.

Suggested image subcategories:

Pre Imaging
Post Imaging
Microscopy
Processed Image
Threshold Result
Pore Map
Unknown Image

Suggested data subcategories:

Pressure
Flow
Temperature
Water Intrusion
Compression
Unknown Sensor Data

Suggested report subcategories:

Experiment Report
Lab Report
Analysis Report
Presentation
Reference Report

Do not over-classify if confidence is low.

---

# 44. Classification Confidence

Optional but recommended:

classification_confidence

Values:

high
medium
low

Examples:

folder context → high
clear extension + folder → high
filename guess → medium
extension only → medium
unknown → low

---

# 45. Relationship Inference

Infer:

experiment_id
run_id
sample_id
procedure_id

from structure and filenames where possible.

Example:

03_Experiments/E-20251010-A/R03/S-20251010-B/video.mp4

Infer:

experiment_id = E-20251010-A
run_id = E-20251010-A-R03
sample_id = S-20251010-B

For old data, retain legacy names if current IDs are absent.

Do not fabricate IDs.

---

# 46. Legacy IDs

If historical data lacks current project IDs:

Use:

legacy_reference
legacy_sample_name
legacy_experiment_name

Example:

{
  "sample_id": "",
  "legacy_sample_name": "GDL Sample A"
}

Later manual mapping may connect old names to current conventions.

---

# 47. Current vs Legacy Relationship Rule

Legacy experiments must not count toward current project metrics unless explicitly requested.

Examples:

Dashboard:
Experiments Running = current project only

Historical comparison:
may include legacy data when selected

---

# 48. Search Behavior

Global file search should support:

Current Project
Old Test Data
All

Search across:

name
relative path
category
sub_category
experiment
run
sample
procedure
legacy project name
legacy note

---

# 49. Filter Bar

Recommended filters:

[ Data Origin ▾ ]
[ Type ▾ ]
[ Experiment ▾ ]
[ Sample ▾ ]
[ Date ▾ ]
[ Legacy Project ▾ ]

Data Origin:

Current
Old Test Data
All

Default:

Current

---

# 50. Files & Data Page

Layout:

Search
Filters
Origin selector
File table

Columns:

Name
Category
Subcategory
Experiment
Sample
Origin
Modified
Size

Optional details pane:

Full relative path
Cloud/local availability
Legacy project
Legacy note
Web URL
IDs

---

# 51. Legacy Project Browser

Add:

Project
→ Old Test Data

Show historical projects as cards.

Example:

Previous GDL Project

Imported: Oct 7, 2026
Files indexed: 2,418
Size represented: 86.3 GB
Source: SharePoint
Status: Cloud Only
Note: Historical project data imported for reference.

[ Browse ]
[ Refresh Index ]
[ Open Online ]
[ Edit Note ]

---

# 52. Dashboard Behavior

Optional small card:

Old Test Data
2 legacy projects
3,812 indexed files

[ Browse ]

Do not include legacy data in current project progress metrics.

---

# 53. Data Origin Field

Add required:

data_origin

Allowed:

current
legacy
archive
external_reference

Legacy import must set:

data_origin = "legacy"

---

# 54. Legacy Project ID Field

Add:

legacy_project_id

to every imported legacy item.

---

# 55. Local Index Storage

Machine-generated indexes should remain local.

Preferred:

%LOCALAPPDATA%\FuelCellProjectHub\index\

Example:

current_index.json
legacy_LEG-2026-001_index.json

This prevents shared-write conflicts.

---

# 56. Shared Legacy Metadata

Shared project metadata may store:

legacy_projects.json

Do not store tokens or machine-specific paths.

---

# 57. Legacy Cache Location Must Be Editable

The local location used for:

- cached legacy indexes
- thumbnails, if added later
- cached Graph metadata
- temporary legacy working files

must be editable from:

Settings
→ Storage
→ Old Test Data

Default:

%LOCALAPPDATA%\FuelCellProjectHub\legacy\

Allow:

[ Browse ]
[ Open ]
[ Reset ]

Do not silently move existing cache without warning.

If changed, offer:

Use New Location

or optionally:

Move Existing Cache

but never move automatically.

---

# 58. Index Refresh

Support:

Refresh Current Index
Refresh Legacy Index
Rebuild Current Index
Rebuild Legacy Index

Keep these separate.

Do not accidentally merge legacy and current index records.

---

# 59. Delta Sync Preparation

Design legacy project records for:

delta_link

Future refresh:

full metadata scan
→ save delta link
→ update only changes

Do not require full delta implementation immediately.

---

# 60. File Availability

Support:

Local
Cloud Only
Available Online
Unavailable

Legacy imports will commonly be:

Cloud Only

Opening them should use web_url unless local copy exists.

---

# 61. Hybrid Matching

If a legacy project is locally synced later, optionally match cloud records to local files.

Use:

drive_id
item_id
relative_path

Do not require this initially.

---

# 62. Open Behavior

Cloud-only:

Open
→ Microsoft web URL

Local/hybrid:

Open
→ local file

Fallback:

web URL

Do not bulk-download during browsing.

---

# 63. No Automatic Download

The indexer must never bulk-hydrate cloud-only legacy data.

Do not:

read file contents
hash contents
inspect media internals
download for classification

Metadata-only means metadata-only.

---

# 64. Storage Migration UX

If the user changes their current local shared storage path, show:

Change Local Storage

Old:
C:\Old\Path

New:
D:\New\Path

This only changes where the app looks for locally synced project files.
Files will not be moved automatically.

[ Cancel ]
[ Use New Path ]

If desired later:

[ Move Local Files ]

must be a separate explicit workflow.

Do not combine path changes with file moves.

---

# 65. Storage Reset

Provide:

Reset Local Storage Configuration

This should reset only the saved mapping.

It must not delete project files.

Confirmation:

Reset local storage mapping?

This removes the saved local folder from Fuel Cell Project Hub.
It does not delete any files.

[ Cancel ]
[ Reset ]

---

# 66. Error Handling

Handle:

Microsoft sign-in failed
Admin consent required
Site unavailable
Library unavailable
Permission denied
Project folder removed
Local shared path unavailable
Token expired
Network offline
Index interrupted
Malformed metadata
Classification failure

One file failure must not fail the entire import.

---

# 67. Partial Import Handling

If indexing partially fails:

Old test data index completed with warnings.

2,416 files indexed
3 items skipped

[ View Details ]

Keep successful records.

---

# 68. Offline Behavior

If offline:

- cached legacy index remains searchable
- local files remain usable
- cloud-only files show unavailable
- Graph refresh is disabled
- current local OneDrive functionality remains usable

---

# 69. Loading UX

Follow the Project Hub design language.

Use skeleton placeholders while:

- loading account info
- listing sites
- browsing document libraries
- validating storage
- indexing metadata
- classifying files

For long imports:

Indexing Old Test Data…
1,842 files discovered
1,790 classified

Do not freeze the UI.

---

# 70. Classification Progress

Show phases:

Connecting…
Scanning metadata…
Classifying files…
Building relationships…
Saving index…
Complete

---

# 71. Empty States

Example:

No old test data imported

Connect a previous OneDrive or SharePoint project to make historical test data searchable without downloading it.

[ Add Previous Project ]

---

# 72. Legacy Warning Copy

Use consistently:

Old Test Data

This data comes from a previous project and is retained for historical reference and comparison. It is not part of the current project test record unless explicitly linked.

---

# 73. Manual Reclassification

Allow later manual correction.

Fields:

Category
Subcategory
Experiment
Sample
Procedure
Legacy Note

Manual values override automatic classification.

Do not rename or move the source file.

---

# 74. Classification Rules Service

Create:

app/services/file_classifier.py

Responsibilities:

classify()
infer_category()
infer_subcategory()
infer_relationships()
apply_override()

---

# 75. Classification Rules Config

Create:

config/file_classification.json

Example:

{
  "folder_rules": {
    "01_Procedures": "Procedure",
    "07_Reports": "Report",
    "04_Raw_Data": "Sensor Data"
  },
  "extensions": {
    ".tif": "Image",
    ".tiff": "Image",
    ".png": "Image",
    ".mp4": "Video",
    ".csv": "Sensor Data",
    ".xlsx": "Spreadsheet",
    ".docx": "Document",
    ".pdf": "Document",
    ".py": "Code"
  }
}

---

# 76. Classification Precedence

Use:

manual override
→ explicit metadata
→ folder rule
→ known filename pattern
→ extension
→ Other

Never let lower-priority logic overwrite a higher-priority decision.

---

# 77. Microsoft Login Tests

Add tests for:

1. signed-out state
2. successful sign-in
3. account identity retrieval
4. token refresh
5. reconnect
6. sign-out
7. admin consent failure
8. network failure
9. token cache clearing
10. secure log redaction

---

# 78. Graph Tests

Add tests for:

1. list sites
2. list drives
3. list libraries
4. list folder children
5. metadata-only enumeration
6. cloud-only record creation
7. web URL
8. access denied
9. missing library
10. offline fallback

---

# 79. Storage Configuration Tests

Add tests for:

1. change local shared-storage path
2. validate new project root
3. reject invalid folder
4. initialize empty folder only after confirmation
5. relative paths remain intact
6. local absolute path remains machine-local
7. reset local mapping
8. cloud storage change
9. cloud disconnect
10. legacy cache path change
11. no files moved during path change
12. no files deleted during reset

---

# 80. Legacy Import Tests

Add tests for:

1. create LEG ID
2. save legacy project note
3. data_origin = legacy
4. legacy_project_id on all imported files
5. no current metrics contamination
6. cloud-only items remain cloud-only
7. cancel import
8. partial import recovery
9. duplicate detection
10. refresh legacy project

---

# 81. Classification Tests

Add tests for:

1. image extension
2. video extension
3. spreadsheet extension
4. report folder override
5. procedure folder override
6. sensor-data folder override
7. unknown fallback
8. manual override precedence
9. experiment ID inference
10. sample ID inference
11. run ID inference
12. legacy origin preserved
13. no moves
14. no renames

---

# 82. Real Validation

On a real university account verify:

1. sign in
2. Graph access
3. browse SharePoint/OneDrive
4. select old project folder
5. import as Old Test Data
6. no bulk download
7. cloud-only files remain cloud-only
8. files classify correctly
9. legacy files appear under Old Test Data
10. current project remains separate
11. search can include legacy
12. opening cloud-only file uses Microsoft web view
13. refresh does not bulk-download
14. local shared-storage path can be changed
15. app successfully resolves project-relative paths after path change
16. cloud project connection can be changed
17. old test data cache location can be changed

---

# 83. Required New Files

Recommended:

app/services/microsoft_auth.py
app/services/microsoft_graph.py
app/services/file_classifier.py
app/services/path_registry.py
app/services/storage/microsoft_graph_provider.py

config/microsoft_auth.json
config/file_classification.json

tests/test_microsoft_auth.py
tests/test_microsoft_graph.py
tests/test_storage_settings.py
tests/test_legacy_import.py
tests/test_file_classifier.py

docs/microsoft_login.md
docs/legacy_data_import.md
docs/storage_configuration.md

---

# 84. Documentation

Create:

docs/storage_configuration.md

Include:

Local shared storage
Changing project root
Relative-path behavior
Cloud storage connection
Changing cloud project
Legacy cache location
Reset behavior
Safety rules
Troubleshooting

Create:

docs/legacy_data_import.md

Include:

Why old data is separated
How to import previous projects
Metadata-only indexing
Classification
Legacy notes
Search/filter behavior
Offline behavior

---

# 85. README Update

Add:

## Editable Storage

Fuel Cell Project Hub allows each user to change their local synced project root at any time.

Absolute local paths remain machine-specific. Shared project references use relative paths.

Changing the saved path does not move or delete files.

## Old Test Data

Previous OneDrive/SharePoint projects can be indexed through Microsoft Graph without bulk downloading the project.

Imported historical data is clearly labeled as Old Test Data and kept separate from current project records.

The Hub classifies indexed files by type and project context without moving or renaming the source files.

---

# 86. Non-Goals

Do not implement in this work order:

- bulk cloud downloads
- automatic legacy migration
- automatic file moves
- automatic renaming
- deleting cloud files
- Graph write access
- semantic AI classification
- OCR
- document-content parsing
- moving local storage automatically
- database migration

This is metadata-first and read-only for legacy data.

---

# 87. Recommended Implementation Phases

## Phase 1 — Editable Storage

- Storage settings page
- change local shared root
- relative path validation
- cloud storage selection/change
- legacy cache location
- safe reset

## Phase 2 — Microsoft Login

- Entra app
- MSAL
- sign in/out
- identity
- secure token cache

## Phase 3 — Graph Browsing

- sites
- libraries
- folders
- metadata listing

## Phase 4 — Legacy Import

- select old project
- create LEG project
- note
- metadata-only index

## Phase 5 — Classification

- file classifier
- categories
- subcategories
- relationship inference

## Phase 6 — UI Integration

- Current / Old Test Data separation
- filters
- legacy project browser
- storage status

## Phase 7 — Tests and Packaging

- mocked tests
- real university account
- packaged EXE validation
- offline behavior
- documentation

---

# 88. Final Acceptance Criteria

The work is complete when:

1. I can change the local shared-storage path from Settings.
2. The app validates the new path.
3. Changing the path does not move or delete files.
4. Shared project references remain relative.
5. I can change Microsoft cloud storage.
6. I can sign in with my university Microsoft account.
7. The app can browse SharePoint/OneDrive.
8. I can select a previous project folder.
9. I can import it as Old Test Data.
10. The app indexes metadata without downloading all files.
11. Every imported file is marked legacy.
12. A legacy project note is saved.
13. Files are classified into app categories.
14. Legacy files do not pollute current project metrics.
15. Search can toggle Current / Old Test Data / All.
16. Cloud-only files open via Microsoft web URL.
17. Offline mode preserves cached indexes.
18. The old-test-data cache location can be changed.
19. No Microsoft tokens appear in shared config or logs.
20. The packaged application still supports all of the above.

---

# 89. Codex Instruction

Before implementation:

1. Inspect the current storage settings.
2. Identify why local shared storage cannot currently be changed.
3. Find every use of `project_folder`, `local_project_root`, and related storage settings.
4. Remove UI assumptions that storage is write-once.
5. Centralize storage path handling in a reusable PathRegistry/StorageSettings service.
6. Preserve existing user data.
7. Do not rewrite unrelated project logic.

Implement editable storage first, because Microsoft cloud and legacy indexing should build on a sane storage configuration rather than another immovable path.
