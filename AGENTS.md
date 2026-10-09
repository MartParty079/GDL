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
Use the protected production workflow. The explicitly authorized sole maintainer
may dispatch and approve their own exact-commit release when GitHub self-review
is enabled. Never publish from ordinary development work or bypass platform
permissions. This repair order prepares a candidate only; new explicit human
authorization is required to publish it.

Inspect status, branch and origin; pull the target branch with --ff-only before
editing. Preserve unexpected work and reconcile divergence intentionally. Never
reset, clean or force-push. Explicitly stage intended source, audit with
fuel-cell-project-hub/tools/audit_source.py, review staged diff/whitespace, commit,
push normally, fetch and verify HEAD equals the target remote branch. Report SHA,
tests and tree status. Fix new regressions before pushing.

Development, Beta and Stable require separate profiles, research data, caches,
configuration and update channels. Source execution defaults to isolated
Development; packaged Beta and Stable have immutable edition identities. This
local identity work order supersedes the earlier live OneDrive Beta mapping:
Development/Beta may use only isolated test directories and representative
fixtures, never Production research/index/configuration writes. Preserve earlier
shared catalogs and mappings. Read fuel-cell-project-hub/docs/SHARED_ONEDRIVE_INDEX.md
for the historical catalog-only migration; never move archive files without a
separate validated plan. Local organizational roles now replace hosted desktop
roles; Admin functions require a PIN. Never connect to production Supabase,
apply production migrations or delete remote records during development.
Do not launch Fiji or test Microsoft identity without new human authorization.

Before every Stable promotion, identify the exact tested Beta/SHA/artifacts,
verify compatibility/installers/tests, display changes, known issues and migration
requirements, then ask exactly:
"Beta version [VERSION] has passed the required release checks and is ready for Production. Do you approve promoting this exact build to Stable version [VERSION] and publishing it for all Capstone Hub users?"
An affirmative human answer authorizes the complete gated release workflow for
that exact build only. Rejection cancels it. Record the exact question, Beta tag,
SHA, proposed Stable version and YES response in an ignored local confirmation
receipt; tools/publish_stable.py requires it before dispatch. Never invent a
confirmation or use an earlier release's approval. The desktop never holds
GitHub release credentials.

Git stores source, templates, tests, docs and assets. Do not publish secrets,
profiles, active personal paths, datasets, caches or builds to source Git. Keep
the original GDL baseline ignored. A source push never updates installed Stable.
