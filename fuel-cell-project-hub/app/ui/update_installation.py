"""Bounded update preparation with cooperative indexing cancellation."""
import time
from PySide6.QtCore import QObject, QTimer, QThread
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from app.services.updates import PendingUpdate, newer, launch_installer
from app.ui.research_viewers import Tasks


class SafeUpdate(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window=window
        self.pending=PendingUpdate(window.store.local_dir)
        self.timer=QTimer(self);self.timer.setInterval(100);self.timer.timeout.connect(self.tick)
        self.state='idle';self.paused=[];self.flush_future=None
        self.tasks=Tasks(self)

    def schedule(self):
        self.pending.schedule(self.window.latest_release_info)
        return True

    def start(self):
        if self.state != 'idle':return
        self.schedule()  # Retain a retry even if downloading or installer launch fails.
        self.state='draining';self.deadline=time.monotonic()+30
        self.window.setEnabled(False)
        for name in ('account_timer','startup_reconciliation'):
            timer=getattr(self.window,name,None)
            if timer is not None and timer.isActive():
                self.paused.append((timer,timer.interval()));timer.stop()
        presence=getattr(self.window,'session_presence',None)
        if presence and presence.timer.isActive():
            self.paused.append((presence.timer,presence.timer.interval()));presence.timer.stop()
        self.window.research_panel.watcher.stop()
        shared_poll = getattr(self.window.research_panel, 'shared_poll', None)
        if shared_poll and shared_poll.isActive():
            self.paused.append((shared_poll, shared_poll.interval())); shared_poll.stop()
        try:
            self.window.storage_panel.cancel_index();self.window.research_panel.cancel_index()
            analysis=getattr(self.window,'gdl_service',None)
            if analysis and analysis.active():
                self.fail('Scientific analysis may still be writing research data. Finish processing in Fiji before updating, or choose Update on Next Open.');return
        except Exception:
            self.fail('An operation could not safely cancel. It will be allowed to finish. Choose Update on Next Open to update later.');return
        self.timer.start();self.tick()

    def busy(self):
        # Includes previews, dialogs, reports, admin requests and legacy workers.
        analysis=getattr(self.window,'gdl_service',None)
        return bool(analysis and analysis.active()) or any(t.isRunning() for t in self.window.findChildren(QThread))

    def tick(self):
        if time.monotonic() >= self.deadline:
            self.fail('A background operation has not safely finished. It will not be terminated. Choose Update on Next Open to update later.');return
        if self.busy():return
        accounts=getattr(self.window,'account_service',None)
        if self.state == 'draining':
            if accounts and not accounts.lock.acquire(blocking=False):return
            try:
                self.window.research_workspace.save_layout()
                self.window.update_recovery.save()
                self.window.store.save_local()
                if accounts and getattr(accounts,'participation',None):accounts.participation.persist()
            except Exception:
                self.fail('Pending changes could not be saved safely. Update on Next Open is available after saving your work.');return
            finally:
                if accounts:accounts.lock.release()
            self.state='flushing'
            self.flush_deadline=time.monotonic()+5
            if accounts:self.flush_future=accounts.executor.submit(accounts.flush)
        if self.state == 'flushing':
            if self.flush_future and not self.flush_future.done():
                if time.monotonic() >= self.flush_deadline:
                    self.flush_future.cancel()
                    self.fail('Activity synchronization is still running. Your pending activity is saved locally. Choose Update on Next Open to let it finish.');return
                return
            self.timer.stop();self.state='downloading'
            self.tasks.start(self.pending.prepare,self.install,self.fail)

    def install(self,path):
        # ready precedes QThread.finished; wait for the downloader to be disposed.
        if self.tasks.busy():QTimer.singleShot(50,lambda:self.install(path));return
        if self.busy():self.fail('A background operation is still active. Choose Update on Next Open.');return
        if path is None:self.fail('No newer update is available.');return
        accounts=getattr(self.window,'account_service',None)
        if accounts and not accounts.lock.acquire(blocking=False):
            self.fail('Activity synchronization is still finishing. Choose Update on Next Open.');return
        try:
            self.window.research_workspace.save_layout();self.window.store.save_local()
            presence=getattr(self.window,'session_presence',None)
            launch_installer(path)
            if presence:presence.stop()
            self.pending.launched()
        except Exception as exc:
            from app.services.updates import failure_reason
            self.fail('Installer could not start.\nStage: Installer launch\n' + failure_reason(exc));return
        finally:
            if accounts:accounts.lock.release()
        self.state='installer_started';self.window.update_exit_ready=True
        self.window.setEnabled(True);self.window.close()

    def fail(self,message):
        self.timer.stop();self.state='idle';self.window.setEnabled(True)
        for timer,interval in self.paused:timer.start(interval)
        self.paused=[]
        self.window.research_panel.configure_watcher()
        self.window.offer_deferred_update(message)


class StartupUpdate(QDialog):
    """Runs before login/workspace construction; failures resume normal startup."""
    def __init__(self,store):
        super().__init__()
        self.pending=PendingUpdate(store.local_dir);self.installing=False;self.continuing=False
        self.setWindowTitle('GDL Research Hub Update')
        layout=QVBoxLayout(self)
        from app import __version__
        self.message=QLabel(f'Installed: v{__version__} · Preparing your scheduled update…');self.message.setWordWrap(True);layout.addWidget(self.message)
        self.continue_button=QPushButton('Continue without updating');self.continue_button.clicked.connect(self.continue_startup);layout.addWidget(self.continue_button)
        self.tasks=Tasks(self)
        QTimer.singleShot(0,lambda:self.tasks.start(self.pending.prepare,self.ready,self.failed))

    def continue_startup(self):
        self.continuing=True
        if not self.tasks.busy():self.reject()
        else:self.message.setText('Finishing the current download safely. Normal startup will continue when it stops.')

    def ready(self,path):
        if self.tasks.busy():QTimer.singleShot(50,lambda:self.ready(path));return
        if self.continuing or path is None:self.reject();return
        try:
            launch_installer(path);self.pending.launched()
        except Exception:
            self.failed('');return
        self.installing=True;self.accept()

    def failed(self,message):
        self.message.setText(message or 'Installer launch failed. Your files and session are preserved. Retry under Settings → Updates.')
        if self.tasks.busy():QTimer.singleShot(50,lambda:self.failed(message));return
        self.reject()

    def reject(self):
        if self.tasks.busy():self.continue_startup()
        else:super().reject()

    def closeEvent(self,event):
        if self.tasks.busy():self.continue_startup();event.ignore()
        else:event.accept()


def pending_update_at_startup(store):
    pending=PendingUpdate(store.local_dir)
    row=pending.read()
    if not row:return False
    if not newer(row['tag']):pending.path.unlink(missing_ok=True);return False
    return StartupUpdate(store).exec() == QDialog.Accepted
