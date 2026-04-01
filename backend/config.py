from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str
    postgres_db: str = "clinic"
    postgres_user: str = "clinic_user"
    postgres_password: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Claude AI
    anthropic_api_key: str
    claude_model: str = "claude-haiku-4-5-20251001"

    # Clinic
    clinic_name: str = "City Health Clinic"
    clinic_phone: str = ""
    clinic_address: str = ""
    clinic_hours: str = "Monday-Saturday 9am-7pm"
    clinic_timezone: str = "Asia/Kolkata"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    twilio_whatsapp_from: str = ""

    # Email
    resend_api_key: str = ""
    email_from: str = ""

    # Google Calendar
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    # Security
    secret_key: str = "changeme"
    allowed_origins: str = "http://localhost:3000,http://localhost:3001"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
