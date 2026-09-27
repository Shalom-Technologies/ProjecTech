from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    MONGODB_URL: str
    DATABASE_NAME: str = "marketplace_db"
    CORS_ORIGINS: str = "https://verbose-waffle-r4r6g5j955qrh5g6x-5173.app.github.dev/"

    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"

    DEVELOPER_COMMISSION: float = 0.45
    SALESPERSON_COMMISSION: float = 0.35
    PLATFORM_COMMISSION: float = 0.20

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = ""
    FRONTEND_URL: str = "https://verbose-waffle-r4r6g5j955qrh5g6x-5173.app.github.dev/"
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"

settings = Settings()