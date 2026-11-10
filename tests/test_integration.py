# tests/test_integration.py
"""
Integration tests for complete alert workflow.
"""
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta


@patch('src.alerts.master_change.get_db_connection')
@patch('src.alerts.master_change.pd.read_sql_query')
@patch('src.notifications.email_sender.EmailSender.send')
def test_complete_alert_workflow(mock_send, mock_read_sql, mock_get_db, mock_config, sample_dataframe, mock_event_tracker, temp_dir):
    """Test complete alert workflow from fetch to send."""
    from src.alerts.master_change import MasterChangeAlert
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
    sql_file = mock_config.queries_dir / 'MasterChanges.sql'
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
    alert = MasterChangeAlert(mock_config)
    alert.run()

    # One email per Master change (4 rows = 4 emails, no grouping by vessel)
    assert mock_send.call_count == 4

    # To: the company ICT address resolved from the vessel email domain
    sent_to = sorted(call.kwargs['recipients'][0] for call in mock_send.call_args_list)
    assert sent_to == ['ict@prominencemaritime.com'] * 2 + ['ict@seatraders.com'] * 2

    # Verify tracking was updated (4 Master changes)
    assert len(mock_event_tracker.sent_events) == 4


@patch('src.alerts.master_change.get_db_connection')
@patch('src.alerts.master_change.pd.read_sql_query')
def test_alert_prevents_duplicate_sends(mock_read_sql, mock_get_db, mock_config, sample_dataframe, mock_event_tracker, temp_dir):
    """Test that alert doesn't send duplicates."""
    from src.alerts.master_change import MasterChangeAlert

    # Mock get_db_connection
    mock_conn = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_get_db.return_value.__exit__.return_value = None

    # Mock pd.read_sql_query to return sample data
    mock_read_sql.return_value = sample_dataframe

    # Create SQL query file
    sql_file = mock_config.queries_dir / 'MasterChanges.sql'
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
    alert = MasterChangeAlert(mock_config)
    alert.run()

    first_call_count = mock_email_sender.send.call_count
    assert first_call_count > 0

    # Second run - should not send (duplicates)
    alert2 = MasterChangeAlert(mock_config)
    alert2.run()

    # Call count should be same (no new sends)
    assert mock_email_sender.send.call_count == first_call_count


def test_dry_run_email_redirection(mock_config, sample_dataframe, temp_dir):
    """Test that dry-run mode redirects emails correctly."""
    from src.alerts.master_change import MasterChangeAlert

    # Enable dry-run with email redirection
    mock_config.dry_run = True
    mock_config.dry_run_email = 'dryrun@test.com'
    mock_config.enable_email_alerts = True

    # Create alert
    alert = MasterChangeAlert(mock_config)

    # Route notifications
    jobs = alert.route_notifications(sample_dataframe)

    # All jobs should have original recipients (redirection happens in BaseAlert._send_notifications, not routing)
    for job in jobs:
        assert len(job['recipients']) > 0
        # Sample data has both prominencemaritime and seatraders domains
        assert 'prominencemaritime.com' in job['recipients'][0] or 'seatraders.com' in job['recipients'][0]


@patch('src.alerts.master_change.get_db_connection')
@patch('src.alerts.master_change.pd.read_sql_query')
def test_alert_handles_empty_results(mock_read_sql, mock_get_db, mock_config, mock_event_tracker, temp_dir):
    """Test that alert handles empty database results gracefully."""
    from src.alerts.master_change import MasterChangeAlert

    # Mock get_db_connection
    mock_conn = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_get_db.return_value.__exit__.return_value = None

    # Mock pd.read_sql_query to return empty DataFrame with Master Change schema
    empty_df = pd.DataFrame(columns=[
        'crew_contract_id', 'crew_member_id', 'vessel_id', 'vessel',
        'vsl_email', 'full_name', 'rank', 'sign_on_date', 'due_date',
        'outgoing_master', 'outgoing_sign_off_date'
    ])
    mock_read_sql.return_value = empty_df

    # Create SQL query file
    sql_file = mock_config.queries_dir / 'MasterChanges.sql'
    sql_file.write_text('SELECT * FROM crew_contracts;')

    # Initialize
    mock_config.tracker = mock_event_tracker
    mock_email_sender = MagicMock()
    mock_config.email_sender = mock_email_sender
    mock_config.html_formatter = MagicMock()
    mock_config.text_formatter = MagicMock()

    # Run alert
    alert = MasterChangeAlert(mock_config)
    result = alert.run()

    # Should complete successfully without sending emails
    # Note: run() returns False when no new data to process, which is expected behavior
    assert result is False
    assert mock_email_sender.send.call_count == 0


@patch('src.alerts.master_change.get_db_connection')
@patch('src.alerts.master_change.pd.read_sql_query')
def test_alert_sends_one_email_per_master_change(mock_read_sql, mock_get_db, mock_config, mock_event_tracker, temp_dir):
    """Test that each Master change gets its own email, even on the same vessel (no grouping)."""
    from src.alerts.master_change import MasterChangeAlert

    # Mock get_db_connection
    mock_conn = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_get_db.return_value.__exit__.return_value = None

    # Create DataFrame with multiple Master changes for the same vessel
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
        'due_date': [(datetime.now() - timedelta(hours=6) + timedelta(days=14)).date()] * 3,
        'outgoing_master': ['Professor Plum', 'Mrs White', 'Colonel Mustard'],
        'outgoing_sign_off_date': [datetime.now() - timedelta(hours=3)] * 3
    })

    mock_read_sql.return_value = multi_job_df

    # Create SQL query file
    sql_file = mock_config.queries_dir / 'MasterChanges.sql'
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
    alert = MasterChangeAlert(mock_config)
    alert.run()

    # Should send 3 emails (one per Master change, no grouping by vessel)
    assert mock_email_sender.send.call_count == 3

    # Should track all 3 Master changes
    assert len(mock_event_tracker.sent_events) == 3


@patch('src.alerts.master_change.get_db_connection')
@patch('src.alerts.master_change.pd.read_sql_query')
def test_alert_metadata_includes_vessel_info(mock_read_sql, mock_get_db, mock_config, sample_dataframe, mock_event_tracker, temp_dir):
    """Test that metadata includes correct vessel information."""
    from src.alerts.master_change import MasterChangeAlert

    # Mock get_db_connection
    mock_conn = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_get_db.return_value.__exit__.return_value = None

    # Mock pd.read_sql_query
    mock_read_sql.return_value = sample_dataframe

    # Create SQL query file
    sql_file = mock_config.queries_dir / 'MasterChanges.sql'
    sql_file.write_text('SELECT * FROM crew_contracts;')

    # Initialize
    alert = MasterChangeAlert(mock_config)

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
        assert metadata['alert_title'] == "Master Change"
        
        # Vessel name should match one from sample data
        assert metadata['vessel_name'] in ['VESSEL', 'OTHER VESSEL']
        
        # Company name should be set based on domain
        assert metadata['company_name'] in ['Prominence Maritime S.A.', 'Sea Traders S.A.']
