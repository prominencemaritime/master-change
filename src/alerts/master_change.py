#src/alerts/master_change.py
"""Master Change Alert Implementation."""
from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy import text
import logging
from urllib.parse import urlencode

from src.core.base_alert import BaseAlert
from src.core.config import AlertConfig
from src.db_utils import get_db_connection, validate_query_file


logger = logging.getLogger(__name__)


class MasterChangeAlert(BaseAlert):
    """
    Alert for a change of Master.

    Notifies the company ICT address (resolved from the vessel email domain)
    once a new Master has been on board for MASTER_CHANGE_DAYS and is the only
    Master on the crew list. All selection criteria live in
    queries/MasterChanges.sql; this class formats, routes and tracks the rows.
    """

    ALERT_TITLE = "Master Change"
    DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
    DATE_FORMAT = '%Y-%m-%d'

    # Specify WHICH cols to display in email and in what order here
    DISPLAY_COLUMNS = [
        'full_name',
        'rank',
        'sign_on_date',
        'due_date',
        'outgoing_master',
        'outgoing_sign_off_date',
    ]

    # Email routing domain (AlertConfig.email_routing key) -> company name
    COMPANY_NAMES = {
        'prominencemaritime.com': 'Prominence Maritime S.A.',
        'seatraders.com': 'Sea Traders S.A.',
    }
    DEFAULT_COMPANY_NAME = 'Prominence Maritime S.A.'

    # Email routing domain -> AlertConfig.company_logos key (logo shown and attached)
    COMPANY_LOGO_KEYS = {
        'prominencemaritime.com': 'prominence',
        'seatraders.com': 'seatraders',
    }
    DEFAULT_COMPANY_LOGO_KEY = 'prominence'

    def __init__(self, config: AlertConfig):
        """
        Initialise Master Change alert.

        Args:
            config: AlertConfig instance

        Raises:
            ValueError: If the lookback window cannot contain a due change, or
                no To recipients are configured for any company
        """
        super().__init__(config)

        # Load query + windows
        self.sql_query_file = 'MasterChanges.sql'
        self.lookback_days = config.lookback_days
        self.rank_id = config.rank_id
        self.master_change_days = config.master_change_days

        if self.lookback_days <= self.master_change_days:
            raise ValueError(
                f"LOOKBACK_DAYS ({self.lookback_days}) must be greater than "
                f"MASTER_CHANGE_DAYS ({self.master_change_days}), "
                f"otherwise no Master change can ever qualify"
            )

        domains_without_to = [
            domain for domain, routing in config.email_routing.items()
            if not routing.get('to')
        ]
        if len(domains_without_to) == len(config.email_routing):
            raise ValueError(
                "MasterChangeAlert: no To recipients configured. Set "
                "PROMINENCE_EMAIL_TO_RECIPIENTS and/or SEATRADERS_EMAIL_TO_RECIPIENTS in .env"
            )
        for domain in domains_without_to:
            self.logger.warning(
                f"No To recipients configured for {domain}: "
                f"Master changes on its vessels will be skipped"
            )

        # Log instantiation
        self.logger.info(
            f"[OK] MasterChangeAlert instance created "
            f"(MASTER_CHANGE_DAYS={self.master_change_days}, "
            f"LOOKBACK_DAYS={self.lookback_days}, RANK_ID={self.rank_id})"
        )


    def fetch_data(self) -> pd.DataFrame:
        """
        Fetch due Master changes from database.

        Returns:
            DataFrame with the columns listed in get_required_columns()
        """
        # Load SQL query
        query_path = self.config.queries_dir / self.sql_query_file
        query_sql = validate_query_file(query_path)

        # Bind params to the query
        params = {
            "rank_id": self.rank_id,
            "lookback_days": self.lookback_days,
            "master_change_days": self.master_change_days,
        }
        query = text(query_sql)

        # Execute Query
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        self.logger.info(f"MasterChangeAlert.fetch_data() is returning a df with {len(df)} rows and {len(df.columns)} columns")
        self.logger.debug(f"df Columns: {list(df.columns)}")
        return df


    def filter_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare query results for display.

        No rows are removed here: MasterChanges.sql applies every selection
        criterion. Timestamps (stored as naive UTC) are converted to TIMEZONE
        and formatted as strings.

        Args:
            df: Raw pd.DataFrame from database

        Returns:
            pd.DataFrame with display-ready date columns
        """
        if df.empty:
            return df

        df = df.copy()

        df['sign_on_date'] = self._to_local(df['sign_on_date']).dt.strftime(self.DATETIME_FORMAT)
        df['due_date'] = self._to_local(df['due_date']).dt.strftime(self.DATE_FORMAT)
        df['outgoing_sign_off_date'] = (
            self._to_local(df['outgoing_sign_off_date'])
            .dt.strftime(self.DATETIME_FORMAT)
            .fillna('')
        )
        df['outgoing_master'] = df['outgoing_master'].fillna('')

        self.logger.info(f"Prepared {len(df)} Master change{'' if len(df)==1 else 's'} for notification")

        return df


    def _to_local(self, series: pd.Series) -> pd.Series:
        """
        Parse timestamps and convert them to the timezone specified in .env.

        Timezone-naive values are assumed to be UTC (as stored in the database).
        """
        series = pd.to_datetime(series, errors='coerce')
        if series.dt.tz is None:
            series = series.dt.tz_localize('UTC')
        return series.dt.tz_convert(self.config.timezone)


    def route_notifications(self, df: pd.DataFrame) -> List[Dict]:
        """
        Route data to appropriate recipients: one notification per Master change.

        To: the ICT recipients of the company matching the vessel email domain.
        CC: that company's CC recipients plus INTERNAL_RECIPIENTS.

        Args:
            df: Filtered DataFrame

        Returns:
            List of notification job dictionaries
        """
        self.logger.info(f"route_notifications() called with {len(df)} record(s)")
        jobs = []

        for pos in range(len(df)):
            job_df = df.iloc[[pos]].copy()
            row = job_df.iloc[0]
            vessel = row['vessel']
            change_ref = f"'{vessel}' (crew_contract_id={row['crew_contract_id']})"

            vsl_email = row['vsl_email']
            if pd.isna(vsl_email) or not str(vsl_email).strip():
                self.logger.warning(f"Skipping Master change on {change_ref}: vessel has no email, so the company cannot be determined")
                continue
            vsl_email = str(vsl_email).strip()

            domain = self._match_domain(vsl_email)
            routing = self.config.email_routing.get(domain, {}) if domain else {}
            recipients = list(routing.get('to', []))
            if not recipients:
                self.logger.warning(f"Skipping Master change on {change_ref}: no To recipients configured for vessel email {vsl_email}")
                continue

            cc_recipients = self._get_cc_recipients(routing, recipients)

            job = {
                'recipients': recipients,
                'cc_recipients': cc_recipients,
                'data': job_df,
                'metadata': {
                    'vessel_id': row['vessel_id'],
                    'vessel_name': vessel,
                    'alert_title': self.ALERT_TITLE,
                    'company_name': self._get_company_name(domain),
                    'display_columns': self.DISPLAY_COLUMNS,
                    'intro_paragraphs': self._build_intro_paragraphs(row),
                    'logo_keys': [self._get_company_logo_key(domain)],
                }
            }
            jobs.append(job)

            self.logger.info(
                f"Created notification for Master change on {change_ref} -> "
                f"{', '.join(recipients)} (CC: {len(cc_recipients)})"
            )

        if not jobs and len(df) > 0:
            self.logger.warning(f"route_notifications() produced 0 jobs from {len(df)} input record(s) -- see warnings above")

        return jobs


    def _match_domain(self, vsl_email: str) -> Optional[str]:
        """
        Return the email_routing domain matching the vessel email, or None.

        Matches the exact domain or a subdomain of it
        (e.g. vsl.prominencemaritime.com matches prominencemaritime.com).
        """
        email_domain = vsl_email.lower().rsplit('@', 1)[-1]
        for domain in self.config.email_routing:
            routing_domain = domain.lower()
            if email_domain == routing_domain or email_domain.endswith('.' + routing_domain):
                return domain
        return None


    def _get_cc_recipients(self, routing: Dict[str, List[str]], recipients: List[str]) -> List[str]:
        """
        Company CC recipients plus internal recipients, de-duplicated in order,
        excluding anyone already in To.
        """
        to_lower = {r.lower() for r in recipients}
        cc_list = list(routing.get('cc', [])) + list(self.config.internal_recipients)
        return [addr for addr in dict.fromkeys(cc_list) if addr.lower() not in to_lower]


    def _get_company_name(self, domain: Optional[str]) -> str:
        """Company name for an email_routing domain."""
        return self.COMPANY_NAMES.get(domain, self.DEFAULT_COMPANY_NAME)



    def _get_company_logo_key(self, domain: Optional[str]) -> str:
        """AlertConfig.company_logos key of the company logo for an email_routing domain."""
        return self.COMPANY_LOGO_KEYS.get(domain, self.DEFAULT_COMPANY_LOGO_KEY)


    def _crew_list_url(self, vessel_id: int) -> str:
        """Return crew list URL link (on date at which link is clicked) associated to a given vessel."""
        base_url = "https://prominence.orca.tools/crew-list"
        params = {
            "filters[0][name]": "onboard_vessel_id",
            "filters[0][operation]": "=",
            "filters[0][value]": vessel_id,
        }
        return f"{base_url}?{urlencode(params)}"


    def _build_intro_paragraphs(self, row: pd.Series) -> List[str]:
        """
        Plain-text paragraphs shown above the table (escaped by the HTML formatter).
        """
        vessel_id = str(row['vessel_id'])
        url_string = self._crew_list_url(vessel_id)
        url_link = f'<a href="{url_string}" style="color: #0066cc; text-decoration: none;">{here}</a>'

        sign_on_day = str(row['sign_on_date']).split(' ')[0]
        paragraphs = [
            "Dear ICT,",
            f"{self.master_change_days} days have elapsed since Captain {row['full_name']} assumed command of {row['vessel']} (on {sign_on_day}). There is currently no other Master in the crew list. ",
            f"Click {url_link} for the current crew list.",
        ]

        outgoing_master = row.get('outgoing_master', '')
        if outgoing_master and not pd.isna(outgoing_master):
            sign_off = row.get('outgoing_sign_off_date', '')
            sign_off_day = '' if pd.isna(sign_off) else str(sign_off).split(' ')[0]
            if sign_off_day:
                paragraphs.append(f"The previous Master, Captain {outgoing_master}, signed off on {sign_off_day}.")
            else:
                paragraphs.append(f"The previous Master was Captain {outgoing_master}.")
        else:
            paragraphs.append("No previous Master contract was found for this vessel.")

        paragraphs.append("Please carry out any pending actions associated with a change of Master (such as password changes, etc.).")
        return paragraphs


    def get_tracking_key(self, row: pd.Series) -> str:
        """
        Generate unique tracking key for a data row.

        Based on contract and crew member IDs only, so renaming a vessel does
        not cause a resend.

        Args:
            row: Single row from DataFrame

        Returns:
            Unique string key
        """
        try:
            crew_contract_id = int(row['crew_contract_id'])
            crew_member_id = int(row['crew_member_id'])
            return f"master_change__crew_contract_id_{crew_contract_id}__crew_member_id_{crew_member_id}"

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
        return f"AlertDev | {vessel.upper()} {self.ALERT_TITLE}"


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
            'full_name',
            'rank',
            'sign_on_date',
            'due_date',
            'outgoing_master',
            'outgoing_sign_off_date',
        ]
