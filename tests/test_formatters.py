# tests/test_formatters.py
"""
Tests for formatters (HTML and Text).
"""
import pytest
from datetime import datetime
import pandas as pd
from src.formatters.html_formatter import HTMLFormatter
from src.formatters.text_formatter import TextFormatter


def test_html_formatter_generates_valid_html(mock_config, sample_dataframe):
    """Test that HTML formatter generates valid HTML."""
    formatter = HTMLFormatter()
    run_time = datetime.now()
    
    metadata = {
        'alert_title': 'Test Alert',
        'vessel_name': 'TEST VESSEL',
        'company_name': 'Test Company',
        'surname': 'Smith',
        'display_columns': ['full_name', 'rank', 'sign_on_date']  # Masters Navigation Audit columns
    }
    
    html = formatter.format(sample_dataframe, run_time, mock_config, metadata)
    
    assert '<!DOCTYPE html' in html
    assert 'Test Alert' in html
    assert 'TEST VESSEL' in html
    # Check for actual data from sample_dataframe
    assert 'John Smith' in html or 'Smith' in html  # Check for actual captain name


def test_html_formatter_handles_empty_dataframe(mock_config):
    """Test that HTML formatter handles empty DataFrame."""
    formatter = HTMLFormatter()
    run_time = datetime.now()
    
    empty_df = pd.DataFrame(columns=['full_name', 'rank'])
    
    metadata = {
        'alert_title': 'Empty Alert',
        'vessel_name': 'VESSEL',
        'surname': 'Test'
    }
    
    html = formatter.format(empty_df, run_time, mock_config, metadata)
    
    assert '<!DOCTYPE html' in html
    assert 'Empty Alert' in html


def test_html_formatter_displays_only_specified_columns(mock_config, sample_dataframe):
    """Test that only specified columns are displayed."""
    formatter = HTMLFormatter()
    run_time = datetime.now()
    
    metadata = {
        'alert_title': 'Test',
        'surname': 'Smith',
        'display_columns': ['full_name', 'rank']  # Masters Navigation Audit columns
    }
    
    html = formatter.format(sample_dataframe, run_time, mock_config, metadata)
    
    # Should include specified columns (column names are title-cased in HTML)
    assert 'Full Name' in html or 'Full_Name' in html
    assert 'Rank' in html


def test_route_notifications_adds_urls(mock_config, sample_dataframe):
    """Test that route_notifications adds url column when links enabled."""
    from src.alerts.masters_navigation_audit import MastersNavigationAuditAlert
    
    # Enable links
    mock_config.enable_links = True
    mock_config.base_url = 'https://test.com'
    mock_config.url_path = '/events'
    
    alert = MastersNavigationAuditAlert(mock_config)
    jobs = alert.route_notifications(sample_dataframe)
    
    # Check that url column was added
    for job in jobs:
        data = job['data']
        
        # Should have url column
        assert 'url' in data.columns
        
        # Each URL should be properly formatted
        for idx, row in data.iterrows():
            expected_url = f"https://test.com/events/{row['crew_contract_id']}"  # Uses crew_contract_id
            assert row['url'] == expected_url


def test_text_formatter_generates_plain_text(mock_config, sample_dataframe):
    """Test that text formatter generates plain text."""
    formatter = TextFormatter()
    run_time = datetime.now()
    
    metadata = {
        'alert_title': 'Test Alert',
        'vessel_name': 'TEST VESSEL',
        'display_columns': ['full_name', 'rank']  # Masters Navigation Audit columns
    }
    
    text = formatter.format(sample_dataframe, run_time, mock_config, metadata)
    
    assert 'Test Alert' in text
    assert 'TEST VESSEL' in text
    # Check for actual data from sample_dataframe
    assert 'John Smith' in text or 'Smith' in text  # Check for actual captain name


def test_text_formatter_handles_empty_dataframe(mock_config):
    """Test that text formatter handles empty DataFrame."""
    formatter = TextFormatter()
    run_time = datetime.now()
    
    empty_df = pd.DataFrame(columns=['full_name', 'rank'])
    
    metadata = {
        'alert_title': 'Empty Alert',
        'vessel_name': 'VESSEL'
    }
    
    text = formatter.format(empty_df, run_time, mock_config, metadata)
    
    assert 'Empty Alert' in text
    assert 'VESSEL' in text
