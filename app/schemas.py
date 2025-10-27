from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CompanyCreate(BaseModel):
    name: str
    tenant_code: str
    slug_url: Optional[str] = None

class CompanyOut(BaseModel):
    id: int
    name: str
    tenant_code: str
    slug_url: str
    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    tenant_code: str
    display_name: str
    user_code: str
    role: str = Field(pattern="^(admin|user)$")

class UserOut(BaseModel):
    id: int
    display_name: str
    user_code: str
    role: str
    api_key: str
    class Config:
        from_attributes = True

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
    num_chunks: int
    status: str
    created_at: datetime
    error_message: Optional[str] = None
    class Config:
        from_attributes = True
