from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# If DATABASE_URL is not provided, build it from DB_* pieces
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DB_USER = os.getenv("DB_USER", "")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "")
    DB_PORT = os.getenv("DB_PORT", "")
    DB_NAME = os.getenv("DB_NAME", "")
    # URL-encode password if needed
    from urllib.parse import quote_plus
    DATABASE_URL = (
        f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # avoid "MySQL server has gone away"
    pool_recycle=280,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
