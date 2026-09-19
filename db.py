import os
import secrets
import sqlite3
from datetime import datetime, timezone


def _db_path() -> str:
    return os.environ.get("DB_PATH", "data/giveaway.db")


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(_db_path())
    connection.row_factory = sqlite3.Row
    return connection


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


def init() -> None:
    path = _db_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                message_id INTEGER,
                text TEXT,
                prize TEXT,
                draw_at TEXT,
                winner_id INTEGER NULL,
                drawn INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS participants (
                giveaway_id INTEGER,
                user_id INTEGER,
                username TEXT,
                screenshot_file_id TEXT NULL,
                PRIMARY KEY (giveaway_id, user_id)
            );
            """
        )


def create_giveaway(
    chat_id: int, text: str, prize: str, draw_at: datetime
) -> int:
    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO giveaways (chat_id, text, prize, draw_at)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, text, prize, _utc_iso(draw_at)),
        )
        return cursor.lastrowid


def set_message_id(giveaway_id: int, message_id: int) -> None:
    with _connect() as connection:
        connection.execute(
            "UPDATE giveaways SET message_id = ? WHERE id = ?",
            (message_id, giveaway_id),
        )


def add_participant(giveaway_id: int, user_id: int, username: str) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO participants (giveaway_id, user_id, username)
            VALUES (?, ?, ?)
            """,
            (giveaway_id, user_id, username),
        )


def set_screenshot(user_id: int, file_id: str) -> int | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT p.giveaway_id
            FROM participants AS p
            JOIN giveaways AS g ON g.id = p.giveaway_id
            WHERE p.user_id = ? AND g.drawn = 0
            ORDER BY g.id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if row is None:
            return None

        giveaway_id = row["giveaway_id"]
        connection.execute(
            """
            UPDATE participants
            SET screenshot_file_id = ?
            WHERE giveaway_id = ? AND user_id = ?
            """,
            (file_id, giveaway_id, user_id),
        )
        return giveaway_id


def participants(giveaway_id: int) -> list[dict]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT giveaway_id, user_id, username, screenshot_file_id
            FROM participants
            WHERE giveaway_id = ?
            ORDER BY user_id
            """,
            (giveaway_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def due_giveaways(now: datetime) -> list[dict]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, chat_id, message_id, text, prize, draw_at, winner_id, drawn
            FROM giveaways
            WHERE drawn = 0 AND draw_at <= ?
            ORDER BY draw_at, id
            """,
            (_utc_iso(now),),
        ).fetchall()
        return [dict(row) for row in rows]


def _choose_winner(giveaway_id: int, excluded_user_id: int | None) -> dict | None:
    with _connect() as connection:
        if excluded_user_id is None:
            rows = connection.execute(
                """
                SELECT giveaway_id, user_id, username, screenshot_file_id
                FROM participants
                WHERE giveaway_id = ?
                  AND screenshot_file_id IS NOT NULL
                  AND screenshot_file_id != ''
                """,
                (giveaway_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT giveaway_id, user_id, username, screenshot_file_id
                FROM participants
                WHERE giveaway_id = ?
                  AND screenshot_file_id IS NOT NULL
                  AND screenshot_file_id != ''
                  AND user_id != ?
                """,
                (giveaway_id, excluded_user_id),
            ).fetchall()

        winner = dict(secrets.choice(rows)) if rows else None
        connection.execute(
            "UPDATE giveaways SET winner_id = ?, drawn = 1 WHERE id = ?",
            (winner["user_id"] if winner else None, giveaway_id),
        )
        return winner


def pick_winner(giveaway_id: int) -> dict | None:
    return _choose_winner(giveaway_id, None)


def redraw(giveaway_id: int) -> dict | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT winner_id FROM giveaways WHERE id = ?",
            (giveaway_id,),
        ).fetchone()
    current_winner_id = row["winner_id"] if row else None
    return _choose_winner(giveaway_id, current_winner_id)
