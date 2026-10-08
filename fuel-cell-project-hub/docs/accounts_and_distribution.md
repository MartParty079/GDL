# Accounts and Windows distribution — 0.3.0

Version 0.2.0 is replaced by 0.3.0. This adds team identity and distribution
while retaining the native research workspace. Microsoft authentication,
Entra, MSAL and Graph remain removed.

## Responsibilities

Supabase Auth manages passwords and sessions. Existing `profiles`,
`installations` and `activity_events` tables manage roles, installation versions
and meaningful Hub activity. SQLite retains file identity, search, research
objects, associations, metadata, history and caches. Windows/OneDrive retains
actual current and legacy files. App identity does not change filesystem or
OneDrive permissions and cannot prevent a permitted Windows user from opening
files outside the app.

## User flow

Install `GDLResearchHub-Setup.exe`, open GDL Research Hub and sign in with the
invited email/password account. The existing administrator is preserved. There
is no public signup screen or default password. The backend additionally rejects
profile provisioning for Auth users who have not been invited. An existing
approved profile is read directly; an invited user whose profile is missing
may provision only an active USER profile with the authenticated UUID/email.

Use **Use Invitation / Reset Link** to paste the original link from the account
email and set a password. **Forgot Password** requests the provider's reset
email without revealing whether an address exists. Mail delivery depends on the
project's Supabase email/SMTP configuration. No custom password hashing is used.

Saved sessions and the previously verified profile are encrypted using Windows
DPAPI for the current Windows user. Passwords are never saved. Sign Out clears
the encrypted session and revokes the current server session when reachable;
local research settings/indexes remain. Authentication calls run in background
threads with eight-second network timeouts. A restored session revalidates the
Auth user and database profile. Disabled accounts cannot enter the workspace.
Connected sessions recheck every five minutes; loss of access locks the UI and
signs out after background work finishes.

Previously validated sessions can use local research offline for up to 24 hours.
The account control displays OFFLINE; admin operations are disabled. This is a
bounded local grace period, so remote disabling cannot take effect immediately
on an offline client. First login and recovery require connectivity.

New profiles detect the available default research folder or present **Locate
Research Folder**. Advanced path configuration remains in Settings. Existing
personal paths are preserved and never shipped in the installer.

## Administration

An active ADMIN receives Overview, Users, Activity, Installations and System
tabs. Users can be invited, enabled/disabled and assigned USER/ADMIN roles.
Role changes require confirmation. A database trigger prevents disabling or
demoting the last active administrator, including simultaneous update requests.

Every `hub-admin` request requires a verified Auth JWT, a fresh database profile
lookup and `role=admin, active=true`. Client role fields and editable Auth user
metadata are not trusted. Privileged Auth and database credentials stay in
Supabase-managed function secrets. The desktop ships only the publishable key.
Normal users cannot invoke admin operations, update profiles/roles, read other
users' rows or fabricate server-generated administrative audit event types.

Activity has user/event/date/entity/version filters and 100-row pages.
Installation labels are user-selected; install IDs are random UUIDs, not
hardware fingerprints. Shared Windows installations support different users
through the unique `(user_id, install_id)` key. Last seen reflects application
starts, not proof that a computer is currently online. Activity is client-reported
usage information, not a tamper-proof forensic record.

## Activity and privacy

Login/logout, app starts/updates, explicit file/Explorer actions, image and
legacy views, sample/experiment views and saves, metadata/tag changes,
index starts/completions/failures and settings saves produce bounded events.
Administrative invitations, status and role changes are generated server-side.
Events contain logical IDs, filenames, version and small allowlisted details.
Full local paths, private notes, document text, images, passwords and tokens
are excluded. No system-wide activity, screenshots or keystrokes are collected.

Failed sends remain in a local outbox capped at 500 events. Retry runs on later
activity and account rechecks, in batches of 50, for the matching signed-in
user only. Delivery is best effort; ambiguous network failures can duplicate
events. The initial retention recommendation is 180 days; automatic deletion
is deliberately not enabled. Administrators should select and document a
retention policy before configuring scheduled pruning.

## Backend source and deployment

`config/accounts_public.json` contains the existing GDL Capstone project's
client-safe URL and publishable key. Developer overrides are `SUPABASE_URL`
and `SUPABASE_PUBLISHABLE_KEY`; privileged keys are rejected. Normal installed
users do not configure Supabase. Do not put service keys, database passwords,
administrator passwords or GitHub tokens into source, environment templates
or the desktop package.

The two existing baseline migrations were retrieved from the project and
preserved. Three incremental migrations were applied: `accounts_admin`,
`activity_optional_name` and `invite_only_provisioning`. Existing rows remain.
All exposed tables retain RLS; private helpers have fixed search paths and
restricted grants. The deployed `hub-admin` function has JWT verification on.
Source-only pushes do not deploy database/function changes automatically.

Security Advisor found no new table/function/RLS findings. Its remaining Auth
warning is **Leaked Password Protection Disabled**; the project administrator
can review [Supabase password protection](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
Provider-wide public signup should also be disabled in Auth settings to reduce
unwanted Auth registrations; the application profile policy already denies
uninvited access independently of that provider setting.

## Windows install and updates

PyInstaller creates an onedir GUI package; Inno Setup wraps it in a per-user
installer. Default binaries live under LocalAppData/Programs/GDL Research Hub.
Existing mutable state stays under LocalAppData/FuelCellProjectHub (or the
developer-only FUEL_HUB_DATA_DIR override) to preserve earlier profiles. The
installer creates Start Menu shortcuts, an optional desktop shortcut, icon,
version metadata and an uninstaller. Upgrades/uninstall do not erase profiles,
indexes, tags, notes, relationships or research sources.

The source repository is PUBLIC. Clients check only official stable
MartParty079/GDL GitHub releases, cache startup checks for 24 hours and allow
manual checks. The header shows update status; the dialog shows release notes.
Numeric semantic comparison excludes older/equal versions and prereleases.
An update rechecks official release metadata, validates exact asset names/URLs,
downloads a bounded installer to the user updates folder and verifies its
required SHA-256 file before launching it and exiting. The running EXE is not
overwritten by the app. Installed users never run Git pulls or pip installs.

The Windows Actions workflow tests, checks the tag against the central version,
builds the package, runs isolated packaged startup checks, builds the installer
and checksum, and publishes only a successful version-tag build. Workflow
dispatch produces an artifact without publishing a release. Code signing hooks
use a certificate already in the signing machine's store through
`GDL_SIGNTOOL` and `GDL_SIGN_CERT_SHA1`; no signing credential is in source.
Current local installers are unsigned, so Windows SmartScreen may warn.

## Verification and limitations

The complete login-to-visible-workspace regression now covers the Qt acceptance
enum mistake found in the first 0.3.0 test build. The connected administrator's
encrypted session restored successfully, the Admin tab appeared and live
Overview, Users, Activity and Installations queries succeeded.
The administrator also confirmed the Admin tab in the corrected packaged
executable. The first 0.3.0 test package is superseded; use the corrected build
and installer in the `windows-gdl-hub-0.3.0-fixed` and `installer-0.3.0-fixed`
distribution directories.

The full unittest suite ran 205 tests: 203 passed and two reported explicit
skips. Source and packaged startup checks and the research workspace smoke
checks passed. The corrected installer installed into an isolated directory,
passed its installed startup check, and uninstalled successfully with its
executable removed. Existing personal state was retained.

A temporary normal Auth account was created through the authenticated admin
test flow and removed, including its profile, events and installation. Live
checks passed for normal login, USER role, uninvited provisioning denial,
admin endpoint denial, self-promotion denial, installation registration,
activity insertion, privileged audit spoof denial and disabled-account RLS.
The temporary acceptance branch was then removed from the deployed function.
Transactional RLS/last-admin checks also passed and rolled back all test rows.

The full legacy reconciliation retained 172,278 files with zero scan errors:
85,592 images, 1,195 reports/documents and 45,785 data files. It found 14,374
extensions without content extractors and 172,177 online-only files at scan
time. Those records remain browsable/openable. All file IDs, metadata overrides
and research objects matched the pre-change database backup.

Real **Holy GDL** search found 15,484 legacy records and 8,907 images; Current-only
found zero of those images. The real gallery, legacy filter, actual thumbnail
and selected image preview were exercised after a selected original downloaded
through OneDrive. Windows Open File and Explorer selection were dispatched to
the original; visual confirmation of the external windows remains a user check.
The corresponding legacy-view activity was recorded in the live backend.
No fake Holy GDL records/images or research-content uploads were used.

Local isolated installer install, installed startup and uninstall checks passed.
These ran on the developer computer, not a separate clean Windows machine.
A clean-account test, real published older-to-newer upgrade, invitation/reset
email delivery, and signing remain distribution acceptance checks. Source push
does not create a release or change other installed applications. No production
tag/release should be published until those remaining acceptance gates are met.

Supabase Security Advisor reports leaked-password protection disabled. Enable
it in the project's Auth settings when available; see the official
[password security guidance](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
