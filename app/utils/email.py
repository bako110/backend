from email.message import EmailMessage
import aiosmtplib
from app.config import settings


async def send_email_async(subject: str, email_to: str, body: str):
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = email_to
    message["Subject"] = subject
    message.set_content(body)

    await aiosmtplib.send(
        message,
        hostname=settings.mail_server,
        port=settings.mail_port,
        username=settings.mail_username,
        password=settings.mail_password,
        start_tls=True,
    )
