#src/formatters/html_formatter.py
"""
HTML email formatter with rich styling and company branding.

Generates professional HTML emails with embedded logos, tables,
and responsive design.
"""
from typing import Dict, Optional
import pandas as pd
from datetime import datetime
from src.formatters.date_formatter import duration_hours
import logging

logger = logging.getLogger(__name__)


class HTMLFormatter:
    """
    Generates HTML email content with company branding.
    """
    
    def _render_cell(self, column_name: str, value: any, row: pd.Series, enable_links: bool) -> str:
        """
        Render table cell with optional link for document_name column.

        Args:
            column_name: Name of the column being rendered
            value: Cell value to display
            row: Complete row data (for accessing document_url if needed)
            enable_links: Whether links are enabled

        Returns:
            HTML string for table cell content
        """
        # Convert value to string, handle None/NaN
        if pd.isna(value):
            display_value = ''
        else:
            display_value = str(value)

        # Make event_name clickable if links are enabled
        if column_name == 'title' and enable_links:
            # Check if url exists in row and has a value
            if 'url' in row.index and pd.notna(row['url']):
                url = row['url']
                return f'<a href="{url}" style="color: #0066cc; text-decoration: none;">{display_value}</a>'

        # Regular cell - no link
        return display_value


    def _extract_captain_surname(self, df: pd.DataFrame) -> str:
        """
        Extract captain's surname from the first row of the dataframe.
        
        Args:
            df: DataFrame containing surname column
            
        Returns:
            Captain's surname, or empty string if not found
        """
        if df.empty or 'surname' not in df.columns:
            return ''
        
        surname = df.iloc[0]['surname']
        
        # Handle None/NaN
        if pd.isna(surname):
            return ''
        
        return str(surname).strip().title()


    def format(self, df: pd.DataFrame, run_time: datetime, config: 'AlertConfig', metadata: Optional[Dict] = None, enable_links: bool = False) -> str:
        """
        Generate HTML email content from DataFrame.
        
        Args:
            df: DataFrame with data to display
            run_time: Timestamp of this alert run
            config: AlertConfig instance for accessing settings
            metadata: Optional metadata (e.g., vessel_name, alert_title)
            enable_links: Whether to make column names clickable
            
        Returns:
            HTML string for email body
        """
        if metadata is None:
            metadata = {}
        
        # Extract metadata with defaults
        alert_title = metadata.get('alert_title', 'Alert Notification')
        vessel_name = metadata.get('vessel_name', 'vessel')
        company_name = metadata.get('company_name', 'Prominence Maritime S.A.')
        
        # Determine which logos are available
        logos_html = self._build_logos_html(config)
        
        # Build the HTML
        # -apple-system, BlinkMacSystemFont
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    body {{
        font-family: Tahoma, Verdana, "Segoe UI", Roboto, Arial, sans-serif;
        font-size: 13px;
        background-color: #f9fafc;
        color: #333;
        line-height: 1.6;
        margin: 0;
        padding: 0;
    }}
    .container {{
        max-width: 1200px;
        width: 95%;
        margin: 30px auto;
        background: #ffffff;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        overflow: hidden;
    }}
    .table-wrapper {{
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        margin: 20px 0;
    }}
    .header {{
        background-color: #0B4877;
        color: white;
        padding: 20px 30px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
    }}
    .header-logos {{
        display: flex;
        align-items: center;
        gap: 15px;
    }}
    .header-logos img {{
        max-height: 50px;
        vertical-align: middle;
    }}
    .header-text {{
        text-align: right;
    }}
    .header h1 {{
        margin: 0;
        font-size: 24px;
        font-weight: 600;
    }}
    .header p {{
        margin: 5px 0 0 0;
        font-size: 14px;
        color: #d7e7f5;
    }}
    .content {{
        padding: 30px;
    }}
    .metadata {{
        background-color: #f5f8fb;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 25px;
        font-size: 14px;
        border-left: 4px solid #2EA9DE;
    }}
    .metadata-row {{
        margin: 8px 0;
    }}
    .metadata-label {{
        font-weight: 600;
        color: #0B4877;
        display: inline-block;
        min-width: 140px;
    }}
    .count-badge {{
        display: inline-block;
        background-color: #2EA9DE;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 14px;
        font-weight: 600;
    }}
    table {{
        width: 100%;
        min-width: 600px;
        border-collapse: collapse;
        margin: 20px 0;
        font-size: 13px;
        font-family: Tahoma, Verdana, "Segoe UI", Roboto, Arial, sans-serif;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    th {{
        background-color: #0B4877;
        color: white;
        text-align: left;
        padding: 12px;
        font-weight: 600;
        min-width: 80px;
        word-wrap: break-word;
    }}
    td {{
        padding: 10px 12px;
        border-bottom: 1px solid #e0e6ed;
        min-width: 80px;
        word-wrap: break-word;
    }}
    th:first-child, td:first-child {{
        min-width: 120px;
    }}
    tr:nth-child(even) {{
        background-color: #f5f8fb;
    }}
    tr:hover {{
        background-color: #eef5fc;
    }}
    a {{
        color: #2EA9DE;
        text-decoration: none;
    }}
    a:hover {{
        text-decoration: underline;
    }}
    .footer {{
        font-size: 12px;
        color: #888;
        text-align: center;
        padding: 20px;
        border-top: 1px solid #eee;
        background-color: #f9fafc;
    }}
    .no-data {{
        text-align: center;
        padding: 40px;
        color: #666;
        font-size: 16px;
    }}
    @media only screen and (max-width: 1200px) {{
        .container {{
            width: 98%;
            margin: 10px auto;
            border-radius: 8px;
        }}
        .header {{
            flex-direction: column;
            text-align: center;
            padding: 15px;
        }}
        .header-text {{
            text-align: center;
            margin-top: 15px;
        }}
        .content {{
            padding: 15px;
        }}
        body {{
            font-size: 13px
        }}
        table {{
            font-size: 13px;
            min-width: 500px;
        }}
        th, td {{
            padding: 8px;
            min-width: 60px;
            font-size: 13px;
        }}
    }}
    @media only screen and (max-width: 768px) {{
        .container {{
            width: 98%;
            margin: 10px auto;
            border-radius: 8px;
        }}
        .header {{
            flex-direction: column;
            text-align: center;
            padding: 15px;
        }}
        .header-text {{
            text-align: center;
            margin-top: 15px;
        }}
        .content {{
            padding: 15px;
        }}
        body {{
            font-size: 12px
        }}
        table {{
            font-size: 13px;
            min-width: 500px;
        }}
        th, td {{
            padding: 8px;
            min-width: 60px;
            font-size: 12px;
        }}
    }}
    @media only screen and (max-width: 480px) {{
        .container {{
            width: 100%;
            margin: 0;
            border-radius: 0;
        }}
        body {{
            font-size: 11px;
        }}
        table {{
            min-width: 400px;
        }}
        th, td {{
            padding: 6px;
            min-width: 50px;
            font-size: 11px;
        }}
    }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="header-logos">
            {logos_html}
        </div>
        <div class="header-text">
            <h1>{alert_title}</h1>
            {f'<p>{vessel_name}</p>' if vessel_name else ''}
            <p>{run_time.strftime('%A, %d %B %Y • %H:%M %Z')}</p>
        </div>
    </div>
    
    <div class="content">
"""

        if df.empty:
            html += """
        <div class="no-data">
            <p><strong>No records found for the current query.</strong></p>
        </div>
"""
        else:
            # Add metadata section
            #html += 

            f"""
        <div class="metadata">
            <div class="metadata-row">
                <span class="metadata-label">Report Generated:</span>
                {run_time.strftime('%A, %B %d, %Y at %H:%M %Z')}
            </div>
            <div class="metadata-row">
                <span class="metadata-label">Lookback:</span>
                {duration_hours(config.lookback_days * 24)} (to created at)
            </div>
            <div class="metadata-row">
                <span class="metadata-label">Schedule Frequency:</span>
                {duration_hours(config.schedule_frequency_hours)}
            </div>
            <div class="metadata-row">
                <span class="metadata-label">Records Found:</span>
                <span class="count-badge">{len(df)}</span>
            </div>
        </div>
"""

            # Add welcome message if captain surname is available
            captain_surname = self._extract_captain_surname(df)
            if captain_surname:
                html += f"""
        <div style="background-color: #fff; padding: 20px; border-left: 4px solid #2EA9DE; margin-bottom: 25px; line-height: 1.8;">
            <p style="margin: 0 0 10px 0;">Dear Captain {captain_surname},</p>
            <p style="margin: 10px 0;">Welcome onboard.</p> 
            <p style="margin: 10px 0;">The forms 'F.NAV.13 – Master's Navigation Audit' & 'F.MLC.1 - Master's MLC Inspection', along with the current Crew List, must be uploaded within 14 days of assuming command.</p>
            <p style="margin: 10px 0;">Please create <strong>two Events</strong> using the Templates 'Master's Navigation Audit' & 'Master's MLC Inspection'.</p>
        </div>
"""

            # Determine which columns to display

            display_columns = metadata.get('display_columns', list(df.columns))
            # Filter to only columns that exist in the dataframe
            display_columns = [col for col in display_columns if col in df.columns]

            # Build table
            html += """
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
"""
            # Add column headers (only for display columns)
            for col in display_columns:
                if col == 'dispensation_type':
                    col = 'type'
                display_name = col.replace('_', ' ').title()
                html += f"                        <th>{display_name}</th>\n"

            html += """                    </tr>
                </thead>
                <tbody>
"""

            # Add data rows (only display columns)
            for idx, row in df.iterrows():
                html += "                    <tr>\n"
                for col in display_columns:
                    # Use _render_cell to handle links
                    cell_content = self._render_cell(
                        column_name=col,
                        value=row[col],
                        row=row,
                        enable_links=enable_links
                    )
                    html += f"                        <td>{cell_content}</td>\n"
                html += "                    </tr>\n"

            html += """                </tbody>
            </table>
        </div>
"""

        # Footer
        html += f"""
    </div>
    
    <div class="footer">
        <p>This is an automated notification from {company_name}.</p>
        <p>If you have questions, please contact your system administrator.</p>
    </div>
</div>
</body>
</html>
"""
        
        return html
    

    def _build_logos_html(self, config: 'AlertConfig') -> str:
        """
        Build HTML for company logos based on which are available.
        
        Args:
            config: AlertConfig instance
            
        Returns:
            HTML string with img tags for available logos
        """
        logos_html = ""
        
        for company_name, logo_path in config.company_logos.items():
            if logo_path.exists():
                # CID format matches what EmailSender uses
                cid = f"{company_name}_logo"
                logos_html += f'<img src="cid:{cid}" alt="{company_name} logo">\n            '
        
        return logos_html.strip()
