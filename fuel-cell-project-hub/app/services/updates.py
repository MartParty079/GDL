"""Official stable release checks and checksum-verified installer updates."""

import json
import re
import hashlib
import os
import time
import subprocess
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from app import __version__
from app.services.storage import read_json, write_json
from app.edition import BETA, ASSET_NAME

OFFICIAL_REPOSITORY = "MartParty079/GDL"
ASSET = ASSET_NAME


def version(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:-beta\.(\d+))?", value)
    return tuple(map(int,match.groups()[:3]))+(0 if match[4] else 1,int(match[4] or 0)) if match else None


def newer(tag, installed=__version__):
    candidate, current = version(tag), version(installed)
    return bool(candidate and current and candidate[3] == current[3] and candidate > current)


def latest_release(repository=OFFICIAL_REPOSITORY):
    if repository != OFFICIAL_REPOSITORY:
        raise ValueError(
            "Updates use the official GDL Research Hub release repository."
        )
    request = Request(
        f"https://api.github.com/repos/{repository}/releases" + ("?per_page=100" if BETA else "/latest"),
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "FuelCellProjectHub",
        },
    )
    with urlopen(request, timeout=8) as response:
        release = json.load(response)
    if BETA:
        candidates=[r for r in release if not r.get('draft') and r.get('prerelease') and version(r.get('tag_name','')) and version(r['tag_name'])[3]==0]
        if not candidates:raise ValueError('No Beta update is available.')
        release=max(candidates,key=lambda r:version(r['tag_name']))
    if (
        release.get("draft")
        or bool(release.get("prerelease")) != BETA
        or not version(release.get("tag_name", ""))
        or (version(release.get('tag_name',''))[3]==0) != BETA
    ):
        raise ValueError("No release is available for this edition.")
    tag = release["tag_name"]
    url = release["html_url"]
    if url != f"https://github.com/{OFFICIAL_REPOSITORY}/releases/tag/{tag}":
        raise ValueError("Release source could not be verified.")
    assets = {
        a["name"]: a for a in release.get("assets", []) if a.get("state") == "uploaded"
    }
    return {
        "tag": tag,
        "url": url,
        "name": release.get("name") or tag,
        "notes": str(release.get("body", ""))[:30000],
        "assets": assets,
    }


def cached_release(directory, manual=False):
    path = directory / "release-check.local.json"
    cached = read_json(path, {})
    if (
        not manual
        and time.time() - cached.get("checked_at", 0) < 86400
        and cached.get("release")
    ):
        return cached["release"]
    result = latest_release()
    write_json(path, {"checked_at": time.time(), "release": result})
    return result


def asset_url(release, name):
    asset = release["assets"].get(name)
    expected = f"https://github.com/{OFFICIAL_REPOSITORY}/releases/download/{release['tag']}/{name}"
    if not asset or asset.get("browser_download_url") != expected:
        raise ValueError(
            "The verified Windows installer is not available for this release."
        )
    return expected


def verified_download(release, directory):
    fresh = latest_release()
    if fresh["tag"] != release["tag"] or not newer(fresh["tag"]):
        raise ValueError("Release changed. Check for updates again.")
    installer_url = asset_url(fresh, ASSET)
    checksum_url = asset_url(fresh, ASSET + ".sha256")
    with urlopen(
        Request(checksum_url, headers={"User-Agent": "GDLResearchHub"}), timeout=8
    ) as response:
        checksum = response.read(512).decode("ascii").split()[0]
    if not re.fullmatch("[a-fA-F0-9]{64}", checksum):
        raise ValueError("Installer checksum unavailable.")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (fresh["tag"] + "-" + ASSET)
    if target.is_file() and valid_installer(target, checksum):
        return target
    temporary = target.with_suffix(".part")
    digest = hashlib.sha256()
    size = 0
    deadline = time.monotonic() + 90
    try:
        with urlopen(
            Request(installer_url, headers={"User-Agent": "GDLResearchHub"}), timeout=15
        ) as response, temporary.open("wb") as stream:
            if urlparse(response.geturl()).hostname not in (
                "github.com",
                "release-assets.githubusercontent.com",
                "objects.githubusercontent.com",
            ):
                raise ValueError("Installer download source could not be verified.")
            while chunk := response.read(1024 * 1024):
                if time.monotonic() > deadline:
                    raise ValueError("Update download timed out. Retry later.")
                size += len(chunk)
                if size > 600 * 1024 * 1024:
                    raise ValueError("Installer exceeds the supported size.")
                digest.update(chunk)
                stream.write(chunk)
        if digest.hexdigest() != checksum.lower():
            raise ValueError("Installer verification failed. Download discarded.")
        with temporary.open("rb") as stream:
            if stream.read(2) != b"MZ":
                raise ValueError("Windows installer is invalid.")
        os.replace(temporary, target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


def launch_installer(path):
    if os.name != "nt":
        raise ValueError("Installer updates are available on Windows only.")
    if not path.is_file():
        raise ValueError("Verified installer unavailable.")
    return subprocess.Popen([str(path), "/SP-", "/NOCLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS", "/NORESTART"])


def valid_installer(path, checksum):
    """Recheck cached bytes before handing them to Windows."""
    if not re.fullmatch(r'[a-fA-F0-9]{64}', checksum):
        return False
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        if stream.read(2) != b'MZ':
            return False
        stream.seek(0)
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest() == checksum.lower()


class PendingUpdate:
    """Atomic per-user preference; no session, index or research files are changed."""
    def __init__(self, directory):
        self.directory = directory
        self.path = directory / 'pending-update.local.json'

    def read(self):
        try:
            row = read_json(self.path, {})
            return row if isinstance(row, dict) and version(row.get('tag', '')) else {}
        except ValueError:
            return {}

    def schedule(self, release):
        if not newer(release['tag']):
            raise ValueError('A newer update for this edition is required.')
        previous = self.read()
        if previous and version(previous['tag']) > version(release['tag']):
            raise ValueError('A newer update is already scheduled.')
        write_json(self.path, {'tag': release['tag'], 'status': 'scheduled'})

    def prepare(self):
        pending = self.read()
        if not pending:
            return None
        if not newer(pending['tag']):
            self.path.unlink(missing_ok=True)
            return None
        release = latest_release()
        if not newer(release['tag']) or version(release['tag']) < version(pending['tag']):
            raise ValueError('The scheduled update is not available yet.')
        # Newer stable releases supersede the scheduled one; never downgrade.
        self.schedule(release)
        return verified_download(release, self.directory / 'updates')

    def launched(self):
        row = self.read()
        if row:
            row['status'] = 'installer_started'
            write_json(self.path, row)
