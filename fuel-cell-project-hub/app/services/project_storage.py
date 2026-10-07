"""Storage provider contract and metadata-only local OneDrive indexing."""
import copy
import fnmatch
import os
import re
import stat
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath

from app.services.storage import read_json, write_json, timestamp

STANDARD_FOLDERS = ("00_Project_Admin", "01_Procedures", "02_Samples", "03_Experiments",
                    "04_Raw_Data", "05_Processed_Data", "06_Analysis", "07_Reports",
                    "08_Reference", "09_Exports", "99_Archive", ".projecthub")
EXCLUDED = {".projecthub", ".git", "__pycache__", ".venv", "venv", "node_modules",
            ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".sites-runtime"}
RELATION_KEYS = ("experiment_id", "run_id", "sample_id", "procedure_id", "procedure_version")
PLACEHOLDER_FLAGS = 0x1000 | 0x40000 | 0x400000


class IndexCancelled(Exception):
    pass


def normalized_relative(value):
    value = str(value).replace("\\", "/")
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts or ":" in value or "\x00" in value:
        raise ValueError("Project references must be relative paths inside the project root.")
    return path.as_posix()


def validate_shared_settings(value):
    if not isinstance(value, dict) or not isinstance(value.get("links", {}), dict) or not isinstance(value.get("storage", {}), dict):
        raise ValueError("Shared settings, links, and storage must be JSON objects.")
    if value.get("project_folder") or value.get("local_project_root"):
        raise ValueError("Absolute project roots belong in the local profile, not shared settings.")
    def reject_private(data):
        if isinstance(data, dict):
            for key, child in data.items():
                if key.casefold() in {'access_token', 'refresh_token', 'id_token', 'client_secret', 'token_cache', 'microsoft_auth', 'legacy_cache_root'}:
                    raise ValueError('Credentials and local paths cannot be stored in shared project settings.')
                reject_private(child)
        elif isinstance(data, list):
            for child in data:
                reject_private(child)
    reject_private(value)
    for folder in value.get('project_folders', {}).values():
        normalized_relative(folder)
    for folder, category in value.get('file_classification', {}).get('folder_rules', {}).items():
        normalized_relative(folder)
        from app.services.file_classifier import CATEGORIES
        if category not in CATEGORIES:
            raise ValueError('Unsupported classification category.')
    cloud = value.get('current_cloud_connection')
    legacy = value.get('legacy_projects', [])
    if not isinstance(legacy, list):
        raise ValueError('Historical project definitions must be a list.')
    for connection in ([cloud] if cloud else []) + legacy:
        if not isinstance(connection, dict) or connection.get('provider') != 'MicrosoftGraph' or not all(isinstance(connection.get(k), str) and connection[k] for k in ('drive_id', 'root_item_id', 'web_url')):
            raise ValueError('Cloud connections require stable Graph IDs and an online URL.')
        from urllib.parse import urlparse
        parsed = urlparse(connection['web_url'])
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username:
            raise ValueError('Cloud links must use HTTPS.')
        if connection in legacy and (connection.get('data_origin') != 'legacy' or not connection.get('legacy_project_id', '').startswith('LEG-') or connection.get('read_only_reference') is not True):
            raise ValueError('Historical sources must remain read-only legacy references.')
    analysis = value.get("gdl_analysis", {})
    if not isinstance(analysis, dict) or not isinstance(analysis.get("paths", {}), dict):
        raise ValueError("Shared GDL settings must contain a folder path object.")
    allowed = {"quick_run_folder", "swift_magnification_folder", "default_input_folder", "default_output_folder", "report_output_folder"}
    if set(analysis) - {"paths"} or set(analysis.get("paths", {})) - allowed:
        raise ValueError("GDL executable, engine and runtime paths belong only in local settings.")
    for folder in analysis.get("paths", {}).values():
        if not isinstance(folder, str):
            raise ValueError("Shared GDL folder paths must be text.")
        normalized_relative(folder)
    for target in value.get("links", {}).values():
        if not isinstance(target, str):
            raise ValueError("Shared links must be text.")
        if target and not target.startswith(("https://", "http://")):
            normalized_relative(target)
    online = value.get("storage", {}).get("online_url", "")
    if not isinstance(online, str):
        raise ValueError("Online storage URL must be text.")
    if online:
        from urllib.parse import urlparse
        parsed = urlparse(online)
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            raise ValueError("Online storage URL must be a complete http/https address.")


def placeholder(info):
    return bool(getattr(info, "st_file_attributes", 0) & PLACEHOLDER_FLAGS)


def redirects(info):
    # Name-surrogate tags redirect paths (junctions/symlinks); cloud reparse
    # tags do not. Do not skip OneDrive simply for being a reparse point.
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_reparse_tag", 0) & 0x20000000)


def classify(relative):
    parts = PurePosixPath(relative).parts
    for folder, category in (("01_Procedures", "Procedure"), ("07_Reports", "Report"), ("08_Reference", "Reference")):
        if folder in parts:
            return category
    extension = PurePosixPath(relative).suffix.lower()
    groups = {"Image": ".tif .tiff .png .jpg .jpeg .bmp .gif",
              "Video": ".mp4 .mov .avi .mkv .wmv",
              "Sensor Data": ".csv .tsv .dat .txt",
              "Spreadsheet": ".xlsx .xlsm .xls .ods",
              "Document": ".docx .doc .pdf .md .rtf .pptx",
              "Code": ".py .m .jsl .ipynb .js .ts .ps1 .r",
              "CAD": ".sldprt .sldasm .slddrw .step .stp .iges .igs .stl",
              "Configuration": ".json .yaml .yml .toml .ini .xml"}
    return next((category for category, values in groups.items() if extension in values.split()), "Other")


def infer_relationships(relative):
    result = {key: "" for key in RELATION_KEYS}
    for part in PurePosixPath(relative).parts:
        candidate = PurePosixPath(part).stem
        for prefix, key in (("E", "experiment_id"), ("S", "sample_id"), ("P", "procedure_id")):
            if re.fullmatch(prefix + r"-[A-Za-z0-9][A-Za-z0-9_-]*", candidate):
                result[key] = candidate
        if re.fullmatch(r"R\d+", candidate) and result["experiment_id"]:
            result["run_id"] = result["experiment_id"] + "-" + candidate
    return result


def search_items(items, query="", category="", experiment="", run="", sample="", procedure="",
                 date_from="", date_to="", archive="active", origin="", legacy_project=""):
    words = query.casefold().split()
    result = []
    for item in items:
        if item.get("state", "active") != "active":
            continue
        if origin and (item.get('data_origin', 'current') not in ('current', 'archive') if origin == 'current' else item.get('data_origin', 'current') != origin):
            continue
        if legacy_project and item.get('legacy_project_id', '') != legacy_project:
            continue
        if archive == "active" and item["archived"] or archive == "archived" and not item["archived"]:
            continue
        if any(value and item.get(key, "").casefold() != value.casefold() for key, value in
               (("category", category), ("experiment_id", experiment), ("run_id", run), ("sample_id", sample), ("procedure_id", procedure))):
            continue
        date = item["modified"][:10]
        if date_from and date < date_from or date_to and date > date_to:
            continue
        text = " ".join(str(item.get(key, "")) for key in ("name", "relative_path", "category", 'subcategory', 'data_origin', 'legacy_project_id', 'legacy_project_name', 'legacy_note', *RELATION_KEYS)).casefold()
        if all(word in text for word in words):
            result.append(item)
    return sorted(result, key=lambda i: i["relative_path"].casefold())


class ProjectStorageProvider(ABC):
    @abstractmethod
    def list_items(self): ...
    @abstractmethod
    def get_item(self, relative_path): ...
    @abstractmethod
    def open_item(self, relative_path): ...
    @abstractmethod
    def open_folder(self, relative_path="."): ...
    @abstractmethod
    def refresh(self, rebuild=False, cancel=None, progress=None): ...
    @abstractmethod
    def exists(self, relative_path): ...
    @abstractmethod
    def status(self): ...
    @abstractmethod
    def missing_folders(self): ...
    @abstractmethod
    def create_missing_folders(self): ...
    @abstractmethod
    def read_project(self): ...
    @abstractmethod
    def save_project(self, settings, revision): ...
    @abstractmethod
    def history(self): ...
    @abstractmethod
    def summary(self): ...


class LocalOneDriveProvider(ProjectStorageProvider):
    def __init__(self, root, cache_dir):
        self.root = Path(root).expanduser().resolve()
        self.cache_dir = Path(cache_dir)
        self.index_path = self.cache_dir / "file_index.json"
        self.index = {"schema_version": 1, "project_id": "", "records": [], "last_index_time": "", "next_id": 1, "events": [], "warnings": []}
        self.cache_error = ""
        try:
            cached = read_json(self.index_path, self.index)
            if not isinstance(cached, dict) or cached.get("schema_version") != 1 or not isinstance(cached.get("records"), list):
                raise ValueError("Unsupported or invalid local index schema. Existing cache preserved.")
            if (not isinstance(cached.get("project_id"), str) or not isinstance(cached.get("last_index_time"), str)
                    or not isinstance(cached.get("next_id"), int) or cached["next_id"] < 1
                    or not isinstance(cached.get("events"), list) or not isinstance(cached.get("warnings"), list)):
                raise ValueError("Invalid index header. Existing cache preserved.")
            for record in cached["records"]:
                if (not isinstance(record, dict) or any(not isinstance(record.get(key), str) for key in
                    ("id", "relative_path", "name", "modified", "category", "experiment_id", "run_id", "sample_id", "procedure_id"))
                    or not isinstance(record.get("size"), int) or not isinstance(record.get("archived"), bool)):
                    raise ValueError("Invalid index record. Existing cache preserved.")
                normalized_relative(record["relative_path"])
            self.index = cached
        except ValueError as exc:
            self.cache_error = str(exc)

    def path(self, relative):
        relative = normalized_relative(relative)
        candidate = self.root / relative
        # Validate each existing component, then resolve to prevent traversing
        # junctions or symlinks. No file content is read here.
        current = self.root
        for part in PurePosixPath(relative).parts:
            current = current / part
            try:
                if redirects(current.lstat()):
                    raise ValueError("Linked paths are not opened or indexed by the local provider.")
            except FileNotFoundError:
                break
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("Path leaves the project root.")
        return resolved

    def project_key(self, marker):
        return marker.get("project_id") or str(self.root)

    def validate_root(self, require_marker=True, allow_unmarked=False):
        if not self.root.is_dir():
            raise ValueError("Shared project folder unavailable. Locate your synced folder again.")
        protected = {Path(self.root.anchor), Path.home().resolve()}
        protected.update(Path(os.environ[k]).resolve() for k in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)") if os.environ.get(k))
        if self.root in protected:
            raise ValueError("Select the project folder, not a system root, system folder, or user home.")
        with os.scandir(self.root):
            pass
        marker_path = self.path(".projecthub/project.json")
        if marker_path.exists():
            marker = read_json(marker_path, {})
            if not isinstance(marker, dict) or marker.get("schema_version") != 1 or not marker.get("project_name"):
                raise ValueError("Project marker has an invalid or unsupported schema. It was preserved.")
            validate_shared_settings(marker.get("settings", {}))
            return marker
        if require_marker:
            raise ValueError("Project marker missing. Use Locate Synced Folder to validate this project again.")
        known = any(self.path(name).is_dir() for name in STANDARD_FOLDERS if name != ".projecthub")
        if not known and not allow_unmarked:
            raise ValueError("This folder has no project marker or known project folders. Confirm it is your intended project library.")
        return None

    def accept_root(self, name, settings=None, allow_unmarked=False):
        marker = self.validate_root(require_marker=False, allow_unmarked=allow_unmarked)
        if marker:
            return marker
        if not name.strip():
            raise ValueError("Enter the shared project name.")
        settings = settings or {}
        validate_shared_settings(settings)
        marker = {"schema_version": 1, "project_id": uuid.uuid4().hex,
                  "project_name": name.strip(), "settings": copy.deepcopy(settings)}
        write_json(self.path(".projecthub/project.json"), marker)
        return marker

    def read_project(self):
        return self.validate_root()

    def save_project(self, settings, revision):
        validate_shared_settings(settings)
        marker = self.read_project()
        if marker.get("settings", {}) != getattr(self, "settings_baseline", revision["previous"]):
            raise ValueError("Shared settings changed since they were loaded. Reconnect storage before applying edits.")
        marker["settings"] = copy.deepcopy(settings)
        marker["project_name"] = settings.get("storage", {}).get("project_name") or marker["project_name"]
        write_json(self.path(".projecthub/history/" + revision["id"] + ".json"), revision)
        write_json(self.path(".projecthub/project.json"), marker)
        self.settings_baseline = copy.deepcopy(settings)

    def history(self):
        self.validate_root()
        return [read_json(p, {}) for p in sorted(self.path(".projecthub/history").glob("*.json"), reverse=True)]

    def status(self):
        try:
            self.validate_root()
            return "Index Error" if self.cache_error else "Connected"
        except (OSError, ValueError):
            return "Unavailable"

    def missing_folders(self):
        self.validate_root()
        return [name for name in STANDARD_FOLDERS if not self.path(name).is_dir()]

    def create_missing_folders(self):
        missing = self.missing_folders()
        created = []
        for name in missing:
            self.path(name).mkdir(exist_ok=True)
            created.append(name)
        return created

    def exists(self, relative_path):
        return self.path(relative_path).exists()

    def list_items(self):
        marker = self.validate_root()
        if self.index.get("project_id") != self.project_key(marker):
            return []
        return copy.deepcopy(self.index["records"])

    def get_item(self, relative_path):
        key = normalized_relative(relative_path)
        return next((item for item in self.list_items() if item["relative_path"] == key), None)

    def open_item(self, relative_path):
        self.validate_root()
        path = self.path(relative_path)
        if not path.is_file():
            raise ValueError("File unavailable. Refresh the index or check OneDrive sync.")
        if path.suffix.lower() in {".exe", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".msi", ".lnk", ".url", ".scr", ".py", ".pyw", ".sh", ".r", ".m", ".jsl", ".hta", ".reg", ".cpl", ".msix", ".appx"}:
            raise ValueError("This file can execute code. Use Open Containing Folder and choose your editor or tool.")
        os.startfile(str(path))

    def open_folder(self, relative_path="."):
        self.validate_root()
        path = self.path(relative_path)
        if not path.is_dir():
            raise ValueError("Folder unavailable. Check OneDrive sync.")
        os.startfile(str(path))

    def open_containing_folder(self, relative_path):
        self.open_folder(PurePosixPath(normalized_relative(relative_path)).parent.as_posix())

    def summary(self):
        items = self.list_items()
        active = [i for i in items if i.get("state", "active") == "active"]
        return {"files": len(active), "size": sum(i["size"] for i in active),
                "last_index_time": self.index["last_index_time"], "unavailable": len(items) - len(active),
                "warnings": self.index.get("warnings", []), "changes": self.index.get("changes", {})}

    def refresh(self, rebuild=False, cancel=None, progress=None):
        marker = self.validate_root()
        if self.cache_error:
            raise ValueError(self.cache_error + " Choose a different local cache or restore valid JSON before indexing.")
        cancel = cancel or (lambda: False)
        progress = progress or (lambda count: None)
        old = self.index if self.index.get("project_id") == self.project_key(marker) else {"records": [], "next_id": 1, "events": []}
        previous = {i["relative_path"]: i for i in old["records"]}
        records, warnings, changes, uncertain, bad_metadata_dirs = {}, [], [], set(), set()
        next_id = old.get("next_id", 1)
        now = timestamp()
        scanned = 0

        def metadata(directory, inherited):
            values = dict(inherited)
            for name in ("experiment.json", "run.json", "sample.json", "procedure.json", "metadata.json"):
                path = directory / name
                try:
                    if not path.exists():
                        continue
                    info = path.lstat()
                    if redirects(info) or placeholder(info) or info.st_size > 1024 * 1024:
                        bad_metadata_dirs.add(directory.relative_to(self.root).as_posix())
                        warnings.append({"path": path.relative_to(self.root).as_posix(), "message": "Metadata skipped: linked, cloud-only, or larger than 1 MB."})
                        continue
                    data = read_json(path, {})
                    if not isinstance(data, dict):
                        raise ValueError("Metadata must be an object.")
                    if data.get("schema_version", 1) != 1:
                        raise ValueError("Unsupported metadata schema.")
                    parsed_values = {}
                    for key in (*RELATION_KEYS, 'category', 'subcategory'):
                        if key in data:
                            if not isinstance(data[key], str):
                                raise ValueError(f"{key} must be text.")
                            parsed_values[key] = data[key]
                    if isinstance(data.get("procedure"), dict):
                        for source, key in (("id", "procedure_id"), ("version", "procedure_version")):
                            if isinstance(data["procedure"].get(source), str):
                                parsed_values[key] = data["procedure"][source]
                    values.update(parsed_values)
                except (OSError, ValueError) as exc:
                    bad_metadata_dirs.add(directory.relative_to(self.root).as_posix())
                    warnings.append({"path": path.relative_to(self.root).as_posix(), "message": str(exc)})
            return values

        stack = [(self.root, {})]
        while stack:
            if cancel():
                raise IndexCancelled("Indexing cancelled. Previous index preserved.")
            directory, inherited = stack.pop()
            directory_metadata = metadata(directory, inherited)
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if cancel():
                            raise IndexCancelled("Indexing cancelled. Previous index preserved.")
                        relative = Path(entry.path).relative_to(self.root).as_posix()
                        try:
                            info = entry.stat(follow_symlinks=False)
                            if redirects(info):
                                continue
                            if stat.S_ISDIR(info.st_mode):
                                if entry.name.casefold() not in EXCLUDED:
                                    stack.append((Path(entry.path), directory_metadata))
                                continue
                            if not stat.S_ISREG(info.st_mode) or any(fnmatch.fnmatch(entry.name.lower(), pattern) for pattern in ("~$*", "*.tmp", "*.part", "*.crdownload")):
                                continue
                            prior = previous.get(relative)
                            record = copy.deepcopy(prior) if prior else {"id": f"FILE-{next_id:06d}", "first_indexed": now, "modified_after_initial_index": False}
                            if not prior:
                                next_id += 1
                            modified_ns = info.st_mtime_ns
                            change = "added" if not prior else "restored" if prior.get("state") != "active" else "modified" if prior.get("modified_ns") != modified_ns or prior["size"] != info.st_size else ""
                            if change:
                                changes.append({"id": record["id"], "path": relative, "event": change, "timestamp": now})
                            if change == "modified":
                                record["modified_after_initial_index"] = True
                            relationships = infer_relationships(relative)
                            relationships.update(directory_metadata)
                            if "run_id" not in directory_metadata and relationships["experiment_id"]:
                                run_segments = [p for p in PurePosixPath(relative).parts if re.fullmatch(r"R\d+", p)]
                                if run_segments:
                                    relationships["run_id"] = relationships["experiment_id"] + "-" + run_segments[-1]
                            # Keep last known explicit relationships when malformed
                            # metadata makes the current folder unreliable.
                            parent_relative = directory.relative_to(self.root).as_posix()
                            if prior and any(p == "." or parent_relative == p or parent_relative.startswith(p + "/") for p in bad_metadata_dirs):
                                for key in RELATION_KEYS:
                                    if key not in directory_metadata and prior.get(key):
                                        relationships[key] = prior.get(key, "")
                            if relationships["run_id"].startswith("R") and relationships["experiment_id"]:
                                relationships["run_id"] = relationships["experiment_id"] + "-" + relationships["run_id"]
                            elif relationships["run_id"] and re.fullmatch(r"R\d+", PurePosixPath(relative).parent.name) and relationships["experiment_id"]:
                                relationships["run_id"] = relationships["experiment_id"] + "-" + PurePosixPath(relative).parent.name
                            parts = PurePosixPath(relative).parts
                            record.update({"relative_path": relative, "name": entry.name, "extension": Path(entry.name).suffix.lower(),
                                "size": info.st_size, "modified_ns": modified_ns,
                                "modified": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(), "category": classify(relative),
                                "archived": "99_Archive" in parts, "state": "active", "cloud_placeholder": placeholder(info),
                                "raw_data": any(part in ("04_Raw_Data", "sensor_data", "rig_test", "test_data", "pre_imaging", "post_imaging", "raw_data") for part in parts), **relationships})
                            from app.services.file_classifier import classify_file
                            settings = marker.get('settings', {})
                            record.update(classify_file(relative, explicit={**relationships, **directory_metadata},
                                manual=settings.get('file_overrides', {}).get(record['id']), rules=settings.get('file_classification')))
                            record['data_origin'] = 'archive' if record['archived'] else 'current'
                            record.pop("unavailable_since", None)
                            record.pop("scan_unverified", None)
                            records[relative] = record
                            scanned += 1
                            if scanned % 100 == 0:
                                progress(scanned)
                        except (OSError, ValueError, OverflowError) as exc:
                            uncertain.add(relative)
                            warnings.append({"path": relative, "message": str(exc)})
            except OSError as exc:
                relative = directory.relative_to(self.root).as_posix()
                uncertain.add(relative)
                warnings.append({"path": relative, "message": str(exc)})
        if self.project_key(self.validate_root()) != self.project_key(marker):
            raise ValueError("Project marker changed during indexing. Previous index preserved.")
        for relative, prior in previous.items():
            if relative not in records:
                retained = copy.deepcopy(prior)
                if any(prefix == "." or relative == prefix or relative.startswith(prefix + "/") for prefix in uncertain):
                    retained["scan_unverified"] = True
                elif prior.get("state") != "unavailable":
                    retained.update({"state": "unavailable", "unavailable_since": now})
                    changes.append({"id": prior["id"], "path": relative, "event": "removed", "timestamp": now})
                records[relative] = retained
        if cancel():
            raise IndexCancelled("Indexing cancelled. Previous index preserved.")
        counts = {kind: sum(c["event"] == kind for c in changes) for kind in ("added", "modified", "removed", "restored")}
        updated = {"schema_version": 1, "project_id": self.project_key(marker), "records": list(records.values()),
                   "last_index_time": now, "next_id": next_id, "warnings": warnings, "changes": counts,
                   "last_operation": "rebuild" if rebuild else "refresh", "events": old.get("events", []) + changes}
        write_json(self.index_path, updated)
        self.index = updated
        progress(scanned)
        return self.summary()
