# utils/email_utils.py
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

def send_email(to_email, subject, body_html):
    from_email = "daydreamforgephyton.ai@gmail.com"  # Replace with your sender address if needed

    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    plain_text = "Your email client does not support HTML emails. Please view this message in a modern client."

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(from_email, EMAIL_APP_PASSWORD)
            server.send_message(msg)
            logging.info("✅ Email sent successfully.")
    except Exception as e:
        logging.error(f"❌ Failed to send email: {e}")
