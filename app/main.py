from fastapi import FastAPI, Depends, Path
from sqlalchemy.orm import Session
from sqlalchemy import select, update as sa_update
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine, get_db
from . import models, schemas
from .auth import hash_password, verify_password, role_name
from .utils import conflict, unauthorized, generate_short_uid
from .models import User, Company


app = FastAPI(
    title="Role-based Registration & Login",
    version="1.0.0",
    description="Simple FastAPI backend with MySQL, role-aware registration, and login."
)

# (Optional) CORS if you plan to call this from a frontend later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# Auto-create tables (for quick start). In production, use Alembic migrations.
Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/register", response_model=schemas.RegistrationResponse, tags=["auth"])
def register(payload: schemas.RegistrationRequest, db: Session = Depends(get_db)):
    # unique email check
    exists = db.execute(select(models.User).where(models.User.email == str(payload.email))).scalar_one_or_none()
    if exists:
        conflict("Email already registered")

    user = models.User(
        role=payload.role,
        name=payload.name.strip(),
        phone=payload.phone.strip(),
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        company_name=(payload.company_name.strip() if payload.company_name else None),
        active=payload.active if payload.role == 2 else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return schemas.RegistrationResponse(
        id=user.id,
        role=user.role,
        email=user.email,
        message="Registration successful"
    )

@app.post("/api/login", response_model=schemas.LoginResponse, tags=["auth"])
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(select(models.User).where(models.User.email == str(payload.email).lower())).scalar_one_or_none()
    if not user:
        unauthorized()

    if not verify_password(payload.password, user.password_hash):
        unauthorized()

    return schemas.LoginResponse(
        id=user.id,
        role=user.role,
        email=user.email,
        role_name=role_name(user.role),
        message=f"Login successful. You are {role_name(user.role)}."
    )

# ---------------------------
# Company APIs
# ---------------------------

@app.post("/api/companies", response_model=schemas.CompanyOut, tags=["company"])
def create_company(payload: schemas.CompanyCreate, db: Session = Depends(get_db)):
    # Unique email check
    existing_email = db.execute(select(Company).where(Company.email == str(payload.email).lower())).scalar_one_or_none()
    if existing_email:
        conflict("Company email already exists")

    # Generate unique UID (retry small number of times on the off chance of collision)
    for _ in range(5):
        uid = generate_short_uid(8)
        if not db.execute(select(Company).where(Company.uid == uid)).scalar_one_or_none():
            break
    else:
        conflict("Failed to generate unique UID, try again")

    company = Company(
        uid=uid,
        name=payload.company_name.strip(),
        email=str(payload.email).lower(),
        phone=payload.phone.strip(),
        website=(payload.website.strip() if payload.website else None),
        address=(payload.address.strip() if payload.address else None),
        url=(payload.url.strip() if payload.url else None),
        active=bool(payload.active),
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    return schemas.CompanyOut(
        id=company.id,
        uid=company.uid,
        name=company.name,
        email=company.email,
        phone=company.phone,
        website=company.website,
        address=company.address,
        url=company.url,
        active=company.active,
    )


@app.get("/api/companies/{uid}", response_model=schemas.CompanyOut, tags=["company"])
def get_company(uid: str = Path(..., min_length=4, max_length=32), db: Session = Depends(get_db)):
    company = db.execute(select(Company).where(Company.uid == uid)).scalar_one_or_none()
    if not company:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Company not found")

    return schemas.CompanyOut(
        id=company.id,
        uid=company.uid,
        name=company.name,
        email=company.email,
        phone=company.phone,
        website=company.website,
        address=company.address,
        url=company.url,
        active=company.active,
    )


@app.get("/api/companies", response_model=list[schemas.CompanyName], tags=["company"])
def list_company_names(db: Session = Depends(get_db)):
    rows = db.execute(select(Company.uid, Company.name).order_by(Company.name.asc())).all()
    return [schemas.CompanyName(uid=uid, name=name) for uid, name in rows]


@app.patch("/api/companies/{uid}", response_model=schemas.CompanyOut, tags=["company"])
def update_company(
    payload: schemas.CompanyUpdate,
    uid: str = Path(..., min_length=4, max_length=32),
    db: Session = Depends(get_db),
):
    company = db.execute(select(Company).where(Company.uid == uid)).scalar_one_or_none()
    if not company:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Company not found")

    # Unique email check if changing email
    if payload.email and payload.email.lower() != company.email:
        exists_email = db.execute(select(Company).where(Company.email == payload.email.lower())).scalar_one_or_none()
        if exists_email:
            conflict("Company email already exists")

    # Apply changes (only provided fields)
    if payload.company_name is not None:
        company.name = payload.company_name.strip()
    if payload.email is not None:
        company.email = payload.email.lower()
    if payload.phone is not None:
        company.phone = payload.phone.strip()
    if payload.website is not None:
        company.website = payload.website.strip() or None
    if payload.address is not None:
        company.address = payload.address.strip() or None
    if payload.url is not None:
        company.url = payload.url.strip() or None
    if payload.active is not None:
        company.active = bool(payload.active)

    db.commit()
    db.refresh(company)

    return schemas.CompanyOut(
        id=company.id,
        uid=company.uid,
        name=company.name,
        email=company.email,
        phone=company.phone,
        website=company.website,
        address=company.address,
        url=company.url,
        active=company.active,
    )
