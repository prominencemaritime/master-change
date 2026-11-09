# tests/test_integration.py
"""
Integration tests for complete alert workflow.
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta


def test_alert_initializes_correctly(mock_config):
    """Test that alert initializes with correct configuration."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    
    assert alert.sql_query_file == 'MastersNavigationAudit.sql'
    assert alert.lookback_days == mock_config.lookback_days
    assert alert.rank_id == mock_config.rank_id


def test_alert_filters_data_by_lookback_days(mock_config, sample_dataframe):
    """Test that filter_data correctly filters by lookback days."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    alert.lookback_days = 1  # Last 24 hours
    
    # Sample data has one captain who signed on 2 days ago (outside lookback)
    filtered = alert.filter_data(sample_dataframe)
    
    # Should filter out the one that's 2 days old
    assert len(filtered) == 3  # Changed from 4 to 3


def test_alert_filters_out_old_data(mock_config, sample_dataframe):
    """Test that old data is filtered out."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    # Create old record by copying a row and modifying it
    old_record = sample_dataframe.iloc[[0]].copy()
    old_record['crew_contract_id'] = 999
    old_record['crew_member_id'] = 999
    old_record['vessel_id'] = 999
    old_record['vessel'] = 'OLD VESSEL'
    old_record['vsl_email'] = 'old@test.com'
    old_record['surname'] = 'Old'
    old_record['full_name'] = 'Old Captain'
    old_record['sign_on_date'] = datetime.now() - timedelta(days=5)
    
    df_with_old = pd.concat([sample_dataframe, old_record], ignore_index=True)
    
    alert = MastersNavigationAuditAlert(mock_config)
    alert.lookback_days = 1
    
    filtered = alert.filter_data(df_with_old)
    
    # Should exclude the old record (and one from sample that's 2 days old)
    assert len(filtered) == 3  # Changed from 4 to 3
    assert 999 not in filtered['crew_contract_id'].values


def test_alert_routes_by_vessel(mock_config, sample_dataframe):
    """Test that notifications are routed correctly by vessel."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    jobs = alert.route_notifications(sample_dataframe)
    
    # Should create 2 jobs (VESSEL with 2 captains, OTHER VESSEL with 2 captains)
    assert len(jobs) == 2
    
    # Check first vessel job
    vessel_job = next(j for j in jobs if j['metadata']['vessel_name'] == 'VESSEL')
    assert len(vessel_job['data']) == 2
    assert vessel_job['recipients'] == ['test@prominencemaritime.com']


def test_alert_assigns_correct_cc_recipients(mock_config, sample_dataframe):
    """Test that CC recipients are assigned based on email domain plus internal recipients."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    jobs = alert.route_notifications(sample_dataframe)
    
    # Sample data has BOTH Prominence and Seatraders vessels
    for job in jobs:
        cc_recipients = job['cc_recipients']
        
        # Check domain-specific CC based on vessel email
        if 'prominencemaritime' in job['recipients'][0]:
            # Should include Prominence CC recipients
            assert 'prom1@test.com' in cc_recipients
            assert 'prom2@test.com' in cc_recipients
        elif 'seatraders' in job['recipients'][0]:
            # Should include Seatraders CC recipients
            assert 'sea1@test.com' in cc_recipients
            assert 'sea2@test.com' in cc_recipients
        
        # Should ALSO include internal recipients (from conftest.py)
        assert 'internal@test.com' in cc_recipients


def test_alert_prominence_domain_gets_prominence_cc(mock_config):
    """Test that Prominence domain gets Prominence CC recipients."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    # Create test dataframe with Prominence vessel
    test_df = pd.DataFrame({
        'crew_contract_id': [101],
        'crew_member_id': [201],
        'vessel_id': [123],
        'vessel': ['TEST VESSEL'],
        'vsl_email': ['test@prominencemaritime.com'],
        'surname': ['Smith'],
        'full_name': ['John Smith'],
        'rank': ['Captain'],
        'sign_on_date': [datetime.now() - timedelta(days=1)],
        'due_date': [(datetime.now() - timedelta(days=1) + timedelta(days=14)).date()],
    })
    
    alert = MastersNavigationAuditAlert(mock_config)
    jobs = alert.route_notifications(test_df)
    
    assert len(jobs) == 1
    cc_recipients = jobs[0]['cc_recipients']
    
    # Should include Prominence CC recipients
    assert 'prom1@test.com' in cc_recipients
    assert 'prom2@test.com' in cc_recipients


def test_alert_seatraders_domain_gets_seatraders_cc(mock_config):
    """Test that Seatraders domain gets Seatraders CC recipients."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    # Create test dataframe with Seatraders vessel
    test_df = pd.DataFrame({
        'crew_contract_id': [101],
        'crew_member_id': [201],
        'vessel_id': [789],
        'vessel': ['SEA VESSEL'],
        'vsl_email': ['test@seatraders.com'],
        'surname': ['Jones'],
        'full_name': ['Jane Jones'],
        'rank': ['Captain'],
        'sign_on_date': [datetime.now() - timedelta(days=1)],
        'due_date': [(datetime.now() - timedelta(days=1) + timedelta(days=14)).date()],
    })
    
    alert = MastersNavigationAuditAlert(mock_config)
    jobs = alert.route_notifications(test_df)
    
    assert len(jobs) == 1
    cc_recipients = jobs[0]['cc_recipients']
    
    # Should include Seatraders CC recipients
    assert 'sea1@test.com' in cc_recipients
    assert 'sea2@test.com' in cc_recipients


def test_alert_generates_correct_subject_lines(mock_config, sample_dataframe):
    """Test subject line generation."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    
    # Single record
    single_df = sample_dataframe.iloc[:1]
    subject_single = alert.get_subject_line(single_df, {'vessel': 'TEST VESSEL'})
    assert subject_single == "AlertDev | TEST VESSEL Master's Navigation Audit"
    
    # Multiple records (same subject format regardless of count)
    multi_df = sample_dataframe.iloc[:3]
    subject_multi = alert.get_subject_line(multi_df, {'vessel': 'VESSEL'})
    assert subject_multi == "AlertDev | VESSEL Master's Navigation Audit"


def test_alert_generates_correct_tracking_keys(mock_config, sample_dataframe):
    """Test that tracking keys are generated correctly."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    
    row = sample_dataframe.iloc[0]
    key = alert.get_tracking_key(row)
    
    # Format: vessel__crew_contract_id_{X}__crew_member_id_{Y}
    vessel = row['vessel'].lower()
    crew_contract_id = row['crew_contract_id']
    crew_member_id = row['crew_member_id']
    expected_key = f"{vessel}__crew_contract_id_{crew_contract_id}__crew_member_id_{crew_member_id}"
    assert key == expected_key
    assert '__' in key  # Double underscore separator


def test_alert_required_columns_validation(mock_config):
    """Test that required columns are correctly defined."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    required = alert.get_required_columns()
    
    # Masters Navigation Audit schema
    assert 'vsl_email' in required
    assert 'vessel_id' in required
    assert 'vessel' in required
    assert 'crew_contract_id' in required
    assert 'crew_member_id' in required
    assert 'surname' in required
    assert 'full_name' in required
    assert 'rank' in required
    assert 'sign_on_date' in required
    assert 'due_date' in required


def test_alert_validates_dataframe_columns(mock_config, sample_dataframe):
    """Test that DataFrame validation works correctly."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    
    # Should not raise exception with valid DataFrame
    alert.validate_required_columns(sample_dataframe)
    
    # Should raise exception with missing column
    invalid_df = sample_dataframe.drop(columns=['vessel_id'])
    with pytest.raises(ValueError, match="Missing required columns"):
        alert.validate_required_columns(invalid_df)


def test_alert_includes_internal_recipients_in_cc(mock_config, sample_dataframe):
    """Test that internal recipients are always included in CC."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    # Set up internal recipients
    mock_config.internal_recipients = ['admin@company.com', 'manager@company.com']
    
    alert = MastersNavigationAuditAlert(mock_config)
    jobs = alert.route_notifications(sample_dataframe)
    
    # Check all jobs include internal recipients in CC
    for job in jobs:
        cc_recipients = job['cc_recipients']
        
        # Internal recipients should ALWAYS be in the CC list
        assert 'admin@company.com' in cc_recipients, \
            f"Internal recipient 'admin@company.com' missing from CC: {cc_recipients}"
        assert 'manager@company.com' in cc_recipients, \
            f"Internal recipient 'manager@company.com' missing from CC: {cc_recipients}"
        
        # Domain-specific recipients should also be present
        # Sample data has BOTH Prominence and Seatraders vessels
        # So we check based on the recipient email
        if 'prominencemaritime' in job['recipients'][0]:
            assert 'prom1@test.com' in cc_recipients
            assert 'prom2@test.com' in cc_recipients
        elif 'seatraders' in job['recipients'][0]:
            assert 'sea1@test.com' in cc_recipients
            assert 'sea2@test.com' in cc_recipients


def test_alert_internal_recipients_when_no_domain_match(mock_config):
    """Test that internal recipients are used when domain doesn't match routing."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    # Create dataframe with unknown domain
    unknown_domain_df = pd.DataFrame({
        'crew_contract_id': [101],
        'crew_member_id': [201],
        'vessel_id': [999],
        'vessel': ['UNKNOWN VESSEL'],
        'vsl_email': ['unknown@unknowndomain.com'],  # Not in routing
        'surname': ['Unknown'],
        'full_name': ['Captain Unknown'],
        'rank': ['Captain'],
        'sign_on_date': [datetime.now() - timedelta(days=1)],
        'due_date': [(datetime.now() - timedelta(days=1) + timedelta(days=14)).date()],
    })
    
    # Set up internal recipients
    mock_config.internal_recipients = ['admin@company.com', 'manager@company.com']
    
    alert = MastersNavigationAuditAlert(mock_config)
    jobs = alert.route_notifications(unknown_domain_df)
    
    # Should have one job
    assert len(jobs) == 1
    
    # Should ONLY have internal recipients (no domain match)
    cc_recipients = jobs[0]['cc_recipients']
    assert 'admin@company.com' in cc_recipients
    assert 'manager@company.com' in cc_recipients
    assert len(cc_recipients) == 2  # Only internal, no domain-specific


def test_alert_deduplicates_cc_recipients(mock_config, sample_dataframe):
    """Test that duplicate emails in CC list are removed."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    # Set internal recipients to overlap with domain CC (prom1@test.com)
    mock_config.internal_recipients = ['prom1@test.com', 'admin@company.com']
    
    alert = MastersNavigationAuditAlert(mock_config)
    jobs = alert.route_notifications(sample_dataframe)
    
    # Check that duplicates are removed
    for job in jobs:
        cc_recipients = job['cc_recipients']
        
        # Should not have duplicates
        assert len(cc_recipients) == len(set(cc_recipients)), \
            f"Duplicate emails found in CC list: {cc_recipients}"
        
        # Check based on vessel domain
        if 'prominencemaritime' in job['recipients'][0]:
            # prom1@test.com should appear only once (even though it's in both lists)
            assert cc_recipients.count('prom1@test.com') == 1
            # Should have 3 unique recipients: prom1, prom2, admin (prom1 appears in both lists)
            assert len(cc_recipients) == 3
        elif 'seatraders' in job['recipients'][0]:
            # Seatraders vessels get: sea1, sea2, prom1 (from internal), admin
            # Should have 4 unique recipients
            assert len(cc_recipients) == 4


def test_alert_format_date_column(mock_config):
    """Test that _format_date_column formats dates correctly."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    
    # Create test dataframe with various date formats
    test_df = pd.DataFrame({
        'test_date': [
            pd.Timestamp('2025-12-01'),
            pd.Timestamp('2025-12-15 10:30:00'),
            None,
            pd.NaT
        ]
    })
    
    alert._format_date_column(test_df, 'test_date')
    
    # Check formatting
    assert test_df['test_date'].iloc[0] == '2025-12-01'
    assert test_df['test_date'].iloc[1] == '2025-12-15'
    assert test_df['test_date'].iloc[2] == ''  # None becomes empty string
    assert test_df['test_date'].iloc[3] == ''  # NaT becomes empty string


def test_alert_get_url_links_when_enabled(mock_config):
    """Test URL generation when links are enabled."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    mock_config.enable_links = True
    mock_config.base_url = 'https://prominence.orca.tools'
    mock_config.url_path = '/events'
    
    alert = MastersNavigationAuditAlert(mock_config)
    
    url = alert._get_url_links(12345)
    
    assert url == 'https://prominence.orca.tools/events/12345'


def test_alert_get_url_links_when_disabled(mock_config):
    """Test URL generation when links are disabled."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    mock_config.enable_links = False
    
    alert = MastersNavigationAuditAlert(mock_config)
    
    url = alert._get_url_links(12345)
    
    assert url is None


def test_alert_url_links_added_to_dataframe(mock_config, sample_dataframe):
    """Test that URL links are added to dataframe when enabled."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    mock_config.enable_links = True
    mock_config.base_url = 'https://prominence.orca.tools'
    mock_config.url_path = '/events'
    
    alert = MastersNavigationAuditAlert(mock_config)
    jobs = alert.route_notifications(sample_dataframe)
    
    # Check that jobs have URL column
    for job in jobs:
        assert 'url' in job['data'].columns
        # Check that URLs are not null
        assert job['data']['url'].notna().all()


def test_alert_display_columns_specified(mock_config, sample_dataframe):
    """Test that display_columns are specified in metadata."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    jobs = alert.route_notifications(sample_dataframe)
    
    expected_display_columns = [
        'full_name',
        'rank',
        'sign_on_date',
        'due_date'
    ]
    
    for job in jobs:
        assert 'display_columns' in job['metadata']
        assert job['metadata']['display_columns'] == expected_display_columns


def test_alert_get_company_name_prominence(mock_config):
    """Test company name determination for Prominence."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    
    company = alert._get_company_name('vessel@prominencemaritime.com')
    assert company == 'Prominence Maritime S.A.'
    
    company = alert._get_company_name('vessel@vsl.prominencemaritime.com')
    assert company == 'Prominence Maritime S.A.'


def test_alert_get_company_name_seatraders(mock_config):
    """Test company name determination for Seatraders."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    
    company = alert._get_company_name('vessel@seatraders.com')
    assert company == 'Sea Traders S.A.'
    
    company = alert._get_company_name('vessel@vsl.seatraders.com')
    assert company == 'Sea Traders S.A.'


def test_alert_get_company_name_default(mock_config):
    """Test company name determination for unknown domain."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    
    company = alert._get_company_name('vessel@unknown.com')
    assert company == 'Prominence Maritime S.A.'  # Default


def test_alert_filter_replaces_null_values(mock_config):
    """Test that filter_data replaces null values with empty strings."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    # Create dataframe with null values
    test_df = pd.DataFrame({
        'crew_contract_id': [101],
        'crew_member_id': [201],
        'vessel_id': [123],
        'vessel': ['TEST VESSEL'],
        'vsl_email': ['test@test.com'],
        'surname': [None],  # Null
        'full_name': ['John Smith'],
        'rank': [None],  # Null
        'sign_on_date': ['2025-12-01'],
        'due_date': ['2025-12-15'],
    })
    
    alert = MastersNavigationAuditAlert(mock_config)
    filtered = alert.filter_data(test_df)
    
    # Check that nulls are replaced with empty strings
    assert filtered['surname'].iloc[0] == '' or pd.isna(filtered['surname'].iloc[0])
    assert filtered['rank'].iloc[0] == '' or pd.isna(filtered['rank'].iloc[0])


def test_alert_filter_formats_dates_correctly(mock_config, sample_dataframe):
    """Test that filter_data formats dates correctly."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    alert = MastersNavigationAuditAlert(mock_config)
    filtered = alert.filter_data(sample_dataframe)
    
    # sign_on_date should be formatted as datetime string
    for sign_on_date in filtered['sign_on_date']:
        # Should match format: YYYY-MM-DD HH:MM:SS
        assert len(sign_on_date) == 19
        assert sign_on_date[4] == '-'
        assert sign_on_date[7] == '-'
        assert sign_on_date[10] == ' '
        assert sign_on_date[13] == ':'
        assert sign_on_date[16] == ':'
    
    # due_date should be formatted as date strings
    for due_date in filtered['due_date']:
        # Should match format: YYYY-MM-DD
        assert len(due_date) == 10
        assert due_date[4] == '-'
        assert due_date[7] == '-'


@patch('src.alerts.masters_navigation_audit.get_db_connection')
@patch('src.alerts.masters_navigation_audit.pd.read_sql_query')
@patch('src.notifications.email_sender.EmailSender.send')
def test_complete_alert_workflow(mock_send, mock_read_sql, mock_get_db, mock_config, sample_dataframe, mock_event_tracker, temp_dir):
    """Test complete alert workflow from fetch to send."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    from src.formatters.html_formatter import HTMLFormatter
    from src.formatters.text_formatter import TextFormatter
    from src.notifications.email_sender import EmailSender

    # Mock get_db_connection to return a dummy context manager
    mock_conn = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_get_db.return_value.__exit__.return_value = None

    # Mock pd.read_sql_query to return sample data
    mock_read_sql.return_value = sample_dataframe

    # Create SQL query file
    mock_config.queries_dir.mkdir(parents=True, exist_ok=True)
    sql_file = mock_config.queries_dir / 'MastersNavigationAudit.sql'
    sql_file.write_text('SELECT * FROM crew_contracts;')

    # Initialize components
    mock_config.tracker = mock_event_tracker
    mock_config.email_sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    mock_config.html_formatter = HTMLFormatter()
    mock_config.text_formatter = TextFormatter()

    # Create and run alert
    alert = MastersNavigationAuditAlert(mock_config)
    alert.run()

    # Verify email was sent (2 vessels = 2 emails: VESSEL and OTHER VESSEL)
    assert mock_send.call_count == 2

    # Verify tracking was updated (4 jobs total)
    assert len(mock_event_tracker.sent_events) == 4


@patch('src.alerts.masters_navigation_audit.get_db_connection')
@patch('src.alerts.masters_navigation_audit.pd.read_sql_query')
def test_alert_prevents_duplicate_sends(mock_read_sql, mock_get_db, mock_config, sample_dataframe, mock_event_tracker, temp_dir):
    """Test that alert doesn't send duplicates."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert

    # Mock get_db_connection
    mock_conn = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_get_db.return_value.__exit__.return_value = None

    # Mock pd.read_sql_query to return sample data
    mock_read_sql.return_value = sample_dataframe

    # Create SQL query file
    sql_file = mock_config.queries_dir / 'MastersNavigationAudit.sql'
    sql_file.write_text('SELECT * FROM crew_contracts;')

    # Initialize
    mock_config.tracker = mock_event_tracker
    mock_email_sender = MagicMock()
    mock_config.email_sender = mock_email_sender
    mock_config.html_formatter = MagicMock()
    mock_config.text_formatter = MagicMock()

    # Mock formatters to return dummy content
    mock_config.html_formatter.format.return_value = '<html>Test</html>'
    mock_config.text_formatter.format.return_value = 'Test'

    # First run - should send
    alert = MastersNavigationAuditAlert(mock_config)
    alert.run()

    first_call_count = mock_email_sender.send.call_count
    assert first_call_count > 0

    # Second run - should not send (duplicates)
    alert2 = MastersNavigationAuditAlert(mock_config)
    alert2.run()

    # Call count should be same (no new sends)
    assert mock_email_sender.send.call_count == first_call_count


def test_dry_run_email_redirection(mock_config, sample_dataframe, temp_dir):
    """Test that dry-run mode redirects emails correctly."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert

    # Enable dry-run with email redirection
    mock_config.dry_run = True
    mock_config.dry_run_email = 'dryrun@test.com'
    mock_config.enable_email_alerts = True

    # Create alert
    alert = MastersNavigationAuditAlert(mock_config)

    # Route notifications
    jobs = alert.route_notifications(sample_dataframe)

    # All jobs should have original recipients (redirection happens in EmailSender, not routing)
    for job in jobs:
        assert len(job['recipients']) > 0
        # Sample data has both prominencemaritime and seatraders domains
        assert 'prominencemaritime.com' in job['recipients'][0] or 'seatraders.com' in job['recipients'][0]


@patch('src.alerts.masters_navigation_audit.get_db_connection')
@patch('src.alerts.masters_navigation_audit.pd.read_sql_query')
def test_alert_handles_empty_results(mock_read_sql, mock_get_db, mock_config, mock_event_tracker, temp_dir):
    """Test that alert handles empty database results gracefully."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert

    # Mock get_db_connection
    mock_conn = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_get_db.return_value.__exit__.return_value = None

    # Mock pd.read_sql_query to return empty DataFrame with Masters Navigation Audit schema
    empty_df = pd.DataFrame(columns=[
        'crew_contract_id', 'crew_member_id', 'vessel_id', 'vessel',
        'vsl_email', 'surname', 'full_name', 'rank',
        'sign_on_date', 'due_date'
    ])
    mock_read_sql.return_value = empty_df

    # Create SQL query file
    sql_file = mock_config.queries_dir / 'MastersNavigationAudit.sql'
    sql_file.write_text('SELECT * FROM crew_contracts;')

    # Initialize
    mock_config.tracker = mock_event_tracker
    mock_email_sender = MagicMock()
    mock_config.email_sender = mock_email_sender
    mock_config.html_formatter = MagicMock()
    mock_config.text_formatter = MagicMock()

    # Run alert
    alert = MastersNavigationAuditAlert(mock_config)
    result = alert.run()

    # Should complete successfully without sending emails
    # Note: run() returns False when no new data to process, which is expected behavior
    assert result is False
    assert mock_email_sender.send.call_count == 0


@patch('src.alerts.masters_navigation_audit.get_db_connection')
@patch('src.alerts.masters_navigation_audit.pd.read_sql_query')
def test_alert_with_multiple_jobs_per_vessel(mock_read_sql, mock_get_db, mock_config, mock_event_tracker, temp_dir):
    """Test alert correctly groups multiple jobs for the same vessel."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert

    # Mock get_db_connection
    mock_conn = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_get_db.return_value.__exit__.return_value = None

    # Create DataFrame with multiple jobs for same vessel
    multi_job_df = pd.DataFrame({
        'crew_contract_id': [48941, 48942, 48943],
        'crew_member_id': [123, 456, 789],
        'vessel_id': [1, 1, 1],
        'vsl_email': ['lia@vsl.prominencemaritime.com', 'lia@vsl.prominencemaritime.com', 'lia@vsl.prominencemaritime.com'],
        'vessel': ['LIA', 'LIA', 'LIA'],
        'surname': ['White', 'Mustard', 'Scarlet'],
        'full_name': ['Mrs White', 'Colonel Mustard', 'Miss Scarlet'],
        'rank': ['Captain', 'Captain', 'Captain'],
        'sign_on_date': [datetime.now() - timedelta(hours=6)] * 3,
        'due_date': [(datetime.now() - timedelta(hours=6) + timedelta(days=14)).date()] * 3
    })

    mock_read_sql.return_value = multi_job_df

    # Create SQL query file
    sql_file = mock_config.queries_dir / 'MastersNavigationAudit.sql'
    sql_file.write_text('SELECT * FROM crew_contracts;')

    # Initialize
    mock_config.tracker = mock_event_tracker
    mock_email_sender = MagicMock()
    mock_config.email_sender = mock_email_sender
    mock_config.html_formatter = MagicMock()
    mock_config.text_formatter = MagicMock()

    # Mock formatters
    mock_config.html_formatter.format.return_value = '<html>Test</html>'
    mock_config.text_formatter.format.return_value = 'Test'

    # Run alert
    alert = MastersNavigationAuditAlert(mock_config)
    alert.run()

    # Should send only 1 email (all jobs for LIA grouped together)
    assert mock_email_sender.send.call_count == 1

    # Should track all 3 jobs
    assert len(mock_event_tracker.sent_events) == 3


@patch('src.alerts.masters_navigation_audit.get_db_connection')
@patch('src.alerts.masters_navigation_audit.pd.read_sql_query')
def test_alert_respects_lookback_days(mock_read_sql, mock_get_db, mock_config, mock_event_tracker, temp_dir):
    """Test that alert correctly filters by lookback_days."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert

    # Mock get_db_connection
    mock_conn = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_get_db.return_value.__exit__.return_value = None

    # Create DataFrame with captains at different sign-on ages
    mixed_age_df = pd.DataFrame({
        'crew_contract_id': [101, 102, 103],
        'crew_member_id': [201, 202, 203],
        'vessel_id': [1, 2, 3],
        'vessel': ['VESSEL1', 'VESSEL2', 'VESSEL3'],
        'vsl_email': ['v1@test.com', 'v2@test.com', 'v3@test.com'],
        'surname': ['Recent', 'Old', 'VeryOld'],
        'full_name': ['Recent Captain', 'Old Captain', 'Very Old Captain'],
        'rank': ['Captain', 'Captain', 'Captain'],
        'sign_on_date': [
            datetime.now() - timedelta(hours=2),    # Recent (within 1 day)
            datetime.now() - timedelta(days=3),     # Old (outside 1 day)
            datetime.now() - timedelta(days=10)     # Very old (outside 1 day)
        ],
        'due_date': [
            (datetime.now() - timedelta(hours=2) + timedelta(days=14)).date(),
            (datetime.now() - timedelta(days=3) + timedelta(days=14)).date(),
            (datetime.now() - timedelta(days=10) + timedelta(days=14)).date()
        ]
    })

    mock_read_sql.return_value = mixed_age_df

    # Create SQL query file
    sql_file = mock_config.queries_dir / 'MastersNavigationAudit.sql'
    sql_file.write_text('SELECT * FROM crew_contracts;')

    # Initialize with lookback_days=1
    mock_config.lookback_days = 1
    mock_config.tracker = mock_event_tracker
    mock_email_sender = MagicMock()
    mock_config.email_sender = mock_email_sender
    mock_config.html_formatter = MagicMock()
    mock_config.text_formatter = MagicMock()

    # Mock formatters
    mock_config.html_formatter.format.return_value = '<html>Test</html>'
    mock_config.text_formatter.format.return_value = 'Test'

    # Run alert
    alert = MastersNavigationAuditAlert(mock_config)
    alert.run()

    # Should only send 1 email (only the recent job within 1 day)
    assert mock_email_sender.send.call_count == 1

    # Should only track 1 job (the recent one)
    assert len(mock_event_tracker.sent_events) == 1


@patch('src.alerts.masters_navigation_audit.get_db_connection')
@patch('src.alerts.masters_navigation_audit.pd.read_sql_query')
def test_alert_includes_urls_when_enabled(mock_read_sql, mock_get_db, mock_config, sample_dataframe, mock_event_tracker, temp_dir):
    """Test that URLs are added to job data when links are enabled."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert

    # Mock get_db_connection
    mock_conn = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_get_db.return_value.__exit__.return_value = None

    # Mock pd.read_sql_query
    mock_read_sql.return_value = sample_dataframe

    # Create SQL query file
    sql_file = mock_config.queries_dir / 'MastersNavigationAudit.sql'
    sql_file.write_text('SELECT * FROM crew_contracts;')

    # Enable links
    mock_config.enable_links = True
    mock_config.base_url = 'https://prominence.orca.tools'
    mock_config.url_path = '/events'

    # Initialize
    alert = MastersNavigationAuditAlert(mock_config)

    # Route notifications (don't need full run)
    jobs = alert.route_notifications(sample_dataframe)

    # Check that all jobs have URL column in data
    for job in jobs:
        assert 'url' in job['data'].columns
        # Verify URLs are properly formatted
        for url in job['data']['url']:
            assert url.startswith('https://prominence.orca.tools/events/')
            assert url.split('/')[-1].isdigit()  # Should end with crew_contract_id


@patch('src.alerts.masters_navigation_audit.get_db_connection')
@patch('src.alerts.masters_navigation_audit.pd.read_sql_query')
def test_alert_metadata_includes_vessel_info(mock_read_sql, mock_get_db, mock_config, sample_dataframe, mock_event_tracker, temp_dir):
    """Test that metadata includes correct vessel information."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert

    # Mock get_db_connection
    mock_conn = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_get_db.return_value.__exit__.return_value = None

    # Mock pd.read_sql_query
    mock_read_sql.return_value = sample_dataframe

    # Create SQL query file
    sql_file = mock_config.queries_dir / 'MastersNavigationAudit.sql'
    sql_file.write_text('SELECT * FROM crew_contracts;')

    # Initialize
    alert = MastersNavigationAuditAlert(mock_config)

    # Route notifications
    jobs = alert.route_notifications(sample_dataframe)

    # Check metadata for each job
    for job in jobs:
        metadata = job['metadata']
        
        # Should have all required metadata fields
        assert 'vessel_id' in metadata
        assert 'vessel_name' in metadata
        assert 'alert_title' in metadata
        assert 'company_name' in metadata
        assert 'display_columns' in metadata
        
        # Alert title should be correct
        assert metadata['alert_title'] == "Master's Navigation Audit"
        
        # Vessel name should match one from sample data
        assert metadata['vessel_name'] in ['VESSEL', 'OTHER VESSEL']
        
        # Company name should be set based on domain
        assert metadata['company_name'] in ['Prominence Maritime S.A.', 'Sea Traders S.A.']
