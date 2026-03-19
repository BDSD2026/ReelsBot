"""SQLite helper — tracks used posts"""
import sqlite3
import logging
from datetime import datetime
from utils.config import config

log = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.path = config.DB_PATH
        self._init()

    def _conn(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS used_posts (
                    reddit_id     TEXT PRIMARY KEY,
                    title         TEXT,
                    subreddit     TEXT,
                    score         INTEGER,
                    post_id       TEXT,
                    posted_at     TEXT
                );
            """)

    def get_used_post_ids(self) -> set:
        with self._conn() as conn:
            rows = conn.execute("SELECT reddit_id FROM used_posts").fetchall()
        return {r[0] for r in rows}

    def mark_used(self, reddit_id: str, post_id: str = "", title: str = "", subreddit: str = "", score: int = 0):
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO used_posts (reddit_id, title, subreddit, score, post_id, posted_at) VALUES (?,?,?,?,?,?)",
                (reddit_id, title, subreddit, score, post_id, now),
            )
        log.info("Marked '%s' as used", title[:50])
