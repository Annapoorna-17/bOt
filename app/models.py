from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    tenant_code = Column(String(64), unique=True, index=True, nullable=False)  # e.g., qwert
    slug_url = Column(String(255), unique=True, nullable=False)  # e.g., https://service.com/qwert
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="company")
    documents = relationship("Document", back_populates="company")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    display_name = Column(String(255), nullable=False)
    user_code = Column(String(64), unique=True, index=True, nullable=False)  # e.g., qwert-uds1
    role = Column(String(32), nullable=False)  # "admin" or "user"
    api_key = Column(String(128), unique=True, nullable=False)  # per-user API key
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="users")
    documents = relationship("Document", back_populates="uploader")

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tenant_code = Column(String(64), index=True, nullable=False)
    user_code = Column(String(64), index=True, nullable=False)
    filename = Column(String(512), nullable=False)  # stored file name e.g., qwert_uds1.pdf
    original_name = Column(String(512), nullable=False)
    mime_type = Column(String(128), nullable=False)
    num_chunks = Column(Integer, default=0)
    status = Column(String(32), default="indexed")  # 'indexed'/'error'
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="documents")
    uploader = relationship("User", back_populates="documents")

    __table_args__ = (
        UniqueConstraint("tenant_code", "filename", name="uq_tenant_filename"),
    )
