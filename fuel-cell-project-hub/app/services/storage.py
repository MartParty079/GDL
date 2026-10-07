"""Atomic JSON persistence, with separate project and per-user state."""
import copy
import getpass
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
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

    def save_local(self):
        write_json(self.local_dir / "local.json", self.local)

    def record(self, area, message):
        self.events.append({"id": uuid.uuid4().hex, "timestamp": timestamp(),
                            "person": getpass.getuser(), "type": "Update", "area": area, "message": message})
        write_json(self.local_dir / "activity.json", self.events)

    def save_project(self, value, reason="Project settings changed"):
        revision = {"id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8],
                    "timestamp": timestamp(), "person": getpass.getuser(), "reason": reason,
                    "previous": copy.deepcopy(self.project), "next": copy.deepcopy(value)}
        write_json(self.config_dir / "history" / (revision["id"] + ".json"), revision)
        write_json(self.config_dir / "project.json", value)
        self.project = copy.deepcopy(value)
        self.record("Settings", reason)

    def history(self):
        return [read_json(p, {}) for p in sorted((self.config_dir / "history").glob("*.json"), reverse=True)]

    def add_bug(self, title, detail, context, version):
        bug = {"id": "BUG-" + uuid.uuid4().hex[:8].upper(), "title": title, "detail": detail,
               "status": "Open", "timestamp": timestamp(), "person": getpass.getuser(),
               "version": version, "context": context}
        self.bugs.append(bug)
        write_json(self.local_dir / "bugs.json", self.bugs)
        self.record("Bugs", f"Reported {bug['id']}: {title}")
        return bug
