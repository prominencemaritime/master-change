# Master Change Alert

Sends an email to the company ICT team once a new Master has been in command for 14 days and is the only Master on the crew list, so that the actions associated with a change of Master (password changes and similar) can be carried out.

The project is built on the shared alert framework used by the other alert projects. It was created from `masters-navigation-audit` and can itself be used as the template for the next alert: see [Creating a new alert from this project](#creating-a-new-alert-from-this-project).

## Contents

- [Overview](#overview)
- [How detection works](#how-detection-works)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Local setup](#local-setup)
- [Configuration](#configuration)
- [Usage](#usage)
- [Testing](#testing)
- [Release and deployment](#release-and-deployment)
- [Monitoring](#monitoring)
- [Creating a new alert from this project](#creating-a-new-alert-from-this-project)
- [Troubleshooting](#troubleshooting)
- [Project structure](#project-structure)
- [Support](#support)

---

## Overview

Once a day the alert queries the `crew_contracts` table for Master changes that are due for notification (see [How detection works](#how-detection-works)) and sends **one email per change**.

**Recipients** are chosen from the vessel's email domain (`vessels.email`):

| Vessel email | To | CC |
|---|---|---|
| `...@prominencemaritime.com` (or a subdomain, e.g. `vsl.prominencemaritime.com`) | `PROMINENCE_EMAIL_TO_RECIPIENTS` | `PROMINENCE_EMAIL_CC_RECIPIENTS` + `INTERNAL_RECIPIENTS` |
| `...@seatraders.com` (or a subdomain) | `SEATRADERS_EMAIL_TO_RECIPIENTS` | `SEATRADERS_EMAIL_CC_RECIPIENTS` + `INTERNAL_RECIPIENTS` |
| Any other domain, or no vessel email | Not sent: logged as a warning and retried on the next run | |

The CC list is de-duplicated and never repeats a To address.

**Email content**

- Subject: `AlertDev | <VESSEL> Master Change`
- Header: alert title, vessel name, run time, company logos
- Introduction, for example:
  > Dear Colleagues,
  >
  > Captain John Smith assumed command of PROM STAR on 2026-01-10. 14 days have elapsed and no other Master remains on the crew list.
  >
  > The previous Master, Captain Peter Jones, signed off on 2026-01-12.
  >
  > Please carry out the actions associated with a change of Master, such as password changes.
- Table: Full Name, Rank, Sign On Date, Due Date, Outgoing Master, Outgoing Sign Off Date
- A plain-text alternative with the same content

The wording of the introduction is in `MasterChangeAlert._build_intro_paragraphs()` in `src/alerts/master_change.py`.

**Each change is notified once.** Sent changes are recorded in `data/sent_alerts.json` under the key `master_change__crew_contract_id_<id>__crew_member_id_<id>` and never resent while `REMINDER_FREQUENCY_DAYS` is empty.

---

## How detection works

All selection logic is in `queries/MasterChanges.sql`. Python only formats, routes and tracks the rows the query returns. All dates are the `*_as_per_office` columns of `crew_contracts`.

A crew contract is reported when **all** of the following hold at run time:

1. Its rank is `RANK_ID` (Master), the vessel is active and the party is crew.
2. It signed on at least `MASTER_CHANGE_DAYS` ago and no more than `LOOKBACK_DAYS` ago.
3. The incoming Master is still on board: the office sign-off date is empty or in the future.
4. No other Master is on board the same vessel: no contract of the same rank, for a different crew member, has signed on and not yet signed off.
5. It is a real change: the preceding Master contract on the vessel belongs to a different person. A new contract for the Master who was already in command is not reported.

The **outgoing Master** shown in the email is that preceding contract: the Master contract on the same vessel that signed on before the incoming one and signed off most recently (a still-open contract counts as the most recent).

### Timing

With $D$ = `MASTER_CHANGE_DAYS`, $L$ = `LOOKBACK_DAYS` and $t_\text{on}$ the incoming Master's sign-on, the email is sent at the first scheduled run inside the window

$$
t_\text{on} + D \;\le\; t_\text{run} \;\le\; t_\text{on} + L
$$

at which conditions 3 and 4 hold. In practice:

- **Normal handover**: the email goes out at the first run on or after day 14.
- **Overlapping handover**: if the outgoing Master is still on board on day 14, the email goes out at the first run after he signs off, provided that happens before day $L$. If he is still on board on day $L$, the change is never reported.
- **Incoming Master already gone**: if the incoming Master signs off before the email is sent, the change is not reported.
- **Downtime**: changes that become due while the container is down are sent on the next run, as long as they are still inside the window.
- **First deployment**: the first run sends every qualifying change of the last $L$ days.

The application refuses to start unless `LOOKBACK_DAYS` is greater than `MASTER_CHANGE_DAYS`.

### Time zones

Timestamps are stored without a time zone and treated as UTC. The query compares them with `NOW() AT TIME ZONE 'UTC'`, so the database session's time zone does not matter. `TIMEZONE` only affects how dates are displayed in the email.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         main.py                             │
│                      (Entry Point)                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
    ┌─────▼──────┐           ┌──────▼──────┐
    │ AlertConfig│           │  Scheduler  │
    │            │           │             │
    └─────┬──────┘           └─────┬───────┘
          │                        │
          │               ┌────────┴──────────┐
          │               │                   │
    ┌─────▼──────┐  ┌─────▼──────┐    ┌───────▼──────┐
    │  Tracker   │  │ BaseAlert  │    │    Alert     │
    │            │  │ (Abstract) │    │  Subclass    │
    └────────────┘  └─────┬──────┘    └──────┬───────┘
                          │                  │
                    ┌─────┴────────┬─────────┴───────┐
                    │              │                 │
            ┌───────▼────┐  ┌──────▼──────┐   ┌──────▼──────┐
            │EmailSender │  │ Formatters  │   │  db_utils   │
            └────────────┘  └─────────────┘   └─────────────┘
```

| Path | Purpose | Shared or per alert |
|---|---|---|
| `src/core/` | Configuration, scheduling, tracking, `BaseAlert` | Shared |
| `src/notifications/` | Email (and planned Teams) senders | Shared |
| `src/formatters/` | HTML and plain-text email templates | Shared |
| `src/utils/` | Validation and image utilities | Shared |
| `src/db_utils.py` | Database connection, optional SSH tunnel | Shared |
| `src/alerts/` | The alert implementation | Per alert |
| `queries/` | The alert's SQL | Per alert |
| `tests/test_<alert>.py`, fixtures in `tests/conftest.py` | Alert tests | Per alert |

### What one run does

`BaseAlert.run()` (in `src/core/base_alert.py`) executes these steps for every registered alert:

1. `fetch_data()`: run the SQL with its bind parameters.
2. `validate_required_columns()`: fail if the query no longer returns a column the alert needs.
3. `filter_data()`: convert timestamps to `TIMEZONE` and format them. No rows are removed.
4. Tracker: drop rows that were already sent.
5. `route_notifications()`: build one notification job per change (recipients, data, metadata).
6. `_send_notifications()`: render HTML and text, apply dry-run redirection, send, record as sent.
7. Write `logs/health_status.txt` for the container health check.

---

## Prerequisites

- **Python 3.13** (the Docker image is `python:3.13-slim`). Local development also runs on 3.14.
- **Docker** with Compose, for deployment.
- **PostgreSQL** access to the `core_prominence` database, directly or through an SSH tunnel.
- **SMTP** credentials for the sending account.
- Python packages: see `requirements.txt` (pinned versions) and `requirements-dev.txt`.

---

## Local setup

```bash
cd ~/Projects/Alerts/master-change

# Virtual environment (pyenv shown; python -m venv works too).
# <version>: a Python 3.13+ version installed in pyenv (pyenv versions)
pyenv virtualenv <version> master_change_env
pyenv local master_change_env

pip install -r requirements.txt

# Configuration
cp .env.example .env
vim .env

# Folders the application writes to
mkdir -p data logs

# Check
pytest -q
python -m src.main --dry-run --run-once
```

---

## Configuration

All settings come from `.env` in the project root, read by `python-decouple` (locally) or passed in by Docker Compose (`env_file`).

**Rules for `.env`**

- **No inline comments.** `python-decouple` keeps everything after `=` as the value, so `LOG_MAX_BYTES=10485760  # 10MB` is read as `'10485760  # 10MB'` and the application fails to start. Put comments on their own line.
- Lists are comma-separated without spaces around the commas.
- `.env` holds secrets and must never be committed. Keep `.env.example` in sync with it, without real values.

### Reference

```bash
# ============================================================================
# ALERT
# ============================================================================
# crew_ranks.id of Master
RANK_ID=1
# Days after sign-on before a change is notified
MASTER_CHANGE_DAYS=14
# Oldest sign-on still considered (must be greater than MASTER_CHANGE_DAYS)
LOOKBACK_DAYS=40

# ============================================================================
# DATABASE
# ============================================================================
DB_HOST=your.database.host
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_user
DB_PASS=your_password

# SSH tunnel (optional)
USE_SSH_TUNNEL=False
SSH_HOST=
SSH_PORT=22
SSH_USER=
# Path inside the container (see the volumes in docker-compose.yml);
# for local runs, the path on your machine
SSH_KEY_PATH=/app/ssh_ubuntu_key

# ============================================================================
# SMTP
# ============================================================================
SMTP_HOST=smtp.example.com
# 465 = SSL, 587 or 25 = STARTTLS
SMTP_PORT=465
SMTP_USER=alerts@example.com
SMTP_PASS=your_password

# ============================================================================
# RECIPIENTS (comma-separated)
# ============================================================================
# To, chosen by vessel email domain. At least one of the two must be set.
PROMINENCE_EMAIL_TO_RECIPIENTS=ict@prominencemaritime.com
SEATRADERS_EMAIL_TO_RECIPIENTS=ict@seatraders.com
# CC, chosen by vessel email domain (optional)
PROMINENCE_EMAIL_CC_RECIPIENTS=
SEATRADERS_EMAIL_CC_RECIPIENTS=
# CC on every email (optional)
INTERNAL_RECIPIENTS=

# ============================================================================
# SCHEDULING
# ============================================================================
# Use SCHEDULE_TIMES (daily, 24-hour HH:MM, comma-separated) or
# SCHEDULE_FREQUENCY_HOURS (every N hours). Leave the other one empty.
SCHEDULE_FREQUENCY_HOURS=
SCHEDULE_TIMES=09:00
# Time zone of SCHEDULE_TIMES and of tracking timestamps
SCHEDULE_TIMES_TIMEZONE=Europe/Athens
# Time zone for dates displayed in emails and logs
TIMEZONE=Europe/Athens

# ============================================================================
# TRACKING
# ============================================================================
# Empty = never resend (recommended for this alert)
REMINDER_FREQUENCY_DAYS=
# File in data/; use a separate file for dry runs (see Dry-run modes)
SENT_EVENTS_FILE=sent_alerts.json

# ============================================================================
# RUNTIME MODE
# ============================================================================
DRY_RUN=True
# In dry-run mode: redirect every email here, or leave empty to send nothing
DRY_RUN_EMAIL=
RUN_ONCE=False

# ============================================================================
# FEATURE FLAGS
# ============================================================================
ENABLE_EMAIL_ALERTS=True
# Teams notifications are not implemented yet
ENABLE_TEAMS_ALERTS=False
ENABLE_SPECIAL_TEAMS_EMAIL_ALERT=False
SPECIAL_TEAMS_EMAIL=

# ============================================================================
# LINKS (not used by this alert: links only render for a column named "title")
# ============================================================================
ENABLE_LINKS=False
BASE_URL=https://prominence.orca.tools
URL_PATH=/events

# ============================================================================
# BRANDING (files in media/)
# ============================================================================
PROMINENCE_LOGO=trans_logo_prominence_procreate_small.png
SEATRADERS_LOGO=trans_logo_seatraders_procreate_small.png

# ============================================================================
# LOGGING
# ============================================================================
LOG_FILE=alerts.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

# ============================================================================
# DOCKER BUILD USER (output of `id -u` and `id -g` on the host)
# ============================================================================
UID=1000
GID=1000
```

### Startup checks

The application stops with a clear error when:

- `SMTP_HOST`, `SMTP_USER` or `SMTP_PASS` is missing.
- `LOOKBACK_DAYS` is not greater than `MASTER_CHANGE_DAYS`.
- Neither `PROMINENCE_EMAIL_TO_RECIPIENTS` nor `SEATRADERS_EMAIL_TO_RECIPIENTS` is set. If only one is set, it starts with a warning, and changes on the other company's vessels are skipped.

### Dry-run modes

| Mode | Settings | Emails | Tracking file updated |
|---|---|---|---|
| Preview | `DRY_RUN=True` (or `--dry-run`), `DRY_RUN_EMAIL` empty | None; the log shows what would be sent | No |
| Redirect | `DRY_RUN=True` (or `--dry-run`), `DRY_RUN_EMAIL=you@...` | All to `DRY_RUN_EMAIL`, no CC, subject `[DRY-RUN] ... (Original: ...)` | **Yes** |
| Production | `DRY_RUN=False` and no `--dry-run` | Real recipients | Yes |

**Redirect mode records changes as sent.** A change you test with redirected emails would never reach the real recipients afterwards. Always use a separate tracking file for redirect runs, e.g. `SENT_EVENTS_FILE=sent_alerts_dryrun.json`.

`--dry-run` can only switch dry-run **on**: with `DRY_RUN=True` in `.env`, production requires changing `.env`.

---

## Usage

### Local

```bash
# Scheduled (runs until stopped)
python -m src.main

# One run, then exit
python -m src.main --run-once

# Preview: one run, nothing sent, nothing tracked
DRY_RUN_EMAIL= python -m src.main --dry-run --run-once

# Redirect: one run, emails to you, separate tracking file
DRY_RUN_EMAIL=you@example.com SENT_EVENTS_FILE=sent_alerts_dryrun.json \
  python -m src.main --dry-run --run-once
```

Environment variables set in front of the command override `.env`.

### Docker

The examples use `docker compose` (Compose v2). Older installations use `docker-compose` with the same arguments.

```bash
docker compose build
docker compose up -d                 # start the scheduler
docker compose logs -f alerts        # follow the logs
docker compose down                  # stop

# One-off runs in a temporary container (-e overrides .env)
docker compose run --rm -e DRY_RUN_EMAIL= alerts python -m src.main --dry-run --run-once
docker compose run --rm alerts python -m src.main --run-once
```

| Flag | Effect | Overrides |
|---|---|---|
| `--dry-run` | Dry-run mode (preview or redirect, depending on `DRY_RUN_EMAIL`) | `DRY_RUN` (can only turn it on) |
| `--run-once` | Run once and exit | `RUN_ONCE` (can only turn it on) |

---

## Testing

```bash
pytest -q                                   # all tests
pytest tests/test_master_change.py -v       # alert tests
pytest --cov=src --cov-report=html          # coverage, then: open htmlcov/index.html
docker compose run --rm alerts pytest -q    # inside the image
```

| File | Covers |
|---|---|
| `tests/conftest.py` | Shared fixtures: `mock_config` (environment for every setting the alert reads), `sample_dataframe` (query schema) |
| `tests/test_master_change.py` | The alert: startup checks, query bind parameters, formatting, routing, intro text, subject, tracking key, formatters, end-to-end run with mocked database and SMTP |
| `tests/test_integration.py` | Full `run()` workflow with mocked database: sending, duplicate prevention, empty results, one email per change |
| `tests/test_config.py`, `test_db_utils.py`, `test_email_sender.py`, `test_formatters.py`, `test_scheduler.py`, `test_tracking.py` | Shared framework |

`test_query_file_bind_parameters_match_fetch_data` parses `queries/MasterChanges.sql` exactly as SQLAlchemy does and fails if the query's bind parameters differ from the ones `fetch_data()` supplies.

### Running the query by hand

`psql` fills the same `:name` placeholders from `-v` variables, so the query file runs unchanged:

```bash
psql -h <host> -U <user> -d core_prominence \
  -v rank_id=1 -v lookback_days=40 -v master_change_days=14 \
  -f queries/MasterChanges.sql
```

Useful check before deployment: the rows returned are the emails the next production run will send, minus changes already in the tracking file and changes on vessels whose email domain matches no To list.

---

## Release and deployment

### First-time repository setup

This project was copied from another alert project. Before the first push:

1. **Check where the repository points.** If the folder was copied together with its `.git`, it still pushes to the original project:
   ```bash
   git remote -v
   ```
   - To start a clean history: `rm -rf .git && git init -b main`
   - To keep the copied history: `git remote set-url origin <new repository URL>`

2. **Check what would be committed.** Secrets, runtime state and editor files must not appear:
   ```bash
   git add --dry-run . | grep -E "\.env'|\.swp'|'(data|logs|htmlcov|\.pytest_cache)/|__pycache__" || echo "clean"
   ```
   If anything is listed, add it to `.gitignore`. The minimum is:
   ```
   .env
   *.swp
   data/
   logs/
   __pycache__/
   .pytest_cache/
   htmlcov/
   .coverage
   docker-compose.override.yml
   ```

3. **Create the GitHub repository** (private) and connect it:
   ```bash
   gh repo create <org>/master-change --private --source=. --remote=origin
   # or create it on github.com, then:
   git remote add origin git@github.com:<org>/master-change.git
   ```

4. **Commit and push**:
   ```bash
   git add .
   git commit
   git push -u origin main
   ```

### Release checklist

Each release goes through the same stages. Do not skip a stage after a failure; fix, commit and restart from step 1.

**1. Local checks**

```bash
pytest -q
DRY_RUN_EMAIL= python -m src.main --dry-run --run-once
```

Read the log: the number of records fetched, each "Created notification for Master change on ..." line, and no errors. (Outside Docker, a "Failed to write health status" error about `/app/logs` is expected and harmless.)

**2. Local redirect run** (optional): see what the emails look like.

```bash
DRY_RUN_EMAIL=you@example.com SENT_EVENTS_FILE=sent_alerts_dryrun.json \
  python -m src.main --dry-run --run-once
```

**3. Commit and push**

```bash
git status
git add <files>
git commit
git push
```

**4. Server: get the code**

First time:

```bash
ssh <server>
cd <alerts directory>
git clone git@github.com:<org>/master-change.git
cd master-change
mkdir -p data logs
```

Then create `.env` on the server, either from the template (`cp .env.example .env && vim .env`) or by copying yours from your machine (`scp .env <server>:<alerts directory>/master-change/.env`). On the server, set:

- `UID` and `GID` to the output of `id -u` and `id -g`
- `DRY_RUN=True` until go-live
- `SSH_KEY_PATH` and `USE_SSH_TUNNEL` as appropriate for the server

**Machine-specific volume paths:** the SSH key entries under `volumes:` in `docker-compose.yml` are host paths. If a host path does not exist, Docker creates an empty directory in its place and the SSH tunnel fails. Instead of editing the tracked file on the server, override the entries in a `docker-compose.override.yml` next to it (Compose merges it automatically; keep it out of git):

```yaml
services:
  alerts:
    volumes:
      - /home/<user>/.ssh/<key>:/app/ssh_key:ro
      - /home/<user>/.ssh/<other key>:/app/ssh_ubuntu_key:ro
```

Entries with the same container path replace the ones in `docker-compose.yml`. If the server reaches the database without a tunnel (`USE_SSH_TUNNEL=False`), the keys are not used, but the host paths should still point at existing files.

Later releases:

```bash
cd <alerts directory>/master-change
git pull
```

**5. Server: dry runs**

```bash
docker compose build

# Preview: nothing sent, nothing tracked. The log lists every email the
# first production run would send (the backlog of the last LOOKBACK_DAYS).
docker compose run --rm -e DRY_RUN_EMAIL= alerts \
  python -m src.main --dry-run --run-once

# Redirect: emails to you, separate tracking file
docker compose run --rm \
  -e DRY_RUN_EMAIL=you@example.com \
  -e SENT_EVENTS_FILE=sent_alerts_dryrun.json \
  alerts python -m src.main --dry-run --run-once
```

**6. Production**

In the server's `.env`:

```bash
DRY_RUN=False
SENT_EVENTS_FILE=sent_alerts.json
RUN_ONCE=False
```

Then:

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f alerts
```

The log should show the scheduler starting and the next run time. At the first scheduled run, the backlog seen in the preview is sent.

**Later releases** repeat steps 1, 3, 4 (`git pull`), the preview in 5, and `docker compose up -d --build`.

**Rollback**:

```bash
git log --oneline
git checkout <previous commit>
docker compose up -d --build
# back to the latest version later:
git checkout main
```

---

## Monitoring

```bash
docker compose logs -f alerts                 # live log (Docker)
tail -f logs/alerts.log                       # live log (file)
grep -E "ERROR|WARNING" logs/alerts.log       # problems, including skipped changes
cat logs/health_status.txt                    # result of the last run

jq '.sent_events | length' data/sent_alerts.json
jq '.sent_events | to_entries[] | select(.key | contains("crew_contract_id_123"))' data/sent_alerts.json
```

**Health check**: after every run, `BaseAlert` writes `logs/health_status.txt` (status, timestamp, alert class, time zone and any error), which the container health check (`scripts/healthcheck.py`) reads:

```bash
docker inspect --format='{{.State.Health.Status}}' master-change-app
```

This alert runs once a day, so the health check must accept a status file up to 24 hours old (plus a margin). Check the limit in `scripts/healthcheck.py` whenever the schedule changes.

---

## Creating a new alert from this project

The framework (`src/core`, `src/notifications`, `src/formatters`, `src/utils`, `src/db_utils.py`, Docker files) is reused unchanged. A new alert needs a query, an alert class, its tests, its configuration and its documentation. The steps below are in the order to do them. The example creates a "Hot Works" alert; replace the names with yours.

### Step 1: Copy the project without history or runtime state

```bash
cd ~/Projects/Alerts
rsync -a \
  --exclude '.git/' --exclude '.env' --exclude '*.swp' \
  --exclude 'data/' --exclude 'logs/' \
  --exclude '__pycache__/' --exclude '.pytest_cache/' --exclude 'htmlcov/' \
  --exclude 'docker-compose.override.yml' \
  master-change/ hot-works/
cd hot-works
mkdir -p data logs
git init -b main
cp .env.example .env
```

Why each exclusion matters:

- `.git/`: a copied repository still pushes to the original project's GitHub repository.
- `.env`, `*.swp`: secrets (vim swap files of `.env` contain it too).
- `data/`, `logs/`: the tracking file, logs and health status belong to the original alert.
- `__pycache__/`: compiled files remember the old folder path, so pytest reports tests as `<- ../master-change/tests/...` and tracebacks point at the wrong files.

Choose the final folder name now. If you rename the folder later, delete the caches: `find . -name __pycache__ -type d -prune -exec rm -rf {} + ; rm -rf .pytest_cache`.

### Step 2: Choose the names

| Item | This project | New alert (example) |
|---|---|---|
| Folder and GitHub repository | `master-change` | `hot-works` |
| SQL file | `queries/MasterChanges.sql` | `queries/HotWorks.sql` |
| Alert module | `src/alerts/master_change.py` | `src/alerts/hot_works.py` |
| Alert class | `MasterChangeAlert` | `HotWorksAlert` |
| Title (subject and email header) | `Master Change` | `Hot Works` |
| Tracking key prefix | `master_change__` | `hot_works__` |
| Test module | `tests/test_master_change.py` | `tests/test_hot_works.py` |
| Container name | `master-change-app` | `hot-works-app` |

Use them consistently: most problems when copying an alert come from one place still using the old name (see the leftover check in step 8).

### Step 3: Write the query

Create `queries/HotWorks.sql` and delete `queries/MasterChanges.sql`.

- **One row per item to notify.** Decide now whether one email covers one row or all rows of a vessel (see step 4).
- **Columns the framework needs**: `vessel`, `vsl_email`, `vessel_id`, plus stable unique IDs for the tracking key (e.g. `event_id`). Add the columns to display, named as they should appear: `sign_on_date` becomes the header "Sign On Date".
- **All selection logic belongs in SQL.** `filter_data()` should only format. Keep the Python side free of date windows, so the query can be tested on its own.
- **Parameters** are written `:name` and supplied by `fetch_data()`. SQLAlchemy treats every `:word` in the file as a parameter, **comments included**: write `rank_id` in comments, never `:rank_id`.
- **Timestamps** are stored without a time zone and are UTC: compare with `(NOW() AT TIME ZONE 'UTC')`, not `NOW()`.
- Test it with `psql -v name=value -f queries/HotWorks.sql` (see [Running the query by hand](#running-the-query-by-hand)) against real data, including edge cases, before writing Python.

### Step 4: Create the alert class

```bash
mv src/alerts/master_change.py src/alerts/hot_works.py
```

Then go through the file top to bottom:

| Part | Change |
|---|---|
| Module docstring, class name, class docstring | `HotWorksAlert` and a description of what triggers it |
| `ALERT_TITLE` | Title used in the subject and the email header |
| `DISPLAY_COLUMNS` | Columns shown in the email table, in order |
| `COMPANY_NAMES` | Normally unchanged |
| `__init__` | `self.sql_query_file = 'HotWorks.sql'`; read the alert's settings from `config`; startup checks. Remove the `LOOKBACK_DAYS`/`MASTER_CHANGE_DAYS` check if it does not apply. Keep the To-recipients check only if the alert sends to the `*_EMAIL_TO_RECIPIENTS` addresses |
| `fetch_data()` | The `params` dict must contain exactly the query's parameters |
| `filter_data()` | Which timestamp columns to convert to `TIMEZONE` and their formats. Do not remove rows here |
| `route_notifications()` | Grouping and recipients: choose a pattern below |
| `_build_intro_paragraphs()` | The email text. Plain text: the HTML formatter escapes it |
| `get_tracking_key()` | New prefix plus IDs that never change. Never include names (a vessel rename would resend everything) |
| `get_subject_line()` | Keep the convention `AlertDev \| <VESSEL> <ALERT_TITLE>` |
| `get_required_columns()` | Every column the class reads, including `DISPLAY_COLUMNS` |

**Routing patterns**

- **A. One email per row, to a company address** (this project). To comes from `email_routing[domain]['to']`, i.e. `PROMINENCE_EMAIL_TO_RECIPIENTS` / `SEATRADERS_EMAIL_TO_RECIPIENTS`; CC from `email_routing[domain]['cc']` plus `INTERNAL_RECIPIENTS`. Keep `route_notifications()` as it is.
- **B. One email per vessel, to the vessel** (as in `masters-navigation-audit`). Group the rows and send to the vessel's own address, reusing the helpers of this class:
  ```python
  for (vsl_email, vessel), vessel_df in df.groupby(['vsl_email', 'vessel']):
      domain = self._match_domain(vsl_email)
      routing = self.config.email_routing.get(domain, {}) if domain else {}
      jobs.append({
          'recipients': [vsl_email],
          'cc_recipients': self._get_cc_recipients(routing, [vsl_email]),
          'data': vessel_df.copy(),
          'metadata': { ... },   # as in this project
      })
  ```
  Remove the To-recipients startup check in `__init__`. Every row in an email is tracked individually, so a later row for the same vessel still produces a new email.

### Step 5: Register the alert

1. `src/alerts/__init__.py`: replace the import and the `__all__` entry:
   ```python
   from .hot_works import HotWorksAlert

   __all__ = ['HotWorksAlert']
   ```
   This file runs whenever anything under `src.alerts` is imported. If it still imports the old module, **every** alert import fails with `ModuleNotFoundError`.
2. `src/main.py`: change the import (`from src.alerts.hot_works import HotWorksAlert`) and the block in `register_alerts()`:
   ```python
   hot_works_alert = HotWorksAlert(config)
   scheduler.register_alert(hot_works_alert.run)
   logger.info("[OK] Registered HotWorksAlert")
   ```
3. Check: `python -c "import src.main"`

### Step 6: Configuration

For each new setting:

1. `src/core/config.py`: add a field to the alert-specific section of `AlertConfig`, and load it in `from_env()` with a sensible default, e.g. `hot_works_days=int(config('HOT_WORKS_DAYS', default=7))`.
2. `.env` and `.env.example`: add it, with a comment line above it (no inline comments).
3. `tests/conftest.py`, `mock_config`: add `monkeypatch.setenv('HOT_WORKS_DAYS', '7')`. Every setting the alert reads must be set here: anything missing falls back to your real `.env`, and the tests then depend on your local configuration.

Settings the new alert does not use (e.g. `MASTER_CHANGE_DAYS`) can stay in `config.py`, which keeps the framework identical between projects. Remove them from `.env.example`.

Also review in `.env`: `LOOKBACK_DAYS`, `RANK_ID`, recipients, the schedule, and `SENT_EVENTS_FILE` (a fresh file name avoids confusion with the original alert's tracking).

### Step 7: Email layout

The formatters are shared and normally need no change.

- The introduction comes from `metadata['intro_paragraphs']`. **Always set it.** Without it, if the data has a `surname` column, the HTML formatter falls back to the Master's Navigation Audit welcome text ("Dear Captain ..., F.NAV.13 ...").
- Table headers are the column names in title case. Rename columns in the SQL to change them.
- Links: a cell becomes a link only for a column named `title`, when the data has a `url` column and `ENABLE_LINKS=True`.

### Step 8: Tests

1. `mv tests/test_master_change.py tests/test_hot_works.py`, then adapt it:
   - `raw_row()`: one row as the new query returns it
   - routing expectations (pattern A or B), intro text, subject, tracking key format
   - the expected set in `test_query_file_bind_parameters_match_fetch_data`
   - the file name in `QUERY_FILE`
2. `tests/conftest.py`:
   - `mock_config`: environment for every setting (step 6)
   - `sample_dataframe`: the new query's columns. `tests/test_formatters.py` uses `full_name` and `rank` from it; update those tests if the columns change.
3. `tests/test_integration.py`:
   - the patch targets `src.alerts.hot_works.get_db_connection` and `src.alerts.hot_works.pd.read_sql_query`
   - the query file name written to `queries_dir`
   - expected email counts: one per row (pattern A) or one per vessel (pattern B)
4. Look for leftovers of the old alert:
   ```bash
   grep -rn --exclude-dir=__pycache__ \
     -e master_change -e MasterChange -e 'Master Change' \
     src tests scripts Dockerfile docker-compose.yml .env.example
   ```
   The only expected match is the `master_change_days` setting in `src/core/config.py`, if you kept it (step 6).
5. `pytest -q`: everything must pass.

### Step 9: Docker

1. `docker-compose.yml`: set `container_name: hot-works-app`. Two containers cannot share a name, so the second `docker compose up` fails otherwise.
2. Check the SSH key volume paths for each machine (see [Release and deployment](#release-and-deployment)).
3. `.env`: `UID`/`GID`, and `DRY_RUN=True` until go-live.

### Step 10: Documentation

1. `README.md`: update the title, Overview, How detection works, the `.env` reference, the container name in the commands and the project structure.
2. `docs/`: remove or replace documents that describe the original alert.

### Step 11: Verify and release

Follow [Release and deployment](#release-and-deployment) from "First-time repository setup".

### Checklist

- [ ] Copied without `.git`, `.env`, `data`, `logs`, caches; `git init` done
- [ ] Query written and checked in `psql`; old query deleted
- [ ] Alert class renamed and adapted (title, display columns, params, routing, intro, tracking key, subject, required columns)
- [ ] `src/alerts/__init__.py` and `src/main.py` updated; `python -c "import src.main"` works
- [ ] New settings in `config.py`, `.env`, `.env.example`, `conftest.py`
- [ ] `metadata['intro_paragraphs']` set
- [ ] Tests renamed and adapted; `conftest.py` fixtures match the new query; leftover grep clean; `pytest -q` passes
- [ ] `container_name` changed; volume paths valid on each machine
- [ ] README and `docs/` updated
- [ ] Local preview and redirect runs look right
- [ ] Pushed to the new GitHub repository; server preview, then production

---

## Troubleshooting

### Error messages

| Message | Cause and fix |
|---|---|
| `LOOKBACK_DAYS (...) must be greater than MASTER_CHANGE_DAYS (...)` | Fix the values in `.env`. |
| `MasterChangeAlert: no To recipients configured` | Set `PROMINENCE_EMAIL_TO_RECIPIENTS` and/or `SEATRADERS_EMAIL_TO_RECIPIENTS`. |
| `Required configuration missing from .env: ...` | Set the listed SMTP settings. |
| `ValueError: invalid literal for int()` / `could not convert string to float` | An inline comment in `.env` (e.g. `LOG_MAX_BYTES=10485760  # 10MB`). Move the comment to its own line. |
| `ModuleNotFoundError: No module named 'src.alerts.<old module>'` | `src/alerts/__init__.py` still imports a removed alert (step 5 above). |
| `Query file not found: .../queries/MasterChanges.sql` (in a run, not at startup) | The file was renamed or deleted, or the `queries` volume is not mounted. |

### A change was not notified

1. Run the query by hand for that vessel (see [Running the query by hand](#running-the-query-by-hand)) and check each condition in [How detection works](#how-detection-works). The usual reasons:
   - the outgoing Master is still on board (no office sign-off date, or one in the future)
   - the incoming Master has already signed off
   - the sign-on is older than `LOOKBACK_DAYS`
   - the preceding Master contract is for the same person (re-contract)
   - the office sign-on/sign-off dates are missing; the alert uses the `*_as_per_office` columns only
2. Search the log for `Skipping Master change on '<VESSEL>'`: the vessel has no email, or its domain matches no configured To list. Skipped changes are not tracked and go out on the next run once fixed, while still inside the window.
3. Check whether it is already tracked:
   ```bash
   jq '.sent_events | to_entries[] | select(.key | contains("crew_contract_id_<id>"))' data/sent_alerts.json
   ```
   If it was "sent" by a redirect dry run with the production tracking file, delete that entry and run again.

### No emails at all

- `ENABLE_EMAIL_ALERTS=False`, or dry-run mode with `DRY_RUN_EMAIL` empty (preview mode).
- `DRY_RUN=True` in `.env`: `--dry-run` cannot switch it off.
- Everything is already tracked: `jq '.sent_events | length' data/sent_alerts.json`.

### Database connection fails

`psycopg2.OperationalError` or "connection refused":

```bash
grep -E '^(DB_|SSH_|USE_SSH)' .env
ls -la <ssh key>                     # must exist and be a file, mode 600
python -c "from src.db_utils import check_db_connection; print(check_db_connection())"
```

In Docker, `SSH_KEY_PATH` is the path **inside** the container (`/app/...`), and the corresponding volume's host path must exist.

### SMTP authentication fails

Check `SMTP_*` in `.env`, then `python scripts/email_checker.py`. Accounts with two-factor authentication need an app password.

### Permission denied on `logs/` or `data/` (Docker)

The container runs as `UID`:`GID` from `.env`. They must match the owner of the folders:

```bash
id -u; id -g
sudo chown -R "$(id -u):$(id -g)" logs data
```

### Expected messages

- `Failed to write health status: ... '/app/logs'` when running outside Docker: the health file is only written in the container.
- `DeprecationWarning: The 'generic' unit for NumPy timedelta is deprecated` from `src/formatters/date_formatter.py` during tests: harmless.

### Tests

- Test IDs shown as `tests/x.py::test <- ../other-folder/tests/x.py`: stale `__pycache__` after renaming or copying the folder. Delete the caches (step 1 of the template instructions).
- Docker running old code after a pull: `docker compose build --no-cache && docker compose up -d`.

---

## Project structure

```
master-change/
├── data/                        # Runtime state (not in git)
│   └── sent_alerts.json         # Tracking of sent notifications
├── docs/                        # Documentation (partly from the original project)
├── logs/                        # Runtime logs (not in git)
│   ├── alerts.log
│   └── health_status.txt        # Result of the last run, read by the health check
├── media/                       # Logos embedded in emails
├── queries/
│   └── MasterChanges.sql        # Selection logic of this alert
├── scripts/
│   ├── email_checker.py         # SMTP test
│   ├── healthcheck.py           # Container health check
│   └── verify_teams_webhook.py  # Teams webhook test (planned feature)
├── src/
│   ├── alerts/
│   │   ├── __init__.py          # Exports MasterChangeAlert
│   │   └── master_change.py     # This alert
│   ├── core/
│   │   ├── base_alert.py        # Run workflow shared by all alerts
│   │   ├── config.py            # AlertConfig, loaded from .env
│   │   ├── scheduler.py         # Interval and time-of-day scheduling
│   │   └── tracking.py          # Sent-notification tracking
│   ├── formatters/
│   │   ├── date_formatter.py
│   │   ├── html_formatter.py
│   │   └── text_formatter.py
│   ├── notifications/
│   │   ├── email_sender.py
│   │   └── teams_sender.py      # Planned
│   ├── utils/
│   ├── db_utils.py              # Database connection and SSH tunnel
│   └── main.py                  # Entry point, alert registration
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_db_utils.py
│   ├── test_email_sender.py
│   ├── test_formatters.py
│   ├── test_integration.py
│   ├── test_master_change.py
│   ├── test_scheduler.py
│   └── test_tracking.py
├── .dockerignore
├── .env                         # Configuration and secrets (not in git)
├── .env.example                 # Template for .env
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── pytest.ini
├── README.md
├── requirements-dev.txt
└── requirements.txt
```

---

## Support

1. This README, in particular [Troubleshooting](#troubleshooting)
2. The logs: `docker compose logs -f alerts`
3. A preview run: `docker compose run --rm -e DRY_RUN_EMAIL= alerts python -m src.main --dry-run --run-once`
4. The query by hand: [Running the query by hand](#running-the-query-by-hand)
5. Contact: data@prominencemaritime.com

## License

Proprietary - Prominence Maritime / Seatraders

*Last updated: 10 November 2026*
