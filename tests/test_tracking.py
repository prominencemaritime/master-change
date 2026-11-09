# tests/test_tracking.py
"""
Tests for event tracking and duplicate prevention.
"""
import pytest
from datetime import datetime, timedelta
import json


def test_tracker_initializes_with_empty_file(mock_event_tracker):
    """Test that tracker initializes correctly with no existing file."""
    assert len(mock_event_tracker.sent_events) == 0


def test_tracker_marks_events_as_sent(mock_event_tracker):
    """Test marking events as sent."""
    keys = {'event_1', 'event_2', 'event_3'}
    run_time = datetime.now()

    mock_event_tracker.mark_as_sent(keys, run_time)

    assert len(mock_event_tracker.sent_events) == 3
    assert 'event_1' in mock_event_tracker.sent_events


def test_tracker_identifies_already_sent_events(mock_event_tracker):
    """Test that tracker identifies previously sent events."""
    keys = {'event_1', 'event_2'}
    run_time = datetime.now()

    # Mark as sent
    mock_event_tracker.mark_as_sent(keys, run_time)

    # Check if already sent
    assert mock_event_tracker.is_sent('event_1') is True
    assert mock_event_tracker.is_sent('event_3') is False


def test_tracker_persists_to_file(mock_event_tracker):
    """Test that tracker saves data to file."""
    keys = {'event_1'}
    run_time = datetime.now()

    mock_event_tracker.mark_as_sent(keys, run_time)

    # Check file exists and contains data
    assert mock_event_tracker.tracking_file.exists()

    with open(mock_event_tracker.tracking_file, 'r') as f:
        data = json.load(f)

    assert 'event_1' in data['sent_events']


def test_tracker_loads_existing_data(temp_dir):
    """Test that tracker loads existing tracking data."""
    from src.core.tracking import EventTracker

    tracking_file = temp_dir / 'tracking.json'

    # Create initial tracker and save data
    tracker1 = EventTracker(
        tracking_file=tracking_file,
        reminder_frequency_days=None,
        schedule_times_timezone='Europe/Athens'
    )
    tracker1.mark_as_sent({'event_1'}, datetime.now())

    # Create new tracker instance (should load existing data)
    tracker2 = EventTracker(
        tracking_file=tracking_file,
        reminder_frequency_days=None,
        schedule_times_timezone='Europe/Athens'
    )

    assert tracker2.is_sent('event_1') is True


def test_tracker_cleans_old_events_with_reminder_frequency(temp_dir):
    """Test that old events are removed when reminder frequency is set."""
    from src.core.tracking import EventTracker
    from datetime import timezone

    tracking_file = temp_dir / 'tracking.json'

    # Create tracker with 7-day reminder frequency
    tracker = EventTracker(
        tracking_file=tracking_file,
        reminder_frequency_days=7.0,
        schedule_times_timezone='Europe/Athens'
    )

    # Use timezone-aware datetimes (required by tracker)
    import zoneinfo
    tz = zoneinfo.ZoneInfo('Europe/Athens')

    # Add old event (10 days ago)
    old_time = datetime.now(tz=tz) - timedelta(days=10)
    tracker.sent_events['old_event'] = old_time.isoformat()
    tracker._save()

    # Add recent event (1 day ago)
    recent_time = datetime.now(tz=tz) - timedelta(days=1)
    tracker.sent_events['recent_event'] = recent_time.isoformat()
    tracker._save()

    # Reload (should clean up old event)
    tracker2 = EventTracker(
        tracking_file=tracking_file,
        reminder_frequency_days=7.0,
        schedule_times_timezone='Europe/Athens'
    )

    assert 'recent_event' in tracker2.sent_events
    assert 'old_event' not in tracker2.sent_events


def test_tracker_keeps_all_events_with_no_reminder_frequency(temp_dir):
    """Test that all events are kept when reminder_frequency_days is None."""
    from src.core.tracking import EventTracker
    import zoneinfo

    tracking_file = temp_dir / 'tracking.json'
    tz = zoneinfo.ZoneInfo('Europe/Athens')

    # Create tracker with no reminder frequency
    tracker = EventTracker(
        tracking_file=tracking_file,
        reminder_frequency_days=None,
        schedule_times_timezone='Europe/Athens'
    )


    # Add very old event (100 days ago) - with timezone
    old_time = datetime.now(tz=tz) - timedelta(days=100)
    tracker.sent_events['very_old_event'] = old_time.isoformat()
    tracker._save()

    # Reload (should keep old event)
    tracker2 = EventTracker(
        tracking_file=tracking_file,
        reminder_frequency_days=None,
        schedule_times_timezone='Europe/Athens'
    )


    assert 'very_old_event' in tracker2.sent_events
