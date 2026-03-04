from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}

    database_url: str = "postgresql+asyncpg://nelson:nelson@localhost:5432/nelson"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    fernet_key: str = "change-me-in-production"
    resend_api_key: str = ""
    cors_origins: list[str] = ["http://localhost:3000"]
    magic_link_base_url: str = "http://localhost:3000/login/verify"


settings = Settings()
