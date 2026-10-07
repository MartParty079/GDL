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
        self.root = Path(root)
        self.config_dir = self.root / "config"
        self.local_dir = Path(local_dir or os.environ.get("FUEL_HUB_DATA_DIR") or
                              Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "FuelCellProjectHub")
        defaults = read_json(self.config_dir / "project_defaults.json", {})
        self.project = read_json(self.config_dir / "project.json", defaults)
        self.local = read_json(self.local_dir / "local.json", {"paths": {}, "setup_complete": False})
        self.events = read_json(self.local_dir / "activity.json", [])
        self.bugs = read_json(self.local_dir / "bugs.json", [])
        self.manifest = read_json(self.config_dir / "software_manifest.json", [])
        self.defaults = defaults
        cached_project = read_json(self.local_dir / "project_snapshot.json", {})
        if cached_project and self.local.get("project_snapshot_enabled"):
            self.project = cached_project
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
        if self.local["local_project_root"]:
            try:
                self.connect_storage(self.local["local_project_root"], persist=False)
            except (OSError, ValueError) as exc:
                self.storage_error = str(exc)

    def save_local(self):
        write_json(self.local_dir / "local.json", self.local)

    def cache_project(self):
        from app.services.project_storage import validate_shared_settings
        validate_shared_settings(self.project)
        write_json(self.local_dir / "project_snapshot.json", self.project)
        self.local['project_snapshot_enabled'] = True
        self.save_local()

    def record(self, area, message):
        self.events.append({"id": uuid.uuid4().hex, "timestamp": timestamp(),
                            "person": getpass.getuser(), "type": "Update", "area": area, "message": message})
        write_json(self.local_dir / "activity.json", self.events)

    def save_project(self, value, reason="Project settings changed"):
        from app.services.project_storage import validate_shared_settings
        validate_shared_settings(value)
        if self.migration_pending:
            self.save_local()
            self.migration_pending = False
        revision = {"id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8],
                    "timestamp": timestamp(), "person": getpass.getuser(), "reason": reason,
                    "previous": copy.deepcopy(self.project), "next": copy.deepcopy(value)}
        if self.provider:
            self.provider.save_project(value, revision)
        elif self.local.get("local_project_root"):
            raise ValueError("Shared storage unavailable. Reconnect it before changing project settings.")
        else:
            write_json(self.config_dir / "history" / (revision["id"] + ".json"), revision)
            write_json(self.config_dir / "project.json", value)
        self.project = copy.deepcopy(value)
        self.cache_project()
        self.record("Settings", reason)

    def history(self):
        if self.provider:
            return self.provider.history()
        return [read_json(p, {}) for p in sorted((self.config_dir / "history").glob("*.json"), reverse=True)]

    def connect_storage(self, root, persist=True):
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
        return self.local.get("local_project_root") or self.local.get("local_project_folder", "")

    def add_bug(self, title, detail, context, version, expected="", steps=""):
        bug = {"id": "BUG-" + uuid.uuid4().hex[:8].upper(), "title": title, "detail": detail,
               "status": "Open", "timestamp": timestamp(), "person": getpass.getuser(),
               "version": version, "context": context, "expected": expected, "steps": steps}
        self.bugs.append(bug)
        write_json(self.local_dir / "bugs.json", self.bugs)
        self.record("Bugs", f"Reported {bug['id']}: {title}")
        return bug
