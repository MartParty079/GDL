"""Atomic JSON persistence, with separate project and per-user state."""
import copy
import getpass
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

from app.services.resources import RESOURCE_ROOT as ROOT


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def read_json(path, fallback):
    if not path.exists():
        return copy.deepcopy(fallback)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Could not read {path}. The existing file was preserved: {exc}") from exc


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Store:
    def __init__(self, root=ROOT, local_dir=None):
        from app.edition import BETA, PROFILE_NAME
        self.root = Path(root)
        self.config_dir = self.root / "config"
        self.sandbox_required = BETA and local_dir is None
        self.shared_required = False
        self.shared_index = None
        override = os.environ.get('GDL_HUB_BETA_DATA_DIR' if BETA else 'FUEL_HUB_DATA_DIR')
        self.local_dir = Path(local_dir or (Path(override) / PROFILE_NAME if BETA and override else override) or
                              Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / PROFILE_NAME)
        defaults = read_json(self.config_dir / "project_defaults.json", {})
        self.project = read_json(self.local_dir / 'project_settings.json',
                                 read_json(self.config_dir / "project.json", defaults))
        self.local = read_json(self.local_dir / "local.json", {"paths": {}, "setup_complete": False})
        if self.sandbox_required:
            # Retire earlier Beta's live-project mapping without touching its files.
            unsafe = self.local.get('shared_root') or self.local.get('local_project_root')
            locations = self.local.get('project_locations', {})
            paths = [locations.get(k) for k in ('shared_storage', 'database', 'generated', 'cache', 'backups')]
            paths += [s.get('root_path') for s in [locations.get('active', {}), *locations.get('legacy', [])]]
            if unsafe or any(p and not Path(p).resolve().is_relative_to(self.local_dir.resolve()) for p in paths):
                write_json(self.local_dir / 'migration-backups' / ('pre-local-identity-' + uuid.uuid4().hex + '.json'), self.local)
                for key in ('shared_root', 'shared_project_id', 'project_locations', 'local_project_root', 'local_project_folder', 'project_snapshot_enabled'):
                    self.local.pop(key, None)
                self.local['sandbox_migration_notice'] = 'Earlier shared mappings were preserved in a local backup. Beta now uses isolated test data.'
                self.project = copy.deepcopy(defaults)
                self.save_local()
        self.events = read_json(self.local_dir / "activity.json", [])
        self.bugs = read_json(self.local_dir / "bugs.json", [])
        self.manifest = read_json(self.config_dir / "software_manifest.json", [])
        self.defaults = defaults
        cached_project = read_json(self.local_dir / "project_snapshot.json", {})
        if cached_project and self.local.get("project_snapshot_enabled"):
            self.project = cached_project
        # One-time retirement of abandoned cloud configuration. Other personal
        # application settings remain intact; no credentials are read or used.
        for key in ('microsoft_auth', 'storage_mode', 'legacy_cache_root', 'previous_legacy_caches'):
            self.local.pop(key, None)
        for key in ('current_cloud_connection', 'legacy_projects'):
            self.project.pop(key, None)
        self.migration_pending = False
        self.provider = None
        self.storage_error = ""
        # Older builds put folder shortcuts into project settings. Preserve
        # them in this profile, and omit them from every future shared write.
        legacy_folder = self.project.pop("project_folder", "")
        if legacy_folder:
            self.local.setdefault("local_project_folder", legacy_folder)
            self.migration_pending = True
        self.local.setdefault("paths", {})
        self.local.setdefault("local_project_root", "")
        self.local.setdefault("local_resource_paths", {})
        for name, target in self.project.get("links", {}).items():
            if target and (Path(target).is_absolute() or PureWindowsPath(target).drive):
                self.local["local_resource_paths"].setdefault(name, target)
                self.project["links"][name] = ""
                self.migration_pending = True
        self.project.setdefault("storage", {"project_name": "Fuel Cell Capstone", "online_url": ""})
        if self.local["local_project_root"] and not self.local.get('project_locations', {}).get('enabled'):
            try:
                self.connect_storage(self.local["local_project_root"], persist=False)
            except (OSError, ValueError) as exc:
                self.storage_error = str(exc)

        if self.sandbox_required:
            from app.services.project_locations import ProjectLocations
            locations = ProjectLocations(self)
            if not locations.value.get('enabled'):
                value = locations.value
                for path in [value['active']['root_path'], *[value[k] for k in ('shared_storage', 'database', 'generated', 'cache', 'backups')]]:
                    Path(path).mkdir(parents=True, exist_ok=True)
                locations.save(value)

    def save_local(self):
        write_json(self.local_dir / "local.json", self.local)

    def attach_shared(self, root):
        from app.services.shared_index import SharedIndex
        if self.sandbox_required and not Path(root).resolve().is_relative_to(self.local_dir.resolve()):
            raise ValueError('Beta cannot connect the production shared project. Use its isolated sandbox.')
        expected = self.local.get('shared_project_id')
        if self.shared_required:
            configured = read_json(self.config_dir / 'shared_project_public.json', {}).get('project_id')
            if configured and expected and expected != configured:
                raise ValueError('The saved mapping belongs to a different configured project.')
            expected = configured or expected
        shared = SharedIndex(self, root, expected)
        self.shared_index = shared
        self.local.update(shared_root=str(shared.root), shared_project_id=shared.identity['project_id'],
                          project_locations=shared.locations())
        self.project = read_json(shared.control / 'settings/project_settings.json', self.defaults)
        self.events = []
        self.save_local()
        return shared

    def project_data(self, relative):
        if self.shared_index:
            from app.services.project_storage import normalized_relative
            path = self.shared_index.control / normalized_relative(relative)
            if not path.resolve().is_relative_to(self.shared_index.control):
                raise ValueError('Project data must remain inside shared control storage.')
            return path
        if self.shared_required:
            raise ValueError('Connect the verified shared project before saving research data.')
        return self.local_dir / relative

    def validate_project_output(self, path):
        path = Path(path).resolve()
        if self.sandbox_required and not path.is_relative_to(self.local_dir.resolve()):
            raise ValueError('Development and Beta exports must stay in the isolated profile sandbox.')
        if self.shared_index:
            if not path.is_relative_to(self.shared_index.root) or path.is_relative_to(self.shared_index.control):
                raise ValueError('Save research exports inside the shared project, outside its control folder.')
        elif self.shared_required:
            raise ValueError('Connect the shared project before exporting research data.')
        return path

    def cache_project(self):
        from app.services.project_storage import validate_shared_settings
        validate_shared_settings(self.project)
        if self.shared_index:
            return
        if self.shared_required:
            raise ValueError('Connect shared project storage first.')
        write_json(self.local_dir / "project_snapshot.json", self.project)
        self.local['project_snapshot_enabled'] = True
        self.save_local()

    def record(self, area, message):
        self.events.append({"id": uuid.uuid4().hex, "timestamp": timestamp(),
                            "person": getpass.getuser(), "type": "Update", "area": area, "message": message})
        if self.shared_index:
            write_json(self.project_data('logs') / (self.events[-1]['id'] + '.json'), self.events[-1])
        elif not self.shared_required:
            write_json(self.local_dir / "activity.json", self.events)
        if getattr(self, "accounts", None):
            self.accounts.event("SETTINGS_CHANGED" if area == "Settings" else "MANUAL_RECORD_EDIT", entity_name=message[:180])

    def save_project(self, value, reason="Project settings changed"):
        from app.services.project_storage import validate_shared_settings
        if getattr(self, "accounts", None):
            self.accounts.require_admin()
        validate_shared_settings(value)
        if self.migration_pending:
            self.save_local()
            self.migration_pending = False
        revision = {"id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8],
                    "timestamp": timestamp(), "person": getpass.getuser(), "reason": reason,
                    "previous": copy.deepcopy(self.project), "next": copy.deepcopy(value)}
        if self.shared_index:
            if not self.shared_index.authority:
                raise ValueError('Shared settings changes require the configured project authority.')
            write_json(self.project_data('settings/history') / (revision['id'] + '.json'), revision)
            write_json(self.project_data('settings/project_settings.json'), value)
        elif self.shared_required:
            raise ValueError('Connect shared project storage first.')
        elif self.provider:
            self.provider.save_project(value, revision)
        elif self.local.get("local_project_root") and not self.local.get('project_locations', {}).get('enabled'):
            raise ValueError("Shared storage unavailable. Reconnect it before changing project settings.")
        else:
            write_json(self.local_dir / "history" / (revision["id"] + ".json"), revision)
            write_json(self.local_dir / "project_settings.json", value)
        self.project = copy.deepcopy(value)
        self.cache_project()
        self.record("Settings", reason)

    def history(self):
        if self.shared_index:
            return [read_json(p, {}) for p in sorted(self.project_data('settings/history').glob('*.json'), reverse=True)]
        if self.provider:
            return self.provider.history()
        paths = [*(self.local_dir / 'history').glob('*.json'), *(self.config_dir / 'history').glob('*.json')]
        return [read_json(p, {}) for p in sorted(paths, reverse=True)]

    def connect_storage(self, root, persist=True):
        if self.shared_required:
            return self.attach_shared(root)
        if self.sandbox_required and not Path(root).resolve().is_relative_to(self.local_dir.resolve()):
            raise ValueError('Beta can connect only to its isolated research sandbox.')
        from app.services.project_storage import LocalOneDriveProvider
        provider = LocalOneDriveProvider(root, self.local_dir / "index")
        marker = provider.read_project()
        if self.migration_pending and persist:
            self.save_local()
            self.migration_pending = False
        self.provider = provider
        provider.settings_baseline = copy.deepcopy(marker.get("settings", {}))
        value = copy.deepcopy(self.defaults)
        value.pop("project_folder", None)
        value.update(marker.get("settings", {}))
        for key in ("links", "storage"):
            merged = copy.deepcopy(self.defaults.get(key, {}))
            merged.update(marker.get("settings", {}).get(key, {}))
            value[key] = merged
        value.setdefault("storage", {"project_name": marker["project_name"], "online_url": ""})
        value["storage"]["project_name"] = marker["project_name"]
        for key in ('current_cloud_connection', 'legacy_projects'):
            value.pop(key, None)
        self.project = value
        previous = self.local.get("local_project_root", "")
        self.local["local_project_root"] = str(provider.root)
        self.local["project_id"] = marker["project_id"]
        self.storage_error = provider.cache_error
        if persist:
            self.cache_project()
            self.save_local()
            self.record("Storage", "Project storage path changed" if previous and previous != str(provider.root) else "Project storage connected")
        return provider

    def project_folder(self):
        locations = self.local.get('project_locations', {})
        if locations.get('enabled'):
            return locations['active']['root_path']
        return self.local.get("local_project_root") or self.local.get("local_project_folder", "")

    def add_bug(self, title, detail, context, version, expected="", steps=""):
        bug = {"id": "BUG-" + uuid.uuid4().hex[:8].upper(), "title": title, "detail": detail,
               "status": "Open", "timestamp": timestamp(), "person": getpass.getuser(),
               "version": version, "context": context, "expected": expected, "steps": steps}
        self.bugs.append(bug)
        if self.shared_index:
            write_json(self.project_data('metadata/bugs') / (bug['id'] + '.json'), bug)
        elif not self.shared_required:
            write_json(self.local_dir / "bugs.json", self.bugs)
        self.record("Bugs", f"Reported {bug['id']}: {title}")
        return bug
