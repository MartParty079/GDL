# Updater and solo-maintainer release repair — 0.4.3 candidate

## Reproduced cause

The public latest-release API returned v0.4.2 as Stable with only
GDLResearchHubBeta-Setup.exe, its checksum and a Beta build manifest. The Stable
updater requires GDLResearchHub-Setup.exe. Running the unchanged v0.4.0 updater
against that live metadata reproduced its asset lookup failure before any
installer download. The generic UI hid the specific error. Existing application
logs did not record the download failure; this is a newly reproduced failure,
not a claim about every earlier attempt.

The v0.4.2 tag pointed to 74106a7382bd75cfe7c4a2d4b5ab1b3b0b1c6406,
while the Beta artifact manifest identified a401066bfa178082b1d497dd01536e02b98501f2
and version 0.4.2-beta.4. Renaming a Beta release does not build a Stable edition.
No binary was renamed or checksum fabricated. The malformed release was made
draft, preserving assets and tags. The old queued promotion was cancelled.
Stable discovery returned to v0.4.0. The unchanged original updater then fetched
and verified its actual 50,324,767-byte installer in an isolated test directory.
Its comparison used a simulated older installed version; no real user app was
replaced in that reproduction. Existing tags are never overwritten.

## Architecture and compatibility

PyInstaller packages a Windows x64 Python/Qt app. Inno Setup creates per-user
installers with distinct Stable/Beta AppIds, folders and protocols. This is a
custom GitHub REST updater, not Electron/Squirrel: it needs an installer and a
plain SHA-256 sidecar bearing that installer's exact filename. New release
validation also checks build-manifest.json for version, channel and source SHA.
Older Stable clients require no new metadata format or account/token to download
public releases. They can consume a correctly published newer Stable installer.

Authenticode is optional and currently no signing credentials are configured.
Unsigned installers remain unsigned: SHA-256 over HTTPS is required, but does
not constitute publisher signature verification. Signing credentials, if later
configured, stay outside source control. Installer staging remains under each
edition's local profile, never the shared research root. Updates preserve local
settings, encrypted sessions, indexes and OneDrive mappings and do not invoke an
index rebuild or move research files.

## Repairs and verification boundaries

Download failures record local diagnostics with stage, current/target version,
channel, HTTP status, expected/actual hashes and staging directory. Raw HTTP
exception URLs, signed redirect query strings and transport text are excluded.
The UI offers retry, details, deferred update and cancel. Startup failures allow
normal startup with the scheduled preference intact. An OS file lock serializes
downloads; an edition-specific Inno mutex serializes installer execution.
Cached installers are rehashed and launch requires a matching verified receipt.
Failed partial downloads are removed. Cooperative cancellation, saved editor
drafts, bounded activity flush and scientific-task deferral remain in place.

Both CI workflows validate actual generated installer bytes before publication
and fetch public release assets afterward. Stable post-publication validation
withdraws a malformed release and fails the workflow. Disposable Windows tests
use the actual installer with /GDLTESTINSTALL=1, disable global registration,
shortcuts and automatic normal startup, and restrict output to the temporary
gdl-installer-tests subtree. They check fresh installation, installed-edition
upgrade, packaged startup, installer version and preservation sentinels. Copying
an old installed package allows an old-to-new test without changing the owner's
installed registration. This does not replace testing a published Stable
candidate through an old client's real interactive update UI after approval.

## Solo developer and authorization

There are no main branch protections or rulesets imposing another review. The
actual blocker was the production environment's sole reviewer also being the
dispatch actor while prevent_self_review=true. The human explicitly approved
setting it to false. The named reviewer and deployment branch restrictions
remain. Production dispatch is restricted to MartParty079, requires an explicit
release-order phrase, exact tested Beta SHA/tag/run, matching workflow source,
successful tests and integrity checks. Ordinary develop pushes publish Beta only.

After presenting the exact validated candidate and receiving a subsequent human
Stable release instruction, run from the application directory:

```powershell
.venv/Scripts/python.exe tools/publish_stable.py --commit APPROVED_SHA --beta-tag TESTED_BETA_TAG --beta-run SUCCESSFUL_RUN_ID --production-release-order "APPROVE PRODUCTION RELEASE"
```

The helper dispatches the protected workflow and submits the same maintainer's
authorized review through GitHub's normal approval API. It refuses stale develop
commits, wrong actors and failed Beta runs. It never bypasses platform permission
checks. A dispatched/approved run is not a completed release: verify Actions,
main/tag SHA, public assets and updater checks before reporting success.
This repair order prepares 0.4.3; it does not itself publish that Stable release.
