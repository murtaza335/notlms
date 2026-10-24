"""Native desktop notifications, using each OS's built-in tooling (no dependencies)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

_WINDOWS_SCRIPT = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent('ToastText02')
$text = $xml.GetElementsByTagName('text')
$text.Item(0).AppendChild($xml.CreateTextNode($env:NOTLMS_TITLE)) | Out-Null
$text.Item(1).AppendChild($xml.CreateTextNode($env:NOTLMS_BODY)) | Out-Null
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($xml))
"""

_MAC_SCRIPT = "on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv)\nend run"


def notify(title: str, body: str) -> None:
    """Show a desktop notification. Raises RuntimeError when the OS refuses or lacks support."""
    try:
        if sys.platform == "win32":
            env = {**os.environ, "NOTLMS_TITLE": title, "NOTLMS_BODY": body}
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", _WINDOWS_SCRIPT]
            subprocess.run(cmd, env=env, check=True, capture_output=True, timeout=20)
        elif sys.platform == "darwin":
            subprocess.run(["osascript", "-e", _MAC_SCRIPT, title, body], check=True, capture_output=True, timeout=20)
        elif shutil.which("notify-send"):
            subprocess.run(
                ["notify-send", "--app-name=notlms", "--urgency=normal", title, body],
                check=True, capture_output=True, timeout=20,
            )
        else:
            raise RuntimeError("notify-send not found (install libnotify)")
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError(f"desktop notification failed: {exc}") from exc
