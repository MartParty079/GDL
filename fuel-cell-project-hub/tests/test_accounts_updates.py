import base64
import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from app.services.storage import Store, write_json
from app.services.accounts import Accounts, AccountError, ConnectionUnavailable, protect
from app.services import updates


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(); self.root=Path(self.temporary.name)
        self.store=Store(local_dir=self.root)
        self.profile={'id':'9f020e44-7f50-4aef-a716-655a647c2498','email':'research@example.test','role':'user','active':True}
        self.calls=[]
        self.rows=[self.profile]
        def transport(method,path,data):
            self.calls.append((method,path,data))
            if 'token?' in path:return {'access_token':'fake-short-token','refresh_token':'fake-refresh','expires_at':time.time()+3600}
            if path=='/auth/v1/user':return self.profile
            if path.startswith('/rest/v1/profiles'):
                if method=='GET':return self.rows
                self.rows=[dict(data)]; return None
            return None
        self.accounts=Accounts(self.store,transport)

    def tearDown(self):
        self.accounts.executor.shutdown(wait=True); self.temporary.cleanup()

    @unittest.skipUnless(os.name=='nt','Windows session encryption')
    def test_dpapi_restore_refresh_and_signout(self):
        self.accounts.sign_in('research@example.test','not-saved-password')
        text=self.accounts.session_path.read_text()
        self.assertNotIn('fake-short-token',text); self.assertNotIn('not-saved-password',text)
        self.accounts.session=None
        self.assertEqual(self.accounts.restore()['role'],'user')
        self.accounts.sign_out(); self.assertFalse(self.accounts.session_path.exists())
        self.assertIn('LOGIN',[e['event_type'] for _,path,data in self.calls if path=='/rest/v1/activity_events' for e in data])

    @unittest.skipUnless(os.name=='nt','Windows session encryption')
    def test_self_provision_only_user_and_disabled_denied(self):
        self.rows=[]; self.accounts.sign_in('research@example.test','not-saved-password')
        inserts=[d for m,p,d in self.calls if m=='POST' and p=='/rest/v1/profiles']
        self.assertEqual(inserts[0]['role'],'user')
        self.rows=[dict(self.profile,active=False)]
        with self.assertRaisesRegex(AccountError,'disabled'):self.accounts.load_profile()
        self.assertIsNone(self.accounts.session)

    @unittest.skipUnless(os.name=='nt','Windows session encryption')
    def test_offline_grace_is_bounded_and_role_not_admin_authority(self):
        self.accounts.sign_in('research@example.test','not-saved-password')
        def offline(*args):raise ConnectionUnavailable('Offline')
        self.accounts.transport=offline
        self.assertTrue(self.accounts.restore()); self.assertTrue(self.accounts.offline)
        with self.assertRaises(AccountError):self.accounts.admin('users')
        self.accounts.validated_at=time.time()-86401; self.accounts.save_session()
        self.assertIsNone(self.accounts.restore())

    def test_bounded_queue_path_privacy_and_installation_identity(self):
        self.accounts.profile=self.profile; self.accounts.offline=True
        original=self.accounts.install_id
        for i in range(505):
            self.accounts.event('FILE_OPENED','file',str(i),'C:\\Users\\example\\secret\\image.png',{'source':'legacy','notes':'private','password':'private','full_path':'private'})
        self.assertEqual(len(self.accounts.pending),500)
        event=self.accounts.pending[-1]; self.assertEqual(event['entity_name'],'image.png'); self.assertEqual(event['details'],{'source':'legacy'})
        self.assertEqual(original,self.store.local['install_id'])
        with self.assertRaises(AccountError):self.accounts.admin('set_role',role='admin')

    def test_main_restored_login_opens_visible_workspace(self):
        import sys
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        from app.main import main
        from app.ui.window import HubWindow
        from app.services.project_locations import ProjectLocations
        app=QApplication.instance() or QApplication([])
        current=self.root/'current'; legacy=self.root/'legacy'; current.mkdir();legacy.mkdir()
        locations=ProjectLocations(self.store); value=locations.value
        value['active']['root_path']=str(current);value['legacy'][0]['root_path']=str(legacy)
        value['shared_storage']=str(current);locations.save(value)
        def restore():
            self.accounts.profile=self.profile
            return self.profile
        observed=[]; deadline=time.monotonic()+15
        timer=QTimer()
        def inspect():
            windows=[w for w in app.topLevelWidgets() if isinstance(w,HubWindow) and w.isVisible()]
            if windows:
                window=windows[0]; observed.append(window.tabs.count())
                if not window.research_workspace.busy() and window.close():timer.stop()
            if time.monotonic()>deadline:
                timer.stop();app.exit(1)
        timer.timeout.connect(inspect);timer.start(50)
        old_hook=sys.excepthook
        try:
            with patch('app.main.Store',return_value=self.store),patch('app.services.accounts.Accounts',return_value=self.accounts),patch.object(self.accounts,'restore',restore),patch.object(HubWindow,'scan',lambda _:None),patch.object(HubWindow,'check_updates_on_startup',lambda _:None):
                self.assertEqual(main(),0)
            self.assertTrue(observed);self.assertEqual(observed[0],6)
        finally:
            timer.stop();sys.excepthook=old_hook
            import logging
            logger=logging.getLogger('gdlhub')
            for handler in list(logger.handlers):
                handler.close();logger.removeHandler(handler)


class UpdateTests(unittest.TestCase):
    def test_semver_stable_channel_and_official_urls(self):
        self.assertTrue(updates.newer('v0.10.0','0.9.9'))
        for value in ('v0.3.0-beta','v0.2.0','bad'):
            self.assertFalse(updates.newer(value,'0.3.0'))
        with self.assertRaises(ValueError):updates.latest_release('attacker/repository')
        release={'tag':'v0.4.0','assets':{updates.ASSET:{'browser_download_url':'https://example.test/malware.exe'}}}
        with self.assertRaises(ValueError):updates.asset_url(release,updates.ASSET)

    def test_checksum_mismatch_discarded_and_verified_download(self):
        release={'tag':'v0.4.0','assets':{name:{'browser_download_url':f'https://github.com/MartParty079/GDL/releases/download/v0.4.0/{name}'} for name in (updates.ASSET,updates.ASSET+'.sha256')}}
        payload=b'MZinstaller-test'; checksum=hashlib.sha256(payload).hexdigest()
        class Response:
            def __init__(self,data):self.data=data; self.offset=0
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):result=self.data[self.offset:self.offset+n]; self.offset+=len(result); return result
            def geturl(self):return 'https://release-assets.githubusercontent.com/asset'
        with tempfile.TemporaryDirectory() as temporary, patch.object(updates,'latest_release',return_value=release):
            root=Path(temporary)
            with patch.object(updates,'urlopen',side_effect=[Response((checksum+'  file').encode()),Response(payload)]):
                result=updates.verified_download(release,root); self.assertEqual(result.read_bytes(),payload)
            result.unlink()
            with patch.object(updates,'urlopen',side_effect=[Response(('0'*64).encode()),Response(payload)]):
                with self.assertRaises(ValueError):updates.verified_download(release,root)
            self.assertEqual(list(root.iterdir()),[])


if __name__=='__main__':unittest.main()
