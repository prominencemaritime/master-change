#src/formatters/text_formatter.py
"""
Plain text email formatter.

Generates simple, readable plain text emails as fallback
for HTML emails or for email clients that don't support HTML.
"""
from typing import Dict, Optional
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


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
            text += f"Found {len(df)} record(s):\n\n"

            # Determine which columns to display
            display_columns = metadata.get('display_columns', list(df.columns))
            # Filter to only columns that exist in the dataframe
            display_columns = [col for col in display_columns if col in df.columns]

            # Add each record
            for idx, row in df.iterrows():
                text += f"Record {idx + 1}:\n"
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
