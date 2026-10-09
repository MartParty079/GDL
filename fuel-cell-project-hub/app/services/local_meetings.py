"""Immutable, revision-checked meeting files; SQLite stays a local UI cache."""
import copy
import uuid
from app.services.storage import read_json, write_json
from app.services.updates import update_lock


def meeting_rows(accounts):
    rows = {}
    conflicted = set()
    for folder in (accounts.shared / 'Meetings', accounts.base / 'meetings-outbox'):
        for path in folder.glob('*.json'):
            row = read_json(path, {})
            identity, revision = row['id'], row['revision']
            key = (identity, revision)
            if key in rows and rows[key] != row:
                conflicted.add(identity)
            rows[key] = row
    if conflicted:
        raise ValueError('OneDrive meeting revision conflict. Export local drafts and ask the Admin to compare the immutable meeting files.')
    latest = {}
    for (identity, revision), row in rows.items():
        if identity not in latest or revision > latest[identity]['revision']:
            latest[identity] = row
    return list(latest.values())


def sync_meetings(service):
    a = service.accounts
    if not a.shared.parent.parent.is_dir():
        return 'OneDrive unavailable · meeting edits remain saved locally'
    folder = a.shared / 'Meetings'
    with update_lock(folder), service.connect() as db:
        remote = {r['id']: r for r in meeting_rows(a)}
        service.conflicts = []
        pending = [(identity, __import__('json').loads(payload)) for identity, payload in db.execute(
            'SELECT id,payload FROM meeting_cache WHERE user_id=? AND pending=1', (service.user,))]
        for identity, row in pending:
            previous = remote.get(identity)
            if (previous or {}).get('client_mutation_id') == row['client_mutation_id']:
                saved = previous
            elif (previous or {}).get('revision', 0) != row['revision']:
                service.conflicts.append(identity)
                continue
            else:
                saved = copy.deepcopy(row)
                saved['revision'] += 1
                write_json(folder / (identity + '-' + str(saved['revision']) + '-' + uuid.uuid4().hex + '.json'), saved)
            db.execute('UPDATE meeting_cache SET payload=?,pending=0 WHERE user_id=? AND id=?',
                       (__import__('json').dumps(saved), service.user, identity))
            remote[identity] = saved
        for identity, row in remote.items():
            db.execute('INSERT INTO meeting_cache VALUES(?,?,?,0) ON CONFLICT(user_id,id) DO UPDATE SET payload=excluded.payload WHERE meeting_cache.pending=0',
                       (service.user, identity, __import__('json').dumps(row)))
    return ('Meeting changes conflict with a shared revision; export your draft before reloading.'
            if service.conflicts else 'Meetings synchronized through OneDrive')
