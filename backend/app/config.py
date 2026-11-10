from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    frontend_origin: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
