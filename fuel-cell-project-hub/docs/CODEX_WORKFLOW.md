# Codex source publishing workflow

Repository: MartParty079/GDL (https://github.com/MartParty079/GDL.git)
Primary branch: main. Development model: single developer.
The Git root contains this app directory and a repository README; preserve the
existing layout. No feature branch or worktree is required for normal work.

## Start every work order

From the repository or app directory, inspect git status, git branch
--show-current and git remote -v. Verify main and the expected origin.
Run git pull --ff-only origin main before edits. If it fails, stop editing,
inspect divergence and reconcile intentionally while preserving all work.
Never force push. Never automatically reset, clean, stash away or delete
unexpected uncommitted work. Stage unrelated changes only when the user asks.

## Work order version policy

Every implemented work order must produce a new traceable application version.
Read app/version.py, the latest version_history.json entry and CHANGELOG first;
confirm they agree, then record the target version before implementation.
Default to a PATCH increment. Never reuse a completed work-order version or
downgrade the application to an older version mentioned in a work order.
Use tools/bump_version.py patch --work-order "Name" --summary "Completed changes"
(minor/major require a justified milestone). History is append-only; correct
historical factual errors explicitly. Include features, fixes and breaking
changes. Unpublished tags and unavailable commit IDs remain null, not invented.
Verify tools/bump_version.py check, header, login, About/history, installer
metadata and release tag alignment before completion. Packaging derives build
date and commit from Git; an entry cannot contain its own future commit SHA.
Version inconsistency is a release failure. Source commits alone are not releases.

## Complete every work order

1. Implement the authorized changes.
2. Run applicable tests. The app uses unittest, not pytest:
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
3. Run relevant documented offscreen smoke tests; scientific launches remain
   subject to the user's authorization. Do not launch Fiji as a packaging test.
4. Review git status and git diff, including staged diff and whitespace checks.
5. Explicitly stage intended source files. Do not stage OneDrive datasets.
6. Run .\.venv\Scripts\python.exe tools/audit_source.py against the staged tree.
7. Commit with a descriptive message, then git push origin main.
8. Fetch origin and verify git rev-parse HEAD == git rev-parse origin/main.
9. Report tests, final commit SHA/message, branch, push result and tree status.

Fix new failures before a normal push; clearly report any pre-existing failures.
If a normal push is rejected, fetch and inspect, reconcile, rerun relevant checks
and push normally. Never use --force or -f on main.
Use existing Git Credential Manager/GitHub CLI/browser authentication. Never
write a token, password, secret or session cookie into repository files.

## Storage boundary

GitHub stores app source, portable managed GDL source, config templates, tests,
docs, assets, packaging .spec source and release metadata. OneDrive/SharePoint
stores images, videos, sensor data, processed datasets, reports and old test data.
Local profiles, caches, tokens and machine paths remain in Local AppData.
Microsoft login provides identity through Supabase; native indexing and file
access have no Microsoft Graph dependency.

The preserved original GDL baseline stays ignored on this development computer
because its historical defaults contain named user paths. The portable managed
engine and baseline hash inventory are published. Fresh checkouts can run
ordinary engine/package tests with the sanitized legacy test fixture; three comparisons against
the original require restoring the privately held original into
analysis/gdl/baseline and otherwise report explicit skips. Never claim those
comparisons were performed when the original was absent.

## Source push versus user update

A source push is not a release. Production flow is source push, stable tested
build, version tag, GitHub Release and packaged app update discovery. Do not
make ordinary app users perform Git pulls or create releases for normal work.
