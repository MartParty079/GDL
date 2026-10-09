# Local team identity and measured activity (0.5.0 Beta)

This development order replaces hosted desktop authentication. No Supabase or
Microsoft identity endpoint is called. Windows OneDrive sign-in and file ACLs
are unchanged. Historical Supabase projects, migrations, functions and remote
records are retained; they are not deleted, migrated or modified by this order.
The old desktop authentication modules and packaged public endpoint files are
retired. Existing local token files, meeting caches and old outboxes are left
intact. Old hosted user IDs are not guessed or silently attributed to new users.
The Admin's **Preserved hosted history** button opens existing local cached records read-only with their original IDs. Use the prior Stable application or the project owner's Supabase dashboard for
those historical remote records. A validated export and explicit ID mapping are
required before any later history migration.

## Everyday use

Install the published **Beta installer**, then open GDL Research Hub Beta.
Select Matthew Kime, Andrew Michelson, Monterrius Ridley or Ryan Rodriguez.
Each initial profile has a permanent UUID independent of its display name.
Members can open the workspace without a PIN until they choose one.
On the initial profile writer, select **Set up Admin PIN**, enter and confirm
four to six digits, and save the one-time recovery code privately. Matthew's
Admin profile cannot log in or open administrative functions without its PIN.
There is no default Admin PIN. Do not send PINs or recovery codes to Codex.

The header shows the current name and role. Its menu contains **Change my PIN**
and **Switch User / Sign Out**. Remember selection is local to this edition and
device. Automatic login is available only to Members without a PIN; Admin and
PIN-protected Members always authenticate. A PIN change clears eligibility for
automatic login on the next launch. Five failed PIN attempts trigger a persistent
one-minute wait. PINs and recovery codes use PBKDF2-HMAC-SHA256, random 128-bit
salts and 600,000 iterations. Research files are never encrypted with these PINs.

Admin can add Members, rename/deactivate profiles, reset Member PINs, view team
activity, and configure storage/indexing. Members retain research editing,
experiments, samples, images, procedures, meetings and personal reports; their
storage/indexing settings are disabled. Roles are organizational controls.
Someone with direct write access to the profile JSON can change it; use university
OneDrive permissions to control file access.

## Storage and writer procedure

Development and Beta now use isolated profile-contained research sandboxes.
This **supersedes the earlier permission to map Beta directly to the live project**.
An older Beta live mapping is backed up under its local `migration-backups` and
disconnected. Production research files and `.project_hub` snapshots are never
edited, copied, moved or deleted by that migration. Existing Stable remains usable.
Copy representative test files into Beta's **Project / Settings / Storage** paths.
The previously published legacy index remains available in the existing Stable
workspace; this Beta deliberately does not open the live production index.

Identity transport is under the configured shared-storage directory:

```
AppData/<channel>/Users/profiles.json
AppData/<channel>/Configuration/Backups/<revision>-<uuid>.json
AppData/<channel>/Activity/Events/<uuid>.json
AppData/<channel>/Activity/Sessions/<session-id>-<snapshot-uuid>.json
AppData/<channel>/Meetings/<meeting-id>-<revision>-<uuid>.json
```

Changing shared-storage mapping as Admin copies only channel identity/activity/meeting transport into an existing destination, with conflict checks and profiles published last. Original files are preserved; research files and databases are not moved.

The channel is `development`, `beta` or `stable`. The current Beta locations must
remain inside its own local profile; live production OneDrive is rejected. A
future approved Stable build can use the existing university OneDrive project
selected in its per-user storage configuration. Paths are resolved from that
configuration, never from a hardcoded Windows username. No new research project
root is implicitly created. Missing configured roots block first profile load.

Only the device recorded as `writer_device` may change profiles or PINs. All
users may change their own PIN **on that designated profile writer**; other
computers display an explanation to contact the Admin. Admin profile management
also stays on that writer. Revision checks, local OS locks, atomic replacement
and revision backups preserve concurrent edits. OneDrive conflict JSON copies
block profile changes and require owner comparison, not last-writer-wins.
OS locks do not provide distributed OneDrive fencing. Never clone the writer's
local profile to another computer or appoint another writer while it may return
online. Writer transfer requires retiring the old device, backing up profiles,
resolving sync conflicts and changing the writer identifier under owner control.

Activity queues under the local edition's `identity/outbox` while the configured
root is unavailable. A background retry runs every minute and at logout. Files
have unique IDs and atomic writes; retries deduplicate event IDs. Session snapshots
are immutable on shared storage and reports select the most recent absolute
snapshot per session. Local UI meeting SQLite caches remain local, never in
OneDrive; shared meetings use immutable revisions. Conflicting same-number
meeting revisions are reported for manual comparison, never silently merged.
OneDrive being available locally does not prove that its cloud sync is complete.
The app detects missing roots, unreadable files and conflict copies, but cannot
promise cloud propagation time or inspect the OneDrive client's private status.

## PIN recovery

Use **Recover Admin PIN** on the designated writer and enter the saved private
recovery code. Choose and confirm a new PIN. Recovery rotates the code and shows
its replacement once; the old code stops working. Keep it outside shared project
files. If both PIN and recovery code are lost, the OneDrive folder owner must
retire active writer sessions, make a backup, and restore a verified profile
backup with a known PIN/recovery code. Do not delete profiles or regenerate user
IDs to recover access. If no verified backup is usable, request an owner-approved
recovery that resets only the Admin hash while preserving IDs and activity.

## Activity and weekly reports

**Admin · User Activity** shows per-person logins, sessions, estimated focused
active time, files added by explicit app actions, experiment/sample changes,
procedure revisions and individual event details. Filter user, UTC dates and
action category. **My Activity** restricts Members to their own events.
**Weekly Activity** generates individual PDFs/CSV and an Admin combined team PDF.
Team active time sums each person's measured active intervals; per-person
overlapping sessions are merged. Session duration is estimated through the last
persisted heartbeat after a crash. Idle cutoff is 15 minutes. Background or
outside-application time does not count as focused active time. No productivity
score is calculated. Externally discovered files have no assigned contributor.
Processing metrics count completed processing runs, not invented image counts.
Earlier hosted history is not relabeled as local activity.

## Release stages and updates

Running source (`python -m app.main`) defaults to **Development**, with its own
FuelCellProjectHubDevelopment profile and automatic UTC `-dev.N` identifier.
It never checks a Beta or Stable installer feed; rerun current `develop` source
to test a new Development build. Release tests explicitly select Beta metadata.
Beta CI builds immutable `-beta.N` packages from clean `develop` commits. Beta
and Stable retain distinct installer IDs, installation folders, profiles, icons,
protocols and update feeds. Stable installer/asset names are unchanged for older
updaters. The original production application and data are not replaced here.

Check for Updates supports Update Now, Next Open and Skip This Version. Manual
checks can show a skipped version again. SHA-256 and installer structure are
verified, active writes drain cooperatively, and pending state remains on failure.
Starting an installer is not reported as success. On a subsequent launch, the
running edition/version must meet the pending target before a `version_verified`
receipt and application-updated event are recorded. Installer failures preserve
the old version and retain retry state. Windows installers remain unsigned until
the maintainer configures signing credentials; SmartScreen may warn. Confirm the
official repository and published checksum rather than disabling system security.

Stable publication requires the exact tested Beta/SHA and a fresh affirmative
answer to the question documented in CODEX_WORKFLOW.md. Codex performs dispatch,
sole-maintainer review and publication after approval; no manual GitHub commands
are required. A rejection or missing/mismatched confirmation prevents dispatch.
This order publishes Beta only. Production data migration and any historical-ID
mapping must be reviewed before proposing Stable promotion.
