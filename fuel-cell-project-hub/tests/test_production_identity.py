import base64
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QWidget
from app.services.accounts import Accounts, AccountError, protect
from app.services.desktop_oauth import CALLBACK, CLIENT, TENANT, MicrosoftLogin, CallbackBroker, callback_values
from app.services.storage import Store, write_json
from tools.bump_version import bump, check
QT_APPLICATION = None


class ProductionIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.user = {"id": "9f020e44-7f50-4aef-a716-655a647c2498", "email": "approved@tarleton.edu", "identities": [{"provider": "azure"}]}
        self.profile = {"id": self.user["id"], "email": self.user["email"], "role": "admin", "active": True}
        self.calls = []
        self.rows = [self.profile]

        def transport(method, path, data):
            self.calls.append((method, path, data))
            if path.startswith('/auth/v1/token?grant_type=pkce'):
                if data['auth_code'] != 'matching-code':
                    raise AccountError('Access unavailable.')
                return {'access_token': 'short-test-token', 'refresh_token': 'short-test-refresh', 'expires_at': time.time()+3600,
                        'provider_token': 'must-not-be-saved', 'provider_refresh_token': 'must-not-be-saved'}
            if path == '/auth/v1/user': return self.user
            if path.startswith('/rest/v1/profiles'): return self.rows
            return None

        self.accounts = Accounts(Store(local_dir=self.root), transport)
        self.login = MicrosoftLogin(self.accounts)

    def tearDown(self):
        self.accounts.executor.shutdown(wait=True)
        self.temporary.cleanup()

    def begin(self, tenant=TENANT):
        from urllib.parse import urlencode
        location = f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?' + urlencode({
            'client_id': CLIENT, 'redirect_uri': self.accounts.url+'/auth/v1/callback', 'scope': 'openid email'})
        opener = unittest.mock.Mock()
        opener.open.side_effect = HTTPError('unused', 302, 'Found', {'Location': location}, None)
        with patch('app.services.desktop_oauth.build_opener', return_value=opener):
            result = self.login.begin()
        return result, opener.open.call_args.args[0]

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_exact_redirect_identity_only_scopes_and_pkce(self):
        location, request = self.begin()
        query = parse_qs(urlparse(request.full_url).query)
        self.assertEqual(query['redirect_to'], [CALLBACK])
        self.assertEqual(query['scopes'], ['email'])
        self.assertEqual(query['code_challenge_method'], ['s256'])
        self.assertNotIn('Sites.Read.All', location)
        self.assertNotIn('common', location)
        self.assertNotIn('verifier', self.login.path.read_text())
        saved = json.loads(protect(base64.b64decode(json.loads(self.login.path.read_text())['protected']), True))
        import hashlib
        expected = base64.urlsafe_b64encode(hashlib.sha256(saved['verifier'].encode()).digest()).decode().rstrip('=')
        self.assertEqual(query['code_challenge'], [expected])

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_same_uuid_linking_provider_tokens_discarded_and_replay_denied(self):
        self.begin()
        profile = self.login.complete(CALLBACK+'?code=matching-code')
        self.assertEqual(profile['id'], self.user['id'])
        self.assertEqual(profile['role'], 'admin')
        self.assertFalse(any(m == 'POST' and '/profiles' in p for m,p,d in self.calls))
        self.assertNotIn('provider_token', self.accounts.session)
        self.assertNotIn('provider_refresh_token', self.accounts.session)
        self.assertEqual(self.accounts.auth_method, 'microsoft_entra')
        with self.assertRaises(AccountError): self.login.complete(CALLBACK+'?code=matching-code')
        self.assertEqual(self.accounts.restore()['id'], self.user['id'])
        self.assertEqual(self.accounts.auth_method, 'microsoft_entra')

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_wrong_code_expired_attempt_and_cancellation(self):
        self.begin()
        with self.assertRaises(AccountError): self.login.complete(CALLBACK+'?code=wrong-code')
        self.assertIsNone(self.accounts.profile)
        self.assertTrue(self.login.path.exists())
        self.login.cancel()
        with self.assertRaises(AccountError): self.login.complete(CALLBACK+'?code=matching-code')
        write_json(self.login.path, {'protected': base64.b64encode(protect(json.dumps({'url': self.accounts.url, 'verifier': 'short', 'created_at':time.time()-601}).encode())).decode()})
        with self.assertRaises(AccountError): self.login.complete(CALLBACK+'?code=matching-code')
        self.begin()
        with self.assertRaisesRegex(AccountError, 'not completed'):
            self.login.complete(CALLBACK+'?error=access_denied&error_description=private-provider-diagnostic')
        self.assertFalse(self.login.path.exists())

    def test_wrong_tenant_never_opens_or_saves_attempt(self):
        with self.assertRaisesRegex(AccountError, 'administrator attention'): self.begin('common')
        self.assertFalse(self.login.path.exists())

    def test_unsafe_duplicate_and_token_callbacks_rejected(self):
        for value in ('https://auth/callback?code=a', CALLBACK+'#access_token=private', CALLBACK+'?code=a&code=b',
                      CALLBACK+'?access_token=private', 'gdlresearchhub://auth/other?code=a', CALLBACK+'?code='+'a'*4096):
            with self.subTest(value=value[:55]), self.assertRaises(AccountError): callback_values(value)

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_unapproved_disabled_or_non_azure_profile_denied(self):
        for kind in ('unapproved', 'disabled', 'personal', 'not-azure'):
            with self.subTest(kind=kind):
                self.rows = [dict(self.profile, active=kind!='disabled')]
                self.user['email'] = 'approved@tarleton.edu' if kind!='personal' else 'personal@example.test'
                self.user['identities'] = [{'provider': 'email' if kind=='not-azure' else 'azure'}]
                if kind=='unapproved': self.rows = []
                self.begin()
                with self.assertRaises(AccountError): self.login.complete(CALLBACK+'?code=matching-code')
                self.assertIsNone(self.accounts.session)
                self.assertFalse(any(m=='POST' and '/profiles' in p for m,p,d in self.calls))

    def test_password_fallback_rejects_other_domains(self):
        with self.assertRaises(AccountError): self.accounts.sign_in('external@example.test','unused')
        self.assertEqual(self.calls, [])

    def test_local_pipe_delivers_callback_without_http_server(self):
        global QT_APPLICATION
        app = QApplication.instance() or QApplication([])
        QT_APPLICATION = app
        broker = CallbackBroker(self.root)
        self.assertTrue(broker.listen())
        values = []
        broker.received.connect(values.append)
        try:
            import subprocess, sys
            code="from pathlib import Path; import sys; from PySide6.QtCore import QCoreApplication; from app.services.desktop_oauth import CallbackBroker,CALLBACK; app=QCoreApplication([]); broker=CallbackBroker(Path(sys.argv[1])); sys.exit(0 if broker.forward(CALLBACK+'?code=matching-code') else 1)"
            sender=subprocess.Popen([sys.executable,'-c',code,str(self.root)])
            deadline=time.monotonic()+8
            while sender.poll() is None and time.monotonic()<deadline:
                app.processEvents();time.sleep(.01)
            self.assertEqual(sender.wait(timeout=3),0)
            self.assertEqual(values, [CALLBACK+'?code=matching-code'])
        finally:
            if sender.poll() is None: sender.terminate();sender.wait(timeout=3)
            broker.server.close();app.processEvents()
            broker.deleteLater()
            from PySide6.QtCore import QCoreApplication,QEvent
            QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


class VersionHistoryTests(unittest.TestCase):
    def test_work_order_bumps_preserve_history_and_refuse_inconsistency(self):
        original = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'app').mkdir()
            for name in ('app/version.py','version_history.json','CHANGELOG.md'):
                (root/name).write_text((original/name).read_text(encoding='utf-8'),encoding='utf-8')
            before=json.loads((root/'version_history.json').read_text())['versions']
            original_version=check(root)[0]
            major,minor,patch_version=map(int,original_version.split('.'))
            previous,current=bump(root,'patch','Test work order','A real test summary')
            after=check(root)[1]['versions']
            self.assertEqual(after[:-1],before)
            self.assertEqual(current,f'{major}.{minor}.{patch_version+1}')
            self.assertEqual(previous,original_version)
            self.assertEqual(bump(root,'minor','Test minor','Summary')[1],f'{major}.{minor+1}.0')
            final=f'{major+1}.0.0'
            self.assertEqual(bump(root,'major','Test major','Summary')[1],final)
            source=root/'app/version.py'
            source.write_text(source.read_text().replace(final,f'{major+1}.0.1'))
            with self.assertRaises(ValueError): bump(root,'patch','Bad','Summary')

    def test_canonical_history_and_changelog_agree(self):
        from app import __version__
        self.assertEqual(check(Path(__file__).resolve().parents[1])[0],__version__)


if __name__ == '__main__': unittest.main()
