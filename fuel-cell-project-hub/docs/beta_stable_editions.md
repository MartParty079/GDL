# Beta and Stable editions

| Setting | Beta | Stable |
| --- | --- | --- |
| Branch | develop | main |
| Application | GDL Research Hub Beta | GDL Research Hub |
| Executable | GDLResearchHubBeta.exe | FuelCellProjectHub.exe |
| Installer | GDLResearchHubBeta-Setup.exe | GDLResearchHub-Setup.exe |
| Install folder under LocalAppData/Programs | GDL Research Hub Beta | GDL Research Hub |
| Profile under LocalAppData | FuelCellProjectHubBeta | FuelCellProjectHub |
| Protocol | gdlresearchhubbeta | gdlresearchhub |
| Updates | vX.Y.Z-beta.N prereleases only | vX.Y.Z stable releases only |
| Backend | Local sandbox; optional separate Beta Supabase | Existing production Supabase |

Stable installation/data stay untouched. Beta never migrates Stable settings or
tokens. Both editions can run simultaneously. Beta has a blue B icon with gold
BETA badge, and Beta labels in window, login, About and version. Local Beta has
no administrator privileges. Authenticated Beta retains database-authorized roles.

For a future separate Beta backend, set GDL_BETA_SUPABASE_URL and
GDL_BETA_SUPABASE_PUBLISHABLE_KEY or configure config/accounts_beta_public.json
before an approved Beta build. Use only a publishable key from a separate project.
The production endpoint is explicitly refused. Apply migrations only to that
verified Beta project. Production database/storage are unchanged by this order.

Copy test research into the Beta profile's research-sandbox folder. Writable
storage, indexes, generated files, backups and scientific analysis inputs/outputs
stay inside the Beta profile. Do not configure a production research folder there.

## Update choices

Update Now confirms cooperative indexing cancellation, pauses automatic work,
waits up to 30 seconds for other writes, atomically saves settings/editor drafts,
and gives activity flushing up to 5 seconds. Nothing is forcibly terminated.
Unsafe or unfinished work offers Update on Next Open. Download or launch errors
preserve current use and a durable retry preference. Partial downloads are removed.
Cached installers are rehashed against the official checksum before reuse.
The installer never force-closes apps, overwrites the other edition or downgrades.

Update on Next Open writes a per-profile preference without interrupting work.
The next launch handles it before login/workspace/background operations. Failure
allows normal startup and retry later. An installed matching/newer version clears
the preference. Settings, sessions, indexes and research files remain intact.
Unapplied settings restore on startup; matching editor drafts restore on reopening.
Changed editor layouts retain update-drafts.local.json for manual recovery.

## Approval gate

Beta CI publishes only tested prereleases. Production requires an explicit order,
approved Beta SHA/tag/run, the approval phrase and protected environment review.
It promotes the exact tested source and uses the dependency lock. Stable requires
different installer metadata, so its bytes are built from the approved source.
Develop pushes and stable tag pushes cannot automatically publish Stable.
Keep production reviewers enabled; never bypass the gate.
