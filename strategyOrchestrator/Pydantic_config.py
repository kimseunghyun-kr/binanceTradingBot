from pydantic_settings import BaseSettings
from dotenv import load_dotenv

from config_profile import DOTENV_FILE

load_dotenv(DOTENV_FILE)

class Settings(BaseSettings):
    MONGO_URI: str
    MONGO_DB: str = "trading"

    class Config:
        env_file = DOTENV_FILE
        case_sensitive = False

settings = Settings()
