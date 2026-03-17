from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Logistics Pro API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./logistics_pro.db"

    # JWT
    SECRET_KEY: str = "logistics-pro-secret-key-change-in-production-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    
    # Data retention (temporary test window)
    RETENTION_MINUTES: int = 5

    # Google AI Studio (Gemini)
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    class Config:
        env_file = ".env"


settings = Settings()
