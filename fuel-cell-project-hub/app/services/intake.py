"""Recoverable batch intake; copy sources, preview provisional names, no overwrites."""
import uuid
from datetime import date
from pathlib import Path
from app.services.organization import CATEGORIES, FOLDERS, filename
from app.services.storage import read_json, write_json
from app.services.team_workflow import workspace_relative


class Intake:
    def __init__(self, organization):
        self.service = organization
        self.path = organization.local / ('intake-' + organization.actor['user_id'] + '.json')
        self.rows = read_json(self.path, [])

    def save(self): write_json(self.path, self.rows)

    def add(self, paths, fields=None):
        for source in paths:
            source = Path(source)
            if any(r['source'] == str(source) and r['status'] != 'Cancelled' for r in self.rows): continue
            values = dict(fields or {})
            values.setdefault('destination_category', self.service.classify(source.name))
            values.setdefault('file_state', self.service.classify_state(source.name))
            values.setdefault('created_at', date.today().isoformat())
            self.rows.append({'queue_uuid': str(uuid.uuid4()), 'source': str(source), 'title': source.stem,
                              'fields': values, 'status': 'Ready', 'error': '', 'record_uuid': None})
        self.save()

    def preview(self, row):
        source, fields = Path(row['source']), row['fields']
        for key in ('experiment_uuid', 'meeting_uuid', 'research_uuid', 'design_uuid', 'deliverable_uuid'):
            if fields.get(key) and fields[key] not in self.service.state['records']:
                raise ValueError('A linked record is unavailable. Wait for a valid snapshot or edit this file context.')
        ids = []
        for key in ('experiment_uuid', 'sample_uuids', 'procedure_uuid', 'research_uuid', 'design_uuid', 'meeting_uuid'):
            values = fields.get(key, []) if key.endswith('uuids') else [fields.get(key)]
            ids.extend(self.service.state['records'][v]['id'] for v in filter(None, values) if v in self.service.state['records'])
        proposed = filename(fields.get('created_at') or date.today().isoformat(), 'file', ids + [row['queue_uuid'][:8]],
                            fields.get('file_state', 'reference') if fields.get('file_state', 'reference') != 'reference' else row['title'],
                            extension=source.suffix)
        category = fields.get('destination_category', 'Experimental')
        folder = '01_Experimental/Experiments/Unassigned' if category == 'Experimental' else next(p for p in FOLDERS if p.startswith(CATEGORIES[category] + '/'))
        if fields.get('experiment_uuid'):
            experiment = self.service.state['records'][fields['experiment_uuid']]
            folder = '01_Experimental/Experiments/' + experiment['id'] + ('/Raw_Data' if fields.get('file_state') == 'raw' else '/Processed_Data')
        for key in ('meeting_uuid', 'research_uuid', 'design_uuid', 'deliverable_uuid'):
            if fields.get(key): folder = Path(self.service.state['records'][fields[key]]['relative_path']).parent.as_posix()
        if fields.get('workspace_owner_id'): folder = workspace_relative(self.service, fields['workspace_owner_id'])
        return {'old': source.name, 'proposed': proposed, 'folder': folder, 'links': ', '.join(ids),
                'creator': self.service.actor['display_name'], 'identity': 'Provisional UUID; final ID/name confirmed by Admin'}

    def apply(self, cancelled=lambda: False, progress=lambda: None):
        for row in self.rows:
            if cancelled(): break
            if row['status'] in ('Queued', 'Cancelled'): continue
            try:
                key = row['queue_uuid']
                if key in self.service.state['records'] or any(p.get('record_uuid') == key for p in self.service.pending()):
                    row['record_uuid'], row['status'], row['error'] = key, 'Queued', ''
                    self.save(); progress(); continue
                self.preview(row)
                self.service._validate_fields('file', row['fields'], self.service.state['records'])
                row['record_uuid'] = self.service.upload(Path(row['source']), row['title'], row['fields'], record_uuid=key)
                row['status'], row['error'] = 'Queued', ''
            except (OSError, ValueError, KeyError) as exc:
                row['status'], row['error'] = 'Needs attention', str(exc) if isinstance(exc, ValueError) else 'Source unavailable; originals and successful queue entries are preserved.'
            self.save(); progress()
        return self.rows
