import os
import smtplib
from email.message import EmailMessage

def send_email(email, title, link):
    msg = EmailMessage()
    msg['From'] = os.getenv('SMTP_FROM_EMAIL', 'noreply@gnkalgo.local')
    msg['To'] = email
    msg['Subject'] = 'GNK ALGO — ' + title
    msg.set_content(f'{title}\n{link}\nIf you did not request this, ignore this email.')
    msg.add_alternative(f'<div style="font-family:Arial;background:#0a1020;color:#fff;padding:40px"><h1>GNK ALGO</h1><h2>{title}</h2><p>Intelligence Behind Every Trade.</p><a style="color:#4ee0ce" href="{link}">Continue securely</a></div>', subtype='html')
    with smtplib.SMTP(os.getenv('SMTP_HOST', 'mailpit'), int(os.getenv('SMTP_PORT', '1025')), timeout=10) as smtp:
        if os.getenv('SMTP_USE_TLS') == 'true':
            smtp.starttls()
        if os.getenv('SMTP_USERNAME'):
            smtp.login(os.environ['SMTP_USERNAME'], os.environ['SMTP_PASSWORD'])
        smtp.send_message(msg)
