from pathlib import Path
from sqlite3 import Connection

from sqlalchemy import Engine, event
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


def sqlite_url(path: Path) -> URL:
    return URL.create("sqlite+pysqlite", database=str(path))


def create_sqlite_engine(path: Path) -> Engine:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    engine = create_engine(sqlite_url(path))

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection: Connection, _record: object) -> None:
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA journal_mode = WAL")
        finally:
            cursor.close()

    return engine
