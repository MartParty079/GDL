# Meetings and weekly contributions — 0.3.3

Previous version: 0.3.2. Chosen version: 0.3.3, PATCH, following the standing
per-work-order version rule. This extends the existing desktop Hub, accounts,
research index and activity records. It does not change Microsoft sign-in.

## Use

Open **Meetings** in the main tabs or research navigation. Create a meeting,
check attendance, attach a recording from a configured shared source, and add
notes, transcript text, action items and related samples/experiments/files.
Meeting types are editable. The list filters by date, type, attendee and origin;
search includes notes and transcripts. Linked meetings appear in research
timelines and global search.

Normal users open **My Weekly Activity**. Administrators open **Weekly
Contributions**, or use **Admin → Weekly Reports**. Choose one person or all
active team members, set the dates, and Generate. PDF and CSV export the selected
person. Generate All Team Reports creates a uniquely named PDF per active
profile. It does not send reports to anyone.

## Measured definitions

- A LOGIN event means a fresh password/provider authentication, not a restored
  session. Opening the app with an existing session starts a measured application
  session without adding a login. The existing Microsoft route remains unchanged
  and was explicitly excluded from acceptance testing at the user's request.
- Active time uses monotonic elapsed time and UTC intervals. Hub navigation,
  clicks, search/editor changes and audited research actions refresh presence.
  After 15 minutes without interaction, accumulation stops; it resumes on the
  next interaction. Losing focus to another program stops accumulation. Hub-owned
  modal dialogs remain eligible. No key events, keystrokes, pointer movement,
  coordinates, screenshots, clipboard contents or unrelated programs are logged.
- A report clips intervals to its date range and merges overlaps across
  installations, preventing overlapping sessions from doubling active time.
  The default range is local Monday midnight to the following Monday midnight,
  exclusive. Each endpoint uses its own local timezone offset, including DST.
- Files added count explicit app-created/copied files with
  `attribution=app_user_action`. Native scanner discoveries never receive that
  attribution. Import into Current Project and new exported meeting notes or
  transcripts are known additions. Attaching an existing file is a relationship,
  not an addition. File opens count FILE_OPENED once; category-specific audit
  events contribute their own metrics without doubling the file-open total.
- Sample/experiment totals use explicit IDs in object events and safe file audit
  context. Names are preferred in the top-sample summary. No scientific conditions
  or qualitative performance grades are inferred.
- Attendance is recorded explicitly. Present, Remote and Partial count as
  attended; Absent counts as missed. Excused entries are excluded from the rate.
  A person with no recorded attendance receives “Not recorded”, not 0%.
- Notes/transcript edits and action completion are credited to the person making
  the app action, not automatically to an action's assignee. Activity timestamps
  and compact timeline dates are UTC. Totals include all fetched records;
  the compact exported timeline shows at most 150 grouped entries.

## Persistence, storage and authorization

The additive Supabase migrations create user_sessions, meetings,
meeting_attendees and meeting_actions with RLS and explicit authenticated grants.
Session/activity reads are self-only or active database-verified administrators.
Shared meetings are readable by active project accounts; the creator or active
administrator can modify a meeting. No authorization comes from editable user
metadata. Anonymous users have no new table/RPC access. The team-roster RPC
returns only active IDs and display names, not private authentication records.

Recordings and other physical files remain in configured OneDrive research
sources. Shared metadata uses source labels and relative paths. The resolver
rejects traversal and paths escaping the configured source. Local absolute paths
are displayed only on this computer. No third-party recording uploads or automatic
recording occurs.

Sessions are saved as absolute durable snapshots in the local profile and
upserted by UUID; activity events have client UUIDs and idempotent inserts.
Meeting drafts use a user-scoped SQLite outbox. Transactional saves include
attendance/actions and reject stale revisions. Retrying the same mutation does
not increment the revision. Conflicts preserve the local draft; export it before
explicitly reloading the shared version. Other users' queued edits are never
submitted under the current account. Network failures leave local research usable.

## Acceptance evidence

Controlled source tests use fake passwords/transports and temporary shared-drive
fixtures. Database tests execute as authenticated roles with fixture JWT claims
inside a transaction that rolls back all fixture profiles and meeting/session
data. These are database authorization tests, not real-person browser logins.

| Weekly reporting check | Status | Evidence |
|---|---|---|
| Login/session counts | PASS | Two LOGINs and a restored APP_STARTED fixture remain distinct |
| Active time / idle exclusion | PASS | Controlled clock: idle cutoff, resume, focus exclusion and logout |
| File attribution | PASS | External scanner addition emits no FILE_ADDED; explicit copy does |
| Research/category metrics | PASS | Source records match the aggregate; unrelated user excluded |
| Meeting metrics / attendance rate | PASS | Present/Absent persists and reports 1/2, 50% |
| PDF / CSV export | PASS | Correct person/period/metrics extracted; rendered PDF pages reviewed |
| Generate All | PASS | Actual report UI produces two distinct person PDFs |
| Offline retry | PASS | Durable meeting/session snapshots, event UUID deduplication and conflicts |

| Meetings check | Status | Evidence |
|---|---|---|
| Creation / attendance | PASS | Source restart and live SQL RPC/RLS fixtures |
| Recording attachment | PASS | Portable shared-source reference, size/type and path round trip |
| Transcript import | PASS | TXT/MD, DOCX paragraphs/tables, extractable PDF fixtures |
| Transcript generation | NOT IMPLEMENTED | Modular service seam; generation button explains unavailability |
| Transcript editing / search / revisions | PASS | Saved text survives restart, search and later revision |
| Notes / action items | PASS | Save/reload and completion events |
| Related samples / experiments / files | PASS | Existing research objects and portable file-reference integration |
| Open / Show in Folder | PASS (dispatch) | Correct fixture path reaches the OS action; no media player launched |
| UI layout | PASS | Seven meeting tabs reviewed at 920px; research smoke at 1024px |

RLS: PASS — self reporting, administrator reporting, denied foreign edits,
disabled-account denial, anonymous grants, attendance/actions, conflict and retry
checks passed against the live database. All temporary fixture rows were removed
by rollback. Security Advisor: REVIEW REQUIRED — the pre-existing Auth leaked
password protection warning remains; no new security findings. New performance
findings (policy overlap and session FK index) were corrected. The existing
profile insert init-plan and duplicate activity-index warnings remain outside
this work order; newly created unused indexes are expected before production use.

## Limitations

- No bundled local speech model or automatic transcription. Import/edit/export
  transcripts works; no recording was uploaded or transcribed for acceptance.
- Active time exists only from 0.3.3 onward. Earlier events cannot yield a measured
  historical duration. Abrupt termination preserves time through the most recent
  one-minute snapshot, rather than inventing time after a crash.
- The existing activity outbox retains the most recent 500 queued actions; an
  extended outage beyond that limit can leave older event totals incomplete.
  Session snapshots and meeting drafts are durable independently of this cap.
- Offline reports require the hosted read service. Local work and draft editing
  remain usable; cached drafts are not a complete offline team report. Pending
  activity from the current installation is included after hosted records load;
  other offline installations appear after their own sync.
- Recording duration is not probed in this build. File type, size, shared location
  and meeting date are available. Playback uses the associated OS application.
- Transcript history retains the latest 20 prior revisions; large transcripts
  should remain linked shared files. Meeting JSON is limited to 500 KB.
- Cross-computer file resolution requires a unique matching source label and
  shared relative path. Shared notes/transcript export is optional and explicit;
  it is not automatically rewritten whenever a meeting is saved.
- Microsoft approval, live Microsoft login, clean-machine installation and real
  media-player playback were not tested. The installer is unsigned. A source push
  is not a GitHub Release or an automatic installed-app update.
- Running the account-window tests alone can trigger a Qt garbage-collection
  access violation after assertions complete. It reproduces with the pre-change
  account UI. The full regression suite and source startup check exit cleanly;
  isolated runs with this crash are not counted as successful process checks.

Automated verification: final broad run 220 tests (218 pass, 2 expected skips), excluding
ProductionIdentityTests. Subsequent targeted checks include the additional
DOCX/PDF transcript acceptance and meeting layout improvements. Research smoke:
21 screens. Source startup check verifies version/history and readable PDF export.
