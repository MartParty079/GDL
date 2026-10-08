"""Audit staged source before publication; never print sensitive matched values."""
import re
import subprocess
import sys
from pathlib import PurePosixPath

BLOCKED_DIRECTORIES = {'.project_hub', '.venv', 'venv', 'env', '__pycache__', 'build', 'dist', 'runtime',
                       'logs', 'auth', 'tokens', 'secrets', '.projecthub', '.test-state', 'cache', 'backups', 'generated'}
DATA_EXTENSIONS = {'.tif', '.tiff', '.mp4', '.avi', '.mov', '.csv', '.xls', '.xlsx', '.parquet', '.h5', '.hdf5'}
SECRET_PATTERNS = [re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'), re.compile(r'github_pat_[A-Za-z0-9_]{30,}'),
                   re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
                   re.compile(r'(?i)(?:access_token|refresh_token|client_secret|api_key|password)[\"\']?\s*[=:]\s*[\"\']([A-Za-z0-9_./+\-=]{32,})[\"\']')]
PERSONAL_PATH = re.compile(r'(?i)[a-z]:[/\\]+Users[/\\]+[^/\\\s\"\']+')


def audit_blob(name, data):
    path = PurePosixPath(name)
    problems = []
    if any(part in BLOCKED_DIRECTORIES for part in path.parts) or 'analysis/gdl/baseline/' in name:
        problems.append('local/runtime/private directory')
    if path.suffix.lower() in DATA_EXTENSIONS or path.suffix.lower() in {'.pyc', '.pyo', '.log', '.token', '.sqlite3', '.db'}:
        problems.append('dataset or generated file')
    if path.name in {'local.json', 'local_config.json', 'user_config.json', 'project_settings.json', 'tokens.bin'} or path.name.startswith('.env'):
        problems.append('personal configuration or credentials')
    if name.endswith('/config/project.json') or '/config/history/' in name:
        problems.append('live project configuration')
    if len(data) > 10 * 1024 * 1024:
        problems.append('large file needs explicit publication review')
    try:
        content = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return problems
    if any(pattern.search(content) for pattern in SECRET_PATTERNS):
        problems.append('potential credential')
    # Documentation records historical examples; tests contain deliberately fake
    # paths. Active code/config must not contain a personal Windows home path.
    if 'docs' not in path.parts and 'tests' not in path.parts and PERSONAL_PATH.search(content):
        problems.append('active personal machine path')
    return problems


def git(*args):
    return subprocess.check_output(['git', *args])


def main():
    repository = git('rev-parse', '--show-toplevel').decode().strip()
    names = git('-C', repository, 'ls-files', '-z').decode().split('\0')
    failures = []
    count = 0
    for name in filter(None, names):
        data = git('-C', repository, 'show', ':' + name)
        issues = audit_blob(name, data)
        failures.extend(name + ': ' + problem for problem in issues)
        count += 1
    if failures:
        print('\n'.join(failures))
        return 1
    print(f'Staged source audit passed: {count} files; no blocked files or credential patterns found.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
