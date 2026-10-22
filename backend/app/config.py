from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    MONGODB_URL: str
    DATABASE_NAME: str = "marketplace_db"
    # Comma separated list of the websites allowed to call this API from a browser,
    # for example "https://projectech.dev,https://www.projectech.dev". Defaults to local development only.
    CORS_ORIGINS: str = "http://localhost:5173"

    # Signs every login token. No default on purpose: the app refuses to start without a
    # strong one, because an empty or guessable key lets anyone forge a login as any user.
    # Generate one with:  openssl rand -hex 32
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"

    # The single currency the platform trades in (Kenya).
    CURRENCY: str = "KES"

    # Sanity limits for any invoiced amount (in CURRENCY), to catch typos.
    MIN_PAYMENT_AMOUNT: float = 100.0
    MAX_PAYMENT_AMOUNT: float = 5_000_000.0

    # Refund policy: days the client has to review delivered work (money is held,
    # and released automatically at the end unless a problem is reported), and days
    # released earnings wait before they can be withdrawn (protects against card chargebacks).
    REVIEW_WINDOW_DAYS: int = 7
    PAYOUT_HOLD_DAYS: int = 7

    # How often the background job releases due deliveries and matured payout holds.
    BACKGROUND_JOB_INTERVAL_SECONDS: int = 900

    DEVELOPER_COMMISSION: float = 0.45
    SALESPERSON_COMMISSION: float = 0.35
    PLATFORM_COMMISSION: float = 0.20

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = ""
    # Where the website lives. Used in emails, invoice links and the Paystack return page.
    FRONTEND_URL: str = "http://localhost:5173"
    # Who hears about things only a person can fix: problem reports, payments to refund, refunds
    # that failed, emails that could not be sent. Leave empty to only write them to the logs.
    ADMIN_EMAIL: str = ""
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, value: str) -> str:
        if len(value) < 32 or len(set(value)) < 8:
            raise ValueError(
                "SECRET_KEY must be a random string of at least 32 characters. "
                "Generate one with: openssl rand -hex 32"
            )
        return value

    @field_validator("FRONTEND_URL")
    @classmethod
    def frontend_url_without_trailing_slash(cls, value: str) -> str:
        # Links are built as f"{FRONTEND_URL}/path", so a trailing slash would double up.
        return value.strip().rstrip("/")

    @field_validator("CORS_ORIGINS")
    @classmethod
    def cors_origins_clean(cls, value: str) -> str:
        # Browsers send origins without a trailing slash, so "https://x.dev/" would never match.
        origins = [o.strip().rstrip("/") for o in value.split(",") if o.strip()]
        if not origins or "*" in origins:
            raise ValueError("CORS_ORIGINS must list the real website address(es), not be empty or '*'")
        return ",".join(origins)

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()