# from passlib.context import CryptContext

# # Use bcrypt_sha256 to avoid the 72-byte limit safely
# pwd_ctx = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")

# def hash_password(plain: str) -> str:
#     return pwd_ctx.hash(plain)

# def verify_password(plain: str, hashed: str) -> bool:
#     return pwd_ctx.verify(plain, hashed)

# def role_name(role: int) -> str:
#     return {1: "Super Admin", 2: "Admin", 3: "User"}.get(role, "Unknown")

import os
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

# --- IMPORTANT ---
# You need to import your models, schemas, and db session.
# Adjust these import paths if they are incorrect for your project.
from . import models, schemas
from .db import get_db

# ----------------------------------------------------
# 1. PASSWORD HASHING
# ----------------------------------------------------
def hash_password(plain: str) -> str:
    """Hash a password using bcrypt."""
    # Convert to bytes and hash
    password_bytes = plain.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    password_bytes = plain.encode('utf-8')
    hashed_bytes = hashed.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)

def role_name(role: int) -> str:
    """Get role name from role ID (legacy function)."""
    return {1: "Super Admin", 2: "Admin", 3: "User"}.get(role, "Unknown")
# ----------------------------------------------------
# 2. JWT (TOKEN) CONFIGURATION (SECURE VERSION)
# ----------------------------------------------------

# Read secrets from the environment (which main.py already loaded)
SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", 7))

# Fail fast if the secret key is missing from your .env file
if not SECRET_KEY:
    raise ValueError("SECRET_KEY not set in .env file. Please add it.")

# This tells FastAPI where to go to get a token.
# We will create the "/auth/login" endpoint in your router file.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ----------------------------------------------------
# 3. NEW: JWT (TOKEN) CREATION FUNCTIONS
# ----------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Creates a new Access Token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Creates a new Refresh Token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ----------------------------------------------------
# 4. NEW: SECURITY DEPENDENCY
# ----------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> models.User:
    """
    This is the dependency you will add to your protected endpoints.
    It decodes the token, validates it, and fetches the user from the DB.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Check if it's an access token
        if payload.get("type") != "access":
            raise credentials_exception
            
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        
        # We use the TokenData schema we defined in schemas.py
        token_data = schemas.TokenData(sub=email, type="access")
    
    except JWTError:
        # This catches expired tokens, invalid signatures, etc.
        raise credentials_exception
    
    # Get the user from the database
    user = db.query(models.User).filter(models.User.email == token_data.sub).first()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return user
