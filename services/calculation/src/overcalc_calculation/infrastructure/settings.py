from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OVERCALC_DATABASE_")

    url: str
    probe_timeout_seconds: float = 2.0
