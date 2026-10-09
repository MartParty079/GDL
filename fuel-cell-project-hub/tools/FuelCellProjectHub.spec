# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import runpy
import json
import subprocess
import os
from datetime import datetime, timezone
from PyInstaller.utils.win32.versioninfo import (VSVersionInfo,FixedFileInfo,StringFileInfo,StringTable,StringStruct,VarFileInfo,VarStruct)
project_directory = Path(SPECPATH).parent
channel = os.environ.get('GDL_BUILD_CHANNEL', 'beta')
if channel not in ('beta','stable'):raise ValueError('Invalid edition')
runpy.run_path(str(project_directory/'tools/release_policy.py'))['check'](channel,os.environ.get('GDL_PRODUCTION_APPROVAL_FILE'))
beta=channel=='beta'
exe_name='GDLResearchHubBeta' if beta else 'FuelCellProjectHub'
app_name='GDL Research Hub Beta' if beta else 'GDL Research Hub'
icon_name='app_icon_beta.ico' if beta else 'app_icon.ico'
datas = [(str(project_directory / 'config' / name), 'config') for name in ('project_defaults.json', 'software_manifest.json', 'file_classification.json', 'research_defaults.json', 'indexing_rules.json')]
engine = project_directory / 'analysis/gdl/engine'
for source_file in engine.rglob('*'):
    if source_file.is_file() and '__pycache__' not in source_file.parts and source_file.suffix != '.pyc':
        datas.append((str(source_file), 'analysis/gdl/engine/' + source_file.relative_to(engine).parent.as_posix()))
datas.append((str(project_directory / 'analysis/gdl/manifest.json'), 'analysis/gdl'))
datas.append((str(project_directory / 'analysis/gdl/hub_runtime.py'), 'analysis/gdl'))
datas.append((str(project_directory / 'assets'), 'assets'))
datas.append((str(project_directory / 'CHANGELOG.md'), '.'))
datas.append((str(project_directory / 'version_history.json'), '.'))
datas.append((str(project_directory / 'work_order_history.json'), '.'))
app_version = runpy.run_path(str(project_directory / 'app/version.py'))['VERSION']
sequence=int(os.environ.get('GDL_BETA_SEQUENCE') or json.loads((project_directory/'config/edition.json').read_text()).get('beta_sequence',1))
display_version=app_version+(f'-beta.{sequence}' if beta else '')
edition_file=project_directory/'build/edition.json'
edition_file.parent.mkdir(parents=True,exist_ok=True)
edition_file.write_text(json.dumps({'channel':channel,'beta_sequence':sequence}))
datas.append((str(edition_file),'config'))
try:
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=project_directory,text=True).strip()
except (OSError,subprocess.CalledProcessError):
    commit = 'unavailable'
build_metadata = project_directory / 'build' / 'build_metadata.json'
build_metadata.parent.mkdir(parents=True,exist_ok=True)
build_metadata.write_text(json.dumps({'commit':commit,'channel':channel,'version':display_version,'production_approved':not beta,'dependency_lock_sha256':__import__('hashlib').sha256((project_directory/'requirements-build.lock.txt').read_bytes()).hexdigest(),'built_at':datetime.now(timezone.utc).isoformat()}),encoding='utf-8')
datas.append((str(build_metadata),'config'))
version_tuple = tuple(int(part) for part in app_version.split('-')[0].split('.')) + (sequence if beta else 0,)
version_resource = VSVersionInfo(ffi=FixedFileInfo(filevers=version_tuple,prodvers=version_tuple,mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)), kids=[StringFileInfo([StringTable('040904B0',[StringStruct('FileDescription',app_name),StringStruct('FileVersion',display_version),StringStruct('ProductName',app_name),StringStruct('ProductVersion',display_version)])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])
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
    name=exe_name,
    version=version_resource,
    icon=str(project_directory / 'assets' / icon_name),
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
    name=exe_name,
)
