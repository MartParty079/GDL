# Initial build status

Created October 6, 2026 from the provided document pack.

## Verification completed

- Nine service tests passed: revision/restore, local/shared separation, missing configured paths, non-executing detection, launch arguments with spaces, malformed config preservation, bug persistence, resource URI validation, and release repository validation.
- Qt offscreen smoke test passed: first launch, background detection, six pages, settings revision/restore, and local bug report.
- Dashboard screenshot reviewed after loading Windows fonts for offscreen rendering.
- Python source compilation passed.

These checks did not install or launch engineering tools, access university accounts, submit reports, or modify existing project files outside the new app directory.

## Product status

Working source application with a project-local Python environment and double-click launcher. Not yet a packaged production release. Manual software configuration, project links, and dashboard content are required. Release installation/rollback, quick installers, shared requests, multi-user editing, and future research entities remain unimplemented.

The supplied technical framework is treated as design guidance rather than authority to execute installers, create accounts, or change unrelated system settings.

## Teams launch fix

Applied the subsequently authorized Teams work order:

- A common launcher dispatches executable, Windows application protocol, and web targets.
- Teams uses `msteams://` with Test Launch and no executable locator. Launch failures offer download and retry. Teams readiness is verified by explicit launch, not by executing during a scan.
- GitHub web launcher added; GitHub Desktop's existing ID, saved executable paths, and lifecycle overrides remain compatible.
- Old manifest entries default to executable launching. Strict `.exe` and Windows Store alias validation remains intact for executable tools.
- All 23 service/UI regression tests passed, along with the updated desktop smoke test and source compilation.
- A real `msteams://` launch was accepted by Windows outside the restricted test sandbox. The initial in-sandbox attempt returned access denied; no application or system configuration was changed to bypass it.

Launch-control tests mock Windows handoff and browsers; they do not establish that Teams sign-in or a particular Teams window is working. Successful real Windows handoff likewise confirms dispatch only.
