"""Multi-client fixtures: immutable requests, provenance and crash-safe publication."""
import copy
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from app.services.storage import Store, read_json, write_json
from app.services.local_accounts import LocalAccounts
from app.services.organization import Organization, CATEGORIES, ROLES, filename, comparability, digest


class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'shared-fixture'; self.root.mkdir()
        self.clients = []
        self.admin = self.client('admin', admin=True)
        self.admin.initialize()

    def client(self, name, admin=False):
        store = Store(local_dir=self.base / name)
        store.local['project_locations'] = {'enabled': True, 'shared_storage': str(self.root)}
        accounts = LocalAccounts(store); store.accounts = accounts
        if admin:
            accounts.setup_admin('135790'); accounts.sign_in(accounts.users()[0]['id'], '135790')
        else:
            accounts.sign_in(accounts.users()[1 if name == 'member1' else 2]['id'])
        service = Organization(store); self.clients.append(service)
        return service

    def tearDown(self):
        for client in self.clients: client.accounts.close()
        self.temp.cleanup()

    def create(self, kind, title, fields=None, client=None):
        client = client or self.admin
        key = client.submit(kind, title, fields)
        self.admin.consume(); client.refresh()
        self.assertIn(key, self.admin.state['records'], self.admin.state['requests'])
        return key

    def test_four_categories_additive_setup_five_unassigned_roles(self):
        self.assertEqual(len(CATEGORIES), 4)
        roles = self.admin.rows(kind='role')
        self.assertEqual({r['title'] for r in roles}, set(ROLES))
        self.assertTrue(all(not r['fields']['member_id'] and not r['fields']['backup_id'] for r in roles))
        self.assertEqual(self.admin.preview()['moves'], [])
        self.assertEqual(list(self.root.rglob('*.sqlite*')), [])

    def test_member_creation_unique_ids_date_filenames_and_creator(self):
        first, second = self.client('member1'), self.client('member2')
        for kind in ('sample', 'procedure', 'experiment'):
            a = first.submit(kind, 'Team record', {'created_at': '2026-10-10'})
            b = second.submit(kind, 'Other team record', {'created_at': '2026-10-10'})
            self.assertNotIn(a, self.admin.state['records'])
            self.admin.consume(); first.refresh(); second.refresh()
            ar, br = self.admin.state['records'][a], self.admin.state['records'][b]
            self.assertNotEqual(ar['id'], br['id'])
            self.assertTrue(Path(ar['relative_path']).name.startswith('2026-10-10_'))
            self.assertTrue(self.admin.safe(ar['relative_path']).is_file())
            self.assertEqual(ar['created_by_user_id'], first.actor['user_id'])
            self.assertEqual(br['uploaded_by_user_id'], second.actor['user_id'])

    def test_edit_preserves_creator_and_creation_date_append_audit(self):
        first, second = self.client('member1'), self.client('member2')
        key = self.create('sample', 'Original', {'created_at': '2026-09-01'}, first)
        second.refresh(); second.submit('sample', 'Renamed', {'created_at': '2026-10-10'}, key, 'Verified manufacturer')
        self.admin.consume(); row = self.admin.state['records'][key]
        self.assertEqual(row['created_by_user_id'], first.actor['user_id'])
        self.assertEqual(row['last_modified_by_user_id'], second.actor['user_id'])
        self.assertEqual(row['created_at'], '2026-09-01')
        self.assertTrue(Path(row['relative_path']).name.startswith('2026-09-01_'))
        history = [r for r in self.admin.state['audit'] if r.get('record_uuid') == key]
        self.assertEqual(len(history), 2); self.assertEqual(history[-1]['prior']['title'], 'Original')
        self.assertTrue(self.admin.safe(history[-1]['prior']['relative_path']).exists())

    def test_member_cannot_scan_consume_initialize_or_assign_roles(self):
        member = self.client('member1')
        for action in (member.consume, member.inventory, member.initialize, member.reconcile):
            with self.assertRaises(ValueError): action()
        role = member.rows(kind='role')[0]
        with self.assertRaises(ValueError): member.submit('role', role['title'], {}, role['uuid'], 'Assign')

    def test_enrolled_device_required_even_for_other_admin(self):
        other = self.client('other-admin', admin=False)
        other.accounts.sign_out(); other.accounts.sign_in(other.accounts.users()[0]['id'], '135790')
        self.assertFalse(other.authority)
        with self.assertRaises(ValueError): other.consume()

    def test_two_stale_editors_no_lost_write_idempotent_receipts(self):
        first, second = self.client('member1'), self.client('member2')
        key = self.create('sample', 'Baseline')
        first.refresh(); second.refresh()
        first.submit('sample', 'Edit A', {}, key, 'A')
        second.submit('sample', 'Edit B', {}, key, 'B')
        receipts = self.admin.consume()
        self.assertEqual(sorted(r['status'] for r in receipts.values()), ['accepted', 'accepted', 'conflict'])
        revision = self.admin.state['revision']; audit = copy.deepcopy(self.admin.state['audit'])
        self.admin.consume(); self.assertEqual(self.admin.state['revision'], revision)
        self.assertEqual(self.admin.state['audit'], audit)
        self.assertEqual(self.admin.state['records'][key]['revision'], 2)

    def test_offline_queue_restart_and_member_snapshot_without_scan(self):
        member = self.client('member1')
        for client in self.clients: client.accounts.executor.submit(client.accounts.flush).result()
        moved = self.base / 'offline'; self.root.rename(moved)
        key = member.submit('sample', 'Offline sample')
        self.assertTrue(list((member.local / 'outbox').glob('*.json')))
        self.assertFalse(self.root.exists())
        member.refresh(); self.assertIn('Offline', member.status)
        again = Organization(member.store); self.assertEqual(again.state['revision'], 1)
        moved.rename(self.root); again.flush(); self.admin.consume()
        with patch.object(Organization, 'inventory', side_effect=AssertionError('Member rescanned')):
            self.assertTrue(again.refresh()); self.assertIn(key, again.state['records'])

    def test_corrupt_partial_sync_keeps_last_good_and_rollback_monotonic(self):
        key = self.create('sample', 'Keep')
        member = self.client('member1'); previous = member.state['revision']
        pointer = read_json(self.admin.control / 'published.json', {})
        snapshot = self.admin.control / pointer['snapshot']; original = snapshot.read_bytes()
        snapshot.write_text('{partial', encoding='utf-8')
        self.assertFalse(member.refresh()); self.assertIn(key, member.state['records'])
        self.assertEqual(member.state['revision'], previous)
        snapshot.write_bytes(original)
        self.admin.rollback(1)
        self.assertGreater(self.admin.state['revision'], previous)
        self.assertNotIn(key, self.admin.state['records'])
        newer = self.create('sample', 'After rollback')
        self.assertEqual(self.admin.state['records'][newer]['id'], 'S0002')
        self.assertTrue(self.admin.safe('01_Experimental/Samples/S0001').exists())

    def test_interrupted_publication_retries_materialized_record(self):
        key = self.admin.submit('sample', 'Interrupted')
        with patch.object(self.admin, '_publish', side_effect=OSError('sync interrupted')):
            with self.assertRaises(OSError): self.admin.consume()
        self.admin.consume()
        self.assertIn(key, self.admin.state['records'])

    def test_conflicted_manifest_never_adopted(self):
        member = self.client('member1')
        write_json(self.admin.control / 'published-conflicted-copy.json', {})
        self.assertFalse(member.refresh())
        with self.assertRaises(ValueError): self.admin.consume()

    def test_exact_procedure_revision_and_derived_raw_traceability(self):
        member = self.client('member1')
        sample = self.create('sample', 'GDL', client=member)
        procedure = self.create('procedure', 'Compression', {'instructions': 'v1'}, member)
        experiment = self.create('experiment', 'Run', {'sample_uuids': [sample], 'procedure_uuid': procedure, 'procedure_revision': 1}, member)
        member.submit('procedure', 'Compression', {'instructions': 'v2'}, procedure, 'Revised calibration')
        self.admin.consume(); member.refresh()
        self.assertEqual(member.state['records'][experiment]['fields']['procedure_revision'], 1)
        source = self.base / 'capture.tif'; source.write_bytes(b'representative-image-fixture')
        links = {'experiment_uuid': experiment, 'sample_uuids': [sample], 'file_state': 'raw', 'created_at': '2026-09-20', 'sequence': 1}
        raw = member.upload(source, 'Captured region', links); self.admin.consume(); member.refresh()
        original = self.admin.state['records'][raw]
        self.assertEqual(original['checksum'], digest(source))
        for state in ('poremap', 'overlay', 'outline'):
            derived = member.upload(source, state, dict(links, file_state=state, parent_file_uuid=raw, processing_run_id=str(uuid.uuid4())))
            self.admin.consume(); member.refresh()
            self.assertEqual(member.state['records'][derived]['fields']['parent_file_uuid'], raw)
            self.assertEqual(member.state['records'][derived]['fields']['sample_uuids'], [sample])
        fields = dict(original['fields'], notes='Scale verified')
        member.submit('file', 'Renamed nickname', fields, raw, 'Document scale')
        self.admin.consume()
        self.assertEqual(self.admin.state['records'][raw]['relative_path'], original['relative_path'])
        member.refresh(); member.submit('file', 'Replace raw', dict(fields, checksum='wrong'), raw, 'Not allowed')
        receipts = self.admin.consume(); self.assertIn('conflict', [r['status'] for r in receipts.values()])
        self.assertEqual(self.admin.state['records'][raw]['checksum'], original['checksum'])

    def test_incomplete_upload_rejected_without_canonical_overwrite(self):
        member = self.client('member1'); source = self.base / 'raw.png'; source.write_bytes(b'original')
        member.upload(source, 'Raw', {'file_state': 'raw'})
        artifact = next((self.admin.control / 'Incoming_Files').iterdir()); artifact.write_bytes(b'partial')
        result = self.admin.consume()
        self.assertEqual(next(iter(result.values()))['status'], 'conflict')
        self.assertEqual(self.admin.rows(kind='file'), [])
        member.refresh(); request_id = next(iter(result))
        member.resubmit(request_id, 'Retry original verified local bytes after partial synchronization')
        self.admin.consume(); member.refresh()
        self.assertEqual(len(member.rows(kind='file')), 1)
        self.assertEqual(member.rows(kind='file')[0]['checksum'], digest(source))

    def test_legacy_dry_run_aliases_five_samples_original_names_unknown_creator(self):
        folder = self.root / 'Previous summer'; folder.mkdir()
        for name in ['Holy GDL.png', '1344 Pascal.csv'] + [f'sample-{i}.txt' for i in range(5)]:
            (folder / name).write_text('representative legacy fixture', encoding='utf-8')
        before = {p.name: digest(p) for p in folder.iterdir()}
        report = self.admin.inventory()
        self.assertEqual(len(report['files']), 7); self.assertEqual(len(self.admin.rows(kind='sample')), 0)
        self.assertEqual(len(report['aliases_found']), 2)
        self.admin.import_inventory(report)
        self.assertEqual(len(self.admin.rows(kind='sample')), 5)
        self.assertEqual(len(self.admin.rows(query='Holy GDL')), 1)
        self.assertEqual(len(self.admin.rows(query='1344 Pascal')), 1)
        self.assertEqual(before, {p.name: digest(p) for p in folder.iterdir()})
        for row in self.admin.rows():
            if row.get('legacy'):
                self.assertIsNone(row['created_by_user_id']); self.assertEqual(row['created_by_display_name'], 'Unknown')
                self.assertEqual(row['uploaded_by_user_id'], self.admin.actor['user_id'])
        version = self.admin.state['revision']; self.admin.import_inventory(report)
        self.assertEqual(self.admin.state['revision'], version)

    def test_resume_inventory_missing_is_not_deleted(self):
        (self.root / 'sample-a.txt').write_text('a')
        interrupted = self.admin.inventory(lambda: True)
        self.assertFalse(interrupted['complete'])
        report = self.admin.inventory(); self.assertTrue(report['complete'])
        self.admin.import_inventory(report)
        (self.root / 'sample-a.txt').unlink()
        self.assertIn('not deleted', next(iter(self.admin.reconcile().values())))

    def test_tasks_meeting_lifecycle_carryover_explicit_ownership(self):
        member = self.client('member1')
        meeting = self.create('meeting', 'Planning', {'attendees': [member.actor['user_id']]}, member)
        fields = {'owner_id': member.actor['user_id'], 'due_date': '2026-10-20', 'acceptance': 'Reviewed baseline',
                  'meeting_uuid': meeting, 'status': 'active', 'semester': 'Fall 2026'}
        action = self.create('task', 'Replicate baseline', fields, member)
        for stage in ('minutes', 'summary'):
            current = dict(member.state['records'][meeting]['fields'], stage=stage)
            current[stage] = 'Verified decisions and follow-up'
            member.submit('meeting', 'Planning', current, meeting, 'Meeting ' + stage)
            self.admin.consume(); member.refresh()
        next_meeting = self.create('meeting', 'Follow-up', client=member)
        self.assertIn(action, member.state['records'][next_meeting]['fields']['carried_actions'])
        self.assertIn('Replicate baseline', member.meeting_text(next_meeting, 'agenda'))
        self.assertEqual(len(member.rows(kind='task')), 1)
        with self.assertRaises(ValueError): member._validate_fields('task', {}, member.state['records'])

    def test_noncomparable_bulk_metrics_excluded_and_2d_requires_review(self):
        self.assertFalse(comparability({'dimensionality': '3D', 'metric': 'bulk porosity'})[0])
        fields = {'dimensionality': '2D', 'metric': 'apparent surface porosity', 'definition': 'segmented area fraction',
            'method': 'Optical microscopy', 'sample_basis': 'same surface and pressure', 'units': '%',
            'comparison_reason': 'Matching threshold and field of view', 'reviewer_id': self.admin.actor['user_id']}
        key = self.create('research', 'Method review', fields)
        self.assertTrue(self.admin.state['records'][key]['fields']['comparable'])
        self.assertIn('not 3D bulk', self.admin.state['records'][key]['fields']['comparability_warning'])

    def test_names_reject_traversal_avoid_reserved_characters(self):
        name = filename('2026-10-10', 'procedure', ['P0001'], 'final:stuff?/../', 2, extension='.docx')
        self.assertEqual(name, '2026-10-10_PROC_P0001_final-stuff_v02.docx')
        with self.assertRaises(ValueError): self.admin.safe('../production.txt')
        with self.assertRaises(ValueError): filename('invalid', 'sample', [], 'a')

    def test_beta_external_root_guard(self):
        self.admin.store.sandbox_required = True
        with self.assertRaisesRegex(ValueError, 'isolated'): Organization(self.admin.store)

    def test_cross_channel_identity_requests_rejected(self):
        member = self.client('member1')
        identity = read_json(self.admin.control / 'identity.json', {}); identity['channel'] = 'other-channel'
        write_json(self.admin.control / 'identity.json', identity)
        with self.assertRaises(ValueError): member.submit('sample', 'Cannot cross channels')
        self.assertTrue(list((member.local / 'outbox').glob('*.json')))

    def test_conflicting_request_copy_is_rejected_before_either_applies(self):
        member = self.client('member1'); key = member.submit('sample', 'Original request')
        source = next((self.admin.control / 'Incoming_Changes').glob('*.json'))
        conflict = read_json(source, {}); conflict['title'] = 'Conflicting sync copy'
        write_json(source.with_name(source.stem + '-conflicted-copy.json'), conflict)
        self.admin.consume()
        self.assertNotIn(key, self.admin.state['records'])
        self.assertEqual(self.admin.state['requests'][conflict['request_uuid']]['status'], 'conflict')

    def test_meeting_pdf_registered_in_mtg_folder_and_upload_cache_released(self):
        from app.services.organization_export import export_meeting
        from pypdf import PdfReader
        member = self.client('member1')
        meeting = self.create('meeting', 'Planning summary', {'summary': 'The baseline was reviewed. Raw captures remain immutable.',
            'attendees': [member.actor['user_id']]}, member)
        pdf = export_meeting(member, meeting, 'summary')
        self.assertIn('Andrew Michelson', PdfReader(pdf).pages[0].extract_text())
        self.admin.consume(); member.refresh()
        row = member.rows(kind='file')[0]
        self.assertIn('03_Meetings_and_Goals/Meetings/', row['relative_path'])
        self.assertEqual(row['created_by_user_id'], member.actor['user_id'])
        self.assertEqual(digest(member.safe(row['relative_path'])), digest(pdf))
        self.assertEqual(list((member.local / 'uploads').glob('*')), [])

    def test_source_search_resolves_public_sample_ids_and_nicknames(self):
        sample = self.create('sample', 'Baseline', {'aliases': ['Holy GDL']})
        experiment = self.create('experiment', 'Test', {'sample_uuids': [sample]})
        self.assertIn(experiment, [r['uuid'] for r in self.admin.rows(query='S0001')])
        self.assertIn(experiment, [r['uuid'] for r in self.admin.rows(query='Holy GDL')])

    def test_accepted_actions_and_attendance_feed_existing_activity_reports_once(self):
        from app.services.contributions import fetch_pages
        member = self.client('member1')
        self.create('sample', 'Tracked sample', client=member)
        meeting = self.create('meeting', 'Recorded attendance', {'attendees': [member.actor['user_id']]}, member)
        member.refresh()
        events = member.accounts.rows('Events')
        accepted = [e for e in events if e['event_type'] == 'SAMPLE_CREATED']
        self.assertEqual(len(accepted), 1); self.assertEqual(accepted[0]['device_id'], member.accounts.install_id)
        self.assertEqual(len([e for e in member.accounts.rows('Events') if e['event_type'] == 'SAMPLE_CREATED']), 1)
        attendance = fetch_pages(member.accounts, 'meeting_attendees')
        self.assertEqual([a['meeting_id'] for a in attendance if a['user_id'] == member.actor['user_id']], [meeting])


if __name__ == '__main__': unittest.main()
