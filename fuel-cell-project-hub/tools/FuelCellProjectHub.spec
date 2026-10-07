# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
project_directory = Path(SPECPATH).parent
datas = [(str(project_directory / 'config' / name), 'config') for name in ('project_defaults.json', 'software_manifest.json', 'file_classification.json', 'research_defaults.json', 'indexing_rules.json')]
engine = project_directory / 'analysis/gdl/engine'
for source_file in engine.rglob('*'):
    if source_file.is_file() and '__pycache__' not in source_file.parts and source_file.suffix != '.pyc':
        datas.append((str(source_file), 'analysis/gdl/engine/' + source_file.relative_to(engine).parent.as_posix()))
datas.append((str(project_directory / 'analysis/gdl/manifest.json'), 'analysis/gdl'))
datas.append((str(project_directory / 'analysis/gdl/hub_runtime.py'), 'analysis/gdl'))
datas.append((str(project_directory / 'assets'), 'assets'))
binaries = []
hiddenimports = ['unittest.mock']
a = Analysis(
    [str(project_directory / 'tools/desktop_entry.py')],
    pathex=[str(project_directory)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['msal', 'msal_extensions', 'azure.identity'],
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
