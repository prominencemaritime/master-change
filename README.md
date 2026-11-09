# Master's Navigation Audit Alert System

A modular, production-ready alert system for monitoring new Master sign-ons and sending automated email notifications for required navigation audits. Built with a plugin-based architecture that makes it easy to create new alert types by copying and customizing the project.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Testing](#testing)
- [Creating New Alert Projects](#creating-new-alert-projects)
- [Docker Deployment](#docker-deployment)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)

---

## Overview

This system monitors a PostgreSQL database for new Master sign-ons (rank_id=1) and sends automated email notifications reminding captains to complete their Master's Navigation Audit and Master's MLC Inspection within 14 days of assuming command. The modular architecture allows you to easily create new alert types (hot works, certifications, surveys, etc.) by copying this project and customizing the alert logic.

**Current Alert Type**: Master's Navigation Audit
- Monitors `crew_contracts` table for Masters (rank_id='1') who have recently signed on
- Tracks crew contracts created in the last N days (configurable via `LOOKBACK_DAYS`)
- Sends individual emails to each vessel with personalized captain greeting
- Automatically determines CC recipients based on vessel email domain
- Tracks sent notifications to prevent duplicates
- Optional reminder system after configurable days
- Includes clickable links to crew contract details (if enabled)

**Key Requirements Reminder**:
- Form F.NAV.13 – Master's Navigation Audit
- Form F.MLC.1 - Master's MLC Inspection
- Current Crew List
- All must be uploaded within 14 days of assuming command

---

## Architecture

### Core Components
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

### Module Breakdown

| Module | Purpose | Reusable? |
|--------|---------|-----------|
| **src/core/** | Core infrastructure (config, tracking, scheduling, base alert class) | ✅ Yes - shared across all alerts |
| **src/notifications/** | Email and Teams notification handlers | ✅ Yes - shared across all alerts |
| **src/formatters/** | HTML and plain text email templates | ✅ Yes - shared across all alerts |
| **src/utils/** | Validation, image loading utilities | ✅ Yes - shared across all alerts |
| **src/alerts/** | Alert-specific implementations | ❌ No - customized per alert type |
| **queries/** | SQL query files | ❌ No - customized per alert type |

---

## Features

### Current Features
- ✅ **Modular Architecture**: Plugin-based design for easy extensibility
- ✅ **Email Notifications**: Rich HTML emails with company logos and responsive design
- ✅ **Personalized Messages**: Custom greeting using captain's surname
- ✅ **Clickable Contract Links**: Direct links from emails to crew contract details (optional)
- ✅ **Smart Routing**: Automatic CC list selection based on email domain
- ✅ **Duplicate Prevention**: Tracks sent notifications to avoid re-sending
- ✅ **Optional Reminders**: Re-send alerts after configurable days (or never)
- ✅ **Dual Timezone Support**: 
  - `TIMEZONE` for SQL queries and data display
  - `SCHEDULE_TIMES_TIMEZONE` for scheduler timing and event tracking
- ✅ **Flexible Scheduling**: 
  - Interval-based: Run every N hours (e.g., every 1 hour, 30 minutes, etc.)
  - Time-based: Run at specific times daily (e.g., 09:00, 15:00)
- ✅ **Dry-Run Mode**: Test without sending emails (redirects to test addresses)
- ✅ **Command-Line Overrides**: `--dry-run` and `--run-once` flags override `.env` settings
- ✅ **Graceful Shutdown**: SIGTERM/SIGINT handlers for clean termination
- ✅ **Error Recovery**: Continues running after transient failures
- ✅ **Docker Support**: Fully containerized with docker-compose
- ✅ **SSH Tunnel Support**: Secure remote database access
- ✅ **Atomic File Operations**: Prevents data corruption on interruption
- ✅ **Comprehensive Logging**: Rotating logs with detailed execution traces
- ✅ **Responsive Email Design**: Adapts to desktop, tablet, and mobile screens

### Future Features (Planned)
- 🔜 **Microsoft Teams Integration**: Send notifications to Teams channels
- 🔜 **Slack Integration**: Send notifications to Slack channels
- 🔜 **Multiple Alert Types**: Hot works, certifications, surveys, etc.

---

## Prerequisites

### Required Software
- **Python 3.13+**
- **Docker & Docker Compose** (recommended for deployment)
- **PostgreSQL** database (remote or local)
- **SSH key** (if using SSH tunnel to database)

### Required Python Packages

See `requirements.txt` for exact versions. Key dependencies:

**Core Dependencies**:
- `python-decouple==3.8` - Environment variable management
- `pandas==2.2.3` - Data manipulation and analysis
- `sqlalchemy==2.0.44` - Database ORM and connection pooling
- `psycopg2-binary==2.9.11` - PostgreSQL adapter
- `sshtunnel>=0.4.0,<1.0.0` - SSH tunnel for remote database access
- `paramiko>=2.12.0,<4.0.0` - SSH protocol implementation (required by sshtunnel)
- `pymsteams==0.2.5` - Microsoft Teams webhook integration *(planned)*

**Testing Dependencies**:
- `pytest==7.4.3` - Testing framework
- `pytest-cov==4.1.0` - Coverage reporting
- `pytest-mock==3.12.0` - Mocking utilities
- `freezegun==1.4.0` - Time/date mocking for tests

**Install all dependencies**:
```bash
pip install -r requirements.txt
```

**Install only production dependencies** (exclude testing):
```bash
grep -v "^#\|pytest\|freezegun" requirements.txt | pip install -r /dev/stdin
```

### Required Accounts/Access
- SMTP server credentials (e.g., Gmail, Office365)
- PostgreSQL database credentials
- SSH access to database server (if using SSH tunnel)

---

## Installation

### Docker Deployment (Recommended)

1. **Clone or copy the project**:
```bash
   cd ~/Dev
   git clone <repository> masters-navigation-audit-alerts
   cd masters-navigation-audit-alerts
```

2. **Create `.env` file**:
```bash
   cp .env.example .env
   vi .env  # Edit with your settings
```

3. **Build and run**:
```bash
   export UID=$(id -u) GID=$(id -g)
   docker-compose build
   docker-compose up -d
```

4. **Fix directory permissions** (important for Linux servers):
```bash
   # Ensure the container can write to logs and data directories
   # Use your user's UID:GID (check with: id -u and id -g)
   sudo chown -R $(id -u):$(id -g) logs/ data/
   
   # Or if deploying on a server where you know the UID/GID:
   sudo chown -R 1000:1000 logs/ data/
   
   # Alternative (less secure but works):
   chmod -R 777 logs/ data/
```

**Note**: This step is especially important when:
- Deploying to a remote Linux server
- Using this project as a template for a new alert
- The directories were created by a different user (e.g., root)

5. **Verify it's running**:
```bash
   docker-compose logs -f alerts
```

### Local Development Setup

1. **Clone or copy the project**:
```bash
   cd ~/Dev
   git clone <repository> masters-navigation-audit-alerts
   cd masters-navigation-audit-alerts
```

2. **Create virtual environment**:
```bash
   python3.13 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate  # On Windows
```

3. **Install dependencies**:
```bash
   pip install -r requirements.txt
```

4. **Create `.env` file**:
```bash
   cp .env.example .env
   vi .env  # Edit with your settings
```

5. **Test the configuration**:
```bash
   python -m src.main --dry-run --run-once
```

---

## Configuration

### Environment Variables (`.env`)

Create a `.env` file in the project root using the .env.example template.

```bash
# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
DB_HOST=your.database.host.com
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_user
DB_PASS=your_password

# SSH Tunnel Configuration (optional - for remote database access)
USE_SSH_TUNNEL=True
SSH_HOST=your.ssh.host.com
SSH_PORT=22
SSH_USER=ubuntu
SSH_KEY_PATH=/app/ssh_ubuntu_key  # Inside Docker container
# SSH_KEY_PATH=/Users/username/.ssh/id_rsa  # For local development

# ============================================================================
# EMAIL CONFIGURATION
# ============================================================================
SMTP_HOST=smtp_host
SMTP_PORT=465
SMTP_USER=alerts@yourcompany.com
SMTP_PASS=your_email_password

# Email Recipients (comma-separated)
# Company-specific CC recipients (added automatically based on vessel email domain)
PROMINENCE_EMAIL_CC_RECIPIENTS=operations@prominencemaritime.com,fleet@prominencemaritime.com
SEATRADERS_EMAIL_CC_RECIPIENTS=operations@seatraders.com,fleet@seatraders.com

# Internal recipients (always CC'd on all emails)
INTERNAL_RECIPIENTS=data@prominencemaritime.com

# ============================================================================
# SCHEDULING CONFIGURATION
# ============================================================================

# METHOD 1: Interval-based scheduling (run every N hours)
# Set SCHEDULE_FREQUENCY_HOURS to run at regular intervals
SCHEDULE_FREQUENCY_HOURS=1  # Run every 1 hour

# METHOD 2: Time-based scheduling (run at specific times daily)
# Set SCHEDULE_TIMES to run at specific times (comma-separated, 24-hour format)
# If both are set, SCHEDULE_TIMES takes precedence
# SCHEDULE_TIMES=09:00,15:00,21:00  # Run at 9 AM, 3 PM, and 9 PM daily

# Timezone for scheduled run times and event tracking
SCHEDULE_TIMES_TIMEZONE=Europe/Athens

# Timezone for SQL queries and data display (timestamps in emails)
TIMEZONE=Europe/Athens

# ============================================================================
# ALERT-SPECIFIC CONFIGURATION
# ============================================================================

# Lookback period: Check crew contracts created in last N days
LOOKBACK_DAYS=1

# Rank ID for Masters (typically '1' for Captain/Master)
RANK_ID=1

# ============================================================================
# TRACKING & REMINDERS
# ============================================================================

# Reminder frequency (days after which to allow re-sending same alert)
# Set to empty or comment out to NEVER resend (track forever)
# REMINDER_FREQUENCY_DAYS=7  # Resend after 7 days
REMINDER_FREQUENCY_DAYS=  # Never resend (recommended for Masters Navigation Audit)

# Tracking file location
SENT_EVENTS_FILE=sent_alerts.json

# ============================================================================
# FEATURE FLAGS
# ============================================================================

# Enable/disable email notifications
ENABLE_EMAIL_ALERTS=True

# Enable/disable Microsoft Teams notifications (not yet implemented)
ENABLE_TEAMS_ALERTS=False

# Enable/disable special Teams email alert (not yet implemented)
ENABLE_SPECIAL_TEAMS_EMAIL_ALERT=False
SPECIAL_TEAMS_EMAIL=

# ============================================================================
# LINKS CONFIGURATION
# ============================================================================

# Enable clickable links in emails to crew contract details
ENABLE_LINKS=True

# Base URL for your application
BASE_URL=https://prominence.orca.tools/

# URL path pattern for crew contracts
# Example: https://prominence.orca.tools/events/123
URL_PATH=/events

# ============================================================================
# COMPANY BRANDING
# ============================================================================

# Logo file paths (relative to media/ directory)
PROMINENCE_LOGO=trans_logo_prominence_procreate_small.png
SEATRADERS_LOGO=trans_logo_seatraders_procreate_small.png

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
LOG_FILE=alerts.log
LOG_MAX_BYTES=10485760  # 10MB
LOG_BACKUP_COUNT=5

# ============================================================================
# RUNTIME MODE
# ============================================================================

# Dry-run mode: Test without sending real emails
# Can be overridden with --dry-run command line flag
DRY_RUN=True

# Dry-run email: Redirect all emails to this address in dry-run mode
# If empty, no emails will be sent at all in dry-run mode
DRY_RUN_EMAIL=test@yourcompany.com

# Run-once mode: Execute once and exit (no scheduling)
# Can be overridden with --run-once command line flag
RUN_ONCE=False
```

### Configuration Notes

#### Scheduling Options

You have two scheduling methods:

**Option 1: Interval-based (SCHEDULE_FREQUENCY_HOURS)**
- Runs continuously at regular intervals
- Example: `SCHEDULE_FREQUENCY_HOURS=1` runs every hour
- Example: `SCHEDULE_FREQUENCY_HOURS=0.5` runs every 30 minutes

**Option 2: Time-based (SCHEDULE_TIMES)**
- Runs at specific times each day
- Example: `SCHEDULE_TIMES=09:00,15:00` runs at 9 AM and 3 PM daily
- Uses 24-hour format (HH:MM)
- If both are set, SCHEDULE_TIMES takes precedence

#### Timezone Configuration

This system uses **two separate timezone settings**:

1. **`SCHEDULE_TIMES_TIMEZONE`** - For scheduler and tracking
   - Controls when alerts run (if using SCHEDULE_TIMES)
   - Controls event tracking timestamps
   - Example: `SCHEDULE_TIMES_TIMEZONE=Europe/Athens` means alerts run at 9:00 Athens time

2. **`TIMEZONE`** - For SQL queries and data display
   - Controls timezone conversion for database timestamps
   - Controls timezone shown in email notifications
   - Example: `TIMEZONE=Europe/Athens` means timestamps display in Athens time

**Typical setup**: Set both to the same timezone (e.g., `Europe/Athens`) for consistency.

#### Email Routing Logic

Emails are routed based on vessel email domain:

```
Vessel email: knossos@prominencemaritime.com
→ TO: knossos@prominencemaritime.com
→ CC: [PROMINENCE_EMAIL_CC_RECIPIENTS] + [INTERNAL_RECIPIENTS]

Vessel email: olympia@seatraders.com
→ TO: olympia@seatraders.com
→ CC: [SEATRADERS_EMAIL_CC_RECIPIENTS] + [INTERNAL_RECIPIENTS]
```

#### Tracking & Reminders

- **`REMINDER_FREQUENCY_DAYS` set**: Events can be re-sent after N days
  - Example: `REMINDER_FREQUENCY_DAYS=7` allows reminders after 7 days
  - Older events are automatically cleaned up from tracking file
  
- **`REMINDER_FREQUENCY_DAYS` empty/not set**: Events are tracked forever
  - Each crew contract will only trigger ONE notification ever
  - Recommended for Masters Navigation Audit (captain only needs one reminder)
  - Tracking file grows indefinitely (but this is usually fine)

#### Dry-Run Modes

**Mode 1: Dry-run without emails** (`DRY_RUN=True`, `DRY_RUN_EMAIL` empty)
- No emails sent at all
- Shows what would be sent in logs
- Use for: Initial setup, testing configurations

**Mode 2: Dry-run with email redirection** (`DRY_RUN=True`, `DRY_RUN_EMAIL=test@example.com`)
- Emails redirected to test address
- CC lists ignored
- Subject prefixed with `[DRY-RUN]`
- Use for: Testing email formatting, template rendering

**Mode 3: Production** (`DRY_RUN=False`)
- Real emails sent to real recipients
- Use for: Production deployment

---

## Usage

### Running the Application

#### Option 1: Docker (Recommended)

**Start the scheduler**:
```bash
docker-compose up -d
```

**View logs**:
```bash
docker-compose logs -f alerts
```

**Stop the scheduler**:
```bash
docker-compose down
```

**Restart after config changes**:
```bash
docker-compose down
docker-compose up -d
```

**Run once and exit** (good for testing):
```bash
docker-compose run --rm alerts python -m src.main --run-once
```

**Run in dry-run mode** (override .env):
```bash
docker-compose run --rm alerts python -m src.main --dry-run --run-once
```

#### Option 2: Local Python

**Activate virtual environment**:
```bash
source venv/bin/activate
```

**Run with scheduling** (continuous mode):
```bash
python -m src.main
```

**Run once and exit**:
```bash
python -m src.main --run-once
```

**Run in dry-run mode**:
```bash
python -m src.main --dry-run
```

**Combine flags**:
```bash
python -m src.main --dry-run --run-once
```

### Command-Line Flags

| Flag | Description | Overrides |
|------|-------------|-----------|
| `--dry-run` | Enable dry-run mode (no emails or redirect to test address) | `DRY_RUN` in .env |
| `--run-once` | Execute once and exit (no scheduling) | `RUN_ONCE` in .env |

**Priority**: Command-line flags > Environment variables

### Monitoring

**View live logs**:
```bash
# Docker
docker-compose logs -f alerts

# Local
tail -f logs/alerts.log
```

**Check container status**:
```bash
docker-compose ps
```

**Check container health**:
```bash
docker inspect --format='{{.State.Health.Status}}' masters-navigation-audit-app
```

**View tracking file**:
```bash
cat data/sent_alerts.json | jq '.'
```

---

## Testing

### Running Tests

**Run all tests**:
```bash
# Docker
docker-compose run --rm alerts pytest tests/ -v

# Local
pytest tests/ -v
```

**Run specific test file**:
```bash
pytest tests/test_masters_navigation_audit.py -v
```

**Run with coverage**:
```bash
pytest tests/ --cov=src --cov-report=html
```

**View coverage report**:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Test Structure

```
tests/
├── conftest.py                        # Shared fixtures
├── test_config.py                     # Configuration tests
├── test_db_utils.py                   # Database connection tests
├── test_email_sender.py               # Email sending tests
├── test_formatters.py                 # HTML/text formatting tests
├── test_integration.py                # End-to-end tests
├── test_masters_navigation_audit.py   # Masters Navigation Audit alert tests
├── test_scheduler.py                  # Scheduling tests
└── test_tracking.py                   # Event tracking tests
```

### Manual Testing Checklist

Before deploying to production, verify:

- [ ] Dry-run completes without errors: `docker-compose run --rm alerts python -m src.main --dry-run --run-once`
- [ ] SQL query returns expected columns (use query in `queries/MastersNavigationAudit.sql`)
- [ ] Email recipients configured correctly in `.env`
- [ ] CC recipients configured correctly per domain
- [ ] `DRY_RUN=False` in `.env` for production
- [ ] `DRY_RUN_EMAIL` contains valid test address for dry-run testing
- [ ] Company logos exist in `media/` directory and display in emails
- [ ] Link generation works (if `ENABLE_LINKS=True`)
- [ ] `BASE_URL` and `URL_PATH` configured correctly
- [ ] `RANK_ID=1` for Masters
- [ ] Tracking file updates after test run: `cat data/sent_alerts.json`
- [ ] No duplicates on second dry-run (same crew contracts not resent)
- [ ] Docker build succeeds: `docker-compose build`
- [ ] Container starts: `docker-compose up -d`
- [ ] Container stays running: `docker-compose ps`
- [ ] Logs show successful execution: `docker-compose logs -f alerts`
- [ ] Health check passes: `docker inspect --format='{{.State.Health.Status}}' masters-navigation-audit-app`
- [ ] Email greeting uses correct captain surname
- [ ] Email displays correct vessel name in subject

---

## Creating New Alert Projects

This project is designed to be easily copied and customized for new alert types. Here's how:

### Step 1: Copy the Project

```bash
cd ~/Dev
cp -r masters-navigation-audit-alerts new-alert-name-alerts
cd new-alert-name-alerts
```

### Step 2: Update Configuration

1. **Update `.env` file**:
   - Change `LOOKBACK_DAYS` if needed
   - Update `RANK_ID` or add new alert-specific parameters
   - Update `URL_PATH` for new alert type
   - Keep email routing and other core settings

2. **Update `docker-compose.yml`**:
   - Change `container_name` to `new-alert-name-app`

### Step 3: Create Alert Implementation

1. **Create new SQL query**: `queries/NewAlertName.sql`
   ```sql
   -- Example for hot works alert
   SELECT
       event_id,
       vessel_id,
       vessel_email,
       vessel_name,
       event_title,
       event_date,
       created_at
   FROM events
   WHERE event_type = 'hot_work'
     AND created_at >= NOW() - INTERVAL ':lookback_days days'
   ORDER BY created_at DESC;
   ```

2. **Create alert class**: `src/alerts/new_alert_name.py`
   ```python
   from src.core.base_alert import BaseAlert
   from src.core.config import AlertConfig
   
   class NewAlertNameAlert(BaseAlert):
       def __init__(self, config: AlertConfig):
           super().__init__(config)
           self.sql_query_file = 'NewAlertName.sql'
       
       def fetch_data(self) -> pd.DataFrame:
           # Query database
           pass
       
       def filter_data(self, df: pd.DataFrame) -> pd.DataFrame:
           # Apply filters
           pass
       
       def route_notifications(self, df: pd.DataFrame) -> List[Dict]:
           # Route to recipients
           pass
       
       def get_tracking_key(self, row: pd.Series) -> str:
           # Generate unique key
           return f"vessel_id_{row['vessel_id']}__event_id_{row['event_id']}"
       
       def get_subject_line(self, data: pd.DataFrame, metadata: Dict) -> str:
           # Generate subject
           return f"Alert | {metadata['vessel_name']} Hot Works Notification"
       
       def get_required_columns(self) -> List[str]:
           # List required columns
           return ['event_id', 'vessel_id', 'vessel_email', 'vessel_name']
   ```

3. **Register alert in `src/main.py`**:
   ```python
   from src.alerts.new_alert_name import NewAlertNameAlert
   
   def register_alerts(scheduler: AlertScheduler, config: AlertConfig) -> None:
       # ... existing alerts ...
       
       new_alert = NewAlertNameAlert(config)
       scheduler.register_alert(new_alert.run)
       logger.info("[OK] Registered NewAlertNameAlert")
   ```

### Step 4: Test

```bash
# Build
docker-compose build

# Test dry-run
docker-compose run --rm alerts python -m src.main --dry-run --run-once

# Deploy
docker-compose up -d
```

### What Stays the Same

When creating new alert types, you can reuse:
- ✅ `src/core/` - Configuration, scheduling, tracking, base alert class
- ✅ `src/notifications/` - Email and Teams senders
- ✅ `src/formatters/` - HTML and text formatters (or customize if needed)
- ✅ `src/utils/` - Validation and utility functions
- ✅ `db_utils.py` - Database connection handling
- ✅ `.dockerignore`, `Dockerfile`, `requirements.txt`

### What Changes

For each new alert type:
- ❌ `queries/*.sql` - Custom SQL query for your alert
- ❌ `src/alerts/*.py` - Alert-specific implementation
- ❌ `.env` - Alert-specific parameters (LOOKBACK_DAYS, RANK_ID, etc.)
- ❌ `README.md` - Update for new alert description
- ❌ `docker-compose.yml` - Update container name

---

## 🐳 Docker Deployment

### Docker Compose Configuration

```yaml
services:
  alerts:
    build:
      context: .
      args:
        UID: ${UID}
        GID: ${GID}
    container_name: masters-navigation-audit-app
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
      - ./queries:/app/queries
      - /Users/username/.ssh/ssh_key:/app/ssh_key:ro
      - /Users/username/.ssh/ssh_ubuntu_key:/app/ssh_ubuntu_key:ro
    restart: unless-stopped
```

### Volume Mounts

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `./logs` | `/app/logs` | Log files (persistent across restarts) |
| `./data` | `/app/data` | Tracking file (persistent across restarts) |
| `./queries` | `/app/queries` | SQL queries (allows updates without rebuild) |
| `~/.ssh/ssh_key` | `/app/ssh_key` | SSH key for database tunnel (read-only) |

### Health Check

The container includes an automatic health check:
- Runs every 1 hour
- Checks if log file was updated recently
- Container marked unhealthy if logs are stale

**Check health status**:
```bash
docker inspect --format='{{.State.Health.Status}}' masters-navigation-audit-app
```

### Container Management

**View container status**:
```bash
docker-compose ps
```

**View resource usage**:
```bash
docker stats masters-navigation-audit-app
```

**Execute command in running container**:
```bash
docker-compose exec alerts bash
```

**Rebuild after code changes**:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## Development

### Development Workflow

1. **Make changes** to source code
2. **Test locally**:
   ```bash
   python -m src.main --dry-run --run-once
   ```
3. **Run tests**:
   ```bash
   pytest tests/ -v
   ```
4. **Build Docker image**:
   ```bash
   docker-compose build
   ```
5. **Test in Docker**:
   ```bash
   docker-compose run --rm alerts python -m src.main --dry-run --run-once
   ```
6. **Deploy**:
   ```bash
   docker-compose up -d
   ```

### Code Style

This project follows Python best practices:
- **Type hints** for function signatures
- **Docstrings** for all classes and methods
- **Logging** instead of print statements
- **Error handling** with try/except blocks
- **Configuration** via environment variables (no hardcoded values)

### Adding New Features

#### Add a new configuration parameter:

1. Add to `.env`:
   ```bash
   NEW_PARAMETER=value
   ```

2. Add to `AlertConfig` dataclass in `src/core/config.py`:
   ```python
   @dataclass
   class AlertConfig:
       # ... existing fields ...
       new_parameter: str
   ```

3. Load in `AlertConfig.from_env()`:
   ```python
   return cls(
       # ... existing params ...
       new_parameter=config('NEW_PARAMETER', default='default_value'),
   )
   ```

4. Access in alerts:
   ```python
   value = self.config.new_parameter
   ```

#### Add a new notification channel:

1. Create sender in `src/notifications/`:
   ```python
   # src/notifications/slack_sender.py
   class SlackSender:
       def send(self, message: str, channel: str):
           # Implementation
           pass
   ```

2. Add configuration in `AlertConfig`
3. Initialize in `main.py`
4. Use in alert implementations

### Debugging Tips

**Enable debug logging**:
```python
# In src/main.py setup_logging()
logger.setLevel(logging.DEBUG)
```

**Test SQL query manually**:
```bash
# Connect to database
psql -h hostname -U username -d database

# Run query from queries/MastersNavigationAudit.sql
# Replace :lookback_days and :rank_id with actual values
```

**Inspect tracking file**:
```bash
# Pretty-print JSON
cat data/sent_alerts.json | jq '.'

# Count tracked events
cat data/sent_alerts.json | jq '.sent_events | length'

# Find specific crew contract
cat data/sent_alerts.json | jq '.sent_events | to_entries[] | select(.key | contains("crew_contract_id_123"))'
```

**Test email formatting**:
```python
# In Python REPL
from src.formatters.html_formatter import HTMLFormatter
from src.core.config import AlertConfig
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

config = AlertConfig.from_env()
formatter = HTMLFormatter()

# Create sample data
df = pd.DataFrame({
    'full_name': ['John Smith'],
    'rank': ['Master'],
    'sign_on_date': ['2024-01-15 10:00:00'],
    'due_date': ['2024-01-29']
})

metadata = {
    'vessel_name': 'KNOSSOS',
    'alert_title': "Master's Navigation Audit",
    'company_name': 'Prominence Maritime S.A.',
    'display_columns': ['full_name', 'rank', 'sign_on_date', 'due_date']
}

html = formatter.format(
    df, 
    datetime.now(tz=ZoneInfo('Europe/Athens')), 
    config, 
    metadata
)

# Save to file for inspection
with open('test_email.html', 'w') as f:
    f.write(html)
```

---

## Troubleshooting

### Common Issues

#### 1. Database connection fails

**Symptoms**: `psycopg2.OperationalError` or "connection refused"

**Causes**:
- Wrong database credentials
- Database host not accessible
- SSH tunnel not working
- Firewall blocking connection

**Solutions**:
```bash
# Test SSH tunnel manually
ssh -i ~/.ssh/ssh_ubuntu_key username@ssh.host.com

# Test database connection without tunnel
psql -h db.host.com -U username -d database

# Check .env settings
grep DB_ .env

# Verify SSH key permissions (must be 600)
chmod 600 ~/.ssh/ssh_ubuntu_key
ls -la ~/.ssh/ssh_ubuntu_key

# Test with Python
python -c "from src.db_utils import get_db_connection; conn = get_db_connection(); print('Success!')"
```

#### 2. SMTP authentication fails

**Symptoms**: `SMTPAuthenticationError` or "authentication failed"

**Causes**:
- Wrong SMTP credentials
- 2FA enabled without app password
- SMTP server settings incorrect

**Solutions**:
```bash
# For Gmail: Enable "Less secure app access" or create app password
# For Office365: Use app password or OAuth

# Test SMTP manually
python scripts/email_checker.py

# Check .env settings
grep SMTP .env
```

#### 3. No emails sent (even when data exists)

**Causes**:
- `ENABLE_EMAIL_ALERTS=False`
- `DRY_RUN=True` with empty `DRY_RUN_EMAIL`
- All events already tracked

**Solutions**:
```bash
# Check feature flags
grep ENABLE_EMAIL_ALERTS .env
grep DRY_RUN .env

# Check tracking file
cat data/sent_alerts.json | jq '.sent_events | length'

# Clear tracking to resend (CAUTION: Will resend everything!)
rm data/sent_alerts.json

# Or use dry-run to test
python -m src.main --dry-run --run-once
```

#### 4. Wrong timezone in emails

**Symptoms**: Timestamps show incorrect time zone

**Cause**: `TIMEZONE` not set correctly

**Solution**:
```bash
# Set in .env
TIMEZONE=Europe/Athens

# Verify in Python
python -c "from zoneinfo import ZoneInfo; import datetime; print(datetime.datetime.now(tz=ZoneInfo('Europe/Athens')))"
```

#### 5. Scheduler runs at wrong times

**Symptoms**: Alert runs at unexpected times (when using SCHEDULE_TIMES)

**Cause**: `SCHEDULE_TIMES_TIMEZONE` not set correctly

**Solution**:
```bash
# Set in .env
SCHEDULE_TIMES_TIMEZONE=Europe/Athens
SCHEDULE_TIMES=09:00,15:00

# Verify in logs - should show:
# "Next run scheduled at: 2024-12-05 09:00:00 EET"
docker-compose logs -f alerts | grep "Next run"
```

#### 6. Permission denied errors (Docker)

**Symptoms**: `PermissionError: [Errno 13] Permission denied: '/app/logs/alerts.log'`

**Cause**: Docker container doesn't have write permission to mounted volumes

**Solution**:
```bash
# Fix directory permissions
sudo chown -R $(id -u):$(id -g) logs/ data/

# Or use specific UID:GID
sudo chown -R 1000:1000 logs/ data/

# Verify permissions
ls -la logs/ data/

# Restart container
docker-compose down
docker-compose up -d
```

#### 7. Tests fail after git pull / Docker caching old modules

**Cause**: Docker is caching old Python bytecode

**Solution**:
```bash
# Complete Docker cache clear
docker-compose down -v && \
docker-compose build --no-cache && \
docker-compose run --rm alerts pytest tests/ -v
```

#### 8. No crew contracts found when there should be

**Causes**:
- `RANK_ID` doesn't match database values (should be '1' for Masters)
- `LOOKBACK_DAYS` too short
- Crew contracts already tracked in `sent_alerts.json`
- Sign-on date not within lookback period

**Solution**:
```bash
# Check rank_id values in database
# Connect to database and run:
SELECT DISTINCT rank_id, name 
FROM crew_contracts cc
LEFT JOIN crew_ranks cr ON cr.id = cc.rank_id
WHERE cc.sign_on_date_as_per_office >= NOW() - INTERVAL '7 days';

# Should return: rank_id='1', name='Master'

# Update RANK_ID in .env to match
RANK_ID=1

# Increase lookback if needed
LOOKBACK_DAYS=7  # Check last 7 days instead of 1

# Check if sign-on date is recent enough
SELECT 
    crew_member_id,
    sign_on_date_as_per_office,
    NOW() - sign_on_date_as_per_office as days_ago
FROM crew_contracts
WHERE rank_id = '1'
ORDER BY sign_on_date_as_per_office DESC
LIMIT 5;

# Clear tracking file to re-send (use cautiously!)
rm data/sent_alerts.json
```

#### 9. Email greeting shows wrong captain name

**Symptoms**: Email says "Dear Captain [Wrong Name]" or no greeting at all

**Cause**: `surname` column not in database results or contains NULL values

**Solution**:
```bash
# Check SQL query includes surname
cat queries/MastersNavigationAudit.sql | grep surname

# Should contain:
# p.last_name AS surname

# Verify data in database
psql -h hostname -U username -d database -c \
  "SELECT p.last_name AS surname FROM crew_contracts cc \
   LEFT JOIN parties p ON p.id = cc.crew_member_id \
   WHERE cc.rank_id = '1' LIMIT 5;"
```

### Logging & Debugging

```bash
# View live logs (local)
tail -f logs/alerts.log

# View live logs (Docker)
docker-compose logs -f alerts

# View last 100 lines
tail -n 100 logs/alerts.log

# Search for errors
grep ERROR logs/alerts.log

# Search for specific vessel
grep "KNOSSOS" logs/alerts.log

# Check tracking file
cat data/sent_alerts.json | jq '.'

# Count tracked crew contracts
cat data/sent_alerts.json | jq '.sent_events | length'

# Find specific crew contract in tracking
cat data/sent_alerts.json | jq '.sent_events | to_entries[] | select(.key | contains("crew_contract_id_123"))'

# Find all crew contracts for a vessel
cat data/sent_alerts.json | jq '.sent_events | to_entries[] | select(.key | contains("knossos"))'
```

### Testing Checklist

Before deploying to production:

- [ ] Dry-run completes without errors: `docker-compose run --rm alerts python -m src.main --dry-run --run-once`
- [ ] SQL query returns expected columns
- [ ] Email recipients configured correctly in `.env`
- [ ] CC recipients configured correctly per domain
- [ ] `DRY_RUN=False` in `.env` for production
- [ ] `DRY_RUN_EMAIL` contains valid test addresses
- [ ] Company logos exist in `media/` directory
- [ ] Link generation works (if `ENABLE_LINKS=True`)
- [ ] `BASE_URL` and `URL_PATH` configured correctly
- [ ] `RANK_ID=1` for Masters
- [ ] Both timezone settings configured: `TIMEZONE` and `SCHEDULE_TIMES_TIMEZONE`
- [ ] Tracking file updates after test run: `cat data/sent_alerts.json`
- [ ] No duplicates on second dry-run
- [ ] Docker build succeeds: `docker-compose build`
- [ ] Container starts: `docker-compose up -d`
- [ ] Container stays running: `docker-compose ps`
- [ ] Logs show successful execution: `docker-compose logs -f alerts`
- [ ] Health check passes: `docker inspect --format='{{.State.Health.Status}}' masters-navigation-audit-app`

---

## Key Concepts

### Alert Workflow

```
1. Scheduler triggers alert run (based on SCHEDULE_FREQUENCY_HOURS or SCHEDULE_TIMES)
   ↓
2. fetch_data() - Query database for Masters who recently signed on
   - WHERE rank_id = '1' (Master)
   - AND sign_on_date >= NOW() - LOOKBACK_DAYS
   - AND NOW() >= sign_on_date + 1 day (at least 1 day has passed)
   ↓
3. filter_data() - Apply timezone conversion and date formatting
   ↓
4. Check tracking - Skip already-sent crew contracts
   ↓
5. route_notifications() - Group by vessel, add captain greeting, create email jobs
   ↓
6. Send emails - One email per vessel with crew contract details
   ↓
7. Update tracking - Mark crew contracts as sent
```

### Tracking Key Format

```python
def get_tracking_key(self, row: pd.Series) -> str:
    vessel = row['vessel']
    crew_contract_id = row['crew_contract_id']
    crew_member_id = row['crew_member_id']
    
    return f"{vessel.lower()}__crew_contract_id_{crew_contract_id}__crew_member_id_{crew_member_id}"

# Example: "knossos__crew_contract_id_456__crew_member_id_123"
```

This ensures uniqueness across:
- Different vessels (knossos vs olympia)
- Different crew contracts (456 vs 789)
- Different crew members (123 vs 456)

### Email Content

**Subject**: `AlertDev | KNOSSOS Master's Navigation Audit`

**Body** includes:
- **Personalized greeting**: "Dear Captain [Surname],"
- **Requirements reminder**: F.NAV.13, F.MLC.1, Crew List due within 14 days
- **Responsive HTML table** with:
  - **Full Name** - Captain's full name
  - **Rank** - Should always be "Master"
  - **Sign On Date** - When captain signed on (YYYY-MM-DD HH:MM:SS)
  - **Due Date** - 14 days after sign-on (YYYY-MM-DD)
- **Company branding**: Logos for Prominence and/or Seatraders

### Configuration Flow

```
.env file
  ↓
python-decouple reads file
  ↓
AlertConfig.from_env() parses values
  ↓
AlertConfig dataclass instance created
  ↓
Passed to all components (alerts, formatters, senders)
  ↓
Accessed via self.config throughout application
```

### Timezone Handling

**Two timezone settings work together**:

1. **Data/Display Timezone (`TIMEZONE`)**:
   - Used in SQL queries for datetime filtering
   - Used for displaying timestamps in emails
   - Converts database UTC timestamps to local time
   - Example: Database has `2024-01-15 08:00:00 UTC`, displays as `2024-01-15 10:00:00 EET`

2. **Scheduler Timezone (`SCHEDULE_TIMES_TIMEZONE`)**:
   - Used for time-based scheduling (SCHEDULE_TIMES)
   - Used for event tracking timestamps
   - Example: `SCHEDULE_TIMES=09:00` with `SCHEDULE_TIMES_TIMEZONE=Europe/Athens` runs at 9 AM Athens time

**Why separate?**
- Allows scheduling in one timezone while displaying data in another
- Most users will set both to the same value
- Example use case: Schedule alerts in UTC but display timestamps in local time

---

## Project Structure

```
masters-navigation-audit-alerts/
├── data/                           # Persistent data (gitignored)
│   └── sent_alerts.json           # Tracking file for sent notifications
├── docs/                           # Documentation
│   ├── AlertDev.docx              # Development documentation
│   └── example.pdf                # Example outputs
├── logs/                           # Log files (gitignored)
│   └── alerts.log                 # Application logs
├── media/                          # Static assets
│   ├── trans_logo_prominence_procreate_small.png
│   └── trans_logo_seatraders_procreate_small.png
├── queries/                        # SQL query files
│   └── MastersNavigationAudit.sql # Main SQL query
├── scripts/                        # Utility scripts
│   ├── email_checker.py           # Test SMTP connection
│   └── verify_teams_webhook.py    # Test Teams webhook
├── src/                            # Source code
│   ├── alerts/                     # Alert implementations
│   │   ├── __init__.py
│   │   └── masters_navigation_audit.py  # Masters Navigation Audit alert
│   ├── core/                       # Core infrastructure
│   │   ├── __init__.py
│   │   ├── base_alert.py          # Abstract base class for alerts
│   │   ├── config.py              # Configuration management
│   │   ├── scheduler.py           # Scheduling system
│   │   └── tracking.py            # Event tracking system
│   ├── formatters/                 # Email formatters
│   │   ├── __init__.py
│   │   ├── date_formatter.py      # Date/time formatting utilities
│   │   ├── html_formatter.py      # HTML email templates
│   │   └── text_formatter.py      # Plain text email templates
│   ├── notifications/              # Notification handlers
│   │   ├── __init__.py
│   │   ├── email_sender.py        # Email sending via SMTP
│   │   └── teams_sender.py        # Teams notifications (planned)
│   ├── utils/                      # Utilities
│   │   ├── __init__.py
│   │   ├── image_utils.py         # Image loading for emails
│   │   └── validation.py          # Data validation
│   ├── __init__.py
│   ├── db_utils.py                # Database connection utilities
│   └── main.py                    # Application entry point
├── tests/                          # Test suite
│   ├── __init__.py
│   ├── conftest.py                # Shared test fixtures
│   ├── test_config.py             # Configuration tests
│   ├── test_db_utils.py           # Database tests
│   ├── test_email_sender.py       # Email sending tests
│   ├── test_formatters.py         # Formatting tests
│   ├── test_integration.py        # End-to-end tests
│   ├── test_masters_navigation_audit.py  # Alert-specific tests
│   ├── test_scheduler.py          # Scheduling tests
│   └── test_tracking.py           # Tracking tests
├── .dockerignore                   # Docker ignore rules
├── .env                            # Environment variables (gitignored)
├── .env.example                    # Example environment configuration
├── .gitignore                      # Git ignore rules
├── docker-compose.yml              # Docker Compose configuration
├── Dockerfile                      # Docker image definition
├── pytest.ini                      # Pytest configuration
├── README.md                       # This file
├── requirements-dev.txt            # Development dependencies
└── requirements.txt                # Production dependencies
```

---

## Support

For questions or issues:

1. **Check this README** - Most answers are here
2. **Review logs**: `docker-compose logs -f alerts`
3. **Test in dry-run**: `docker-compose run --rm alerts python -m src.main --dry-run --run-once`
4. **Check tracking file**: `cat data/sent_alerts.json | jq '.'`
5. **Verify database query**: Run `queries/MastersNavigationAudit.sql` manually
6. **Contact**: data@prominencemaritime.com

---

## License

Proprietary - Prominence Maritime / Seatraders

---

## Quick Start Summary

```bash
# 1. Copy/clone project
cd ~/Dev
git clone <repository> masters-navigation-audit-alerts
cd masters-navigation-audit-alerts

# 2. Configure
cp .env.example .env
vi .env  # Update all settings

# 3. Fix permissions
sudo chown -R $(id -u):$(id -g) logs/ data/

# 4. Test dry-run
export UID=$(id -u) GID=$(id -g)
docker-compose build
docker-compose run --rm alerts python -m src.main --dry-run --run-once

# 5. Deploy
docker-compose up -d

# 6. Monitor
docker-compose logs -f alerts

# 7. Check health
docker inspect --format='{{.State.Health.Status}}' masters-navigation-audit-app
```

**That's it! You now have a production-ready Master's Navigation Audit alert system.** 🚀

---

## Additional Resources

- **Python decouple docs**: https://pypi.org/project/python-decouple/
- **Pandas documentation**: https://pandas.pydata.org/docs/
- **Docker Compose docs**: https://docs.docker.com/compose/
- **Pytest documentation**: https://docs.pytest.org/
- **SSH tunnel guide**: https://www.ssh.com/academy/ssh/tunneling
- **ZoneInfo timezone database**: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

---

*Last updated: December 2025*
