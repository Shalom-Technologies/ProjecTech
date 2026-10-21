import httpx
from app.config import settings


class PaystackClient:
    def __init__(self):
        self.base_url = settings.PAYSTACK_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

    async def initialize_transaction(
        self,
        email: str,
        amount_kobo: int,
        metadata: dict,
        callback_url: str = None,
        currency: str = None,
    ) -> dict:
        # "amount_kobo" is the amount in the currency's smallest unit (cents for KES).
        payload = {
            "email": email,
            "amount": amount_kobo,
            "currency": currency or settings.CURRENCY,
            "metadata": metadata,
        }
        if callback_url:
            payload["callback_url"] = callback_url

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/transaction/initialize",
                headers=self.headers,
                json=payload,
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    async def verify_transaction(self, reference: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/transaction/verify/{reference}",
                headers=self.headers,
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    async def create_mpesa_recipient(self, name: str, phone_number: str) -> dict:
        """Register an individual M-Pesa number as a payout recipient (KES)."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/transferrecipient",
                headers=self.headers,
                json={
                    "type": "mobile_money",
                    "name": name,
                    "account_number": phone_number,
                    "bank_code": "MPESA",
                    "currency": settings.CURRENCY,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    async def initiate_transfer(
        self,
        amount_kobo: int,
        recipient_code: str,
        reason: str,
        reference: str,
    ) -> dict:
        # "reference" is our own unique id for this transfer. Paystack echoes it
        # back in the transfer.* webhooks, and re-sending the same reference
        # never pays out twice.
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/transfer",
                headers=self.headers,
                json={
                    "source": "balance",
                    "amount": amount_kobo,
                    "recipient": recipient_code,
                    "reason": reason,
                    "reference": reference,
                    "currency": settings.CURRENCY,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()


paystack = PaystackClient()
