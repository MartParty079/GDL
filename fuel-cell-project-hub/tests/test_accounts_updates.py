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
from app.services import updates


class UpdateTests(unittest.TestCase):
    def test_semver_stable_channel_and_official_urls(self):
        self.assertTrue(updates.newer('v0.10.0','0.9.9'))
        for value in ('v0.3.0-beta','v0.2.0','bad'):
            self.assertFalse(updates.newer(value,'0.3.0'))
        with self.assertRaises(ValueError):updates.latest_release('attacker/repository')
        release={'tag':'v0.4.0','assets':{updates.ASSET:{'browser_download_url':'https://example.test/malware.exe'}}}
        with self.assertRaises(ValueError):updates.asset_url(release,updates.ASSET)

    def test_checksum_mismatch_discarded_and_verified_download(self):
        next_tag = f'v{updates.version(updates.__version__)[0] + 1}.0.0'
        if '-beta.' in updates.__version__:next_tag+='-beta.1'
        release={'tag':next_tag,'assets':{name:{'browser_download_url':f'https://github.com/MartParty079/GDL/releases/download/{next_tag}/{name}'} for name in (updates.ASSET,updates.ASSET+'.sha256')}}
        payload=b'MZinstaller-test'; checksum=hashlib.sha256(payload).hexdigest()
        class Response:
            def __init__(self,data):self.data=data; self.offset=0
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):result=self.data[self.offset:self.offset+n]; self.offset+=len(result); return result
            def geturl(self):return 'https://release-assets.githubusercontent.com/asset'
        with tempfile.TemporaryDirectory() as temporary, patch.object(updates,'latest_release',return_value=release):
            root=Path(temporary)
            with patch.object(updates,'urlopen',side_effect=[Response((checksum+'  '+updates.ASSET).encode()),Response(payload)]):
                result=updates.verified_download(release,root); self.assertEqual(result.read_bytes(),payload)
            result.unlink()
            with patch.object(updates,'urlopen',side_effect=[Response(('0'*64+'  '+updates.ASSET).encode()),Response(payload)]):
                with self.assertRaises(ValueError):updates.verified_download(release,root)
            self.assertEqual(list(root.glob('*.exe'))+list(root.glob('*.part')),[])


if __name__=='__main__':unittest.main()
