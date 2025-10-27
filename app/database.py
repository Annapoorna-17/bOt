# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker, declarative_base
# from dotenv import load_dotenv
# import os

# load_dotenv()  # loads .env at project root

# DB_USER = os.getenv("DB_USER")
# DB_PASSWORD = os.getenv("DB_PASSWORD")
# DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
# DB_PORT = os.getenv("DB_PORT", "3306")
# DB_NAME = os.getenv("DB_NAME")

# if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
#     raise RuntimeError("❌ Missing one or more DB_* env vars. Check your .env")

# DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# engine = create_engine(
#     DATABASE_URL,
#     pool_pre_ping=True,
#     pool_recycle=280,
#     future=True,
# )
# SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

# Base = declarative_base()

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()
