"""Initialize the Rhizome SQLite database."""
import sqlite3
import os

DB_PATH = os.environ.get(
    "RHIZOME_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "rhizome.db"),
)
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def init(db_path=None):
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = f.read()
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.executescript(schema)
    conn.close()
    print(f"Database initialized at {path}")


if __name__ == "__main__":
    init()
