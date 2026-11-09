#src/core/scheduler.py
"""
Scheduling system for running alerts at regular intervals.

Handles graceful shutdown, error recovery, and interval-based execution.
"""
import signal
import threading
import logging
from datetime import datetime, timedelta, time
from src.formatters.date_formatter import duration_hours
from zoneinfo import ZoneInfo
from typing import Callable, List
import pandas as pd

logger = logging.getLogger(__name__)


class AlertScheduler:
    """
    Scheduler for running alerts at regular intervals.
    
    Supports graceful shutdown, multiple alerts, and error recovery.
    """
    
    def __init__(self, frequency_hours: float, timezone: str, schedule_times_timezone: str = 'Europe/Athens', schedule_times: List[str] = None):
        """
        Initialize scheduler.
        
        Args:
            frequency_hours: Hours between alert runs (ignored if schedule_times provided)
            timezone: Timezone for scheduling and logging
            schedule_times: Optional list of daily run times in HH:MM format
        """
        self.frequency_hours = frequency_hours
        self.schedule_times = schedule_times
        self.schedule_times_timezone = ZoneInfo(schedule_times_timezone)
        self.timezone = ZoneInfo(timezone)
        self.shutdown_event = threading.Event()
        self._alerts: List[Callable] = []
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
        self.shutdown_event.set()
    
    def register_alert(self, alert_runner: Callable) -> None:
        """
        Register an alert to be run on schedule.
        
        Args:
            alert_runner: Callable that executes the alert (typically alert.run())
        """
        self._alerts.append(alert_runner)
        logger.info(f"Registered alert: {alert_runner.__name__ if hasattr(alert_runner, '__name__') else 'anonymous'}")
    
    def _run_all_alerts(self) -> None:
        """Execute all registered alerts."""
        if not self._alerts:
            logger.warning("No alerts registered. Nothing to run.")
            return
        
        logger.info(f"Running {len(self._alerts)} alert(s)...")
        
        for idx, alert_runner in enumerate(self._alerts, 1):
            if self.shutdown_event.is_set():
                logger.info("Shutdown requested. Stopping alert execution.")
                break
            
            try:
                logger.info(f"Executing alert {idx}/{len(self._alerts)}...")
                alert_runner()
            except Exception as e:
                logger.exception(f"Error executing alert {idx}: {e}")
                # Continue with next alert despite error
    

    def _calculate_next_run_time(self, current_time: datetime) -> datetime:
        """
        Calculate the next scheduled run time based on schedule_times.

        Args:
            current_time: Current datetime with timezone

        Returns:
            Next scheduled datetime
        """
        if not self.schedule_times:
            raise ValueError("schedule_times must be set to calculate next run time")

        # Parse schedule times into time objects
        schedule_times_parsed = []
        for time_str in self.schedule_times:
            hour, minute = map(int, time_str.split(':'))
            schedule_times_parsed.append(time(hour, minute))

        # Sort times
        schedule_times_parsed.sort()

        # Find next run time today or tomorrow
        current_date = current_time.date()
        current_time_only = current_time.time()

        # Check if any scheduled time is still upcoming today
        for scheduled_time in schedule_times_parsed:
            if scheduled_time > current_time_only:
                next_run = datetime.combine(current_date, scheduled_time, tzinfo=self.schedule_times_timezone)
                return next_run

        # No more runs today, take first time tomorrow
        next_date = current_date + timedelta(days=1)
        next_run = datetime.combine(next_date, schedule_times_parsed[0], tzinfo=self.schedule_times_timezone)
        return next_run

    def run_once(self) -> None:
        """
        Run all alerts once and exit.
        
        Useful for manual execution or testing.
        """
        logger.info("=" * 60)
        logger.info("▶ RUN-ONCE MODE: Executing alerts once without scheduling")
        logger.info("=" * 60)
        
        self._run_all_alerts()
        
        logger.info("=" * 60)
        logger.info("◼ RUN-ONCE COMPLETE")
        logger.info("=" * 60)
    
    def run_continuous(self) -> None:
        """
        Run alerts continuously at scheduled intervals.
        
        Runs immediately on startup, then repeats every frequency_hours.
        Handles graceful shutdown and error recovery.
        """
        logger.info("=" * 60)
        logger.info(f"▶ SCHEDULER STARTED")
        logger.info(f"Frequency: Every {duration_hours(self.frequency_hours)}")
        logger.info(f"Scheduling Timezone: {self.schedule_times_timezone}")
        logger.info(f"Registered alerts: {len(self._alerts)}")
        logger.info("=" * 60)
        
        while not self.shutdown_event.is_set():
            try:
                # Run all alerts
                self._run_all_alerts()
                
                # Check if shutdown was requested during execution
                if self.shutdown_event.is_set():
                    break
                
                # Calculate next run time
                sleep_seconds = self.frequency_hours * 3600
                next_run = datetime.now(tz=self.schedule_times_timezone) + timedelta(hours=self.frequency_hours)
                
                logger.info(f"Sleeping for {duration_hours(self.frequency_hours)}")
                logger.info(f"Next run scheduled at: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                
                # Use shutdown_event.wait() for interruptible sleep
                if self.shutdown_event.wait(timeout=sleep_seconds):
                    logger.info("Shutdown requested during sleep period")
                    break
            
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received. Shutting down...")
                break
            
            except Exception as e:
                logger.exception(f"Unhandled exception in scheduler loop: {e}")
                # Wait before retrying to avoid rapid failure loops
                if not self.shutdown_event.is_set():
                    logger.info("Waiting 5 minutes before retry...")
                    if self.shutdown_event.wait(timeout=300):
                        logger.info("Shutdown requested during error recovery wait")
                        break
        
        logger.info("=" * 60)
        logger.info("⏹ SCHEDULER STOPPED")
        logger.info("=" * 60)


    def run_at_times(self) -> None:
        """
        Run alerts at specified times each day.
        
        Uses schedule_times (and schedule_times_timezone) to determine when to run alerts.
        Handles graceful shutdown and error recovery.
        """
        if not self.schedule_times:
            raise ValueError("schedule_times must be configured for time-based scheduling")

        if not self.schedule_times_timezone:
            raise ValueError("self.schedule_times_timezone must be configued for time-based scheduling")
        
        logger.info("=" * 60)
        logger.info(f"▶ TIME-BASED SCHEDULER STARTED")
        logger.info(f"Daily run times: {', '.join(self.schedule_times)}")
        logger.info(f"Timezone: {self.schedule_times_timezone}")
        logger.info(f"Registered alerts: {len(self._alerts)}")
        logger.info("=" * 60)
        
        while not self.shutdown_event.is_set():
            try:
                current_time = datetime.now(tz=self.schedule_times_timezone)
                next_run = self._calculate_next_run_time(current_time)
                
                # Calculate sleep duration
                sleep_seconds = (next_run - current_time).total_seconds()
                
                logger.info(f"Next run scheduled at: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                logger.info(f"Sleeping for {sleep_seconds / 3600:.2f} hours")
                
                # Wait until next scheduled time
                if self.shutdown_event.wait(timeout=sleep_seconds):
                    logger.info("Shutdown requested during sleep period")
                    break
                
                # Run all alerts at scheduled time
                self._run_all_alerts()
                
                # Check if shutdown was requested during execution
                if self.shutdown_event.is_set():
                    break
            
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received. Shutting down...")
                break
            
            except Exception as e:
                logger.exception(f"Unhandled exception in scheduler loop: {e}")
                # Wait before retrying to avoid rapid failure loops
                if not self.shutdown_event.is_set():
                    logger.info("Waiting 5 minutes before retry...")
                    if self.shutdown_event.wait(timeout=300):
                        logger.info("Shutdown requested during error recovery wait")
                        break
        
        logger.info("=" * 60)
        logger.info("⏹ TIME-BASED SCHEDULER STOPPED")
        logger.info("=" * 60)
