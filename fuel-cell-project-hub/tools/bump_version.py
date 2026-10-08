"""Append one traceable work-order version; packaging derives its metadata."""

import argparse
import json
import re
import runpy
from datetime import date
from pathlib import Path


def check(root):
    current = runpy.run_path(str(root / "app/version.py"))["VERSION"]
    history = json.loads((root / "version_history.json").read_text(encoding="utf-8"))
    versions = [row["version"] for row in history["versions"]]
    if not versions or versions[-1] != current or len(set(versions)) != len(versions):
        raise ValueError("Canonical version and append-only history disagree.")
    if f"## {current}" not in (root / "CHANGELOG.md").read_text(encoding="utf-8"):
        raise ValueError("Current version is missing from CHANGELOG.")
    return current, history


def bump(root, kind, work_order, summary, features=(), fixes=(), breaking=()):
    current, history = check(root)
    if not re.fullmatch(r"\d+\.\d+\.\d+", current):
        raise ValueError("Work-order bumps require a stable canonical version.")
    major, minor, patch = map(int, current.split("."))
    target = {
        "patch": (major, minor, patch + 1),
        "minor": (major, minor + 1, 0),
        "major": (major + 1, 0, 0),
    }[kind]
    version = ".".join(map(str, target))
    stamp = date.today().isoformat()
    history["versions"].append(
        {
            "version": version,
            "date": stamp,
            "work_order": work_order,
            "summary": summary,
            "major_features": list(features),
            "major_fixes": list(fixes),
            "breaking_changes": list(breaking),
            "git_commit": None,
            "git_release_tag": None,
        }
    )
    source = root / "app/version.py"
    text = source.read_text(encoding="utf-8")
    text = re.sub(r'^VERSION = "[^"]+"$', f'VERSION = "{version}"', text, flags=re.M)
    text = re.sub(
        r'^PREVIOUS_VERSION = "[^"]+"$',
        f'PREVIOUS_VERSION = "{current}"',
        text,
        flags=re.M,
    )
    source.write_text(text, encoding="utf-8")
    edition = root / 'config/edition.json'
    if edition.exists():
        settings=json.loads(edition.read_text(encoding='utf-8'))
        settings.update(channel='beta',beta_sequence=1)
        edition.write_text(json.dumps(settings,indent=2)+'\n',encoding='utf-8')
    (root / "version_history.json").write_text(
        json.dumps(history, indent=2) + "\n", encoding="utf-8"
    )
    orders = root / 'work_order_history.json'
    if orders.exists():
        value = json.loads(orders.read_text(encoding='utf-8'))
        value['work_orders'].append({'work_order_id': re.sub(r'[^a-z0-9]+', '-', work_order.lower()).strip('-'),
            'title': work_order, 'version': version, 'started_at': stamp, 'completed_at': None,
            'summary': summary, 'status': 'implemented', 'channel': 'beta'})
        orders.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    changelog = root / "CHANGELOG.md"
    notes = f"## {version} — {stamp}\n\n- {summary}\n" + "".join(
        f"- {item}\n" for item in (*features, *fixes, *breaking)
    )
    changelog.write_text(
        changelog.read_text(encoding="utf-8").replace(
            "# Changelog\n", "# Changelog\n\n" + notes, 1
        ),
        encoding="utf-8",
    )
    check(root)
    return current, version


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["patch", "minor", "major", "check"])
    parser.add_argument("--work-order")
    parser.add_argument("--summary")
    parser.add_argument("--feature", action="append", default=[])
    parser.add_argument("--fix", action="append", default=[])
    parser.add_argument("--breaking", action="append", default=[])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.kind == "check":
        print("Version consistency passed:", check(root)[0])
    else:
        import subprocess
        if subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip() != 'develop':
            parser.error('Work-order version changes belong on develop. Stable promotes an already tested version.')
        if not args.work_order or not args.summary:
            parser.error(
                "--work-order and --summary are required for a traceable release"
            )
        print(
            " -> ".join(
                bump(
                    root,
                    args.kind,
                    args.work_order,
                    args.summary,
                    args.feature,
                    args.fix,
                    args.breaking,
                )
            )
        )
