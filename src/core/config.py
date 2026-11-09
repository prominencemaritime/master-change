#src/core/config.py
"""
Centralized configuration management for alert system.

Loads configuration from environment variables and provides
validated access to all settings needed by alerts.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union
from pathlib import Path
from decouple import config
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)


@dataclass
class AlertConfig:
    """
    Configuration container for alert system.
    
    All alerts share this common configuration, with the ability
    to override specific settings per alert type if needed.
    """
    
    # Project structure
    project_root: Path
    queries_dir: Path
    logs_dir: Path
    data_dir: Path
    media_dir: Path
    
    # Database connection handled by db_utils
    # (no config needed here)
    
    # Email settings
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    
    # Company-specific email routing
    email_routing: Dict[str, Dict[str, List[str]]]  # domain -> {to: [...], cc: [...]}
    internal_recipients: List[str]
    
    # Feature flags
    enable_email_alerts: bool
    enable_teams_alerts: bool
    enable_special_teams_email: bool
    special_teams_email: str

    # Logos
    company_logos: Dict[str, Path]  # company_name -> logo_path

    # Scheduling
    schedule_frequency_hours: float
    schedule_times: Optional[List[str]] # Daily run times in HH:MM format
    schedule_times_timezone: str
    timezone: str

    # Alert-specific configurations
    lookback_days: int
    rank_id: str

    # Tracking
    reminder_frequency_days: Union[float, None]
    sent_events_file: Path

    # Logging
    log_file: Path
    log_max_bytes: int
    log_backup_count: int

    # URLs
    base_url: str
    enable_links: bool
    url_path: str

    # Runtime objects (injected after initialization)
    tracker: Optional['EventTracker'] = None
    email_sender: Optional['EmailSender'] = None
    html_formatter: Optional['HTMLFormatter'] = None
    text_formatter: Optional['TextFormatter'] = None
    dry_run: bool = False
    dry_run_email: str = ''  # Redirect all emails here in dry-run mode

    @classmethod
    def from_env(cls, project_root: Optional[Path] = None) -> 'AlertConfig':
        """
        Load configuration from environment variables.

        Args:
            project_root: Override project root path (default: auto-detect)

        Returns:
            AlertConfig instance with all settings loaded
        """
        # Determine project root
        if project_root is None:
            # Assume this file is in src/core/, so project root is 2 levels up
            project_root = Path(__file__).resolve().parent.parent.parent

        # Directory structure
        queries_dir = project_root / 'queries'
        logs_dir = project_root / 'logs'
        data_dir = project_root / 'data'
        media_dir = project_root / 'media'

        # Ensure directories exist
        logs_dir.mkdir(exist_ok=True)
        data_dir.mkdir(exist_ok=True)

        # Load email routing configuration
        email_routing = cls._load_email_routing()

        # Load company logos
        company_logos = {
            'prominence': media_dir / config('PROMINENCE_LOGO', default='trans_logo_prominence_procreate_small.png'),
            'seatraders': media_dir / config('SEATRADERS_LOGO', default='trans_logo_seatraders_procreate_small.png'),
        }

        return cls(
            project_root=project_root,
            queries_dir=queries_dir,
            logs_dir=logs_dir,
            data_dir=data_dir,
            media_dir=media_dir,

            # Email settings
            smtp_host=config('SMTP_HOST'),
            smtp_port=int(config('SMTP_PORT', default=465)),
            smtp_user=config('SMTP_USER'),
            smtp_pass=config('SMTP_PASS'),

            email_routing=email_routing,
            internal_recipients=cls._parse_email_list('INTERNAL_RECIPIENTS'),

            # Feature flags
            enable_email_alerts=config('ENABLE_EMAIL_ALERTS', default=True, cast=bool),
            enable_teams_alerts=config('ENABLE_TEAMS_ALERTS', default=False, cast=bool),
            enable_special_teams_email=config('ENABLE_SPECIAL_TEAMS_EMAIL_ALERT', default=False, cast=bool),
            special_teams_email=config('SPECIAL_TEAMS_EMAIL', default='').strip(),

            company_logos=company_logos,

            # Scheduling
            schedule_frequency_hours=cls._parse_frequency_hours(),
            schedule_times=cls._parse_schedule_times(),
            schedule_times_timezone=config('SCHEDULE_TIMES_TIMEZONE', default='Europe/Athens'),
            timezone=config('TIMEZONE', default='UTC'),

            # Tracking - if None or empty, never resend (track "forever")
            reminder_frequency_days=config('REMINDER_FREQUENCY_DAYS', default=None, cast=lambda x: float(x) if x and x.strip() else None),
            sent_events_file=data_dir / config('SENT_EVENTS_FILE', default='sent_alerts.json'),

            # Logging
            log_file=logs_dir / config('LOG_FILE', default='alerts.log'),
            log_max_bytes=int(config('LOG_MAX_BYTES', default=10_485_760)),
            log_backup_count=int(config('LOG_BACKUP_COUNT', default=5)),

            # URLs
            base_url=config('BASE_URL', default='https://prominence.orca.tools/'),

            # Documents links config
            enable_links=config('ENABLE_LINKS', default='False', cast=bool),
            url_path=config('URL_PATH', default='/events'),

            # Alert-specific configurations
            lookback_days=int(config('LOOKBACK_DAYS', default=1)),
            rank_id=str(config('RANK_ID', default='1')),

            # Dry-run settings (don't set dry_run here, it's set by CLI flag in main.py)
            dry_run_email=config('DRY_RUN_EMAIL', default='').strip(),
        )

    @staticmethod
    def _parse_email_list(env_var: str) -> List[str]:
        """Parse comma-separated email list from environment variable."""
        return [s.strip() for s in config(env_var, default='').split(',') if s.strip()]

    @staticmethod
    def _load_email_routing() -> Dict[str, Dict[str, List[str]]]:
        """
        Load company-specific email routing configuration.

        Returns dict mapping domain suffix to recipient configuration:
        {
            'prominencemaritime.com': {
                'cc': ['user1@prominencemaritime.com', ...]
            },
            'seatraders.com': {
                'cc': ['user1@seatraders.com', ...]
            }
        }
        """
        return {
            'prominencemaritime.com': {
                'cc': AlertConfig._parse_email_list('PROMINENCE_EMAIL_CC_RECIPIENTS')
            },
            'seatraders.com': {
                'cc': AlertConfig._parse_email_list('SEATRADERS_EMAIL_CC_RECIPIENTS')
            }
        }

    @staticmethod
    def _parse_schedule_times() -> Optional[List[str]]:
        """
        Parse comma-separated schedule times (in 24-hour format) from environment variable.

        Returns:
            List of times in HH:MM format, or None if not configured
        """
        times_str = config('SCHEDULE_TIMES', default='').strip()
        if not times_str:
            return None

        times = [t.strip() for t in times_str.split(',') if t.strip()]

        # Validate format
        for time_str in times:
            if not time_str or ':' not in time_str:
                raise ValueError(f"Invalid time format: '{time_str}'. Expected HH:MM")

            parts = time_str.split(':')
            if len(parts) != 2:
                raise ValueError(f"Invalid time format: '{time_str}'. Expected HH:MM")

            try:
                hour, minute = int(parts[0]), int(parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError(f"Invalid time: '{time_str}'. Hour must be 0-23, minute must be 0-59")
            except ValueError as e:
                raise ValueError(f"Invalid time format: '{time_str}'. {str(e)}")

        return times


    @staticmethod
    def _parse_frequency_hours() -> float:
        """
        Parse frequency hours from environment, handling empty strings.

        Returns:
            Frequency in hours, or 1.0 as default
        """
        freq_str = config('SCHEDULE_FREQUENCY_HOURS', default='').strip()

        if not freq_str:
            # Empty string - default to 1 hour (will be ignored if SCHEDULE_TIMES is set)
            return 1.0

        try:
            freq = float(freq_str)
            if freq <= 0:
                raise ValueError("SCHEDULE_FREQUENCY_HOURS must be positive")
            return freq
        except ValueError as e:
            raise ValueError(f"Invalid SCHEDULE_FREQUENCY_HOURS value '{freq_str}': {str(e)}")


    def validate(self) -> None:
        """
        Validate that all required configuration is present.

        Raises:
            ValueError: If required configuration is missing
        """
        required = {
            'SMTP_HOST': self.smtp_host,
            'SMTP_USER': self.smtp_user,
            'SMTP_PASS': self.smtp_pass,
        }

        missing = [key for key, value in required.items() if not value]

        if missing:
            raise ValueError(
                f"Required configuration missing from .env: {', '.join(missing)}"
            )

        # Validate scheduling configuration
        if not self.schedule_times and not self.schedule_frequency_hours:
            raise ValueError(
                "No scheduling configuration found. Please set either "
                "SCHEDULE_FREQUENCY_HOURS or SCHEDULE_TIMES in your .env file"
            )

        if self.schedule_times and self.schedule_frequency_hours != 1:
            logger.warning(
                "Both SCHEDULE_TIMES and SCHEDULE_FREQUENCY_HOURS are set. "
                "SCHEDULE_TIMES will take precedence."
            )

        logger.info("[OK] Configuration validation passed")
