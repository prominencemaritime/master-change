#src/alerts/masters_navigation_audit.py
"""Master's Navigation Audit Alert Implementation.""" 
from typing import Dict, List, Optional
import pandas as pd 
from datetime import datetime, timedelta 
from zoneinfo import ZoneInfo
from sqlalchemy import text
import logging
 
from src.core.base_alert import BaseAlert 
from src.core.config import AlertConfig 
from src.db_utils import get_db_connection, validate_query_file 


logger = logging.getLogger(__name__)


class MastersNavigationAuditAlert(BaseAlert):
    """Alert for Master's Navigation Audit"""

    def __init__(self, config: AlertConfig):
        """
        Initialise Master's Navigation Audit
        
        Args:
            config: AlertConfig instance
        """
        super().__init__(config)

        # Load query + lookback
        self.sql_query_file = 'MastersNavigationAudit.sql'
        self.lookback_days = config.lookback_days
        self.rank_id = config.rank_id

        # Log instantiation
        self.logger.info(f"[OK] MastersNavigationAuditAlert instance created")

        
    def fetch_data(self) -> pd.DataFrame:
        """
        Fetch Master's Navigation Audits from database

        Returns:
            DataFrame with columns: 
                
                crew_contract_id,
                crew_member_id,
                vessel_id,
                vsl_email,
                vessel, 
                surname,
                full_name,
                rank,
                sign_on_date,
                due_date
        """
        # Load SQL query
        query_path = self.config.queries_dir / self.sql_query_file
        query_sql = validate_query_file(query_path)

        # Bind params to the query
        params = {
                "lookback_days": self.lookback_days,
                "rank_id": self.rank_id
                }
        query = text(query_sql)

        # Execute Query
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        self.logger.info(f"MastersNavigationAuditAlert.fetch_data() is returning a df with {len(df)} rows and {len(df.keys())} columns")
        self.logger.debug(f"df Columns: {[key for key in df.keys()]}")
        return df


    def filter_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter for entries synced in the last lookback_days
    
        Args:
            df: Raw pd.DataFrame from database

        Returns:
            Filtered pd.DataFrame with only recently udpated entries

        Note: this filter preserves the number of columns - which columns are going to be displayed is specified in formatter
        """
        if df.empty:
            return df

        # Timezone awareness
        df['sign_on_date'] = pd.to_datetime(df['sign_on_date'])

        # If the datetime is timezone-naive, localise it to UTC first, then convert to timezone specified in .env 
        # I am assuming all times appearing are UTC, and then, e.g., converting to TIMEZONE='Europe/Athens' will automatically be correct during Winter (UTC+2) and Summer (UTC+3). Alternatively, TIMEZONE=UTC in .env will also work, and this just preserves UTC as the timezone of interest.
        if df['sign_on_date'].dt.tz is None:
            df['sign_on_date'] = df['sign_on_date'].dt.tz_localize('UTC').dt.tz_convert(self.config.timezone)
        else:
            # If already timezone-aware, convert to timezone specified in .env
            df['sign_on_date'] = df['sign_on_date'].dt.tz_convert(self.config.timezone)

        # Calculate cutoff date (timezone-aware)
        cutoff_date = datetime.now(tz=ZoneInfo(self.config.timezone)) - timedelta(days=self.lookback_days)

        # Filter for recent sync (timezone-aware) corresponding to config.lookback_days
        df_filtered = df[df['sign_on_date'] >= cutoff_date].copy()

        # Format dates for display
        df_filtered['sign_on_date'] = df_filtered['sign_on_date'].dt.strftime('%Y-%m-%d %H:%M:%S')

        self._format_date_column(df_filtered, 'due_date')

        self.logger.info(f"Filtered to {len(df_filtered)} entr{'y' if len(df_filtered)==1 else 'ies'} synced with LOOKBACK={self.lookback_days} day{'' if len(df_filtered)==1 else 's'}")

        return df_filtered


    def _format_date_column(self, df: pd.DataFrame, col: str) -> None:
        """
        Modifies the DataFrame in place
        """
        if col in df.columns:
            df[col] = (
                pd.to_datetime(df[col], errors='coerce')
                .dt.strftime('%Y-%m-%d')
                .fillna('')
            )


    def _get_url_links(self, link_id: int) -> Optional[str]:
        """
        Generate URL if links are enabled.

        Constructs URL by combining:
            - BASE_URL from config (e.g. https://prominence.orca.tools)
            - URL_PATH from config (e.g. /jobs/flag-extension-dispensation/)
            - link_id from database (e.g. 123)
        Result: https://prominence.orca.tools/events/123

        Args:
            link_id: in PassagePlan project, given by event.id = event_id

        Returns:
            Complete URL, or None if links are disabled
        """
        if not self.config.enable_links:
            return None

        # Build URL: BASE_URL + URL_PATH + link_id
        base_url = self.config.base_url.rstrip('/')
        url_path = self.config.url_path.rstrip('/')
        full_url = f"{base_url}{url_path}/{link_id}"

        return full_url


    def route_notifications(self, df:pd.DataFrame) -> List[Dict]:
        """
        Route data to appropriate recipients.

        Returns list of notification jobs, where each job is a dict with:
        - 'recipients': List[str] - primary email addresses
        - 'cc_recipients': List[str] - CC email addresses
        - 'data': pd.DataFrame - data for this specific notification
        - 'metadata': Dict - any additional info (vessel name, etc.)

        Args:
            df: Filtered DataFrame

        Returns:
            List of notification job dictionaries
        """
        self.logger.info(f"route_notifications() called with {len(df)} record(s) across {df['vsl_email'].nunique()} vessel(s)")
        jobs = []
    
        # Check if vsl_email is empty and log warning if so
        missing_email = df[df['vsl_email'].isna() | (df['vsl_email'] == '')]
        if not missing_email.empty:
            self.logger.warning(
                f"Skipping {len(missing_email)} record(s) with no vsl_email: "
                f"{missing_email['vessel'].tolist()}"
            )
        df = df[df['vsl_email'].notna() & (df['vsl_email'] != '')]

        # Group by vessel
        grouped = df.groupby(['vsl_email', 'vessel'])
        self.logger.info(f"Grouped into {len(grouped)} vessel group(s): {list(grouped.groups.keys())}")

        for (vsl_email, vessel), vessel_df in grouped:
            self.logger.info(f"Processing vessel '{vessel}' ({vsl_email}): {len(vessel_df)} record(s)")
            # Determine cc recipients
            cc_recipients = self._get_cc_recipients(vsl_email)
            if not cc_recipients:
                self.logger.warning(f"No CC recipients resolved for {vsl_email} -- job will be created with empty CC list")
            else:
                self.logger.info(f"Resolved {len(cc_recipients)} CC recipient(s) for {vsl_email}: {cc_recipients}")

            # Add URLs to dataframe if ENABLE_LINKS
            if self.config.enable_links:
                vessel_df = vessel_df.copy()
                # Masters Navigation Audit doesn't use job_id - use crew_contract_id for URLs
                vessel_df['url'] = vessel_df['crew_contract_id'].apply(
                        self._get_url_links
                )

            # Keep full data with tracking columns for the job
            # The formatter will handle which columns to display
            full_data = vessel_df.copy()

            # Specify WHICH cols to display in email and in what order here
            display_columns = [
                    'full_name',
                    'rank',
                    'sign_on_date',
                    'due_date'
            ]

            # Create notification job
            job = {
                    'recipients': [vsl_email],
                    'cc_recipients': cc_recipients,
                    'data': full_data,
                    'metadata': {
                        'vessel_id': vessel_df['vessel_id'].iloc[0],
                        'vessel_name': vessel,
                        'surname': vessel_df['surname'].iloc[0],
                        'alert_title': "Master's NAV Audit & MLC Inspection",
                        'company_name': self._get_company_name(vsl_email),
                        'display_columns': display_columns
                    }
            }

            jobs.append(job)
            if not jobs:
                self.logger.warning(f"route_notifications() produced 0 jobs from {len(df)} input record(s) -- all records were silently dropped")

            self.logger.info(
                    f"Created notification for vessel '{vessel}' "
                    f"({len(full_data)} document{'' if len(full_data)==1 else 's'}) -> {vsl_email} "
                    f"(CC: {len(cc_recipients)})"
            )

        return jobs


    def _get_cc_recipients(self, vsl_email: str) -> List[str]:
        """
        Determine CC recipients based on vessel email domain.
        Always includes internal recipients.

        Args:
            vsl_email: Vessel's email address

        Returns:
            List of CC email addresses (domain-specific + internal)
        """
        vsl_email_lower = vsl_email.lower()

        # Start with empty list
        cc_list = []

        # Check each configured domain
        entry = 0
        total_entries = len(self.config.email_routing.items())
        for domain, recipients_config in self.config.email_routing.items():
            entry += 1
            if domain.lower() in vsl_email_lower:
                cc_list = recipients_config.get('cc', [])
                break
            else:
                self.logger.info(f"Entry {entry}/{total_entries}: No domain match for vsl_email={vsl_email} (only including internal CC recipients)")

        # Always add internal recipients to CC list
        all_cc_recipients = list(set(cc_list + self.config.internal_recipients))

        return all_cc_recipients


    def _get_company_name(self, vsl_email: str) -> str:
        """
        Determine company name based on vessel email domain.
        
        Args:
            vsl_email: Vessel's email address
            
        Returns:
            Company name string
        """
        vsl_email_lower = vsl_email.lower()
        
        if 'prominence' in vsl_email_lower:
            return 'Prominence Maritime S.A.'
        elif 'seatraders' in vsl_email_lower:
            return 'Sea Traders S.A.'
        else:
            return 'Prominence Maritime S.A.'   # Default company name


    def get_tracking_key(self, row:pd.Series) -> str:
        """
        Generate unique tracking key for a data row.

        This key is used to prevent duplicate notifications.

        Args:
            row: Single row from DataFrame

        Returns:
            Unique string key (e.g., "vessel_123_doc_456")
        """
        try:
            vessel = row['vessel']
            vessel = "_".join(vessel.lower().split(' '))
            crew_contract_id = row['crew_contract_id']
            crew_member_id = row['crew_member_id']

            return f"{vessel}__crew_contract_id_{crew_contract_id}__crew_member_id_{crew_member_id}"

        except KeyError as e:
            self.logger.error(f"Missing column in row for tracking key: {e}")
            self.logger.error(f"Available columns: {list(row.index)}")
            raise


    def get_subject_line(self, data: pd.DataFrame, metadata: Dict) -> str:
        """
        Generate email subject line for a notification.

        Args:
            data: DataFrame for this notification
            metadata: Additional context (vessel name, etc.)

        Returns:
            Email subject string
        """
        vessel = metadata.get('vessel_name', 'Vessel')
        return f"AlertDev | {vessel.upper()} Master's NAV Audit & MLC Inspection"


    def get_required_columns(self) -> List[str]:
        """
        Return list of column names required in the DataFrame.

        Returns:
            List of required column names
        """
        return [
            'crew_contract_id',
            'crew_member_id',
            'vessel_id',
            'vsl_email',
            'vessel',
            'surname',
            'full_name',
            'rank',
            'sign_on_date',
            'due_date'
        ]
