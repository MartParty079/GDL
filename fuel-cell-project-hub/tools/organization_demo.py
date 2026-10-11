"""Produce reproducible screenshots/PDF using only a new isolated fixture tree."""
import argparse
import gc
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtPdf import QPdfDocument
from app.services.storage import Store, write_json
from app.services.local_accounts import LocalAccounts
from app.services.organization import Organization, CATEGORIES, digest
from app.services.organization_export import export_meeting
from app.ui.organization import OrganizationPanel, RecordEditor
from app.ui.theme import apply_theme


def demo(output):
    output.mkdir(parents=True, exist_ok=True)
    fixture = output / ('fixture-' + uuid.uuid4().hex)
    store = Store(local_dir=fixture / 'profile')
    shared = fixture / 'shared'; shared.mkdir(parents=True)
    store.local['project_locations'] = {'enabled': True, 'shared_storage': str(shared)}
    accounts = LocalAccounts(store); store.accounts = accounts
    accounts.setup_admin('246810'); accounts.sign_in(accounts.users()[0]['id'], '246810')
    service = Organization(store); service.initialize()
    def create(kind, title, fields=None):
        key = service.submit(kind, title, fields); service.consume(); return key
    sample = create('sample', 'Carbon paper baseline', {'manufacturer': 'Representative fixture', 'material': 'Carbon paper',
                    'nominal_thickness': '0.19', 'units': 'mm', 'new_used_state': 'New', 'aliases': ['Baseline GDL']})
    procedure = create('procedure', 'Baseline microscopy', {'instructions': 'Calibrate scale and capture consistent surface regions.', 'approval_status': 'Draft'})
    experiment = create('experiment', 'Optical surface baseline', {'sample_uuids': [sample], 'procedure_uuid': procedure, 'procedure_revision': 1, 'units': 'kPa'})
    image = QImage(640, 400, QImage.Format_RGB32); image.fill(QColor('#283c40'))
    painter = QPainter(image); painter.setPen(QColor('#afc6bd'))
    for position in range(0, 640, 25): painter.drawLine(position, 0, max(0, position - 160), 400)
    painter.end(); raw = fixture / 'representative-raw.png'; image.save(str(raw))
    raw_key = service.upload(raw, 'Surface region', {'file_state': 'raw', 'experiment_uuid': experiment, 'sample_uuids': [sample], 'sequence': 1})
    service.consume()
    service.upload(raw, 'Pore map', {'file_state': 'poremap', 'experiment_uuid': experiment, 'sample_uuids': [sample], 'parent_file_uuid': raw_key, 'processing_run_id': str(uuid.uuid4())}); service.consume()
    create('research', 'Optical and bulk porosity comparison', {'research_section': 'Literature_Reviews_and_Comparisons',
        'dimensionality': '3D', 'metric': 'bulk porosity', 'relevance': 'Different measurement basis; excluded from direct surface comparison.',
        'access_license_provenance': 'Representative QA record; no copyrighted content bundled'})
    create('design', 'Microscope alignment fixture', {'material': 'PLA', 'units': 'mm', 'tolerance': '0.2',
        'manufacturing_process': '3D printing', 'prototype_status': 'Draft; fit check pending'})
    meeting = create('meeting', 'Fall baseline planning', {'facilitator_id': accounts.users()[0]['id'], 'note_taker_id': accounts.users()[1]['id'],
        'attendees': [u['id'] for u in accounts.users()], 'stage': 'summary',
        'summary': 'The team reviewed the baseline microscopy procedure and the legacy inventory. The optical workflow will report apparent surface porosity. Bulk porosity comparisons remain excluded until measurement compatibility is established. Fixture fit checks and equipment refurbishment remain Fall priorities.',
        'minutes': 'DECISION: preserve raw captures. Rationale: reproducible processing.\nACTION: review baseline procedure before next meeting.',
        'summary_reviewed_by_id': accounts.users()[0]['id'], 'summary_approved': 'Yes'})
    create('task', 'Review baseline procedure', {'owner_id': accounts.users()[1]['id'], 'due_date': '2026-10-20',
        'acceptance': 'Calibration and capture conditions reviewed', 'status': 'active', 'meeting_uuid': meeting, 'semester': 'Fall 2026'})
    pdf = export_meeting(service, meeting, 'summary'); service.consume()
    # Copy only this QA deliverable for visual inspection; original shared file
    # remains registered in its meeting folder with its verified checksum.
    (output / 'meeting-summary.pdf').write_bytes(pdf.read_bytes())
    app = QApplication.instance() or QApplication([])
    class DemoWindow(QMainWindow):
        def work(self, *args): raise RuntimeError('QA screenshots do not run background mutations')
    window = DemoWindow(); window.store = store
    panel = OrganizationPanel(window); window.setCentralWidget(panel); window.resize(1440, 900); apply_theme(window); window.show()
    screenshots = []
    for category in CATEGORIES:
        panel.category.setCurrentText(category); app.processEvents()
        if panel.table.rowCount(): panel.table.selectRow(0)
        app.processEvents(); target = output / (category.split(' ')[0].lower() + '.png'); window.grab().save(str(target)); screenshots.append(target.name)
    editor = RecordEditor(service, 'meeting', service.state['records'][meeting], window); apply_theme(editor); editor.show(); app.processEvents()
    editor.grab().save(str(output / 'meeting-editor.png')); editor.close(); editor.deleteLater()
    document = QPdfDocument(); document.load(str(output / 'meeting-summary.pdf'))
    for index in range(document.pageCount()):
        from PySide6.QtCore import QSize
        rendered = document.render(index, QSize(1000, 1294))
        white = QImage(rendered.size(), QImage.Format_RGB32); white.fill(Qt.white)
        painter = QPainter(white); painter.drawImage(0, 0, rendered); painter.end()
        white.save(str(output / f'meeting-pdf-{index+1}.png'))
    write_json(output / 'evidence.json', {'fixture_only': True, 'categories': list(CATEGORIES), 'screenshots': screenshots,
        'snapshot_revision': service.state['revision'], 'meeting_pdf_sha256': digest(output / 'meeting-summary.pdf')})
    document.close(); accounts.close(); window.close(); window.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    del panel, window, editor, document; gc.collect(); app.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', required=True, type=Path)
    demo(parser.parse_args().output.resolve())
