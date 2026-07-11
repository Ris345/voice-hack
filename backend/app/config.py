from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_role_key: str

    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str  # voice-capable — places the outbound call
    twilio_sms_number: str = ""  # SMS sender; falls back to from_number if unset

    # "sms" or "whatsapp". WhatsApp sandbox avoids US A2P 10DLC registration.
    messaging_channel: str = "sms"
    twilio_whatsapp_from: str = "whatsapp:+14155238886"  # Twilio global sandbox number

    public_base_url: str
    voice_agent_twiml_url: str = ""

    @property
    def sms_from(self) -> str:
        return self.twilio_sms_number or self.twilio_from_number


settings = Settings()
