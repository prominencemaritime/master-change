# tests/conftest.py
"""
Shared pytest fixtures for all tests.
"""
import pytest
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import json
from unittest.mock import Mock, MagicMock

from src.core.config import AlertConfig
from src.core.tracking import EventTracker
from src.core.scheduler import AlertScheduler
from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config(temp_dir, monkeypatch):
    """Create a mock AlertConfig for testing."""
    # Set minimal required environment variables
    monkeypatch.setenv('DB_HOST', 'localhost')
    monkeypatch.setenv('DB_PORT', '5432')
    monkeypatch.setenv('DB_NAME', 'test_db')
    monkeypatch.setenv('DB_USER', 'test_user')
    monkeypatch.setenv('DB_PASS', 'test_pass')
    monkeypatch.setenv('USE_SSH_TUNNEL', 'False')
    
    monkeypatch.setenv('SMTP_HOST', 'smtp.test.com')
    monkeypatch.setenv('SMTP_PORT', '465')
    monkeypatch.setenv('SMTP_USER', 'test@test.com')
    monkeypatch.setenv('SMTP_PASS', 'test_pass')
    
    monkeypatch.setenv('INTERNAL_RECIPIENTS', 'internal@test.com')
    monkeypatch.setenv('PROMINENCE_EMAIL_CC_RECIPIENTS', 'prom1@test.com,prom2@test.com')
    monkeypatch.setenv('SEATRADERS_EMAIL_CC_RECIPIENTS', 'sea1@test.com,sea2@test.com')
    
    monkeypatch.setenv('ENABLE_EMAIL_ALERTS', 'True')
    monkeypatch.setenv('ENABLE_TEAMS_ALERTS', 'False')
    
    monkeypatch.setenv('SCHEDULE_FREQUENCY_HOURS', '0.5')
    monkeypatch.setenv('TIMEZONE', 'Europe/Athens')
    monkeypatch.setenv('REMINDER_FREQUENCY_DAYS', '')  # None
    
    monkeypatch.setenv('BASE_URL', 'https://test.orca.tools')
    monkeypatch.setenv('LOOKBACK_DAYS', '4')
    monkeypatch.setenv('RANK_ID', '1')
    monkeypatch.setenv('ENABLE_LINKS', 'True')
    monkeypatch.setenv('URL_PATH', '/events')
    
    monkeypatch.setenv('DRY_RUN_EMAIL', '')
    
    # Create directories
    (temp_dir / 'queries').mkdir(parents=True, exist_ok=True)
    (temp_dir / 'media').mkdir(parents=True, exist_ok=True)
    (temp_dir / 'logs').mkdir(parents=True, exist_ok=True)
    (temp_dir / 'data').mkdir(parents=True, exist_ok=True)
    
    # Load config from environment
    config = AlertConfig.from_env(project_root=temp_dir)
    
    return config


@pytest.fixture
def sample_dataframe():
    """Create sample Masters Navigation Audit DataFrame with correct schema."""
    data = {
        'crew_contract_id': [48941, 48942, 48943, 48944],
        'crew_member_id': [201, 202, 203, 204],
        'vessel_id': [1, 1, 2, 2],
        'vessel': ['VESSEL', 'VESSEL', 'OTHER VESSEL', 'OTHER VESSEL'],
        'vsl_email': [
            'test@prominencemaritime.com',
            'test@prominencemaritime.com',
            'test2@seatraders.com',
            'test2@seatraders.com'
        ],
        'surname': ['Smith', 'Jones', 'Brown', 'Wilson'],
        'full_name': ['John Smith', 'Jane Jones', 'Bob Brown', 'Alice Wilson'],
        'rank': ['Captain', 'Captain', 'Captain', 'Captain'],
        'sign_on_date': [
            datetime.now() - timedelta(days=1),
            datetime.now() - timedelta(days=2),
            datetime.now() - timedelta(hours=12),
            datetime.now() - timedelta(hours=6)
        ],
        'due_date': [
            (datetime.now() - timedelta(days=1) + timedelta(days=14)).date(),
            (datetime.now() - timedelta(days=2) + timedelta(days=14)).date(),
            (datetime.now() - timedelta(hours=12) + timedelta(days=14)).date(),
            (datetime.now() - timedelta(hours=6) + timedelta(days=14)).date()
        ]
    }
    return pd.DataFrame(data)


@pytest.fixture
def mock_email_sender():
    """Create mock EmailSender."""
    sender = Mock()
    sender.send = Mock()
    return sender


@pytest.fixture
def mock_event_tracker(temp_dir):
    """Create EventTracker with temporary file."""
    tracking_file = temp_dir / 'test_tracking.json'
    tracker = EventTracker(
        tracking_file=tracking_file,
        reminder_frequency_days=None,
        schedule_times_timezone='Europe/Athens'
    )
    return tracker


@pytest.fixture
def mock_db_connection():
    """Mock database connection context manager."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    def mock_get_db_connection():
        return mock_conn
    
    return mock_get_db_connection, mock_cursor
