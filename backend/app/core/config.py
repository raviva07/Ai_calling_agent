from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Calling Agent"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ai_calling_agent"
    frontend_url: str = "http://localhost:3000"
    public_backend_url: str = "http://localhost:8000"
    calling_provider: str = "simulated"

    # GenAI: OpenRouter free router by default.
    llm_provider: str = "openrouter"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openrouter/free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str | None = "http://localhost:3000"
    openrouter_app_name: str = "AI Calling Agent"
    llm_timeout_seconds: float = 20.0

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    # "trial" uses a Twilio-approved outbound bootstrap and then switches the
    # live call to our custom Gather/Say flow; "upgraded" uses our webhook directly.
    twilio_account_tier: str = "trial"
    twilio_voice_mode: str = "gather"
    twilio_relay_language: str = "en-IN"
    twilio_validate_signature: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
