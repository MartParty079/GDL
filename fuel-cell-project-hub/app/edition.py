"""Immutable packaged edition metadata; source development defaults to Beta."""
import json
import sys
from pathlib import Path
from app.version import VERSION

root = Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
metadata = root / 'config/edition.json'
EDITION = json.loads(metadata.read_text()) if metadata.exists() else {'channel':'beta','beta_sequence':1}
CHANNEL = EDITION['channel']
if CHANNEL not in ('beta','stable'):raise ValueError('Unknown application edition')
BETA = CHANNEL == 'beta'
APP_NAME = 'GDL Research Hub Beta' if BETA else 'GDL Research Hub'
PROFILE_NAME = 'FuelCellProjectHubBeta' if BETA else 'FuelCellProjectHub'
PROTOCOL = 'gdlresearchhubbeta' if BETA else 'gdlresearchhub'
EXECUTABLE = 'GDLResearchHubBeta' if BETA else 'FuelCellProjectHub'
DISPLAY_VERSION = VERSION + (f"-beta.{EDITION.get('beta_sequence',1)}" if BETA else '')
ASSET_NAME = 'GDLResearchHubBeta-Setup.exe' if BETA else 'GDLResearchHub-Setup.exe'
