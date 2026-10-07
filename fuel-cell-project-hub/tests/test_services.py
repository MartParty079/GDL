import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.storage import Store, ROOT, write_json
from app.services.software import detect, launch, open_resource, launch_type, LaunchType, valid_executable
from app.services.updates import latest_release


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ("software_manifest.json", "project_defaults.json"):
            write_json(self.root / "config" / name, json.loads((ROOT / "config" / name).read_text()))
        self.store = Store(self.root, self.root / "local")

    def tearDown(self):
        self.temp.cleanup()

    def test_project_revision_preserves_before_and_after(self):
        previous = copy.deepcopy(self.store.project)
        updated = copy.deepcopy(previous)
        updated["goal"] = "Assess electrode durability"
        self.store.save_project(updated)
        revision = self.store.history()[0]
        self.assertEqual(revision["previous"], previous)
        self.assertEqual(revision["next"], updated)
        self.store.save_project(revision["previous"], "Restore")
        self.assertEqual(self.store.project, previous)
        self.assertEqual(len(self.store.history()), 2)

    def test_paths_are_never_saved_in_project_config(self):
        self.store.local["paths"]["python"] = "C:/Personal/Python/python.exe"
        self.store.save_local()
        self.assertNotIn("paths", self.store.project)
        loaded = Store(self.root, self.root / "local")
        self.assertEqual(loaded.local["paths"], self.store.local["paths"])

    def test_missing_configured_path_is_not_silently_replaced(self):
        item = self.store.manifest[0]
        result = detect(item, str(self.root / "missing.exe"))
        self.assertEqual(result["status"], "Missing")
        self.assertIn("Configured", result["source"])

    def test_scan_never_executes_discovered_file(self):
        executable = self.root / "tool.exe"
        executable.touch()
        with patch("subprocess.Popen") as process:
            result = detect(self.store.manifest[0], str(executable))
        self.assertEqual(result["status"], "Ready")
        process.assert_not_called()

    def test_launch_handles_spaces_without_shell_interpolation(self):
        executable = self.root / "Tool with spaces.exe"
        executable.touch()
        with patch("subprocess.Popen") as process:
            launch(self.store.manifest[0], {"path": str(executable)})
        self.assertEqual(process.call_args.args[0], [str(executable)])
        self.assertNotIn("shell", process.call_args.kwargs)

    def test_bad_config_preserved(self):
        path = self.root / "local" / "local.json"
        path.parent.mkdir()
        path.write_text("{invalid")
        with self.assertRaises(ValueError):
            Store(self.root, path.parent)
        self.assertEqual(path.read_text(), "{invalid")

    def test_bug_captures_context_and_persists_status(self):
        bug = self.store.add_bug("Launch issue", "Steps to reproduce", {"page": "Software"}, "0.1.0-dev")
        self.assertEqual(bug["status"], "Open")
        self.assertEqual(Store(self.root, self.root / "local").bugs[0]["context"], {"page": "Software"})

    def test_rejects_executable_resource_and_unsafe_uri(self):
        for value in ("javascript:alert(1)", "file:///C:/tool.exe", "cmd://run", "https:"):
            with self.assertRaises(ValueError):
                open_resource(value)

    def test_release_repository_validation_before_network(self):
        with self.assertRaises(ValueError):
            latest_release("https://github.com/team/repo")

    def test_teams_launch_uses_uri_even_with_old_executable_override(self):
        teams = next(i for i in self.store.manifest if i["id"] == "teams")
        with patch("app.services.software.os.startfile") as start, patch("app.services.software.valid_executable") as valid:
            launch(teams, {"path": "C:/WindowsApps/old-teams.exe"})
        start.assert_called_once_with("msteams://")
        valid.assert_not_called()

    def test_uri_detection_never_launches_or_scans_executables(self):
        teams = next(i for i in self.store.manifest if i["id"] == "teams")
        with patch("app.services.software.registry_candidates") as registry, patch("app.services.software.valid_executable") as valid, patch("app.services.software.os.startfile") as start:
            result = detect(teams, "C:/stale/Teams.exe")
        self.assertEqual(result["status"], "Needs test")
        self.assertEqual(result["target"], "msteams://")
        registry.assert_not_called()
        valid.assert_not_called()
        start.assert_not_called()

    def test_url_launcher_opens_browser_without_executable_validation(self):
        github = next(i for i in self.store.manifest if i["id"] == "github_web")
        with patch("app.services.software.webbrowser.open", return_value=True) as browser, patch("app.services.software.valid_executable") as valid:
            self.assertEqual(detect(github)["status"], "Ready")
            launch(github)
        browser.assert_called_once_with("https://github.com/")
        valid.assert_not_called()

    def test_failed_uri_launch_is_propagated(self):
        with patch("app.services.software.os.startfile", side_effect=OSError("No handler")):
            with self.assertRaises(OSError):
                launch({"name": "Teams", "launch_type": "uri", "launch_target": "msteams://"})

    def test_invalid_web_and_protocol_targets_rejected(self):
        for kind, target in (("url", "msteams://"), ("url", "https:"), ("uri", "file:///C:/tool.exe"), ("uri", "C:/tool.exe"), ("uri", "")):
            item = {"name": "Invalid", "launch_type": kind, "launch_target": target}
            self.assertEqual(detect(item)["status"], "Missing")
            with self.assertRaises(ValueError):
                launch(item)

    def test_web_launch_failure_is_propagated(self):
        with patch("app.services.software.webbrowser.open", return_value=False):
            with self.assertRaises(ValueError):
                launch({"name": "GitHub", "launch_type": "url", "launch_target": "https://github.com/"})

    def test_legacy_manifest_entries_default_to_executable(self):
        item = {"id": "legacy", "name": "Legacy", "executables": [], "patterns": []}
        executable = self.root / "legacy.exe"
        executable.touch()
        self.assertEqual(launch_type(item), LaunchType.EXE)
        result = detect(item, str(executable))
        with patch("subprocess.Popen") as process:
            launch(item, result)
        self.assertEqual(process.call_args.args[0], [str(executable.resolve())])

    def test_executable_validation_still_rejects_windows_store_aliases(self):
        alias = self.root / "WindowsApps" / "Teams.exe"
        alias.parent.mkdir()
        alias.touch()
        self.assertFalse(valid_executable(str(alias)))
        with self.assertRaises(ValueError):
            launch({"id": "legacy", "name": "Legacy"}, {"path": str(alias)})

    def test_unknown_launch_type_is_rejected(self):
        with self.assertRaises(ValueError):
            launch({"name": "Unknown", "launch_type": "script"})

    def test_manifest_regression_and_desktop_identity_preserved(self):
        entries = {i["id"]: i for i in self.store.manifest}
        for key in ("swift", "fiji", "jmp", "python", "excel", "word", "git", "discord", "github"):
            self.assertEqual(launch_type(entries[key]), LaunchType.EXE)
        self.assertEqual(entries["github"]["name"], "GitHub Desktop")
        self.assertEqual(launch_type(entries["teams"]), LaunchType.URI)
        self.assertEqual(launch_type(entries["github_web"]), LaunchType.URL)

if __name__ == "__main__":
    unittest.main()
