# GDL / Fuel Cell Project Hub

The Windows Hub manages local OneDrive research, historical reference indexes,
meetings, weekly reports and the managed GDL analysis launcher.
See [application setup and verification](fuel-cell-project-hub/README.md).

GitHub = application and managed analysis source.
OneDrive/SharePoint = project and experimental data.

## Development workflow

Development defaults to **develop** and the independently installed **GDL Research
Hub Beta**. **main** and Stable publication require an explicit Production Release
Order approving the tested Beta commit. See the
[edition guide](fuel-cell-project-hub/docs/beta_stable_editions.md).

```powershell
git status
git branch --show-current
git remote -v
git pull --ff-only origin develop
# Implement, test, review and explicitly stage intended source files.
git commit -m "Describe the resulting behavior"
git push origin develop
git fetch origin
git rev-parse HEAD
git rev-parse origin/develop
git status
```

Never force-push or discard uncommitted work. Follow the standing
[Codex workflow](fuel-cell-project-hub/docs/CODEX_WORKFLOW.md).
Source pushes are separate from version tags, tested packages and GitHub Releases.
App users do not need Git.
