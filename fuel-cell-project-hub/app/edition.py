"""Immutable packaged edition metadata; source development defaults to Beta."""
import json
import os
from datetime import datetime, timezone
import sys
from pathlib import Path
from app.version import VERSION

root = Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
metadata = root / 'config/edition.json'
EDITION = json.loads(metadata.read_text()) if metadata.exists() else {'channel':'beta','beta_sequence':1}
CHANNEL = EDITION['channel'] if getattr(sys, 'frozen', False) else os.environ.get('GDL_HUB_CHANNEL', 'development')
if CHANNEL not in ('development','beta','stable'):raise ValueError('Unknown application edition')
DEVELOPMENT = CHANNEL == 'development'
BETA = CHANNEL != 'stable'
APP_NAME = 'GDL Research Hub Development' if DEVELOPMENT else ('GDL Research Hub Beta' if BETA else 'GDL Research Hub')
PROFILE_NAME = 'FuelCellProjectHubDevelopment' if DEVELOPMENT else ('FuelCellProjectHubBeta' if BETA else 'FuelCellProjectHub')
PROTOCOL = 'gdlresearchhubdevelopment' if DEVELOPMENT else ('gdlresearchhubbeta' if BETA else 'gdlresearchhub')
EXECUTABLE = 'GDLResearchHubBeta' if BETA else 'FuelCellProjectHub'
DISPLAY_VERSION = VERSION + (('-dev.' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')) if DEVELOPMENT else (f"-beta.{EDITION.get('beta_sequence',1)}" if BETA else ''))
ASSET_NAME = 'GDLResearchHubDevelopment-Setup.exe' if DEVELOPMENT else ('GDLResearchHubBeta-Setup.exe' if BETA else 'GDLResearchHub-Setup.exe')
