# tests/test_master_change.py
"""
Tests for MasterChangeAlert logic.

Uses the shared fixtures in conftest.py (mock_config, mock_event_tracker,
mock_email_sender). Alert imports happen inside fixtures/tests, as in the
other test modules, so src.db_utils is only imported once env vars are set.
"""
from contextlib import contextmanager
from pathlib import Path
import logging

import pandas as pd
import pytest


QUERY_FILE = Path(__file__).resolve().parent.parent / 'queries' / 'MasterChanges.sql'


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mc_config(mock_config):
    """mock_config adapted for MasterChangeAlert (conftest sets LOOKBACK_DAYS=4)."""
    mock_config.lookback_days = 40
    mock_config.master_change_days = 14
    mock_config.rank_id = 1
    mock_config.enable_links = False
    mock_config.email_routing = {
        'prominencemaritime.com': {
            'to': ['ict@prominencemaritime.com'],
            'cc': ['prom1@test.com', 'prom2@test.com'],
        },
        'seatraders.com': {
            'to': ['ict@seatraders.com'],
            'cc': ['sea1@test.com', 'sea2@test.com'],
        },
    }
    mock_config.internal_recipients = ['internal@test.com']
    return mock_config


@pytest.fixture
def alert(mc_config):
    from src.alerts.master_change import MasterChangeAlert
    return MasterChangeAlert(mc_config)


def raw_row(**overrides):
    """One row as returned by MasterChanges.sql (naive UTC timestamps)."""
    row = {
        'crew_contract_id': 50001,
        'crew_member_id': 301,
        'vessel_id': 11,
        'vsl_email': 'vessel@prominencemaritime.com',
        'vessel': 'PROM STAR',
        'full_name': 'John Smith',
        'rank': 'Master',
        'sign_on_date': pd.Timestamp('2026-01-10 22:30:00'),
        'due_date': pd.Timestamp('2026-01-24 22:30:00'),
        'outgoing_master': 'Peter Jones',
        'outgoing_sign_off_date': pd.Timestamp('2026-01-12 06:00:00'),
    }
    row.update(overrides)
    return row


def make_df(*rows):
    return pd.DataFrame(list(rows))


def wire_runtime(config, tracker, sender):
    """Inject the runtime components main.initialize_components() would provide."""
    from src.formatters.html_formatter import HTMLFormatter
    from src.formatters.text_formatter import TextFormatter
    config.tracker = tracker
    config.email_sender = sender
    config.html_formatter = HTMLFormatter()
    config.text_formatter = TextFormatter()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def test_alert_initializes_correctly(alert, mc_config):
    assert alert.sql_query_file == 'MasterChanges.sql'
    assert alert.lookback_days == 40
    assert alert.master_change_days == 14
    assert alert.rank_id == 1


@pytest.mark.parametrize('lookback_days', [10, 14])
def test_init_rejects_lookback_not_greater_than_master_change_days(mc_config, lookback_days):
    from src.alerts.master_change import MasterChangeAlert
    mc_config.lookback_days = lookback_days
    with pytest.raises(ValueError, match='LOOKBACK_DAYS'):
        MasterChangeAlert(mc_config)


def test_init_requires_some_to_recipients(mc_config):
    from src.alerts.master_change import MasterChangeAlert
    for routing in mc_config.email_routing.values():
        routing['to'] = []
    with pytest.raises(ValueError, match='no To recipients configured'):
        MasterChangeAlert(mc_config)


def test_init_warns_when_one_company_has_no_to_recipients(mc_config, caplog):
    from src.alerts.master_change import MasterChangeAlert
    mc_config.email_routing['seatraders.com']['to'] = []
    with caplog.at_level(logging.WARNING):
        MasterChangeAlert(mc_config)
    assert 'No To recipients configured for seatraders.com' in caplog.text


# ---------------------------------------------------------------------------
# Query and fetch_data
# ---------------------------------------------------------------------------

def test_query_file_bind_parameters_match_fetch_data():
    """Guards against stray colon-prefixed words (e.g. in comments) becoming bind parameters."""
    from sqlalchemy import text
    sql = QUERY_FILE.read_text(encoding='utf-8')
    assert set(text(sql).compile().params) == {'rank_id', 'lookback_days', 'master_change_days'}


def test_fetch_data_binds_parameters(alert, mc_config, monkeypatch):
    (mc_config.queries_dir / 'MasterChanges.sql').write_text('SELECT 1', encoding='utf-8')
    captured = {}

    @contextmanager
    def fake_connection():
        yield 'conn'

    def fake_read_sql_query(query, conn, params=None):
        captured['params'] = params
        return make_df(raw_row())

    monkeypatch.setattr('src.alerts.master_change.get_db_connection', fake_connection)
    monkeypatch.setattr('src.alerts.master_change.pd.read_sql_query', fake_read_sql_query)

    df = alert.fetch_data()

    assert captured['params'] == {'rank_id': 1, 'lookback_days': 40, 'master_change_days': 14}
    assert len(df) == 1


# ---------------------------------------------------------------------------
# filter_data
# ---------------------------------------------------------------------------

def test_filter_data_converts_utc_to_configured_timezone(alert, mc_config):
    mc_config.timezone = 'Europe/Athens'  # UTC+2 in January
    filtered = alert.filter_data(make_df(raw_row()))
    row = filtered.iloc[0]
    assert row['sign_on_date'] == '2026-01-11 00:30:00'
    assert row['due_date'] == '2026-01-25'
    assert row['outgoing_sign_off_date'] == '2026-01-12 08:00:00'


def test_filter_data_keeps_utc_when_timezone_is_utc(alert, mc_config):
    mc_config.timezone = 'UTC'
    row = alert.filter_data(make_df(raw_row())).iloc[0]
    assert row['sign_on_date'] == '2026-01-10 22:30:00'
    assert row['due_date'] == '2026-01-24'


def test_filter_data_handles_missing_outgoing_master(alert):
    df = make_df(raw_row(outgoing_master=None, outgoing_sign_off_date=None))
    row = alert.filter_data(df).iloc[0]
    assert row['outgoing_master'] == ''
    assert row['outgoing_sign_off_date'] == ''


def test_filter_data_keeps_all_rows_and_does_not_mutate_input(alert):
    df = make_df(
        raw_row(),
        raw_row(crew_contract_id=50002, crew_member_id=302, vessel_id=12, vessel='SEA STAR'),
        raw_row(crew_contract_id=50003, crew_member_id=303, vessel_id=13, vessel='OLD STAR'),
    )
    filtered = alert.filter_data(df)
    assert len(filtered) == 3
    assert isinstance(df['sign_on_date'].iloc[0], pd.Timestamp)


def test_filter_data_empty(alert):
    assert alert.filter_data(pd.DataFrame()).empty


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def test_route_prominence_vessel(alert):
    jobs = alert.route_notifications(alert.filter_data(make_df(raw_row())))
    assert len(jobs) == 1
    job = jobs[0]
    assert job['recipients'] == ['ict@prominencemaritime.com']
    assert job['cc_recipients'] == ['prom1@test.com', 'prom2@test.com', 'internal@test.com']
    assert job['metadata']['company_name'] == 'Prominence Maritime S.A.'


def test_route_seatraders_vessel(alert):
    df = make_df(raw_row(vsl_email='vessel@seatraders.com', vessel='SEA STAR'))
    job = alert.route_notifications(alert.filter_data(df))[0]
    assert job['recipients'] == ['ict@seatraders.com']
    assert job['cc_recipients'] == ['sea1@test.com', 'sea2@test.com', 'internal@test.com']
    assert job['metadata']['company_name'] == 'Sea Traders S.A.'


def test_route_matches_subdomain_case_insensitively(alert):
    df = make_df(raw_row(vsl_email='Vessel@VSL.ProminenceMaritime.com'))
    job = alert.route_notifications(alert.filter_data(df))[0]
    assert job['recipients'] == ['ict@prominencemaritime.com']


def test_route_does_not_match_lookalike_domain(alert, caplog):
    df = make_df(raw_row(vsl_email='vessel@notseatraders.com'))
    with caplog.at_level(logging.WARNING):
        jobs = alert.route_notifications(alert.filter_data(df))
    assert jobs == []
    assert 'no To recipients configured for vessel email vessel@notseatraders.com' in caplog.text


@pytest.mark.parametrize('vsl_email', [None, '', '   '])
def test_route_skips_vessel_without_email(alert, caplog, vsl_email):
    df = make_df(raw_row(vsl_email=vsl_email))
    with caplog.at_level(logging.WARNING):
        jobs = alert.route_notifications(alert.filter_data(df))
    assert jobs == []
    assert 'vessel has no email' in caplog.text


def test_route_skips_company_without_to_but_sends_others(mc_config, caplog):
    from src.alerts.master_change import MasterChangeAlert
    mc_config.email_routing['seatraders.com']['to'] = []
    alert = MasterChangeAlert(mc_config)
    df = make_df(
        raw_row(),
        raw_row(crew_contract_id=50002, crew_member_id=302, vessel_id=12,
                vsl_email='vessel@seatraders.com', vessel='SEA STAR'),
    )
    jobs = alert.route_notifications(alert.filter_data(df))
    assert [j['metadata']['vessel_name'] for j in jobs] == ['PROM STAR']


def test_route_creates_one_job_per_master_change(alert):
    df = make_df(
        raw_row(),
        raw_row(crew_contract_id=50002, crew_member_id=302),
    )
    jobs = alert.route_notifications(alert.filter_data(df))
    assert len(jobs) == 2
    assert [len(j['data']) for j in jobs] == [1, 1]
    assert [int(j['data']['crew_contract_id'].iloc[0]) for j in jobs] == [50001, 50002]


def test_cc_is_deduplicated_and_excludes_to_recipients(alert, mc_config):
    mc_config.internal_recipients = ['prom1@test.com', 'ICT@prominencemaritime.com', 'internal@test.com']
    job = alert.route_notifications(alert.filter_data(make_df(raw_row())))[0]
    assert job['cc_recipients'] == ['prom1@test.com', 'prom2@test.com', 'internal@test.com']


def test_route_metadata(alert):
    job = alert.route_notifications(alert.filter_data(make_df(raw_row())))[0]
    metadata = job['metadata']
    assert metadata['vessel_name'] == 'PROM STAR'
    assert metadata['vessel_id'] == 11
    assert metadata['alert_title'] == 'Master Change'
    assert metadata['display_columns'] == [
        'full_name', 'rank', 'sign_on_date', 'due_date', 'outgoing_master', 'outgoing_sign_off_date'
    ]


# ---------------------------------------------------------------------------
# Intro paragraphs
# ---------------------------------------------------------------------------

def test_intro_paragraphs_with_outgoing_master(alert, mc_config):
    mc_config.timezone = 'UTC'
    job = alert.route_notifications(alert.filter_data(make_df(raw_row())))[0]
    paragraphs = job['metadata']['intro_paragraphs']
    assert paragraphs[:2] == [
        "Dear ICT,",
        "14 days have elapsed since Captain John Smith assumed command of PROM STAR (on 2026-01-10). "
        "There is currently no other Master in the crew list. ",
        ]
    assert paragraphs[2].startswith('Navigate to the <a href="')
    assert paragraphs[3:] == [
        "The previous Master, Captain Peter Jones, signed off on 2026-01-12.",
        "Please carry out any pending actions associated with a change of Master (such as password changes, etc.).",
    ]


def test_intro_paragraphs_without_outgoing_master(alert):
    df = make_df(raw_row(outgoing_master=None, outgoing_sign_off_date=None))
    paragraphs = alert.route_notifications(alert.filter_data(df))[0]['metadata']['intro_paragraphs']
    assert "No previous Master contract was found for this vessel." in paragraphs
    assert not any('previous Master, Captain' in p for p in paragraphs)


def test_intro_uses_master_change_days(mc_config):
    from src.alerts.master_change import MasterChangeAlert
    mc_config.master_change_days = 21
    alert = MasterChangeAlert(mc_config)
    paragraphs = alert.route_notifications(alert.filter_data(make_df(raw_row())))[0]['metadata']['intro_paragraphs']
    assert '21 days have elapsed' in paragraphs[1]


# ---------------------------------------------------------------------------
# Subject, tracking key, required columns
# ---------------------------------------------------------------------------

def test_subject_line(alert):
    assert alert.get_subject_line(pd.DataFrame(), {'vessel_name': 'Prom Star'}) == 'AlertDev | PROM STAR Master Change'


def test_tracking_key_format_and_independent_of_vessel_name(alert):
    row = pd.Series(raw_row())
    renamed = pd.Series(raw_row(vessel='RENAMED STAR'))
    assert alert.get_tracking_key(row) == 'master_change__crew_contract_id_50001__crew_member_id_301'
    assert alert.get_tracking_key(renamed) == alert.get_tracking_key(row)


def test_tracking_key_missing_column_raises(alert):
    with pytest.raises(KeyError):
        alert.get_tracking_key(pd.Series({'crew_member_id': 301}))


def test_required_columns_cover_display_and_tracking(alert):
    required = set(alert.get_required_columns())
    assert set(alert.DISPLAY_COLUMNS) <= required
    assert {'crew_contract_id', 'crew_member_id', 'vsl_email', 'vessel', 'vessel_id'} <= required


def test_validate_required_columns(alert):
    df = make_df(raw_row())
    alert.validate_required_columns(df)
    with pytest.raises(ValueError, match='Missing required columns'):
        alert.validate_required_columns(df.drop(columns=['outgoing_master']))


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def test_html_contains_intro_and_no_navigation_audit_text(alert, mc_config):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.formatters.html_formatter import HTMLFormatter

    job = alert.route_notifications(alert.filter_data(make_df(raw_row())))[0]
    html = HTMLFormatter().format(job['data'], datetime.now(tz=ZoneInfo('UTC')), mc_config, job['metadata'])

    assert 'Captain John Smith assumed command of PROM STAR' in html
    assert 'The previous Master, Captain Peter Jones' in html
    assert '<th>Outgoing Master</th>' in html
    assert '<th>Outgoing Sign Off Date</th>' in html
    assert 'Welcome onboard' not in html
    assert 'F.NAV.13' not in html


def test_html_escapes_intro_text(alert, mc_config):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.formatters.html_formatter import HTMLFormatter

    df = make_df(raw_row(full_name='A & B <script>'))
    job = alert.route_notifications(alert.filter_data(df))[0]
    html = HTMLFormatter().format(job['data'], datetime.now(tz=ZoneInfo('UTC')), mc_config, job['metadata'])
    assert 'Captain A &amp; B &lt;script&gt; assumed command' in html


def test_html_without_intro_keeps_navigation_audit_welcome(mc_config):
    """Formatter stays compatible with alerts that pass no intro_paragraphs."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.formatters.html_formatter import HTMLFormatter

    df = pd.DataFrame({'surname': ['smith'], 'full_name': ['John Smith']})
    html = HTMLFormatter().format(df, datetime.now(tz=ZoneInfo('UTC')), mc_config, {'display_columns': ['full_name']})
    assert 'Dear Captain Smith,' in html
    assert 'Welcome onboard' in html


def test_text_contains_intro_and_numbers_records_from_one(alert, mc_config):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.formatters.text_formatter import TextFormatter

    data = alert.filter_data(make_df(raw_row()))
    data.index = [7]  # e.g. after tracker filtering
    job = alert.route_notifications(data)[0]
    text = TextFormatter().format(job['data'], datetime.now(tz=ZoneInfo('UTC')), mc_config, job['metadata'])

    assert 'Dear ICT,' in text
    assert 'Captain John Smith assumed command of PROM STAR' in text
    assert 'Record 1:' in text
    assert 'Record 8:' not in text
    assert text.index('Dear ICT,') < text.index('Found 1 record(s):')


    # ---------------------------------------------------------------------------
    # Crew list link
    # ---------------------------------------------------------------------------

def test_crew_list_url_filters_on_vessel(alert):
    from urllib.parse import urlparse, parse_qs

    url = urlparse(alert._crew_list_url(11))
    assert url.path == '/crew-list'
    assert parse_qs(url.query) == {
        'filters[0][name]': ['onboard_vessel_id'],
        'filters[0][operation]': ['='],
        'filters[0][value]': ['11'],
    }


def test_html_intro_contains_crew_list_link(alert, mc_config):
    import re
    from datetime import datetime
    from html import unescape
    from zoneinfo import ZoneInfo
    from src.formatters.html_formatter import HTMLFormatter

    job = alert.route_notifications(alert.filter_data(make_df(raw_row())))[0]
    html = HTMLFormatter().format(job['data'], datetime.now(tz=ZoneInfo('UTC')), mc_config, job['metadata'])

    links = re.findall(r'<a href="([^"]+)"[^>]*>crew list</a>', html)
    assert len(links) == 1
    assert unescape(links[0]) == alert._crew_list_url(11)
    assert '&lt;a' not in html


def test_text_intro_shows_crew_list_url(alert, mc_config):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.formatters.text_formatter import TextFormatter

    job = alert.route_notifications(alert.filter_data(make_df(raw_row())))[0]
    text = TextFormatter().format(job['data'], datetime.now(tz=ZoneInfo('UTC')), mc_config, job['metadata'])

    assert f"Navigate to the crew list ({alert._crew_list_url(11)}) page." in text
    assert '<a ' not in text


# ---------------------------------------------------------------------------
# Company logo
# ---------------------------------------------------------------------------

@pytest.fixture
def logo_files(mc_config):
    """Create the configured logo files so the formatter and sender find them."""
    for path in mc_config.company_logos.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 16)
    return mc_config.company_logos


@pytest.mark.parametrize('vsl_email, expected', [
    ('vessel@prominencemaritime.com', ['prominence']),
    ('vessel@vsl.seatraders.com', ['seatraders']),
])
def test_route_sets_company_logo(alert, vsl_email, expected):
    job = alert.route_notifications(alert.filter_data(make_df(raw_row(vsl_email=vsl_email))))[0]
    assert job['metadata']['logo_keys'] == expected


@pytest.mark.parametrize('vsl_email, shown, hidden', [
    ('vessel@prominencemaritime.com', 'prominence', 'seatraders'),
    ('vessel@seatraders.com', 'seatraders', 'prominence'),
])
def test_html_shows_only_company_logo(alert, mc_config, logo_files, vsl_email, shown, hidden):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.formatters.html_formatter import HTMLFormatter

    job = alert.route_notifications(alert.filter_data(make_df(raw_row(vsl_email=vsl_email))))[0]
    html = HTMLFormatter().format(job['data'], datetime.now(tz=ZoneInfo('UTC')), mc_config, job['metadata'])
    assert f'cid:{shown}_logo' in html
    assert f'cid:{hidden}_logo' not in html


def test_html_without_logo_keys_shows_all_logos(mc_config, logo_files):
    """Formatter stays compatible with alerts that pass no logo_keys."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.formatters.html_formatter import HTMLFormatter

    df = pd.DataFrame({'full_name': ['John Smith']})
    html = HTMLFormatter().format(df, datetime.now(tz=ZoneInfo('UTC')), mc_config, {'display_columns': ['full_name']})
    assert 'cid:prominence_logo' in html
    assert 'cid:seatraders_logo' in html


@pytest.mark.parametrize('logo_keys, expected_cids', [
    (['seatraders'], ['<seatraders_logo>']),
    (None, ['<prominence_logo>', '<seatraders_logo>']),
])
def test_email_sender_embeds_selected_logos(logo_files, monkeypatch, logo_keys, expected_cids):
    from unittest.mock import MagicMock
    from src.notifications.email_sender import EmailSender

    smtp = MagicMock()
    monkeypatch.setattr('src.notifications.email_sender.smtplib.SMTP_SSL', MagicMock(return_value=smtp))
    sender = EmailSender('smtp.test.com', 465, 'a@test.com', 'x', company_logos=logo_files)

    sender.send('Subject', 'text', '<p>html</p>', ['to@test.com'], logo_keys=logo_keys)

    msg = smtp.__enter__.return_value.send_message.call_args.args[0]
    cids = sorted(part['Content-ID'] for part in msg.walk() if part['Content-ID'])
    assert cids == expected_cids


# ---------------------------------------------------------------------------
# End-to-end run (database and SMTP mocked)
# ---------------------------------------------------------------------------

def test_run_sends_once_and_tracks(alert, mc_config, mock_event_tracker, mock_email_sender, monkeypatch):
    wire_runtime(mc_config, mock_event_tracker, mock_email_sender)
    monkeypatch.setattr(alert, 'fetch_data', lambda: make_df(raw_row()))
    monkeypatch.setattr(alert, '_write_health_status', lambda *args, **kwargs: None)

    assert alert.run() is True
    mock_email_sender.send.assert_called_once()
    sent = mock_email_sender.send.call_args.kwargs
    assert sent['recipients'] == ['ict@prominencemaritime.com']
    assert sent['cc_recipients'] == ['prom1@test.com', 'prom2@test.com', 'internal@test.com']
    assert sent['subject'] == 'AlertDev | PROM STAR Master Change'
    assert 'Captain John Smith assumed command of PROM STAR' in sent['plain_text']
    assert sent['logo_keys'] == ['prominence']
    assert mock_event_tracker.is_sent('master_change__crew_contract_id_50001__crew_member_id_301')

    # Second run: already tracked, nothing sent
    assert alert.run() is False
    assert mock_email_sender.send.call_count == 1


def test_run_dry_run_email_redirects(alert, mc_config, mock_event_tracker, mock_email_sender, monkeypatch):
    wire_runtime(mc_config, mock_event_tracker, mock_email_sender)
    mc_config.dry_run = True
    mc_config.dry_run_email = 'tester@test.com'
    monkeypatch.setattr(alert, 'fetch_data', lambda: make_df(raw_row()))
    monkeypatch.setattr(alert, '_write_health_status', lambda *args, **kwargs: None)

    assert alert.run() is True
    sent = mock_email_sender.send.call_args.kwargs
    assert sent['recipients'] == ['tester@test.com']
    assert sent['cc_recipients'] == []
    assert sent['subject'] == (
        '[DRY-RUN] AlertDev | PROM STAR Master Change (Original: ict@prominencemaritime.com)'
    )


def test_run_with_no_routable_changes_sends_nothing(alert, mc_config, mock_event_tracker, mock_email_sender, monkeypatch):
    wire_runtime(mc_config, mock_event_tracker, mock_email_sender)
    monkeypatch.setattr(alert, 'fetch_data', lambda: make_df(raw_row(vsl_email=None)))
    monkeypatch.setattr(alert, '_write_health_status', lambda *args, **kwargs: None)

    assert alert.run() is False
    mock_email_sender.send.assert_not_called()
    assert mock_event_tracker.sent_events == {}
