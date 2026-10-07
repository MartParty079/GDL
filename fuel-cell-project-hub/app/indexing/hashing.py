"""Resident-file SHA-256 only, bounded by the manager's file and run budgets."""
import hashlib
from app.services.project_storage import placeholder


def hash_file(path, signature):
    if placeholder(path.stat()):
        return '', 'Online-only'
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    after = path.stat()
    if [after.st_size, after.st_mtime_ns] != signature:
        return '', 'Still syncing'
    return digest.hexdigest(), 'Locally available'
