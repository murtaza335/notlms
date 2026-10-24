"""Command-line entry point.

    notlms            start the local app and open the dashboard in your browser
    notlms list       print pending tasks in the terminal (uses the saved login)
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
import webbrowser

from . import __version__
from .formatting import course_label, format_due, time_left
from .moodle import MoodleClient
from .paths import data_dir
from .service import Service
from .store import ConfigStore
from .tasks import TaskCollector
from .web import App

DEFAULT_PORT = 8765


def _open_server(service: Service, port: int) -> App:
    for candidate in (port, 0):  # fall back to any free port
        try:
            return App(candidate, service)
        except OSError:
            if candidate == 0:
                raise
    raise AssertionError("unreachable")


def cmd_serve(store: ConfigStore, port: int, open_browser: bool) -> int:
    service = Service(store, data_dir() / "state.json")
    app = _open_server(service, port)
    service.start()
    print(f"notlms {__version__} is running. Open this link if your browser did not open:\n  {app.url}", flush=True)
    print("Press Ctrl+C to quit. Reminders only fire while notlms is running.", flush=True)
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(app.url,)).start()
    try:
        app.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
        app.server_close()
    return 0


def cmd_list(store: ConfigStore) -> int:
    cfg = store.config
    if not cfg.logged_in:
        print("Not logged in. Run `notlms` and log in from the dashboard first.")
        return 1
    client = MoodleClient(cfg.lms_url, legacy_tls=cfg.legacy_tls)
    client.token = cfg.token
    now = time.time()
    tasks = TaskCollector(client, section=cfg.section, lookback_days=cfg.lookback_days).collect(now)
    if not tasks:
        print("Nothing pending.")
    for task in tasks:
        print(f"[{time_left(task, now)}] {course_label(task)} - {task.name}\n  Due {format_due(task)} - {task.url}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="notlms", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"notlms {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="print pending tasks in the terminal")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    store = ConfigStore(data_dir() / "config.json")
    if args.command == "list":
        return cmd_list(store)
    return cmd_serve(store, args.port, not args.no_browser)


if __name__ == "__main__":
    sys.exit(main())
