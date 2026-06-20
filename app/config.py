from pydantic import BaseModel
from typing import Optional
import os


class Settings(BaseModel):
    PORT: int = 8144
    HOST: str = "0.0.0.0"
    DB_PATH: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "db.json")
    SECRET_KEY: str = "laundry-factory-secret-key-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    QC_TIMEOUT_HOURS: int = 24
    REWASH_BACKLOG_THRESHOLD: int = 10
    DAMAGE_RATE_THRESHOLD: float = 0.05


settings = Settings()
