"""Official stable release checks and checksum-verified installer updates."""

import json
import re
import hashlib
import os
import time
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from app import __version__
from app.services.storage import read_json, write_json
from app.edition import BETA, ASSET_NAME

OFFICIAL_REPOSITORY = "MartParty079/GDL"
ASSET = ASSET_NAME


class UpdateError(ValueError):
    """Safe actionable text; raw transport exceptions must never reach the UI."""


@contextmanager
def update_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'update.lock').open('a+b') as stream:
        stream.seek(0); stream.write(b'0'); stream.flush(); stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise UpdateError('Stage: Staging\nAnother update is already running. Retry after it finishes.') from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def failure_reason(exc):
    if isinstance(exc, HTTPError):
        return f'GitHub returned HTTP {exc.code}. ' + ('Wait and retry.' if exc.code in (403, 429) else 'Retry or contact the release maintainer.')
    if isinstance(exc, (URLError, TimeoutError, ConnectionError)):
        return 'GitHub could not be reached. Check your connection and retry.'
    if isinstance(exc, PermissionError):
        return 'Windows denied access to the local update folder. Check permissions and security software.'
    if isinstance(exc, ValueError):
        return str(exc)
    return 'The operation was interrupted. Retry; your existing installation is unchanged.'


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
    record = {'timestamp': datetime.now(timezone.utc).isoformat(), 'current_version': __version__,
              'target_version': release.get('tag'), 'channel': 'beta' if BETA else 'stable',
              'asset': ASSET, 'stage': 'Release metadata', 'status': 'started',
              'signature': 'Not required by this release policy; SHA-256 is mandatory.',
              'staging_directory': str(directory)}
    try:
        with update_lock(directory):
            result = _verified_download(release, directory, record)
        record.update(status='verified', stage='Verified')
        return result
    except Exception as exc:
        reason = failure_reason(exc)
        record.update(status='failed', reason=reason, http_status=getattr(exc, 'code', None))
        raise UpdateError(f"Version: {record['target_version']}\nStage: {record['stage']}\nReason: {reason}\nYour existing installation was not changed.") from None
    finally:
        try:
            write_json(directory / 'update-diagnostics.local.json', record)
        except OSError:
            pass


def _verified_download(release, directory, record):
    fresh = latest_release()
    if fresh["tag"] != release["tag"] or not newer(fresh["tag"]):
        raise ValueError("Release changed. Check for updates again.")
    installer_url = asset_url(fresh, ASSET)
    checksum_url = asset_url(fresh, ASSET + ".sha256")
    record['stage'] = 'Checksum download'
    with urlopen(
        Request(checksum_url, headers={"User-Agent": "GDLResearchHub"}), timeout=8
    ) as response:
        fields = response.read(512).decode("ascii").split()
        checksum = fields[0] if fields else ''
    if len(fields) != 2 or fields[1].lstrip('*') != ASSET:
        raise ValueError('Published checksum must identify the installer for this edition.')
    if not re.fullmatch("[a-fA-F0-9]{64}", checksum):
        raise ValueError("Installer checksum unavailable.")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (fresh["tag"] + "-" + ASSET)
    record['expected_sha256'] = checksum.lower()
    if target.is_file() and valid_installer(target, checksum):
        write_json(target.with_suffix('.verified.json'), {'sha256': checksum.lower(), 'tag': fresh['tag'], 'asset': ASSET})
        return target
    target.with_suffix('.verified.json').unlink(missing_ok=True)
    target.unlink(missing_ok=True)
    temporary = target.with_suffix(".part")
    digest = hashlib.sha256()
    size = 0
    deadline = time.monotonic() + 600
    record['stage'] = 'Installer download'
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
        record.update(stage='Checksum verification', actual_sha256=digest.hexdigest(), downloaded_bytes=size)
        if fresh['assets'][ASSET].get('size') and size != fresh['assets'][ASSET]['size']:
            raise ValueError('Download is incomplete. Retry Download.')
        if digest.hexdigest() != checksum.lower():
            raise ValueError("Installer verification failed. Download discarded.")
        with temporary.open("rb") as stream:
            if stream.read(2) != b"MZ":
                raise ValueError("Windows installer is invalid.")
        os.replace(temporary, target)
        write_json(target.with_suffix('.verified.json'), {'sha256': checksum.lower(), 'tag': fresh['tag'], 'asset': ASSET})
        return target
    finally:
        temporary.unlink(missing_ok=True)


def launch_installer(path):
    if os.name != "nt":
        raise ValueError("Installer updates are available on Windows only.")
    if not path.is_file():
        raise ValueError("Verified installer unavailable.")
    receipt = read_json(path.with_suffix('.verified.json'), {})
    if receipt.get('asset') != ASSET or not newer(receipt.get('tag', '')) or not valid_installer(path, receipt.get('sha256', '')):
        raise UpdateError('Stage: Installer launch\nInstaller integrity changed or verification is missing. Retry Download.')
    diagnostic = read_json(path.parent / 'update-diagnostics.local.json', {})
    try:
        process = subprocess.Popen([str(path), "/SP-", "/NOCLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS", "/NORESTART"])
        diagnostic.update(stage='Installer launch', status='installer_started')
        return process
    except OSError as exc:
        diagnostic.update(stage='Installer launch', status='failed', reason=failure_reason(exc))
        raise UpdateError('Stage: Installer launch\n' + failure_reason(exc)) from None
    finally:
        try:
            write_json(path.parent / 'update-diagnostics.local.json', diagnostic)
        except OSError:
            pass


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
        try:
            return self._prepare()
        except UpdateError:
            raise
        except Exception as exc:
            reason = failure_reason(exc)
            try:
                write_json(self.directory / 'updates' / 'update-diagnostics.local.json', {
                    'timestamp': datetime.now(timezone.utc).isoformat(), 'current_version': __version__,
                    'target_version': self.read().get('tag'), 'channel': 'beta' if BETA else 'stable',
                    'asset': ASSET, 'stage': 'Release metadata', 'status': 'failed',
                    'reason': reason, 'http_status': getattr(exc, 'code', None)})
            except OSError:
                pass
            raise UpdateError('Stage: Release metadata\nReason: ' + reason + '\nYour existing installation was not changed.') from None

    def _prepare(self):
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
