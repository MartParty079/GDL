# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import runpy
import json
import subprocess
from datetime import datetime, timezone
from PyInstaller.utils.win32.versioninfo import (VSVersionInfo,FixedFileInfo,StringFileInfo,StringTable,StringStruct,VarFileInfo,VarStruct)
project_directory = Path(SPECPATH).parent
datas = [(str(project_directory / 'config' / name), 'config') for name in ('project_defaults.json', 'software_manifest.json', 'file_classification.json', 'research_defaults.json', 'indexing_rules.json', 'accounts_public.json')]
engine = project_directory / 'analysis/gdl/engine'
for source_file in engine.rglob('*'):
    if source_file.is_file() and '__pycache__' not in source_file.parts and source_file.suffix != '.pyc':
        datas.append((str(source_file), 'analysis/gdl/engine/' + source_file.relative_to(engine).parent.as_posix()))
datas.append((str(project_directory / 'analysis/gdl/manifest.json'), 'analysis/gdl'))
datas.append((str(project_directory / 'analysis/gdl/hub_runtime.py'), 'analysis/gdl'))
datas.append((str(project_directory / 'assets'), 'assets'))
datas.append((str(project_directory / 'CHANGELOG.md'), '.'))
app_version = runpy.run_path(str(project_directory / 'app/version.py'))['VERSION']
try:
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=project_directory,text=True).strip()
except (OSError,subprocess.CalledProcessError):
    commit = 'unavailable'
build_metadata = project_directory / 'build' / 'build_metadata.json'
build_metadata.parent.mkdir(parents=True,exist_ok=True)
build_metadata.write_text(json.dumps({'commit':commit,'built_at':datetime.now(timezone.utc).isoformat()}),encoding='utf-8')
datas.append((str(build_metadata),'config'))
version_tuple = tuple(int(part) for part in app_version.split('-')[0].split('.')) + (0,)
version_resource = VSVersionInfo(ffi=FixedFileInfo(filevers=version_tuple,prodvers=version_tuple,mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)), kids=[StringFileInfo([StringTable('040904B0',[StringStruct('FileDescription','GDL Research Hub'),StringStruct('FileVersion',app_version),StringStruct('ProductName','GDL Research Hub'),StringStruct('ProductVersion',app_version)])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])
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
    version=version_resource,
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
