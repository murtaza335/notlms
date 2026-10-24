# Distribution design: open-source, runs on the student's laptop

Status: **decision + plan, no code yet**. Last updated 2026-10-24.
Supersedes the server-side options in [MULTI_USER_DESIGN.md](MULTI_USER_DESIGN.md);
we are going with its "on-device" branch.

## 1. Decision

**A local web app, shipped as a single downloadable executable per platform.**

The user downloads one file, double-clicks it, and a browser tab opens at
`http://127.0.0.1:<port>` showing setup and the pending-tasks dashboard. A
small background process keeps running, polls the LMS, and sends reminders.
Nothing ever leaves the laptop except calls to the LMS and to the notification
channel the student chose.

### Why not a desktop framework (Electron / Tauri)?

| | Local web app (chosen) | Electron | Tauri |
|---|---|---|---|
| Reuses current code | Yes, the Python package as-is, stdlib only | Rewrite in JS or bundle Python as a sidecar | Rewrite in Rust/JS or sidecar |
| Download size | ~10-15 MB | 80-150 MB | 5-15 MB |
| Build toolchain | PyInstaller | node + electron-builder | Rust + node + per-OS webview deps |
| Auditability | One small Python tree, no npm | Large dependency tree | Rust + JS trees |
| Native feel | Browser tab | Real window | Real window |

The tool is a background reminder, not an app people sit in. A browser tab for
setup and "what's pending" is enough, the code stays tiny enough that a student
can actually audit it, and we keep zero third-party runtime dependencies, which
is the strongest possible answer to "what is this code doing with my password".
A tray icon (optional) can be added later without changing the architecture.

## 2. Architecture

```
 lms-notifier (one process)
 ├─ HTTP server on 127.0.0.1 only (stdlib http.server) ── dashboard + setup UI
 ├─ Scheduler thread: every N min → Moodle API → reminders.py → notifiers/
 └─ Local store (per-user config dir, 0600): config.json, state.json
```

- Reuses `moodle.py`, `sections.py`, `reminders.py`, `notifiers/` unchanged.
  New code: `lms_notifier/web/` (server + static HTML/JS) and a scheduler loop.
- UI: plain HTML + a little vanilla JS. No build step, no framework.
- Binds to `127.0.0.1` only, random-free fixed port with fallback; requests
  require a per-launch token in the URL to stop other local sites or users from
  poking it (also checks `Host`/`Origin` to block DNS-rebinding).
- UI screens: first-run setup (LMS URL, login, section, channel) → dashboard
  (pending tasks sorted by due date, next reminders, last sync) → settings
  (channel, reminder stages, "send test notification", "forget everything").

### Credentials handling

Preferred order, shown honestly in the UI:

1. Use the password **once** to call `login/token.php`, then discard it and
   store only the token in the OS keychain (Windows Credential Manager,
   macOS Keychain, Secret Service on Linux) via a thin wrapper around the
   `security` / `secret-tool` / `cmdkey` tools, with a `0600` file fallback.
   No new dependency is needed.
2. Tell the user plainly that a Moodle token can do what the Moodle app can do
   (see MULTI_USER_DESIGN §3), is revocable under *Preferences → Security
   keys*, and never leaves the device.
3. "Forget everything" button deletes token and config.

### Staying alive

Reminders only fire while the process runs. First-run offers "Start
automatically when I log in", implemented per OS: a Startup-folder shortcut /
`HKCU\...\Run` entry (Windows), a LaunchAgent plist (macOS), an XDG autostart
`.desktop` or systemd user unit (Linux). A laptop that is asleep sends nothing;
on wake the scheduler catches up and sends overdue stage reminders once. This
limitation goes on the download page, not buried.

## 3. Packaging and release

- **Build:** PyInstaller `--onefile` per OS, driven by a GitHub Actions matrix:
  `windows-latest` → `lms-notifier-windows-x64.exe`, `macos-14` (arm64) and
  `macos-13` (x64) → `.dmg`/`.zip`, `ubuntu-22.04` → `lms-notifier-linux-x64`
  (+ optional AppImage). Build on the oldest practical OS image for glibc
  compatibility.
- **Release flow:** push tag `vX.Y.Z` → CI builds all targets → attaches
  binaries plus `SHA256SUMS` to a GitHub Release. Use GitHub's artifact
  attestations (Sigstore build provenance) so users can verify that a binary
  was built from a specific commit of the public repo.
- **Reproducibility/audit:** pinned Python version and pinned PyInstaller in
  CI; docs explain "build it yourself in three commands".
- **Legacy TLS:** the LMS needs OpenSSL legacy renegotiation. The bundled
  Python's OpenSSL must be tested against the live site per platform; this is
  the most likely thing to break and gets a CI smoke test (`lms-notifier
  check-tls`).

### The unsigned-binary problem (the real UX risk)

| OS | Unsigned behavior | Mitigation |
|---|---|---|
| Windows | SmartScreen "unknown publisher" warning (More info → Run anyway) | Document with screenshots. Later: free code signing via SignPath Foundation for OSS, or Azure Trusted Signing. |
| macOS | Gatekeeper blocks; right-click → Open, or System Settings → Allow | Document. Proper fix needs an Apple Developer account ($99/yr) for signing + notarization. |
| Linux | None; needs `chmod +x` | Ship `.tar.gz` with a launcher, or AppImage. |

Plan: ship v0.x unsigned with clear instructions, and treat Windows signing as
the first thing to fix once there are real users. Because the project is open
source, the "verify the checksum / attestation" path doubles as the trust story.

## 4. GitHub Pages site (`/site`, deployed by Actions)

Static, no framework. Sections:

1. **Hero:** one sentence, one big **Download for <your OS>** button (detected
   from `navigator.userAgent`, with an "other platforms" link).
2. **Downloads table:** version selector (latest + older), per-platform
   buttons, size, SHA-256, "verify" link. Populated at load from the GitHub
   Releases API (`/repos/<org>/<repo>/releases`), so publishing a release
   updates the page with no site rebuild; falls back to a link to the Releases
   page if the API call fails.
3. **How it works:** a diagram of laptop ↔ LMS ↔ your notification channel,
   with "no server of ours in this picture".
4. **Privacy & trust declaration** (also `PRIVACY.md` in the repo):
   - We run no servers and receive no data. There is no analytics or telemetry.
   - Your password is used once to obtain a token and is never stored; the
     token lives in your OS keychain.
   - The only network calls are to your LMS and the notification service you
     pick. Link to the exact source files that do this.
   - How to audit, verify a download, and revoke the token.
5. **Setup walkthrough** with screenshots per notification channel.
6. **FAQ:** laptop asleep, unsigned warning, uninstall, other universities.
7. **Changelog** rendered from release notes.

## 5. Implementation order

1. Refactor: config in a per-user dir (not `.env`), `serve` command, scheduler
   loop with catch-up, state persistence. Keep existing CLI.
2. Local web UI (setup, dashboard, settings, test notification).
3. Token-based auth + keychain storage; drop stored passwords.
4. Autostart helpers per OS.
5. PyInstaller spec + CI matrix + release workflow + checksums/attestation.
6. GitHub Pages site + `PRIVACY.md` + `SECURITY.md`.
7. Manual test on real Windows, macOS and Linux machines, especially TLS and
   autostart. Then Windows signing.

## 6. Open questions

- Is a tray icon needed in v1? (Recommendation: no, add after feedback.)
- Which notification channels are in the first release? ntfy and Telegram need
  nothing but a topic/bot token; email needs SMTP details; WhatsApp is the
  awkward one. (Recommendation: ntfy, Telegram, email first.)
- Do we have, or want, a macOS developer account?
- Project name and GitHub org, since they appear in release URLs and the site.
