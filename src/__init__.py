#src/__init__.py
"""
Modular Alert System Package.

This package provides a flexible, reusable framework for implementing
various types of alerts that query databases and send notifications.
"""
from src.core.base_alert import BaseAlert
from src.core.config import AlertConfig
from src.core.tracking import EventTracker
from src.core.scheduler import AlertScheduler

__version__ = '2.0.0'
__all__ = [
    'BaseAlert',
    'AlertConfig',
    'EventTracker',
    'AlertScheduler',
]
