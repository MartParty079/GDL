"""Representative records, confined to a fresh explicit local sandbox."""
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4
from app.services.storage import Store
from app.services.local_accounts import LocalAccounts
from app.services.organization import Organization


def create_fixture(base, role='member'):
    base = Path(base).resolve()
    # Never accept an arbitrary shared root or an existing profile as input.
    profile = base / ('fixture-' + uuid4().hex) / 'profile'
    store = Store(local_dir=profile)
    accounts = LocalAccounts(store); store.accounts = accounts
    accounts.setup_admin('246810')
    admin, member = accounts.users()[:2]
    accounts.sign_in(admin['id'], '246810')
    accounts.manage_user(member['id'], new_pin='135790')
    service = Organization(store); service.root.mkdir(parents=True, exist_ok=True)
    service.initialize()
    def record(kind, title, **fields):
        key = service.submit(kind, title, fields); service.consume(); return key
    today = date.today(); due = (today + timedelta(days=13)).isoformat()
    period = record('period', 'Repeatability and fixture review', start_date=today.isoformat(),
                    end_date=due, due_at=due + 'T17:00:00-05:00')
    sample = record('sample', 'Carbon paper reference coupon', aliases=['Holy GDL'],
                    nominal_thickness='0.190', units='mm', new_used_state='New')
    record('sample', 'Prior-year reference', aliases=['1344 Pascal'])
    procedure = record('procedure', 'Microscope calibration and capture',
                       instructions='Record illumination and scale calibration. Preserve the original raw capture.',
                       approval_status='Approved')
    experiment = record('experiment', 'Surface imaging repeatability', procedure_uuid=procedure,
                        procedure_revision=1, sample_uuids=[sample], active_experiment='Yes',
                        apparatus_settings='Fixed illumination · calibration pending', units='µm / pixel')
    goal = record('goal', 'Establish a repeatable imaging baseline', owner_id=member['id'],
                  due_date=due, output='Reviewed reference capture and traceable procedure',
                  next_step='Verify calibration before comparing pore maps', status='In Progress',
                  active_goal='Yes', period_uuid=period)
    meeting = record('meeting', 'Repeatability review and fixture planning', created_at=today.isoformat(),
                     meeting_time='14:00 America/Chicago', facilitator_id=admin['id'],
                     note_taker_id=member['id'], agenda='Review calibration evidence\nAgree fixture requirements',
                     minutes='Reference capture prepared. Calibration review is pending.', stage='agenda',
                     period_uuid=period, attendees=[admin['id'], member['id']])
    task = record('task', 'Review scale calibration', owner_id=member['id'], due_date=due,
                  acceptance='Reviewed calibration image with explicit units', status='active',
                  meeting_uuid=meeting, goal_uuid=goal, period_uuid=period)
    record('task', 'Confirm fixture alignment requirements', owner_id=admin['id'], due_date=due,
           acceptance='Documented alignment constraints', status='planned', goal_uuid=goal, period_uuid=period)
    record('research', 'Surface and bulk porosity comparison', research_section='Literature_Reviews_and_Comparisons')
    record('design', 'Microscope alignment fixture', design_section='CAD_and_Drawings', prototype_status='Draft')
    accounts.sign_out(); accounts.sign_in(member['id'], '135790')
    member_service = Organization(store)
    submission = member_service.submit('deliverable', 'Reference capture preparation',
        dict(owner_id=member['id'], period_uuid=period, work_completed='Prepared the reference imaging procedure.',
             next_plan='Review calibration evidence.', submission_status='Submitted', evidence_uuids=[sample, experiment]))
    accounts.sign_out(); accounts.sign_in(admin['id'], '246810'); service.consume()
    accounts.sign_out()
    accounts.sign_in(admin['id'] if role == 'admin' else member['id'], '246810' if role == 'admin' else '135790')
    assert service.root.resolve().is_relative_to(profile.resolve())
    return store, accounts, dict(sample=sample, procedure=procedure, experiment=experiment,
                                 goal=goal, task=task, meeting=meeting, period=period, submission=submission)
