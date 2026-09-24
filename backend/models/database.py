"""SQLAlchemy engine, session factory and declarative base."""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        """并发加固：定时调度（news/papers/digest/weekly）与手动采集会并发写库，
        WAL 提升读写并发，busy_timeout 让写锁等待而非立即 'database is locked'。"""
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=15000")  # 15s
        cur.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Import models so they register on Base.metadata."""
    from models import schema  # noqa: F401
    from models.migrate import ensure_columns

    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)  # 旧库补新列（create_all 不改已有表）
