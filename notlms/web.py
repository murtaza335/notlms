"""Loopback-only HTTP server: serves the dashboard and a small JSON API.

Every request must carry the per-launch secret, and the Host header must be a
loopback name, so other websites or local users cannot drive the app.
"""

from __future__ import annotations

import hmac
import json
import logging
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import desktop
from .sections import parse_section
from .moodle import MoodleClient, MoodleError
from .service import Service

log = logging.getLogger(__name__)
_INDEX = Path(__file__).with_name("ui") / "index.html"
_MAX_BODY = 64 * 1024


class App(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int, service: Service):
        self.service = service
        self.secret = secrets.token_urlsafe(24)
        super().__init__(("127.0.0.1", port), Handler)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/#{self.secret}"


class Handler(BaseHTTPRequestHandler):
    server: App

    def log_message(self, fmt: str, *args) -> None:
        log.debug(fmt, *args)

    # -- plumbing ----------------------------------------------------------
    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in {"127.0.0.1", "localhost"}

    def _authorized(self) -> bool:
        given = self.headers.get("X-Notlms-Token", "")
        return hmac.compare_digest(given, self.server.secret)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > _MAX_BODY:
            raise ValueError("request too large")
        return json.loads(self.rfile.read(length) or b"{}")

    # -- routes ------------------------------------------------------------
    def do_GET(self) -> None:
        if not self._host_ok():
            return self._json(403, {"error": "bad host"})
        path = urlparse(self.path).path
        if path == "/":
            return self._send(200, _INDEX.read_bytes(), "text/html; charset=utf-8")
        if path == "/api/status" and self._authorized():
            return self._json(200, self.server.service.status())
        if path.startswith("/api/"):
            return self._json(401, {"error": "unauthorized"})
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._host_ok() or not self._authorized():
            return self._json(401, {"error": "unauthorized"})
        route = urlparse(self.path).path
        service = self.server.service
        try:
            data = self._body()
            if route == "/api/login":
                return self._login(data)
            if route == "/api/settings":
                return self._settings(data)
            if route == "/api/hide":
                cmid, name = str(int(data["cmid"])), str(data.get("name", ""))[:200]
                if data.get("hidden", True):
                    service.store.config.hidden[cmid] = name
                else:
                    service.store.config.hidden.pop(cmid, None)
                service.store.save()
                service.sync_soon()
                return self._json(200, {"ok": True})
            if route == "/api/sync":
                service.sync_soon()
                return self._json(200, {"ok": True})
            if route == "/api/test-notification":
                desktop.notify("notlms", "Desktop notifications are working.")
                return self._json(200, {"ok": True})
            if route == "/api/logout":
                service.store.forget()
                service.snapshot.tasks = []
                service.snapshot.synced_at = 0
                service.state_path.unlink(missing_ok=True)
                return self._json(200, {"ok": True})
        except (ValueError, RuntimeError, MoodleError, OSError) as exc:
            return self._json(400, {"error": str(exc)})
        self._json(404, {"error": "not found"})

    def _login(self, data: dict) -> None:
        store = self.server.service.store
        cfg = store.config
        lms_url = str(data.get("lms_url") or cfg.lms_url).strip().rstrip("/")
        if not lms_url.startswith("https://"):
            raise ValueError("The LMS address must start with https://")
        username, password = str(data.get("username", "")).strip(), str(data.get("password", ""))
        if not username or not password:
            raise ValueError("Enter your LMS username and password.")
        no_sections = bool(data.get("no_sections"))
        section = "" if no_sections else parse_section(str(data.get("section", "")))
        client = MoodleClient(lms_url, legacy_tls=cfg.legacy_tls)
        client.login(username, password)  # password goes nowhere else and is not kept
        cfg.lms_url, cfg.username, cfg.token = lms_url, username, client.token or ""
        cfg.section, cfg.no_sections = section, no_sections
        store.save()
        self.server.service.sync_soon()
        self._json(200, {"ok": True})

    def _settings(self, data: dict) -> None:
        service = self.server.service
        cfg = service.store.config
        if "no_sections" in data or "section" in data:
            no_sections = bool(data.get("no_sections", cfg.no_sections))
            section = "" if no_sections else parse_section(str(data.get("section", cfg.section)))
            cfg.section, cfg.no_sections = section, no_sections
        if "ignore_words" in data:
            cfg.ignore_words = [w.strip() for w in data["ignore_words"] if str(w).strip()][:50]
        if "remind_hours" in data:
            hours = sorted({int(h) for h in data["remind_hours"] if 0 < int(h) <= 24 * 30}, reverse=True)
            cfg.remind_hours = hours
        if "poll_minutes" in data:
            cfg.poll_minutes = min(max(int(data["poll_minutes"]), 5), 240)
        if "desktop_notifications" in data:
            cfg.desktop_notifications = bool(data["desktop_notifications"])
        service.store.save()
        service.sync_soon()
        self._json(200, {"ok": True})
