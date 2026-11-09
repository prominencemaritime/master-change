#!/usr/bin/env python3
"""
Healthcheck script for Docker containers with flexible scheduling.
Supports both SCHEDULE_FREQUENCY_HOURS and SCHEDULE_TIMES modes.

This script checks if /app/logs/health_status.txt exists, contains "OK",
and has been updated recently enough based on the schedule configuration.

Environment Variables:
    SCHEDULE_FREQUENCY_HOURS: Run every N hours (e.g., "2" for every 2 hours)
    SCHEDULE_TIMES: Run at specific times (e.g., "12:00,18:00")
    
At least one must be set. If both are set, SCHEDULE_FREQUENCY_HOURS takes precedence.

Exit Codes:
    0: Healthy
    1: Unhealthy
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def main():
    """
    Main healthcheck logic.

    Validates the health_status.txt file by checking:
    1. File exists
    2. File contains valid structured data
    3. Status is OK or ERROR is recent
    4. Timestamp is recent enough based on schedule

    Exit codes:
        0: Healthy
        1: Unhealthy
    """
    health_file = Path("/app/logs/health_status.txt")

    # Validate file structure first
    try:
        validate_health_file_structure(health_file)
    except Exception as e:
        print(f"Health file validation failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Read and parse health status
    try:
        health_data = parse_health_file(health_file)
    except Exception as e:
        print(f"Cannot parse health status: {e}", file=sys.stderr)
        sys.exit(1)

    # Get the timezone to use for time calculations
    tz_name = get_effective_timezone()

    # Calculate maximum age based on schedule mode
    max_age_minutes = calculate_max_age()

    # Calculate file age using the parsed timestamp (timezone-aware)
    try:
        now = datetime.now(tz=ZoneInfo(tz_name))
        file_age_seconds = (now - health_data['timestamp']).total_seconds()
        file_age_minutes = file_age_seconds / 60
    except Exception as e:
        print(f"Cannot calculate file age: {e}", file=sys.stderr)
        sys.exit(1)

    # Check status and age
    if health_data['status'] == "ERROR":
        # For ERROR status, check if it's a recent error
        if file_age_minutes > max_age_minutes:
            print(
                f"Health status is ERROR and stale: {file_age_minutes:.1f} minutes old "
                f"(max: {max_age_minutes:.1f} minutes). "
                f"Error: {health_data.get('error_msg', 'No error message')}",
                file=sys.stderr
            )
            sys.exit(1)
        else:
            # Recent error - still fail but with different message
            print(
                f"Health status is ERROR (recent): {health_data.get('error_msg', 'No error message')}",
                file=sys.stderr
            )
            sys.exit(1)

    elif health_data['status'] == "OK":
        # Check if OK status is recent enough
        if file_age_minutes > max_age_minutes:
            print(
                f"Health status file is too old: {file_age_minutes:.1f} minutes "
                f"(max: {max_age_minutes:.1f} minutes)",
                file=sys.stderr
            )
            sys.exit(1)

    else:
        print(f"Unknown health status: {health_data['status']}", file=sys.stderr)
        sys.exit(1)

    # All checks passed
    print(
        f"Healthy (status: {health_data['status']}, "
        f"alert: {health_data.get('alert_type', 'unknown')}, "
        f"age: {file_age_minutes:.1f}/{max_age_minutes:.1f} minutes)"
    )
    sys.exit(0)


def parse_health_file(health_file: Path) -> dict:
    """
    Parse the structured health status file.

    Expected format:
        Line 1: STATUS YYYY-MM-DDTHH:MM:SS.ffffff+HH:MM
        Line 2: ALERT_TYPE: ClassName
        Line 3: TIMEZONE: timezone_name
        Line 4: ERROR_MSG: message (optional, only if ERROR)

    Args:
        health_file: Path to health_status.txt

    Returns:
        Dictionary with parsed health data:
            - status: "OK" or "ERROR"
            - timestamp: timezone-aware datetime object
            - alert_type: Alert class name
            - timezone: Timezone name from file
            - error_msg: Error message (only if status is ERROR)

    Raises:
        ValueError: If file format is invalid
        Exception: If file cannot be read or parsed
    """
    content = health_file.read_text().strip()
    lines = content.split('\n')

    if len(lines) < 3:
        raise ValueError(f"Health file has insufficient lines: {len(lines)} (expected at least 3)")

    # Parse line 1: STATUS TIMESTAMP
    status_line = lines[0].strip()
    parts = status_line.split(' ', 1)

    if len(parts) != 2:
        raise ValueError(f"Invalid status line format: '{status_line}'")

    status = parts[0]
    timestamp_str = parts[1]

    if status not in ["OK", "ERROR"]:
        raise ValueError(f"Invalid status: '{status}' (expected OK or ERROR)")

    # Parse timestamp (ISO format with timezone)
    try:
        timestamp = datetime.fromisoformat(timestamp_str)
    except ValueError as e:
        raise ValueError(f"Invalid timestamp format: '{timestamp_str}': {e}")

    # Ensure timestamp is timezone-aware
    if timestamp.tzinfo is None:
        raise ValueError(f"Timestamp is not timezone-aware: '{timestamp_str}'")

    # Parse line 2: ALERT_TYPE
    if not lines[1].startswith("ALERT_TYPE: "):
        raise ValueError(f"Invalid ALERT_TYPE line: '{lines[1]}'")
    alert_type = lines[1].replace("ALERT_TYPE: ", "").strip()

    # Parse line 3: TIMEZONE
    if not lines[2].startswith("TIMEZONE: "):
        raise ValueError(f"Invalid TIMEZONE line: '{lines[2]}'")
    timezone = lines[2].replace("TIMEZONE: ", "").strip()

    result = {
        'status': status,
        'timestamp': timestamp,
        'alert_type': alert_type,
        'timezone': timezone
    }

    # Parse line 4 (optional): ERROR_MSG
    if len(lines) >= 4 and lines[3].startswith("ERROR_MSG: "):
        error_msg = lines[3].replace("ERROR_MSG: ", "").strip()
        result['error_msg'] = error_msg

    return result


def get_effective_timezone() -> str:
    """
    Determine which timezone to use for time calculations.
    
    Precedence:
        1. SCHEDULE_TIMES_TIMEZONE (if set)
        2. TIMEZONE (if set)
        3. UTC (default fallback)
    
    Returns:
        Timezone name (e.g., "Europe/Athens", "UTC")
    """
    schedule_tz = os.getenv('SCHEDULE_TIMES_TIMEZONE', '').strip()
    if schedule_tz:
        return schedule_tz
    
    general_tz = os.getenv('TIMEZONE', '').strip()
    if general_tz:
        return general_tz
    
    return 'UTC'


def validate_health_file_structure(health_file: Path) -> None:
    """
    Perform initial validation of health file structure before parsing.

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is empty or has invalid structure
    """
    if not health_file.exists():
        raise FileNotFoundError(f"Health file not found: {health_file}")

    stat = health_file.stat()
    if stat.st_size == 0:
        raise ValueError("Health file is empty")

    if stat.st_size > 10000:  # 10KB limit
        raise ValueError(f"Health file is too large: {stat.st_size} bytes (max 10KB)")


def calculate_max_age() -> float:
    """
    Calculate maximum allowed age for health_status.txt based on schedule mode.
    
    Returns:
        Maximum age in minutes
    """
    freq_hours = os.getenv('SCHEDULE_FREQUENCY_HOURS', '').strip()
    schedule_times = os.getenv('SCHEDULE_TIMES', '').strip()
    
    # Mode 1: Frequency-based (e.g., every 2 hours)
    if freq_hours:
        try:
            hours = float(freq_hours)
            # Allow schedule interval + 10 minute buffer
            return hours * 60 + 10
        except (ValueError, TypeError):
            print(f"Invalid SCHEDULE_FREQUENCY_HOURS: {freq_hours}", file=sys.stderr)
            return 70  # Default fallback: 1 hour + 10 min buffer
    
    # Mode 2: Specific times (e.g., 12:00,18:00)
    elif schedule_times:
        try:
            return calculate_max_age_from_times(schedule_times)
        except Exception as e:
            print(f"Error calculating age from SCHEDULE_TIMES: {e}", file=sys.stderr)
            return 70  # Default fallback
    
    # Mode 3: No schedule defined (default to hourly + buffer)
    else:
        print("Warning: Neither SCHEDULE_FREQUENCY_HOURS nor SCHEDULE_TIMES set", file=sys.stderr)
        return 70  # 1 hour + 10 minute buffer


def calculate_max_age_from_times(schedule_times: str) -> float:
    """
    Calculate maximum age based on SCHEDULE_TIMES.

    For times like "12:00,18:00", the health file should be updated within
    10 minutes after the most recent scheduled time.

    Uses the effective timezone (SCHEDULE_TIMES_TIMEZONE or TIMEZONE) for
    determining "now" and calculating schedule times.

    Args:
        schedule_times: Comma-separated list of times (HH:MM format)

    Returns:
        Maximum age in minutes (time since most recent scheduled time + 10 min buffer)

    Note:
        This function uses timezone-aware datetime calculations to ensure
        correct behavior across different timezones.
    """
    # Get timezone-aware "now"
    tz_name = get_effective_timezone()
    try:
        now = datetime.now(tz=ZoneInfo(tz_name))
    except Exception as e:
        print(f"Invalid timezone '{tz_name}': {e}, falling back to UTC", file=sys.stderr)
        now = datetime.now(tz=ZoneInfo('UTC'))

    # Parse all scheduled times
    time_list = [t.strip() for t in schedule_times.split(',')]
    scheduled_datetimes = []

    for time_str in time_list:
        try:
            hour, minute = map(int, time_str.split(':'))

            # Create timezone-aware datetime for today
            scheduled_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            scheduled_datetimes.append(scheduled_today)

            # Also consider yesterday's schedule
            scheduled_yesterday = scheduled_today - timedelta(days=1)
            scheduled_datetimes.append(scheduled_yesterday)

        except (ValueError, IndexError) as e:
            print(f"Invalid time format '{time_str}': {e}", file=sys.stderr)
            continue

    if not scheduled_datetimes:
        print("No valid times found in SCHEDULE_TIMES", file=sys.stderr)
        return 70

    # Find the most recent scheduled time that has passed
    past_times = [dt for dt in scheduled_datetimes if dt <= now]

    if not past_times:
        # No scheduled time has passed yet today - use most recent from yesterday
        past_times = sorted(scheduled_datetimes)

    most_recent = max(past_times)

    # Calculate minutes since most recent scheduled time
    minutes_since = (now - most_recent).total_seconds() / 60

    # Allow the time since last schedule + 10 minute buffer
    return minutes_since + 10


if __name__ == "__main__":
    main()
