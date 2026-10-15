import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "review_signal.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    business_type TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    source TEXT DEFAULT '',
    author TEXT DEFAULT '',
    rating REAL,
    text TEXT NOT NULL,
    review_date TEXT,
    fingerprint TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reviews_fingerprint
    ON reviews(project_id, fingerprint);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    stage TEXT DEFAULT '',
    processed INTEGER DEFAULT 0,
    total INTEGER DEFAULT 0,
    model TEXT DEFAULT '',
    error TEXT,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    category TEXT DEFAULT 'other',
    polarity TEXT DEFAULT 'negative',
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id INTEGER NOT NULL,
    review_id INTEGER NOT NULL,
    sentiment TEXT NOT NULL,
    severity INTEGER DEFAULT 3,
    excerpt TEXT DEFAULT '',
    FOREIGN KEY (theme_id) REFERENCES themes(id) ON DELETE CASCADE,
    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_mentions_theme ON mentions(theme_id);
"""


def connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def cursor():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with cursor() as conn:
        conn.executescript(SCHEMA)
