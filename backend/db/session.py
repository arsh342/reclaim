from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()

# SQLite doesn't support pool_size/max_overflow
if _settings.database_url.startswith("sqlite"):
    engine = create_engine(
        _settings.database_url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        _settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
