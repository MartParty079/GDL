# GDL / Fuel Cell Project Hub

The Windows Hub manages local OneDrive metadata, optional Microsoft Graph
connections, historical reference indexes and the managed GDL analysis launcher.
See [application setup and verification](fuel-cell-project-hub/README.md).

GitHub = application and managed analysis source.
OneDrive/SharePoint = project and experimental data.

## Development workflow

Single developer; work directly on main.

```powershell
git status
git branch --show-current
git remote -v
git pull --ff-only origin main
# Implement, test, review and explicitly stage intended source files.
git commit -m "Describe the resulting behavior"
git push origin main
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git status
```

Never force-push or discard uncommitted work. Follow the standing
[Codex workflow](fuel-cell-project-hub/docs/CODEX_WORKFLOW.md).
Source pushes are separate from version tags, tested packages and GitHub Releases.
App users do not need Git.
