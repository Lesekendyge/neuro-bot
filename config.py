import os
from dataclasses import dataclass


@dataclass
class Config:
    BOT_TOKEN: str
    DB_PATH: str = "neuro_bot.db"
    SEND_HOUR: int = 19
    SEND_MINUTE: int = 0
    MAX_MSG_LEN: int = 4096


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable is not set")
    return Config(BOT_TOKEN=token)
