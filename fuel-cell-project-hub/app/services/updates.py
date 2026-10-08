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

OFFICIAL_REPOSITORY = "MartParty079/GDL"
ASSET = "GDLResearchHub-Setup.exe"


def version(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
    return tuple(map(int, match.groups())) if match else None


def newer(tag, installed=__version__):
    candidate, current = version(tag), version(installed.split("-")[0])
    return bool(candidate and current and candidate > current)


def latest_release(repository=OFFICIAL_REPOSITORY):
    if repository != OFFICIAL_REPOSITORY:
        raise ValueError(
            "Updates use the official GDL Research Hub release repository."
        )
    request = Request(
        f"https://api.github.com/repos/{repository}/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "FuelCellProjectHub",
        },
    )
    with urlopen(request, timeout=8) as response:
        release = json.load(response)
    if (
        release.get("draft")
        or release.get("prerelease")
        or not version(release.get("tag_name", ""))
    ):
        raise ValueError("No stable release is available.")
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
    temporary = target.with_suffix(".part")
    digest = hashlib.sha256()
    size = 0
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
    return subprocess.Popen([str(path), "/SP-", "/CLOSEAPPLICATIONS", "/NORESTART"])
