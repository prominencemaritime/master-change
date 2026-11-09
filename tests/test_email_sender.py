# tests/test_email_sender.py
"""
Tests for email sending functionality.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import smtplib
from src.notifications.email_sender import EmailSender


def test_email_sender_initializes_correctly():
    """Test that EmailSender initializes with correct parameters."""
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    assert sender.smtp_host == 'smtp.test.com'
    assert sender.smtp_port == 465
    assert sender.smtp_user == 'test@test.com'
    assert sender.smtp_pass == 'password'
    assert sender.company_logos == {}
    assert sender.dry_run is False


def test_email_sender_initializes_with_logos():
    """Test that EmailSender initializes with company logos."""
    logos = {
        'Prominence': Path('/path/to/prominence.png'),
        'Seatraders': Path('/path/to/seatraders.png')
    }
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos=logos,
        dry_run=False
    )
    
    assert sender.company_logos == logos
    assert len(sender.company_logos) == 2


def test_email_sender_blocks_in_dry_run_mode():
    """Test that EmailSender blocks sends in dry-run mode."""
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=True
    )
    
    with pytest.raises(RuntimeError, match="SAFETY CHECK FAILED"):
        sender.send(
            subject='Test',
            plain_text='Test',
            html_content='<html>Test</html>',
            recipients=['test@test.com']
        )


def test_email_sender_raises_on_no_recipients():
    """Test that EmailSender raises error when no recipients provided."""
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    with pytest.raises(ValueError, match="No recipients provided"):
        sender.send(
            subject='Test',
            plain_text='Test',
            html_content='<html>Test</html>',
            recipients=[]
        )


def test_email_sender_raises_on_empty_recipients_list():
    """Test that EmailSender raises error when recipients list is empty."""
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    with pytest.raises(ValueError, match="No recipients provided"):
        sender.send(
            subject='Test',
            plain_text='Test',
            html_content='<html>Test</html>',
            recipients=[],
            cc_recipients=['cc@test.com']
        )


@patch('smtplib.SMTP_SSL')
def test_email_sender_sends_successfully(mock_smtp):
    """Test that EmailSender sends email successfully via SSL."""
    # Mock SMTP server
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    sender.send(
        subject='Test Subject',
        plain_text='Test Body',
        html_content='<html>Test</html>',
        recipients=['recipient@test.com'],
        cc_recipients=['cc@test.com']
    )
    
    # Verify SMTP methods were called
    mock_smtp.assert_called_once_with('smtp.test.com', 465, timeout=30)
    mock_server.login.assert_called_once_with('test@test.com', 'password')
    mock_server.send_message.assert_called_once()


@patch('smtplib.SMTP')
def test_email_sender_sends_via_starttls(mock_smtp):
    """Test that EmailSender sends email successfully via STARTTLS (port 587)."""
    # Mock SMTP server
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=587,  # STARTTLS port
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    sender.send(
        subject='Test Subject',
        plain_text='Test Body',
        html_content='<html>Test</html>',
        recipients=['recipient@test.com']
    )
    
    # Verify SMTP methods were called
    mock_smtp.assert_called_once_with('smtp.test.com', 587, timeout=30)
    assert mock_server.ehlo.call_count == 2  # Called before and after STARTTLS
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with('test@test.com', 'password')
    mock_server.send_message.assert_called_once()


@patch('smtplib.SMTP')
def test_email_sender_sends_via_port_25(mock_smtp):
    """Test that EmailSender sends email via port 25 (standard SMTP)."""
    # Mock SMTP server
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=25,  # Standard SMTP port
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    sender.send(
        subject='Test Subject',
        plain_text='Test Body',
        html_content='<html>Test</html>',
        recipients=['recipient@test.com']
    )
    
    # Verify SMTP methods were called
    mock_smtp.assert_called_once_with('smtp.test.com', 25, timeout=30)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once()
    mock_server.send_message.assert_called_once()


@patch('smtplib.SMTP_SSL')
def test_email_sender_includes_cc_recipients(mock_smtp):
    """Test that CC recipients are included in email."""
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    sender.send(
        subject='Test',
        plain_text='Test',
        html_content='<html>Test</html>',
        recipients=['to@test.com'],
        cc_recipients=['cc1@test.com', 'cc2@test.com']
    )
    
    # Get the message that was sent
    call_args = mock_server.send_message.call_args
    msg = call_args[0][0]
    
    assert 'cc1@test.com' in msg['Cc']
    assert 'cc2@test.com' in msg['Cc']


@patch('smtplib.SMTP_SSL')
def test_email_sender_works_without_cc_recipients(mock_smtp):
    """Test that email can be sent without CC recipients."""
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    sender.send(
        subject='Test',
        plain_text='Test',
        html_content='<html>Test</html>',
        recipients=['to@test.com']
        # No cc_recipients
    )
    
    # Get the message that was sent
    call_args = mock_server.send_message.call_args
    msg = call_args[0][0]
    
    # CC header should not exist or be empty
    assert msg.get('Cc') is None or msg['Cc'] == ''


@patch('smtplib.SMTP_SSL')
def test_email_sender_includes_multiple_recipients(mock_smtp):
    """Test that multiple TO recipients are included."""
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    sender.send(
        subject='Test',
        plain_text='Test',
        html_content='<html>Test</html>',
        recipients=['to1@test.com', 'to2@test.com', 'to3@test.com']
    )
    
    # Get the message that was sent
    call_args = mock_server.send_message.call_args
    msg = call_args[0][0]
    
    assert 'to1@test.com' in msg['To']
    assert 'to2@test.com' in msg['To']
    assert 'to3@test.com' in msg['To']


@patch('smtplib.SMTP_SSL')
def test_email_sender_sets_correct_headers(mock_smtp):
    """Test that email headers are set correctly."""
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='sender@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    sender.send(
        subject='Test Subject Line',
        plain_text='Test',
        html_content='<html>Test</html>',
        recipients=['to@test.com']
    )
    
    # Get the message that was sent
    call_args = mock_server.send_message.call_args
    msg = call_args[0][0]
    
    assert msg['Subject'] == 'Test Subject Line'
    assert msg['From'] == 'sender@test.com'
    assert msg['To'] == 'to@test.com'


@patch('smtplib.SMTP_SSL')
def test_email_sender_handles_smtp_exception(mock_smtp):
    """Test that EmailSender properly raises SMTP exceptions."""
    mock_server = MagicMock()
    mock_server.send_message.side_effect = smtplib.SMTPException("SMTP error")
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    with pytest.raises(smtplib.SMTPException):
        sender.send(
            subject='Test',
            plain_text='Test',
            html_content='<html>Test</html>',
            recipients=['to@test.com']
        )


@patch('smtplib.SMTP_SSL')
def test_email_sender_handles_login_failure(mock_smtp):
    """Test that EmailSender handles login failures."""
    mock_server = MagicMock()
    mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, 'Authentication failed')
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='wrong_password',
        company_logos={},
        dry_run=False
    )
    
    with pytest.raises(smtplib.SMTPAuthenticationError):
        sender.send(
            subject='Test',
            plain_text='Test',
            html_content='<html>Test</html>',
            recipients=['to@test.com']
        )


@patch('smtplib.SMTP')
def test_email_sender_handles_starttls_failure(mock_smtp):
    """Test that EmailSender handles STARTTLS failures."""
    mock_server = MagicMock()
    mock_server.starttls.side_effect = smtplib.SMTPException("STARTTLS failed")
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=587,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    with pytest.raises(smtplib.SMTPException):
        sender.send(
            subject='Test',
            plain_text='Test',
            html_content='<html>Test</html>',
            recipients=['to@test.com']
        )


def test_load_logo_returns_none_for_missing_file(tmp_path):
    """Test that _load_logo returns None for missing file."""
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    missing_file = tmp_path / "missing_logo.png"
    
    data, mime_type, filename = sender._load_logo(missing_file)
    
    assert data is None
    assert mime_type is None
    assert filename is None


def test_load_logo_loads_png_correctly(tmp_path):
    """Test that _load_logo loads PNG file correctly."""
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    # Create a fake PNG file
    logo_file = tmp_path / "logo.png"
    logo_file.write_bytes(b'\x89PNG\r\n\x1a\n')  # PNG header
    
    data, mime_type, filename = sender._load_logo(logo_file)
    
    assert data == b'\x89PNG\r\n\x1a\n'
    assert mime_type == 'image/png'
    assert filename == 'logo.png'


def test_load_logo_loads_jpg_correctly(tmp_path):
    """Test that _load_logo loads JPG file correctly."""
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    # Create a fake JPG file
    logo_file = tmp_path / "logo.jpg"
    logo_file.write_bytes(b'\xFF\xD8\xFF')  # JPEG header
    
    data, mime_type, filename = sender._load_logo(logo_file)
    
    assert data == b'\xFF\xD8\xFF'
    assert mime_type == 'image/jpeg'
    assert filename == 'logo.jpg'


def test_load_logo_loads_jpeg_correctly(tmp_path):
    """Test that _load_logo loads JPEG file correctly."""
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    # Create a fake JPEG file
    logo_file = tmp_path / "logo.jpeg"
    logo_file.write_bytes(b'\xFF\xD8\xFF')
    
    data, mime_type, filename = sender._load_logo(logo_file)
    
    assert mime_type == 'image/jpeg'


def test_load_logo_loads_gif_correctly(tmp_path):
    """Test that _load_logo loads GIF file correctly."""
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    # Create a fake GIF file
    logo_file = tmp_path / "logo.gif"
    logo_file.write_bytes(b'GIF89a')
    
    data, mime_type, filename = sender._load_logo(logo_file)
    
    assert mime_type == 'image/gif'


def test_load_logo_loads_svg_correctly(tmp_path):
    """Test that _load_logo loads SVG file correctly."""
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    # Create a fake SVG file
    logo_file = tmp_path / "logo.svg"
    logo_file.write_text('<svg></svg>')
    
    data, mime_type, filename = sender._load_logo(logo_file)
    
    assert mime_type == 'image/svg+xml'


def test_load_logo_defaults_to_png_for_unknown_extension(tmp_path):
    """Test that _load_logo defaults to PNG for unknown extensions."""
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    # Create a file with unknown extension
    logo_file = tmp_path / "logo.xyz"
    logo_file.write_bytes(b'some data')
    
    data, mime_type, filename = sender._load_logo(logo_file)
    
    assert mime_type == 'image/png'  # Default


def test_load_logo_handles_read_error(tmp_path):
    """Test that _load_logo handles file read errors."""
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    # Create a file then make it unreadable by patching open
    logo_file = tmp_path / "logo.png"
    logo_file.write_bytes(b'data')
    
    with patch('builtins.open', side_effect=IOError("Read error")):
        data, mime_type, filename = sender._load_logo(logo_file)
    
    assert data is None
    assert mime_type is None
    assert filename is None


@patch('smtplib.SMTP_SSL')
def test_email_sender_attaches_logos(mock_smtp, tmp_path):
    """Test that logos are attached to emails."""
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    # Create logo files
    prominence_logo = tmp_path / "prominence.png"
    prominence_logo.write_bytes(b'\x89PNG\r\n\x1a\n')
    
    seatraders_logo = tmp_path / "seatraders.jpg"
    seatraders_logo.write_bytes(b'\xFF\xD8\xFF')
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={
            'Prominence': prominence_logo,
            'Seatraders': seatraders_logo
        },
        dry_run=False
    )
    
    sender.send(
        subject='Test',
        plain_text='Test',
        html_content='<html>Test</html>',
        recipients=['to@test.com']
    )
    
    # Get the message that was sent
    call_args = mock_server.send_message.call_args
    msg = call_args[0][0]
    
    # Check that message has attachments
    assert mock_server.send_message.called
    # The message should be multipart with logos attached
    assert len(msg.get_payload()) > 1  # More than just the alternative part


@patch('smtplib.SMTP_SSL')
def test_email_sender_skips_missing_logos(mock_smtp, tmp_path):
    """Test that missing logos are skipped without error."""
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    # Create one logo but not the other
    existing_logo = tmp_path / "existing.png"
    existing_logo.write_bytes(b'\x89PNG\r\n\x1a\n')
    
    missing_logo = tmp_path / "missing.png"  # Don't create this
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={
            'ExistingCompany': existing_logo,
            'MissingCompany': missing_logo
        },
        dry_run=False
    )
    
    # Should not raise exception
    sender.send(
        subject='Test',
        plain_text='Test',
        html_content='<html>Test</html>',
        recipients=['to@test.com']
    )
    
    assert mock_server.send_message.called


@patch('smtplib.SMTP_SSL')
def test_email_sender_handles_general_exception(mock_smtp):
    """Test that EmailSender handles general exceptions."""
    mock_server = MagicMock()
    mock_server.send_message.side_effect = Exception("Unexpected error")
    mock_smtp.return_value.__enter__.return_value = mock_server
    
    sender = EmailSender(
        smtp_host='smtp.test.com',
        smtp_port=465,
        smtp_user='test@test.com',
        smtp_pass='password',
        company_logos={},
        dry_run=False
    )
    
    with pytest.raises(Exception, match="Unexpected error"):
        sender.send(
            subject='Test',
            plain_text='Test',
            html_content='<html>Test</html>',
            recipients=['to@test.com']
        )
