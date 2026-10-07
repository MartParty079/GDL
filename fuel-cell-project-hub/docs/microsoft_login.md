# Microsoft account setup

Open **Settings Ã¢â€ â€™ Microsoft Account**. The supplied public registration identifiers are bundled in `config/microsoft_auth.json`; personal changes are saved in the local profile. No client secret is used.

The university Entra registration must have a **Mobile and desktop applications** redirect URI `http://localhost` (not a Web redirect), public client flows enabled, and delegated Microsoft Graph permission **User.Read** for basic login. Optional file and SharePoint permissions are requested incrementally by their connection actions. Keep implicit token grants disabled. The existing university account audience is left unchanged. University administrators control consent; configuring a permission does not grant tenant consent.

Choose **Sign in** (User.Read only), complete the Microsoft browser prompt, then **Test connection**. Account display name, university username, tenant ID and stable Microsoft user ID appear after connection. Reconnect uses browser sign-in. Sign out removes remembered accounts from the encrypted MSAL cache.

Authentication is optional. Local storage and previously cached indexes remain available while signed out, offline, or awaiting consent. The app never accepts passwords directly, uses application permissions, or requests cloud write/mail/calendar/Teams scopes. MSAL also requests its standard identity/session scopes for browser authentication.

MSAL Extensions protects tokens with Windows DPAPI at `%LOCALAPPDATA%\FuelCellProjectHub\auth\tokens.bin`. Cache persistence uses file locking; no plaintext fallback exists. Token storage is independent of project folders, the configurable legacy cache, `FUEL_HUB_DATA_DIR`, and shared settings. A token-cache redirect into a detected OneDrive folder is rejected. Token/error responses are not printed or copied into activity logs.

For **Admin approval required**, use Local OneDrive / Files On-Demand and ask university IT to review only the blocked feature. Tenant policy may require approval even for basic login; reducing scopes cannot override that policy. For registration errors, verify the desktop redirect and public client settings. For expired sessions, reconnect. If Windows encrypted persistence is unavailable, use local storage until the profile is repaired.

Implementation follows [Microsoft's public-client guidance](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/client-applications) and [encrypted cache persistence guidance](https://learn.microsoft.com/en-us/python/api/msal/msal.token_cache?view=msal-py-latest).

## Permission tiers

**Basic Microsoft Login** requests only `User.Read`, shows account identity, and tests `/me` without enumerating files or sites. Microsoft Account settings show account connection, basic Graph access, own-file access and SharePoint cloud-indexing availability separately.

**Cloud storage / legacy indexing** requests `Files.Read` only after choosing **My OneDrive** in the cloud folder picker, or `Sites.Read.All` only after choosing **Connect SharePoint / search sites**. Opening the picker itself requests no additional consent. Delegated `Files.Read` is intended for the signed-in user's files; university policy controls whether user consent is allowed. [Microsoft permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference#filesread).

A blocked optional permission displays **Admin approval required** while preserving the basic identity and permission state. Cloud refreshes use silent acquisition only; they never open a consent prompt. Permission errors are translated into plain messages, including error details. Cached cloud metadata remains searchable. Even when CloudOnly was selected, current local records are included while the current cloud permission is unavailable; the saved mode is preserved for later reconnection.

No initial request uses `Sites.Read.All`, `.default`, cloud write permissions or an admin-consent endpoint. The archived work order's original broad-login instructions are superseded by this reduced-permission design.

The supplied registration now declares only User.Read in its configured permission list. Runtime explicit cloud connection actions use incremental consent for optional scopes; tenant IT can review each blocked feature separately.
