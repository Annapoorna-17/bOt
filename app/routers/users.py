from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..db import get_db
from ..models import Company, User
from ..schemas import UserCreate, UserOut

# --- 1. Import new auth and models ---
from ..auth import get_current_user, hash_password
from .. import models

# --- 2. REMOVED old auth imports (require_admin, require_caller, Caller) ---

router = APIRouter(prefix="/users", tags=["Users & Admin"])

@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    # --- 3. USE new dependency ---
    current_admin: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db),
):
    """
    Create a new user. Only an 'admin' can do this.
    """
    
    # --- 4. ADD check to ensure current user is an admin ---
    if current_admin.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create users"
        )
    
    # --- 5. UPDATE logic to use 'current_admin' ---
    if current_admin.company.tenant_code != payload.tenant_code:
        raise HTTPException(status_code=403, detail="Cannot create user in another tenant")

    if not payload.user_code.startswith(payload.tenant_code + "-"):
        raise HTTPException(status_code=400, detail="user_code must start with '<tenant_code>-'")

    # Check if email or user_code already exists
    existing = db.query(User).filter(
        (User.email == payload.email) | (User.user_code == payload.user_code)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="User with this email or user_code already exists")

    # --- 6. UPDATE to hash password (no more api_key) ---
    hashed_pass = hash_password(payload.password)

    u = User(
        company_id=current_admin.company_id, # <-- Changed
        display_name=payload.display_name,
        user_code=payload.user_code,
        role=payload.role,
        hashed_password=hashed_pass, # <-- Changed
        email=payload.email,
        address=payload.address,
        contact_number=payload.contact_number,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

@router.get("", response_model=List[UserOut])
def list_users(
    # --- 7. USE new dependency ---
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db),
):
    """
    List all users in the caller's tenant. Any authenticated user can see the user list.
    """
    # --- 8. UPDATE logic ---
    users = db.query(User).filter(User.company_id == current_user.company_id).order_by(User.created_at.desc()).all()
    return users

@router.get("/me", response_model=UserOut)
def get_logged_in_user(
    # --- 9. USE new dependency ---
    current_user: models.User = Depends(get_current_user)
):
    """
    Get the current authenticated user's information.
    """
    # --- 10. UPDATE logic ---
    return current_user
