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
| Identity in the new candidate | Local team profiles / required Admin PIN | Same local design only after approved promotion |

Existing Stable installation/data stay untouched. Beta never migrates Stable
settings or tokens. Both editions can run simultaneously. Beta has its BETA icon
badge and labels in window, login, About and version. Local Admin organizational
access requires the Admin PIN; Beta status never grants privileges.

Source execution is a third **Development** stage: FuelCellProjectHubDevelopment
profile, Development title, automatic `-dev.N` identifier, separate sandbox and no
remote installer feed. Rerun current develop source for Development updates.
Packaged editions ignore source environment overrides and remain immutable.

The local identity order supersedes the earlier live-root Beta amendment.
Development/Beta cannot map/write production research, configuration or indexes.
Older Beta mappings are backed up locally and disconnected; a fresh index namespace
prevents reopening an earlier production-linked Beta catalog. Files and prior
snapshots remain intact. See LOCAL_TEAM_IDENTITY.md for profile writer procedure,
recovery, shared transport and the retained historical Supabase records.

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

Beta CI publishes only tested prereleases. Production requires a fresh affirmative
answer to the exact question in CODEX_WORKFLOW.md, a matching local confirmation
receipt, an explicit order,
approved Beta SHA/tag/run, the approval phrase and protected environment review.
It promotes the exact tested source and uses the dependency lock. Stable requires
different installer metadata, so its bytes are built from the approved source.
Develop pushes and stable tag pushes cannot automatically publish Stable.
Keep production reviewers enabled; never bypass the gate.
