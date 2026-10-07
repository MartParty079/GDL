"""Personal project locations and a transactional, read-only research catalog.

Provider JSON files are transport snapshots. SQLite is the combined searchable
catalog. Scanning never creates markers, reads placeholders or changes sources.
"""
import copy
import os
import uuid
from pathlib import Path
from app.services.storage import timestamp, read_json
from app.services.project_storage import redirects
from app.services.file_classifier import classify_file

RESEARCH_CATEGORIES = ('Literature', 'Research Papers', 'Standards', 'GDL Images', 'Microscopy',
    'Raw Experimental Data', 'Processed Data', 'Analysis', 'Python / MATLAB / Code',
    'Previous Reports', 'Presentations', 'Test Rig', 'Water Intrusion Testing',
    'Compression Testing', 'Pressure Testing', 'Image Analysis', 'CAD', 'Drawings',
    'Equipment', 'Calibration', 'Procedures', 'Meeting Notes', 'Project Management',
    'Funding / Grants', 'Miscellaneous')
PATH_LABELS = {'shared_storage': 'Shared Storage', 'database': 'Index / Database folder',
    'generated': 'Generated Output', 'cache': 'Temp / Cache', 'backups': 'Backups'}


def research_category(relative):
    value = relative.casefold().replace('_', ' ').replace('-', ' ')
    rules = [('microscopy', 'Microscopy'), ('water intrusion', 'Water Intrusion Testing'),
        ('compression', 'Compression Testing'), ('pressure', 'Pressure Testing'),
        ('calibration', 'Calibration'), ('standard', 'Standards'), ('literature', 'Literature'),
        ('paper', 'Research Papers'), ('presentation', 'Presentations'), ('meeting', 'Meeting Notes'),
        ('grant', 'Funding / Grants'), ('funding', 'Funding / Grants'), ('procedure', 'Procedures'),
        ('processed', 'Processed Data'), ('raw', 'Raw Experimental Data'), ('test rig', 'Test Rig'),
        ('equipment', 'Equipment'), ('drawing', 'Drawings'), ('report', 'Previous Reports'),
        ('analysis', 'Analysis'), ('management', 'Project Management')]
    for word, category in rules:
        if word in value:
            return category
    extension = Path(relative).suffix.lower()
    if extension in ('.py', '.m', '.jsl', '.ijm', '.ipynb', '.bat', '.ps1', '.r'):
        return 'Python / MATLAB / Code'
    kind = classify_file(relative)['category']
    return {'Image': 'GDL Images', 'CAD': 'CAD', 'Sensor Data': 'Raw Experimental Data',
            'Spreadsheet': 'Raw Experimental Data', 'Reference': 'Literature'}.get(kind, 'Miscellaneous')


class ProjectLocations:
    def __init__(self, store):
        self.store = store
        self.value = copy.deepcopy(store.local.get('project_locations') or self.defaults())
        self.value.setdefault('additional', [])
        self.validate(self.value)

    def defaults(self):
        from app.services.resources import RESOURCE_ROOT
        template = read_json(RESOURCE_ROOT / 'config/research_defaults.json', {})
        drive = Path(os.environ.get('OneDriveCommercial') or os.environ.get('OneDrive') or
                     Path.home() / 'OneDrive - tarleton.edu (NTNET)')
        def source(name, folder, kind):
            return {'id': str(uuid.uuid5(uuid.NAMESPACE_URL, 'research-hub:' + kind + ':' + folder)),
                    'source_label': name, 'name': 'Previous GDL Research' if kind == 'legacy' else name, 'root_path': str(drive / folder), 'project_type': kind,
                    'source_type': kind, 'dataset_status': 'old_test_data' if kind == 'legacy' else 'current',
                    'read_only': kind == 'legacy', 'created_date': timestamp(), 'active': kind == 'active'}
        active = template.get('active', {'name': 'GDL Research', 'folder': 'GDL research - General'})
        legacy = template.get('legacy', [{'name': 'Michelson GDL Stuffs', 'folder': "Michelson, Andrew's files - GDL Stuffs"}])
        return {'enabled': False, 'active': source(active['name'], active['folder'], 'active'),
            'legacy': [source(s['name'], s['folder'], 'legacy') for s in legacy],
            'projects': [], 'shared_storage': str(drive / 'GDL research - General'),
            **{k: str(self.store.local_dir / v) for k, v in template.get('application_folders',
               {'database': 'catalog', 'generated': 'generated', 'cache': 'cache', 'backups': 'backups'}).items()}}

    @staticmethod
    def validate(value):
        roots = []
        identities = set()
        for source in [value['active'], *value['legacy'], *value.get('additional', [])]:
            try:
                uuid.UUID(source['id'])
            except (ValueError, KeyError, TypeError):
                raise ValueError('The project identity is invalid. Restore valid personal configuration.') from None
            if source['id'] in identities:
                raise ValueError('Each research source needs a separate project identity.')
            identities.add(source['id'])
            path = Path(os.path.expandvars(source['root_path'])).expanduser()
            if not path.is_absolute() or path == Path(path.anchor) or path == Path.home():
                raise ValueError('Choose a dedicated absolute research folder.')
            if path.exists() and redirects(path.lstat()):
                raise ValueError('Choose a direct research folder, not a filesystem link.')
            if any(path == root or path in root.parents or root in path.parents for root in roots):
                raise ValueError('Current and legacy sources must be separate, non-overlapping folders.')
            roots.append(path)
        for key in PATH_LABELS:
            path = Path(os.path.expandvars(value[key])).expanduser()
            if not path.is_absolute() or path == Path(path.anchor) or path == Path.home():
                raise ValueError('Choose dedicated absolute storage folders.')
            if key != 'shared_storage':
                path = path.resolve()
                if any(path == root.resolve() or root.resolve() in path.parents for root in roots):
                    raise ValueError('Keep databases, generated output, cache and backups outside research sources.')
        if len({str(Path(value[k]).resolve()) for k in ('database', 'generated', 'cache', 'backups')}) != 4:
            raise ValueError('Use separate application-owned storage folders.')

    def save(self, value):
        value = copy.deepcopy(value)
        for source in [value['active'], *value['legacy'], *value.get('additional', [])]:
            source['root_path'] = str(Path(os.path.expandvars(source['root_path'])).expanduser().resolve())
        for key in PATH_LABELS:
            value[key] = str(Path(os.path.expandvars(value[key])).expanduser().resolve())
        self.validate(value)
        # Changing projects creates a stable identity; remapping the same project
        # can retain its ID through the explicit project selector.
        old = self.value['active']
        if old['root_path'] != value['active']['root_path'] and old['id'] == value['active']['id']:
            value['active']['id'] = str(uuid.uuid4())
            value['active']['created_date'] = timestamp()
        if old['id'] != value['active']['id']:
            projects = {s['id']: s for s in value.get('projects', [])}
            projects[old['id']] = dict(old, active=False)
            value['projects'] = [s for identity, s in projects.items() if identity != value['active']['id']]
        for source in value['legacy']:
            source.update(source_type='legacy', project_type='legacy', dataset_status='old_test_data', read_only=True, active=False)
        value['active'].update(source_type='active', project_type='active', dataset_status='current', active=True)
        value['enabled'] = True
        self.store.local['project_locations'] = value
        self.store.save_local()
        self.value = value
        self.store.record('Configuration', 'Research project locations changed; source files preserved')

    def sources(self):
        return [self.value['active'], *self.value['legacy'], *self.value.get('additional', [])]

    def status(self):
        return [{'name': s['name'], 'status': 'Available' if Path(s['root_path']).is_dir() and
                 os.access(s['root_path'], os.R_OK) else 'Disconnected / inaccessible'} for s in self.sources()]
