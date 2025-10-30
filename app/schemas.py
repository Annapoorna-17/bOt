from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

class CompanyCreate(BaseModel):
    name: str
    tenant_code: str
    slug_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

class CompanyOut(BaseModel):
    id: int
    name: str
    tenant_code: str
    slug_url: str
    widget_key: Optional[str] = None

    email: Optional[str] = None
    phone: Optional[str] = None
    # website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    display_name: str
    user_code: str
    role: str = Field(pattern="^(superadmin|admin|user)$")

    # --- FIELD ADDED ---
    # Added email to base, as it's common
    email: EmailStr


class UserCreate(BaseModel):
    tenant_code: str
    display_name: str
    user_code: str
    role: str = Field(pattern="^(superadmin|admin|user)$")

     # NEW FIELDS
    email: EmailStr  # <--- 2. CHANGED to EmailStr for consistency
    contact_number: Optional[str] = None
    # website: Optional[str] = None

    # --- FIELD ADDED FOR AUTH ---
    # Add password field for registration
    password: str
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    contact_number: Optional[str] = None
    address: Optional[str] = None # Deprecated
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

class UserOut(BaseModel):
    id: int
    display_name: str
    user_code: str
    role: str

    # --- FIELD MODIFIED FOR AUTH ---
    # Made api_key optional, as password-users might not have one
    api_key: Optional[str] = None

    # NEW FIELDS
    # Made email optional to handle older records with empty/null email values
    email: Optional[EmailStr] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    contact_number: Optional[str] = None
    profile_image: Optional[str] = None
    company_name: Optional[str] = None  # Added for list users response
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating user profile information."""
    display_name: Optional[str] = None
    email: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    contact_number: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

    class Config:
        from_attributes = True


# --- NEW SCHEMA ADDED FOR ADMIN UPDATES ---
class AdminUserUpdate(BaseModel):
    """Schema for an admin updating another user's profile information."""
    display_name: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(admin|user)$") # Allow role changes
    address: Optional[str] = None
    contact_number: Optional[str] = None
    is_active: Optional[bool] = None # Optional: Allow admin to activate/deactivate

    # Note: Exclude fields admins shouldn't change directly, like email or password.
    # Password changes should go through the reset flow.

    class Config:
        from_attributes = True
# --- END OF NEW SCHEMA ---


# --- NEW SCHEMAS ADDED FOR AUTHENTICATION ---

class Token(BaseModel):
    """Schema for the login response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Schema for the data encoded in the JWT."""
    sub: str # 'sub' is standard for 'subject', we'll use user's email
    type: str # We'll use this to differentiate 'access' vs 'refresh'

class PasswordResetRequest(BaseModel):
    """Schema for requesting a password reset."""
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    """Schema for confirming the password reset."""
    new_password: str

class SuperadminCreate(BaseModel):
    """Schema for creating a superadmin user. Does not require tenant_code as it uses a reserved system tenant."""
    display_name: str
    user_code: str
    email: EmailStr
    password: str
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    address: Optional[str] = None
    contact_number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

# --- END OF NEW SCHEMAS ---


class UploadResponse(BaseModel):
    document_id: int
    stored_filename: str
    chunks_indexed: int

class QueryRequest(BaseModel):
    question: str
    top_k: int = 8
    user_filter: bool = False  # if True, filter by uploader user_code too

class QueryAnswer(BaseModel):
    answer: str
    sources: List[str]

class DocumentOut(BaseModel):
    id: int
    filename: str
    original_name: str
    uploader_id: int
    user_code: str  # Added user_code field
    num_chunks: int
    status: str
    created_at: datetime
    error_message: Optional[str] = None
    class Config:
        from_attributes = True

class WebsiteSubmit(BaseModel):
    url: str

class WebsiteResponse(BaseModel):
    website_id: int
    url: str
    title: str
    chunks_indexed: int

class WebsiteOut(BaseModel):
    id: int
    url: str
    title: Optional[str]
    uploader_id: int
    user_code: str  # Added user_code field
    num_chunks: int
    status: str
    created_at: datetime
    error_message: Optional[str] = None
    class Config:
        from_attributes = True
