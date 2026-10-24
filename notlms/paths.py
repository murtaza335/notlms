"""Per-user locations for notlms data."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("NOTLMS_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "notlms"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "notlms"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "notlms"
    base.mkdir(parents=True, exist_ok=True)
    return base
