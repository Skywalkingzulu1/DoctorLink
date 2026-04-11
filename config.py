"""
Configuration settings for DoctorLink.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./doctorlink.db"

    # Security
    SECRET_KEY: str = "doctorlink-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # PayFast Configuration
    PAYFAST_MERCHANT_ID: str = ""  # Add your PayFast merchant ID
    PAYFAST_PASS_PHRASE: str = ""  # Add your PayFast passphrase
    PAYFAST_MODE: str = "sandbox"  # sandbox or live
    PAYFAST_RETURN_URL: str = "http://localhost:8000/api/payments/return"
    PAYFAST_CANCEL_URL: str = "http://localhost:8000/api/payments/cancel"
    PAYFAST_NOTIFY_URL: str = "http://localhost:8000/api/payments/notify"

    # PayFast URLs
    PAYFAST_PAYMENT_URL: str = "https://sandbox.payfast.co.za/eng/process"
    PAYFAST_VALIDATE_URL: str = "https://sandbox.payfast.co.za/eng/query/validate"

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
