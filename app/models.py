from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Boolean, UniqueConstraint, DateTime, func, Index
from .database import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    role: Mapped[int] = mapped_column(Integer, index=True)  # 1=Super Admin, 2=Admin, 3=User

    # Common
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(255), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    # Role-specific (nullable for others)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # for Admin (role 2)
    active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)           # for Admin (role 2)


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("uid", name="uq_companies_uid"),
        UniqueConstraint("email", name="uq_companies_email"),
        Index("ix_companies_name", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uid: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # short, unique, auto
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    url: Mapped[str | None] = mapped_column(String(255), nullable=True)  # allowed empty/NULL
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )