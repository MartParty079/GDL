"""Two real local identities, review policy, intake recovery and Home navigation."""
import copy
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from tests import test_organization as fixtures
from app.services.organization import Organization, digest
from app.services.intake import Intake
from app.services.team_workflow import (ensure_workspaces, workspace_relative, user_code,
    period_status, digest_text, draft_summary)


class TeamWorkflowTests(unittest.TestCase):
    setUp = fixtures.OrganizationTests.setUp
    tearDown = fixtures.OrganizationTests.tearDown
    client = fixtures.OrganizationTests.client
    create = fixtures.OrganizationTests.create

    def period(self, begin='2026-10-05', end='2026-10-18', due='2026-10-19T17:00:00-05:00'):
        return self.create('period', 'Two-week report', {'start_date': begin, 'end_date': end, 'due_at': due})

    def deliverable(self, member, period, status='Draft'):
        return self.create('deliverable', 'Progress', {'period_uuid': period, 'owner_id': member.actor['user_id'],
                           'submission_status': status, 'work_completed': 'Reviewed microscope calibration.', 'next_plan': 'Repeat the reference capture.'}, member)

    def test_periods_exact_fourteen_days_no_overlap_no_fixed_cutoff(self):
        first = self.period()
        second = self.period('2026-10-19', '2026-11-01', '2026-11-03T09:15:00-06:00')
        self.assertNotEqual(first, second)
        for fields in ({'start_date': '2026-10-06', 'end_date': '2026-10-19', 'due_at': '2026-10-20T12:00:00Z'},
                       {'start_date': '2026-11-02', 'end_date': '2026-11-10', 'due_at': '2026-11-11T12:00:00Z'},
                       {'start_date': '2026-11-02', 'end_date': '2026-11-15', 'due_at': '2026-11-15T12:00:00'}):
            key = self.admin.submit('period', 'Invalid period', fields); self.admin.consume()
            self.assertNotIn(key, self.admin.state['records'])
        member = self.client('member1')
        key = member.submit('period', 'Unauthorized', {'start_date': '2026-11-02', 'end_date': '2026-11-15', 'due_at': '2026-11-16T12:00:00Z'})
        self.admin.consume(); self.assertNotIn(key, self.admin.state['records'])

    def test_workspace_identity_survives_rename_and_future_user_allocation(self):
        mapping = ensure_workspaces(self.admin)
        people = self.admin.accounts.registry['users']
        first, second = people[:2]
        self.assertEqual(user_code(self.admin, first['id']), 'U0001')
        self.assertEqual(user_code(self.admin, second['id']), 'U0002')
        before = workspace_relative(self.admin, second['id'])
        self.assertTrue(self.admin.safe(before).is_dir())
        self.admin.accounts.manage_user(second['id'], name='Renamed team member')
        ensure_workspaces(self.admin)
        self.assertEqual(workspace_relative(self.admin, second['id']), before)
        self.assertTrue(self.admin.safe('_Team_Workspaces/U0005_Unassigned').is_dir())
        self.admin.accounts.manage_user(name='Fifth member fixture'); ensure_workspaces(self.admin)
        fifth = self.admin.accounts.registry['users'][-1]
        self.assertEqual(user_code(self.admin, fifth['id']), 'U0005')
        self.assertTrue(self.admin.safe(workspace_relative(self.admin, fifth['id'])).is_dir())

    def test_submission_review_feedback_resubmission_acceptance_lock_addendum(self):
        period = self.period(); member = self.client('member1')
        key = self.deliverable(member, period)
        original = copy.deepcopy(self.admin.state['records'][key])
        self.assertIn('_Team_Workspaces/', original['relative_path'])
        def update(client, status, **extra):
            client.refresh(); record = client.state['records'][key]; fields = dict(record['fields'], submission_status=status, **extra)
            client.submit('deliverable', record['title'], fields, key, 'Workflow transition'); self.admin.consume(); client.refresh()
        update(member, 'Submitted')
        update(member, 'Accepted', reviewer_id=member.actor['user_id'])
        self.assertEqual(self.admin.state['records'][key]['fields']['submission_status'], 'Submitted')
        update(self.admin, 'Under Review', reviewer_id=self.admin.actor['user_id'])
        update(self.admin, 'Changes Requested', reviewer_id=self.admin.actor['user_id'], feedback='Attach reference procedure.')
        update(member, 'Resubmitted')
        update(self.admin, 'Under Review', reviewer_id=self.admin.actor['user_id'])
        update(self.admin, 'Accepted', reviewer_id=self.admin.actor['user_id'])
        accepted = copy.deepcopy(self.admin.state['records'][key])
        self.assertIn('Biweekly_Deliverables/BW0001/U0002', accepted['relative_path'])
        self.assertEqual(accepted['created_by_user_id'], member.actor['user_id'])
        self.assertTrue(accepted['fields']['reviewed_at'])
        update(member, 'Draft', work_completed='Rewrite accepted history')
        self.assertEqual(self.admin.state['records'][key], accepted)
        member.refresh()
        add = dict(accepted['fields'], submission_status='Draft', addendum_to=key, work_completed='Additional repeatability evidence.')
        extra = self.create('deliverable', 'Addendum', add, member)
        self.assertNotEqual(extra, key)
        self.assertIn('Accepted', digest_text(self.admin, self.admin.state['records'][period]))

    def test_deadline_states_not_missing_before_configured_due(self):
        key = self.period(); member = self.client('member1'); period = member.state['records'][key]
        owner = member.actor['user_id']
        self.assertEqual(period_status(member, period, owner, datetime(2026, 10, 6, tzinfo=timezone.utc)), 'Not started')
        self.assertIn('Due Soon', period_status(member, period, owner, datetime(2026, 10, 18, tzinfo=timezone.utc)))
        self.assertIn('Overdue', period_status(member, period, owner, datetime(2026, 10, 21, tzinfo=timezone.utc)))
        self.deliverable(member, key, 'Submitted'); member.refresh()
        self.assertEqual(period_status(member, period, owner, datetime(2026, 10, 21, tzinfo=timezone.utc)), 'Submitted')

    def test_review_cannot_change_contributor_content_or_spoof_reviewer(self):
        period = self.period(); member = self.client('member1'); key = self.deliverable(member, period, 'Submitted')
        before = copy.deepcopy(self.admin.state['records'][key])
        for changes in ({'work_completed': 'Fabricated work', 'reviewer_id': self.admin.actor['user_id']}, {'reviewer_id': member.actor['user_id']}):
            fields = dict(before['fields'], submission_status='Under Review', **changes)
            self.admin.submit('deliverable', before['title'], fields, key, 'Review'); self.admin.consume()
            self.assertEqual(self.admin.state['records'][key], before)

    def test_intake_batch_preview_errors_retry_cancel_preserves_sources(self):
        member = self.client('member1'); files = []
        for name in ('raw.tif', 'reference.pdf', 'notes.docx', 'part.sldprt', 'print.3mf'):
            file = self.base / name; file.write_bytes(name.encode()); files.append(file)
        queue = Intake(member); queue.add(files)
        previews = [queue.preview(r) for r in queue.rows]
        self.assertTrue(all(p['proposed'].startswith(datetime.now().date().isoformat()) for p in previews))
        self.assertTrue(all(p['creator'] == member.actor['display_name'] for p in previews))
        queue.rows[1]['source'] = str(self.base / 'not-downloaded.pdf')
        queue.apply(); self.admin.consume(); member.refresh()
        self.assertEqual(sum(r['status'] == 'Queued' for r in queue.rows), 4)
        self.assertEqual(queue.rows[1]['status'], 'Needs attention')
        queue.rows[1]['source'] = str(files[1]); queue.apply(); self.admin.consume(); member.refresh()
        self.assertEqual(len(member.rows(kind='file')), 5)
        self.assertTrue(all(path.exists() and path.read_bytes() == path.name.encode() for path in files))
        restarted = Intake(member); restarted.apply(); self.admin.consume()
        self.assertEqual(len(self.admin.rows(kind='file')), 5)
        queue.add([self.base / 'cancelled.png']); queue.apply(cancelled=lambda: True)
        self.assertEqual(queue.rows[-1]['status'], 'Ready')

    def test_workspace_publication_same_uuid_creator_checksum_no_authoritative_duplicates(self):
        member = self.client('member1'); source = self.base / 'draft.pdf'; source.write_bytes(b'workspace fixture')
        key = member.upload(source, 'Design draft', {'workspace_owner_id': member.actor['user_id']})
        self.admin.consume(); member.refresh(); record = member.state['records'][key]; old_path = self.admin.safe(record['relative_path'])
        self.assertIn('_Team_Workspaces/U0002', record['relative_path'])
        fields = dict(record['fields'], destination_category='Design & Prototyping', publish_workspace='Yes'); fields.pop('workspace_owner_id')
        member.submit('file', record['title'], fields, key, 'Confirmed project publication'); self.admin.consume()
        moved = self.admin.state['records'][key]
        self.assertTrue(moved['relative_path'].startswith('04_Design_and_Prototyping/'))
        self.assertEqual(moved['created_by_user_id'], record['created_by_user_id'])
        self.assertEqual(moved['checksum'], digest(source)); self.assertFalse(old_path.exists()); self.assertTrue(source.exists())
        self.assertEqual(len(self.admin.rows(kind='file')), 1)

    def test_meeting_recording_requires_consent_summary_preserves_notes_actions(self):
        member = self.client('member1'); owner = member.actor['user_id']
        meeting = self.create('meeting', 'Planning', {'facilitator_id': owner, 'minutes': 'Reviewed microscope repeatability. Agreed to capture a reference sample.', 'attendees': [owner]}, member)
        task = self.create('task', 'Reference capture', {'owner_id': owner, 'meeting_uuid': meeting, 'due_date': '2026-10-20', 'acceptance': 'Raw image and calibration evidence'}, member)
        member.refresh(); row = member.state['records'][meeting]
        summary = draft_summary(member, row)
        self.assertIn('T0001', summary); self.assertIn('DRAFT', summary)
        invalid = dict(row['fields'], recording_path='03_Meetings_and_Goals/recording.wav')
        with self.assertRaises(ValueError): member._validate_fields('meeting', invalid, member.state['records'])
        f = dict(row['fields'], summary=summary, summary_approved='Yes', summary_reviewed_by_id=owner)
        member.submit('meeting', row['title'], f, meeting, 'Lead reviewed draft'); self.admin.consume()
        approved = self.admin.state['records'][meeting]
        self.assertEqual(approved['fields']['minutes'], row['fields']['minutes'])
        self.assertTrue(approved['fields']['summary_approved_at'])
        next_meeting = self.create('meeting', 'Next agenda', {}, member)
        self.assertIn(task, self.admin.state['records'][next_meeting]['fields']['carried_actions'])

    def test_goal_task_deliverable_share_canonical_references(self):
        period = self.period(); owner = self.admin.actor['user_id']
        goal = self.create('goal', 'Repeatability', {'owner_id': owner, 'due_date': '2026-10-18', 'output': 'Reference evidence', 'active_goal': 'Yes', 'period_uuid': period})
        task = self.create('task', 'Capture reference', {'owner_id': owner, 'due_date': '2026-10-15', 'acceptance': 'TIF + settings', 'goal_uuid': goal, 'period_uuid': period})
        report = digest_text(self.admin, self.admin.state['records'][period])
        self.assertIn(self.admin.state['records'][goal]['id'], report); self.assertIn(self.admin.state['records'][task]['id'], report)
        self.assertNotIn('%', report)

    def test_two_pin_accounts_cross_user_revision_keeps_creator(self):
        first, second = self.client('member1'), self.client('member2')
        writer = self.admin.accounts
        writer.manage_user(first.actor['user_id'], new_pin='2468')
        writer.manage_user(second.actor['user_id'], new_pin='8642')
        first.accounts.refresh(); second.accounts.refresh()
        first.accounts.sign_out(); first.accounts.sign_in(first.accounts.users()[1]['id'], '2468')
        second.accounts.sign_out(); second.accounts.sign_in(second.accounts.users()[2]['id'], '8642')
        key = self.create('sample', 'Creator fixture', {}, first)
        second.refresh(); second.submit('sample', 'Cross-user correction', {}, key, 'Verified specs'); self.admin.consume()
        row = self.admin.state['records'][key]
        self.assertEqual(row['created_by_user_id'], first.actor['user_id']); self.assertEqual(row['last_modified_by_user_id'], second.actor['user_id'])
        self.assertEqual(row['created_by_verification'], 'Local PIN')

    def test_home_member_four_categories_full_navigation_and_settings(self):
        from PySide6.QtWidgets import QApplication
        from app.ui.window import HubWindow
        from app.ui.local_accounts import attach_account_ui
        app = QApplication.instance() or QApplication([])
        member = self.client('member1')
        from app.services.project_locations import ProjectLocations
        member.store.local.pop('project_locations')
        locations = ProjectLocations(member.store).defaults(); locations.update(enabled=False, shared_storage=str(self.root), legacy=[])
        locations['active']['root_path'] = str(self.root)
        member.store.local['project_locations'] = locations
        with patch('app.ui.window.QTimer.singleShot'):
            window = HubWindow(member.store)
        attach_account_ui(window, member.accounts, lambda: None)
        window.show(); app.processEvents()
        if not window.storage_settings.catalog: self.assertTrue(window.research_workspace.isHidden())
        self.assertIs(window.tabs.currentWidget(), window.home_panel)
        self.assertEqual(len(window.home_panel.category_buttons), 4)
        from app.ui.home import SUBMENUS
        for category, entries in SUBMENUS.items():
            window.home_panel.navigate(category)
            labels = [window.organization_panel.subsection.itemText(i) for i in range(window.organization_panel.subsection.count())]
            self.assertTrue(all(entry[0] in labels for entry in entries))
        self.assertIn('Current Goal', window.home_panel.cards)
        self.assertFalse(hasattr(window, 'admin_workspace'))
        window.session_presence.stop(); window.account_timer.stop()
        # Drain report workers before destroying their QThreads.
        import time
        deadline = time.monotonic() + 20
        while window.weekly_panel.tasks.busy() or window.meetings_panel.busy():
            app.processEvents(); time.sleep(.01)
            if time.monotonic() > deadline: self.fail('Report workers did not settle')
        app.processEvents()
        window.close(); window.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete); app.processEvents()

    def test_semester_anchor_generates_consecutive_periods_validates_all_first(self):
        from app.services.team_workflow import configure_periods
        keys = configure_periods(self.admin, '2026-10-05', 3, '2026-10-20T11:30:00-05:00')
        self.admin.consume()
        periods = sorted((self.admin.state['records'][key] for key in keys), key=lambda r: r['fields']['start_date'])
        self.assertEqual([r['fields']['start_date'] for r in periods], ['2026-10-05', '2026-10-19', '2026-11-02'])
        self.assertTrue(periods[1]['fields']['due_at'].startswith('2026-11-03T11:30:00'))
        before = len(self.admin.pending())
        with self.assertRaises(ValueError): configure_periods(self.admin, '2026-09-21', 3, '2026-10-06T11:30:00-05:00')
        self.assertEqual(len(self.admin.pending()), before)

    def test_legacy_review_links_five_samples_known_images_without_modifying_originals(self):
        folder = self.root / 'Previous Research'; folder.mkdir()
        for n in range(5): (folder / f'sample-{n}.txt').write_text('Legacy fixture', encoding='utf-8')
        for name in ('Holy GDL', '1344 Pascal'):
            for state in ('raw', 'poremap', 'overlay', 'outline'):
                (folder / (name + ' ' + state + '.png')).write_bytes((name + state).encode())
        before = {p.name: digest(p) for p in folder.iterdir()}
        self.admin.import_inventory(self.admin.inventory())
        samples = self.admin.rows(kind='sample'); self.assertEqual(len(samples), 5)
        for i, name in enumerate(('Holy GDL', '1344 Pascal')):
            images = [r for r in self.admin.rows(query=name) if r.get('legacy')]
            raw = next(r for r in images if r['fields']['file_state'] == 'raw')
            derived = [r['uuid'] for r in images if r['fields']['file_state'] in ('poremap', 'overlay', 'outline')]
            self.admin.link_legacy_images(samples[i]['uuid'], raw['uuid'], derived, 'Reviewed representative original/derived filenames and correspondence')
            for key in derived:
                row = self.admin.state['records'][key]
                self.assertEqual(row['fields']['parent_file_uuid'], raw['uuid'])
                self.assertIsNone(row['created_by_user_id'])
                self.assertIn('Unknown legacy run', row['fields']['processing_run_provenance'])
        self.assertEqual(before, {p.name: digest(p) for p in folder.iterdir()})

    def test_recording_upload_needs_explicit_consent_and_verified_meeting_link(self):
        member = self.client('member1'); meeting = self.create('meeting', 'Recorded discussion', {}, member)
        source = self.base / 'recording.wav'; source.write_bytes(b'representative recording')
        with self.assertRaises(ValueError): member.upload(source, 'Recording', {'meeting_uuid': meeting})
        key = member.upload(source, 'Recording', {'meeting_uuid': meeting, 'recording_consent': 'Yes'})
        self.admin.consume(); member.refresh(); row = member.state['records'][meeting]
        fields = dict(row['fields'], recording_path=member.state['records'][key]['relative_path'], recording_consent='Yes')
        member.submit('meeting', row['title'], fields, meeting, 'Participants permitted storage'); self.admin.consume()
        self.assertEqual(self.admin.state['records'][meeting]['fields']['recording_path'], fields['recording_path'])

    def test_workspace_rollback_restores_source_without_losing_canonical_bytes(self):
        member = self.client('member1'); source = self.base / 'draft.txt'; source.write_text('Retain rollback bytes')
        key = member.upload(source, 'Draft', {'workspace_owner_id': member.actor['user_id']})
        self.admin.consume(); member.refresh(); old = copy.deepcopy(member.state['records'][key]); revision = self.admin.state['revision']
        fields = dict(old['fields'], destination_category='Research', publish_workspace='Yes'); fields.pop('workspace_owner_id')
        member.submit('file', old['title'], fields, key, 'Confirmed publication'); self.admin.consume()
        canonical = self.admin.safe(self.admin.state['records'][key]['relative_path'])
        self.admin.rollback(revision)
        self.assertTrue(self.admin.safe(old['relative_path']).is_file()); self.assertTrue(canonical.is_file())
        self.assertEqual(self.admin.state['records'][key]['relative_path'], old['relative_path'])

    def test_draft_review_metadata_is_not_user_fabricated_and_editor_defaults_survive(self):
        period = self.period(); member = self.client('member1')
        key = self.create('deliverable', 'Draft', {'owner_id': member.actor['user_id'], 'period_uuid': period, 'submission_status': 'Draft',
                          'reviewer_id': self.admin.actor['user_id'], 'reviewed_at': '1900-01-01', 'submitted_at': '1900-01-01'}, member)
        fields = self.admin.state['records'][key]['fields']
        self.assertNotIn('reviewer_id', fields); self.assertNotIn('reviewed_at', fields); self.assertNotIn('submitted_at', fields)
        from PySide6.QtWidgets import QApplication
        from app.ui.organization import RecordEditor
        from app.services.storage import read_json
        app = QApplication.instance() or QApplication([])
        editor = RecordEditor(member, 'file', defaults={'workspace_owner_id': member.actor['user_id'], 'destination_category': 'Research'})
        self.assertEqual(editor.values()['workspace_owner_id'], member.actor['user_id'])
        editor.close(); editor.deleteLater()
        meeting = self.create('meeting', 'Local recovery', {}, member); member.refresh()
        editor = RecordEditor(member, 'meeting', member.state['records'][meeting])
        editor.fields['minutes'].setPlainText('Recover this typed note'); editor.autosave()
        self.assertEqual(read_json(editor.draft_path, {})['fields']['minutes'], 'Recover this typed note')
        editor.close(); editor.deleteLater(); app.processEvents()

    def test_submission_artifacts_move_on_acceptance_and_partial_failure_is_transactional(self):
        period = self.period(); member = self.client('member1'); key = self.deliverable(member, period)
        source = self.base / 'progress.docx'; source.write_bytes(b'representative report')
        artifact = member.upload(source, 'Progress report', {'deliverable_uuid': key})
        self.admin.consume(); member.refresh()
        original_path = self.admin.safe(self.admin.state['records'][artifact]['relative_path'])
        self.assertIn('_Team_Workspaces/', original_path.as_posix())
        row = member.state['records'][key]
        member.submit('deliverable', row['title'], dict(row['fields'], submission_status='Submitted', evidence_uuids=[artifact]), key, 'Submit report')
        self.admin.consume(); row = self.admin.state['records'][key]
        self.admin.submit('deliverable', row['title'], dict(row['fields'], submission_status='Under Review', reviewer_id=self.admin.actor['user_id']), key, 'Review')
        self.admin.consume(); row = copy.deepcopy(self.admin.state['records'][key])
        self.admin.submit('deliverable', row['title'], dict(row['fields'], submission_status='Accepted'), key, 'Accept reviewed report')
        original_copy = self.admin._copy_once
        with patch.object(self.admin, '_copy_once', side_effect=OSError('Interrupted artifact promotion')): self.admin.consume()
        self.assertEqual(self.admin.state['records'][key], row)
        self.assertTrue(original_path.exists())
        self.admin.submit('deliverable', row['title'], dict(row['fields'], submission_status='Accepted'), key, 'Retry verified artifact promotion')
        self.admin.consume()
        accepted = self.admin.state['records'][artifact]
        self.assertIn('Biweekly_Deliverables/BW0001/U0002', accepted['relative_path'])
        self.assertTrue(self.admin.safe(accepted['relative_path']).name.startswith(accepted['created_at'][:10] + '_DEL_'))
        self.assertEqual(accepted['created_by_user_id'], member.actor['user_id']); self.assertFalse(original_path.exists())
        member.refresh()
        with self.assertRaises(ValueError): member.upload(source, 'Extra report after approval', {'deliverable_uuid': key})

    def test_archive_is_admin_only_reversible_and_retains_bytes(self):
        key = self.create('sample', 'Archive fixture'); member = self.client('member1'); record = member.state['records'][key]
        member.submit('sample', record['title'], dict(record['fields'], archived='Yes'), key, 'Not authorized')
        self.admin.consume(); self.assertNotIn('archived', self.admin.state['records'][key]['fields'])
        path = self.admin.safe(record['relative_path'])
        self.admin.submit('sample', record['title'], dict(record['fields'], archived='Yes'), key, 'Reviewed archive')
        self.admin.consume(); self.assertTrue(path.exists())
        row = self.admin.state['records'][key]
        self.admin.submit('sample', row['title'], dict(row['fields'], archived='No'), key, 'Restore visible record')
        self.admin.consume(); self.assertEqual(self.admin.state['records'][key]['fields']['archived'], 'No'); self.assertTrue(path.exists())
