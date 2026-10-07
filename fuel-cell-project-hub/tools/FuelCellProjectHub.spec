# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

from pathlib import Path
project_directory = Path(SPECPATH).parent
datas = [(str(project_directory / 'config' / name), 'config') for name in ('project_defaults.json', 'software_manifest.json', 'microsoft_auth.json', 'file_classification.json')]
datas.append((str(project_directory / 'analysis/gdl/engine'), 'analysis/gdl/engine'))
datas.append((str(project_directory / 'analysis/gdl/manifest.json'), 'analysis/gdl'))
datas.append((str(project_directory / 'analysis/gdl/hub_runtime.py'), 'analysis/gdl'))
datas.append((str(project_directory / 'assets'), 'assets'))
binaries = []
hiddenimports = ['unittest.mock']
tmp_ret = collect_all('msal')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('msal_extensions')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    [str(project_directory / 'tools/desktop_entry.py')],
    pathex=[str(project_directory)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Qt 6.11 uses the unversioned ICU API supplied by Windows. The bundled
# Python runtime contains a different ICU with suffixed exports; collecting it
# shadows System32 and prevents QtCore from loading. Use the Windows ICU.
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() not in ('icuuc.dll', 'icudt78.dll')]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FuelCellProjectHub',
    icon=str(project_directory / 'assets/app_icon.ico'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FuelCellProjectHub',
)
