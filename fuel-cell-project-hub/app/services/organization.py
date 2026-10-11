"""Four-category project records, immutable proposals and single-writer snapshots.

OneDrive is transport, not a distributed lock. Only the enrolled device publishes;
all participants submit immutable proposals against a record revision. No live
database is opened under the project root. Existing catalogs are never rewritten.
"""
import copy
import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import date
from pathlib import Path
from app import __version__
from app.edition import CHANNEL
from app.services.storage import read_json, write_json, timestamp
from app.services.project_storage import normalized_relative, redirects, PLACEHOLDER_FLAGS
from app.services.updates import update_lock

SCHEMA = 1
CATEGORIES = {
    'Experimental': '01_Experimental',
    'Research': '02_Research',
    'Meetings & Goals': '03_Meetings_and_Goals',
    'Design & Prototyping': '04_Design_and_Prototyping',
}
FOLDERS = (
    '01_Experimental/Experiments', '01_Experimental/Samples', '01_Experimental/Procedures',
    '02_Research/Published_Articles', '02_Research/ASTM_Standards_and_References',
    '02_Research/Previous_Research', '02_Research/Literature_Reviews_and_Comparisons',
    '03_Meetings_and_Goals/Meetings', '03_Meetings_and_Goals/Goals_and_Milestones',
    '04_Design_and_Prototyping/CAD_and_Drawings', '04_Design_and_Prototyping/Manufacturing_and_Laser',
    '04_Design_and_Prototyping/3D_Printing', '04_Design_and_Prototyping/Parameters_and_Calculations',
    '04_Design_and_Prototyping/Prototypes_and_Feedback',
)
KINDS = {'experiment': ('E', 'Experimental'), 'sample': ('S', 'Experimental'),
         'procedure': ('P', 'Experimental'), 'research': ('R', 'Research'),
         'design': ('D', 'Design & Prototyping'), 'meeting': ('MTG', 'Meetings & Goals'),
         'task': ('T', 'Meetings & Goals'), 'file': ('F', 'Experimental'),
         'role': ('ROLE', 'Meetings & Goals')}
ROLES = ('Project Lead & Systems Integration', 'Data Science & Analysis Lead',
         'Experimental & Testing Lead', 'Design & Manufacturing Lead', 'Research & Documentation Lead')
IMAGE_STATES = ('raw', 'poremap', 'overlay', 'outline', 'derived', 'reference')
LIMIT = '2D optical imaging measures apparent surface porosity, not 3D bulk porosity.'
MEETING_TEMPLATES = {
    'agenda': 'Prior action review:\n\nTopics / goal / estimated minutes:\n\nSupporting links:\n\nQuestions requiring a decision:\n',
    'minutes': 'Attendance:\n\nTopic notes and evidence:\n\nDECISION / rationale:\n\nACTION / one owner / due date / deliverable:\n\nIssues and blockers:\n\nParking lot:\n\nNext meeting:\n',
    'summary': 'Overview (3–6 sentences):\n\nDecisions:\n\nCompleted work:\n\nActions and deadlines:\n\nBlockers and next priorities:\n\nSource minutes / recording links:\n',
}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')


def token(value):
    value = re.sub(r'[^\w-]+', '-', str(value), flags=re.UNICODE).strip('-_ .')[:70]
    return value or 'Record'


def filename(created, kind, ids, description, revision=1, sequence=None, extension='.json'):
    day = date.fromisoformat(str(created)[:10]).isoformat()
    if not re.fullmatch(r'\.[a-zA-Z0-9]{1,12}', extension):
        raise ValueError('Choose a supported file extension.')
    code = {'experiment': 'EXP', 'sample': 'SAMPLE', 'procedure': 'PROC', 'research': 'REF',
            'design': 'DES', 'meeting': 'MTG', 'task': 'TASK', 'file': 'IMG'}.get(kind, 'DOC')
    if kind == 'file' and extension.lower() not in ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'):
        code = 'DES' if extension.lower() in ('.sldprt', '.sldasm', '.step', '.stp', '.stl', '.3mf', '.dxf') else 'DATA' if extension.lower() in ('.csv', '.xlsx', '.json', '.txt') else 'DOC'
    identity = '_'.join(token(i) for i in ids if i)
    suffix = f'{int(sequence):03d}' if sequence is not None else f'v{int(revision):02d}'
    return '_'.join(p for p in (day, code, identity, token(description), suffix) if p) + extension.lower()


def comparability(fields):
    if fields.get('dimensionality') != '2D' or fields.get('metric') not in ('apparent surface porosity', '2D pore size', '2D fiber width'):
        return False, 'Excluded: bulk/3D or unspecified metric is not directly comparable. ' + LIMIT
    required = ('definition', 'method', 'sample_basis', 'units', 'comparison_reason')
    if not all(str(fields.get(k, '')).strip() for k in required):
        return False, 'Comparison requires definition, method, sample basis, units and a reviewer rationale.'
    return bool(fields.get('reviewer_id')), 'Reviewer must verify compatible measurement definitions and conditions. ' + LIMIT


class Organization:
    def __init__(self, store, root=None):
        self.store = store
        self.accounts = store.accounts
        locations = store.local.get('project_locations', {})
        original = Path(root or locations.get('shared_storage') or store.local_dir / 'research-sandbox/shared')
        if original.exists() and redirects(original.lstat()):
            raise ValueError('Choose a direct project root, not a filesystem link.')
        self.root = original.resolve()
        if store.sandbox_required and not self.root.is_relative_to(store.local_dir.resolve()):
            raise ValueError('Development/Beta organization must use the isolated profile sandbox.')
        self.control = self.root / '_System' / 'Organization'
        self.local = store.local_dir / 'organization' / hashlib.sha256(str(self.root).encode()).hexdigest()[:16]
        self.local.mkdir(parents=True, exist_ok=True)
        self.state = read_json(self.local / 'last-good.json', self.empty())
        if self.state.get('channel') != CHANNEL or self.state.get('schema') != SCHEMA:
            raise ValueError('Cached organization belongs to another edition or schema.')
        self.status = 'Not initialized · Admin can preview setup'
        self.refresh()
        store.organization_service = self

    @staticmethod
    def empty():
        return {'schema': SCHEMA, 'channel': CHANNEL, 'revision': 0, 'records': {},
                'counters': {}, 'audit': [], 'requests': {}}

    @property
    def actor(self):
        profile = self.accounts.profile
        if not profile or not profile.get('active', True):
            raise ValueError('Select an active local user before changing project records.')
        return {'user_id': profile['id'], 'display_name': profile['display_name']}

    @property
    def authority(self):
        identity = read_json(self.control / 'identity.json', {})
        return (self.accounts.admin_unlocked and identity.get('writer_device') == self.accounts.install_id
                and identity.get('channel') == CHANNEL)

    def safe(self, relative):
        relative = normalized_relative(relative)
        path = self.root / relative
        if not path.resolve().is_relative_to(self.root):
            raise ValueError('Project files must remain within the configured root.')
        for candidate in (self.root, *path.parents, path):
            if candidate == self.root.parent:
                break
            if candidate.is_relative_to(self.root) and candidate.exists() and redirects(candidate.lstat()):
                raise ValueError('Project destinations cannot traverse filesystem links.')
        return path

    def preview(self):
        return {'create_if_missing': [p for p in (*FOLDERS, '_System/Organization') if not self.safe(p).exists()],
                'preserved_existing': sorted(p.name for p in self.root.iterdir()) if self.root.is_dir() else [],
                'moves': [], 'deletions': [], 'legacy_catalog': 'Existing .project_hub and catalog files remain unchanged.'}

    def initialize(self):
        self.accounts.require_admin()
        if not self.root.is_dir():
            raise ValueError('Configure an existing synchronized project root (Beta: isolated sandbox).')
        self.safe('_System/Organization/identity.json')
        backup = self.local / 'setup-backups' / uuid.uuid4().hex
        backup.mkdir(parents=True)
        write_json(backup / 'team-profiles.json', self.accounts.registry)
        for source in self.control.rglob('*.json') if self.control.exists() else []:
            if not redirects(source.lstat()):
                target = backup / 'organization' / source.relative_to(self.control)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        self.control.mkdir(parents=True, exist_ok=True)
        identity = self.control / 'identity.json'
        if not identity.exists():
            with identity.open('x', encoding='utf-8') as stream:
                json.dump({'schema': SCHEMA, 'channel': CHANNEL, 'writer_device': self.accounts.install_id,
                           'project_uuid': str(uuid.uuid4()), 'created_at': timestamp()}, stream)
        if not self.authority:
            raise ValueError('Only the enrolled Admin device may initialize or publish this project.')
        for folder in FOLDERS:
            self.safe(folder).mkdir(parents=True, exist_ok=True)
        self.refresh()
        if not self.state['revision']:
            state = self.empty()
            for index, name in enumerate(ROLES, 1):
                key = str(uuid.uuid5(uuid.NAMESPACE_URL, 'capstone-organization-role:' + name))
                state['records'][key] = {'uuid': key, 'id': f'ROLE{index}', 'kind': 'role',
                    'category': 'Meetings & Goals', 'title': name, 'fields': {'member_id': '', 'backup_id': ''},
                    'revision': 1, 'created_at': timestamp(), 'created_by_user_id': self.actor['user_id'],
                    'created_by_display_name': self.actor['display_name'], 'schema_version': SCHEMA}
            self._publish(state)
        return self.preview()

    def refresh(self):
        try:
            self.safe('_System/Organization/published.json')
            if not self.root.is_dir():
                raise ValueError('Project folder unavailable')
            identity = read_json(self.control / 'identity.json', {})
            if identity and identity.get('channel') != CHANNEL:
                raise ValueError('Project belongs to another edition')
            for pattern, expected in (('published*.json', 'published.json'), ('identity*.json', 'identity.json')):
                if any(p.name != expected for p in self.control.glob(pattern)):
                    raise ValueError('OneDrive conflict copies require Admin review')
            pointer = read_json(self.control / 'published.json', {})
            if not pointer:
                self.status = 'Not initialized · Admin can preview setup'; return False
            state = self._read_snapshot(pointer)
            if state['revision'] < self.state['revision']:
                raise ValueError('Older snapshot received; keeping last-known-good data')
            write_json(self.local / 'last-good.json', state)
            self.state = state
            # Uploaded binary caches are temporary pending changes, not a second
            # authoritative research store. Keep conflicting/unaccepted uploads.
            for proposal in (self.control / 'Incoming_Changes').glob('*.json'):
                request = read_json(proposal, {})
                if state['requests'].get(request.get('request_uuid'), {}).get('status') == 'accepted' and request.get('device_id') == self.accounts.install_id:
                    upload = request.get('fields', {}).get('upload_uuid')
                    if upload:
                        cache = self.local / 'uploads' / str(uuid.UUID(upload))
                        cache.unlink(missing_ok=True)
            pending = len(list((self.local / 'outbox').glob('*.json')))
            shared_pending = sum(p.stem not in state['requests'] for p in (self.control / 'Incoming_Changes').glob('*.json'))
            conflicts = sum(r['status'] == 'conflict' for r in state['requests'].values())
            self.status = f"Index v{state['revision']} · published {state['published_at'][:19]} UTC · {pending} local / {shared_pending} shared pending · {conflicts} conflicts · possibly stale until OneDrive sync completes"
            return True
        except (OSError, ValueError, KeyError, TypeError):
            self.status = f"Offline/possibly stale · last-known-good v{self.state['revision']} · missing, incomplete or conflicting shared index"
            return False

    def _read_snapshot(self, pointer):
        path = self.safe('_System/Organization/' + normalized_relative(pointer['snapshot']))
        if digest(path) != pointer['sha256']:
            raise ValueError('Incomplete snapshot checksum')
        state = read_json(path, {})
        if state.get('schema') != SCHEMA or state.get('channel') != CHANNEL or state.get('revision') != pointer['revision']:
            raise ValueError('Unsupported snapshot schema, channel or revision')
        if not isinstance(state.get('records'), dict) or not isinstance(state.get('requests'), dict):
            raise ValueError('Invalid index contents')
        return state

    def _publish(self, state):
        if not self.authority:
            raise ValueError('Only the enrolled Admin writer may publish the master index.')
        prior = read_json(self.control / 'published.json', {})
        state['revision'] = self.state['revision'] + 1
        state['published_at'] = timestamp()
        name = f"Snapshots/{state['revision']:08d}-{uuid.uuid4().hex}.json"
        snapshot = self.safe('_System/Organization/' + name)
        write_json(snapshot, state)
        pointer = {'schema': SCHEMA, 'revision': state['revision'], 'snapshot': name, 'sha256': digest(snapshot)}
        self._read_snapshot(pointer)
        if prior:
            write_json(self.control / 'Backups' / (uuid.uuid4().hex + '.json'), prior)
        write_json(self.control / 'published.json', pointer)
        self.refresh()

    def rows(self, category=None, kind=None, query=''):
        rows = self.state['records'].values()
        def matches(row):
            text = json.dumps(row, ensure_ascii=False)
            references = re.findall(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', json.dumps(row.get('fields', {})))
            for key in references:
                linked = self.state['records'].get(key, {})
                text += ' ' + linked.get('id', '') + ' ' + linked.get('title', '') + ' ' + json.dumps(linked.get('aliases', []))
            return query.casefold() in text.casefold()
        return sorted((copy.deepcopy(r) for r in rows if (not category or r['category'] == category)
            and (not kind or r['kind'] == kind) and (not query or matches(r))),
            key=lambda r: (r['kind'], r['id']))

    def submit(self, kind, title, fields=None, key=None, reason='', legacy=None):
        if kind not in KINDS:
            raise ValueError('Unsupported project record type.')
        fields = copy.deepcopy(fields or {})
        if not title.strip():
            raise ValueError('Enter a short description.')
        existing = self.state['records'].get(key) if key else None
        if key and not existing:
            raise ValueError('Refresh before editing a record unavailable in this snapshot.')
        if existing and existing['kind'] != kind:
            raise ValueError('A permanent record cannot change type.')
        if kind == 'role' and (not self.accounts.admin_unlocked or not existing):
            raise ValueError('Admin may assign the five existing coordination roles; they do not grant permissions.')
        if existing and not reason.strip():
            raise ValueError('Describe the reason for the metadata change.')
        request = {'request_uuid': str(uuid.uuid4()), 'record_uuid': key or str(uuid.uuid4()),
            'kind': kind, 'title': title.strip(), 'fields': fields, 'reason': reason,
            'base_revision': existing['revision'] if existing else 0, 'actor': self.actor,
            'device_id': self.accounts.install_id, 'created_at': timestamp(), 'schema': SCHEMA,
            'channel': CHANNEL, 'legacy': legacy}
        write_json(self.local / 'outbox' / (request['request_uuid'] + '.json'), request)
        self.accounts.event('ORGANIZATION_CHANGE_REQUESTED', kind, request['record_uuid'], title,
                            {'reason': reason, 'prior': existing, 'new_fields': fields}, status='pending')
        self.flush()
        return request['record_uuid']

    def flush(self):
        if not self.root.is_dir() or not (self.control / 'identity.json').exists():
            self.status = 'Pending offline changes · Admin setup or project synchronization required'; return
        if read_json(self.control / 'identity.json', {}).get('channel') != CHANNEL:
            raise ValueError('Cannot submit Beta/Development changes into another release channel.')
        destination = self.safe('_System/Organization/Incoming_Changes')
        destination.mkdir(parents=True, exist_ok=True)
        for source in (self.local / 'outbox').glob('*.json'):
            request = read_json(source, {})
            upload = request.get('fields', {}).get('upload_uuid')
            if upload:
                upload = str(uuid.UUID(upload))
                artifact = self.local / 'uploads' / upload
                if artifact.exists():
                    self._copy_once(artifact, self.safe('_System/Organization/Incoming_Files/' + upload))
            target = destination / source.name
            if target.exists() and read_json(target, {}) != request:
                raise ValueError('Conflicting change request preserved for Admin review.')
            if not target.exists():
                write_json(target, request)
            source.unlink()
        self.refresh()

    @staticmethod
    def _copy_once(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if digest(source) != digest(target):
                raise ValueError('Destination exists with different contents. No file was overwritten.')
            return
        temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.part')
        try:
            with source.open('rb') as incoming, temporary.open('xb') as output:
                shutil.copyfileobj(incoming, output)
            if digest(temporary) != digest(source):
                raise ValueError('Source changed during copy; retry after capture finishes.')
            # Windows rename is atomic and refuses an existing destination;
            # avoid hard links, which OneDrive and restricted runtimes may reject.
            if os.name == 'nt': os.rename(temporary, target)
            else: os.link(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def upload(self, source, title, fields):
        source = Path(source)
        if not source.is_file() or redirects(source.lstat()) or getattr(source.stat(), 'st_file_attributes', 0) & PLACEHOLDER_FLAGS:
            raise ValueError('Select a resident file; download Files On-Demand content explicitly first.')
        upload = str(uuid.uuid4())
        target = self.local / 'uploads' / upload
        self._copy_once(source, target)
        values = dict(fields, upload_uuid=upload, checksum=digest(target), file_size=target.stat().st_size,
                      original_filename=source.name, extension=source.suffix.lower(),
                      source_modified_at=source.stat().st_mtime, source_created_at=source.stat().st_ctime)
        return self.submit('file', title, values)

    def _validate_fields(self, kind, fields, records):
        people = {r['id'] for r in self.accounts.registry['users'] if r.get('active', True)}
        for key in ('owner_id', 'member_id', 'backup_id', 'facilitator_id', 'note_taker_id', 'reviewer_id', 'operator_id', 'summary_reviewed_by_id'):
            if fields.get(key) and fields[key] not in people:
                raise ValueError('Choose an active team member for ownership.')
        for key in ('attendees', 'supporting_members'):
            if fields.get(key) and (not isinstance(fields[key], list) or set(fields[key]) - people):
                raise ValueError('Choose active team members for attendance/support.')
        if kind == 'task' and (not fields.get('owner_id') or not fields.get('due_date') or not fields.get('acceptance')):
            raise ValueError('Tasks require one owner, due date and acceptance criterion.')
        if fields.get('due_date'):
            date.fromisoformat(fields['due_date'])
        for key, expected in (('sample_uuids', 'sample'), ('experiment_uuid', 'experiment'),
                              ('procedure_uuid', 'procedure'), ('meeting_uuid', 'meeting'), ('design_uuid', 'design'),
                              ('research_uuid', 'research'), ('parent_file_uuid', 'file')):
            values = fields.get(key, []) if key.endswith('uuids') else [fields.get(key)]
            if not isinstance(values, list):
                raise ValueError('Sample references must be a list of permanent record UUIDs.')
            for value in filter(None, values):
                if value not in records or records[value]['kind'] != expected:
                    raise ValueError('A linked record is unavailable. Publish its creation first.')
        for key in ('export_file_uuids', 'linked_file_uuids'):
            if fields.get(key) and (not isinstance(fields[key], list) or any(records.get(value, {}).get('kind') != 'file' for value in fields[key])):
                raise ValueError('Choose published file UUIDs for fabrication exports and supporting files.')
        if fields.get('cad_source_uuid') and records.get(fields['cad_source_uuid'], {}).get('kind') != 'file':
            raise ValueError('Choose a published editable CAD source file.')
        if fields.get('procedure_uuid'):
            procedure = records[fields['procedure_uuid']]
            revision = int(fields.get('procedure_revision', 0))
            if not 1 <= revision <= procedure['revision']:
                raise ValueError('Choose the exact published procedure revision.')
        if kind == 'file':
            state = fields.get('file_state', 'reference')
            if sum(bool(fields.get(k)) for k in ('experiment_uuid', 'meeting_uuid', 'design_uuid', 'research_uuid')) > 1:
                raise ValueError('Choose one primary experiment, meeting, design or research folder; use related file links for cross-references.')
            if state not in IMAGE_STATES:
                raise ValueError('Choose raw, poremap, overlay, outline, derived or reference.')
            if state in ('poremap', 'overlay', 'outline', 'derived'):
                parent = records.get(fields.get('parent_file_uuid'), {})
                if parent.get('fields', {}).get('file_state') != 'raw' or not fields.get('processing_run_id'):
                    raise ValueError('Derived files require an exact raw parent and processing-run ID.')
                pf = parent['fields']
                if fields.get('experiment_uuid') != pf.get('experiment_uuid') or fields.get('sample_uuids', []) != pf.get('sample_uuids', []):
                    raise ValueError('Derived image experiment/sample links must match its raw parent.')
        if kind == 'meeting' and fields.get('stage', 'agenda') not in ('agenda', 'minutes', 'summary'):
            raise ValueError('Choose agenda, minutes or summary stage.')
        if kind == 'meeting':
            for key in ('recording_path', 'transcript_path'):
                if fields.get(key): self.safe(normalized_relative(fields[key]))
            if fields.get('summary_approved') == 'Yes' and not fields.get('summary_reviewed_by_id'):
                raise ValueError('Record the meeting lead who reviewed the summary.')
        if kind == 'task' and fields.get('status', 'planned') not in ('planned', 'active', 'blocked', 'done'):
            raise ValueError('Choose a supported task status.')

    def consume(self):
        if not self.authority:
            raise ValueError('Only the enrolled Admin writer consumes requests or rebuilds this master index.')
        self.safe('_System/Organization')
        with update_lock(self.control):
            if not self.refresh():
                raise ValueError('Restore a valid shared snapshot before publishing.')
            state = copy.deepcopy(self.state)
            changed = False
            proposals = [(p, read_json(p, {})) for p in (self.control / 'Incoming_Changes').glob('*.json')]
            conflicts = set()
            grouped = {}
            for _, request in proposals:
                identity = request.get('request_uuid')
                if identity in grouped and encoded(grouped[identity]) != encoded(request): conflicts.add(identity)
                grouped[identity] = request
            for source in sorted((self.control / 'Incoming_Changes').glob('*.json'), key=lambda p: p.name):
                request = read_json(source, {})
                request_id = request.get('request_uuid', '')
                if request_id in conflicts:
                    if request_id not in state['requests']:
                        state['requests'][request_id] = {'status': 'conflict', 'at': timestamp(), 'reason': 'Conflicting immutable request copies require Admin comparison.'}
                        changed = True
                    self.status = 'Conflicting request copies require Admin review'
                    continue
                if request_id in state['requests']:
                    continue
                # Conflicted copies are never silently selected by filename order.
                if source.stem != request_id:
                    self.status = 'Conflicting request copy requires Admin review'; continue
                try:
                    self._apply(state, request)
                    state['requests'][request_id] = {'status': 'accepted', 'at': timestamp()}
                except (ValueError, OSError, KeyError, TypeError) as exc:
                    state['requests'][request_id] = {'status': 'conflict', 'at': timestamp(),
                        'reason': str(exc) if isinstance(exc, ValueError) else 'Incomplete request/file. Preserve and resubmit after synchronization.'}
                changed = True
            if changed:
                self._publish(state)
            return copy.deepcopy(state['requests'])

    def _apply(self, state, request):
        uuid.UUID(request['request_uuid']); uuid.UUID(request['record_uuid'])
        if request['schema'] != SCHEMA or request['channel'] != CHANNEL:
            raise ValueError('Request schema/channel mismatch.')
        people = {p['id']: p for p in self.accounts.registry['users'] if p.get('active', True)}
        actor = request['actor']
        if actor['user_id'] not in people:
            raise ValueError('Inactive or unknown contributor.')
        key, kind, fields = request['record_uuid'], request['kind'], copy.deepcopy(request['fields'])
        if kind not in KINDS:
            raise ValueError('Unsupported record kind.')
        old = state['records'].get(key)
        if request['base_revision'] != (old['revision'] if old else 0):
            raise ValueError('Stale edit conflicts with a published revision. Refresh, compare and resubmit.')
        if old and (old['kind'] != kind or not request.get('reason')):
            raise ValueError('Changing record type or editing without a reason is not permitted.')
        if kind == 'role' and (not old or people[actor['user_id']]['role'] != 'admin'):
            raise ValueError('Only Admin may assign the five coordination roles.')
        if old and kind == 'file' and old['fields'].get('file_state') == 'raw':
            for field in ('upload_uuid', 'checksum', 'file_size', 'file_state', 'created_at'):
                if fields.get(field) != old['fields'].get(field):
                    raise ValueError('Raw capture content and identity are immutable; register a new acquisition.')
        if old and kind == 'file' and any(fields.get(k) != old['fields'].get(k) for k in ('upload_uuid', 'checksum', 'extension', 'file_size')):
            raise ValueError('Register a new file for changed binary contents; metadata edits preserve the original.')
        self._validate_fields(kind, fields, state['records'])
        if kind == 'meeting' and fields.get('summary_approved') == 'Yes':
            if fields.get('summary_reviewed_by_id') != actor['user_id'] or (fields.get('facilitator_id') != actor['user_id'] and people[actor['user_id']]['role'] != 'admin'):
                raise ValueError('Only the recorded meeting lead or Admin may approve a summary, using their own selected profile.')
        prefix, category = KINDS[kind]
        if old:
            public_id, created = old['id'], old['created_at']
            if 'created_at' in fields: fields['created_at'] = created
        else:
            state['counters'][prefix] = state['counters'].get(prefix, 0) + 1
            public_id = f"{prefix}{state['counters'][prefix]:04d}"
            created = fields.get('created_at') or request['created_at']
        date.fromisoformat(created[:10])
        if kind == 'file' and fields.get('file_state') == 'raw':
            fields.setdefault('sequence', int(public_id[1:]))
        if kind == 'research':
            fields['comparable'], fields['comparability_warning'] = comparability(fields)
        if kind == 'meeting' and not old:
            fields = {**MEETING_TEMPLATES, **fields, 'carried_actions': [r['uuid'] for r in state['records'].values()
                if r['kind'] == 'task' and r['fields'].get('status') != 'done']}
        legacy = request.get('legacy') or (old or {}).get('legacy')
        if legacy and people[actor['user_id']]['role'] != 'admin':
            raise ValueError('Only Admin may register a legacy inventory.')
        record = {'uuid': key, 'id': public_id, 'kind': kind, 'category': category,
            'title': old['title'] if kind == 'role' and old else request['title'], 'fields': fields,
            'revision': (old['revision'] + 1) if old else 1, 'created_at': created,
            'registered_at': old['registered_at'] if old and 'registered_at' in old else request['created_at'],
            'updated_at': request['created_at'], 'schema_version': SCHEMA,
            'created_by_user_id': old['created_by_user_id'] if old else (None if legacy else actor['user_id']),
            'created_by_display_name': old['created_by_display_name'] if old else ('Unknown' if legacy else actor['display_name']),
            'uploaded_by_user_id': old.get('uploaded_by_user_id') if old else actor['user_id'],
            'last_modified_by_user_id': actor['user_id'], 'legacy': old.get('legacy') if old else legacy,
            'aliases': fields.get('aliases', [])}
        record['file_uuid'] = key
        record['document_type'] = fields.get('document_type', kind)
        record['file_state'] = fields.get('file_state', 'reference')
        if kind == 'file':
            linked = next((state['records'][fields[k]] for k in ('meeting_uuid', 'design_uuid', 'research_uuid') if fields.get(k)), None)
            if linked: record['category'] = linked['category']
        if legacy:
            record['relative_path'] = normalized_relative(legacy['relative_path'])
            record['category'] = legacy.get('category', category)
            self.safe(record['relative_path'])
        elif old and kind == 'file':
            record['relative_path'] = old['relative_path']
        elif kind != 'role':
            record['relative_path'] = self._materialize(record, state)
        if record.get('relative_path'):
            path = self.safe(record['relative_path'])
            record['original_filename'] = fields.get('original_filename') or (old or {}).get('original_filename') or path.name
            record['file_size'] = fields.get('file_size') if legacy else path.stat().st_size
            record['checksum'] = fields.get('checksum') if legacy else digest(path)
        state['records'][key] = record
        state['audit'].append({'event_uuid': str(uuid.uuid5(uuid.UUID(request['request_uuid']), 'audit')), 'request_uuid': request['request_uuid'],
            'record_uuid': key, 'actor': actor, 'device_id': request['device_id'], 'timestamp': timestamp(), 'prior': old, 'new': record,
            'reason': request.get('reason', ''), 'channel': CHANNEL, 'application_version': __version__})

    def _materialize(self, record, state):
        kind, fields = record['kind'], record['fields']
        folder = {'experiment': '01_Experimental/Experiments/' + record['id'],
            'sample': '01_Experimental/Samples/' + record['id'], 'procedure': '01_Experimental/Procedures/' + record['id'],
            'research': '02_Research/' + fields.get('research_section', 'Published_Articles'),
            'design': '04_Design_and_Prototyping/' + fields.get('design_section', 'CAD_and_Drawings'),
            'meeting': '03_Meetings_and_Goals/Meetings/' + record['created_at'][:10] + '_' + record['id'],
            'task': '03_Meetings_and_Goals/Goals_and_Milestones', 'file': '01_Experimental/Experiments/Unassigned'}[kind]
        ids = [record['id']]
        if kind == 'file':
            linked = state['records'].get(fields.get('experiment_uuid'), {})
            if linked:
                folder = '01_Experimental/Experiments/' + linked['id'] + ('/Raw_Data' if fields.get('file_state') == 'raw' else '/Processed_Data')
                ids = [linked['id']] + [state['records'][s]['id'] for s in fields.get('sample_uuids', [])]
            # File UUID is included to avoid collisions across simultaneous captures.
            ids.append(record['uuid'][:8])
            for link in ('meeting_uuid', 'design_uuid', 'research_uuid'):
                if fields.get(link):
                    linked = state['records'][fields[link]]
                    folder = str(Path(linked['relative_path']).parent).replace('\\', '/')
                    ids = [linked['id'], record['uuid'][:8]]
        if kind in ('research', 'design') and folder not in FOLDERS:
            raise ValueError('Choose an approved research/design subfolder.')
        extension = fields.get('extension', '.json') if kind == 'file' else '.json'
        name_kind = 'meeting' if kind == 'file' and fields.get('meeting_uuid') else 'design' if kind == 'file' and fields.get('design_uuid') else 'research' if kind == 'file' and fields.get('research_uuid') else kind
        description = fields.get('file_state') if kind == 'file' and fields.get('file_state') != 'reference' else record['title']
        name = filename(record['created_at'], name_kind, ids, description,
                        record['revision'], sequence=fields.get('sequence') if kind == 'file' else None, extension=extension)
        target = self.safe(folder + '/' + name)
        if kind == 'experiment':
            for child in ('Setup', 'Raw_Data', 'Processed_Data', 'Results', 'Notes_Logs'):
                self.safe(folder + '/' + child).mkdir(parents=True, exist_ok=True)
        if kind == 'file':
            upload = str(uuid.UUID(fields['upload_uuid']))
            source = self.safe('_System/Organization/Incoming_Files/' + upload)
            if digest(source) != fields['checksum'] or source.stat().st_size != fields['file_size']:
                raise ValueError('Upload incomplete or checksum differs; wait for sync and resubmit.')
            self._copy_once(source, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and read_json(target, {}) != record:
                raise ValueError('Revision destination already exists; never overwrite a document.')
            if not target.exists(): write_json(target, record)
        return target.relative_to(self.root).as_posix()

    def inventory(self, cancel=None, hash_limit=32 * 1024 * 1024):
        if not self.authority:
            raise ValueError('Only the enrolled Admin writer may scan legacy material.')
        report_path = self.control / 'Import_Reports' / 'inventory.json'
        report = read_json(report_path, {'schema': SCHEMA, 'files': {}, 'complete': False})
        managed = {r.get('relative_path') for r in self.rows() if not r.get('legacy')}
        for base, dirs, names in os.walk(self.root, followlinks=False):
            dirs[:] = [d for d in dirs if d not in ('_System', 'AppData', '.project_hub', '.git') and not redirects((Path(base) / d).lstat())]
            for name in names:
                if cancel and cancel():
                    report['complete'] = False; write_json(report_path, report); return report
                path = Path(base) / name
                relative = path.relative_to(self.root).as_posix()
                if relative in report['files'] or relative in managed:
                    continue
                stat = path.lstat()
                row = {'relative_path': relative, 'original_filename': name, 'file_size': stat.st_size,
                    'source_modified_at': stat.st_mtime, 'source_created_at': stat.st_ctime,
                    'creator': 'Unknown', 'dataset_status': 'old_test_data', 'checksum': None,
                    'category': self.classify(relative), 'state': self.classify_state(name)}
                row['detected_ids'] = re.findall(r'\b(?:MTG|E|S|P|R|D)\d{4,}\b', relative, flags=re.IGNORECASE)
                if not redirects(stat) and not getattr(stat, 'st_file_attributes', 0) & PLACEHOLDER_FLAGS and stat.st_size <= hash_limit:
                    row['checksum'] = digest(path)
                report['files'][relative] = row
                if len(report['files']) % 50 == 0:
                    write_json(report_path, report)
        report['complete'] = True; report['at'] = timestamp()
        report['aliases_found'] = [alias for alias in ('Holy GDL', '1344 Pascal') if any(alias.casefold() in p.casefold() for p in report['files'])]
        write_json(report_path, report)
        return report

    @staticmethod
    def classify(relative):
        value = relative.casefold()
        for category, folder in CATEGORIES.items():
            if value.startswith(folder.casefold() + '/'):
                return category
        if any(word in value for word in ('meeting', 'agenda', 'minutes', 'goal')):
            return 'Meetings & Goals'
        if Path(value).suffix in ('.sldprt', '.sldasm', '.step', '.stp', '.stl', '.3mf', '.dxf'):
            return 'Design & Prototyping'
        if any(word in value for word in ('paper', 'standard', 'literature', 'previous', 'research')):
            return 'Research'
        return 'Experimental'

    @staticmethod
    def classify_state(name):
        return next((s for s in ('poremap', 'overlay', 'outline', 'raw') if s in name.casefold()), 'reference')

    def import_inventory(self, report):
        if not self.authority:
            raise ValueError('Only Admin may accept a dry-run inventory.')
        for relative, legacy in report['files'].items():
            # Deterministic registration across retries; identity survives later edits.
            key = str(uuid.uuid5(uuid.UUID(read_json(self.control / 'identity.json', {})['project_uuid']), relative))
            if key in self.state['records']:
                continue
            kind = 'sample' if 'sample' in relative.casefold() else 'research'
            fields = {'aliases': [Path(relative).stem], 'provenance': 'Legacy inventory; conditions unverified',
                      'dataset_status': 'old_test_data', 'original_filename': legacy['original_filename'],
                      'checksum': legacy['checksum'], 'file_size': legacy['file_size'],
                      'source_created_at': legacy['source_created_at'], 'source_modified_at': legacy['source_modified_at'],
                      'file_state': legacy['state'], 'detected_ids_unverified': legacy.get('detected_ids', [])}
            request = {'request_uuid': str(uuid.uuid5(uuid.UUID(key), 'initial-import')), 'record_uuid': key,
                'kind': kind, 'title': Path(relative).stem, 'fields': fields, 'base_revision': 0,
                'actor': self.actor, 'device_id': self.accounts.install_id, 'created_at': timestamp(),
                'schema': SCHEMA, 'channel': CHANNEL, 'legacy': legacy, 'reason': 'Reviewed dry-run legacy inventory'}
            write_json(self.local / 'outbox' / (request['request_uuid'] + '.json'), request)
        self.flush()
        return self.consume()

    def reconcile(self):
        if not self.authority:
            raise ValueError('Only Admin may reconcile source availability.')
        status = {}
        for record in self.rows():
            if not record.get('relative_path'): continue
            path = self.safe(record['relative_path'])
            value = 'missing / possibly not synchronized; not deleted'
            if path.exists():
                value = 'available'
                stat = path.stat()
                if getattr(stat, 'st_file_attributes', 0) & PLACEHOLDER_FLAGS:
                    value = 'metadata available / content not resident; no hydration requested'
                elif record.get('checksum') and stat.st_size <= 32 * 1024 * 1024 and digest(path) != record['checksum']:
                    value = 'changed checksum / review required; original registration retained'
            status[record['uuid']] = value
        return status

    def rollback(self, revision):
        if not self.authority:
            raise ValueError('Only Admin may restore a published snapshot.')
        with update_lock(self.control):
            snapshots = list((self.control / 'Snapshots').glob(f'{int(revision):08d}-*.json'))
            if len(snapshots) != 1:
                raise ValueError('Select one unambiguous known-good snapshot.')
            selected = snapshots[0]
            pointers = [read_json(p, {}) for p in (self.control / 'Backups').glob('*.json')]
            pointer = next((p for p in pointers if p.get('snapshot') == selected.relative_to(self.control).as_posix()), None)
            if not pointer:
                raise ValueError('No checksum-backed manifest exists for that revision.')
            restored = self._read_snapshot(pointer)
            # Retain monotonically increasing counters and processed receipts so IDs
            # are never recycled and rolled-back requests cannot replay unexpectedly.
            restored['counters'] = dict(self.state['counters'])
            restored['requests'] = dict(self.state['requests'])
            restored['audit'] = list(self.state['audit']) + [{'event_uuid': str(uuid.uuid4()),
                'timestamp': timestamp(), 'actor': self.actor, 'reason': f'Rollback to snapshot {revision}'}]
            self._publish(restored)

    def pending(self):
        values = [read_json(p, {}) for p in (self.local / 'outbox').glob('*.json')]
        for p in (self.control / 'Incoming_Changes').glob('*.json'):
            row = read_json(p, {})
            if row.get('actor', {}).get('user_id') == self.actor['user_id'] or self.accounts.admin_unlocked:
                row['receipt'] = self.state['requests'].get(row.get('request_uuid'), {'status': 'pending'})
                values.append(row)
        return values

    def resubmit(self, request_id, reason):
        if not reason.strip():
            raise ValueError('Compare the published revision and explain your retry before resubmitting.')
        self.refresh()
        source = self.safe('_System/Organization/Incoming_Changes/' + str(uuid.UUID(request_id)) + '.json')
        previous = read_json(source, {})
        if not previous or self.state['requests'].get(request_id, {}).get('status') == 'accepted':
            raise ValueError('Select an unaccepted request; accepted requests cannot be replayed.')
        if previous['actor']['user_id'] != self.actor['user_id'] and not self.accounts.admin_unlocked:
            raise ValueError('Only the original contributor or Admin may resubmit this request.')
        request = copy.deepcopy(previous)
        record = self.state['records'].get(request['record_uuid'])
        request.update(request_uuid=str(uuid.uuid4()), base_revision=record['revision'] if record else 0,
                       actor=self.actor, device_id=self.accounts.install_id, created_at=timestamp(), reason=reason)
        request['fields'].setdefault('created_at', previous['fields'].get('created_at') or previous['created_at'])
        upload = request['fields'].get('upload_uuid')
        if upload:
            original = self.local / 'uploads' / str(uuid.UUID(upload))
            shared = self.safe('_System/Organization/Incoming_Files/' + upload)
            if shared.exists() and digest(shared) != request['fields']['checksum']:
                if not original.exists() or digest(original) != request['fields']['checksum']:
                    raise ValueError('The staged upload is incomplete and this device lacks the original. Upload the resident source again; both existing copies are preserved.')
                replacement = str(uuid.uuid4())
                self._copy_once(original, self.local / 'uploads' / replacement)
                request['fields']['upload_uuid'] = replacement
        write_json(self.local / 'outbox' / (request['request_uuid'] + '.json'), request)
        self.flush()
        return request['request_uuid']

    def activity_events(self):
        """Derive accepted activity from immutable audit IDs, without another log
        write that could be duplicated or lost after publication/restart."""
        result = []
        for audit in self.state['audit']:
            record = audit.get('new')
            if not record: continue
            kind = record['kind']; previous = audit.get('prior')
            event = ('LEGACY_REGISTERED' if record.get('legacy') and not previous else
                     'FILE_ADDED' if kind == 'file' and not previous else
                     'MEETING_NOTES_EDITED' if kind == 'meeting' and previous else
                     kind.upper() + ('_UPDATED' if previous else '_CREATED'))
            fields = record['fields']; details = {'reason': audit['reason'], 'attribution': 'app_user_action',
                'source': 'legacy' if record.get('legacy') else 'current', 'record_uuid': record['uuid']}
            if kind == 'file':
                extension = Path(record.get('relative_path', '')).suffix.lower()
                details['file_category'] = 'Images' if extension in ('.png', '.jpg', '.jpeg', '.tif', '.tiff') else 'Reports' if extension in ('.pdf', '.docx') else 'Data'
            for link, name in (('experiment_uuid', 'experiment_id'), ('sample_uuids', 'sample_id')):
                value = fields.get(link)
                if isinstance(value, list): value = value[0] if value else None
                if value in self.state['records']: details[name] = self.state['records'][value]['id']
            result.append({'id': audit['event_uuid'], 'client_event_id': audit['event_uuid'], 'user_id': audit['actor']['user_id'],
                'device_id': audit.get('device_id', 'Unknown'), 'created_at': audit['timestamp'], 'event_type': event,
                'category': kind.upper(), 'description': event.replace('_', ' ').title(), 'entity_type': kind,
                'entity_id': record['id'], 'entity_name': record['title'], 'details': details,
                'app_version': audit['application_version'], 'channel': CHANNEL, 'status': 'completed'})
        return result

    def meeting_text(self, key, stage):
        meeting = self.state['records'][key]
        if meeting['kind'] != 'meeting' or stage not in MEETING_TEMPLATES:
            raise ValueError('Choose a meeting and agenda, minutes or summary.')
        fields = meeting['fields']
        people = {p['id']: p['display_name'] for p in self.accounts.registry['users']}
        person = lambda key: people.get(key, key or 'Unassigned')
        actions = [r for r in self.rows(kind='task') if r['fields'].get('meeting_uuid') == key or r['uuid'] in fields.get('carried_actions', [])]
        return (f"{meeting['id']} · {meeting['title']} · {stage.title()}\nDate: {meeting['created_at'][:10]}\n"
                + 'Facilitator: ' + person(fields.get('facilitator_id')) + '\n'
                + 'Note-taker: ' + person(fields.get('note_taker_id')) + '\n'
                + 'Attendance: ' + ', '.join(person(p) for p in fields.get('attendees', [])) + '\n\n'
                + fields.get(stage, MEETING_TEMPLATES[stage]) + '\n\nActions:\n'
                + '\n'.join(f"{r['id']} · {r['title']} · owner {person(r['fields'].get('owner_id'))} · due {r['fields'].get('due_date')} · {r['fields'].get('status', 'planned')}" for r in actions))
