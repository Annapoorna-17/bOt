# app/main.py
from dotenv import load_dotenv
load_dotenv()  # ensure .env is loaded before other imports

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

# Import routers
from .routers.companies import router as companies_router
from .routers.users import router as users_router
from .routers.documents import router as documents_router
from .routers.websites import router as websites_router
from .routers.query import router as query_router
from .routers.auth import router as auth_router
from .routers.widget import router as widget_router

from .db import Base, engine

app = FastAPI(
    title="Multi-tenant RAG Service",
    version="1.0.0",
    description="Company-scoped document Q&A with OpenAI + Pinecone"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for profile images
PROFILE_IMAGES_DIR = "profile_images"
os.makedirs(PROFILE_IMAGES_DIR, exist_ok=True)
app.mount("/profile-images", StaticFiles(directory=PROFILE_IMAGES_DIR), name="profile-images")

# Include routers
app.include_router(auth_router)       # Authentication (login, register, etc.)
app.include_router(companies_router)  # Superadmin - company management
app.include_router(users_router)      # User management
app.include_router(documents_router)  # Document upload/management
app.include_router(websites_router)   # Website scraping/management
app.include_router(query_router)      # RAG queries
app.include_router(widget_router)     # Widget and super-admin company queries

@app.on_event("startup")
def _setup():
    """
    Initialize database on startup.
    1. Create tables if they don't exist
    2. Run migrations to add any new columns to existing tables
    """
    # Create new tables
    Base.metadata.create_all(bind=engine)

    # Run migrations to add missing columns
    try:
        from .db_migration import migrate_database
        migrate_database()
    except Exception as e:
        print(f"Warning: Database migration failed: {e}")
        print("Some features may not work if database schema is outdated")

@app.get("/healthz")
def health():
    return {"ok": True}
