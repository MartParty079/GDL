"""Team planning policies on the existing Organization snapshot/event transport.

No parallel database, network service, calendar cutoff or attribution inference.
"""
import copy
from datetime import date, datetime, timedelta, timezone
from app.services.storage import timestamp

STATUSES = ('To Do', 'In Progress', 'Blocked', 'Done')
SUBMISSION_STATES = ('Draft', 'Submitted', 'Under Review', 'Accepted', 'Changes Requested', 'Resubmitted')
TRANSITIONS = {
    'Draft': {'Draft', 'Submitted'}, 'Submitted': {'Under Review', 'Changes Requested'},
    'Under Review': {'Accepted', 'Changes Requested'}, 'Changes Requested': {'Draft', 'Resubmitted'},
    'Resubmitted': {'Under Review', 'Changes Requested'}, 'Accepted': set(),
}


def instant(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Enter a due date/time with timezone, for example 2026-10-23T17:00:00-05:00.')
    return result


def is_lead(service, actor, records):
    return (service.accounts.find(actor)['role'] == 'admin' or any(
        r['kind'] == 'role' and r['fields'].get('member_id') == actor for r in records.values()))


def validate(service, kind, fields, records, old=None, actor=None):
    actor = actor or service.actor['user_id']
    admin = service.accounts.find(actor)['role'] == 'admin'
    if kind == 'file' and fields.get('deliverable_uuid'):
        submission = records.get(fields['deliverable_uuid'], {})
        if submission.get('fields', {}).get('submission_status') == 'Accepted':
            raise ValueError('Upload additional evidence to an addendum; accepted submissions are locked.')
        if submission.get('fields', {}).get('owner_id') != actor:
            raise ValueError('Only the contributor uploads their submission artifacts.')
    if kind in ('goal', 'deliverable') and not fields.get('owner_id'):
        raise ValueError('Choose one accountable owner.')
    if kind == 'goal':
        if fields.get('status', 'To Do') not in STATUSES or not fields.get('due_date') or not fields.get('output'):
            raise ValueError('Goals need an output, due date and supported status.')
    if kind == 'period':
        if not admin:
            raise ValueError('Only Admin configures reporting periods.')
        start, end = date.fromisoformat(fields['start_date']), date.fromisoformat(fields['end_date'])
        if end != start + timedelta(days=13):
            raise ValueError('Each biweekly period contains exactly fourteen days.')
        due = instant(fields['due_at'])
        if due.date() < end:
            raise ValueError('The deadline must be on or after the reporting period ends.')
        for key in ('grace_at', 'review_at'):
            if fields.get(key) and instant(fields[key]) < due:
                raise ValueError('Grace and review dates cannot precede the deadline.')
        for row in records.values():
            if row['kind'] != 'period' or old and row['uuid'] == old['uuid']: continue
            f = row['fields']
            if start <= date.fromisoformat(f['end_date']) and end >= date.fromisoformat(f['start_date']):
                raise ValueError('Reporting periods must not overlap.')
        if old and any(r['kind'] == 'deliverable' and r['fields'].get('period_uuid') == old['uuid'] for r in records.values()):
            if any(fields[k] != old['fields'][k] for k in ('start_date', 'end_date')):
                raise ValueError('A period with submissions retains its original date span.')
    for key, expected in (('period_uuid', 'period'), ('goal_uuid', 'goal'), ('addendum_to', 'deliverable')):
        if fields.get(key) and records.get(fields[key], {}).get('kind') != expected:
            raise ValueError('Choose a published ' + expected + ' record.')
    if kind != 'deliverable': return
    status = fields.get('submission_status', 'Draft')
    if status not in SUBMISSION_STATES or not fields.get('period_uuid'):
        raise ValueError('Select a reporting period and submission status.')
    if fields.get('role_uuid') and records.get(fields['role_uuid'], {}).get('kind') != 'role':
        raise ValueError('Choose a published coordination role.')
    for key in fields.get('evidence_uuids', []):
        if key not in records: raise ValueError('Evidence must link published records.')
    previous = old['fields'].get('submission_status', 'Draft') if old else 'Draft'
    if old and status not in TRANSITIONS[previous]:
        raise ValueError('This submission transition is unavailable; accepted versions are locked. Create an addendum.')
    review = status in ('Under Review', 'Accepted', 'Changes Requested')
    if review:
        if not is_lead(service, actor, records):
            raise ValueError('A coordination lead or Admin reviews submissions.')
        if fields.get('reviewer_id') != actor:
            raise ValueError('The reviewer must be your signed-in identity.')
        if status == 'Changes Requested' and not fields.get('feedback', '').strip():
            raise ValueError('Explain the requested changes.')
        if old and any(fields.get(k) != old['fields'].get(k) for k in
                       ('owner_id', 'period_uuid', 'work_completed', 'next_plan', 'evidence_uuids', 'results', 'blockers', 'support_needed')):
            raise ValueError('Review preserves the contributor content; use feedback to request changes.')
    elif actor != fields['owner_id']:
        raise ValueError('Only the accountable contributor edits or submits their deliverable.')
    if old and any(fields.get(k) != old['fields'].get(k) for k in ('owner_id', 'period_uuid', 'addendum_to')):
        raise ValueError('Submission owner and reporting period are permanent.')
    if not old:
        if status not in ('Draft', 'Submitted'):
            raise ValueError('A new submission starts Draft or Submitted.')
        if any(r['kind'] == 'deliverable' and r['fields'].get('owner_id') == fields['owner_id'] and
               r['fields'].get('period_uuid') == fields['period_uuid'] and not r['fields'].get('addendum_to')
               for r in records.values()) and not fields.get('addendum_to'):
            raise ValueError('Edit the existing individual submission, or create an addendum after acceptance.')
    if fields.get('addendum_to'):
        parent = records[fields['addendum_to']]
        if parent['fields'].get('submission_status') != 'Accepted' or any(
            fields.get(k) != parent['fields'].get(k) for k in ('period_uuid', 'owner_id')):
            raise ValueError('Addendums link an accepted submission for the same person and period.')
    if status in ('Submitted', 'Resubmitted') and not fields.get('work_completed', '').strip() and not fields.get('evidence_uuids'):
        raise ValueError('Describe completed work or link an uploaded artifact before submission.')


def enrich(kind, fields, old, actor, when):
    if kind == 'deliverable':
        status = fields.get('submission_status', 'Draft')
        previous = (old or {}).get('fields', {})
        if status not in ('Under Review', 'Accepted', 'Changes Requested'):
            for key in ('reviewer_id', 'feedback', 'reviewed_at'):
                if key in previous: fields[key] = previous[key]
                else: fields.pop(key, None)
        if status not in ('Submitted', 'Resubmitted'):
            if 'submitted_at' in previous: fields['submitted_at'] = previous['submitted_at']
            else: fields.pop('submitted_at', None)
        # Server-derived history: a contributor cannot supply a review time/identity.
        fields['submission_history'] = copy.deepcopy((old or {}).get('fields', {}).get('submission_history', []))
        fields['submission_history'].append({'status': status, 'actor_id': actor, 'at': when,
                                              'feedback': fields.get('feedback', '')})
        if status in ('Submitted', 'Resubmitted'): fields['submitted_at'] = when
        if status in ('Accepted', 'Changes Requested', 'Under Review'): fields['reviewed_at'] = when
    if kind == 'meeting':
        before = (old or {}).get('fields', {})
        if fields.get('summary_approved') == 'Yes':
            if before.get('summary_approved') == 'Yes' and fields.get('summary') != before.get('summary'):
                raise ValueError('Reopen the summary as Draft before changing approved text.')
            fields['summary_approved_at'] = before.get('summary_approved_at') or when
        else:
            fields.pop('summary_approved_at', None)
        fields['summary_written_by_id'] = actor if fields.get('summary') != before.get('summary') else before.get('summary_written_by_id', actor)


def user_code(service, identity, state=None):
    state = state or service.state
    mapping = state.get('workspace_users', {})
    if identity in mapping: return mapping[identity]['code']
    # Preview only. Authority persists this allocation, never a client counter.
    roster = service.accounts.registry['users']
    return 'U' + str(next(i for i, p in enumerate(roster, 1) if p['id'] == identity)).zfill(4)


def workspace_relative(service, identity, state=None):
    state = state or service.state
    value = state.get('workspace_users', {}).get(identity)
    return value['path'] if value else '_Team_Workspaces/' + user_code(service, identity, state)


def ensure_workspaces(service):
    if not service.authority: raise ValueError('Only the enrolled Admin initializes shared workspaces.')
    from app.services.organization import token
    from app.services.updates import update_lock
    with update_lock(service.control):
        if not service.refresh(): raise ValueError('Load a validated snapshot before setting up workspaces.')
        state = copy.deepcopy(service.state)
        mapping = state.setdefault('workspace_users', {})
        used = {int(v['code'][1:]) for v in mapping.values()}
        for person in service.accounts.registry['users']:
            if person['id'] not in mapping:
                number = max(used, default=0) + 1; used.add(number)
                code = f'U{number:04d}'
                mapping[person['id']] = {'code': code, 'path': '_Team_Workspaces/' + code + '_' + token(person['display_name'])}
            service.safe(mapping[person['id']]['path']).mkdir(parents=True, exist_ok=True)
        # Reserve space for the unnamed fifth member; never invent an account.
        if len(mapping) < 5: service.safe('_Team_Workspaces/U0005_Unassigned').mkdir(parents=True, exist_ok=True)
        if mapping != service.state.get('workspace_users'): service._publish(state)
    return mapping


def period_status(service, period, owner, now=None):
    now = now or datetime.now(timezone.utc)
    submissions = [r for r in service.rows(kind='deliverable') if r['fields'].get('period_uuid') == period['uuid']
                   and r['fields'].get('owner_id') == owner and not r['fields'].get('addendum_to')]
    row = submissions[0] if submissions else None
    status = row['fields'].get('submission_status', 'Draft') if row else 'Not started'
    if status in ('Submitted', 'Resubmitted', 'Under Review', 'Accepted'): return status
    due = instant(period['fields'].get('grace_at') or period['fields']['due_at'])
    if now > due: return 'Overdue · ' + status
    if due - now <= timedelta(days=3): return 'Due Soon · ' + status
    return status


def configure_periods(service, anchor, count, first_due):
    service.accounts.require_admin()
    start, due = date.fromisoformat(anchor), instant(first_due)
    if not 1 <= count <= 26: raise ValueError('Configure between one and twenty-six reporting periods.')
    planned = []
    records = copy.deepcopy(service.state['records'])
    for index in range(count):
        begin = start + timedelta(days=14 * index)
        fields = {'start_date': begin.isoformat(), 'end_date': (begin + timedelta(days=13)).isoformat(),
                  'due_at': (due + timedelta(days=14 * index)).isoformat()}
        validate(service, 'period', fields, records)
        planned.append(fields)
        records['preview-' + str(index)] = {'uuid': 'preview-' + str(index), 'kind': 'period', 'fields': fields}
    # Validate the entire proposal before queuing any part of the semester.
    return [service.submit('period', f"{f['start_date']} — {f['end_date']}", f) for f in planned]


def digest_text(service, period):
    people = service.accounts.registry['users']
    lines = [period['id'] + ' · ' + period['title'], 'Deadline: ' + period['fields']['due_at'],
             'Activity counts do not measure contribution quality.', '']
    for person in people:
        lines.append(user_code(service, person['id']) + ' · ' + person['display_name'] + ': ' + period_status(service, period, person['id']))
    for kind in ('deliverable', 'goal', 'task'):
        for row in service.rows(kind=kind):
            f = row['fields']
            if f.get('period_uuid') == period['uuid']:
                lines.extend(['', row['id'] + ' · ' + row['title'], 'Status: ' + f.get('submission_status', f.get('status', 'To Do')),
                              'Owner: ' + next((p['display_name'] for p in people if p['id'] == f.get('owner_id')), 'Unassigned'),
                              'Completed: ' + f.get('work_completed', ''), 'Blockers: ' + f.get('blockers', ''),
                              'Next: ' + f.get('next_plan', ''), 'Evidence: ' + ', '.join(service.state['records'][k]['id'] for k in f.get('evidence_uuids', []))])
    return '\n'.join(lines)


def draft_summary(service, meeting):
    fields = meeting['fields']
    # Deliberately template-driven: no fabricated inference or remote AI call.
    topics = [line.strip() for line in fields.get('minutes', '').splitlines() if line.strip()]
    overview = ' '.join(topics[:4]) or 'No meeting notes have been entered.'
    actions = [r for r in service.rows(kind='task') if r['fields'].get('meeting_uuid') == meeting['uuid'] or r['uuid'] in fields.get('carried_actions', [])]
    people = {p['id']: p['display_name'] for p in service.accounts.registry['users']}
    return ('DRAFT — verify against the original minutes.\n\nOverview:\n' + overview + '\n\nDecisions:\n' + fields.get('decisions', '')
            + '\n\nAction register:\n' + '\n'.join(r['id'] + ' · ' + r['title'] + ' · ' + people.get(r['fields'].get('owner_id'), 'Unassigned')
                + ' · due ' + r['fields'].get('due_date', '') + ' · ' + r['fields'].get('acceptance', '') for r in actions)
            + '\n\nBlockers:\n' + fields.get('blockers', '') + '\n\nUpcoming priorities:\n' + fields.get('next_priorities', ''))
