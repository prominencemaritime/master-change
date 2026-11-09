# tests/test_config.py
"""
Tests for configuration loading and validation.
"""
import pytest
from pathlib import Path
from src.core.config import AlertConfig


def test_config_from_env_loads_successfully(monkeypatch, temp_dir):
    """Test that configuration loads from environment variables."""
    # Clear any existing .env values that might interfere
    import os
    if 'LOOKBACK_DAYS' in os.environ:
        del os.environ['LOOKBACK_DAYS']

    # Set environment variables
    monkeypatch.setenv('DB_HOST', 'localhost')
    monkeypatch.setenv('DB_PORT', '5432')
    monkeypatch.setenv('DB_NAME', 'test_db')
    monkeypatch.setenv('DB_USER', 'test_user')
    monkeypatch.setenv('DB_PASS', 'test_pass')
    monkeypatch.setenv('SMTP_HOST', 'smtp.test.com')
    monkeypatch.setenv('SMTP_PORT', '465')
    monkeypatch.setenv('SMTP_USER', 'test@test.com')
    monkeypatch.setenv('SMTP_PASS', 'test_pass')
    monkeypatch.setenv('BASE_URL', 'https://test.com')
    monkeypatch.setenv('TIMEZONE', 'Europe/Athens')
    monkeypatch.setenv('LOOKBACK_DAYS', '1')

    config = AlertConfig.from_env(project_root=temp_dir)

    # Check config attributes that actually exist
    assert config.smtp_user == 'test@test.com'
    assert config.base_url == 'https://test.com'
    assert config.schedule_frequency_hours == 1


def test_config_validation_passes_with_valid_data(mock_config):
    """Test that validation passes with valid configuration."""
    # Should not raise any exceptions
    mock_config.validate()


def test_config_validation_fails_without_smtp_credentials(mock_config):
    """Test that validation fails when email enabled but no SMTP credentials."""
    mock_config.enable_email_alerts = True
    mock_config.smtp_user = ''

    with pytest.raises(ValueError, match="Required configuration missing"):
        mock_config.validate()


def test_config_email_routing_loaded_correctly(mock_config):
    """Test that email routing dictionary is properly loaded."""
    assert 'prominencemaritime.com' in mock_config.email_routing
    assert 'seatraders.com' in mock_config.email_routing

    # Email routing has nested structure: {'domain': {'cc': [emails]}}
    assert 'cc' in mock_config.email_routing['prominencemaritime.com']
    assert len(mock_config.email_routing['prominencemaritime.com']['cc']) == 2


def test_config_reminder_frequency_none_when_empty(monkeypatch, temp_dir):
    """Test that REMINDER_FREQUENCY_DAYS='' results in None."""
    monkeypatch.setenv('REMINDER_FREQUENCY_DAYS', '')
    monkeypatch.setenv('DB_HOST', 'localhost')
    monkeypatch.setenv('SMTP_HOST', 'smtp.test.com')

    config = AlertConfig.from_env(project_root=temp_dir)

    assert config.reminder_frequency_days is None


def test_config_dry_run_email_loads_correctly(monkeypatch, temp_dir):
    """Test that DRY_RUN_EMAIL loads correctly."""
    monkeypatch.setenv('DRY_RUN_EMAIL', 'test@test.com')
    monkeypatch.setenv('DB_HOST', 'localhost')
    monkeypatch.setenv('SMTP_HOST', 'smtp.test.com')

    config = AlertConfig.from_env(project_root=temp_dir)

    assert config.dry_run_email == 'test@test.com'
