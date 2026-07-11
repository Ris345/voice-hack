from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_role_key: str

    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str

    public_base_url: str
    voice_agent_twiml_url: str = ""


settings = Settings()
