#src/main.py
"""
Main entry point for the modular alert system.

This replaces the old alerts.py with a flexible, modular architecture
that supports multiple alert types.

Usage:
    python -m src.main                    # Run continuously with scheduling
    python -m src.main --run-once         # Run once and exit
    python -m src.main --dry-run          # Test mode (no emails sent)
"""
import sys
import logging
from logging.handlers import RotatingFileHandler
import argparse
from pathlib import Path

# Import core components
from src.core.config import AlertConfig
from src.core.scheduler import AlertScheduler
from src.core.tracking import EventTracker

# Import notification handlers
from src.notifications.email_sender import EmailSender
from src.notifications.teams_sender import TeamsSender

# Import formatters
from src.formatters.html_formatter import HTMLFormatter
from src.formatters.text_formatter import TextFormatter

# Import alert implementations
from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert


def setup_logging(config: AlertConfig) -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        config: AlertConfig instance
        
    Returns:
        Configured root logger
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        config.log_file,
        maxBytes=config.log_max_bytes,
        backupCount=config.log_backup_count
    )
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler for real-time monitoring
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger


def initialize_components(config: AlertConfig) -> AlertConfig:
    """Initialize and inject runtime components into config."""
    
    logger = logging.getLogger(__name__)
    
    # Initialize event tracker
    config.tracker = EventTracker(
        tracking_file=config.sent_events_file,
        reminder_frequency_days=config.reminder_frequency_days,
        schedule_times_timezone=config.schedule_times_timezone
    )
    logger.info(f"[OK] Event tracker initialised")
    
    # Initialize email sender
    # Determine if EmailSender should block sends
    if config.dry_run and not config.dry_run_email:
        # Dry-run without email redirection: block all sends
        block_emails = True
        log_msg = "[OK] Email sender initialised (DRY-RUN MODE - will not send emails)"
    elif config.dry_run and config.dry_run_email:
        # Dry-run with email redirection: allow sends (to test address)
        block_emails = False
        log_msg = f"[OK] Email sender initialised (DRY-RUN MODE - emails redirected to {config.dry_run_email})"
    else:
        # Production mode: allow sends
        block_emails = False
        log_msg = "[OK] Email sender initialised"
    
    config.email_sender = EmailSender(
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port,
        smtp_user=config.smtp_user,
        smtp_pass=config.smtp_pass,
        company_logos=config.company_logos,
        dry_run=block_emails
    )
    
    logger.info(log_msg)
    
    # Initialize formatters
    config.html_formatter = HTMLFormatter()
    config.text_formatter = TextFormatter()
    logger.info(f"[OK] Formatters initialized")
    
    return config


def register_alerts(scheduler: AlertScheduler, config: AlertConfig) -> None:
    """
    Register all alert implementations with the scheduler.
    
    To add a new alert type:
    1. Create a new class inheriting from BaseAlert
    2. Import it at the top of this file
    3. Instantiate and register it here
    
    Args:
        scheduler: AlertScheduler instance
        config: AlertConfig instance
    """
    logger = logging.getLogger(__name__)
    
    # Register Flag Dispensations Alert
    masters_navigation_audit_alert = MastersNavigationAuditAlert(config)
    scheduler.register_alert(masters_navigation_audit_alert.run)
    logger.info("[OK] Registered MastersNavigationAuditAlert")
    
    # Future alerts can be registered here:
    # hot_works_alert = HotWorksAlert(config)
    # scheduler.register_alert(hot_works_alert.run)
    # logger.info("[OK] Registered HotWorksAlert")


def main():
    """Main execution function."""
    from decouple import config as env_config

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Modular Alert System')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without sending notifications (test mode) - overrides DRY_RUN env var'
    )
    parser.add_argument(
        '--run-once',
        action='store_true',
        help='Run once and exit (no scheduling) - overrides RUN_ONCE env var'
    )
    args = parser.parse_args()

    # Load runtime modes from .env (can be overridden by CLI flags)
    dry_run_from_env = env_config('DRY_RUN', default=True, cast=bool)
    run_once_from_env = env_config('RUN_ONCE', default=False, cast=bool)

    # CLI flags override .env values
    dry_run_mode = args.dry_run or dry_run_from_env
    run_once_mode = args.run_once or run_once_from_env
    
    try:
        # Load configuration from environment
        config = AlertConfig.from_env()
        
        # Setup logging
        logger = setup_logging(config)
        logger.info("=" * 70)
        logger.info("▶ ALERT SYSTEM STARTING")
        logger.info("=" * 70)
        
        # Validate configuration
        config.validate()
        
        # Handle dry-run mode
        if dry_run_mode:
            config.dry_run = True

            if config.dry_run_email:
                # Dry-run with email redirection
                logger.info("=" * 70)
                logger.info(f"📧 DRY RUN MODE - EMAILS REDIRECTED TO: {config.dry_run_email}")
                logger.info("=" * 70)
                # Keep email alerts enabled but redirect recipients
                config.enable_teams_alerts = False
                config.enable_special_teams_email = False
            else:
                # Dry-run without emails (original behavior)
                logger.info("=" * 70)
                logger.info("🔒 DRY RUN MODE ACTIVATED - NO NOTIFICATIONS WILL BE SENT")
                logger.info("=" * 70)
                config.enable_email_alerts = False
                config.enable_teams_alerts = False
                config.enable_special_teams_email = False
        
        # Initialize components
        config = initialize_components(config)
        
        # Create scheduler
        scheduler = AlertScheduler(
            frequency_hours=config.schedule_frequency_hours,
            timezone=config.timezone,
            schedule_times_timezone=config.schedule_times_timezone,
            schedule_times=config.schedule_times
        )
        
        # Register all alerts
        register_alerts(scheduler, config)
        
        # Run based on mode
        if run_once_mode:
            scheduler.run_once()
        else:
            # Choose scheduling mode based on configuration
            if config.schedule_times:
                logger.info("Using time-based scheduling")
                scheduler.run_at_times()
            else:
                logger.info("Using interval-based scheduling")
                scheduler.run_continuous()
    
    except KeyboardInterrupt:
        logger = logging.getLogger(__name__)
        logger.info("Interrupted by user. Shutting down...")
        sys.exit(0)
    
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Fatal error in main(): {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
