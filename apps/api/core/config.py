"""
CargoIQ API — Application Configuration
"""
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "CargoIQ API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "dev-secret-change-in-production"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # URLs — used to build links in emails/notifications and to
    # reach the Next.js email-send route and Evolution API (WhatsApp).
    API_URL: str = "http://localhost:8000"
    WEB_URL: str = "http://localhost:3000"

    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    # Settings -> API -> JWT Settings -> "JWT Secret" in the Supabase
    # dashboard. Required to actually verify token signatures — without
    # this, any hand-crafted JWT with a fake "sub" claim is accepted.
    SUPABASE_JWT_SECRET: str = ""

    ANTHROPIC_API_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    ENCRYPTION_KEY: str = ""
    MAX_UPLOAD_SIZE_MB: int = 50
    SENTRY_DSN: str = ""

    EVOLUTION_API_URL: str = "http://localhost:8080"
    EVOLUTION_API_KEY: str = ""

    # Platform-level alerts (portal health monitor, etc.) go here —
    # NOT to a client org's contact. Set these to your own email and
    # WhatsApp number so you, not a client, find out when a portal
    # adapter breaks.
    PLATFORM_ADMIN_EMAIL: str = ""
    PLATFORM_ADMIN_WHATSAPP: str = ""

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
