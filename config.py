"""
Configuration settings for DoctorLink.
"""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from typing import List
from dotenv import load_dotenv
import os

# Load .env before initializing settings
load_dotenv()

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv("SUPABASE_DATABASE_URL", "sqlite:///./doctorlink.db")

    # Base URL for redirects and callbacks
    BASE_URL: str = "http://localhost:8000"

    # Security
    SECRET_KEY: str = "doctorlink-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # Filebase S3
    FILEBASE_ACCESS_KEY: str = ""
    FILEBASE_SECRET_KEY: str = ""
    FILEBASE_BUCKET: str = "skyhealth"
    FILEBASE_ENDPOINT: str = "https://s3.filebase.com"

    # Somnia Agentic L1
    SOMNIA_RPC_URL: str = "https://api.infra.testnet.somnia.network"
    SOMNIA_CHAIN_ID: int = 50312
    SOMNIA_CURRENCY: str = "STT"
    SOMNIA_PLATFORM_CONTRACT: str = "0x037Bb9C718F3f7fe5eCBDB0b600D607b52706776"
    SOMNIA_ESCROW_CONTRACT: str = ""
    SOMNIA_PRIVATE_KEY: str = ""
    SOMNIA_SPONSOR_CONTRACT: str = ""
    SOMNIA_GAS_LIMIT: int = 500000

    # T-800 Token
    T800_CONTRACT_ADDRESS: str = ""
    ROUTER_CONTRACT_ADDRESS: str = ""
    DEX_CONTRACT_ADDRESS: str = ""
    TOKEN_VESTING_CONTRACT: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # PayFast Configuration
    PAYFAST_MERCHANT_ID: str = ""  # Add your PayFast merchant ID
    PAYFAST_PASS_PHRASE: str = ""  # Add your PayFast passphrase
    PAYFAST_MODE: str = "sandbox"  # sandbox or live
    
    @property
    def PAYFAST_RETURN_URL(self) -> str:
        return f"{self.BASE_URL}/api/payments/return"
    
    @property
    def PAYFAST_CANCEL_URL(self) -> str:
        return f"{self.BASE_URL}/api/payments/cancel"
    
    @property
    def PAYFAST_NOTIFY_URL(self) -> str:
        return f"{self.BASE_URL}/api/payments/notify"

    # PayFast URLs
    PAYFAST_PAYMENT_URL: str = "https://sandbox.payfast.co.za/eng/process"
    PAYFAST_VALIDATE_URL: str = "https://sandbox.payfast.co.za/eng/query/validate"

    model_config = ConfigDict(env_file=".env", extra="allow")


settings = Settings()
