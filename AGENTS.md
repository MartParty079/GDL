# Standing single-developer workflow

Repository: https://github.com/MartParty079/GDL.git. Primary branch: main.
Read fuel-cell-project-hub/docs/CODEX_WORKFLOW.md before repository work.

The user authorizes direct source commits and normal pushes to origin/main
following each completed work order. Do not create feature branches by default.
Before editing, inspect status, branch and origin and pull with --ff-only.
Preserve unexpected local work. Inspect and intentionally reconcile divergence;
never reset, clean or force-push to make Git state easier.
After implementing, run applicable tests and smoke checks, review the final diff,
stage intended source explicitly, run tools/audit_source.py, commit descriptively,
push normally, fetch, verify HEAD equals origin/main, and report SHA and status.
Fix new regressions before pushing; never claim unsuccessful checks passed.
GitHub stores application/managed analysis source, templates, tests, docs and
assets. OneDrive/SharePoint stores experimental data. Never publish secrets,
personal profiles, active personal paths, datasets, caches or builds.
Keep the original GDL baseline local and ignored; it contains personal paths.
A source push does not create a release or update installed applications.
