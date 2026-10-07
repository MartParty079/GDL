"""Read-only, metadata-only Microsoft Graph client; no content endpoint."""
import json
import time
from urllib.parse import urlparse, quote, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError


class GraphError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def transport(url, token):
    request = Request(url, headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}, method='GET')
    try:
        with build_opener(NoRedirect).open(request, timeout=30) as response:
            return response.status, dict(response.headers), json.loads(response.read(16 * 1024 * 1024 + 1))
    except HTTPError as exc:
        return exc.code, dict(exc.headers), {}
    except (URLError, OSError, ValueError):
        raise GraphError('Microsoft storage is unavailable. Check your connection or use the cached index.') from None


class MicrosoftGraphClient:
    def __init__(self, auth, request=transport, sleep=time.sleep):
        self.auth, self.request, self.sleep = auth, request, sleep
        self.drive_tiers = {}

    def register_connection(self, connection):
        self.drive_tiers[connection['drive_id']] = 'sharepoint' if connection.get('site_id') else 'files'

    def get(self, path, cancel=None, tier='basic'):
        from app.services.project_storage import IndexCancelled
        url = path if path.startswith('https://') else 'https://graph.microsoft.com/v1.0/' + path.lstrip('/')
        parsed = urlparse(url)
        # Graph nextLink is untrusted; no token may reach a different host or dataset endpoint.
        decoded = __import__('urllib.parse', fromlist=['unquote']).unquote(parsed.path).casefold()
        if parsed.scheme != 'https' or parsed.netloc != 'graph.microsoft.com' or not parsed.path.startswith('/v1.0/') or any(x in decoded.split('/') for x in ('content', '$value')):
            raise GraphError('Unsupported Microsoft metadata endpoint.')
        token = self.auth.get_access_token(tier)
        for attempt in range(4):
            if cancel and cancel():
                raise IndexCancelled('Cloud indexing cancelled. Previous index preserved.')
            try:
                status, headers, body = self.request(url, token)
            except Exception:
                raise GraphError('Microsoft storage request could not finish. Retry later; cached files remain available.') from None
            if status == 200:
                if not isinstance(body, dict):
                    raise GraphError('Microsoft returned invalid metadata.')
                return body
            if status in (429, 503) and attempt < 3:
                try:
                    delay = max(1, min(60, int(headers.get('Retry-After', headers.get('retry-after', 2 ** attempt)))))
                except (ValueError, TypeError):
                    delay = 2 ** attempt
                for _ in range(delay):
                    if cancel and cancel():
                        raise IndexCancelled('Cloud indexing cancelled. Previous index preserved.')
                    self.sleep(1)
                continue
            if status in (401, 403):
                self.auth.mark_unavailable(tier, admin=status == 403)
            message = {401: 'This Microsoft connection needs reconnecting. Local storage remains usable.', 403: 'Admin approval or library access is required for this cloud feature. Local OneDrive remains usable.',
                       404: 'The selected cloud folder is no longer available.', 429: 'Microsoft is busy. Retry the refresh later.', 503: 'Microsoft storage is temporarily unavailable.'}.get(status, 'Microsoft metadata request failed. Retry later.')
            raise GraphError(message)

    def collection(self, path, cancel=None, tier='basic'):
        records, visited = [], set()
        while path:
            if path in visited or len(visited) >= 10000:
                raise GraphError('Microsoft pagination could not finish. Previous index preserved.')
            visited.add(path)
            page = self.get(path, cancel, tier)
            values = page.get('value', [])
            if not isinstance(values, list):
                raise GraphError('Microsoft returned invalid metadata.')
            records.extend(values)
            path = page.get('@odata.nextLink')
        return records

    def get_me(self):
        return self.get('me?$select=id,displayName,userPrincipalName')

    def list_drives(self):
        rows = self.collection('me/drives?$select=id,name,webUrl,driveType', tier='files')
        self.drive_tiers.update({row['id']: 'files' for row in rows})
        return rows

    def list_sites(self, search):
        return self.collection('sites?' + urlencode({'search': search, '$select': 'id,displayName,webUrl'}), tier='sharepoint')

    def list_document_libraries(self, site_id):
        rows = self.collection('sites/' + quote(site_id, safe='') + '/drives?$select=id,name,webUrl,driveType', tier='sharepoint')
        self.drive_tiers.update({row['id']: 'sharepoint' for row in rows})
        return rows

    def list_children(self, drive_id, item_id='root', cancel=None):
        base = 'drives/' + quote(drive_id, safe='') + ('/root' if item_id == 'root' else '/items/' + quote(item_id, safe=''))
        return self.collection(base + '/children?$select=id,name,size,createdDateTime,lastModifiedDateTime,webUrl,parentReference,folder,file', cancel, self.drive_tiers.get(drive_id, 'files'))

    def get_drive_item(self, drive_id, item_id='root'):
        base = 'drives/' + quote(drive_id, safe='') + ('/root' if item_id == 'root' else '/items/' + quote(item_id, safe=''))
        return self.get(base + '?$select=id,name,size,createdDateTime,lastModifiedDateTime,webUrl,parentReference,folder,file', tier=self.drive_tiers.get(drive_id, 'files'))

    get_metadata = get_drive_item

    def get_web_url(self, drive_id, item_id):
        return self.get_drive_item(drive_id, item_id).get('webUrl', '')
