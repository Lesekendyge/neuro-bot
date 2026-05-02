import logging
import aiosqlite
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = "neuro_bot.db"


async def init_db(db_path: str = DB_PATH) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                current_topic INTEGER DEFAULT 0,
                reading     INTEGER DEFAULT 0,
                joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS progress_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                topic_index INTEGER,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    logger.info("Database initialized")


async def get_user(user_id: int, db_path: str = DB_PATH) -> Optional[dict]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def register_user(user_id: int, username: str, db_path: str = DB_PATH) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT OR IGNORE INTO users (user_id, username)
               VALUES (?, ?)""",
            (user_id, username),
        )
        await db.commit()


async def set_reading_flag(user_id: int, flag: int, db_path: str = DB_PATH) -> None:
    """flag=1 — пользователь получил тему и читает; flag=0 — готов к следующей."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE users SET reading = ? WHERE user_id = ?", (flag, user_id)
        )
        await db.commit()


async def advance_topic(user_id: int, db_path: str = DB_PATH) -> int:
    """Сдвигает индекс темы вперёд, логирует завершение. Возвращает новый индекс."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT current_topic FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            old_index = row["current_topic"] if row else 0

        await db.execute(
            """INSERT INTO progress_log (user_id, topic_index)
               VALUES (?, ?)""",
            (user_id, old_index),
        )
        new_index = old_index + 1
        await db.execute(
            "UPDATE users SET current_topic = ?, reading = 0 WHERE user_id = ?",
            (new_index, user_id),
        )
        await db.commit()
    return new_index


async def reset_user(user_id: int, db_path: str = DB_PATH) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE users SET current_topic = 0, reading = 0 WHERE user_id = ?",
            (user_id,),
        )
        await db.execute(
            "DELETE FROM progress_log WHERE user_id = ?", (user_id,)
        )
        await db.commit()


async def get_completed_count(user_id: int, db_path: str = DB_PATH) -> int:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM progress_log WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_all_user_ids(db_path: str = DB_PATH) -> list[int]:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]
