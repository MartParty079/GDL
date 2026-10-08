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
Source development defaults to Beta; packaged edition metadata is immutable.
The shared OneDrive amendment explicitly authorizes Beta mapping the existing
GDL research - General project. Identity verification is mandatory, indexing
is restricted to the explicitly enrolled authority, and SQLite publication uses
closed immutable snapshots. Persistent research stays in the shared root; local
verified copies are disposable cache. See SHARED_ONEDRIVE_INDEX.md for migration
and authority recovery. Beta contains no production account configuration.
Its optional URL/publishable key must target a separate Supabase project.
Roles stay database-authorized. Local Beta has no administrator privileges.
Beta migrations are source only until applied to a verified separate project;
production migrations and storage require explicit production approval.

## Publication boundaries

Git stores source, managed analysis engine, templates, tests, docs and assets.
Never commit secrets, datasets, profiles, active personal paths, caches or builds.
Keep the personal original GDL baseline ignored; missing baseline tests skip
explicitly in CI. Artifacts belong in Actions/Release assets. Unknown SHAs and
unpublished tags remain null in history. Build manifests record actual SHA,
version and edition. Source pushes never update installed Stable applications.
