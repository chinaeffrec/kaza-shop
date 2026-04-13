from pydantic import BaseSettings

class Settings(BaseSettings):
    """
    RU: bootstrap-конфигурация приложения
    EN: bootstrap configuration (temporary source)
    """
    app_env: str = "dev"

    #DEV only
    database_url: str
    bot_token: str
    admin_id: int

settings = Settings()