import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from html import escape
import logging
from app.config import settings

logger = logging.getLogger(__name__)

BUTTON_STYLE = (
    "background: #4f46e5; color: white; padding: 12px 24px; "
    "text-decoration: none; border-radius: 8px; display: inline-block;"
)


async def _send(to_email: str, subject: str, html_content: str, kind: str, reply_to: str | None = None):
    """Sends one HTML email. Raises if the provider rejects it, so callers can react."""
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email
    if reply_to:
        message["Reply-To"] = reply_to
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
        logger.info(f"{kind} email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send {kind} email to {to_email}: {e}")
        raise


async def send_password_reset_email(to_email: str, reset_link: str, first_name: str):
    html = f"""
        <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
            <h2>Hi {escape(first_name)},</h2>
            <p>We received a request to reset your password. Click the button below to choose a new one:</p>
            <p style="margin: 24px 0;">
                <a href="{escape(reset_link, quote=True)}" style="{BUTTON_STYLE}">Reset Password</a>
            </p>
            <p>This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.</p>
            <p>If you didn't request this, you can safely ignore this email.</p>
        </div>
    """
    await _send(to_email, "Reset your password", html, "Password reset")


async def send_verification_email(to_email: str, verify_link: str, first_name: str, is_welcome: bool = True):
    intro = (
        "Welcome to ProjecTech! Please confirm your email address so you can apply for projects, "
        "post projects, make payments and withdraw your earnings."
        if is_welcome
        else "Please confirm your email address so you can apply for projects, post projects, "
             "make payments and withdraw your earnings."
    )
    html = f"""
        <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
            <h2>Hi {escape(first_name)},</h2>
            <p>{intro}</p>
            <p style="margin: 24px 0;">
                <a href="{escape(verify_link, quote=True)}" style="{BUTTON_STYLE}">Confirm my email</a>
            </p>
            <p>This link expires in 24 hours. You can ask for a new one from your dashboard.</p>
            <p>If you didn't create a ProjecTech account, you can safely ignore this email.</p>
        </div>
    """
    await _send(to_email, "Welcome to ProjecTech: confirm your email" if is_welcome else "Confirm your email", html, "Verification")


async def send_review_started_email(to_email: str, project_title: str, invoice_url: str, review_deadline):
    """Tell the client that work has been delivered and how to accept it or report a problem."""
    deadline = f"{review_deadline:%d %b %Y}"
    html = f"""
        <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
            <h2>Your project was delivered</h2>
            <p>The work for <strong>{escape(project_title)}</strong> has been marked delivered.</p>
            <p>You have until <strong>{deadline}</strong> to review it. Open the link below to accept it,
               or to report a problem. If you report a problem, the payment is not released until
               ProjecTech has looked into it.</p>
            <p style="margin: 24px 0;">
                <a href="{escape(invoice_url, quote=True)}" style="{BUTTON_STYLE}">Review the delivery</a>
            </p>
            <p>If you do nothing, the payment is released to the team on {deadline}.</p>
        </div>
    """
    await _send(to_email, f"Your project was delivered: {project_title}", html, "Review")


async def send_admin_alert_email(to_email: str, subject: str, lines: list[str]):
    items = "".join(f"<li style='margin-bottom: 8px;'>{escape(line)}</li>" for line in lines)
    html = f"""
        <div style="font-family: sans-serif; max-width: 560px; margin: 0 auto;">
            <h2>ProjecTech needs your attention</h2>
            <ul>{items}</ul>
            <p>Run <code>python -m scripts.resolve_dispute</code> on the server to see the details and act on them.</p>
        </div>
    """
    await _send(to_email, subject, html, "Admin alert")


async def send_support_email(to_email: str, reply_to: str, name: str, topic: str, message: str, details: list[str]):
    """A support request, sent to the admin. Replying to it goes straight to the person who wrote."""
    # A header must be one line, so nothing a visitor typed can add headers of its own.
    clean = lambda text: " ".join(text.split())
    body = escape(message).replace("\n", "<br>")
    meta = "".join(f"<li>{escape(line)}</li>" for line in details)
    html = f"""
        <div style="font-family: sans-serif; max-width: 560px; margin: 0 auto;">
            <h2>{escape(clean(topic))}</h2>
            <p>From {escape(clean(name))} ({escape(clean(reply_to))}). Reply to this email to answer them.</p>
            <div style="border-left: 3px solid #ccc; padding-left: 12px; margin: 16px 0;">{body}</div>
            <ul style="color: #666; font-size: 13px;">{meta}</ul>
        </div>
    """
    await _send(
        to_email, f"[ProjecTech support] {clean(topic)}: {clean(name)}"[:200], html, "Support request",
        reply_to=clean(reply_to),
    )
