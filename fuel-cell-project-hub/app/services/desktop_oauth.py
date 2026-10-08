"""PKCE desktop return over a per-user Qt local pipe, never an HTTP listener."""

import base64
import hashlib
import json
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import HTTPError, URLError
from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from app.services.accounts import AccountError, protect
from app.services.storage import read_json, write_json

CALLBACK = "gdlresearchhub://auth/callback"
TENANT = "2c5ee638-a963-49c0-ac26-828dd9b78d5e"
CLIENT = "16fbe099-c7ed-4da8-94bf-d8abc1c4c5ec"


def callback_values(uri):
    if len(uri) > 4096:
        raise AccountError(
            "This sign-in return is unavailable. Start Microsoft sign-in again."
        )
    parsed = urlparse(uri)
    if (parsed.scheme, parsed.netloc, parsed.path) != (
        "gdlresearchhub",
        "auth",
        "/callback",
    ) or parsed.fragment:
        raise AccountError(
            "This sign-in return is unavailable. Start Microsoft sign-in again."
        )
    values = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=12)
    if any(len(v) != 1 for v in values.values()) or set(values) - {
        "code",
        "error",
        "error_code",
        "error_description",
    }:
        raise AccountError(
            "This sign-in return is unavailable. Start Microsoft sign-in again."
        )
    return {k: v[0] for k, v in values.items()}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class MicrosoftLogin:
    def __init__(self, accounts):
        self.accounts = accounts
        self.path = accounts.store.local_dir / "oauth-pending.bin"

    def cancel(self):
        self.path.unlink(missing_ok=True)

    def begin(self):
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        self.cancel()
        query = urlencode(
            {
                "provider": "azure",
                "scopes": "email",
                "redirect_to": CALLBACK,
                "code_challenge": challenge,
                "code_challenge_method": "s256",
            }
        )
        request = Request(
            self.accounts.url + "/auth/v1/authorize?" + query,
            headers={"apikey": self.accounts.key},
        )
        try:
            response = build_opener(NoRedirect).open(request, timeout=8)
            response.close()
            raise AccountError(
                "Microsoft sign-in is unavailable. Use email and password or try again later."
            )
        except HTTPError as exc:
            if exc.code != 302:
                raise AccountError(
                    "Microsoft sign-in is unavailable. Use email and password or try again later."
                ) from None
            location = exc.headers.get("Location", "")
        except (URLError, TimeoutError, OSError):
            raise AccountError(
                "Microsoft sign-in is unavailable. Use email and password or try again later."
            ) from None
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "login.microsoftonline.com"
            or parsed.path != f"/{TENANT}/oauth2/v2.0/authorize"
            or params.get("client_id") != [CLIENT]
            or params.get("redirect_uri") != [self.accounts.url + "/auth/v1/callback"]
            or set(params.get("scope", [""])[0].split())
            - {"openid", "email", "profile"}
        ):
            raise AccountError(
                "Microsoft sign-in configuration needs administrator attention. Use email and password."
            )
        payload = {
            "verifier": verifier,
            "created_at": time.time(),
            "url": self.accounts.url,
        }
        write_json(
            self.path,
            {
                "protected": base64.b64encode(
                    protect(json.dumps(payload).encode())
                ).decode()
            },
        )
        return location

    def complete(self, uri):
        values = callback_values(uri)
        try:
            saved = json.loads(
                protect(base64.b64decode(read_json(self.path, {})["protected"]), True)
            )
            valid = (
                saved["url"] == self.accounts.url
                and 0 <= time.time() - saved["created_at"] <= 600
            )
        except (ValueError, KeyError, AccountError):
            valid = False
        if not valid:
            raise AccountError(
                "This sign-in return expired or belongs to another attempt. Start Microsoft sign-in again."
            )
        if "error" in values:
            self.cancel()
            raise AccountError(
                "Microsoft sign-in was not completed. Use email and password or try again."
            )
        code = values.get("code", "")
        if not code or len(code) > 2048:
            raise AccountError(
                "This sign-in return is unavailable. Start Microsoft sign-in again."
            )
        session = self.accounts.request(
            "POST",
            "/auth/v1/token?grant_type=pkce",
            {"auth_code": code, "code_verifier": saved["verifier"]},
            False,
        )
        self.cancel()
        return self.accounts.microsoft_session(session)


class CallbackBroker(QObject):
    received = Signal(str)

    def __init__(self, directory, parent=None):
        super().__init__(parent)
        digest = hashlib.sha256(
            str(directory.resolve()).casefold().encode()
        ).hexdigest()[:32]
        self.name = "gdl-research-hub-" + digest
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        self.server.newConnection.connect(self.accept_connection)
        self.buffers = {}

    def forward(self, uri):
        callback_values(uri)
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        if not socket.waitForConnected(400):
            return False
        socket.write((json.dumps(uri) + "\n").encode())
        socket.flush()
        if socket.bytesToWrite() and not socket.waitForBytesWritten(1000):
            socket.abort()
            return False
        delivered = (socket.bytesAvailable() > 0 or socket.waitForReadyRead(2000)) and bytes(socket.readAll()) == b"OK\n"
        socket.disconnectFromServer()
        return delivered

    def listen(self):
        return self.server.listen(self.name)

    def accept_connection(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self.buffers[socket] = b""
            socket.readyRead.connect(lambda s=socket: self.read(s))
            socket.disconnected.connect(lambda s=socket: self.discard(s))
            self.read(socket)

    def discard(self, socket):
        self.buffers.pop(socket, None)
        from shiboken6 import isValid
        if isValid(socket):
            socket.deleteLater()

    def read(self, socket):
        data = self.buffers.get(socket, b"") + bytes(socket.readAll())
        if len(data) > 8192:
            socket.abort()
            return
        self.buffers[socket] = data
        if b"\n" in data:
            try:
                uri = json.loads(data.split(b"\n", 1)[0])
                if not isinstance(uri, str):
                    raise ValueError()
                callback_values(uri)
                self.received.emit(uri)
                socket.write(b"OK\n")
                socket.flush()
                self.buffers[socket] = b""
            except (ValueError, AccountError):
                socket.disconnectFromServer()
