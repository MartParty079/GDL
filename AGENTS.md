# Development and release policy

Repository: https://github.com/MartParty079/GDL.git.
Read fuel-cell-project-hub/docs/CODEX_WORKFLOW.md before repository work.

Every work order is DEVELOPMENT ONLY unless explicitly identified by the human
as a Production Release Order approving the exact tested commit for promotion.
Default branch: develop. Stable branch: main. Use one shared codebase.
Normal commits and pushes to origin/develop are authorized after development
work, verification and source audit. Never push main, create stable tags, publish
Stable or alter production Supabase/storage during a development work order.
An old release authorization does not authorize another Stable publication.

Development: implement -> test -> commit/push develop -> build Beta -> report.
Production: verify approved Beta -> human approves exact promotion -> update main
without unreviewed changes -> stable tag -> gated Stable build/release -> verify.
Use the protected production workflow; never bypass its approval review.

Inspect status, branch and origin; pull the target branch with --ff-only before
editing. Preserve unexpected work and reconcile divergence intentionally. Never
reset, clean or force-push. Explicitly stage intended source, audit with
fuel-cell-project-hub/tools/audit_source.py, review staged diff/whitespace, commit,
push normally, fetch and verify HEAD equals the target remote branch. Report SHA,
tests and tree status. Fix new regressions before pushing.

Beta and Stable require separate installer IDs, folders, profiles, caches,
protocols, research data, update channels and backend endpoints. Beta currently
uses an isolated local sandbox. Never reuse production Supabase credentials or
apply migrations to production for Beta. Roles remain database-authorized; Beta
never grants admin. Do not launch Fiji or test the deferred Microsoft identity
flow without new human authorization.

Git stores source, templates, tests, docs and assets. Do not publish secrets,
profiles, active personal paths, datasets, caches or builds to source Git. Keep
the original GDL baseline ignored. A source push never updates installed Stable.
