# notlms

A small app that runs **on your own computer** and shows the Moodle LMS tasks
you haven't submitted yet, with desktop reminders before they're due.

- No notlms server exists. Nothing is uploaded anywhere.
- Your password is sent only to your LMS, once, to get an access token. It is
  never saved. The token is stored in a file on your computer; "Forget
  everything" deletes it.
- Open source, standard library only (no third-party dependencies), so the
  whole thing is auditable.

## Download

Get the latest build for Windows, macOS or Linux from the project's GitHub Pages
site (or the Releases page). Privacy details: [PRIVACY.md](PRIVACY.md).

## Run from source

Requires Python 3.12+ (downloadable single-file builds are planned, see
[docs/DISTRIBUTION_DESIGN.md](docs/DISTRIBUTION_DESIGN.md)).

```bash
python3 -m notlms          # starts the app and opens http://127.0.0.1:8765
python3 -m notlms list     # print pending tasks in the terminal
```

Log in from the page that opens. Keep notlms running: reminders fire only
while it is running and your computer is awake.

Data lives in `~/.config/notlms` (Linux), `~/Library/Application Support/notlms`
(macOS) or `%APPDATA%\notlms` (Windows). Override with `NOTLMS_HOME`.

## How it works

```
login (moodle_mobile_app token)
  -> core_calendar_get_action_events_by_timesort   # everything still awaiting action
  -> filter by your section                        # combined courses post one link per section
  -> verify completion                             # mod_assign_get_submission_status / mod_quiz_get_user_attempts
  -> pick reminder stage                           # first seen, 72h, 24h, 6h, 1h, overdue
  -> skip stages already sent
  -> one desktop notification per sync
```

It uses Moodle's official web-service API (the one the mobile app uses), no
scraping. The local web page listens on `127.0.0.1` only, and every request
needs a secret generated at launch.

Desktop notifications use `notify-send` (Linux; install libnotify), AppleScript
(macOS) and a PowerShell toast (Windows). The Windows path is not yet tested on
a real machine.

## Development

```bash
python3 -m unittest discover -s tests
```

## Notes

- `lms.nust.edu.pk` only supports legacy TLS renegotiation, which OpenSSL 3
  rejects by default; notlms opts into it for LMS requests only.
- Asking Moodle for an assignment's submission status creates an empty
  submission record (status `new`) if none exists. Opening the assignment page
  in a browser does the same, and it does not count as submitting.

## Releases

Pushing a tag `vX.Y.Z` (must equal `notlms.__version__`) runs
`.github/workflows/release.yml`: tests, PyInstaller builds for Linux, macOS
(Apple silicon and Intel) and Windows, a smoke test of each binary, then a
GitHub Release with the files, `SHA256SUMS` and build provenance attestations.

```bash
git tag v0.1.0 && git push origin v0.1.0
gh attestation verify <file> --repo <owner>/<repo>   # verify a download
```

Build one locally: `pip install pyinstaller && pyinstaller packaging/notlms.spec`
(output in `dist/`). The binaries are unsigned for now, so Windows SmartScreen
and macOS Gatekeeper will warn on first launch.
