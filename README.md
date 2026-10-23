# lms-notifier

Watches the NUST LMS (Moodle) for activities you haven't submitted yet and
reminds you before they're due, via push notification, Telegram, email or
WhatsApp.

## How it works

```
login (moodle_mobile_app token)
  -> core_calendar_get_action_events_by_timesort   # everything still awaiting action
  -> filter by your section                        # combined courses post one link per section
  -> verify completion                             # mod_assign_get_submission_status / mod_quiz_get_user_attempts
  -> pick reminder stage                           # first seen, 72h, 24h, 6h, 1h, overdue
  -> skip stages already sent (.state/state.json)
  -> send one digest per run to each channel
```

It talks to Moodle's official web-service API (the one the Moodle mobile app
uses), so there is no browser automation or HTML scraping. It uses only the
Python standard library.

Overdue assignments are still reported, once, while the assignment accepts
late submissions (no cut-off date, or before the cut-off).

## Setup

Requires Python 3.12+.

```bash
cp .env.example .env      # fill in LMS_USERNAME, LMS_PASSWORD, LMS_SECTION
chmod 600 .env
python3 -m lms_notifier list            # see what's pending
python3 -m lms_notifier run --dry-run   # see what would be sent
```

### Notification channels

Set `NOTIFIERS` to a comma-separated list, then check them with
`python3 -m lms_notifier test-notify`.

| Channel    | Setup                                                                                         |
|------------|-----------------------------------------------------------------------------------------------|
| `ntfy`     | Install the ntfy app, subscribe to a long random topic, and set `NTFY_TOPIC`. No account needed. |
| `telegram` | Create a bot with @BotFather, message it once, then get your chat id from `getUpdates`.        |
| `email`    | SMTP. For Gmail, enable 2FA and create an App Password.                                       |
| `whatsapp` | Register with [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/) to get an API key. |
| `console`  | Prints to stdout. Useful for testing.                                                         |

## Scheduling

### systemd user timer (Linux)

```bash
mkdir -p ~/.config/systemd/user
cp deploy/lms-notifier.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now lms-notifier.timer
loginctl enable-linger "$USER"     # keep running while logged out
journalctl --user -u lms-notifier  # logs
```

Edit `WorkingDirectory` in the service file if the repo lives elsewhere.

## Development

```bash
python3 -m unittest discover -s tests
```

## Notes

- `lms.nust.edu.pk` only supports legacy TLS renegotiation, which OpenSSL 3
  rejects by default. `LMS_LEGACY_TLS=true` opts into it for LMS requests only.
- Asking Moodle for an assignment's submission status creates an empty
  submission record (status `new`) if none exists. Opening the assignment page
  in a browser does the same, and it does not count as submitting.
