import smtplib
from email.message import EmailMessage
from decouple import config

msg = EmailMessage()
msg["From"] = config("SMTP_USER")
msg["To"] = config("TEST_EMAIL_RECIPIENT", default="test@example.com")
msg["Subject"] = "Test Email"
msg.set_content("This is a test.")

SMTP_HOST=config("SMTP_HOST")
SMTP_PORT=config("SMTP_PORT", default=25, cast=int)
SMTP_USER=config("SMTP_USER")
SMTP_PASS=config("SMTP_PASS")

with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
    smtp.ehlo()
    smtp.starttls()
    smtp.ehlo()
    smtp.login(SMTP_USER, SMTP_PASS)
    smtp.send_message(msg)

print("[OK] Email sent successfully!")
