"""The support email must not let a visitor add headers or markup, and must reply to the visitor."""
import asyncio
import os

os.environ.setdefault("MONGODB_URL", "mongodb://localhost:27017")
os.environ.setdefault("SECRET_KEY", "ci-only-secret-key-0123456789abcdef0123456789")


def test_support_email_is_safe_and_replies_to_the_visitor(monkeypatch):
    from app import email_client

    sent = []

    async def fake_send(message, **kwargs):
        sent.append(message)

    monkeypatch.setattr(email_client.aiosmtplib, "send", fake_send)

    asyncio.run(
        email_client.send_support_email(
            "admin@example.com",
            "visitor@example.com",
            "Eve\r\nBcc: spy@example.com",
            "Payments and refunds",
            "Hello <script>alert(1)</script>\nsecond line",
            ["Received today"],
        )
    )

    message = sent[0]
    assert message["Reply-To"] == "visitor@example.com"
    assert message["To"] == "admin@example.com"
    assert message["Bcc"] is None
    assert "\n" not in message["Subject"] and "\r" not in message["Subject"]
    body = message.get_payload()[0].get_payload(decode=True).decode()
    assert "<script>" not in body
    assert "&lt;script&gt;" in body
    assert "second line" in body
