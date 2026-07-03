# Email Verifier

This is a local cold email verification tool. Drag in a CSV and it will:
- Validate each email live (MX, SMTP, syntax)
- Show real-time progress per file
- Let you cancel jobs mid-run
- Persist your results even after refresh
- Let you download the verified leads when ready

<img width="869" height="420" alt="image" src="https://github.com/user-attachments/assets/a0e8dd2a-3461-4930-9b6d-b3da451f658d" />

<img width="928" height="638" alt="image" src="https://github.com/user-attachments/assets/ab17849e-53b5-493c-9d4d-d3e5eb2b26cf" />

<img width="840" height="838" alt="image" src="https://github.com/user-attachments/assets/b404305c-588e-45dc-acb1-f897d6c04207" />


---

## 🧱 Setup

1. Clone the repo:
```
git clone [repo-link]
```

2. Open the Folder

---

## ⚙️ Install Dependencies

Open Terminal, then run:

```bash
cd "/Users/yourname/Desktop/Email Verifier"
python3 -m venv venv
source venv/bin/activate
pip install flask flask-cors dnspython email-validator
```

---

## 🚀 Run the App

### Terminal Tab 1:
```bash
source venv/bin/activate
python3 verify-app.py
```
You should see one of:
```
[SMTP OK] Port 25 is reachable - live mailbox verification is active.
```
```
[SMTP BLOCKED] Port 25 is blocked on this network - running in offline mode.
  Results will use 'unknown' + a confidence score instead of a false 'valid'.
```

### Terminal Tab 2:
```bash
cd "/Users/yourname/Desktop/Email Verifier"
python3 -m http.server 3000
```

---

## 🌐 Use the Tool

Open in your browser:
```
http://localhost:3000/index.html
```

- Drag in one or more CSVs
- Each file shows a progress bar, live email log, cancel button, and close (X)
- When done, a download link will appear
- Everything persists across refreshes

---

## ⚙️ Configuration (optional)

Copy `verifier_config.example.json` to `verifier_config.json` to override any default. All fields are optional; unset ones use the defaults below.

- `helo_hostname` — the domain the verifier identifies itself as on SMTP (HELO/EHLO + MAIL FROM). Defaults to this machine's hostname. The verifier never sends an actual email (it disconnects right after the RCPT check, before the DATA stage), so setting this to a domain you own is safe for that domain's sending reputation — only the probing IP address accumulates any reputation signal, not the domain.
- `max_workers` (15) — concurrent verification threads.
- `per_domain_max_concurrent` (2) / `per_domain_delay_s` (1.0) — throttles how hard any single mail server gets hit, to avoid rate-limit blocks.
- `catchall_probe_count` (2) — random addresses probed per domain to detect catch-all (accept-everything) domains.
- `enable_second_pass` (true) / `greylist_retry_delay_s` (90) — greylisted/rate-limited addresses are automatically re-checked after this delay, recovering mailboxes a single pass would miss.
- `enable_gravatar` (true) — best-effort free Gravatar existence check, used only to refine confidence on ambiguous (catch-all/unknown) results.

### Result columns

Each row in the output CSV gets: `status` (valid/invalid/risky/unknown), `reason`, `confidence` (0-100), `is_role`, `is_disposable`, `is_free`, `is_catch_all`, `did_you_mean` (typo suggestion), `mx_host`, `provider`, `smtp_message`, `has_spf`, `has_dmarc`, `has_gravatar`, `reliable`.

`unknown` means the mailbox could not be confirmed either way (SMTP unreachable, blocked, or still ambiguous after retry) — treat it as "needs review," not as invalid. `risky` means the domain accepts all mail (catch-all) or is a provider known to accept-then-bounce (e.g. Yahoo/AOL), so a 250 response there isn't trustworthy on its own.

---

