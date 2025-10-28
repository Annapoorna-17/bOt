from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from os import getenv
from secrets import token_urlsafe
from ..db import get_db, Base, engine
from ..models import Company, User
from ..schemas import CompanyCreate, CompanyOut, UserCreate, UserOut
from ..security import require_superadmin

router = APIRouter(prefix="/superadmin/companies", tags=["Superadmin"])

# Create tables on import (demo convenience)
Base.metadata.create_all(bind=engine)

@router.post("", response_model=CompanyOut, dependencies=[Depends(require_superadmin)])
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    # slug_url default
    slug_url = payload.slug_url or f"https://service.local/{payload.tenant_code}"
    exists = db.query(Company).filter(
        (Company.tenant_code == payload.tenant_code) | (Company.slug_url == slug_url)
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="tenant_code or slug already exists")
    c = Company(name=payload.name,
        tenant_code=payload.tenant_code,
        slug_url=slug_url, 
        email=payload.email,
        phone=payload.phone,
        website=payload.website,
        address=payload.address,)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

@router.post("/{tenant_code}/admin", response_model=UserOut, dependencies=[Depends(require_superadmin)])
def create_company_admin(
    tenant_code: str,
    payload: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Create the first admin user for a company. This solves the chicken-and-egg problem
    of needing an admin to create users. Superadmin only.
    """
    # Find the company
    company = db.query(Company).filter(Company.tenant_code == tenant_code).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company with tenant_code '{tenant_code}' not found")

    # Ensure tenant_code in payload matches
    if payload.tenant_code != tenant_code:
        raise HTTPException(
            status_code=400,
            detail=f"Payload tenant_code must match URL tenant_code '{tenant_code}'"
        )

    # Ensure user_code starts with tenant_code
    if not payload.user_code.startswith(f"{tenant_code}-"):
        raise HTTPException(
            status_code=400,
            detail=f"user_code must start with '{tenant_code}-'"
        )

    # Force role to admin
    if payload.role != "admin":
        raise HTTPException(
            status_code=400,
            detail="This endpoint only creates admin users. Use role='admin'"
        )

    # Check if user already exists
    existing = db.query(User).filter(User.user_code == payload.user_code).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"User with user_code '{payload.user_code}' already exists")

    # Create admin user
    api_key = token_urlsafe(48)
    user = User(
        company_id=company.id,
        display_name=payload.display_name,
        user_code=payload.user_code,
        role="admin",
        api_key=api_key,
        email=payload.email,
        address=payload.address,
        contact_number=payload.contact_number,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
