from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "BrandBot SDR v2.0 Enterprise"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False

    SECRET_KEY: str = ""
    ENCRYPTION_KEY: str = ""
    WEBHOOK_SECRET: str = ""

    DATABASE_URL: str = "postgresql+asyncpg://brandbot_user:@postgres:5432/brandbot_db"
    REDIS_URL: str = "redis://redis:6379/0"

    DISCORD_BOT_TOKEN: str = ""
    DISCORD_ALERT_CHANNEL_ID: int = 0
    METAAPI_TOKEN: str = ""
    METAAPI_ACCOUNT_ID: str = ""
    METAAPI_API_HOST: str = "https://mt-client-api-v1.agiliumtrade.ai"

    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_ENABLED: bool = False

    WEBHOOK_HMAC_ENABLED: bool = False
    WEBHOOK_IP_ALLOWLIST: str = ""
    WEBHOOK_RATE_LIMIT_PER_MINUTE: int = 60

    REDIS_LOCK_TTL_SECONDS: int = 45
    IDEMPOTENCY_TTL_SECONDS: int = 86400

    MAX_DRAWDOWN_PERCENT: float = 5.0
    MAX_DAILY_DRAWDOWN_PERCENT: float = 3.0
    RISK_PERCENT_PER_TRADE: float = 1.0

    FVG_VOLUME_SMA_PERIOD: int = 20
    FVG_VOLUME_SMA_MULTIPLIER: float = 1.5
    MSS_LOCAL_STRUCTURE_LOOKBACK: int = 10
    SMC_SWEEP_LOOKBACK_CANDLES: int = 20
    ACCOUNT_BALANCE: float = 10000.0
    MIN_LOT_SIZE: float = 0.01
    MAX_LOT_SIZE: float = 2.0

    ML_MODEL_PATH: str = ""
    ML_MIN_WIN_PROBABILITY: float = 0.55
    ALLOW_SIMULATED_EXECUTION: bool = False

    CORS_ORIGINS: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def cors_origin_list(self) -> list[str]:
        if not self.CORS_ORIGINS.strip():
            return []
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def webhook_ip_allowlist(self) -> set[str]:
        if not self.WEBHOOK_IP_ALLOWLIST.strip():
            return set()
        return {ip.strip() for ip in self.WEBHOOK_IP_ALLOWLIST.split(",") if ip.strip()}


settings = Settings()
