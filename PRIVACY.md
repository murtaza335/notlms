# Privacy

notlms runs entirely on your own computer. This page says exactly what it
does with your data, so you can check it against the code.

**What we collect:** nothing. There is no notlms server, no account, no
analytics, no telemetry and no crash reporting. The authors never receive any
of your data.

**Network connections notlms makes:**

1. To your LMS (the address you enter, e.g. `https://lms.nust.edu.pk`): to log
   in and to read your pending tasks. See [`notlms/moodle.py`](notlms/moodle.py)
   and [`notlms/tasks.py`](notlms/tasks.py).
2. Nothing else. Desktop notifications are raised locally by your operating
   system ([`notlms/desktop.py`](notlms/desktop.py)).

(The download page on GitHub Pages asks GitHub's public API for the list of
releases. That happens in your browser when you visit the site, not in the app.)

**Your password:** sent only to your LMS, once, to obtain an access token. It
is not written to disk and not kept in memory after login
([`notlms/web.py`](notlms/web.py), `_login`).

**Your token:** stored in `config.json` in your user data folder, readable
only by your account where the OS supports it:

- Linux: `~/.config/notlms/`
- macOS: `~/Library/Application Support/notlms/`
- Windows: `%APPDATA%\notlms\`

A Moodle token can do what the Moodle mobile app can do for your account, so
treat that folder as sensitive. To remove it: click **Forget everything and
log out** in the app, or delete the folder. To invalidate the token itself, go
to your LMS: *Preferences → Security keys → Reset* for the mobile service.

**Local web page:** the dashboard is served on `127.0.0.1` only (not reachable
from other computers), and every request needs a secret generated at launch.

**Verify it yourself:** the source is small and has no third-party
dependencies. Release binaries carry build provenance attestations tying each
file to a commit in this repository (`gh attestation verify <file> --repo
<owner>/<repo>`) and a `SHA256SUMS` file.
