from pydantic import BaseModel, EmailStr, field_validator, model_validator
from typing import Optional

# ----- Registration -----
class RegistrationRequest(BaseModel):
    role: int  # 1=Super Admin, 2=Admin, 3=User

    # Common fields
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None

    # Admin-only
    company_name: Optional[str] = None
    active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def role_must_be_1_2_3(cls, v: int):
        if v not in (1, 2, 3):
            raise ValueError("role must be 1 (Super Admin), 2 (Admin), or 3 (User)")
        return v

    @field_validator("password")
    @classmethod
    def password_basic_check(cls, v: Optional[str]):
        if v is None:
            return v
        if len(v) < 6:
            raise ValueError("password must be at least 6 characters")
        return v

    @model_validator(mode="after")
    def role_specific_requirements(self):
        """
        Cross-field validation after the model is created.
        Enforces required fields based on role.
        """
        def missing(fields):
            return [f for f in fields if getattr(self, f) in (None, "")]

        if self.role in (1, 3):  # Super Admin or User
            required = ["name", "phone", "email", "password"]
            miss = missing(required)
            if miss:
                raise ValueError(f"Missing required fields for role {self.role}: {', '.join(miss)}")

        if self.role == 2:  # Admin
            required = ["company_name", "name", "phone", "email", "password", "active"]
            miss = missing(required)
            if miss:
                raise ValueError(f"Missing required fields for admin (role 2): {', '.join(miss)}")

        return self


class RegistrationResponse(BaseModel):
    id: int
    role: int
    email: EmailStr
    message: str


# ----- Login -----
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    id: int
    role: int
    email: EmailStr
    role_name: str
    message: str

from pydantic import AnyUrl

# ----- Company -----
class CompanyCreate(BaseModel):
    company_name: str
    email: EmailStr
    phone: str
    website: str | None = None  # keep as free string; you can switch to AnyUrl if you want strict validation
    address: str | None = None
    url: str | None = None      # allowed to be empty / null for now
    active: bool = True

class CompanyOut(BaseModel):
    id: int
    uid: str
    name: str
    email: EmailStr
    phone: str
    website: str | None = None
    address: str | None = None
    url: str | None = None
    active: bool
    # created_at commonly included, add if you want:
    # created_at: datetime

class CompanyUpdate(BaseModel):
    company_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    website: str | None = None
    address: str | None = None
    url: str | None = None
    active: bool | None = None

class CompanyName(BaseModel):
    uid: str
    name: str
