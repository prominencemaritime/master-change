#src/date_formatter.py
from datetime import datetime
import pandas as pd


def duration_hours(hours: float) -> str:
    td = pd.Timedelta(hours=hours).components

    parts = []
    if td.days:
        parts.append(f"{td.days}d")
    if td.hours:
        parts.append(f"{td.hours}h")
    if td.minutes:
        parts.append(f"{td.minutes}m")
    if td.seconds:
        parts.append(f"{td.seconds}s")

    return " ".join(parts)
