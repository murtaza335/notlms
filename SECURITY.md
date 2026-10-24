# Security policy

notlms handles an LMS access token, so security reports are welcome.

Please report vulnerabilities privately using GitHub's **Report a
vulnerability** button (Security tab → Advisories) instead of a public issue.
Include what you found, how to reproduce it, and the version
(`notlms --version`).

Areas of particular interest: the local web server (`notlms/web.py`), token
storage (`notlms/store.py`) and anything that could send credentials
somewhere other than the LMS.

Only the latest release is supported.
