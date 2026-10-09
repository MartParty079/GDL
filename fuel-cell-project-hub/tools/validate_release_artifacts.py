"""Validate real installer bytes, version/edition/source metadata and public assets."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.updates import OFFICIAL_REPOSITORY


def validate(directory, channel, version, commit):
    name = 'GDLResearchHubBeta-Setup.exe' if channel == 'beta' else 'GDLResearchHub-Setup.exe'
    if not re.fullmatch(r'\d+\.\d+\.\d+' + (r'-beta\.\d+' if channel == 'beta' else ''), version):
        raise ValueError('Version does not match release channel.')
    manifest = json.loads((directory / 'build-manifest.json').read_text(encoding='utf-8-sig'))
    if any(manifest.get(key) != value for key, value in {'channel': channel, 'version': version, 'commit': commit}.items()):
        raise ValueError('Build manifest version, channel or source mismatch.')
    binary = directory / name
    with binary.open('rb') as stream:
        if stream.read(2) != b'MZ':
            raise ValueError('Installer is not a Windows executable.')
        stream.seek(0)
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    fields = (directory / (name + '.sha256')).read_text(encoding='ascii').split()
    if fields != [digest, name]:
        raise ValueError('Installer checksum or asset name mismatch.')
    other = 'GDLResearchHub-Setup.exe' if channel == 'beta' else 'GDLResearchHubBeta-Setup.exe'
    if (directory / other).exists():
        raise ValueError('Release contains the other edition installer.')
    return {'channel': channel, 'version': version, 'commit': commit, 'asset': name, 'sha256': digest, 'bytes': binary.stat().st_size}


def published(tag, directory, channel, commit):
    base = f'https://api.github.com/repos/{OFFICIAL_REPOSITORY}'
    def get(url):
        return urlopen(Request(url, headers={'User-Agent': 'GDLResearchHub-ReleaseValidation'}), timeout=30)
    with get(base + '/releases/tags/' + tag) as response:
        release = json.load(response)
    if release.get('draft') or bool(release.get('prerelease')) != (channel == 'beta'):
        raise ValueError('Published release channel mismatch.')
    with get(base + '/commits/' + tag) as response:
        if json.load(response)['sha'] != commit:
            raise ValueError('Published tag does not match tested source.')
    assets = {a['name']: a for a in release['assets'] if a.get('state') == 'uploaded'}
    name = 'GDLResearchHubBeta-Setup.exe' if channel == 'beta' else 'GDLResearchHub-Setup.exe'
    directory.mkdir(parents=True, exist_ok=True)
    for filename in (name, name + '.sha256', 'build-manifest.json'):
        expected = f'https://github.com/{OFFICIAL_REPOSITORY}/releases/download/{tag}/{filename}'
        if filename not in assets or assets[filename]['browser_download_url'] != expected:
            raise ValueError('Required public updater asset is missing or has an invalid URL: ' + filename)
        temporary = directory / (filename + '.part')
        try:
            with get(expected) as response, temporary.open('wb') as stream:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 600 * 1024 * 1024:
                        raise ValueError('Release asset exceeds size limit.')
                    stream.write(chunk)
            if total != assets[filename]['size']:
                raise ValueError('Public download is incomplete.')
            temporary.replace(directory / filename)
        finally:
            temporary.unlink(missing_ok=True)
    return validate(directory, channel, tag.removeprefix('v'), commit)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--channel', required=True, choices=['beta', 'stable'])
    parser.add_argument('--version', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--published-tag')
    args = parser.parse_args()
    if args.published_tag and args.published_tag != 'v' + args.version:
        parser.error('Published tag/version mismatch.')
    result = published(args.published_tag, args.directory, args.channel, args.commit) if args.published_tag else validate(args.directory, args.channel, args.version, args.commit)
    print(json.dumps(result, indent=2))
