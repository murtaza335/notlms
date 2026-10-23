# Multi-user design: options for making lms-notifier usable by anyone

Status: **proposal, no code yet**. Last updated 2026-10-24.

The current tool is a single-user CLI: one student's username and password in
a `.env` file, run on that student's machine. This document lists the ways to
turn it into something any student can use. It covers how each user's data is
fetched, where the tool runs, and how we deal with the fact that students
(rightly) do not want to hand their LMS password to a stranger's server.

---

## 1. Goals and non-goals

**Goals**

- Any NUST student can get reminders for *their own* unsubmitted work, with no
  programming knowledge.
- Students should be able to use it **without giving us their password**, and
  ideally without giving us anything that lets us act as them.
- Reminders arrive even when the student's laptop is closed. This is the
  hard part.
- Section-aware: no reminders for other sections' submission links.
- Works for other Moodle-based universities with only configuration changes.

**Non-goals**

- Submitting work, reading grades, or anything other than "what is still
  pending and when is it due".
- Replacing the LMS or Moodle's own notifications.

---

## 2. What we verified about lms.nust.edu.pk

All of these were checked against the live site on 2026-10-24. Every design
below depends on them, so re-check before building.

| Fact | Value | Why it matters |
|---|---|---|
| Platform | Moodle 5.1.1 | Same API as every modern Moodle, so the tool generalizes. |
| Mobile web services | Enabled (`moodle_mobile_app` service) | Clean JSON API, no scraping needed. |
| Login type (`typeoflogin`) | `1`: in-app username/password | `login/token.php` with a password works. SSO-only sites would not allow this. |
| QR-code login (`tool_mobile_qrcodetype`) | `2`: QR login **enabled** | Possible password-free sign-in (see A3). |
| CORS on `/webservice/rest/server.php` and `/login/token.php` | `Access-Control-Allow-Origin: *` | A web page or extension running in the student's browser can call the LMS directly. |
| Calendar export token (`core_calendar_get_calendar_export_token`) | Available to students | Password-free, read-only iCal feed (see A5). |
| iCal feed contents | All course events, **including already-submitted ones**; no activity URL | The iCal feed alone cannot tell "submitted" from "pending". |
| Action events (`core_calendar_get_action_events_by_timesort`) | Returns only items still needing action | The single most useful call; usually enough on its own. |
| Built-in Moodle notifications | `assign_due_soon`, `assign_overdue`, `assign_due_digest`, `quiz_open_soon` exist and are enabled for **web + email** | Moodle already sends some reminders. Our value-add is section filtering, Telegram/WhatsApp/push, and better timing. |
| Mobile push (Airnotifier) | **Not enabled** (only `popup` and `email` processors) | The official Moodle app will not push these reminders to phones. |
| TLS | Server needs legacy renegotiation; OpenSSL 3 refuses by default | Every hosting platform's HTTP stack must be tested (see §9). |
| DNS | Public IP `111.68.101.225`; on campus it resolves to `172.16.0.122` | Reachable from the internet, so cloud hosting is possible in principle. Not yet tested from cloud IPs. |
| Section tagging | Combined courses (e.g. `CS-337 … ABC`) post one link per section: `sec_B`, `Section A`, `BSCS-14C`, `BSCS 14-D` | Each user needs a section setting, or we infer it. |

---

## 3. The trust problem, precisely

There are four kinds of secret that could give us access. They are very
different in how much power they hand over.

| Secret | How a student gets it | What it lets the holder do | Revocable by student? |
|---|---|---|---|
| **Password** | They already have it | Everything: LMS, and often other NUST systems (shared credentials, possibly NUST email via the same identity) | Only by changing the password |
| **Mobile web-service token** (`moodle_mobile_app`) | `login/token.php`, QR login, or the Moodle app | Everything the Moodle app can do: read courses, **submit assignments, post in forums, send messages**. Combined with the private token it can mint a web session (`tool_mobile_get_autologin_key`). | Usually via *Preferences → Security keys → Reset*; changing password may or may not revoke it (admin setting `passwordchangetokendeletion`) |
| **Browser session cookie** | Already logged in | Same as the password, until it expires | Logging out |
| **Calendar export token** (iCal URL) | *Calendar → Export → Get calendar URL*, or the API | **Read calendar events only.** Cannot submit, read grades or post. | Regenerate the export token |

Key consequences:

1. **A token is not much safer than a password.** It doesn't expose the
   password itself, and it doesn't work for other NUST systems, but within the
   LMS it is effectively full account access. We should say this honestly in
   the UI.
2. **The only truly limited secret is the iCal URL**, and it cannot see
   submission status.
3. **A truly limited token needs NUST IT.** Only a Moodle admin can create a
   custom web service restricted to read-only functions.
4. So the real choices are: *don't send anything to a server* (on-device
   designs), *send only the iCal URL* (limited but lossy), or *send a token
   and earn trust* (open source, encryption, minimal retention).

---

## 4. Access methods: how the tool gets a student's data

### A1. Store the password on our server

The server keeps username and password and logs in whenever needed.

- Pros: simplest; recovers by itself from token expiry.
- Cons: the worst trust model. A breach exposes passwords that are likely
  reused for other NUST systems. Students are right to refuse.
- Verdict: **do not offer this.**

### A2. Password typed once, exchanged for a token, password discarded

The onboarding form posts the password to our server. The server calls
`login/token.php`, keeps only the token, and never stores the password.

- Pros: easy UX; works with the current code almost unchanged.
- Cons: the password still passes through our server, and students can't
  verify that we discard it. The token is still full account access.
- Verdict: acceptable only as a fallback. Prefer A4.

### A3. QR-code login (the Moodle app's "scan to log in")

Every student's LMS profile shows a QR code for the Moodle app (enabled here:
`qrcodetype=2`). It encodes a short-lived login key that
`tool_mobile_get_tokens_for_qr_login` exchanges for a token. **No password is
ever typed anywhere except the real LMS.**

- Pros: the best UX for "no password". It is the same mechanism the official
  app uses.
- Cons and caveats (**verify all of these**):
  - The key is short-lived (admin TTL; Moodle's default is about 10 minutes).
  - With `qrsameipcheck` on (the default), the exchange must come from the
    **same IP** as the browser showing the QR. A central server fails this.
    A phone on mobile data scanning a laptop on campus Wi-Fi fails it too.
  - Moodle checks that QR and auto-login requests come from the Moodle app
    (its user agent). Browsers can't change the User-Agent from JavaScript, so
    a plain web page probably can't do the exchange. A native app or a
    browser extension can. Imitating the official app's user agent is a gray
    area, so be transparent about it.
- Verdict: a good fit inside a **native app (H5)** or **browser extension
  (H4)**. Not feasible from a central server.

### A4. In-browser login: the password goes only to the LMS

Our page (static, open source) runs in the student's browser and calls
`https://lms.nust.edu.pk/login/token.php` **directly**, which is possible
because CORS is `*`. The password never reaches our server. The resulting
token either stays on the device (H3/H4) or is encrypted and sent to our
server (H6/H7).

- Pros: the password provably never touches our infrastructure, if the
  student trusts the page's JavaScript. Verified technically possible.
- Cons: the student still types their password into a page that isn't the
  LMS. That's a phishing-shaped pattern, and a compromised deploy could
  exfiltrate it. Mitigations: open source, reproducible static deploy (GitHub
  Pages from a tagged commit), Subresource Integrity, or ship it as an
  extension whose code store reviewers can see.
- Verdict: **the recommended way to get a token** for the web-based options.

### A5. iCal export URL only ("privacy mode")

The student copies their calendar URL from *Calendar → Export* and gives us
that instead.

- Pros: read-only. It can't submit, grade, post or message. It is easy to
  revoke. This is the only option where a breach of our server is nearly
  harmless.
- Cons: **no submission status** (verified: submitted items still appear).
  No activity links. The feed includes every section's links, so section
  filtering still applies. The lookahead window is set by the admin.
- Workaround: the reminder message has a **"✅ Done"** button (Telegram
  inline keyboard, or a link in email/web) that the student taps after
  submitting, and we stop reminding.
- Verdict: **offer it as the low-trust tier.** Many students will prefer it.

### A6. Browser extension using the existing LMS session

The extension runs in the student's browser. When the student is logged into
the LMS, it calls the same internal AJAX endpoints the Moodle dashboard
timeline uses (`/lib/ajax/service.php` with the page's `sesskey`, for
`core_calendar_get_action_events_by_timesort`).

- Pros: **no password, no token, nothing stored.** It uses exactly what the
  student's browser already has. Full accuracy, including submission status.
- Cons: it only works while the browser runs and the session is alive
  (sessions expire). Needs a Chrome/Firefox extension and store publication.
  Doesn't help on phones.
- Verdict: an excellent **privacy-max option**, best combined with H7 so phone
  notifications still work.

### A7. Student pastes a token they obtained themselves

From *Preferences → Security keys* (if that page is visible to students; we
couldn't verify it from a script), or by running our CLI once.

- Pros: we never see the password.
- Cons: technical and confusing; it's still a full-access token.
- Verdict: fine as a power-user option, not the main path.

### A8. Official integration with NUST IT

NUST's Moodle admins create a dedicated web service that is limited to the
handful of read functions we need, and either issue per-user tokens or run
the service themselves.

- Pros: the only way to get a **limited token**. Removes the gray area
  entirely, and NUST might host or endorse it.
- Cons: depends on the university's priorities and timeline.
- Verdict: **worth pursuing in parallel** (see §11). The simplest version of
  this request: "please enable Airnotifier push in the Moodle app". That alone
  gives every student phone push for due-soon reminders.

---

## 5. Hosting and deployment models

### H0. Baseline: use what already exists (no build)

- Moodle already emails `assign_due_soon` / `overdue` / `due_digest`. Students
  should check whether these reach their inbox (or spam).
- Subscribe the iCal URL in Google Calendar or Apple Calendar to get native
  calendar reminders.
- Gaps: no section filtering (you get every section's links), no
  submitted/pending awareness in the calendar, Google refreshes subscribed
  calendars slowly (hours), no WhatsApp/Telegram.
- Worth documenting in the README as "try this first".

### H1. Local CLI with cron or systemd (current state)

- Trust: total. Everything stays on the student's machine.
- Cost: free.
- Cons: only runs while that machine is on; needs Python and a terminal.
- Audience: technical students.

### H2. Template repo plus GitHub Actions, run by each student

Each student clicks *Use this template*, adds their credentials as **their
own** repository secrets, picks a notification channel, and a scheduled
workflow runs every 30–60 minutes.

- Trust: we never see anything. Secrets live in the student's GitHub account.
- Cost: free (public repos have unlimited Actions minutes; private repos get
  2,000 minutes a month, which is plenty).
- Cons and caveats:
  - Must verify GitHub's runners (Azure, mostly US) can reach the LMS and
    negotiate its TLS. The site might restrict foreign IPs.
  - Scheduled workflows are **auto-disabled after 60 days without repo
    activity**. A keep-alive commit or workflow is needed.
  - Cron timing is best-effort, often 5–15 minutes late.
  - State has to persist between runs: Actions cache, an artifact, or a
    commit to a `state` branch.
  - Students need a GitHub account and must follow a setup guide.
- Audience: CS students. **Easy for us to ship, and nobody has to trust us.**

### H3. Static web app or PWA (GitHub Pages), entirely client-side

A static site that logs in through A4, stores the token in the browser
(IndexedDB), and shows a "what's pending" dashboard.

- Trust: no server holds anything. The code is auditable.
- Cost: free.
- Cons: **no reliable background reminders.** Without a server there is no
  Web Push, and Periodic Background Sync works only in installed Chromium
  PWAs and only when the browser decides to run it. It is a good dashboard
  but a bad notifier.
- Verdict: useful as the **onboarding front-end** for H6/H7, not as a
  standalone notifier.

### H4. Browser extension (Chrome/Edge/Firefox)

Uses A6 (the session) or A3/A4 (a token stored locally). Runs `chrome.alarms`
every 30 minutes and shows desktop notifications plus a toolbar badge with
the pending count.

- Trust: nothing leaves the device.
- Cost: Chrome Web Store one-time $5 developer fee; Firefox is free.
- Cons: desktop only; only while the browser is running; we have to
  maintain store listings.
- Verdict: **the best privacy/effort ratio for desktop.** Pair it with H7 for
  phone notifications.

### H5. Native mobile app (Flutter / React Native)

Signs in with A3 (QR) or A4. Uses background fetch and local notifications.

- Trust: data stays on the phone.
- Pros: phone notifications without a server. QR login fits naturally.
- Cons: Android background work is throttled by battery optimizers. iOS
  background fetch is unreliable and needs a $99/year developer account. It
  is the most work to build and distribute; Android can be sideloaded with an
  APK.
- Verdict: high effort. Consider it only if the project takes off.

### H6. Central hosted service (Telegram bot plus web onboarding)

We run one server that polls the LMS for every registered student and
delivers notifications.

```
student --(A4: browser -> LMS)--> token --(encrypted)--> our API
                                                             |
                    +----------------------------------------+
                    v
   [users DB] <-> [scheduler] -> [poll workers] -> lms.nust.edu.pk
                                       |
                                       v
                        [reminder engine + state] -> Telegram / email / ntfy / WhatsApp
```

- Trust: highest required. We hold tokens (or iCal URLs, with A5).
- Pros: the best UX. Works with the laptop off and on any phone, with
  one-tap Telegram onboarding.
- Cons:
  - We are responsible for securing many students' tokens.
  - All traffic comes from one IP, which NUST may rate-limit or block.
  - Ongoing cost and ops work.
- Hosting choices:

| Platform | Cost | Notes |
|---|---|---|
| Small VPS (Hetzner CX22, DigitalOcean, Contabo) | about $4–6/mo | Full control. Python's `OP_LEGACY_SERVER_CONNECT` works. **Recommended.** |
| Oracle Cloud Always Free (ARM VM) | free | Generous, but account sign-up is often rejected and the free VM can be reclaimed if idle. |
| Fly.io / Railway / Render | $0–5/mo | Easy deploys. Free tiers sleep; use their cron or worker features. |
| Cloudflare Workers + Cron Triggers + D1 | free tier | Cheap and scalable, but **the legacy-TLS requirement may make LMS fetches fail**. Test first. |
| A machine on the NUST network (SEECS lab server, society box) | free | Reaches the LMS internally; needs institutional buy-in. |
| GitHub Actions as a central runner | free | **Not suitable**: everyone's secrets would sit in one repo. |

### H7. Hybrid: fetch on the device, deliver from the server

The device that already has access (extension H4, PWA H3, or app H5) fetches
pending tasks and sends **only task metadata** (title, course, due time,
link) to a small relay server. The relay schedules and sends Telegram,
WhatsApp, email or push reminders.

- Trust: the server never has LMS access. A breach leaks a list of
  assignment titles, nothing that can act as the student.
- Pros: phone notifications without holding credentials. A deadline 6 hours
  away still gets its reminder even if the laptop is closed, because the
  relay already knows about it.
- Cons: it only learns about **new** tasks or submissions when the device
  next syncs (for example, whenever the student opens their browser). A
  student who submits from a lab PC needs one more sync, or a "✅ Done"
  button, to stop reminders.
- Verdict: **the strongest privacy story that still reaches phones.**

### H8. Run by the institution or a student society

The same code as H6, but operated by NUST IT, SEECS, or an official society
such as ACM or IEEE, ideally with an A8 limited token.

- Pros: students trust it more; no IP-blocking risk; possibly limited tokens.
- Cons: depends on the organization.

---

## 6. Notification channels at multi-user scale

| Channel | Cost | Setup for student | Scale | Notes |
|---|---|---|---|---|
| **Telegram bot** | Free | Tap a link, press *Start* | Excellent (bulk limits are about 30 msgs/s) | **Recommended primary.** Also the onboarding UI: inline buttons for "✅ Done", "Snooze 1h", "/section A", "/stop". |
| **ntfy** | Free (public server) or self-host | Install app, subscribe to topic | Good | Topics are public. Generate a long random topic per user, or self-host with auth. |
| **Email** | Free tiers: Brevo 300/day, Resend 3k/mo, AWS SES about $0.10/1k | Nothing | Good | Use a proper sender domain with SPF/DKIM or it lands in spam. Gmail SMTP caps at about 500/day and isn't meant for this. |
| **Web Push** (PWA) | Free | Allow notifications; on iOS, *Add to Home Screen* first (iOS 16.4+) | Good | Needs a server (VAPID keys); pairs with H3/H7. |
| **WhatsApp: official Cloud API** | Meta charges per message; utility templates are cheap in PK but not free; business verification needed | Message our number once | Good | Templates need Meta approval. The most work, but the only ToS-compliant WhatsApp route. |
| WhatsApp: CallMeBot | Free | Each student registers with CallMeBot | **Personal use only** | Fine for H1/H2 self-hosters, not for a service. |
| WhatsApp: unofficial libraries (Baileys, whatsapp-web.js) | Free | Message our number | Fragile | **Violates WhatsApp ToS; the number gets banned.** Avoid. |
| Discord bot | Free | Join server or DM bot | Good | Popular in some batches; easy to add. |
| SMS | About PKR 0.5–2/SMS via local gateways | Nothing | OK | Costs money at scale; only for critical "due in 1h". |
| Google Calendar write (OAuth) | Free | Grant calendar access | Good | Writes *only pending* items with native reminders and removes them once submitted. A nice complement to iCal. |

---

## 7. Comparison matrix

Rating scale: ●●● = best, ● = worst.

| Option | What the student shares | Knows if submitted? | Works with device off? | Student setup effort | Our effort | Our running cost |
|---|---|---|---|---|---|---|
| H0 built-in + iCal subscribe | nothing | ✗ | ✓ | ●●● | none | 0 |
| H1 local CLI | nothing | ✓ | ✗ | ● | done | 0 |
| H2 GitHub Actions template | nothing (own secrets) | ✓ | ✓ | ●● | ●●● low | 0 |
| H3 PWA only | nothing | ✓ | ✗ | ●●● | ●● | 0 |
| H4 extension | nothing | ✓ | ✗ | ●●● | ●● | $5 once |
| H5 native app | nothing | ✓ | ~ (OS-dependent) | ●●● | ● high | $0–99/yr |
| H6 hosted + A5 (iCal) | read-only calendar URL | ✗ (manual "Done") | ✓ | ●●● | ●● | ~$5/mo |
| H6 hosted + A4 token | full-access token | ✓ | ✓ | ●●● | ●● | ~$5/mo |
| H7 hybrid relay | task titles only | ✓ (on sync) | ✓ for known tasks | ●●● | ●● | ~$5/mo |
| H8 institution-run | depends (maybe limited token) | ✓ | ✓ | ●●● | ●● plus politics | theirs |

---

## 8. Recommendation

Ship in tiers, so each student picks the trust level they're comfortable with.
Everything should be **open source** in this repo so anyone can audit what
runs.

1. **Tier 0, Self-host (H1 + H2).** For people who trust no one: a GitHub
   template plus a 5-minute guide. Cheapest for us and nearly done.
2. **Tier 1, Privacy mode (H6 + A5).** A Telegram bot where you paste your iCal
   URL and set your section. Reminders come with a "✅ Done" button. A breach
   is nearly harmless.
3. **Tier 2, Full accuracy (H6 + A4).** The same bot, but linking happens on a
   static page that logs in **from your browser directly to the LMS**. Only
   the resulting token is sent to us, encrypted at rest. Automatic "submitted"
   detection.
4. **Later, Extension + relay (H4 + H7).** The no-credentials-on-server option
   with phone reminders, for people who want accuracy without trusting us
   with a token.
5. **In parallel, talk to NUST IT (A8/H8):** ask them to enable Airnotifier
   push, issue a limited-scope web service, or host the project.

Why Telegram first: it's free, needs no app store, and onboarding is a single
link. Its buttons give us "Done", "Snooze" and settings with no web UI to
build.

---

## 9. Security and privacy requirements (for any hosted option)

**Credential handling**

- Never accept or store passwords server-side (A1/A2 ruled out for the hosted
  tiers).
- Encrypt tokens and iCal URLs at rest with envelope encryption. Each record
  is encrypted with a data key; data keys are wrapped by a master key held
  outside the DB (KMS, or at minimum an env var or secret file outside the
  backup path). Use libsodium / `cryptography` (Fernet or AES-GCM).
- Never log tokens, URLs containing `authtoken`/`wstoken`, or message bodies.
  Scrub them in the error reporter.
- Show the student exactly what they're granting (the §3 table, in plain
  language) and how to revoke it (*Security keys → Reset*, or regenerate the
  calendar export token).

**Data minimization**

- Store only: messaging chat id, LMS user id, section, encrypted credential,
  reminder state (task id, due time, stages sent), preferences.
- No grades, file contents or messages.
- Prune task state 30 days after the deadline (already implemented).
- `/delete` command: erases everything immediately and tells the student how
  to revoke the token.

**Operational**

- Detect expired or revoked tokens (`invalidtoken`) and message the student
  to re-link instead of failing silently. Tokens from `login/token.php`
  usually expire after an admin-configured period (Moodle's default is 12
  weeks).
- Admin access to the server limited to maintainers; SSH keys only; automatic
  security updates; encrypted backups.
- A published privacy policy and a public changelog of deployed commits.
- Rate-limit onboarding endpoints; bind each linked LMS account to exactly one
  messaging account.

**Abuse cases to design against**

- Someone links *another student's* iCal URL or token to their own Telegram
  and watches that student's deadlines. Mitigation: display the LMS full name
  on linking and require a confirmation; one LMS account per chat; anyone can
  revoke by regenerating their token.
- A compromised maintainer or server. Mitigations: Tier 1 limits the blast
  radius; H7 removes it.

---

## 10. Being a good citizen toward the LMS

**Load estimate per user per poll:** 1 call (`get_action_events_by_timesort`),
plus status checks only for **newly seen** tasks. Action events already
exclude submitted work, so per-task status checks can be dropped or cached.
For 1,000 students polled every 30 minutes that is about 2,000–3,000
requests an hour, under 1 request a second. That's modest, but it all comes
from one IP.

**Polling strategy:**

- Adaptive polling: every 2–3 h when nothing is due within 24 h; every 30 min
  inside 24 h; every 10 min inside 2 h.
- Spread users across the interval (jitter) rather than polling everyone on
  the hour.
- Cache course and assignment metadata for hours (it rarely changes).
- Back off globally on HTTP 5xx or timeouts; pause during known maintenance.
- Send an honest User-Agent with a contact URL, e.g.
  `lms-notifier/1.0 (+https://github.com/<org>/lms-notifier)`, except where
  A3 requires the Moodle app's user agent.

**TLS:** every runtime must negotiate the server's legacy renegotiation.
Python works with `ssl.OP_LEGACY_SERVER_CONNECT`. Node needs
`secureOptions: crypto.constants.SSL_OP_LEGACY_SERVER_CONNECT`. Cloudflare
Workers, Deno and some managed fetch stacks may not support it at all. Test
before choosing a platform. Browsers connect fine, so H3/H4 are unaffected.

---

## 11. Generalizing beyond NUST

Introduce **site profiles** so another university is a config entry, not a
fork:

```yaml
# sites/nust.yaml (illustrative)
id: nust
name: NUST LMS
url: https://lms.nust.edu.pk
timezone: Asia/Karachi
tls:
  legacy_renegotiation: true
sections:
  patterns:
    - '(?<![a-z])sec(?:tion)?[\s_\-]*([a-z])(?![a-z])'
    - '(?<![a-z])bs[a-z]{2}[\s_\-]*\d{2}[\s_\-]*([a-z])(?![a-z])'
```

Use auto-discovery to decide which login methods to offer.
`tool_mobile_get_public_config` reports, per site:

- `typeoflogin`: 1 means password login works (A2/A4). 2 or 3 means
  browser/SSO only (common with Microsoft/Google SSO), where A4 is impossible
  and only A3, A5 or A6 work.
- `tool_mobile_qrcodetype`: whether QR login (A3) is available.
- Whether web services are enabled at all. If not, only A5 (iCal) or A6
  (extension with session) work.

Also needed:

- **Section inference:** suggest a section from courses that contain a single
  section letter (e.g. `CS-245 … A`), and let the student confirm.
- **Per-user overrides:** mute a course, mute a specific activity, add custom
  patterns.

---

## 12. Policy, legal and ethics checklist

- **NUST IT acceptable-use policy:** check what it says about automated
  access and about sharing credentials or tokens with third parties. If it
  prohibits sharing, Tiers 1 and 2 are a problem and Tier 0, H4 and H7 are
  the safe options.
- **Consent:** a student authorizing access to their own account is
  different from unauthorized access (Pakistan's PECA 2016 targets the
  latter). Get explicit, recorded consent and offer instant deletion. Take
  proper advice before operating at scale.
- **Moodle app user agent (A3):** imitating the official app is a gray area.
  Prefer A4/A6 unless NUST endorses it.
- **WhatsApp ToS:** only the official Cloud API for a service; CallMeBot only
  for personal self-hosting.
- **Not affiliated:** don't use NUST logos or anything that suggests an
  official service unless it actually becomes one (H8).

---

## 13. Open questions to verify before building

- [ ] Can GitHub Actions runners reach `lms.nust.edu.pk` and complete the TLS
      handshake? (Decides whether H2 works.)
- [ ] Same check from the chosen VPS region (Europe or Singapore).
- [ ] Does `tool_mobile_get_tokens_for_qr_login` enforce the Moodle-app user
      agent and same-IP check here? What is `qrkeyttl`?
- [ ] Is *Preferences → Security keys* visible to students, and does *Reset*
      revoke the mobile token?
- [ ] Does changing the password revoke existing tokens
      (`passwordchangetokendeletion`)?
- [ ] How long do mobile tokens stay valid here (`tokenduration`)?
- [ ] iCal export lookahead and lookback windows: do they cover a whole
      semester?
- [ ] Do students actually receive Moodle's `assign_due_soon` emails? If they
      do, H0 may already cover part of the need.
- [ ] Are quiz and other activity types (forum, workshop, H5P) worth
      supporting, or are assignments 95% of the value?
- [ ] What does NUST IT policy say (§12)? Would they enable Airnotifier, or
      issue a limited web service (A8)?

---

## 14. Phased roadmap

| Phase | Deliverable | Depends on |
|---|---|---|
| 0 | Run the §13 checks; write findings into this doc | — |
| 1 | **Self-host polish**: GitHub template repo, Actions workflow with state persistence and keep-alive, setup guide with screenshots, site profiles | Actions reachability |
| 2 | **Telegram bot MVP, Tier 1 (iCal)**: link via iCal URL, section setting, digests, "Done"/"Snooze" buttons, `/delete`; deploy on a small VPS | VPS reachability |
| 3 | **Tier 2 (token)**: static linking page doing A4 in-browser, encrypted token storage, re-link flow, automatic submitted detection | Phase 2 |
| 4 | **Extension + relay (H4 + H7)**: Chrome/Firefox extension, session-based fetch, optional sync to the relay | Phase 2 relay |
| 5 | Email and Web Push channels; official WhatsApp Cloud API if there's demand | Phase 2 |
| ∥ | Conversation with NUST IT / SEECS (A8, Airnotifier, hosting) | — |

Architecture note for the code, once we start: keep the existing
`lms_notifier` package as the **core library** (Moodle client, task
collection, section filtering, reminder engine, notifiers). The CLI, the
GitHub Action, the bot and the relay become thin front-ends over it, with an
iCal-based collector added next to the API-based one behind the same `Task`
interface.
