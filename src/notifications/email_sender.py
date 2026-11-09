#src/notifications/email_sender.py
"""
Email notification handler with company-specific routing.

Handles SMTP connection, email composition with HTML/text alternatives,
and embedded logo attachments.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from typing import List, Optional, Dict
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class EmailSender:
    """
    Handles email sending with SMTP and company-specific routing.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_pass: str,
        company_logos: Dict[str, Path],
        dry_run: bool = False
    ):
        """
        Initialize email sender.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port (465 for SSL, 587 for STARTTLS)
            smtp_user: SMTP username (usually email address)
            smtp_pass: SMTP password
            company_logos: Dict mapping company name to logo file path
            dry_run: If True, will not actually send emails (safety check)
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.company_logos = company_logos
        self.dry_run = dry_run

    def send(
        self,
        subject: str,
        plain_text: str,
        html_content: str,
        recipients: List[str],
        cc_recipients: Optional[List[str]] = None
    ) -> None:
        """
        Send email with both plain text and HTML versions.

        Args:
            subject: Email subject line
            plain_text: Plain text version of email body
            html_content: HTML version of email body
            recipients: List of primary recipient email addresses
            cc_recipients: Optional list of CC recipient email addresses

        Raises:
            ValueError: If no recipients provided
            RuntimeError: If called in dry-run mode
            smtplib.SMTPException: If email sending fails
        """
        # SAFETY CHECK: Prevent accidental sends in dry-run mode
        if self.dry_run:
            raise RuntimeError(
                "[XXX] SAFETY CHECK FAILED: EmailSender.send() called in dry-run mode! "
                "This should never happen. Emails will NOT be sent."
            )

        if not recipients:
            raise ValueError("No recipients provided")

        if cc_recipients is None:
            cc_recipients = []

        # Create multipart message
        msg = MIMEMultipart('related')
        msg['Subject'] = subject
        msg['From'] = self.smtp_user
        msg['To'] = ', '.join(recipients)
        if cc_recipients:
            msg['Cc'] = ', '.join(cc_recipients)

        # Create alternative part for text and HTML
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)

        # Attach plain text version
        part_text = MIMEText(plain_text, 'plain', 'utf-8')
        msg_alternative.attach(part_text)

        # Attach HTML version
        part_html = MIMEText(html_content, 'html', 'utf-8')
        msg_alternative.attach(part_html)

        # Attach company logos as embedded images
        for company_name, logo_path in self.company_logos.items():
            logo_data, mime_type, filename = self._load_logo(logo_path)
            if logo_data:
                maintype, subtype = mime_type.split('/')
                img = MIMEImage(logo_data, _subtype=subtype)
                # CID format: <company_name>_logo
                cid = f"{company_name}_logo"
                img.add_header('Content-ID', f'<{cid}>')
                img.add_header('Content-Disposition', 'inline', filename=filename)
                msg.attach(img)

        # Send email
        try:
            if self.smtp_port == 465:
                # SSL connection
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30) as smtp:
                    smtp.login(self.smtp_user, self.smtp_pass)
                    smtp.send_message(msg)
            else:
                # STARTTLS connection (ports 587/25)
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as smtp:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.ehlo()
                    smtp.login(self.smtp_user, self.smtp_pass)
                    smtp.send_message(msg)

            total_recipients = len(recipients) + len(cc_recipients)
            cc_info = f" (including {len(cc_recipients)} CC)" if cc_recipients else ""
            logger.info(
                f"[OK] Email sent successfully to {total_recipients} recipient(s){cc_info}: "
                f"To: {', '.join(recipients)}"
                f"{f' | CC: {', '.join(cc_recipients)}' if cc_recipients else ''}"
            )

        except Exception as e:
            logger.exception(f"[EXC] Failed to send email: {e}")
            raise

    def _load_logo(self, logo_path: Path) -> tuple:
        """
        Load logo file for email attachment.

        Args:
            logo_path: Path to logo file

        Returns:
            Tuple of (file_data, mime_type, filename) or (None, None, None) if not found
        """
        if not logo_path.exists():
            logger.warning(f"Logo not found at: {logo_path}")
            return None, None, None

        try:
            with open(logo_path, 'rb') as f:
                logo_data = f.read()

            # Determine MIME type from extension
            ext = logo_path.suffix.lower()
            mime_types = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.svg': 'image/svg+xml'
            }
            mime_type = mime_types.get(ext, 'image/png')

            return logo_data, mime_type, logo_path.name

        except Exception as e:
            logger.error(f"Failed to load logo from {logo_path}: {e}")
            return None, None, None
