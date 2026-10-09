# Development and production workflow

Repository: MartParty079/GDL. Default branch: develop. Stable branch: main.
Every work order is development only unless explicitly identified by the human
as a Production Release Order. Read repository AGENTS.md before repository work.
A previous release authorization does not authorize a new Stable release.

## Development work order

1. Inspect status, branch and origin; pull develop with --ff-only before edits.
   Preserve local work. Reconcile divergence; never reset/clean/force-push.
2. Implement on develop. Increment the canonical numeric version per work order
   with tools/bump_version.py. History is append-only. Beta build/display versions
   append -beta.N; CI assigns N from its run number for distinct corrected builds.
3. Run tools/run_release_tests.py and relevant offscreen smoke checks. Microsoft
   identity tests remain deferred. Never launch Fiji during packaging checks.
4. Review diff/whitespace, explicitly stage intended source, run audit_source.py,
   commit/push develop normally, fetch and verify HEAD equals origin/develop.
5. Beta CI tests the exact pushed commit, builds and checks packaged startup,
   compiles the Beta installer/checksum and publishes a versioned prerelease.
   Report SHA, tests, actual Beta version, installer assets and workflow status.

## Production Release Order

Present the tested Beta SHA/tag/run to the human and obtain approval for that
exact promotion. Do not infer approval from development work or old orders.
The manual Production promotion workflow requires a successful Beta workflow
run, matching SHA/prerelease tag/assets, an explicit approval phrase and review
in the protected production GitHub environment before main or Stable changes.
The sole authorized maintainer, MartParty079, may both dispatch and approve a
release after explicit human authorization; a second developer is not required.
The production environment retains its named reviewer and branch restrictions,
with prevent_self_review=false only after the exact setting change is approved.
Never bypass GitHub permissions. The updater repair order authorizes candidate
preparation, not publication. Present the tested candidate and await a subsequent
explicit Stable release instruction.

Promotion must be a normal fast-forward of main to the tested source commit.
Build Stable from that same SHA with the dependency lock and Stable metadata.
Beta installer bytes are never distributed as Stable; identities differ.
Never rebuild unreviewed source edits during promotion. Local Stable builds
require main, a clean committed source tree and a commit-specific approval file.
Verify version/history, packaged startup and installer/checksum before tagging or
publishing. Stable tag pushes alone never trigger publication in the new workflow.
Report failures honestly. Never force-push or overwrite existing release assets.

## Data and identity separation

Stable retains its existing installer ID, LocalAppData/FuelCellProjectHub profile
and gdlresearchhub protocol. No migration copies or deletes Stable data.
Beta has its own installer ID, executable, icon, folder, profile and protocol.
Source execution defaults to isolated Development with automatic -dev.N versions;
release tests select Beta explicitly and frozen edition metadata is immutable.
The local identity order supersedes the earlier live-project Beta amendment.
Development/Beta data, profiles and research indexes stay in isolated local
sandboxes, never the Production OneDrive project. Earlier mappings are backed up
locally and disconnected; no shared files/snapshots are moved or deleted.
Shared identity/activity files are channel-scoped; local SQLite caches never
become multi-user OneDrive databases. Organizational local roles replace hosted
login requirements. Admin requires a PIN; Members do not gain administrative
access because a build is Beta. Supabase projects, historical remote records and
migrations remain untouched. Read LOCAL_TEAM_IDENTITY.md for setup/recovery.

## Mandatory confirmation before every Stable promotion

After checking the exact Beta tag, SHA, workflow and installer assets, display
source Beta, proposed Stable version, changes, test results, known issues,
installer compatibility and data migration requirements. Ask exactly:

"Beta version [VERSION] has passed the required release checks and is ready for Production. Do you approve promoting this exact build to Stable version [VERSION] and publishing it for all Capstone Hub users?"

Only a new explicit affirmative human answer authorizes publication. A rejection
cancels promotion. Record the displayed question, approved_commit, beta_tag,
stable_version and response YES in an ignored local confirmation file. Never
fabricate this receipt or infer it from a development order. The release helper
requires --confirmation-file and validates the exact question/build/version before
any GitHub operation. The protected production workflow also checks the answer,
question, exact source and proposed version. Its named review gate remains.
After approval Codex dispatches and legitimately reviews as the sole maintainer,
then verifies the workflow, installer/checksum/manifest, public downloads and
Stable update discovery. The user need not execute GitHub commands. A failed run
is not a completed release. This work order authorizes Beta publication only.

## Publication boundaries

Git stores source, managed analysis engine, templates, tests, docs and assets.
Never commit secrets, datasets, profiles, active personal paths, caches or builds.
Keep the personal original GDL baseline ignored; missing baseline tests skip
explicitly in CI. Artifacts belong in Actions/Release assets. Unknown SHAs and
unpublished tags remain null in history. Build manifests record actual SHA,
version and edition. Source pushes never update installed Stable applications.
