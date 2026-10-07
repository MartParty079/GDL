"""Save public registration identifiers; optionally test browser sign-in and metadata."""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.storage import read_json, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('client_id')
    parser.add_argument('tenant_id')
    parser.add_argument('--test-sign-in', action='store_true')
    args = parser.parse_args()
    import uuid
    uuid.UUID(args.client_id)
    uuid.UUID(args.tenant_id)
    profile = Path(os.environ['LOCALAPPDATA']) / 'FuelCellProjectHub'
    path = profile / 'local.json'
    local = read_json(path, {'paths': {}, 'setup_complete': False})
    config = {'client_id': args.client_id, 'tenant_id': args.tenant_id, 'authority_mode': 'organizations'}
    previous = local.get('microsoft_auth')
    if previous and previous != config:
        raise ValueError('A different registration already exists. Change it in Microsoft Account settings after signing out.')
    local['microsoft_auth'] = config
    write_json(path, local)
    print('Public registration identifiers saved in the local profile.', flush=True)
    if args.test_sign_in:
        from types import SimpleNamespace
        from app.services.microsoft_auth import MicrosoftAuth, AuthError
        from app.services.microsoft_graph import MicrosoftGraphClient, GraphError
        store = SimpleNamespace(local=local, local_dir=profile)
        auth = MicrosoftAuth(store)
        graph = MicrosoftGraphClient(auth)
        print('Opening the Microsoft browser sign-in prompt (up to 180 seconds).', flush=True)
        try:
            auth.sign_in()
            me = graph.get_me()
            print(json.dumps({'status': auth.connection_status(), 'display_name': me.get('displayName'), 'permissions': auth.permission_status()}), flush=True)
        except (AuthError, GraphError) as exc:
            print(str(exc), flush=True)
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
