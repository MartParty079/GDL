"""Meetings and contribution views integrated into the authenticated Hub."""
import copy
import json
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from PySide6.QtCore import Qt, QDate, QTimer, QObject, QEvent
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QDateEdit, QListWidget, QListWidgetItem, QSplitter,
    QTextEdit, QDialog, QDialogButtonBox, QFormLayout, QTabWidget, QTableWidget,
    QCheckBox, QFileDialog, QMessageBox, QInputDialog, QApplication)
from app.ui.research_viewers import Tasks
from app.ui.flow_layout import FlowLayout
from app.services.meetings import Meetings, MEETING_TYPES, ATTENDANCE, import_transcript, TranscriptionService
from app.services.contributions import Participation, WeeklyReports, default_week, report_html, export_pdf, export_csv
from app.services.formatting import format_file_size
from app.services import file_launcher
from app.ui.theme import apply_theme


def action(layout, title, callback):
    button = QPushButton(title)
    button.clicked.connect(callback)
    layout.addWidget(button)
    return button


class SessionPresence(QObject):
    """Only boolean Hub interactions. No key events, coordinates or movement."""
    def __init__(self, window, accounts):
        super().__init__(window)
        self.window, self.accounts = window, accounts
        accounts.participation = Participation(accounts)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.heartbeat)
        self.timer.start(60000)
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, watched, event):
        if not isinstance(watched, QWidget):
            return False
        if watched is not self.window and not self.window.isAncestorOf(watched):
            return False
        session = self.accounts.participation.session
        if event.type() in (QEvent.WindowActivate, QEvent.WindowDeactivate):
            # Modal Hub dialogs also count; another program never does.
            QTimer.singleShot(0,self.update_focus)
        elif event.type() in (QEvent.MouseButtonPress, QEvent.Wheel):
            session.touch()
        elif event.type()==QEvent.FocusIn and not watched.property('participation_connected'):
            if isinstance(watched,QLineEdit):
                watched.textEdited.connect(lambda *_:session.touch())
                watched.setProperty('participation_connected',True)
            elif isinstance(watched,QTextEdit) and not watched.isReadOnly():
                watched.textChanged.connect(session.touch)
                watched.setProperty('participation_connected',True)
        return False

    def update_focus(self):
        if self.accounts.participation.session.closed:
            return
        active=QApplication.activeWindow()
        owned=active is self.window or (active is not None and self.window.isAncestorOf(active))
        self.accounts.participation.session.focus(owned)

    def heartbeat(self):
        self.accounts.participation.persist()
        self.accounts.executor.submit(self.flush)

    def flush(self):
        try:
            self.accounts.participation.flush()
            self.accounts.flush()
        except ValueError:
            pass

    def stop(self):
        self.timer.stop()
        self.accounts.participation.persist(close=True)
        QApplication.instance().removeEventFilter(self)


class MeetingEditor(QDialog):
    def __init__(self, service, row, roster, parent):
        super().__init__(parent)
        self.service, self.row, self.roster = service, copy.deepcopy(row), roster
        self.tasks = Tasks(self)
        self.setWindowTitle('Meeting · ' + (row['title'] or 'New meeting'))
        apply_theme(self)
        self.resize(920, 740)
        layout = QVBoxLayout(self); layout.setSpacing(16)
        self.tabs = QTabWidget(); layout.addWidget(self.tabs, 1)
        metadata = QWidget(); form = QFormLayout(metadata); form.setSpacing(12)
        self.fields = {}
        for field, label in [('title','Title'),('meeting_date','Date (YYYY-MM-DD)'),('start_time','Start time'),
                             ('end_time','End time'),('location','Location'),('meeting_type','Type'),('source_type','Origin'),('description','Description')]:
            if field in ('meeting_type','source_type'):
                edit = QComboBox(); edit.addItems(MEETING_TYPES if field=='meeting_type' else ('current','legacy'))
                edit.setEditable(field=='meeting_type'); edit.setCurrentText(row.get(field,''))
            else:
                edit = QLineEdit(row.get(field,''))
            self.fields[field]=edit; form.addRow(label,edit)
        self.tabs.addTab(metadata,'Meeting')
        self.attendance = QTableWidget(0,4)
        self.attendance.setHorizontalHeaderLabels(['Person','Attended','Status','Notes'])
        self.attendance.setColumnWidth(0,200);self.attendance.setColumnWidth(1,100);self.attendance.setColumnWidth(2,130)
        self.attendance.horizontalHeader().setStretchLastSection(True)
        attendance_page=QWidget(); col=QVBoxLayout(attendance_page)
        attendance_help=QLabel('Attendance is explicitly recorded. Excused entries are excluded from the attendance rate.')
        attendance_help.setWordWrap(True);col.addWidget(attendance_help)
        col.addWidget(self.attendance)
        action(col,'Add guest',self.guest)
        self.tabs.addTab(attendance_page,'Attendance')
        recorded={r['person_key']:r for r in row.get('attendees',[])}
        for person in roster:
            identity=person['id']; record=recorded.pop(identity, dict(person_key=identity,user_id=identity,guest_name='',attended=False,attendance_status='Absent',notes=''))
            self.attendee(person.get('display_name') or person.get('email') or identity,record)
        for record in recorded.values():
            self.attendee(record.get('guest_name') or record['person_key'],record)
        self.notes=QTextEdit(); self.notes.setPlainText(row['content'].get('notes',''))
        self.notes.setPlaceholderText('Summary, discussion, decisions, problems, next steps…')
        self.tabs.addTab(self.notes,'Notes')
        transcript_page=QWidget(); col=QVBoxLayout(transcript_page); col.setSpacing(16)
        bar=FlowLayout(); col.addLayout(bar)
        action(bar,'Attach existing transcript',self.import_text)
        generation=action(bar,'Generate transcript',lambda: None)
        generation.setEnabled(False); generation.setToolTip(TranscriptionService.status)
        action(bar,'Export transcript to shared file',lambda:self.export_text('transcript'))
        action(bar,'Transcript revisions',self.revisions)
        self.transcript_status=QLabel(row['content'].get('transcript_status','No Transcript')+' · '+TranscriptionService.status)
        self.transcript_status.setWordWrap(True); col.addWidget(self.transcript_status)
        self.transcript_search=QLineEdit();self.transcript_search.setPlaceholderText('Find transcript text; press Enter')
        self.transcript_search.returnPressed.connect(lambda:self.transcript.find(self.transcript_search.text()))
        col.addWidget(self.transcript_search)
        self.transcript=QTextEdit(); self.transcript.setPlainText(row['content'].get('transcript','')); col.addWidget(self.transcript,1)
        self.tabs.addTab(transcript_page,'Transcript')
        self.actions=QTableWidget(0,4);self.actions.setHorizontalHeaderLabels(['Action','Assigned','Due (YYYY-MM-DD)','Completed'])
        self.actions.setColumnWidth(0,320);self.actions.setColumnWidth(1,200);self.actions.setColumnWidth(2,160)
        self.actions.horizontalHeader().setStretchLastSection(True)
        actions_page=QWidget();col=QVBoxLayout(actions_page);col.addWidget(self.actions)
        action(col,'Add action item',lambda:self.add_action(dict(id=str(uuid.uuid4()),title='',assigned_to=None,due_date='',completed=False)))
        action(col,'Remove selected action item',lambda:self.actions.removeRow(self.actions.currentRow()) if self.actions.currentRow()>=0 else None)
        for item in row.get('actions',[]):self.add_action(item)
        self.tabs.addTab(actions_page,'Action items')
        files_page=QWidget();col=QVBoxLayout(files_page);col.setSpacing(16)
        self.files=QListWidget();self.files.setWordWrap(True); col.addWidget(self.files,1)
        bar=FlowLayout();col.addLayout(bar)
        action(bar,'Add recording · shared drive',lambda:self.attach('recording'))
        action(bar,'Choose indexed recording',self.indexed_recording)
        action(bar,'Attach related file',lambda:self.attach('related_file'))
        action(bar,'Open selected file',lambda:self.open_file(False))
        action(bar,'Show in Folder',lambda:self.open_file(True))
        action(bar,'Remove selected file link',self.remove_file)
        action(bar,'Export notes to shared file',lambda:self.export_text('notes'))
        self.refresh_files(); self.tabs.addTab(files_page,'Recording / Files')
        research_page=QWidget();col=QVBoxLayout(research_page)
        col.addWidget(QLabel('Link existing samples and experiments without changing source files.'))
        self.related=QListWidget();col.addWidget(self.related)
        action(col,'Link sample or experiment',self.link_research)
        action(col,'Remove selected link',self.unlink_research)
        self.refresh_related();self.tabs.addTab(research_page,'Related research')
        self.error=QLabel();self.error.setWordWrap(True);layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        editable=service.editable(row)
        buttons.button(QDialogButtonBox.Save).setEnabled(editable)
        if not editable:self.error.setText('Read only · the meeting creator or an administrator can edit.')
        # Boolean text activity only; never record editor contents in activity events.
        for edit in self.findChildren(QLineEdit):edit.textEdited.connect(self.touch)
        self.notes.textChanged.connect(self.touch);self.transcript.textChanged.connect(self.touch)

    def touch(self,*_):
        p=getattr(self.service.accounts,'participation',None)
        if p:p.session.touch()

    def attendee(self,name,record):
        index=self.attendance.rowCount();self.attendance.insertRow(index)
        self.attendance.setRowHeight(index,48)
        label=QLabel(name);label.setProperty('record',record);self.attendance.setCellWidget(index,0,label)
        check=QCheckBox();check.setChecked(record['attended']);self.attendance.setCellWidget(index,1,check)
        status=QComboBox();status.addItems(ATTENDANCE);status.setCurrentText(record['attendance_status']);self.attendance.setCellWidget(index,2,status)
        notes=QLineEdit(record.get('notes',''));self.attendance.setCellWidget(index,3,notes)
        def set_status(yes):status.setCurrentText('Present' if yes else 'Absent')
        def set_check(value):
            check.blockSignals(True);check.setChecked(value in ('Present','Remote','Partial'));check.blockSignals(False)
        check.toggled.connect(set_status);status.currentTextChanged.connect(set_check)

    def guest(self):
        name,ok=QInputDialog.getText(self,'Guest attendance','Guest name:')
        if ok and name.strip():self.attendee(name.strip(),dict(person_key='guest:'+uuid.uuid4().hex,user_id=None,guest_name=name.strip(),attended=False,attendance_status='Absent',notes=''))

    def add_action(self,item):
        index=self.actions.rowCount();self.actions.insertRow(index)
        self.actions.setRowHeight(index,48)
        title=QLineEdit(item['title']);title.setProperty('action_id',item['id']);self.actions.setCellWidget(index,0,title)
        assigned=QComboBox();assigned.addItem('Unassigned',None)
        for p in self.roster:assigned.addItem(p.get('display_name') or p.get('email') or p['id'],p['id'])
        match=assigned.findData(item.get('assigned_to'));assigned.setCurrentIndex(max(0,match));self.actions.setCellWidget(index,1,assigned)
        self.actions.setCellWidget(index,2,QLineEdit(item.get('due_date') or ''))
        done=QCheckBox();done.setChecked(item.get('completed',False));self.actions.setCellWidget(index,3,done)

    def shared_start(self):
        return str(self.service.catalog.locations.value['shared_storage']) if self.service.catalog else ''

    def attach(self,kind):
        filename,_=QFileDialog.getOpenFileName(self,'Choose shared research file',self.shared_start(),
                 'Recordings (*.mp3 *.wav *.m4a *.mp4 *.mov)' if kind=='recording' else 'All files (*)')
        if filename:
            try:
                key=kind+':'+uuid.uuid4().hex if kind=='related_file' else kind
                self.row['content'].setdefault('files',{})[key]=self.service.file_ref(filename);self.refresh_files()
            except ValueError as exc:self.error.setText(str(exc))

    def indexed_recording(self):
        if not self.service.catalog:return
        query,ok=QInputDialog.getText(self,'Indexed recording','Search filename:')
        if not ok or not query.strip():return
        def find():
            rows,_=self.service.catalog.query(query=query,limit=200)
            return [r for r in rows if r['extension'] in ('.mp3','.wav','.m4a','.mp4','.mov')]
        def choose(rows):
            if not rows:self.error.setText('No recording in these results. Use Browse Shared Drive.');return
            labels=[r['name']+' · '+r.get('relative_path','') for r in rows]
            value,selected=QInputDialog.getItem(self,'Indexed recording','Recording:',labels,editable=False)
            if selected:
                try:self.row['content'].setdefault('files',{})['recording']=self.service.file_ref(self.service.catalog.safe_path(rows[labels.index(value)]));self.refresh_files()
                except ValueError as exc:self.error.setText(str(exc))
        self.tasks.start(find,choose,self.error.setText)

    def refresh_files(self):
        self.files.clear()
        for kind,ref in self.row['content'].get('files',{}).items():
            item=QListWidgetItem(kind.split(':',1)[0].replace('_',' ').title()+' · '+ref['filename']+' · '+format_file_size(ref.get('size',0))+' · '+ref.get('extension','')+'\n'+ref['source_label']+' / '+ref['relative_path'])
            item.setData(Qt.UserRole,ref);item.setData(Qt.UserRole+1,kind)
            try:item.setToolTip(str(self.service.file_path(ref)))
            except ValueError:item.setToolTip('Configure the matching source to locate this file.')
            self.files.addItem(item)

    def remove_file(self):
        item=self.files.currentItem()
        if item:
            self.row['content']['files'].pop(item.data(Qt.UserRole+1),None)
            self.refresh_files()

    def revisions(self):
        history=self.row['content'].get('transcript_history',[])
        if not history:
            self.error.setText('No earlier transcript revisions are recorded.');return
        dialog=QDialog(self);dialog.setWindowTitle('Earlier transcript revisions');dialog.resize(760,600)
        layout=QVBoxLayout(dialog);text=QTextEdit();text.setReadOnly(True)
        text.setPlainText('\n\n'.join('Edited '+str(r.get('at') or 'Date not recorded')+' · '+str(r.get('edited_by') or 'Editor not recorded')+'\n'+r['text'] for r in reversed(history)))
        layout.addWidget(text);action(layout,'Close',dialog.accept);dialog.exec()

    def open_file(self,folder):
        item=self.files.currentItem()
        if not item:return
        try:
            path=self.service.file_path(item.data(Qt.UserRole))
            (file_launcher.show_in_folder if folder else file_launcher.open_file)(path)
        except (ValueError,OSError):self.error.setText('File unavailable. Check the matching shared source and OneDrive availability.')

    def import_text(self):
        path,_=QFileDialog.getOpenFileName(self,'Attach existing transcript',self.shared_start(),'Transcript (*.txt *.md *.docx *.pdf)')
        if not path:return
        try:ref=self.service.file_ref(path)
        except ValueError as exc:self.error.setText(str(exc));return
        self.transcript_status.setText('Importing transcript…')
        def imported(text):
            self.transcript.setPlainText(text);self.row['content']['files']['transcript']=ref
            self.row['content']['transcript_status']='Imported';self.transcript_status.setText('Imported · editable');self.refresh_files()
        self.tasks.start(lambda:import_transcript(path),imported,lambda message:(self.transcript_status.setText('Import failed'),self.error.setText(message)))

    def export_text(self,kind):
        path,_=QFileDialog.getSaveFileName(self,'Save '+kind+' in shared storage',self.shared_start()+'/'+kind+'.md','Text (*.md *.txt)')
        if not path:return
        try:
            # Validate the parent before creating a new file.
            destination=Path(path).resolve(); root=Path(self.shared_start()).resolve()
            if not destination.is_relative_to(root):raise ValueError('Choose the configured shared storage folder.')
            created=not destination.exists()
            Path(path).write_text(self.transcript.toPlainText() if kind=='transcript' else self.notes.toPlainText(),encoding='utf-8')
            self.row['content'].setdefault('files',{})[kind]=self.service.file_ref(path);self.refresh_files()
            if created:
                self.service.accounts.event('FILE_ADDED','file','',Path(path).name,{'source':'current','attribution':'app_user_action','file_category':'Reports','meeting_id':self.row['id']})
        except (ValueError,OSError) as exc:self.error.setText(str(exc) if isinstance(exc,ValueError) else 'Unable to save the shared file.')

    def refresh_related(self):
        self.related.clear()
        for ref in self.row['content'].get('related',[]):
            item=QListWidgetItem(ref['kind'].title()+' · '+ref['name']+' · '+ref['origin']);item.setData(Qt.UserRole,ref);self.related.addItem(item)

    def link_research(self):
        workspace=self.parent().window.research_workspace
        if not workspace.repository:return
        objects=[dict(o,kind=kind) for kind in ('sample','experiment') for o in workspace.repository.objects(kind,origin='')]
        labels=[o['kind'].title()+' · '+o['name']+' · '+o['origin'] for o in objects]
        if not labels:return
        value,ok=QInputDialog.getItem(self,'Link research','Object:',labels,editable=False)
        if ok:
            obj=objects[labels.index(value)];ref={k:obj[k] for k in ('id','kind','name','origin')}
            if ref not in self.row['content']['related']:self.row['content']['related'].append(ref)
            self.refresh_related()

    def unlink_research(self):
        item=self.related.currentItem()
        if item:self.row['content']['related'].remove(item.data(Qt.UserRole));self.refresh_related()

    def save(self):
        if self.tasks.busy():self.error.setText('Finish importing before saving.');return
        try:
            for key,edit in self.fields.items():self.row[key]=edit.currentText() if isinstance(edit,QComboBox) else edit.text()
            datetime.fromisoformat(self.row['meeting_date'])
            self.row['content']['notes']=self.notes.toPlainText();self.row['content']['transcript']=self.transcript.toPlainText()
            self.row['attendees']=[]
            for i in range(self.attendance.rowCount()):
                r=dict(self.attendance.cellWidget(i,0).property('record'))
                r.update(attended=self.attendance.cellWidget(i,1).isChecked(),attendance_status=self.attendance.cellWidget(i,2).currentText(),notes=self.attendance.cellWidget(i,3).text())
                self.row['attendees'].append(r)
            self.row['actions']=[]
            for i in range(self.actions.rowCount()):
                due=self.actions.cellWidget(i,2).text().strip()
                if due:datetime.fromisoformat(due)
                title=self.actions.cellWidget(i,0).text().strip()
                if not title:raise ValueError('Give each action item a title, or remove its row.')
                self.row['actions'].append(dict(id=self.actions.cellWidget(i,0).property('action_id'),title=title,assigned_to=self.actions.cellWidget(i,1).currentData(),due_date=due or None,completed=self.actions.cellWidget(i,3).isChecked()))
            self.row=self.service.save(self.row);self.accept()
        except ValueError as exc:self.error.setText(str(exc))

    def reject(self):
        if self.tasks.busy():self.error.setText('Wait for the import to finish before closing.');return
        super().reject()

    def closeEvent(self,event):
        if self.tasks.busy():event.ignore()
        else:super().closeEvent(event)


class MeetingsPanel(QWidget):
    def __init__(self,window,accounts):
        super().__init__(window);self.window=window;self.service=Meetings(accounts,window.storage_settings.catalog)
        self.tasks=Tasks(self);self.roster=[accounts.profile];self.dialogs=[]
        layout=QVBoxLayout(self);layout.setSpacing(16)
        layout.addWidget(QLabel('Meetings · recordings, explicit attendance and research decisions'))
        controls=FlowLayout();layout.addLayout(controls)
        self.search=QLineEdit();self.search.setPlaceholderText('Search title, notes or transcript');controls.addWidget(self.search)
        self.type=QComboBox();self.type.addItems(['All meeting types',*MEETING_TYPES]);controls.addWidget(self.type)
        self.origin=QComboBox();self.origin.addItems(['All origins','current','legacy']);controls.addWidget(self.origin)
        self.attendee_filter=QComboBox();self.attendee_filter.addItem('All attendees',None);controls.addWidget(self.attendee_filter)
        self.start=QDateEdit(QDate.currentDate().addYears(-2));self.end=QDateEdit(QDate.currentDate().addYears(1))
        self.start.setCalendarPopup(True);self.end.setCalendarPopup(True);controls.addWidget(self.start);controls.addWidget(self.end)
        self.sort=QComboBox();self.sort.addItems(['Newest','Oldest','Title','Meeting Type']);controls.addWidget(self.sort)
        for edit in (self.search,):edit.textChanged.connect(self.reload)
        for combo in (self.type,self.origin,self.attendee_filter,self.sort):combo.currentIndexChanged.connect(self.reload)
        self.start.dateChanged.connect(self.reload);self.end.dateChanged.connect(self.reload)
        bar=FlowLayout();layout.addLayout(bar)
        action(bar,'New meeting',lambda:self.edit(self.service.new()))
        action(bar,'View / edit selected',self.open_selected)
        action(bar,'Sync shared meetings',self.sync)
        action(bar,'Export selected draft',self.export_draft)
        action(bar,'Reload shared version',self.reload_shared)
        self.status=QLabel('Local meeting cache · Sync to load shared meetings');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.list=QListWidget();self.list.itemDoubleClicked.connect(lambda _:self.open_selected());layout.addWidget(self.list,1)
        self.reload()
        QTimer.singleShot(0,self.sync)

    def busy(self):return self.tasks.busy() or any(d.tasks.busy() for d in self.dialogs)

    def reload(self,*_):
        self.list.clear();rows=self.service.list(self.search.text())
        rows=[r for r in rows if self.start.date().toString('yyyy-MM-dd')<=r['meeting_date']<=self.end.date().toString('yyyy-MM-dd')
            and (self.type.currentIndex()==0 or r['meeting_type']==self.type.currentText())
            and (self.origin.currentIndex()==0 or r['source_type']==self.origin.currentText())
            and (not self.attendee_filter.currentData() or any(a.get('user_id')==self.attendee_filter.currentData() for a in r.get('attendees',[])))]
        key={'Newest':'meeting_date','Oldest':'meeting_date','Title':'title','Meeting Type':'meeting_type'}[self.sort.currentText()]
        rows.sort(key=lambda r:r[key],reverse=self.sort.currentText()=='Newest')
        for row in rows:
            attended=sum(a['attended'] for a in row.get('attendees',[]))
            item=QListWidgetItem(row['title']+'\n'+row['meeting_date']+' · '+row['meeting_type']+' · '+row['source_type']+f' · {attended} attended')
            item.setData(Qt.UserRole,row['id']);self.list.addItem(item)

    def open_selected(self):
        item=self.list.currentItem()
        if item:self.edit(self.service.get(item.data(Qt.UserRole)))

    def edit(self,row):
        dialog=MeetingEditor(self.service,row,self.roster,self);self.dialogs.append(dialog)
        if dialog.exec()==QDialog.Accepted:self.reload();self.sync()
        self.dialogs.remove(dialog);dialog.deleteLater()

    def sync(self):
        if self.tasks.busy():return
        self.status.setText('Synchronizing meetings…')
        def work():return self.service.sync(),self.service.roster()
        def done(result):
            status,roster=result;self.roster=roster or self.roster;self.status.setText(status)
            selected=self.attendee_filter.currentData();self.attendee_filter.blockSignals(True);self.attendee_filter.clear();self.attendee_filter.addItem('All attendees',None)
            for p in self.roster:self.attendee_filter.addItem(p.get('display_name') or p['id'],p['id'])
            self.attendee_filter.setCurrentIndex(max(0,self.attendee_filter.findData(selected)));self.attendee_filter.blockSignals(False);self.reload()
        self.tasks.start(work,done,lambda _:self.status.setText('Shared meetings unavailable. Local drafts are preserved; reconnect and retry.'))

    def export_draft(self):
        item=self.list.currentItem()
        if not item:return
        path,_=QFileDialog.getSaveFileName(self,'Export meeting draft','','Meeting (*.json)')
        if path:
            try:self.service.accounts.store.validate_project_output(path).write_text(json.dumps(self.service.get(item.data(Qt.UserRole)),indent=2),encoding='utf-8')
            except (OSError,ValueError):self.status.setText('Choose a writable folder inside the shared project.')

    def reload_shared(self):
        item=self.list.currentItem()
        if not item:return
        if QMessageBox.question(self,'Reload shared version','Discard this locally saved draft and fetch the shared version? Export your draft first to preserve its edits.')==QMessageBox.Yes:
            self.service.discard_pending(item.data(Qt.UserRole));self.sync()


class WeeklyPanel(QWidget):
    def __init__(self,window,accounts):
        super().__init__(window);self.window=window;self.accounts=accounts;self.service=WeeklyReports(accounts)
        self.tasks=Tasks(self);self.reports=[]
        layout=QVBoxLayout(self);layout.setSpacing(16)
        layout.addWidget(QLabel('Weekly contribution reports · measured Hub activity'))
        bar=FlowLayout();layout.addLayout(bar)
        begin,end=default_week()
        self.begin=QDateEdit(QDate(begin.year,begin.month,begin.day));self.end=QDateEdit(QDate(end.year,end.month,end.day))
        for edit in (self.begin,self.end):edit.setCalendarPopup(True)
        bar.addWidget(QLabel('From'));bar.addWidget(self.begin);bar.addWidget(QLabel('Until (exclusive)'));bar.addWidget(self.end)
        self.person=QComboBox();self.person.addItem('My weekly activity',accounts.profile);bar.addWidget(self.person)
        action(bar,'Generate',self.generate)
        action(bar,'Refresh team list',self.refresh_roster)
        action(bar,'Export PDF',lambda:self.export('pdf'))
        action(bar,'Export CSV',lambda:self.export('csv'))
        self.all_button=action(bar,'Generate All Team Reports',self.export_all);self.all_button.setVisible(accounts.profile['role']=='admin')
        self.combined_button=action(bar,'Export Combined Team PDF',self.export_combined)
        self.combined_button.setVisible(accounts.profile['role']=='admin')
        self.status=QLabel('Choose a period, then Generate. Active time is measured from v0.3.3 onward.');self.status.setWordWrap(True);layout.addWidget(self.status)
        splitter=QSplitter();layout.addWidget(splitter,1)
        self.team=QListWidget();self.team.setMaximumWidth(270);self.team.itemClicked.connect(self.select_report);splitter.addWidget(self.team)
        self.document=QTextEdit();self.document.setReadOnly(True);splitter.addWidget(self.document);splitter.setStretchFactor(1,1)
        QTimer.singleShot(0,self.refresh_roster)

    def refresh_roster(self):
        if self.tasks.busy():return
        def done(roster):
            self.person.clear()
            if self.accounts.profile['role']=='admin':self.person.addItem('All active team members',None)
            for p in roster:self.person.addItem(p.get('display_name') or p.get('email') or p['id'],p)
        self.tasks.start(self.service.roster,done,lambda _:self.status.setText('Team list unavailable. You can still select your own profile and retry.'))

    def bounds(self):
        # Obtain each endpoint's local UTC offset separately, including DST changes.
        begin=datetime.combine(self.begin.date().toPython(),datetime.min.time()).astimezone()
        end=datetime.combine(self.end.date().toPython(),datetime.min.time()).astimezone()
        if end<=begin:raise ValueError('Choose an end date after the start date.')
        return begin,end

    def generate(self,callback=None):
        if self.tasks.busy():return
        try:begin,end=self.bounds()
        except ValueError as exc:self.status.setText(str(exc));return
        chosen=self.person.currentData()
        self.status.setText('Loading recorded activity…')
        def work():
            people=[chosen] if chosen else self.service.roster()
            return [self.service.load(p,begin,end) for p in people]
        def done(reports):
            self.reports=reports;self.team.clear()
            for i,r in enumerate(reports):
                item=QListWidgetItem(r['person']+'\n'+r['metrics']['Active time']+f' · {r["metrics"]["Sessions"]} sessions');item.setData(Qt.UserRole,i);self.team.addItem(item)
            if reports:self.team.setCurrentRow(0);self.document.setHtml(report_html(reports[0]))
            self.status.setText('Recorded activity loaded. Pending activity from this installation is included; other offline installations appear after sync.')
            if callable(callback):callback(reports)
        self.tasks.start(work,done,lambda _:self.status.setText('Reports unavailable. Your local research remains usable; reconnect and retry.'))

    def select_report(self,item):self.document.setHtml(report_html(self.reports[item.data(Qt.UserRole)]))

    def export(self,kind):
        if not self.reports:return
        index=max(0,self.team.currentRow());report=self.reports[index]
        path,_=QFileDialog.getSaveFileName(self,'Export weekly report','Weekly-Contributions.'+kind,kind.upper()+' (*.'+kind+')')
        if path:
            try:(export_pdf if kind=='pdf' else export_csv)(report,path,self.accounts.store);self.status.setText('Report exported.')
            except (OSError,ValueError):self.status.setText('Choose a writable folder inside the shared project.')

    def export_all(self):
        if self.accounts.profile['role']!='admin':return
        folder=QFileDialog.getExistingDirectory(self,'One PDF per active team member')
        if not folder:return
        self.person.setCurrentIndex(0)
        def exported(reports):
            try:
                for r in reports:
                    name=re.sub(r'[^\w .-]','_',r['person'])[:70]
                    export_pdf(r,Path(folder)/(name+'-'+r['user_id'][:8]+'-'+r['begin'][:10]+'.pdf'),self.accounts.store)
                self.status.setText(f'{len(reports)} individual team reports exported.')
            except (OSError,ValueError):self.status.setText('Choose a writable folder inside the shared project.')
        self.generate(exported)

    def export_combined(self):
        if not self.accounts.admin_unlocked:return
        from app.services.contributions import combined_report
        path,_=QFileDialog.getSaveFileName(self,'Combined team report','Team-Weekly-Activity.pdf','PDF (*.pdf)')
        if not path:return
        self.person.setCurrentIndex(0)
        def exported(reports):
            try:
                export_pdf(combined_report(reports),path,self.accounts.store)
                self.status.setText('Combined team report exported.')
            except (OSError,ValueError):self.status.setText('Choose a writable folder within the configured workspace.')
        self.generate(exported)
