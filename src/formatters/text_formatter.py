#src/formatters/text_formatter.py
"""
Plain text email formatter.

Generates simple, readable plain text emails as fallback
for HTML emails or for email clients that don't support HTML.
"""
from typing import Dict, Optional
from html import unescape
import re
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

_LINK_RE = re.compile(r'<a\s[^>]*?href="([^"]*)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r'<[^>]+>')


def _html_to_text(fragment: str) -> str:
    """
    Plain-text version of an HTML fragment: links become 'text (url)',
    other tags are removed and character entities decoded.
    """
    def plain(part: str) -> str:
        return unescape(_TAG_RE.sub('', part))

    parts, pos = [], 0
    for match in _LINK_RE.finditer(fragment):
        parts.append(plain(fragment[pos:match.start()]))
        parts.append(f"{plain(match.group(2))} ({unescape(match.group(1))})")
        pos = match.end()
    parts.append(plain(fragment[pos:]))
    return ''.join(parts)

class TextFormatter:
    """
    Generates plain text email content.
    """
    
    def format(
        self,
        df: pd.DataFrame,
        run_time: datetime,
        config: 'AlertConfig',
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Generate plain text email content from DataFrame.
        
        Args:
            df: DataFrame with data to display
            run_time: Timestamp of this alert run
            config: AlertConfig instance for accessing settings
            metadata: Optional metadata (e.g., vessel_name, alert_title)
            
        Returns:
            Plain text string for email body
        """
        if metadata is None:
            metadata = {}
        
        # Extract metadata with defaults
        alert_title = metadata.get('alert_title', 'Alert Notification')
        vessel_name = metadata.get('vessel_name', '')
        company_name = metadata.get('company_name', 'Company')
        
        # Build header
        separator = "=" * 70
        text = f"{separator}\n"
        text += f"{alert_title}\n"
        if vessel_name:
            text += f"{vessel_name}\n"
        text += f"{run_time.strftime('%A, %B %d, %Y at %H:%M %Z')}\n"
        text += f"{separator}\n\n"
        
        if df.empty:
            text += "No records found for the current query.\n"
        else:
            # Alert-specific intro paragraphs (optional)
            for paragraph in metadata.get('intro_paragraphs') or []:
                # HTML paragraphs (markupsafe.Markup) are converted; plain strings are used as they are
                if hasattr(paragraph, '__html__'):
                    paragraph = _html_to_text(paragraph.__html__())
                text += f"{paragraph}\n\n"
                text += f"Found {len(df)} record(s):\n\n"

            # Determine which columns to display
            display_columns = metadata.get('display_columns', list(df.columns))
            # Filter to only columns that exist in the dataframe
            display_columns = [col for col in display_columns if col in df.columns]

            # Add each record
            for record_num, (_, row) in enumerate(df.iterrows(), start=1):
                text += f"Record {record_num}:\n"
                text += "-" * 70 + "\n"

                for col in display_columns:
                    value = row[col]
                    # Format None/NaN as empty string
                    if pd.isna(value):
                        display_value = "(empty)"
                    else:
                        display_value = str(value)

                    # Format column name
                    col_display = col.replace('_', ' ').title()
                    text += f"  {col_display}: {display_value}\n"

                text += "\n"
        
        # Footer
        text += f"{separator}\n"
        text += f"This is an automated notification from {company_name}.\n"
        text += "If you have questions, please contact your system administrator.\n"
        text += f"{separator}\n"
        
        return text
