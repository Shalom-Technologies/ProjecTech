import httpx
from app.config import settings


class PaystackClient:
    def __init__(self):
        self.base_url = settings.PAYSTACK_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

    async def initialize_transaction(self, email: str, amount_kobo: int, metadata: dict, callback_url: str = None) -> dict:
        payload = {"email": email, "amount": amount_kobo, "metadata": metadata}
        if callback_url:
            payload["callback_url"] = callback_url

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/transaction/initialize",
                headers=self.headers,
                json={"email": email, "amount": amount_kobo, "metadata": metadata},
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

    async def resolve_account(self, account_number: str, bank_code: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/bank/resolve",
                headers=self.headers,
                params={"account_number": account_number, "bank_code": bank_code},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    async def create_transfer_recipient(self, name: str, account_number: str, bank_code: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/transferrecipient",
                headers=self.headers,
                json={
                    "type": "nuban",
                    "name": name,
                    "account_number": account_number,
                    "bank_code": bank_code,
                    "currency": "NGN",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    async def initiate_transfer(self, amount_kobo: int, recipient_code: str, reason: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/transfer",
                headers=self.headers,
                json={
                    "source": "balance",
                    "amount": amount_kobo,
                    "recipient": recipient_code,
                    "reason": reason,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()


paystack = PaystackClient()