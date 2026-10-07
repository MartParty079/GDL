"""Publication guard and source/frozen resource resolution checks."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from app.services.resources import resource_path
from tools.audit_source import audit_blob


class PublicationTests(unittest.TestCase):
    def test_local_profiles_datasets_and_builds_are_blocked(self):
        for name in ('fuel-cell-project-hub/auth/tokens.bin', 'fuel-cell-project-hub/dist/app.exe',
                     'fuel-cell-project-hub/04_Raw_Data/pressure.csv',
                     'fuel-cell-project-hub/analysis/gdl/baseline/defaults.py',
                     'fuel-cell-project-hub/config/project.json'):
            self.assertTrue(audit_blob(name, b'fixture'), name)

    def test_credentials_and_active_personal_paths_are_blocked(self):
        self.assertTrue(audit_blob('fuel-cell-project-hub/config/unsafe.json', b'"access_token": "' + b'a' * 40 + b'"'))
        self.assertTrue(audit_blob('fuel-cell-project-hub/app/unsafe.py', b'folder="C:/Users/ExampleUser/data"'))
        self.assertFalse(audit_blob('fuel-cell-project-hub/docs/example.md', b'Documentation example: C:/Users/ExampleUser/data'))

    def test_public_identifiers_and_packaging_source_are_allowed(self):
        self.assertFalse(audit_blob('fuel-cell-project-hub/config/indexing_rules.json', b'{"keywords":{"astm":"Standards"}}'))
        self.assertFalse(audit_blob('fuel-cell-project-hub/tools/app.spec', b'project_directory / "assets/app_icon.ico"'))

    def test_resource_resolution_in_source_and_frozen_layouts(self):
        self.assertTrue(resource_path('assets/app_icon.ico').is_file())
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, '_MEIPASS', '/example/package/_internal', create=True):
            self.assertEqual(resource_path('assets/app_icon.ico'), Path('/example/package/_internal/assets/app_icon.ico'))
