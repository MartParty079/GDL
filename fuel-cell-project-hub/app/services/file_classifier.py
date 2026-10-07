"""Conservative metadata classification; never opens dataset contents."""
import re
from pathlib import PurePosixPath

CATEGORIES = ('Image', 'Video', 'Sensor Data', 'Spreadsheet', 'Document', 'Procedure',
              'Report', 'Code', 'CAD', 'Configuration', 'Reference', 'Other')
EXTENSIONS = {
    'Image': '.tif .tiff .png .jpg .jpeg .bmp .gif', 'Video': '.mp4 .mov .avi .mkv .wmv',
    'Sensor Data': '.csv .tsv .dat', 'Spreadsheet': '.xlsx .xlsm .xls .ods',
    'Document': '.docx .doc .pdf .md .rtf .pptx .txt',
    'Code': '.py .m .jsl .ipynb .js .ts .ps1 .r .ijm',
    'CAD': '.sldprt .sldasm .slddrw .step .stp .iges .igs .stl .dxf .dwg',
    'Configuration': '.json .yaml .yml .toml .ini .xml'}
DEFAULT_RULES = {'01_Procedures': 'Procedure', '07_Reports': 'Report', '08_Reference': 'Reference'}


def classify_file(relative, explicit=None, manual=None, rules=None):
    explicit, manual = explicit or {}, manual or {}
    path = PurePosixPath(relative)
    context = relative.casefold().replace('_', ' ').replace('-', ' ')
    category, source, confidence = 'Other', 'extension', 'low'
    for candidate, extensions in EXTENSIONS.items():
        if path.suffix.lower() in extensions.split():
            category, confidence = candidate, 'medium'
            break
    if category in ('Document', 'Other') and path.suffix.lower() in ('.txt', '.log', '.csv', '.dat') and any(word in context for word in ('pressure', 'flow', 'temperature', 'water intrusion', 'compression')):
        category, source, confidence = 'Sensor Data', 'filename', 'medium'
    folders = dict(DEFAULT_RULES)
    folders.update((rules or {}).get('folder_rules', {}))
    for part in path.parts[:-1]:
        if part in folders and folders[part] in CATEGORIES:
            category, source, confidence = folders[part], 'folder', 'high'
    if any(part in ('04_Raw_Data', 'raw_data', 'sensor_data') for part in path.parts[:-1]) and category == 'Sensor Data':
        source, confidence = 'folder', 'high'
    for values, name in ((explicit, 'metadata'), (manual, 'manual')):
        if values.get('category') in CATEGORIES:
            category, source, confidence = values['category'], name, 'high'
    subcategory = ''
    if category == 'Image':
        subcategory = 'Unknown Image'
        for word, value in (('pre imaging', 'Pre Imaging'), ('post imaging', 'Post Imaging'),
                            ('microscopy', 'Microscopy'), ('processed', 'Processed Image'),
                            ('threshold', 'Threshold Result'), ('pore', 'Pore Map')):
            if word in context:
                subcategory = value
                break
    elif category == 'Sensor Data':
        subcategory = 'Unknown Sensor Data'
        for word in ('pressure', 'flow', 'temperature', 'water intrusion', 'compression'):
            if word in context:
                subcategory = word.title()
                break
    elif category == 'Report':
        subcategory = 'Reference Report'
        for word in ('experiment', 'lab', 'analysis', 'presentation'):
            if word in context:
                subcategory = word.title() + (' Report' if word != 'presentation' else '')
                break
    subcategory = manual.get('subcategory', explicit.get('subcategory', subcategory))
    relationships = {key: '' for key in ('experiment_id', 'run_id', 'sample_id', 'procedure_id', 'procedure_version')}
    # IDs need explicit prefixes; ordinary historical folder names are not current IDs.
    for prefix, key in (('E', 'experiment_id'), ('S', 'sample_id'), ('P', 'procedure_id')):
        match = re.search(r'(?<![A-Za-z0-9])(' + prefix + r'-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)(?![A-Za-z0-9])', relative)
        if match:
            relationships[key] = match.group(1)
    for values in (explicit, manual):
        relationships.update({key: value for key, value in values.items() if key in relationships and isinstance(value, str)})
    return {'category': category, 'subcategory': subcategory, 'classification_source': source,
            'classification_confidence': confidence, **relationships}
