# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from secrets import token_urlsafe
from typing import List
from ..db import get_db
from ..models import Company, User
from ..schemas import UserCreate, UserOut
from ..security import require_admin, require_caller, Caller

router = APIRouter(prefix="/users", tags=["Users & Admin"])

@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    caller: Caller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if caller.tenant.tenant_code != payload.tenant_code:
        raise HTTPException(status_code=403, detail="Cannot create user in another tenant")

    if not payload.user_code.startswith(payload.tenant_code + "-"):
        raise HTTPException(status_code=400, detail="user_code must start with '<tenant_code>-'")

    api_key = token_urlsafe(48)
    u = User(
        company_id=caller.tenant.id,
        display_name=payload.display_name,
        user_code=payload.user_code,
        role=payload.role,
        api_key=api_key,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

@router.get("", response_model=List[UserOut])
def list_users(
    caller: Caller = Depends(require_caller),
    db: Session = Depends(get_db),
):
    """
    List all users in the caller's tenant. Any authenticated user can see the user list.
    """
    users = db.query(User).filter(User.company_id == caller.tenant.id).order_by(User.created_at.desc()).all()
    return users

@router.get("/me", response_model=UserOut)
def get_current_user(caller: Caller = Depends(require_caller)):
    """
    Get the current authenticated user's information.
    """
    return caller.user
