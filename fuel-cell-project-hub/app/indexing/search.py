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
        'experiment': 'experiment_id', 'run': 'run_id', 'sample': 'sample_id', 'procedure': 'procedure_id'}
    for key, column in mapping.items():
        if filters.get(key):
            clauses.append('m.' + column + '=?')
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
    return clauses, args
