from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # sqlite default means `uvicorn app.main:app` just works with no setup
    database_url: str = "sqlite:///./playnext.db"
    secret_key: str = "dev-only-change-me"
    access_token_minutes: int = 60 * 24 * 7

    # comma-separated list of origins allowed to call the API. Localhost by
    # default; set CORS_ORIGINS to the deployed frontend URL in production.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # how many login attempts one IP gets per minute
    login_rate_limit: str = "10/minute"
    # how many verification/reset emails one IP can ask for
    email_rate_limit: str = "5/hour"

    # ---- email ----
    # "console" prints links to the log, which is what local development wants.
    # "smtp" sends for real and needs the settings below.
    mail_mode: str = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = "PlayNext <no-reply@playnext.app>"
    # Turn on to block sign-in until the address is confirmed. Off by default so
    # a deployment without mail configured stays usable.
    require_email_verification: bool = False
    verify_token_hours: int = 48
    reset_token_hours: int = 1

    # One-click demo sign-in. On for a portfolio deployment so a recruiter can
    # look around without registering; turn off for anything real.
    enable_demo_login: bool = True
    demo_email: str = "demo@playnext.app"

    igdb_client_id: str = ""
    igdb_client_secret: str = ""
    steam_api_key: str = ""

    # where this API and the web app live, needed for the Steam OpenID round-trip
    public_api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return not self.database_url.startswith("sqlite")


settings = Settings()

# a default secret is fine locally and dangerous in production, so say so loudly
if settings.is_production and settings.secret_key == "dev-only-change-me":
    import warnings

    warnings.warn("SECRET_KEY is still the development default - set it before exposing this API", stacklevel=2)
