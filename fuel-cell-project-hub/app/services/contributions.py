"""Measurable Hub participation. No keyboard, pointer or outside-app capture."""
import csv
import html
import time
import uuid
from datetime import datetime, timedelta, timezone
from app import __version__
from app.services.storage import read_json, write_json
from app.services.formatting import format_duration

IDLE_SECONDS = 15 * 60


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)


def utc_text(value):
    return value.astimezone(timezone.utc).isoformat()


class ActiveSession:
    """Tick before resetting activity; monotonic time resists clock adjustments."""
    def __init__(self, user_id, install_id, clock=time.monotonic, now=None, idle=IDLE_SECONDS):
        self.clock = clock
        self.anchor = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        self.start = self.last_tick = self.last_touch = clock()
        self.idle = idle
        self.focused = True
        self.closed = False
        self.intervals = []
        self.row = dict(id=str(uuid.uuid4()), user_id=user_id, install_id=install_id,
                        started_at=utc_text(self.anchor), last_active_at=utc_text(self.anchor),
                        ended_at=None, active_seconds=0, active_intervals=[], app_version=__version__)

    def at(self, seconds):
        return utc_text(self.anchor + timedelta(seconds=seconds-self.start))

    def tick(self):
        if self.closed:
            return dict(self.row)
        now = self.clock()
        end = min(now, self.last_touch + self.idle)
        if self.focused and end > self.last_tick:
            begin = self.last_tick
            if self.intervals and abs(self.intervals[-1][1]-begin) < .001:
                self.intervals[-1][1] = end
            else:
                self.intervals.append([begin, end])
            self.row['last_active_at'] = self.at(end)
        self.last_tick = now
        self.row['active_seconds'] = sum(b-a for a, b in self.intervals)
        self.row['active_intervals'] = [[self.at(a), self.at(b)] for a, b in self.intervals]
        return dict(self.row)

    def touch(self):
        self.tick()
        if not self.closed:
            self.last_touch = self.clock()

    def focus(self, focused):
        self.tick()
        self.focused = focused
        if focused:
            self.last_touch = self.clock()

    def close(self):
        if self.closed:
            return dict(self.row)
        self.tick()
        self.closed = True
        self.row['ended_at'] = self.at(self.clock())
        return dict(self.row)


class Participation:
    """Durable absolute session snapshots; retry never adds duplicate duration."""
    def __init__(self, accounts):
        self.accounts = accounts
        store = accounts.store
        self.path = store.project_data('logs/outboxes/' + accounts.install_id + '/sessions.json') if store.shared_index else store.local_dir / 'pending_sessions.local.json'
        self.pending = read_json(self.path, {})
        self.session = ActiveSession(accounts.profile['id'], accounts.install_id)
        self.persist()

    def persist(self, close=False):
        row = self.session.close() if close else self.session.tick()
        with self.accounts.lock:
            self.pending[row['id']] = row
            write_json(self.path, self.pending)
            if getattr(self.accounts, 'local_identity', False):
                self.accounts.publish_session(row)
            if self.accounts.store.shared_index:
                write_json(self.accounts.store.project_data('logs/sessions') / (row['id'] + '.json'), row)
        return row

    def flush(self):
        return self.accounts.flush()


def fetch_pages(accounts, table, filters=()):
    if table == 'activity_events':
        return accounts.rows('Events')
    if table == 'user_sessions':
        return accounts.rows('Sessions')
    from app.services.local_meetings import meeting_rows
    meetings = meeting_rows(accounts)
    if table == 'meetings':
        return meetings
    if table in ('meeting_attendees', 'meeting_actions'):
        key = 'attendees' if table == 'meeting_attendees' else 'actions'
        return [dict(row, meeting_id=m['id']) for m in meetings for row in m.get(key, [])]
    raise ValueError('Unsupported local activity collection.')

def default_week(now=None):
    now = now or datetime.now().astimezone()
    monday = now.date() - timedelta(days=now.weekday())
    return monday, monday + timedelta(days=7)


def union_seconds(intervals, begin, end):
    clipped = sorted((max(instant(a), begin), min(instant(b), end)) for a, b in intervals
                     if instant(b) > begin and instant(a) < end)
    merged = []
    for a, b in clipped:
        if a >= b:
            continue
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(b, merged[-1][1])
        else:
            merged.append([a, b])
    return sum((b-a).total_seconds() for a, b in merged)


def aggregate(person, begin, end, events, sessions, attendance, meetings):
    """Filter again by owner even when admin loads an entire team period."""
    identity = person['id']
    events = [e for e in events if e['user_id'] == identity and begin <= instant(e['created_at']) < end]
    # Client event ids are the idempotency key, including pending local events.
    unique = {}
    for event in events:
        unique[event.get('client_event_id') or str(event['id'])] = event
    events = sorted(unique.values(), key=lambda e: e['created_at'])
    sessions = {s['id']: s for s in sessions if s['user_id'] == identity and
                instant(s['started_at']) < end and instant(s.get('ended_at') or s['last_active_at']) >= begin}
    counts = {}
    for e in events:
        counts[e['event_type']] = counts.get(e['event_type'], 0) + 1
    related = {kind: {} for kind in ('sample', 'experiment')}
    for e in events:
        for kind in related:
            key = e['entity_id'] if e.get('entity_type') == kind else e.get('details', {}).get(kind + '_id')
            if key:
                related[kind][key] = related[kind].get(key, 0) + 1
    eligible = {m['id']: m for m in meetings if begin.date() <= datetime.fromisoformat(m['meeting_date']).date() < end.date()}
    records = {r['meeting_id']: r for r in attendance if r.get('user_id') == identity and
               r['meeting_id'] in eligible and r.get('attendance_status') != 'Excused'}
    attended = sum(bool(r['attended']) for r in records.values())
    opened = [e for e in events if e['event_type'] == 'FILE_OPENED']
    added = [e for e in events if e['event_type'] == 'FILE_ADDED' and e.get('details', {}).get('attribution') == 'app_user_action']
    metrics = {'Logins': counts.get('LOGIN', 0), 'Sessions': len(sessions),
               'Procedure revisions': counts.get('PROCEDURE_UPDATED', 0),
               'Image processing runs completed': counts.get('IMAGE_PROCESSED', 0),
               'Reliability errors': sum(n for k, n in counts.items() if k.endswith(('_FAILED', '_ERROR'))),
               'Active time': format_duration(union_seconds([i for s in sessions.values() for i in s.get('active_intervals', [])], begin, end)),
               'Files added (known attribution)': len(added), 'Files opened': len(opened),
               'Current files opened': sum(e.get('details', {}).get('source') == 'current' for e in opened),
               'Legacy files opened': sum(e.get('details', {}).get('source') == 'legacy' for e in opened),
               'Unique samples worked with': len(related['sample']), 'Unique experiments worked with': len(related['experiment']),
               'Samples viewed': counts.get('SAMPLE_VIEWED', 0), 'Samples updated': counts.get('SAMPLE_UPDATED', 0),
               'Experiments viewed': counts.get('EXPERIMENT_VIEWED', 0), 'Experiments created': counts.get('EXPERIMENT_CREATED', 0),
               'Experiments updated': counts.get('EXPERIMENT_UPDATED', 0), 'Images viewed': counts.get('IMAGE_VIEWED', 0),
               'Reports opened': counts.get('REPORT_OPENED', 0),
               'Data files opened': sum(e.get('details', {}).get('file_category') == 'Data' for e in opened),
               'Images added': sum(e.get('details', {}).get('file_category') == 'Images' for e in added),
               'Reports added': sum(e.get('details', {}).get('file_category') == 'Reports' for e in added),
               'Data files added': sum(e.get('details', {}).get('file_category') == 'Data' for e in added),
               'Meetings attended': attended, 'Meetings explicitly missed': len(records)-attended,
               'Attendance': f'{attended} / {len(records)} ({attended / len(records):.0%})' if records else 'Not recorded',
               'Meeting notes edited': counts.get('MEETING_NOTES_EDITED', 0),
               'Transcripts edited': counts.get('TRANSCRIPT_EDITED', 0),
               'Action items completed': counts.get('ACTION_ITEM_COMPLETED', 0)}
    for category in ('Original', 'Overlay', 'Pore Map', 'Outline'):
        metrics[category + ' images added'] = sum(e.get('details', {}).get('image_category') == category or
            e.get('details', {}).get('image_subcategory') == category.replace(' ', '') for e in added)
    logins = [e['created_at'] for e in events if e['event_type'] == 'LOGIN']
    metrics['First login'] = logins[0] if logins else 'Not recorded'
    metrics['Last activity'] = events[-1]['created_at'] if events else 'Not recorded'
    name = person.get('display_name') or person.get('email') or identity
    summary = f'{name} recorded {metrics["Active time"]} of active Hub use across {len(sessions)} sessions, opened {len(opened)} files, added {len(added)} attributed files, and attended {attended} explicitly recorded meetings.'
    sample_names={e['entity_id']:e.get('entity_name') or e['entity_id'] for e in events if e.get('entity_type')=='sample'}
    sample_names.update({e.get('details',{}).get('sample_id'):e['details']['sample_name'] for e in events if e.get('details',{}).get('sample_name')})
    active_seconds = union_seconds([i for s in sessions.values() for i in s.get('active_intervals', [])], begin, end)
    session_seconds = union_seconds([[s['started_at'], s.get('ended_at') or s['last_active_at']] for s in sessions.values()], begin, end)
    metrics['Estimated session duration'] = format_duration(session_seconds)
    return dict(person=name, user_id=identity, begin=begin.isoformat(), end=end.isoformat(), metrics=metrics,
                active_seconds=active_seconds, session_seconds=session_seconds,
                summary=summary, samples=related['sample'], experiments=related['experiment'], events=events,
                sample_names=sample_names,
                attendance=[dict(r, title=eligible[r['meeting_id']]['title']) for r in records.values()],
                limitations='This report covers recorded activity available in this edition. Earlier hosted history is preserved separately. Externally discovered files have unknown attribution. Attendance excludes Excused entries. Usage measures recorded actions, not engineering value.')


class WeeklyReports:
    def __init__(self, accounts):
        self.accounts = accounts

    def roster(self):
        return self.accounts.roster()

    def load(self, person, begin, end):
        a = self.accounts
        if person['id'] != a.profile['id'] and not a.admin_unlocked:
            raise ValueError('You can view your own weekly activity.')
        events = fetch_pages(a, 'activity_events', [('user_id', 'eq.' + person['id']), ('created_at', 'gte.' + utc_text(begin)), ('created_at', 'lt.' + utc_text(end))])
        sessions = fetch_pages(a, 'user_sessions', [('user_id', 'eq.' + person['id']), ('started_at', 'lt.' + utc_text(end)), ('last_active_at', 'gte.' + utc_text(begin))])
        meetings = fetch_pages(a, 'meetings', [('meeting_date', 'gte.' + begin.date().isoformat()), ('meeting_date', 'lt.' + end.date().isoformat())])
        attendance = fetch_pages(a, 'meeting_attendees', [('user_id', 'eq.' + person['id'])])
        # Include this user's durable pending snapshots without crediting others.
        with a.lock:
            events += [dict(e, id=e.get('client_event_id', str(n))) for n, e in enumerate(a.pending) if e['user_id'] == person['id']]
            participation = getattr(a, 'participation', None)
            if participation:
                pending = participation.pending
                sessions = [s for s in sessions if s['id'] not in pending] + list(pending.values())
        return aggregate(person, begin, end, events, sessions, attendance, meetings)


def combined_report(reports):
    if not reports:
        raise ValueError('Generate individual reports for this period first.')
    result = dict(reports[0], person='Combined team report', user_id='team', samples={}, experiments={}, sample_names={})
    result['metrics'] = {key: sum(r['metrics'][key] for r in reports) for key, value in reports[0]['metrics'].items()
                         if isinstance(value, (int, float)) and key not in ('Unique samples worked with', 'Unique experiments worked with')}
    for kind in ('samples', 'experiments'):
        for r in reports:
            for identity, count in r[kind].items():
                result[kind][identity] = result[kind].get(identity, 0) + count
        result['metrics']['Unique ' + kind + ' worked with'] = len(result[kind])
    result['metrics']['Active time'] = format_duration(sum(r['active_seconds'] for r in reports))
    result['metrics']['Estimated session duration'] = format_duration(sum(r['session_seconds'] for r in reports))
    events = {e['client_event_id']: e for r in reports for e in r['events']}
    result['events'] = sorted(events.values(), key=lambda e: e['created_at'])
    result['metrics']['First login'] = min((r['metrics']['First login'] for r in reports if r['metrics']['First login'] != 'Not recorded'), default='Not recorded')
    result['metrics']['Last activity'] = result['events'][-1]['created_at'] if result['events'] else 'Not recorded'
    result['metrics']['Attendance'] = 'See per-user reports; attendance totals count person-meetings.'
    result['attendance'] = [dict(a, title=r['person'] + ': ' + a['title']) for r in reports for a in r['attendance']]
    result['summary'] = 'Combined measured activity for ' + str(len(reports)) + ' team members. ' + '; '.join(r['person'] + ': ' + r['metrics']['Active time'] for r in reports)
    return result


def report_html(report):
    esc = lambda v: html.escape(str(v))
    metrics = ''.join('<tr><td>' + esc(k) + '</td><td>' + esc(v) + '</td></tr>' for k, v in report['metrics'].items())
    timeline = {}
    for e in report['events']:
        day = e['created_at'][:10]
        key = (day, e['event_type'], e.get('entity_name') or '')
        timeline[key] = timeline.get(key, 0) + 1
    items = ''.join('<li>' + esc(f'{d} · {t.replace("_", " ").title()} · {n} ({count})') + '</li>' for (d, t, n), count in list(timeline.items())[:150])
    samples = ''.join('<li>' + esc(f'{report.get("sample_names",{}).get(k,k)}: {v} actions') + '</li>' for k, v in sorted(report['samples'].items(), key=lambda pair: -pair[1])[:10])
    meetings = ''.join('<li>' + esc(r['title'] + ' · ' + r['attendance_status']) + '</li>' for r in report['attendance'])
    return '<html><head><style>body{font-family:Arial;font-size:10pt;color:#173044}h1{font-size:20pt}h2{margin-top:20px;color:#12665e}td{padding:4px 14px 4px 0}li{margin:4px}</style></head><body><h1>GDL Research Hub</h1><h2>Weekly Contribution Report</h2><p><b>' + esc(report['person']) + '</b><br>' + esc(report['begin'][:10]) + ' through ' + esc(report['end'][:10]) + ' (end exclusive)</p><p>' + esc(report['summary']) + '</p><h2>Usage, research and meetings</h2><table>' + metrics + '</table><h2>Top samples</h2><ul>' + samples + '</ul><h2>Recorded attendance</h2><ul>' + meetings + '</ul><h2>Activity timeline</h2><ul>' + items + '</ul><p>' + esc(report['limitations']) + '</p></body></html>'


def export_pdf(report, path, store=None):
    if store:
        path = store.validate_project_output(path)
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    styles=getSampleStyleSheet()
    styles['Heading1'].textColor=colors.HexColor('#12665e')
    styles['BodyText'].spaceAfter=8
    esc=lambda value:html.escape(str(value))
    doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=48,bottomMargin=48,
                          title='Weekly Contribution Report - '+report['person'],author='GDL Research Hub')
    story=[Paragraph('GDL Research Hub',styles['Title']),Paragraph('Weekly Contribution Report',styles['Heading1']),
           Paragraph(esc(report['person']),styles['Heading2']),
           Paragraph(esc(report['begin'][:10]+' through '+report['end'][:10]+' (end exclusive)'),styles['BodyText']),
           Paragraph(esc(report['summary']),styles['BodyText'])]
    usage=('Logins','Sessions','Active time','Estimated session duration','First login','Last activity')
    def display_metric(key):
        value = report['metrics'][key]
        if key in ('First login', 'Last activity') and value != 'Not recorded':
            return instant(value).strftime('%Y-%m-%d %H:%M UTC')
        return value
    meeting=('Meetings attended','Meetings explicitly missed','Attendance','Meeting notes edited','Transcripts edited','Action items completed')
    for title,keys in [('Application usage',usage),('Research activity',[k for k in report['metrics'] if k not in usage+meeting]),('Meetings',meeting)]:
        rows=[[Paragraph(esc(k),styles['BodyText']),Paragraph(esc(display_metric(k)),styles['BodyText'])] for k in keys]
        table=Table(rows,colWidths=[330,170],hAlign='LEFT')
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),12),
            ('BOTTOMPADDING',(0,0),(-1,-1),4),('LINEBELOW',(0,0),(-1,-1),.25,colors.HexColor('#e4e9ed'))]))
        story += [Spacer(1,8),Paragraph(title,styles['Heading2']),table]
    story += [Spacer(1,10),Paragraph('Top samples',styles['Heading2'])]
    for key,count in sorted(report['samples'].items(),key=lambda item:-item[1])[:10]:
        story.append(Paragraph(esc(f'{report.get("sample_names",{}).get(key,key)}: {count} actions'),styles['BodyText']))
    if not report['samples']:story.append(Paragraph('No sample activity recorded.',styles['BodyText']))
    story.append(Paragraph('Recorded attendance',styles['Heading2']))
    for row in report['attendance']:story.append(Paragraph(esc(row['title']+' - '+row['attendance_status']),styles['BodyText']))
    if not report['attendance']:story.append(Paragraph('No attendance recorded for this period.',styles['BodyText']))
    timeline={}
    for e in report['events']:
        key=(e['created_at'][:10],e['event_type'],e.get('entity_name') or '')
        timeline[key]=timeline.get(key,0)+1
    story.append(Paragraph('Activity timeline (UTC dates)',styles['Heading2']))
    for (day,kind,name),count in list(timeline.items())[:150]:
        story.append(Paragraph(esc(f'{day} - {kind.replace("_"," ").title()} - {name} ({count})'),styles['BodyText']))
    if len(timeline)>150:story.append(Paragraph('First 150 grouped activities shown; all records are included in the totals.',styles['BodyText']))
    story += [Spacer(1,12),Paragraph(esc(report['limitations']),styles['BodyText'])]
    def footer(canvas,document):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#52616e'))
        canvas.drawString(44,25,'GDL Research Hub - '+report['begin'][:10]);canvas.drawRightString(A4[0]-44,25,f'Page {document.page}');canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)


def export_csv(report, path, store=None):
    if store:
        path = store.validate_project_output(path)
    with open(path, 'w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Person', 'Period start', 'Period end (exclusive)', 'Metric', 'Value'])
        for key, value in report['metrics'].items():
            # Spreadsheet formula injection must not turn names into executable cells.
            safe = lambda v: "'" + str(v) if str(v).startswith(('=', '+', '-', '@')) else str(v)
            writer.writerow([safe(report['person']), report['begin'][:10], report['end'][:10], key, safe(value)])
