"""Deliver admin sign-in codes through an authenticated TLS SMTP connection."""
import os
import smtplib
import ssl
from email.message import EmailMessage


def send_admin_code(email: str, code: str):
    host = os.getenv('LEXITRACE_SMTP_HOST', '')
    username = os.getenv('LEXITRACE_SMTP_USERNAME', '')
    password = os.getenv('LEXITRACE_SMTP_PASSWORD', '')
    sender = os.getenv('LEXITRACE_SMTP_FROM', '') or username
    if not all((host, username, password, sender)):
        raise RuntimeError('SMTP is not configured')
    mode = os.getenv('LEXITRACE_SMTP_SECURITY', 'starttls').lower()
    if mode not in ('starttls', 'ssl'):
        raise RuntimeError('SMTP requires TLS')
    port = int(os.getenv('LEXITRACE_SMTP_PORT', '465' if mode == 'ssl' else '587'))
    message = EmailMessage()
    message['Subject'] = 'Your LexiTrace administrator verification code'
    message['From'] = sender
    message['To'] = email
    message.set_content(
        f'Your LexiTrace administrator verification code is: {code}\n\n'
        'This code expires in 10 minutes and can only be used once.\n'
        'If you did not request this code, you can ignore this email.\n'
        'Never share this code with anyone.'
    )
    context = ssl.create_default_context()
    connection = (smtplib.SMTP_SSL(host, port, timeout=15, context=context)
                  if mode == 'ssl' else smtplib.SMTP(host, port, timeout=15))
    with connection as smtp:
        if mode == 'starttls':
            smtp.starttls(context=context)
        smtp.login(username, password)
        smtp.send_message(message)
