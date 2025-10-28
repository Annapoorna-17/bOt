from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..db import get_db, Base, engine
from ..models import Company, User
from ..schemas import CompanyCreate, CompanyOut, UserCreate, UserOut
from ..security import require_superadmin
from ..auth import hash_password

router = APIRouter(prefix="/superadmin/companies", tags=["Superadmin"])

# Create tables on import (demo convenience)
Base.metadata.create_all(bind=engine)


@router.post("", response_model=CompanyOut, dependencies=[Depends(require_superadmin)])
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    """
    Create a new company/tenant. Superadmin only.
    """
    # slug_url default
    slug_url = payload.slug_url or f"https://service.local/{payload.tenant_code}"

    exists = db.query(Company).filter(
        (Company.tenant_code == payload.tenant_code) | (Company.slug_url == slug_url)
    ).first()

    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="tenant_code or slug already exists"
        )

    c = Company(
        name=payload.name,
        tenant_code=payload.tenant_code,
        slug_url=slug_url,
        email=payload.email,
        phone=payload.phone,
        website=payload.website,
        address=payload.address,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.get("", response_model=list[CompanyOut], dependencies=[Depends(require_superadmin)])
def list_companies(db: Session = Depends(get_db)):
    """
    List all companies. Superadmin only.
    """
    companies = db.query(Company).order_by(Company.created_at.desc()).all()
    return companies


@router.post("/{tenant_code}/admin", response_model=UserOut, dependencies=[Depends(require_superadmin)])
def create_first_admin(
    tenant_code: str,
    payload: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Create the first admin user for a company/tenant.
    This solves the chicken-and-egg problem of needing an admin to create users.
    Superadmin only.

    After creating this first admin, they can use /auth/register or /users endpoints
    to create additional users.
    """
    # Find the company
    company = db.query(Company).filter(Company.tenant_code == tenant_code).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with tenant_code '{tenant_code}' not found"
        )

    # Ensure tenant_code in payload matches
    if payload.tenant_code != tenant_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payload tenant_code must match URL tenant_code '{tenant_code}'"
        )

    # Ensure user_code starts with tenant_code
    if not payload.user_code.startswith(f"{tenant_code}-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"user_code must start with '{tenant_code}-'"
        )

    # Force role to admin
    if payload.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint only creates admin users. Use role='admin'"
        )

    # Check if user already exists (by email or user_code)
    existing = db.query(User).filter(
        (User.user_code == payload.user_code) | (User.email == payload.email)
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with this email or user_code already exists"
        )

    # Hash the password
    hashed_pass = hash_password(payload.password)

    # Create admin user with password (no API key)
    user = User(
        company_id=company.id,
        display_name=payload.display_name,
        user_code=payload.user_code,
        role="admin",
        hashed_password=hashed_pass,
        email=payload.email,
        address=payload.address,
        contact_number=payload.contact_number,
        api_key=None,  # No API key for JWT users
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user
