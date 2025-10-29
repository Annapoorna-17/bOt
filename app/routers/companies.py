from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..db import get_db, Base, engine
from ..models import Company, User
from ..schemas import CompanyCreate, CompanyOut, UserCreate, UserOut, SuperadminCreate
from ..security import require_superadmin, SUPERADMIN_SYSTEM_TENANT
from ..auth import hash_password

router = APIRouter(prefix="/superadmin/companies", tags=["Superadmin"])

# Create tables on import (demo convenience)
Base.metadata.create_all(bind=engine)


@router.post("", response_model=CompanyOut, dependencies=[Depends(require_superadmin)])
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    """
    Create a new company/tenant. Superadmin only.
    """
    # Prevent using the reserved superadmin tenant code
    if payload.tenant_code.upper() == SUPERADMIN_SYSTEM_TENANT.upper():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The tenant code '{SUPERADMIN_SYSTEM_TENANT}' is reserved for system use and cannot be used for regular companies"
        )

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


@router.get("/admins", response_model=list[UserOut], dependencies=[Depends(require_superadmin)])
def list_all_company_admins(db: Session = Depends(get_db)):
    """
    List all admin users across all companies with their company names.
    Superadmin only.
    """
    admins = db.query(User).filter(User.role.in_(["admin", "superadmin"])).order_by(User.created_at.desc()).all()

    # Add company_name to each admin
    result = []
    for admin in admins:
        admin_dict = {
            "id": admin.id,
            "display_name": admin.display_name,
            "user_code": admin.user_code,
            "role": admin.role,
            "api_key": admin.api_key,
            # Convert empty string to None for proper validation
            "email": admin.email if admin.email else None,
            "address": admin.address,
            "contact_number": admin.contact_number,
            "profile_image": admin.profile_image,
            "company_name": admin.company.name if admin.company else None
        }
        result.append(admin_dict)

    return result


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
    # Prevent creating regular users in the reserved superadmin tenant
    if tenant_code.upper() == SUPERADMIN_SYSTEM_TENANT.upper():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot create regular users in the reserved tenant '{SUPERADMIN_SYSTEM_TENANT}'. Use POST /superadmin/companies/superadmin to create superadmin users."
        )

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


@router.post("/superadmin", response_model=UserOut, dependencies=[Depends(require_superadmin)])
def create_superadmin_user(
    payload: SuperadminCreate,
    db: Session = Depends(get_db)
):
    """
    Create a superadmin user.
    This endpoint is only accessible with token-based superadmin authentication
    (not JWT-based), to bootstrap the first superadmin user.

    Superadmin users have system-wide privileges including:
    - Creating and managing companies
    - Creating admin users for any company
    - All capabilities of the superadmin token

    Superadmin users automatically belong to a reserved system company with
    tenant_code '{SUPERADMIN_SYSTEM_TENANT}' which cannot be used by regular companies.
    The system company is auto-created if it doesn't exist.
    """
    # Ensure the reserved system company exists
    company = db.query(Company).filter(Company.tenant_code == SUPERADMIN_SYSTEM_TENANT).first()
    if not company:
        # Auto-create the system company for superadmin users
        company = Company(
            name="System Administration",
            tenant_code=SUPERADMIN_SYSTEM_TENANT,
            slug_url=f"https://service.local/{SUPERADMIN_SYSTEM_TENANT.lower()}",
            email="system@admin.local",
            phone=None,
            website=None,
            address="System Reserved"
        )
        db.add(company)
        db.commit()
        db.refresh(company)

    # Check if user_code starts with the system tenant prefix
    expected_prefix = f"{SUPERADMIN_SYSTEM_TENANT}-"
    if not payload.user_code.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Superadmin user_code must start with '{expected_prefix}'"
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

    # Create superadmin user with password (no API key)
    user = User(
        company_id=company.id,
        display_name=payload.display_name,
        user_code=payload.user_code,
        role="superadmin",
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
