from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = _normalize_database_url(settings.DATABASE_URL)

# SQLite connection pooling and optimization
connect_args = {}
engine_kwargs = {
    "pool_pre_ping": True,
    "echo": False,
}

# For SQLite, use NullPool for development (no pooling needed)
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy.pool import NullPool
    engine_kwargs["poolclass"] = NullPool
    connect_args = {
        "timeout": 10,  # Connection timeout in seconds
        "check_same_thread": False,  # Allow access from other threads
    }
else:
    # For other databases, use connection pooling
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 40

engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)

# Enable query optimization for SQLite
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys=ON")
        # Optimize for better query performance
        cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
        cursor.execute("PRAGMA synchronous=NORMAL")  # Safer than FULL, faster
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
