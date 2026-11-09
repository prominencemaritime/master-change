#src/core/tracking.py
"""
Event tracking system for preventing duplicate notifications.

Tracks which events have been sent and when, with automatic cleanup
of old entries based on reminder frequency.
"""
import json
import tempfile
import shutil
import os
from pathlib import Path
from typing import Dict, Set, Callable, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class EventTracker:
    """
    Manages tracking of sent events to prevent duplicate notifications.

    Events are tracked by unique keys (defined by each alert type) with
    timestamps. Old events are automatically cleaned up based on the
    reminder frequency setting.
    """

    def __init__(self, tracking_file: Path, reminder_frequency_days: Optional[float], schedule_times_timezone: str):
        """
        Initialize event tracker.

        Args:
            tracking_file: Path to JSON file for persistent storage
            reminder_frequency_days: Days after which to allow re-sending (None = never resend)
            schedule_times_timezone: Timezone for timestamps
        """
        self.tracking_file = tracking_file
        self.reminder_frequency_days = reminder_frequency_days
        self.schedule_times_timezone = ZoneInfo(schedule_times_timezone)
        self.sent_events: Dict[str, str] = {}  # key -> timestamp

        # Load existing tracking data
        self._load()


    def _load(self) -> None:
        """
        Load sent events from JSON file with automatic cleanup of old entries.
        """
        if not self.tracking_file.exists():
            logger.info(f"Tracking file not found at {self.tracking_file}. Starting fresh.")
            self.sent_events = {}
            return
        
        try:
            with open(self.tracking_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both old format (list) and new format (dict with timestamps)
            sent_events_data = data.get('sent_events', {})
            
            # Backward compatibility: convert old list format
            if not sent_events_data and 'sent_event_ids' in data:
                logger.info("Converting old tracking format to new format")
                current_time = datetime.now(tz=self.schedule_times_timezone).isoformat()
                sent_events_data = {
                    str(event_id): current_time
                    for event_id in data['sent_event_ids']
                }
            
            logger.info(f"Loaded {len(sent_events_data)} tracked event(s) from {self.tracking_file}")
            
            # Filter out events older than reminder frequency (if reminder frequency is set)
            if self.reminder_frequency_days is not None:
                # Reminder mode: clean up old events
                cutoff_date = datetime.now(tz=self.schedule_times_timezone) - timedelta(days=self.reminder_frequency_days)
                filtered_events = {}
                removed_count = 0
                
                for event_key, timestamp_str in sent_events_data.items():
                    try:
                        event_timestamp = datetime.fromisoformat(timestamp_str)
                        
                        if event_timestamp >= cutoff_date:
                            filtered_events[event_key] = timestamp_str
                        else:
                            removed_count += 1
                            logger.debug(
                                f"Removing event key '{event_key}' "
                                f"(sent at {timestamp_str}, older than {self.reminder_frequency_days} days)"
                            )
                    
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid timestamp for event key '{event_key}': {timestamp_str}. Removing.")
                        removed_count += 1
                
                if removed_count > 0:
                    logger.info(
                        f"Cleaned up {removed_count} event(s) older than {self.reminder_frequency_days} days"
                    )
                    # Save cleaned data immediately
                    self.sent_events = filtered_events
                    self._save()
                else:
                    self.sent_events = filtered_events
                
                logger.info(
                    f"Tracking {len(self.sent_events)} recent event(s) "
                    f"(sent within last {self.reminder_frequency_days} days)"
                )
            
            else:
                # No reminder frequency: track forever (never remove old events)
                self.sent_events = sent_events_data
                logger.info(
                    f"Tracking {len(self.sent_events)} event(s) permanently "
                    f"(no reminder frequency set - events will never be resent)"
                )
        
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted JSON in {self.tracking_file}: {e}. Starting fresh.")
            self.sent_events = {}
        except Exception as e:
            logger.error(f"Error loading tracking data from {self.tracking_file}: {e}. Starting fresh.")
            self.sent_events = {}


    def _save(self) -> None:
        """
        Save sent events to JSON file using atomic write to prevent corruption.
        """
        try:
            data = {
                'sent_events': self.sent_events,
                'last_updated': datetime.now(tz=self.schedule_times_timezone).isoformat()
            }

            # Write to temporary file first
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.tracking_file.parent,
                suffix='.tmp',
                text=True
            )

            try:
                # Write JSON to temp file
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                # Atomically replace old file with new file
                shutil.move(temp_path, self.tracking_file)

                logger.info(f"Saved {len(self.sent_events)} tracked event(s) to {self.tracking_file}")

            except Exception:
                # Clean up temp file if something went wrong
                if Path(temp_path).exists():
                    Path(temp_path).unlink()
                raise

        except Exception as e:
            logger.error(f"Failed to save tracking data to {self.tracking_file}: {e}")
            raise

    def filter_unsent_events(
        self,
        df: pd.DataFrame,
        key_func: Callable[[pd.Series], str]
    ) -> pd.DataFrame:
        """
        Filter DataFrame to only include events that haven't been sent.

        Args:
            df: DataFrame to filter
            key_func: Function that generates tracking key from a DataFrame row

        Returns:
            Filtered DataFrame with only unsent events
        """
        if df.empty:
            return df

        # Generate tracking keys for all rows
        tracking_keys = df.apply(key_func, axis=1)

        # Filter out already-sent events
        unsent_mask = ~tracking_keys.isin(self.sent_events.keys())
        unsent_df = df[unsent_mask].copy()

        filtered_count = len(df) - len(unsent_df)
        if filtered_count > 0:
            logger.info(
                f"Filtered out {filtered_count} previously sent event(s). "
                f"{len(unsent_df)} new event(s) remain."
            )

        return unsent_df

    def mark_as_sent(self, event_keys: Set[str], timestamp: datetime) -> None:
        """
        Mark events as sent and persist to disk.

        Args:
            event_keys: Set of unique event keys to mark as sent
            timestamp: When these events were sent
        """
        timestamp_str = timestamp.isoformat()

        for key in event_keys:
            self.sent_events[key] = timestamp_str

        logger.info(f"Marking {len(event_keys)} event(s) as sent at {timestamp_str}")
        self._save()

    def is_sent(self, event_key: str) -> bool:
        """
        Check if an event has been sent.

        Args:
            event_key: Unique tracking key for the event

        Returns:
            True if event was sent within reminder frequency window
        """
        return event_key in self.sent_events

    def get_sent_timestamp(self, event_key: str) -> Optional[datetime]:
        """
        Get the timestamp when an event was sent.

        Args:
            event_key: Unique tracking key for the event

        Returns:
            Datetime when event was sent, or None if not sent
        """
        timestamp_str = self.sent_events.get(event_key)
        if timestamp_str:
            try:
                return datetime.fromisoformat(timestamp_str)
            except ValueError:
                return None
        return None

    def clear(self) -> None:
        """Clear all tracking data (useful for testing)."""
        self.sent_events = {}
        self._save()
        logger.info("Cleared all tracking data")
