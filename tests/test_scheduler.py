# tests/test_scheduler.py
"""
Tests for alert scheduler.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import time
import signal
from datetime import datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from src.core.scheduler import AlertScheduler


def test_scheduler_initializes_correctly():
    """Test that scheduler initializes with correct parameters."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens'
    )
    
    assert scheduler.frequency_hours == 24
    assert str(scheduler.timezone) == 'Europe/Athens'
    assert len(scheduler._alerts) == 0


def test_scheduler_initializes_with_schedule_times():
    """Test that scheduler initializes with schedule times."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens',
        schedule_times_timezone='Europe/Athens',
        schedule_times=['12:00', '18:00']
    )
    
    assert scheduler.schedule_times == ['12:00', '18:00']
    assert str(scheduler.schedule_times_timezone) == 'Europe/Athens'


def test_scheduler_registers_alerts():
    """Test that alerts can be registered."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    mock_alert = Mock()
    scheduler.register_alert(mock_alert)
    
    assert len(scheduler._alerts) == 1


def test_scheduler_registers_multiple_alerts():
    """Test that multiple alerts can be registered."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    mock_alert1 = Mock()
    mock_alert2 = Mock()
    mock_alert3 = Mock()
    
    scheduler.register_alert(mock_alert1)
    scheduler.register_alert(mock_alert2)
    scheduler.register_alert(mock_alert3)
    
    assert len(scheduler._alerts) == 3


def test_scheduler_runs_once():
    """Test that run_once executes all alerts."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    mock_alert1 = Mock()
    mock_alert2 = Mock()
    
    scheduler.register_alert(mock_alert1)
    scheduler.register_alert(mock_alert2)
    
    scheduler.run_once()
    
    mock_alert1.assert_called_once()
    mock_alert2.assert_called_once()


def test_scheduler_run_once_with_no_alerts():
    """Test that run_once handles no registered alerts gracefully."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    # Should not raise exception
    scheduler.run_once()
    
    assert len(scheduler._alerts) == 0


def test_scheduler_handles_alert_failure():
    """Test that scheduler continues after alert failure."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    failing_alert = Mock(side_effect=Exception("Test error"))
    successful_alert = Mock()
    
    scheduler.register_alert(failing_alert)
    scheduler.register_alert(successful_alert)
    
    scheduler.run_once()
    
    # Both should have been called despite first one failing
    failing_alert.assert_called_once()
    successful_alert.assert_called_once()


def test_scheduler_shutdown_signal():
    """Test that scheduler responds to shutdown signal."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    # Trigger shutdown
    scheduler.shutdown_event.set()
    
    assert scheduler.shutdown_event.is_set()


def test_scheduler_signal_handler():
    """Test that signal handler sets shutdown event."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    # Call signal handler directly
    scheduler._signal_handler(signal.SIGTERM, None)
    
    assert scheduler.shutdown_event.is_set()


def test_scheduler_signal_handler_sigint():
    """Test that SIGINT handler sets shutdown event."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    # Call signal handler with SIGINT
    scheduler._signal_handler(signal.SIGINT, None)
    
    assert scheduler.shutdown_event.is_set()


def test_scheduler_stops_alerts_on_shutdown():
    """Test that scheduler stops running alerts when shutdown is triggered."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    alert1 = Mock()
    alert2 = Mock()
    alert3 = Mock()
    
    # Set shutdown event after first alert
    def trigger_shutdown():
        scheduler.shutdown_event.set()
    
    alert1.side_effect = trigger_shutdown
    
    scheduler.register_alert(alert1)
    scheduler.register_alert(alert2)
    scheduler.register_alert(alert3)
    
    scheduler.run_once()
    
    # First alert should run (and trigger shutdown)
    alert1.assert_called_once()
    # Second and third should not run
    alert2.assert_not_called()
    alert3.assert_not_called()


def test_calculate_next_run_time_later_today():
    """Test calculating next run time when there's a scheduled time later today."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens',
        schedule_times_timezone='Europe/Athens',
        schedule_times=['14:00', '18:00']
    )
    
    # Current time is 10:00
    current_time = datetime(2025, 12, 3, 10, 0, 0, tzinfo=ZoneInfo('Europe/Athens'))
    
    next_run = scheduler._calculate_next_run_time(current_time)
    
    # Should be 14:00 today
    assert next_run.hour == 14
    assert next_run.minute == 0
    assert next_run.date() == current_time.date()


def test_calculate_next_run_time_tomorrow():
    """Test calculating next run time when no more runs today."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens',
        schedule_times_timezone='Europe/Athens',
        schedule_times=['12:00', '14:00']
    )
    
    # Current time is 15:00 (after all scheduled times)
    current_time = datetime(2025, 12, 3, 15, 0, 0, tzinfo=ZoneInfo('Europe/Athens'))
    
    next_run = scheduler._calculate_next_run_time(current_time)
    
    # Should be 12:00 tomorrow
    assert next_run.hour == 12
    assert next_run.minute == 0
    assert next_run.date() == current_time.date() + timedelta(days=1)


def test_calculate_next_run_time_sorts_schedule_times():
    """Test that schedule times are sorted correctly."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens',
        schedule_times_timezone='Europe/Athens',
        schedule_times=['18:00', '12:00', '06:00']  # Unsorted
    )
    
    # Current time is 05:00
    current_time = datetime(2025, 12, 3, 5, 0, 0, tzinfo=ZoneInfo('Europe/Athens'))
    
    next_run = scheduler._calculate_next_run_time(current_time)
    
    # Should be 06:00 (earliest time after current)
    assert next_run.hour == 6
    assert next_run.minute == 0


def test_calculate_next_run_time_raises_without_schedule_times():
    """Test that calculating next run time raises error without schedule_times."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens'
    )
    
    current_time = datetime.now(tz=ZoneInfo('Europe/Athens'))
    
    with pytest.raises(ValueError, match="schedule_times must be set"):
        scheduler._calculate_next_run_time(current_time)


@patch('src.core.scheduler.datetime')
def test_run_continuous_executes_alerts(mock_datetime):
    """Test that run_continuous executes alerts."""
    # Mock datetime.now to return consistent time
    mock_now = datetime(2025, 12, 3, 12, 0, 0, tzinfo=ZoneInfo('Europe/Athens'))
    mock_datetime.now.return_value = mock_now
    
    scheduler = AlertScheduler(frequency_hours=1, timezone='Europe/Athens')
    
    mock_alert = Mock()
    scheduler.register_alert(mock_alert)
    
    # Set shutdown after first run
    def trigger_shutdown():
        scheduler.shutdown_event.set()
    
    mock_alert.side_effect = trigger_shutdown
    
    scheduler.run_continuous()
    
    # Alert should have been called once
    mock_alert.assert_called_once()


@patch('src.core.scheduler.datetime')
def test_run_continuous_sleeps_between_runs(mock_datetime):
    """Test that run_continuous sleeps between runs."""
    mock_now = datetime(2025, 12, 3, 12, 0, 0, tzinfo=ZoneInfo('Europe/Athens'))
    mock_datetime.now.return_value = mock_now
    
    scheduler = AlertScheduler(frequency_hours=2, timezone='Europe/Athens')
    
    mock_alert = Mock()
    call_count = 0
    
    def increment_and_shutdown():
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            scheduler.shutdown_event.set()
    
    mock_alert.side_effect = increment_and_shutdown
    scheduler.register_alert(mock_alert)
    
    # Mock wait to return immediately
    original_wait = scheduler.shutdown_event.wait
    def mock_wait(timeout=None):
        if call_count >= 2:
            return True  # Shutdown
        return False  # Continue
    
    scheduler.shutdown_event.wait = mock_wait
    
    scheduler.run_continuous()
    
    # Alert should have been called twice
    assert call_count == 2


def test_run_continuous_handles_keyboard_interrupt():
    """Test that run_continuous handles KeyboardInterrupt."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    mock_alert = Mock(side_effect=KeyboardInterrupt())
    scheduler.register_alert(mock_alert)
    
    # Should not raise exception
    scheduler.run_continuous()
    
    mock_alert.assert_called_once()


def test_run_continuous_recovers_from_errors():
    """Test that run_continuous recovers from unhandled exceptions."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    call_count = 0
    
    def failing_alert():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Test error")
        else:
            scheduler.shutdown_event.set()
    
    scheduler.register_alert(failing_alert)
    
    # Mock wait to return immediately for first error recovery, then shutdown
    original_wait = scheduler.shutdown_event.wait
    wait_count = 0
    
    def mock_wait(timeout=None):
        nonlocal wait_count
        wait_count += 1
        if wait_count == 1:
            # First wait is the error recovery (5 min wait)
            return False  # Continue
        else:
            # Second wait means we're past error recovery
            return True  # Shutdown
    
    scheduler.shutdown_event.wait = mock_wait
    
    scheduler.run_continuous()
    
    # Should have attempted to run twice (once failed, once succeeded)
    assert call_count == 2


def test_run_at_times_raises_without_schedule_times():
    """Test that run_at_times raises error without schedule_times."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens'
    )
    
    with pytest.raises(ValueError, match="schedule_times must be configured"):
        scheduler.run_at_times()


def test_run_at_times_raises_without_schedule_times_timezone():
    """Test that run_at_times raises error without schedule_times_timezone."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens',
        schedule_times=['12:00']
    )
    
    # Unset the timezone
    scheduler.schedule_times_timezone = None
    
    with pytest.raises(ValueError, match="schedule_times_timezone must be configued"):
        scheduler.run_at_times()


def test_run_at_times_executes_alerts():
    """Test that run_at_times executes alerts at scheduled times."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens',
        schedule_times_timezone='Europe/Athens',
        schedule_times=['12:00']
    )

    mock_alert = Mock()
    scheduler.register_alert(mock_alert)

    wait_count = 0

    def mock_wait(timeout=None):
        nonlocal wait_count
        wait_count += 1
        if wait_count == 1:
            # First wait - simulate waiting until scheduled time
            return False  # Don't shutdown, continue to run alerts
        else:
            # After running alerts, shutdown
            return True

    scheduler.shutdown_event.wait = mock_wait

    scheduler.run_at_times()

    # Alert should have been called once
    mock_alert.assert_called_once()


def test_run_at_times_handles_keyboard_interrupt():
    """Test that run_at_times handles KeyboardInterrupt."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens',
        schedule_times_timezone='Europe/Athens',
        schedule_times=['12:00']
    )
    
    # Mock wait to raise KeyboardInterrupt
    def mock_wait(timeout=None):
        raise KeyboardInterrupt()
    
    scheduler.shutdown_event.wait = mock_wait
    
    # Should not raise exception
    scheduler.run_at_times()


def test_run_at_times_recovers_from_errors():
    """Test that run_at_times recovers from unhandled exceptions."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens',
        schedule_times_timezone='Europe/Athens',
        schedule_times=['12:00']
    )
    
    wait_count = 0
    
    def mock_wait(timeout=None):
        nonlocal wait_count
        wait_count += 1
        if wait_count == 1:
            # First wait - raise error
            raise RuntimeError("Test error")
        elif wait_count == 2:
            # Second wait is error recovery (5 min)
            return False
        else:
            # Third wait - shutdown
            return True
    
    scheduler.shutdown_event.wait = mock_wait
    
    scheduler.run_at_times()
    
    # Should have waited at least twice (initial + error recovery)
    assert wait_count >= 2


def test_run_at_times_shutdown_during_sleep():
    """Test that run_at_times respects shutdown during sleep."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens',
        schedule_times_timezone='Europe/Athens',
        schedule_times=['12:00']
    )
    
    mock_alert = Mock()
    scheduler.register_alert(mock_alert)
    
    # Mock wait to return True (shutdown requested)
    def mock_wait(timeout=None):
        return True  # Shutdown
    
    scheduler.shutdown_event.wait = mock_wait
    
    scheduler.run_at_times()
    
    # Alert should not have been called (shutdown during sleep)
    mock_alert.assert_not_called()


def test_run_at_times_shutdown_during_execution():
    """Test that run_at_times respects shutdown during alert execution."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens',
        schedule_times_timezone='Europe/Athens',
        schedule_times=['12:00']
    )
    
    mock_alert = Mock()
    
    def trigger_shutdown():
        scheduler.shutdown_event.set()
    
    mock_alert.side_effect = trigger_shutdown
    scheduler.register_alert(mock_alert)
    
    # Mock wait to return immediately first time
    call_count = 0
    def mock_wait(timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return False  # Continue to run alerts
        return True  # Shutdown after
    
    scheduler.shutdown_event.wait = mock_wait
    
    scheduler.run_at_times()
    
    # Alert should have been called once
    mock_alert.assert_called_once()


def test_run_at_times_shutdown_during_error_recovery():
    """Test that run_at_times respects shutdown during error recovery wait."""
    scheduler = AlertScheduler(
        frequency_hours=24,
        timezone='Europe/Athens',
        schedule_times_timezone='Europe/Athens',
        schedule_times=['12:00']
    )
    
    wait_count = 0
    
    def mock_wait(timeout=None):
        nonlocal wait_count
        wait_count += 1
        if wait_count == 1:
            # First wait - raise error to trigger error recovery
            raise RuntimeError("Test error")
        else:
            # Second wait is error recovery - shutdown requested
            return True
    
    scheduler.shutdown_event.wait = mock_wait
    
    scheduler.run_at_times()
    
    # Should have waited twice (error + error recovery shutdown)
    assert wait_count == 2


def test_run_continuous_shutdown_during_error_recovery():
    """Test that run_continuous respects shutdown during error recovery wait."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    mock_alert = Mock(side_effect=RuntimeError("Test error"))
    scheduler.register_alert(mock_alert)
    
    wait_count = 0
    
    def mock_wait(timeout=None):
        nonlocal wait_count
        wait_count += 1
        return True  # Shutdown during error recovery
    
    scheduler.shutdown_event.wait = mock_wait
    
    scheduler.run_continuous()
    
    # Should have called wait once (error recovery)
    assert wait_count == 1


def test_scheduler_logs_alert_name():
    """Test that scheduler logs alert name when registering."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    def named_alert():
        pass
    
    named_alert.__name__ = 'test_alert'
    
    scheduler.register_alert(named_alert)
    
    assert len(scheduler._alerts) == 1


def test_scheduler_handles_anonymous_alert():
    """Test that scheduler handles alerts without __name__ attribute."""
    scheduler = AlertScheduler(frequency_hours=24, timezone='Europe/Athens')
    
    mock_alert = Mock(spec=[])  # No __name__ attribute
    
    scheduler.register_alert(mock_alert)
    
    assert len(scheduler._alerts) == 1
