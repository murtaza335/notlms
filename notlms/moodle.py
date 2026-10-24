"""Minimal client for the Moodle mobile web-service REST API."""

from __future__ import annotations

import json
import os
import ssl
import urllib.parse
import urllib.request
from typing import Any


class MoodleError(RuntimeError):
    pass


# Where Linux distros keep their CA bundle. A frozen binary is built on one
# distro and only knows that distro's path, so check the others too.
_CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",  # Debian, Ubuntu, Arch
    "/etc/pki/tls/certs/ca-bundle.crt",  # Fedora, RHEL
    "/etc/ssl/ca-bundle.pem",  # openSUSE
    "/etc/ssl/cert.pem",  # Alpine, macOS, BSD
)


def _trusted_context() -> ssl.SSLContext:
    """Default TLS context plus every CA bundle we can find (system, then certifi if bundled)."""
    ctx = ssl.create_default_context()
    for path in _CA_BUNDLES:
        if os.path.isfile(path):
            try:
                ctx.load_verify_locations(cafile=path)
            except (ssl.SSLError, OSError):
                continue
    try:
        import certifi  # present in the released binaries; optional when running from source

        ctx.load_verify_locations(cafile=certifi.where())
    except (ImportError, ssl.SSLError, OSError):
        pass
    return ctx


class MoodleClient:
    def __init__(self, base_url: str, *, legacy_tls: bool = False, timeout: float = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token: str | None = None
        self._ssl = _trusted_context()
        if legacy_tls:
            # Some institutional servers still require pre-RFC 5746 renegotiation,
            # which OpenSSL 3 refuses by default.
            self._ssl.options |= ssl.OP_LEGACY_SERVER_CONNECT

    def _post(self, path: str, params: dict[str, Any]) -> Any:
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl) as resp:
            body = resp.read().decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise MoodleError(f"Non-JSON response from {path}: {body[:200]!r}") from exc

    def login(self, username: str, password: str) -> None:
        result = self._post(
            "/login/token.php",
            {"username": username, "password": password, "service": "moodle_mobile_app"},
        )
        if "token" not in result:
            raise MoodleError(f"Login failed: {result.get('error') or result}")
        self.token = result["token"]

    def call(self, function: str, **params: Any) -> Any:
        if not self.token:
            raise MoodleError("Not logged in")
        payload = {"wstoken": self.token, "wsfunction": function, "moodlewsrestformat": "json"}
        payload.update(_flatten(params))
        result = self._post("/webservice/rest/server.php", payload)
        if isinstance(result, dict) and "exception" in result:
            raise MoodleError(f"{function}: {result.get('errorcode')}: {result.get('message')}")
        return result


def _flatten(params: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Encode nested lists/dicts the way Moodle expects: courseids[0]=1&courseids[1]=2."""
    flat: dict[str, Any] = {}
    for key, value in params.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(_flatten(value, name))
        elif isinstance(value, (list, tuple)):
            flat.update(_flatten(dict(enumerate(value)), name))
        elif isinstance(value, bool):
            flat[name] = int(value)
        elif value is not None:
            flat[name] = value
    return flat
