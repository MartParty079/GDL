"""Client-safe hosted accounts; Windows DPAPI sessions and bounded activity outbox.

Research content and machine paths never enter this service. No privileged key
is accepted. Roles are read from the database and checked again by admin APIs.
"""

import base64
import ctypes
import json
import os
import platform
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from app import __version__
from app.services.storage import read_json, write_json, timestamp


class AccountError(ValueError):
    pass


class ConnectionUnavailable(AccountError):
    pass


def protect(data, decrypt=False):
    """DPAPI current-user protection, with UI disabled. Fail closed elsewhere."""
    if os.name != "nt":
        raise AccountError("Persistent sign-in is available on Windows only.")
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    function = (
        ctypes.windll.crypt32.CryptUnprotectData
        if decrypt
        else ctypes.windll.crypt32.CryptProtectData
    )
    function.argtypes = [
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(Blob),
    ]
    function.restype = wintypes.BOOL
    if not function(
        ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)
    ):
        raise AccountError("Saved sign-in could not be read. Please sign in again.")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree(target.data)


class Accounts:
    def __init__(self, store, transport=None):
        self.store = store
        config = read_json(store.config_dir / "accounts_public.json", {})
        self.url = os.environ.get("SUPABASE_URL", config.get("url", "")).rstrip("/")
        self.key = os.environ.get(
            "SUPABASE_PUBLISHABLE_KEY", config.get("publishable_key", "")
        )
        if not self.url.startswith("https://") or not self.key.startswith(
            "sb_publishable_"
        ):
            raise AccountError("Account service configuration is unavailable.")
        self.transport = transport
        self.session = None
        self.profile = None
        self.offline = False
        self.validated_at = 0
        self.auth_method = "email_password"
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="activity")
        self.session_path = store.local_dir / "tokens.bin"
        self.outbox_path = store.local_dir / "pending_activity.local.json"
        self.pending = read_json(self.outbox_path, [])[-500:]
        self.install_id = store.local.setdefault("install_id", str(uuid.uuid4()))
        store.local.setdefault("install_created_at", timestamp())
        store.save_local()

    def request(self, method, path, data=None, authenticated=True, prefer=None):
        if self.transport:
            return self.transport(method, path, data)
        headers = {"apikey": self.key, "Content-Type": "application/json"}
        if authenticated:
            if not self.session:
                raise AccountError("Please sign in again.")
            headers["Authorization"] = "Bearer " + self.session["access_token"]
        if prefer:
            headers["Prefer"] = prefer
        request = Request(
            self.url + path,
            headers=headers,
            method=method,
            data=json.dumps(data).encode() if data is not None else None,
        )
        try:
            with urlopen(request, timeout=8) as response:
                body = response.read(4 * 1024 * 1024 + 1)
                if len(body) > 4 * 1024 * 1024:
                    raise AccountError("Account response could not be loaded.")
                return json.loads(body) if body else None
        except HTTPError as exc:
            logging.getLogger("gdlhub").warning("Account HTTP status %s", exc.code)
            if exc.code >= 500:
                raise ConnectionUnavailable(
                    "Unable to connect to the account service. Local research data has not been affected."
                ) from None
            if exc.code in (401, 403):
                raise AccountError(
                    "Access unavailable. Sign in again or contact the administrator."
                ) from None
            if exc.code == 400:
                raise AccountError(
                    "Unable to complete this account action. Check your details and try again."
                ) from None
            if exc.code == 429:
                raise AccountError(
                    "Too many attempts. Please wait a moment before trying again."
                ) from None
            raise AccountError(
                "The account action could not be completed. Please try again."
            ) from None
        except (URLError, TimeoutError, OSError):
            logging.getLogger("gdlhub").warning("Account connection unavailable")
            raise ConnectionUnavailable(
                "Unable to connect to the account service. Local research data has not been affected."
            ) from None

    def save_session(self):
        if self.session:
            payload = json.dumps(
                {
                    "session": self.session,
                    "profile": self.profile,
                    "validated_at": self.validated_at,
                    "auth_method": self.auth_method,
                    "url": self.url,
                }
            ).encode()
            write_json(
                self.session_path,
                {"protected": base64.b64encode(protect(payload)).decode()},
            )

    def load_profile(self, user=None, allow_provision=True):
        user = user or self.request("GET", "/auth/v1/user")
        identity = str(uuid.UUID(user["id"]))
        rows = self.request("GET", "/rest/v1/profiles?id=eq." + identity + "&select=*")
        if not rows:
            if not allow_provision:
                raise AccountError(
                    "This account needs an invitation. Contact the project administrator."
                )
            try:
                self.request(
                    "POST",
                    "/rest/v1/profiles",
                    {
                        "id": identity,
                        "email": user["email"],
                        "role": "user",
                        "active": True,
                    },
                    prefer="return=minimal",
                )
            except ConnectionUnavailable:
                raise
            except AccountError:
                raise AccountError(
                    "This account needs an invitation. Contact the project administrator."
                ) from None
            rows = self.request(
                "GET", "/rest/v1/profiles?id=eq." + identity + "&select=*"
            )
        profile = rows[0]
        if not profile.get("active") or profile.get("role") not in ("user", "admin"):
            self.session = None
            self.profile = None
            self.session_path.unlink(missing_ok=True)
            raise AccountError(
                "This GDL Research Hub account is disabled. Contact the project administrator."
            )
        self.profile = profile
        self.validated_at = time.time()
        self.offline = False
        self.save_session()
        return profile

    def sign_in(self, email, password):
        if email.strip().casefold().split("@")[-1] != "tarleton.edu":
            raise AccountError("Use your approved Tarleton email address.")
        with self.lock:
            self.auth_method = "email_password"
            self.session = self.request(
                "POST",
                "/auth/v1/token?grant_type=password",
                {"email": email.strip(), "password": password},
                False,
            )
            try:
                self.load_profile()
                self.register()
                self.event("LOGIN")
                return self.profile
            except AccountError:
                self.session = None
                self.profile = None
                self.session_path.unlink(missing_ok=True)
                raise

    def microsoft_session(self, session):
        with self.lock:
            self.session = {
                k: session[k]
                for k in ("access_token", "refresh_token", "expires_at", "token_type")
                if k in session
            }
            try:
                user = self.request("GET", "/auth/v1/user")
                if (
                    not any(
                        i.get("provider") == "azure" for i in user.get("identities", [])
                    )
                    or user.get("email", "").casefold().split("@")[-1] != "tarleton.edu"
                ):
                    raise AccountError(
                        "This account is not an approved Tarleton Microsoft identity."
                    )
                self.auth_method = "microsoft_entra"
                self.load_profile(user=user, allow_provision=False)
                self.register()
                self.event("LOGIN")
                return self.profile
            except (AccountError, KeyError):
                self.session = self.profile = None
                self.session_path.unlink(missing_ok=True)
                raise

    def refresh(self):
        with self.lock:
            if self.session.get("expires_at", 0) < time.time() + 120:
                self.session = self.request(
                    "POST",
                    "/auth/v1/token?grant_type=refresh_token",
                    {"refresh_token": self.session["refresh_token"]},
                    False,
                )
            return self.load_profile()

    def restore(self):
        if not self.session_path.exists():
            return None
        try:
            saved = json.loads(
                protect(
                    base64.b64decode(read_json(self.session_path, {})["protected"]),
                    True,
                )
            )
            self.session = saved["session"]
            if saved.get("url", self.url) != self.url:
                raise AccountError("Saved sign-in belongs to another account service.")
            self.profile = saved["profile"]
            self.validated_at = saved["validated_at"]
            self.auth_method = saved.get("auth_method", "email_password")
            try:
                self.refresh()
                self.register()
            except ConnectionUnavailable:
                if (
                    not self.profile.get("active")
                    or time.time() - self.validated_at > 86400
                ):
                    raise AccountError(
                        "Connect to the account service to sign in again."
                    )
                self.offline = True
            return self.profile
        except (ValueError, KeyError, AccountError):
            self.session = self.profile = None
            self.session_path.unlink(missing_ok=True)
            return None

    def register(self):
        self.request(
            "POST",
            "/rest/v1/installations?on_conflict=user_id,install_id",
            {
                "user_id": self.profile["id"],
                "install_id": self.install_id,
                "label": self.store.local.get(
                    "installation_label", "Research workstation"
                ),
                "platform": platform.system(),
                "app_version": __version__,
                "last_seen_at": timestamp(),
            },
            prefer="resolution=merge-duplicates,return=minimal",
        )
        previous = self.store.local.get("last_account_app_version")
        self.event("APP_STARTED")
        if previous and previous != __version__:
            self.event("APP_UPDATED", details={"previous_version": previous})
        self.store.local["last_account_app_version"] = __version__
        self.store.save_local()

    def event(self, kind, entity_type="", entity_id="", entity_name="", details=None):
        if not self.profile:
            return
        # Explicit allowlist prevents notes, paths, extracted text or tokens
        # being included by incidental caller changes.
        safe = {
            k: str(v)[:120]
            for k, v in (details or {}).items()
            if k
            in (
                "source",
                "previous_version",
                "count",
                "status",
                "fields",
                "auth_method",
            )
        }
        if kind in ("LOGIN", "LOGOUT", "APP_STARTED"):
            safe["auth_method"] = self.auth_method
        entity_name = str(entity_name)
        if "/" in entity_name or "\\" in entity_name:
            entity_name = entity_name.replace("\\", "/").rsplit("/", 1)[-1]
        with self.lock:
            self.pending.append(
                {
                    "user_id": self.profile["id"],
                    "install_id": self.install_id,
                    "event_type": kind,
                    "entity_type": entity_type[:60],
                    "entity_id": str(entity_id)[:120],
                    "entity_name": entity_name[:180],
                    "app_version": __version__,
                    "details": safe,
                    "created_at": timestamp(),
                }
            )
            self.pending = self.pending[-500:]
            write_json(self.outbox_path, self.pending)
        self.executor.submit(self.flush)

    def flush(self):
        with self.lock:
            if not self.session or not self.profile or self.offline:
                return
            batch = [e for e in self.pending if e["user_id"] == self.profile["id"]][:50]
            if not batch:
                return
            try:
                self.request(
                    "POST", "/rest/v1/activity_events", batch, prefer="return=minimal"
                )
                self.pending = [e for e in self.pending if e not in batch]
                write_json(self.outbox_path, self.pending)
            except AccountError:
                return

    def sign_out(self):
        with self.lock:
            self.event("LOGOUT")
            self.flush()
            try:
                if self.session:
                    self.request("POST", "/auth/v1/logout?scope=local")
            except AccountError:
                pass
            self.session = self.profile = None
            self.session_path.unlink(missing_ok=True)
            (self.store.local_dir / "oauth-pending.bin").unlink(missing_ok=True)

    def reset_password(self, email):
        self.request("POST", "/auth/v1/recover", {"email": email.strip()}, False)

    def set_password(self, password):
        if len(password) < 12:
            raise AccountError("Use a password with at least 12 characters.")
        self.request("PUT", "/auth/v1/user", {"password": password})

    def verify_code(self, email, token, kind="recovery"):
        self.session = self.request(
            "POST",
            "/auth/v1/verify",
            {"email": email.strip(), "token": token.strip(), "type": kind},
            False,
        )
        return self.load_profile()

    def admin(self, action, **values):
        if self.offline or not self.profile or self.profile["role"] != "admin":
            raise AccountError("Administrator access is unavailable.")
        return self.request(
            "POST", "/functions/v1/hub-admin", {"action": action, **values}
        )
