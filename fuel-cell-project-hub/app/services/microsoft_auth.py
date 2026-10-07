"""Optional desktop browser authentication with a Windows DPAPI token cache."""
import os
import threading
import uuid
import re
from pathlib import Path

SCOPES = ['User.Read']
TIER_SCOPES = {'basic': SCOPES, 'files': ['User.Read', 'Files.Read'],
               'sharepoint': ['User.Read', 'Sites.Read.All']}


class AuthError(ValueError):
    pass


class MicrosoftAuth:
    def __init__(self, store, application_factory=None, cache_factory=None):
        self.store = store
        self.state = 'Signed Out'
        self.account = None
        self.last_error_code = ''
        self.permissions = {'basic': 'Not connected', 'files': 'Not enabled', 'sharepoint': 'Not enabled'}
        self._application = None
        self._lock = threading.RLock()
        self.application_factory, self.cache_factory = application_factory, cache_factory

    def registration(self):
        if 'microsoft_auth' in self.store.local:
            return self.store.local['microsoft_auth']
        if hasattr(self.store, 'config_dir'):
            from app.services.storage import read_json
            return read_json(self.store.config_dir / 'microsoft_auth.json', {})
        return {}

    def configure(self, client_id, tenant_id='organizations'):
        try:
            uuid.UUID(client_id)
            if tenant_id != 'organizations':
                uuid.UUID(tenant_id)
        except (ValueError, AttributeError):
            raise AuthError('Enter a valid Application ID and tenant ID, or use organizations.') from None
        with self._lock:
            self.sign_out()
            self.store.local['microsoft_auth'] = {'client_id': client_id, 'tenant_id': tenant_id, 'authority_mode': 'organizations'}
            self.store.save_local()
            self._application = None

    def _app(self):
        if self._application:
            return self._application
        config = self.registration()
        if not config.get('client_id'):
            self.state = 'Unavailable'
            raise AuthError('Configure the university Entra public client Application ID first. Local storage remains available.')
        try:
            import msal
            from msal_extensions import PersistedTokenCache, FilePersistenceWithDataProtection
            # Tokens must never be written underneath a synced project or redirected profile.
            local_appdata = Path(os.environ.get('LOCALAPPDATA', '')).resolve()
            if os.name != 'nt' or not os.environ.get('LOCALAPPDATA'):
                raise AuthError('Encrypted Microsoft sign-in is supported on Windows. Use local storage on this computer.')
            cache_path = local_appdata / 'FuelCellProjectHub' / 'auth' / 'tokens.bin'
            for variable in ('OneDrive', 'OneDriveCommercial', 'OneDriveConsumer'):
                synced = os.environ.get(variable)
                if synced and cache_path.resolve().is_relative_to(Path(synced).resolve()):
                    raise AuthError('The token cache is redirected into OneDrive. Restore a private Windows Local AppData folder before signing in.')
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache = (self.cache_factory or (lambda p: PersistedTokenCache(FilePersistenceWithDataProtection(str(p)))))(cache_path)
            self._application = (self.application_factory or msal.PublicClientApplication)(
                config['client_id'], authority='https://login.microsoftonline.com/' + config.get('tenant_id', 'organizations'), token_cache=cache, timeout=15)
            return self._application
        except AuthError:
            raise
        except Exception:
            self.state = 'Unavailable'
            raise AuthError('Microsoft sign-in or encrypted token storage is unavailable. Check the MSAL installation and Windows profile.') from None

    def _failure(self, tier, status, message):
        self.permissions[tier] = status
        if tier == 'basic':
            self.state = status
        raise AuthError(message)

    def _accept(self, result, tier='basic', interactive=False):
        if result and result.get('access_token'):
            claims = result.get('id_token_claims', {})
            values = {'display_name': claims.get('name', ''), 'username': claims.get('preferred_username', ''),
                      'tenant_id': claims.get('tid', ''), 'id': claims.get('oid', '')}
            self.account = dict(self.account or {})
            self.account.update({key: value for key, value in values.items() if value})
            self.permissions[tier] = 'Available'
            if tier == 'basic':
                self.state = 'Connected'
            return result['access_token']
        code = (result or {}).get('error', '')
        self.last_error_code = code if isinstance(code, str) and re.fullmatch(r'[a-z_]{1,40}', code) else ''
        # Consent diagnostics are mapped to human messages; no raw code reaches the UI.
        codes = [str(value) for value in (result or {}).get('error_codes', []) if isinstance(value, int)]
        codes += re.findall(r'AADSTS(\d+)', (result or {}).get('error_description', ''))
        if any(value in {'65001', '90094', '90093', '90095'} for value in codes) or code == 'consent_required' or (interactive and code == 'access_denied'):
            self._failure(tier, 'Admin approval required', 'Admin approval required for this Microsoft feature. Local OneDrive and cached indexes remain usable.')
        if '50011' in codes or '7000218' in codes:
            self._failure(tier, 'Unavailable', 'Check that http://localhost is a Mobile and desktop redirect, rather than a Web redirect.')
        if '50020' in codes:
            self._failure(tier, 'Unavailable', 'Use your university account in the configured university directory.')
        if code == 'invalid_request':
            self._failure(tier, 'Unavailable', 'Check the Entra desktop app registration: enable public client flows and add the Mobile and desktop redirect URI http://localhost.')
        if tier != 'basic':
            self._failure(tier, 'Not enabled', 'Cloud access is not enabled. Connect cloud storage to request it, or continue using Local OneDrive.')
        self._failure(tier, 'Token Expired', 'Microsoft sign-in did not finish. Retry basic sign-in; local storage remains usable.')

    def sign_in(self, tier='basic'):
        with self._lock:
            if tier not in TIER_SCOPES:
                raise AuthError('Unsupported Microsoft permission tier.')
            self.permissions[tier] = 'Signing In'
            if tier == 'basic':
                self.state = 'Signing In'
            try:
                self._accept(self._app().acquire_token_interactive(scopes=TIER_SCOPES[tier], timeout=180), tier, True)
                return self.get_account()
            except AuthError:
                raise
            except Exception:
                self._failure(tier, 'Unavailable', 'Microsoft sign-in could not finish. Retry in your browser; local storage remains available.')

    def get_access_token(self, tier='basic'):
        with self._lock:
            app = self._app()
            accounts = app.get_accounts()
            if not accounts:
                if tier == 'basic':
                    self.state = 'Signed Out'
                raise AuthError('Sign in to Microsoft before refreshing cloud storage.')
            try:
                return self._accept(app.acquire_token_silent(TIER_SCOPES[tier], account=accounts[0]), tier)
            except AuthError:
                raise
            except Exception:
                self._failure(tier, 'Unavailable', 'Microsoft connection is unavailable. Cached files remain searchable.')

    def enable_access(self, tier):
        """Called only after an explicit cloud-connect / own-file action."""
        if tier not in ('files', 'sharepoint'):
            raise AuthError('Choose own files or SharePoint cloud indexing.')
        if self.state != 'Connected':
            self.get_access_token('basic')
        try:
            self.get_access_token(tier)
            return self.get_account()
        except AuthError:
            return self.sign_in(tier)

    def permission_status(self):
        return dict(self.permissions)

    def mark_unavailable(self, tier, admin=False):
        self.permissions[tier] = 'Admin approval required' if admin else 'Unavailable'

    refresh = get_access_token

    def get_account(self):
        return dict(self.account or {})

    def connection_status(self):
        return self.state

    def sign_out(self):
        with self._lock:
            if self._application:
                try:
                    for account in self._application.get_accounts():
                        self._application.remove_account(account)
                except Exception:
                    raise AuthError('Could not clear the encrypted Microsoft session. Retry sign out.') from None
            elif self.registration().get('client_id'):
                # Initialize persistence to clear remembered accounts, not just the in-memory display.
                try:
                    app = self._app()
                    for account in app.get_accounts():
                        app.remove_account(account)
                except AuthError:
                    raise
                except Exception:
                    raise AuthError('Could not clear the encrypted Microsoft session. Retry sign out.') from None
            self.account = None
            self.state = 'Signed Out'
            self.permissions = {'basic': 'Not connected', 'files': 'Not enabled', 'sharepoint': 'Not enabled'}

    clear_cache = sign_out
