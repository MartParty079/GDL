"""Windows package entry and isolated startup acceptance check."""
import sys
import tempfile
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def self_check(report):
    import json
    import msal
    from msal_extensions import FilePersistenceWithDataProtection
    from unittest.mock import patch
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    from app.services.storage import Store, ROOT, write_json
    from app.ui.window import HubWindow
    from app.ui.branding import application_icon
    from app.services.resources import resource_path
    with tempfile.TemporaryDirectory() as temporary:
        app = QApplication([])
        app.setApplicationName('FuelCellProjectHub')
        app.setWindowIcon(application_icon())
        with patch('app.ui.window.QTimer.singleShot'):
            window = HubWindow(Store(ROOT, Path(temporary) / 'profile'))
        window.show()
        app.processEvents()
        result = {'startup': True, 'msal_version': msal.__version__, 'settings_tabs': [window.settings_tabs.tabText(i) for i in range(window.settings_tabs.count())],
                  'application_icon_loaded': not app.windowIcon().isNull(), 'window_icon_loaded': not window.windowIcon().isNull(),
                  'icon_asset_present': resource_path('assets/app_icon.ico').is_file(),
                  'local_path_editable': not window.storage_panel.root.isReadOnly(), 'default_origin': window.files_panel.origin.currentData(),
                  'engine_manifest_present': (ROOT / 'analysis/gdl/manifest.json').is_file(), 'fiji_launched': False}
        current, legacy = Path(temporary) / 'current', Path(temporary) / 'legacy'
        current.mkdir()
        legacy.mkdir()
        (current / 'current.txt').write_text('current')
        (legacy / 'historical.txt').write_text('legacy')
        panel = window.research_panel
        panel.active.setText(str(current))
        panel.legacy.setPlainText(str(legacy))
        panel.paths['shared_storage'].setText(str(current))
        if not panel.save():
            raise ValueError('Packaged research configuration failed.')
        indexed = window.storage_settings.catalog.refresh()
        window.files_panel.reload()
        result.update(research_catalog_available=True, research_current_files=indexed['current'],
                      research_legacy_files=indexed['legacy'], research_index_errors=indexed['errors'],
                      research_template_present=resource_path('config/research_defaults.json').is_file(),
                      research_sources_unchanged=not (current / '.projecthub').exists() and not (legacy / '.projecthub').exists())
        cache = FilePersistenceWithDataProtection(str(Path(temporary) / 'test-cache.bin'))
        cache.save('noncredential-test')
        result['dpapi_round_trip'] = cache.load() == 'noncredential-test'
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        write_json(Path(report), result)
    return 0


if __name__ == '__main__':
    if '--self-check' in sys.argv:
        report_path = sys.argv[sys.argv.index('--self-check') + 1]
        try:
            sys.exit(self_check(report_path))
        except Exception as exc:
            import json
            Path(report_path).write_text(json.dumps({'startup': False, 'error': str(exc)}), encoding='utf-8')
            sys.exit(1)
    from app.main import main
    sys.exit(main())
