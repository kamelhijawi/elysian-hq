---
name: run-hq
description: Run, start, restart, smoke-test and screenshot the Moon Shelter reports page (hq/tools/report-server.py, http://127.0.0.1:8770). Use when asked to run hq, start the reports server, check the reports page, screenshot it, or test a change to report-server.py.
---

The reports page is a local-only Python HTTP server (`tools/report-server.py`, stdlib only, port 8770). It lists each department's reports, renders a `.md` as a web page, prints it to PDF with Chrome headless, and has one POST per department that starts a bot run. Drive it with `.claude/skills/run-hq/smoke.sh` (curl + Chrome headless). All paths are relative to `hq/`. macOS only: it shells out to `/Applications/Google Chrome.app` and runs under launchd.

## Prerequisites

Already on Kamel's Mac: `python3` (Homebrew 3.14), Google Chrome, `curl`. No packages to install, no venv.

## Setup

The server is a launchd service, `com.elysian.svc.reports`, installed by:

```bash
python3 tools/install-schedules.py
```

It starts at login and is restarted only if it exits with an error. Log: `~/Library/Logs/elysian-svc-reports.log`.

## Run (agent path)

```bash
.claude/skills/run-hq/smoke.sh
```

What it does, in order: makes sure the server answers (kickstarts the launchd service, else starts `tools/report-server.py` directly), GETs `/`, `/status` and the newest `/report` of every card, checks that `..` paths and unknown jobs get 400, and screenshots the home page with Chrome headless. Outputs land in `$TMPDIR/run-hq/` (`home.html`, `status.json`, `report-<job>.html`, `home.png`). Open `home.png` and look at it: three cards (CRM report, Sales pulse, Production orders), each with a gold Generate button and a file list.

```bash
.claude/skills/run-hq/smoke.sh --pdf
```

Also GETs `/pdf?job=sales&f=pulse.md`, which prints the pulse through Chrome (about 5 s) and saves it as `moonshelter/live/pdf/sales-pulse.pdf`. Verified: `application/pdf`, ~590 KB.

**Never POST `/run/<job>`.** It launches a department bot on Claude headless for 5–10 minutes through `tools/run-ondemand.sh`. The Generate buttons on the page do exactly that; do not click them from a test.

Routes, for ad-hoc checks:

```bash
curl -s http://127.0.0.1:8770/status
```

| Route | Returns |
|---|---|
| `GET /` | home page, one card per department in `departments.json` |
| `GET /status` | `{"crm": ["ok", "last run …"], …}` state per card |
| `GET /report?job=crm&f=<file>.md` | the report rendered; add `&print=1` for the print layout |
| `GET /pdf?job=sales&f=pulse.md` | the PDF (cached while newer than the .md) |
| `POST /run/<job>` | starts the bot. Not for tests. |

## Restart after editing report-server.py

The running process does not reload. Bounce the service:

```bash
launchctl bootout "gui/$(id -u)/com.elysian.svc.reports"; launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.elysian.svc.reports.plist
```

Verified: `/status` answers 200 about two seconds after the bootstrap. Then run `smoke.sh` again.

## Run (human path)

Open http://127.0.0.1:8770 in a browser. The `.claude/launch.json` entry `moonshelter-reports` (at `elysian/`) starts the same script for the Claude desktop preview pane; it is refused in unattended sessions, so from a scheduled task use the URL directly or `smoke.sh`.

## Gotchas

- A second `python3 tools/report-server.py` while the service is up prints "already running" and exits 0 (errno 48 is caught). So "starting it" never tells you whether your edit is live; bounce the launchd service instead.
- Cards appear only for departments listed under `departments` in `departments.json`. `voice` is defined in `JOBS` but paused, so there are three cards, not four.
- `/pdf` writes to `moonshelter/live/pdf/`, never to a department folder (`brain/` is written by sales only). The PDF is reused while it is newer than the `.md`; delete it to force a reprint.
- `make_pdf` runs Chrome without `--user-data-dir` on purpose: with one, Chrome 154 writes the PDF but never exits and the request hangs for the 60 s timeout.
- The server log is silent (`log_message` is overridden); a bad request shows only as the 400/404 you get back.

## Troubleshooting

- `smoke.sh` says `server did not come up`: read `~/Library/Logs/elysian-svc-reports.log`. If the plist is missing from `~/Library/LaunchAgents/`, run `python3 tools/install-schedules.py` and retry.
- `/pdf` returns `PDF failed: Chrome headless did not produce a file`: Chrome is not at `/Applications/Google Chrome.app`, or the 60 s timeout hit; run the Chrome line from `make_pdf` by hand to see its error.
- `no screenshot` from `smoke.sh`: same Chrome path problem; `home.html` in the output dir still proves the page served.
