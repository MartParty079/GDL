"""Research objects and events in the existing catalog; source files stay untouched."""

import json
import uuid
from app.services.storage import timestamp

EXPERIMENT_TYPES = (
    "Optical Microscopy",
    "Image Analysis",
    "Compression Testing",
    "Water Intrusion",
    "Pressure Testing",
    "Flow Testing",
    "Laser Testing",
    "Calibration",
    "Sample Preparation",
    "Validation",
    "Other",
)
SAMPLE_FIELDS = (
    "name",
    "description",
    "material",
    "manufacturer",
    "gdl_type",
    "batch",
    "thickness",
    "received_date",
    "created_date",
    "status",
    "notes",
    "tags",
)
EXPERIMENT_FIELDS = (
    "name",
    "type",
    "sample_id",
    "date",
    "operator",
    "status",
    "description",
    "procedure",
    "equipment",
    "notes",
    "results_summary",
)


def create_schema(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS research_objects(id TEXT PRIMARY KEY,kind TEXT,project_id TEXT,origin TEXT,payload TEXT,updated_at TEXT,favorite INTEGER DEFAULT 0)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS object_project ON research_objects(kind,project_id,origin)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS research_events(id TEXT PRIMARY KEY,project_id TEXT,sample_id TEXT,experiment_id TEXT,file_id TEXT,kind TEXT,at TEXT,detail TEXT,origin TEXT)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS event_scope ON research_events(project_id,sample_id,experiment_id,at)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS workspace_recent(file_id TEXT PRIMARY KEY,viewed_at TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS workspace_files(file_id TEXT PRIMARY KEY,added_at TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS research_file_links(file_id TEXT PRIMARY KEY,sample_id TEXT,experiment_id TEXT,FOREIGN KEY(file_id) REFERENCES files(id))"
    )
    # Previously explicit manual overrides are confirmed links; filename inference is not.
    db.execute(
        """INSERT OR IGNORE INTO research_file_links SELECT o.id,
        coalesce(json_extract(o.payload,'$.sample_id'),''),coalesce(json_extract(o.payload,'$.experiment_id'),'')
        FROM overrides o JOIN files f ON f.id=o.id WHERE json_valid(o.payload) AND
        (json_extract(o.payload,'$.sample_id') IS NOT NULL OR json_extract(o.payload,'$.experiment_id') IS NOT NULL)"""
    )
    db.execute("CREATE TABLE IF NOT EXISTS workspace_hidden(file_id TEXT PRIMARY KEY)")
    db.execute(
        "CREATE TABLE IF NOT EXISTS workspace_revisions(id TEXT PRIMARY KEY,file_id TEXT,at TEXT,payload TEXT)"
    )


class ResearchWorkspace:
    def __init__(self, catalog):
        self.catalog = catalog
        self.project_id = catalog.locations.value["active"]["id"]

    def objects(self, kind, origin="current", query="", favorite=False):
        clauses = ["kind=?", "project_id=?"]
        args = [kind, self.project_id]
        if origin:
            clauses.append("origin=?")
            args.append(origin)
        if favorite:
            clauses.append("favorite=1")
        with self.catalog.connect() as db:
            rows = db.execute(
                "SELECT payload,origin,favorite,updated_at FROM research_objects WHERE "
                + " AND ".join(clauses)
                + " ORDER BY updated_at DESC",
                args,
            ).fetchall()
        result = [
            dict(json.loads(p), origin=o, favorite=bool(f), updated_at=t)
            for p, o, f, t in rows
        ]
        return [r for r in result if query.casefold() in json.dumps(r).casefold()]

    def get(self, identity):
        with self.catalog.connect() as db:
            row = db.execute(
                "SELECT payload,origin,favorite,kind FROM research_objects WHERE id=? AND project_id=?",
                (identity, self.project_id),
            ).fetchone()
        return (
            dict(json.loads(row[0]), origin=row[1], favorite=bool(row[2]), kind=row[3])
            if row
            else None
        )

    def save(self, kind, values, identity=None, origin="current"):
        if kind not in ("sample", "experiment") or origin not in ("current", "legacy"):
            raise ValueError("Choose a research object and its origin.")
        previous = self.get(identity) if identity else None
        if identity and not previous:
            with self.catalog.connect() as db:
                if db.execute(
                    "SELECT 1 FROM research_objects WHERE id=?", (identity,)
                ).fetchone():
                    raise ValueError(
                        "That identity belongs to another project. Choose a different ID."
                    )
        if previous and (previous["kind"] != kind or previous["origin"] != origin):
            raise ValueError("Keep current and legacy objects separate.")
        identity = identity or (
            ("S-" if kind == "sample" else "E-") + uuid.uuid4().hex[:10]
        )
        fields = SAMPLE_FIELDS if kind == "sample" else EXPERIMENT_FIELDS
        payload = {
            k: str(values.get(k, previous.get(k, "") if previous else ""))
            for k in fields
        }
        payload["id"] = identity
        from datetime import date

        for key in ("date", "created_date", "received_date"):
            if payload.get(key):
                try:
                    date.fromisoformat(payload[key])
                except ValueError:
                    raise ValueError(
                        "Use YYYY-MM-DD for research dates, or leave them blank."
                    ) from None
        if not payload["name"].strip():
            raise ValueError("Enter a descriptive name.")
        if kind == "experiment":
            sample = self.get(payload["sample_id"]) if payload["sample_id"] else None
            if payload["sample_id"] and (
                not sample or sample["kind"] != "sample" or sample["origin"] != origin
            ):
                raise ValueError(
                    "Choose a sample with the same current or legacy origin."
                )
            for key in ("conditions", "results"):
                entries = values.get(key, previous.get(key, []) if previous else [])
                if (
                    not isinstance(entries, list)
                    or len(entries) > 200
                    or any(not isinstance(e, dict) for e in entries)
                ):
                    raise ValueError(
                        "Use at most 200 named condition or result entries."
                    )
                payload[key] = [
                    {k: str(e.get(k, "")) for k in ("name", "value", "unit", "notes")}
                    for e in entries
                ]
        if (
            previous
            and kind == "experiment"
            and previous.get("sample_id") != payload["sample_id"]
        ):
            with self.catalog.connect() as db:
                if db.execute(
                    "SELECT 1 FROM research_file_links WHERE experiment_id=? LIMIT 1",
                    (identity,),
                ).fetchone():
                    raise ValueError(
                        "Unassign this experiment from its files before changing its sample."
                    )
        now = timestamp()
        with self.catalog.connect() as db:
            db.execute(
                "INSERT INTO research_objects VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at,favorite=excluded.favorite",
                (
                    identity,
                    kind,
                    self.project_id,
                    origin,
                    json.dumps(payload),
                    now,
                    int(
                        values.get(
                            "favorite",
                            previous.get("favorite", False) if previous else False,
                        )
                    ),
                ),
            )
            self.event(
                db,
                kind + (" updated" if previous else " created"),
                payload["name"],
                sample_id=(
                    identity if kind == "sample" else payload.get("sample_id", "")
                ),
                experiment_id=identity if kind == "experiment" else "",
                origin=origin,
            )
            if previous and previous.get("status") != payload.get("status"):
                self.event(
                    db,
                    kind + " status changed",
                    payload["status"],
                    sample_id=(
                        identity if kind == "sample" else payload.get("sample_id", "")
                    ),
                    experiment_id=identity if kind == "experiment" else "",
                    origin=origin,
                )
            if previous and previous.get("notes") != payload.get("notes"):
                self.event(
                    db,
                    "Note updated",
                    payload["name"],
                    sample_id=(
                        identity if kind == "sample" else payload.get("sample_id", "")
                    ),
                    experiment_id=identity if kind == "experiment" else "",
                    origin=origin,
                )
            key = "sample_id" if kind == "sample" else "experiment_id"
            cursor = db.execute(
                "SELECT f.payload FROM files f JOIN research_file_links m ON m.file_id=f.id WHERE m."
                + key
                + "=?",
                (identity,),
            )
            while batch := cursor.fetchmany(250):
                for (record,) in batch:
                    self.catalog.upsert(db, json.loads(record), update_search=True)
        return self.get(identity)

    def event(
        self,
        db,
        kind,
        detail,
        sample_id="",
        experiment_id="",
        file_id="",
        origin="current",
    ):
        db.execute(
            "INSERT INTO research_events VALUES (?,?,?,?,?,?,?,?,?)",
            (
                uuid.uuid4().hex,
                self.project_id,
                sample_id,
                experiment_id,
                file_id,
                kind,
                timestamp(),
                detail,
                origin,
            ),
        )

    def timeline(self, sample="", experiment="", origin="current", limit=300):
        clauses = ["project_id=?"]
        args = [self.project_id]
        for column, value in (
            ("sample_id", sample),
            ("experiment_id", experiment),
            ("origin", origin),
        ):
            if value:
                clauses.append(column + "=?")
                args.append(value)
        with self.catalog.connect() as db:
            rows = db.execute(
                "SELECT kind,at,detail,sample_id,experiment_id,file_id,origin FROM research_events WHERE "
                + " AND ".join(clauses)
                + " ORDER BY at DESC LIMIT ?",
                args + [limit],
            ).fetchall()
        return [
            dict(
                zip(
                    (
                        "kind",
                        "at",
                        "detail",
                        "sample_id",
                        "experiment_id",
                        "file_id",
                        "origin",
                    ),
                    r,
                )
            )
            for r in rows
        ]

    def annotate(self, rows, values, append_tags=False):
        # Validate the whole batch before modifying anything, and commit all associations atomically.
        allowed = {
            "sample_id",
            "experiment_id",
            "category",
            "tags",
            "title",
            "notes",
            "description",
            "favorite",
            "report_version",
            "report_status",
            "data_stage",
        }
        if (
            set(values) - allowed
            or any(not isinstance(v, str) for k, v in values.items() if k != "favorite")
            or ("favorite" in values and not isinstance(values["favorite"], bool))
        ):
            raise ValueError("Unsupported research metadata.")
        fresh = []
        with self.catalog.connect() as db:
            for item in rows:
                found = db.execute(
                    "SELECT payload FROM files WHERE id=?", (item["id"],)
                ).fetchone()
                if not found:
                    raise ValueError("Refresh the index before editing this selection.")
                row = json.loads(found[0])
                merged = {**row, **values}
                if append_tags and "tags" in values:
                    merged["tags"] = ", ".join(
                        dict.fromkeys(
                            t.strip()
                            for t in (row.get("tags", "") + "," + values["tags"]).split(
                                ","
                            )
                            if t.strip()
                        )
                    )
                links = db.execute(
                    "SELECT sample_id,experiment_id FROM research_file_links WHERE file_id=?",
                    (row["id"],),
                ).fetchone() or ("", "")
                sample = (
                    self.get(merged.get("sample_id"))
                    if merged.get("sample_id")
                    and ("sample_id" in values or links[0] == merged["sample_id"])
                    else None
                )
                exp = (
                    self.get(merged.get("experiment_id"))
                    if merged.get("experiment_id")
                    and (
                        "experiment_id" in values or links[1] == merged["experiment_id"]
                    )
                    else None
                )
                if sample and sample["kind"] != "sample":
                    raise ValueError("Choose a sample identity for the sample field.")
                if exp and exp["kind"] != "experiment":
                    raise ValueError(
                        "Choose an experiment identity for the experiment field."
                    )
                for obj in (sample, exp):
                    if (
                        obj
                        and ("sample_id" in values or "experiment_id" in values)
                        and obj["origin"] != row["data_origin"]
                    ):
                        raise ValueError(
                            "Assign current files to current objects and legacy files to legacy objects."
                        )
                if "sample_id" in values and values["sample_id"] and not sample:
                    raise ValueError("Create or select the sample first.")
                if "experiment_id" in values and values["experiment_id"] and not exp:
                    raise ValueError("Create or select the experiment first.")
                if (
                    exp
                    and ("experiment_id" in values or "sample_id" in values)
                    and exp.get("sample_id")
                    and merged.get("sample_id") != exp["sample_id"]
                ):
                    if "sample_id" in values:
                        raise ValueError(
                            "This experiment belongs to a different sample."
                        )
                    merged["sample_id"] = exp["sample_id"]
                fresh.append((row, merged))
            for row, merged in fresh:
                old = db.execute(
                    "SELECT payload FROM overrides WHERE id=?", (row["id"],)
                ).fetchone()
                override = {
                    **(json.loads(old[0]) if old else {}),
                    **{k: merged[k] for k in values},
                }
                if (
                    "experiment_id" in values
                    and values["experiment_id"]
                    and self.get(values["experiment_id"]).get("sample_id")
                ):
                    override["sample_id"] = merged["sample_id"]
                if merged.get("sample_id") != row.get("sample_id"):
                    override["sample_id"] = merged["sample_id"]
                db.execute(
                    "INSERT OR REPLACE INTO overrides VALUES (?,?)",
                    (row["id"], json.dumps(override)),
                )
                db.execute(
                    "INSERT INTO workspace_revisions VALUES (?,?,?,?)",
                    (uuid.uuid4().hex, row["id"], timestamp(), json.dumps(row)),
                )
                self.catalog.upsert(db, merged, update_search=True)
                self.event(
                    db,
                    "File metadata updated",
                    row["name"],
                    sample_id=merged.get("sample_id", ""),
                    experiment_id=merged.get("experiment_id", ""),
                    file_id=row["id"],
                    origin=row["data_origin"],
                )

    def record_event(self, kind, detail, sample="", experiment="", origin="current"):
        allowed = (
            "Note added",
            "Experiment started",
            "Experiment completed",
            "Analysis performed",
            "Report revised",
            "Sample status changed",
        )
        if kind not in allowed or not detail.strip():
            raise ValueError("Choose an event type and enter its details.")
        obj = self.get(experiment or sample) if (experiment or sample) else None
        if (experiment or sample) and not obj:
            raise ValueError("Select an existing sample or experiment.")
        if obj:
            origin = obj["origin"]
            if experiment:
                sample = obj.get("sample_id", "")
        with self.catalog.connect() as db:
            self.event(
                db,
                kind,
                detail,
                sample_id=sample,
                experiment_id=experiment,
                origin=origin,
            )

    def viewed(self, row):
        with self.catalog.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO workspace_recent VALUES (?,?)",
                (row["id"], timestamp()),
            )

    def hide(self, row):
        with self.catalog.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO workspace_hidden VALUES (?)", (row["id"],)
            )
            self.event(
                db,
                "File hidden from workspace",
                row["name"],
                file_id=row["id"],
                origin=row["data_origin"],
            )

    def restore_hidden(self):
        with self.catalog.connect() as db:
            db.execute("DELETE FROM workspace_hidden")

    def suggestions(self, row):
        text = (row["relative_path"] + " " + row.get("notes", "")).casefold()
        return [
            obj
            for kind in ("sample", "experiment")
            for obj in self.objects(kind, row["data_origin"])
            if obj["id"].casefold() in text
            or (len(obj["name"]) >= 4 and obj["name"].casefold() in text)
        ]

    def revisions(self, row):
        with self.catalog.connect() as db:
            return [
                dict(at=t, metadata=json.loads(p))
                for t, p in db.execute(
                    "SELECT at,payload FROM workspace_revisions WHERE file_id=? ORDER BY at DESC LIMIT 50",
                    (row["id"],),
                )
            ]

    def locate(self, row, path):
        from pathlib import Path
        from app.services.project_storage import normalized_relative

        source = next(
            s for s in self.catalog.locations.sources() if s["id"] == row["source_id"]
        )
        relative = (
            Path(path)
            .resolve()
            .relative_to(Path(source["root_path"]).resolve())
            .as_posix()
        )
        candidate = {**row, "relative_path": normalized_relative(relative)}
        safe = self.catalog.safe_path(candidate)
        if not safe.is_file():
            raise ValueError("Choose an existing file within its original source.")
        with self.catalog.connect() as db:
            if db.execute(
                "SELECT 1 FROM files WHERE source=? AND json_extract(payload,'$.relative_path')=? AND id<>?",
                (row["source_id"], relative, row["id"]),
            ).fetchone():
                raise ValueError(
                    "That file is already indexed. Use a relationship instead."
                )
            stat = safe.stat()
            candidate.update(
                name=safe.name,
                full_path=str(safe),
                extension=safe.suffix.lower(),
                parent_folder=str(Path(relative).parent).replace("\\", "/"),
                size=stat.st_size,
                signature="",
                availability="Local",
            )
            self.catalog.upsert(db, candidate, update_search=True)
            db.execute("DELETE FROM content_index WHERE id=?", (row["id"],))
            self.event(
                db,
                "File reference located",
                candidate["name"],
                file_id=row["id"],
                origin=row["data_origin"],
            )
        return candidate
