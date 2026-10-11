import os
import smtplib
from email.message import EmailMessage


def send_email(subject: str, text: str, html: str, attachment_html: str) -> bool:
    user, password, to = (os.environ.get(k) for k in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "MAIL_TO"))
    if not (user and password and to):
        print("email not configured; subject would be:", subject)
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    msg.add_attachment(attachment_html.encode(), maintype="text", subtype="html", filename="report.html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, password)
        s.send_message(msg)
    return True
