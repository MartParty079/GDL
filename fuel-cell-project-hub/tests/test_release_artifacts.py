import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from app.services import updates
from test_update_editions import Response, future_release

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('artifacts', ROOT / 'tools/validate_release_artifacts.py')
artifacts = importlib.util.module_from_spec(spec); spec.loader.exec_module(artifacts)


class ArtifactTests(unittest.TestCase):
    def test_real_stable_contract_and_wrong_edition_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);name='GDLResearchHub-Setup.exe';payload=b'MZfixture'
            (root/name).write_bytes(payload)
            (root/(name+'.sha256')).write_text(hashlib.sha256(payload).hexdigest()+'  '+name)
            manifest={'channel':'stable','version':'0.4.3','commit':'a'*40}
            (root/'build-manifest.json').write_text(json.dumps(manifest))
            self.assertEqual(artifacts.validate(root,'stable','0.4.3','a'*40)['asset'],name)
            manifest['channel']='beta';(root/'build-manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'manifest'):artifacts.validate(root,'stable','0.4.3','a'*40)
            manifest['channel']='stable';(root/'build-manifest.json').write_text(json.dumps(manifest))
            (root/name).write_bytes(b'MZcorrupted')
            with self.assertRaisesRegex(ValueError,'checksum'):artifacts.validate(root,'stable','0.4.3','a'*40)

    def test_missing_installer_reproduces_beta_assets_in_stable_release(self):
        release=future_release();release['assets']={}
        with tempfile.TemporaryDirectory() as temporary,patch.object(updates,'latest_release',return_value=release):
            root=Path(temporary)
            with self.assertRaisesRegex(updates.UpdateError,'Stage: Release metadata'):updates.verified_download(release,root)
            self.assertEqual(json.loads((root/'update-diagnostics.local.json').read_text())['status'],'failed')
            self.assertFalse(list(root.glob('*.exe')))

    def test_http_failure_is_specific_and_does_not_leak_signed_url(self):
        release=future_release()
        error=HTTPError('https://example.invalid/?token=secret',404,'private details',{},None)
        with tempfile.TemporaryDirectory() as temporary,patch.object(updates,'latest_release',return_value=release),patch.object(updates,'urlopen',side_effect=error):
            root=Path(temporary)
            with self.assertRaisesRegex(updates.UpdateError,'HTTP 404'):updates.verified_download(release,root)
            diagnostic=(root/'update-diagnostics.local.json').read_text()
            self.assertNotIn('secret',diagnostic);self.assertNotIn('private details',diagnostic)
            self.assertEqual(json.loads(diagnostic)['stage'],'Checksum download')

    def test_cached_download_receipt_and_tampering_before_launch(self):
        release=future_release();payload=b'MZfixture';digest=hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temporary,patch.object(updates,'latest_release',return_value=release),patch.object(updates,'urlopen',side_effect=[Response((digest+'  '+updates.ASSET).encode()),Response(payload)]):
            root=Path(temporary);path=updates.verified_download(release,root)
            self.assertEqual(json.loads(path.with_suffix('.verified.json').read_text())['sha256'],digest)
            path.write_bytes(b'MZtampered')
            with patch.object(updates.os,'name','nt'),patch.object(updates.subprocess,'Popen') as launch:
                with self.assertRaisesRegex(updates.UpdateError,'integrity'):updates.launch_installer(path)
                launch.assert_not_called()

    def test_download_lock_rejects_second_updater_and_releases_after_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with updates.update_lock(root):
                with self.assertRaisesRegex(updates.UpdateError,'already running'):
                    with updates.update_lock(root):pass
            with updates.update_lock(root):pass

    def test_checksum_cannot_reference_other_edition(self):
        release=future_release()
        with tempfile.TemporaryDirectory() as temporary,patch.object(updates,'latest_release',return_value=release),patch.object(updates,'urlopen',return_value=Response(('a'*64+'  other.exe').encode())):
            with self.assertRaisesRegex(updates.UpdateError,'identify the installer'):updates.verified_download(release,Path(temporary))

    def test_workflows_verify_assets_before_and_after_publication(self):
        for file in ('production-promotion.yml','windows-release.yml'):
            text=(ROOT.parent/'.github/workflows'/file).read_text()
            self.assertIn('Validate installer assets before publication',text)
            self.assertIn('--published-tag',text)
        text=(ROOT.parent/'.github/workflows/production-promotion.yml').read_text()
        self.assertIn('environment: production',text)
        self.assertIn('APPROVE PRODUCTION RELEASE',text)

    def test_solo_release_helper_requires_new_exact_authorization(self):
        spec=importlib.util.spec_from_file_location('publish',ROOT/'tools/publish_stable.py')
        publish=importlib.util.module_from_spec(spec);spec.loader.exec_module(publish)
        with patch.object(publish,'gh') as gh:
            with self.assertRaisesRegex(ValueError,'explicit human'):
                publish.publish('a'*40,'v0.4.3-beta.5','123','development')
            gh.assert_not_called()
        with patch.object(publish,'gh',side_effect=['MartParty079',json.dumps({'commit':{'sha':'b'*40}})]) as gh:
            with self.assertRaisesRegex(ValueError,'Develop changed'):
                publish.publish('a'*40,'v0.4.3-beta.5','123','APPROVE PRODUCTION RELEASE')
            self.assertEqual(gh.call_count,2)


if __name__=='__main__':unittest.main()
