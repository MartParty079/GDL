# Production integration and version management

Work order: Production Authentication, Administration, Packaging, Updates,
Legacy Data, Microsoft Entra Integration, and Version Management (document
version 0.2.1). The current application was already newer, so its no-downgrade
rule applies: previous 0.3.0, target 0.3.1, final implementation 0.3.1.
`app/version.py` is canonical; `version_history.json` appends the work order.
Earlier history was reconstructed from the existing changelog and Git commits,
without inventing releases. The current entry's future commit/tag remain null;
packaging derives build commit/date from Git. Source publication is not release
publication. Developer policy and the bump/check utility enforce future bumps.

## Identity and desktop return

The existing GDL Capstone Supabase project remains the only backend. Azure and
email/password providers are enabled; public signup is disabled. The approved
initial administrator UUID/profile is preserved. Authorization always resolves
the authenticated UUID and database role/active state, never an email match or
client-editable metadata role.

The login offers Continue with Tarleton Microsoft and Tarleton email/password.
The desktop uses Supabase's Azure social provider with PKCE S256. It explicitly
sends `redirect_to=gdlresearchhub://auth/callback`, with `scopes=email`.
The provider's actual authorization URL was verified as the configured Tarleton
tenant and existing client application, requesting only `openid email`.
No Files/Sites/Graph permissions are requested. Supabase's actual flow record
now confirms the exact desktop return rather than its previous localhost
fallback. The return must also be in Supabase's redirect allowlist.

Before opening the browser, the app checks HTTPS, Microsoft host, tenant path,
client ID, Supabase provider callback and identity-only scopes. Browser MFA is
handled by Microsoft/Tarleton. The Azure secret remains server-side; the app
does not read it. Existing Entra audience/optional claims are not changed.
Production Entra must retain AzureADMyOrg, email and xms_edov; direct manifest
inspection remains an operator check. Tenant restriction is independently
observed in the live provider authorization URL. See the official
[Azure provider guide](https://supabase.com/docs/guides/auth/social-login/auth-azure).

Inno Setup registers the per-user `gdlresearchhub` URI, quoting both the EXE
path and `%1`. A callback launch forwards the URI through a Qt local pipe to
the waiting app and exits. Windows pipe access is limited to the user. There is
no HTTP listener, permanent local server or token-bearing implicit callback.
The only accepted route is the exact auth callback with a bounded, single
authorization code or controlled failure parameters. Fragments, token inputs,
duplicate parameters, other hosts/routes and oversized inputs are rejected.

The verifier is random, DPAPI-encrypted for the current Windows user, bound to
the backend URL and valid for ten minutes. The app exchanges code+verifier
for a Supabase session; successful exchange consumes the pending attempt.
Provider access/refresh tokens are discarded. Only Supabase session credentials
are saved encrypted. Password login cancels pending Microsoft attempts; logout
clears both session and pending verifier. Errors are friendly, with password
login remaining available.

Microsoft access requires an Azure identity returned by Supabase Auth, a
Tarleton email and an existing active approved application UUID/profile. This
route never creates a profile or merges by email. Supabase's verified identity
linking should attach the Microsoft identity to the existing user. Automated
checks cover matching-UUID preservation and duplicate-profile prevention; live
linking and MFA need browser acceptance when university approval is available. See
[identity linking](https://supabase.com/docs/guides/auth/auth-identity-linking).

## Administration and activity

Admin now includes Overview, Users, Activity, Versions, Installations and
System. All privileged requests retain JWT verification plus a fresh active
ADMIN database check in `hub-admin`. USER controls remain absent. The backend
supports bounded paging, user/action/date-range/entity/version/source filtering,
user display labels and activity source/authentication method. Authentication
events record only email_password or microsoft_entra as context, without
credentials. Existing safe activity detail allowlists remain in place.

Versions shows each installation's version and CURRENT, UPDATE AVAILABLE,
NEWER BUILD or UNKNOWN against the latest known release/current build.
Installation identity remains a random UUID; labels remain user-controlled.
These are last-seen records, not presence tracking. Profile last_activity is
maintained from real events by the migrated trigger, replacing the prior
approximation based on installation timestamps. Last-admin protection now also
rejects deletion, in addition to disable/demotion.

Migration `production_identity_audit` extends the existing profile and triggers
without dropping tables or users. The JWT-protected existing admin function was
updated. All three public tables retain RLS. Research data/indexes are not moved
into Supabase. The inherited offline grace remains limited to 24 hours after
validation; offline administration is disabled and activity is queued locally.

## Research acceptance

The local SQLite catalog was backed up before implementation. Real Current and
Legacy reconciliation scanned 172,284 files: Current 6 and Legacy 172,278,
with zero scan errors. Legacy includes 85,592 images, 1,195 reports/documents
and 45,785 data files. Existing file identities and research annotations were
preserved; one new Current record reflected the filesystem reconciliation.
Legacy originals were not moved, renamed, overwritten or deleted.

Holy GDL remains present: 15,484 files and 8,907 images in Legacy/All; Current
returns zero. Authenticated Images → Legacy → Holy GDL, grid selection,
actual resident thumbnail, metadata, large preview and global search were
exercised with real content. A selected original image was opened through its
Windows association and selected in Explorer. External dispatch succeeded;
visual confirmation of those external windows remains a user check.
No fake Holy GDL content was created. A real small legacy PDF and CSV were
explicitly opened, hydrated and read successfully for preview validation.
No mass hydration occurred. One existing resident JPG reports extraction
failure; it remains indexed/openable with the safe fallback.

Visible navigation/details panes now restore a usable width even if older
saved layouts recorded zero. The startup shows the research Overview and
starts cancellable Quick Refresh in the existing background worker after the
window appears. Login never waits for a full content rebuild. Native indexing,
search, preview and file actions require no Microsoft Graph access.

Production Teams app launch/resource behavior and automated tests remain.
No obsolete manual Teams test panel was present to remove. Scientific Fiji/JMP
launches were not used for acceptance.

## Packaging and release acceptance

Canonical version appears in header, login, About/history, installed client
records and activity. About shows chronological structured history, release
notes and available build metadata. The installer reads that same version;
CI rejects inconsistent history/changelog or mismatched production tags.
The bump utility supports patch/minor/major, preserves previous entries and
refuses inconsistent input. Build resources include structured history.

The complete Windows package and per-user Inno installer were generated.
Isolated install/packaged startup/uninstall checks passed. A local installer
upgrade from the prior 0.3.0 package to 0.3.1 passed; quoted URI registration
and removal were verified. This is not a separate clean Windows account or
an end-to-end published GitHub update. Existing profiles/indexes remain outside
the installation directory. The updater continues to validate official stable
release metadata, semantic versions, exact asset URLs and SHA-256 before
launching the installer. It never overwrites its running EXE or invokes Git.

The complete suite ran 215 tests: 213 passed, two explicit skips. Source smoke
produced 21 workspace checks; packaged startup checks include login, DPAPI,
callback resources, version history, native index and all preview parsers.
Additional collapsed-layout and real-gallery checks validate the final fix.
Source and artifacts must pass the credential/publication audit before release.

### Acceptance status

| Check | Status / evidence |
| --- | --- |
| Header/login/About/canonical version | PASS; shared app version and structured history |
| CHANGELOG/history/bump utility | PASS; append-only entries and automated checks |
| Email/password/admin/session persistence | PASS; existing live admin and regression checks |
| Tarleton Microsoft tenant/scopes/return URL | PASS; live provider preflight and server flow record |
| Microsoft login | University admin approval required, reported by the user; password fallback retained |
| MFA/live identity linking | Deferred at the user's explicit request; no further Microsoft-route testing |
| Admin Users/Activity/Installations/Versions | PASS; live backend and version-status UI checks |
| Normal USER/disabled/admin endpoint denial | PASS; regression checks and earlier live USER acceptance |
| Last administrator delete | PASS; transactional backend rejection test |
| Real Current/Legacy/Holy GDL | PASS; actual counts, thumbnail, preview and filters |
| Open File/Show in Folder | Dispatch PASS; external visual confirmation pending |
| Installer version/local upgrade | PASS; local isolated installer checks |
| Clean Windows environment | Not performed; requires separate account/machine |
| GitHub release check/semantic/checksum logic | Automated PASS; live release distribution pending |
| Published upgrade preservation | Not performed; no production release/tag created |
| Supabase Security Advisor | REVIEW REQUIRED; leaked-password protection disabled |

Enable leaked-password protection when supported by the project; see
[Supabase password security](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
Invitation/reset email delivery and Authenticator are user/provider acceptance
checks. Installers remain unsigned. Do not call this a fully accepted production
release until the pending live/clean-machine/published-upgrade checks succeed.
The user explicitly chose password login for now and directed that the
Microsoft route remain as implemented without further testing. Its university
approval, MFA and real identity-linking checks are deferred accordingly.
