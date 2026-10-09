"""Organizational identities and immutable activity transport. No network identity.

OneDrive ACLs protect the files. PINs prevent casual profile switching, not
malicious edits by someone with write access. Only the enrolled device writes
profiles; revisions and an OS lock catch local concurrency, while synchronized
conflict copies stop further writes until the owner resolves them.
"""
import copy
import hashlib
import hmac
import os
import re
import secrets
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

from app.edition import CHANNEL, DISPLAY_VERSION
from app.services.storage import read_json, write_json, timestamp
from app.services.updates import update_lock

NAMES = ('Matthew Kime', 'Andrew Michelson', 'Monterrius Ridley', 'Ryan Rodriguez')
ITERATIONS = 600_000


def password_hash(value):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', value.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return dict(algorithm='pbkdf2-sha256', iterations=ITERATIONS, salt=salt, digest=digest)


def matches(value, record):
    if not record:
        return not value
    try:
        if record['algorithm'] != 'pbkdf2-sha256' or not 100_000 <= record['iterations'] <= 2_000_000:
            return False
        digest = hashlib.pbkdf2_hmac('sha256', value.encode(), bytes.fromhex(record['salt']), record['iterations']).hex()
        return hmac.compare_digest(digest, record['digest'])
    except (ValueError, KeyError, TypeError):
        return False


def validate_pin(value, required=False):
    if (value or required) and not re.fullmatch(r'[0-9]{4,6}', value):
        raise ValueError('Choose a PIN containing four to six digits.')


class LocalAccounts:
    local_identity = True

    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='local-activity')
        self.install_id = store.local.setdefault('local_identity_device', str(uuid.uuid4()))
        store.save_local()
        self.profile = None
        self.session = None
        self.participation = None
        self.pending = []
        self.offline = False
        self.warning = ''
        self.admin_unlocked = False
        self.launch_recorded = False
        self.base = store.local_dir / 'identity'
        self.base.mkdir(parents=True, exist_ok=True)
        self.shared = self.storage_root()
        self.cache = self.base / 'profiles-cache.json'
        self.registry = self.load_registry()

    def storage_root(self):
        """Edition-separated subfolder under the configured project, never a DB."""
        locations = self.store.local.get('project_locations', {})
        root = locations.get('shared_storage') if locations.get('enabled') else None
        root = Path(root) if root else self.store.local_dir / 'research-sandbox' / 'shared'
        if self.store.sandbox_required and not root.resolve().is_relative_to(self.store.local_dir.resolve()):
            raise ValueError('Development and Beta identity storage must stay in the isolated sandbox.')
        return root / 'AppData' / CHANNEL

    def prepare_storage(self, root):
        """Admin-requested remapping copies identity transport, never research/DBs.

        Profiles are published last. A failed preparation preserves the original
        binding and immutable records; a conflicting destination is never replaced.
        """
        destination = Path(root) / 'AppData' / CHANNEL
        if destination.resolve() == self.shared.resolve():
            return destination
        self.require_admin()
        if self.store.sandbox_required and not destination.resolve().is_relative_to(self.store.local_dir.resolve()):
            raise ValueError('Development/Beta identity storage must remain inside its isolated profile.')
        if not Path(root).is_dir():
            raise ValueError('Choose an existing shared-storage folder before remapping profiles. Research files will not be moved.')
        with self.lock, update_lock(destination / 'Users'):
            current = read_json(destination / 'Users' / 'profiles.json', None)
            if current and current != self.registry:
                raise ValueError('The destination has different team profiles. Reconnect the original mapping or resolve the profile revision with the Admin.')
            for folder in ('Activity/Events', 'Activity/Sessions', 'Meetings', 'Configuration/Backups'):
                for source in (self.shared / folder).glob('*.json'):
                    row = read_json(source, {})
                    target = destination / folder / source.name
                    if target.exists() and read_json(target, {}) != row:
                        raise ValueError('The destination contains a conflicting record. The original mapping and both records were preserved.')
                    if not target.exists():
                        write_json(target, row)
            if not current:
                write_json(destination / 'Users' / 'profiles.json', self.registry)
        return destination

    @property
    def profile_path(self):
        return self.shared / 'Users' / 'profiles.json'

    def check_conflicts(self):
        folder = self.profile_path.parent
        if folder.exists() and any(p.name not in ('profiles.json', 'profile.lock') and p.suffix == '.json'
                                   for p in folder.iterdir() if p.is_file()):
            raise ValueError('OneDrive profile conflict detected. Ask the Admin to compare the conflict copy with the configuration backups before making changes.')

    def load_registry(self):
        try:
            self.check_conflicts()
            value = read_json(self.profile_path, None)
            if value:
                if value.get('channel') != CHANNEL:
                    raise ValueError('These profiles belong to another release channel.')
                write_json(self.cache, value)
                return value
            cached = read_json(self.cache, None)
            if cached:
                self.warning = 'Shared profiles unavailable. Using the last verified profiles; activity will queue locally.'
                self.offline = True
                return cached
            # An existing disconnected project must never be silently re-created.
            root = self.shared.parents[1]
            if self.store.local.get('project_locations', {}).get('enabled') and not root.is_dir():
                raise ValueError('Shared storage is unavailable. Reconnect OneDrive to load profiles for the first time.')
            value = dict(revision=1, channel=CHANNEL, writer_device=self.install_id, users=[
                dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL, 'capstone-hub:team:' + name)),
                     display_name=name, role='admin' if n == 0 else 'member', active=True, pin=None)
                for n, name in enumerate(NAMES)])
            with update_lock(self.profile_path.parent):
                if self.profile_path.exists():
                    return self.load_registry()
                write_json(self.profile_path, value)
            write_json(self.cache, value)
            return value
        except OSError:
            cached = read_json(self.cache, None)
            if not cached:
                raise ValueError('Profiles are unavailable. Reconnect shared storage and try again.') from None
            self.offline = True
            self.warning = 'OneDrive unavailable. Profiles are cached and activity is queued locally.'
            return cached

    def users(self):
        return [dict(p, pin=None) for p in self.registry['users'] if p['active']]

    def find(self, identity):
        return next((p for p in self.registry['users'] if p['id'] == identity), None)

    def require_admin(self):
        if not self.profile or self.profile['role'] != 'admin' or not self.admin_unlocked:
            raise ValueError('Unlock the Admin profile with its PIN to use this function.')

    @contextmanager
    def edit(self, admin=True):
        if admin:
            self.require_admin()
        if self.registry['writer_device'] != self.install_id:
            raise ValueError('Profile changes are made on the designated profile writer. Ask the Admin to make this change there.')
        self.check_conflicts()
        with self.lock, update_lock(self.profile_path.parent):
            current = read_json(self.profile_path, None)
            if not current or current['revision'] != self.registry['revision']:
                raise ValueError('Profiles changed on another device. Reload profiles before retrying; your change was not saved.')
            value = copy.deepcopy(current)
            yield value
            value['revision'] += 1
            write_json(self.shared / 'Configuration' / 'Backups' / (str(current['revision']) + '-' + uuid.uuid4().hex + '.json'), current)
            write_json(self.profile_path, value)
            write_json(self.cache, value)
            self.registry = value

    def setup_admin(self, pin):
        validate_pin(pin, required=True)
        if any(p['role'] == 'admin' and p['pin'] for p in self.registry['users']):
            raise ValueError('Admin is already configured. Use its PIN or recovery code.')
        recovery = secrets.token_urlsafe(24)
        with self.edit(admin=False) as value:
            admin = next(p for p in value['users'] if p['role'] == 'admin')
            admin['pin'] = password_hash(pin)
            value['recovery'] = password_hash(recovery)
        return recovery

    def recover_admin(self, code, pin):
        validate_pin(pin, required=True)
        if not matches(code, self.registry.get('recovery')) or not self.registry.get('recovery'):
            raise ValueError('Recovery code was not accepted.')
        recovery = secrets.token_urlsafe(24)
        with self.edit(admin=False) as value:
            next(p for p in value['users'] if p['role'] == 'admin')['pin'] = password_hash(pin)
            value['recovery'] = password_hash(recovery)
        return recovery

    def sign_in(self, identity, pin='', remember=True, automatic=False):
        self.registry = self.load_registry()
        profile = self.find(identity)
        if not profile or not profile['active']:
            raise ValueError('This profile is inactive. Select an active team member.')
        if profile['role'] == 'admin' and not profile['pin']:
            raise ValueError('Set an Admin PIN on the designated writer before signing in as Admin.')
        # Persist rate limiting across restarts. It is only a casual-access control.
        import time
        attempts = read_json(self.base / 'attempts.json', {})
        attempt = attempts.get(identity, {})
        if attempt.get('until', 0) > time.time():
            raise ValueError('Too many PIN attempts. Wait one minute and try again.')
        if not matches(pin, profile['pin']):
            count = attempt.get('count', 0) + 1
            attempts[identity] = dict(count=count, until=time.time() + 60 if count >= 5 else 0)
            write_json(self.base / 'attempts.json', attempts)
            raise ValueError('PIN was not accepted.')
        attempts.pop(identity, None)
        write_json(self.base / 'attempts.json', attempts)
        self.profile = {k: v for k, v in profile.items() if k != 'pin'}
        self.admin_unlocked = profile['role'] == 'admin' and bool(profile['pin'])
        self.session = {'id': str(uuid.uuid4())}
        self.store.local['selected_user'] = identity if remember else ''
        self.store.local['automatic_user'] = identity if automatic and remember and not profile['pin'] and profile['role'] == 'member' else ''
        self.store.save_local()
        if not self.launch_recorded:
            self.event('APP_LAUNCH')
            self.launch_recorded = True
        self.event('LOGIN')
        result_path = self.store.local_dir / 'update-result.local.json'
        result = read_json(result_path, {})
        if result.get('status') == 'version_verified' and not result.get('activity_recorded'):
            self.event('APP_UPDATED', entity_name=result['verified_version'])
            result['activity_recorded'] = True
            write_json(result_path, result)
        return self.profile

    def restore(self):
        identity = self.store.local.get('automatic_user')
        user = self.find(identity)
        if user and user['active'] and user['role'] == 'member' and not user['pin']:
            return self.sign_in(identity, automatic=True)
        return None

    def sign_out(self):
        if self.participation:
            self.participation.persist(close=True)
        self.event('LOGOUT')
        self.flush()
        self.profile = self.session = None
        self.admin_unlocked = False
        self.store.local['automatic_user'] = ''
        self.store.save_local()

    def change_pin(self, old, new):
        if not self.profile:
            raise ValueError('Select a user first.')
        person = self.find(self.profile['id'])
        validate_pin(new, person['role'] == 'admin')
        if not matches(old, person['pin']):
            raise ValueError('Current PIN was not accepted.')
        with self.edit(admin=False) as value:
            next(p for p in value['users'] if p['id'] == person['id'])['pin'] = password_hash(new) if new else None
        self.event('PIN_CHANGED')

    def manage_user(self, identity=None, name=None, active=None, reset_pin=False):
        with self.edit() as value:
            if identity is None:
                person = dict(id=str(uuid.uuid4()), display_name='', role='member', active=True, pin=None)
                value['users'].append(person)
            else:
                person = next(p for p in value['users'] if p['id'] == identity)
            if name is not None:
                if not name.strip() or len(name.strip()) > 100:
                    raise ValueError('Enter a display name of up to 100 characters.')
                person['display_name'] = name.strip()
            if person['role'] == 'admin' and (active is False or reset_pin):
                raise ValueError('Use Admin PIN change or recovery; the Admin profile must remain active.')
            if active is not None:
                person['active'] = bool(active)
            if reset_pin:
                person['pin'] = None
        self.event('PROFILE_CHANGED', 'user', person['id'])

    def event(self, kind, entity_type='', entity_id='', entity_name='', details=None, status='completed', owner=None):
        if not self.profile:
            return
        identity = str(uuid.uuid4())
        if owner is not None and self.find(owner) is None:
            return  # Never invent attribution for an imported processing session.
        row = dict(id=identity, client_event_id=identity, user_id=owner or self.profile['id'], device_id=self.install_id,
                   install_id=self.install_id, created_at=timestamp(), event_type=kind, category=kind.split('_')[0],
                   description=kind.replace('_', ' ').title(), entity_type=entity_type, entity_id=entity_id,
                   entity_name=entity_name[:180], details=details or {}, app_version=DISPLAY_VERSION,
                   channel=CHANNEL, status=status)
        write_json(self.base / 'outbox' / 'Events' / (identity + '.json'), row)
        self.executor.submit(self.flush)

    def publish_session(self, row):
        row = dict(row, channel=CHANNEL, device_id=self.install_id, app_version=DISPLAY_VERSION)
        # Each snapshot has a unique transport ID; session ID remains the dedup key.
        write_json(self.base / 'outbox' / 'Sessions' / (row['id'] + '-' + uuid.uuid4().hex + '.json'), row)

    def flush(self):
        with self.lock:
            shared = self.shared
            if not shared.parent.parent.is_dir():
                self.warning = 'OneDrive unavailable. Activity is saved locally and will retry automatically.'
                self.offline = True
                return False
            try:
                self.check_conflicts()
                for kind in ('Events', 'Sessions'):
                    for source in (self.base / 'outbox' / kind).glob('*.json'):
                        row = read_json(source, {})
                        target = shared / 'Activity' / kind / source.name
                        if target.exists() and read_json(target, {}) != row:
                            raise ValueError('Activity synchronization conflict detected. Local events were preserved.')
                        if not target.exists():
                            write_json(target, row)
                        source.unlink()
                self.offline = False
                self.warning = ''
                return True
            except (OSError, ValueError):
                self.warning = 'Shared activity sync is delayed or conflicting. Local events are preserved; ask the Admin to check OneDrive.'
                self.offline = True
                return False

    def rows(self, kind):
        unique = {}
        conflicts = set()
        for folder in (self.shared / 'Activity' / kind, self.base / 'outbox' / kind):
            for path in sorted(folder.glob('*.json')):
                try:
                    row = read_json(path, {})
                    if row.get('channel') != CHANNEL:
                        continue
                    if kind == 'Events' and row['id'] in unique and unique[row['id']] != row:
                        conflicts.add(row['id'])
                        self.warning = 'Conflicting activity copies were excluded from totals. Ask the Admin to compare the preserved records.'
                        continue
                    if kind == 'Sessions':
                        previous = unique.get(row['id'])
                        if previous and (previous.get('ended_at') or previous['last_active_at']) > (row.get('ended_at') or row['last_active_at']):
                            continue
                    unique[row['id']] = row
                except (OSError, ValueError, KeyError):
                    self.warning = 'An activity record is unreadable. It was preserved for Admin review.'
        rows = [row for identity, row in unique.items() if identity not in conflicts]
        if not self.admin_unlocked:
            rows = [r for r in rows if self.profile and r['user_id'] == self.profile['id']]
        return rows

    def roster(self):
        return self.users() if self.admin_unlocked else [self.profile]

    def refresh(self):
        self.registry = self.load_registry()
        current = self.find(self.profile['id']) if self.profile else None
        if not current or not current['active']:
            raise ValueError('This profile was deactivated. Sign in with an active profile.')
        self.profile.update(display_name=current['display_name'], role=current['role'])

    def close(self):
        if self.profile:
            self.sign_out()
        self.executor.shutdown(wait=True, cancel_futures=True)
