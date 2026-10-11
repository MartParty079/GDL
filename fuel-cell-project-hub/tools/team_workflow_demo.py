"""Screenshot tour of real desktop components on a new profile-contained fixture."""
import argparse
import gc
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QImage, QColor
from app.services.storage import Store, write_json
from app.services.project_locations import ProjectLocations
from app.services.local_accounts import LocalAccounts
from app.services.organization import Organization, digest
from app.ui.window import HubWindow
from app.ui.local_accounts import attach_account_ui
from app.ui.intake import IntakeDialog
from app.ui.organization import RecordEditor


def demo(output):
    output.mkdir(parents=True, exist_ok=True)
    fixture = output / ('fixture-' + uuid.uuid4().hex)
    store = Store(local_dir=fixture / 'profile')
    locations = ProjectLocations(store).defaults(); shared = store.local_dir / 'research-sandbox/shared'; shared.mkdir(parents=True)
    locations.update(enabled=False, shared_storage=str(shared), legacy=[]); locations['active']['root_path'] = str(shared)
    store.local['project_locations'] = locations
    accounts = LocalAccounts(store); store.accounts = accounts
    accounts.setup_admin('246810'); accounts.sign_in(accounts.users()[0]['id'], '246810')
    organization = Organization(store); organization.initialize()
    def create(kind, title, fields=None):
        key = organization.submit(kind, title, fields); organization.consume(); return key
    owner = accounts.users()[0]['id']; member = accounts.users()[1]['id']
    today = date.today(); begin = today.isoformat(); end = (today + timedelta(days=13)).isoformat()
    period = create('period', 'First evidence review', {'start_date': begin, 'end_date': end, 'due_at': end + 'T17:00:00-05:00'})
    sample = create('sample', 'Representative carbon paper', {'aliases': ['Holy GDL'], 'new_used_state': 'New', 'nominal_thickness': '0.190', 'units': 'mm'})
    procedure = create('procedure', 'Baseline microscope capture', {'instructions': 'Use a resident reference capture. Record calibration and illumination before analysis.', 'approval_status': 'Approved'})
    experiment = create('experiment', 'Repeatability fixture', {'procedure_uuid': procedure, 'procedure_revision': 1, 'sample_uuids': [sample], 'active_experiment': 'Yes', 'status': 'Ready', 'apparatus_settings': 'Representative fixture only; no measured result', 'units': 'µm per pixel (calibration required)'})
    goal = create('goal', 'Establish repeatable surface imaging', {'owner_id': owner, 'due_date': end, 'output': 'Reviewed procedure and traceable reference capture', 'next_step': 'Confirm scale calibration', 'status': 'In Progress', 'active_goal': 'Yes', 'period_uuid': period})
    meeting = create('meeting', 'Baseline planning', {'created_at': begin, 'meeting_time': '14:00 America/Chicago', 'facilitator_id': owner, 'note_taker_id': member, 'attendees': [owner, member], 'agenda': 'Review reference capture\nConfirm procedure revision\nAssign evidence review', 'minutes': 'Reviewed baseline capture. Agreed to preserve raw sources. Calibration evidence is pending.', 'decisions': 'Use the same surface region for repeatability.', 'stage': 'minutes', 'period_uuid': period})
    create('task', 'Review scale calibration', {'owner_id': member, 'due_date': end, 'acceptance': 'Calibration image and units reviewed', 'status': 'active', 'meeting_uuid': meeting, 'goal_uuid': goal, 'period_uuid': period})
    create('deliverable', 'Individual evidence review', {'owner_id': owner, 'period_uuid': period, 'work_completed': 'Prepared repeatability workflow and linked the baseline procedure.', 'next_plan': 'Review reference capture evidence.', 'submission_status': 'Submitted', 'evidence_uuids': [sample, procedure, experiment]})
    create('research', 'Surface and bulk comparison', {'research_section': 'Literature_Reviews_and_Comparisons', 'dimensionality': '3D', 'metric': 'bulk porosity'})
    create('design', 'Alignment fixture', {'design_section': 'CAD_and_Drawings', 'material': 'PLA', 'prototype_status': 'Draft'})
    raw = fixture / 'raw.tif'; image = QImage(480, 300, QImage.Format_RGB32); image.fill(QColor('#556d70')); image.save(str(raw))
    raw_key = organization.upload(raw, 'Representative raw surface', {'file_state': 'raw', 'experiment_uuid': experiment, 'sample_uuids': [sample]}); organization.consume()
    png = fixture / 'poremap.png'; image.fill(QColor('#dce9dd')); image.save(str(png))
    organization.upload(png, 'Representative pore map', {'file_state': 'poremap', 'experiment_uuid': experiment, 'sample_uuids': [sample], 'parent_file_uuid': raw_key, 'processing_run_id': str(uuid.uuid4())}); organization.consume()
    organization.upload(png, 'Workspace draft', {'workspace_owner_id': owner}); organization.consume()
    app = QApplication.instance() or QApplication([])
    with patch('app.ui.window.QTimer.singleShot'): window = HubWindow(store)
    attach_account_ui(window, accounts, lambda: None)
    window.resize(1440, 1000); window.show(); app.processEvents()
    screenshots = []
    def capture(widget, name):
        app.processEvents(); path = output / (name + '.png'); widget.grab().save(str(path)); screenshots.append(path.name)
    capture(window, 'home')
    window.resize(1024, 768); app.processEvents(); capture(window, 'home-small'); window.resize(1440, 1000)
    window.home_panel.verticalScrollBar().setValue(window.home_panel.verticalScrollBar().maximum()); capture(window, 'quick-start')
    window.home_panel.navigate('Meetings & Goals'); window.organization_panel.kind.setCurrentIndex(window.organization_panel.kind.findData('deliverable')); capture(window, 'deliverables')
    editor = RecordEditor(organization, 'meeting', organization.state['records'][meeting], window); editor.show(); capture(editor, 'meeting'); editor.close(); editor.deleteLater()
    intake = IntakeDialog(window.organization_panel, organization)
    intake.queue.add([raw, png]); intake.reload(); intake.show(); intake.table.selectRow(0); capture(intake, 'upload'); intake.close(); intake.deleteLater()
    workspace = RecordEditor(organization, 'deliverable', parent=window, defaults={'owner_id': owner, 'period_uuid': period}); workspace.show(); capture(workspace, 'deliverable-editor'); workspace.close(); workspace.deleteLater()
    # Capture the actual workspace/admin dialogs without external file launches.
    from PySide6.QtCore import QTimer
    def capture_dialog(name):
        def action():
            widget = QApplication.activeModalWidget()
            if widget: capture(widget, name); widget.reject()
        QTimer.singleShot(150, action)
    capture_dialog('my-workspace'); window.home_panel.workspace()
    window.tabs.setCurrentWidget(window.local_activity_panel); capture(window, 'administration')
    accounts.sign_in(member); window.session_presence.stop(); window.account_timer.stop()
    # Current role change is intentionally not used to grant UI authority; a fresh Member window is tested by unittest.
    deadline = time.monotonic() + 30
    while window.research_workspace.busy() or window.weekly_panel.tasks.busy() or window.meetings_panel.busy() or window.workers:
        app.processEvents(); time.sleep(.01)
        if time.monotonic() > deadline: raise RuntimeError('QA workers did not settle')
    write_json(output / 'evidence.json', {'fixture_only': True, 'snapshot_revision': organization.state['revision'], 'root': str(shared), 'screenshots': screenshots, 'four_categories': [b.text() for b in window.home_panel.category_buttons], 'workspace_users': organization.state['workspace_users'], 'raw_sha256': digest(raw)})
    accounts.close(); window.close(); window.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    del window, editor, intake, workspace; gc.collect(); app.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    demo(parser.parse_args().output.resolve())
