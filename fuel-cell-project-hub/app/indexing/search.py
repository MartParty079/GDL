"""Parameterized FTS5 prefix search and metadata filters; no raw MATCH syntax."""
import re


def match_expression(query):
    words = re.findall(r'\w+', query, flags=re.UNICODE)[:32]
    return ' AND '.join('"' + word.replace('"', '""') + '"*' for word in words)


def predicates(filters, source_ids):
    clauses = ['m.source_id IN (' + ','.join('?' for _ in source_ids) + ')']
    args = list(source_ids)
    mapping = {'category': 'category', 'extension': 'extension', 'document_type': 'document_type',
        'source': 'source_name', 'project': 'project_name', 'availability': 'availability',
        'duplicate': 'duplicate_status', 'legacy_project': 'source_id',
        'experiment': 'experiment_id', 'run': 'run_id', 'procedure': 'procedure_id'}
    for key, column in mapping.items():
        if filters.get(key):
            clauses.append('m.' + column + '=?')
            args.append(filters[key])
    if filters.get('empty_context'):
        clauses.append('0')
    if filters.get('sample'):
        fallback = 'SELECT file_id FROM research_file_links WHERE sample_id=?' if filters.get('explicit') else 'SELECT id FROM file_metadata WHERE sample_id=?'
        clauses.append('m.id IN (SELECT file_id FROM file_sample_links WHERE sample_id=? UNION '+fallback+')')
        args.extend([filters['sample'],filters['sample']])
    for key in ('image_category','image_subcategory'):
        if filters.get(key):
            clauses.append('m.id IN (SELECT file_id FROM image_assets WHERE '+key+'=?)')
            args.append(filters[key])
    if filters.get('image_family'):
        clauses.append('m.id IN (SELECT file_id FROM image_assets WHERE family_id=?)')
        args.append(filters['image_family'])
    if filters.get('group_families'):
        clauses.append("m.id IN (SELECT coalesce(nullif(original_id,''),min(file_id)) FROM image_assets GROUP BY family_id)")
    if filters.get('explicit'):
        for key,column in (('sample','sample_id'),('experiment','experiment_id')):
            if filters.get(key):
                if key=='sample':
                    continue  # Already selects confirmed and normalized relationships above.
                else:
                    clauses.append('m.id IN (SELECT file_id FROM research_file_links WHERE '+column+'=?)')
                    args.append(filters[key])
    if filters.get('origin'):
        clauses.append('m.data_origin=?')
        args.append(filters['origin'])
    if filters.get('archive', 'active') == 'active':
        clauses.append('m.archived=0')
    elif filters.get('archive') == 'archived':
        clauses.append('m.archived=1')
    for key, symbol in (('date_from', '>='), ('date_to', '<=')):
        if filters.get(key):
            clauses.append('substr(m.modified,1,10)' + symbol + '?')
            args.append(filters[key])
    for key, column in (('tags', 'tags'), ('folder', 'parent_folder')):
        if filters.get(key):
            clauses.append('instr(lower(m.' + column + '),lower(?))>0')
            args.append(filters[key])
    if filters.get('favorite'):
        clauses.append('m.favorite=1')
    if filters.get('exact_folder') is not None:
        clauses.append('m.parent_folder=?')
        args.append(filters['exact_folder'])
    if filters.get('source_id'):
        clauses.append('m.source_id=?')
        args.append(filters['source_id'])
    family = filters.get('family')
    if family in FAMILIES:
        extensions = FAMILIES[family]
        clauses.append('m.extension IN (' + ','.join('?' for _ in extensions) + ')')
        args.extend(extensions)
    if filters.get('recent'):
        clauses.append('m.id IN (SELECT file_id FROM workspace_recent)')
    if filters.get('needs_review'):
        clauses.append("""(NOT EXISTS (SELECT 1 FROM file_sample_links l WHERE l.file_id=m.id)
          OR m.category IN ('Other','Unclassified') OR m.content_status='Extraction failed'
          OR m.id IN (SELECT file_id FROM image_assets WHERE image_category='Unknown' OR image_category='Generated / Processed' AND original_id=''))""")
    clauses.append('m.id NOT IN (SELECT file_id FROM workspace_hidden)')
    return clauses, args


FAMILIES = {
    'Images': ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.gif', '.webp'),
    'Reports': ('.pdf', '.docx', '.doc', '.pptx'),
    'Data': ('.csv', '.tsv', '.xlsx', '.xls', '.json', '.mat', '.jmp'),
    'Code': ('.py', '.m', '.js', '.bat', '.ps1', '.cmd'),
}
SORTS = {
    'Name': 'm.name COLLATE NOCASE',
    'Name Z-A': 'm.name COLLATE NOCASE DESC',
    'Title': 'm.title COLLATE NOCASE,m.name COLLATE NOCASE',
    'Modified newest': 'm.modified DESC',
    'Modified oldest': 'm.modified ASC',
    'Created newest': "coalesce(json_extract(f.payload,'$.created'),m.modified) DESC",
    'Type': 'm.extension,m.name COLLATE NOCASE',
    'Size largest': 'm.size DESC',
    'Size smallest': 'm.size ASC',
    'Original first': "coalesce((SELECT image_category<>'Original' FROM image_assets a WHERE a.file_id=m.id),1),m.name COLLATE NOCASE",
    'Generated first': "coalesce((SELECT image_category<>'Generated / Processed' FROM image_assets a WHERE a.file_id=m.id),1),m.name COLLATE NOCASE",
    'Sample': 'm.sample_id,m.name COLLATE NOCASE',
    'Experiment': 'm.experiment_id,m.name COLLATE NOCASE',
    'Category': 'm.category,m.name COLLATE NOCASE',
    'Current / legacy': "m.data_origin<>'current',m.name COLLATE NOCASE",
    'Recently viewed': '(SELECT viewed_at FROM workspace_recent r WHERE r.file_id=m.id) DESC',
     'Recently added': "coalesce((SELECT added_at FROM workspace_files w WHERE w.file_id=m.id),json_extract(f.payload,'$.indexed')) DESC",
    'Report version': "coalesce(json_extract(f.payload,'$.report_version'),'') DESC",
    'Status': 'm.availability,m.name COLLATE NOCASE',
}
