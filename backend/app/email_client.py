import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from app.config import settings

logger = logging.getLogger(__name__)


async def send_password_reset_email(to_email: str, reset_link: str, first_name: str):
    message = MIMEMultipart("alternative")
    message["Subject"] = "Reset your password"
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email

    html_content = f"""
        <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
            <h2>Hi {first_name},</h2>
            <p>We received a request to reset your password. Click the button below to choose a new one:</p>
            <p style="margin: 24px 0;">
                <a href="{reset_link}"
                   style="background: #4f46e5; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 8px; display: inline-block;">
                    Reset Password
                </a>
            </p>
            <p>This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.</p>
            <p>If you didn't request this, you can safely ignore this email.</p>
        </div>
    """

    message.attach(MIMEText(html_content, "html"))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info(f"Password reset email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send password reset email: {str(e)}")
        raise

async def send_review_started_email(to_email: str, project_title: str, invoice_url: str, review_deadline):
    """Tell the client that work has been delivered and how to accept it or report a problem."""
    from html import escape

    message = MIMEMultipart("alternative")
    message["Subject"] = f"Your project was delivered: {project_title}"
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email

    title = escape(project_title)
    link = escape(invoice_url, quote=True)
    deadline = f"{review_deadline:%d %b %Y}"

    html_content = f"""
        <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
            <h2>Your project was delivered</h2>
            <p>The work for <strong>{title}</strong> has been marked delivered.</p>
            <p>You have until <strong>{deadline}</strong> to review it. Open the link below to accept it,
               or to report a problem. If you report a problem, the payment is not released until
               ProjecTech has looked into it.</p>
            <p style="margin: 24px 0;">
                <a href="{link}"
                   style="background: #4f46e5; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 8px; display: inline-block;">
                    Review the delivery
                </a>
            </p>
            <p>If you do nothing, the payment is released to the team on {deadline}.</p>
        </div>
    """
    message.attach(MIMEText(html_content, "html"))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info(f"Review email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send review email: {str(e)}")
        raise
