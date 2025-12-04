# emailer.py
import os
import ssl
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

def send_email(smtp_user, smtp_pass, to_email, subject, body_text, attachments=[]):
    """
    Send an email with a plain-text body and optional PDF attachments.
    smtp_user: SMTP username (email address)
    smtp_pass: SMTP password (app password recommended for Gmail)
    to_email: destination email (your email)
    subject: email subject
    body_text: plain-text body (can contain the text resume)
    attachments: list of file paths to attach (PDFs)
    """
    msg = EmailMessage()
    msg["From"] = formataddr(("Sandeep Sharma", smtp_user))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)

    # Attach PDFs
    for path in attachments:
        try:
            with open(path, "rb") as f:
                data = f.read()
            filename = path.split("/")[-1]
            msg.add_attachment(data, maintype="application", subtype="pdf", filename=filename)
        except Exception as e:
            print(f"Warning: could not attach {path} -> {e}")

    # Send via Gmail SMTP (SSL)
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"Email sent to {to_email} with subject: {subject}")
    except Exception as e:
        print("Error sending email:", e)
        raise
