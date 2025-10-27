# app/routers/tenant.py
"""
Tenant-scoped routes with tenant_code in URL path.
This makes the API more RESTful and easier for frontend integration.

Example URLs:
  - POST /t/qwert/documents/upload
  - GET  /t/qwert/documents
  - POST /t/qwert/query
  - GET  /t/qwert/users
"""
import os
import uuid
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Header
from sqlalchemy.orm import Session
from secrets import token_urlsafe
from ..db import get_db
from ..models import Document, User
from ..security import require_caller_with_tenant_in_path, require_admin_with_tenant_in_path, Caller
from ..schemas import UploadResponse, DocumentOut, QueryRequest, QueryAnswer, UserCreate, UserOut
from ..rag import pdf_to_pinecone, search, synthesize_answer

UPLOAD_DIR = "uploaded_pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/t", tags=["Tenant-Scoped API"])

# ============ Document Endpoints ============

@router.post("/{tenant_code}/documents/upload", response_model=UploadResponse)
def upload_pdf_tenant(
    tenant_code: str,
    file: UploadFile = File(...),
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """Upload a PDF document for the specified tenant."""
    # Get caller using tenant from path
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Unique file naming: "<tenant>_<user>_<uuid>.pdf"
    user_suffix = caller.user.user_code.split('-', 1)[1] if '-' in caller.user.user_code else caller.user.user_code
    unique_id = uuid.uuid4().hex[:8]
    stored_name = f"{caller.tenant.tenant_code}_{user_suffix}_{unique_id}.pdf"
    path = os.path.join(UPLOAD_DIR, stored_name)

    content = file.file.read()
    with open(path, "wb") as f:
        f.write(content)

    doc = Document(
        company_id=caller.tenant.id,
        uploader_id=caller.user.id,
        tenant_code=caller.tenant.tenant_code,
        user_code=caller.user.user_code,
        filename=stored_name,
        original_name=file.filename,
        mime_type=file.content_type or "application/pdf",
        status="indexed",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        chunks = pdf_to_pinecone(path, caller.tenant.tenant_code, caller.user.user_code, stored_name)
        doc.num_chunks = chunks
        db.commit()
    except Exception as e:
        doc.status = "error"
        doc.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")

    return UploadResponse(document_id=doc.id, stored_filename=stored_name, chunks_indexed=doc.num_chunks)

@router.get("/{tenant_code}/documents", response_model=List[DocumentOut])
def list_documents_tenant(
    tenant_code: str,
    my_docs_only: bool = False,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """List documents for the specified tenant."""
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)

    query = db.query(Document).filter(Document.company_id == caller.tenant.id)

    if my_docs_only or caller.user.role != "admin":
        query = query.filter(Document.uploader_id == caller.user.id)

    return query.order_by(Document.created_at.desc()).all()

@router.delete("/{tenant_code}/documents/{document_id}")
def delete_document_tenant(
    tenant_code: str,
    document_id: int,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """Delete a document from the specified tenant."""
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)

    doc = db.query(Document).filter(Document.id == document_id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.company_id != caller.tenant.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: This document belongs to a different tenant"
        )

    if doc.uploader_id != caller.user.id and caller.user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only delete your own documents unless you are an admin"
        )

    # Delete physical file
    file_path = os.path.join(UPLOAD_DIR, doc.filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Warning: Could not delete file {file_path}: {e}")

    db.delete(doc)
    db.commit()

    return {"message": "Document deleted successfully", "document_id": document_id}

# ============ Query Endpoint ============

@router.post("/{tenant_code}/query", response_model=QueryAnswer)
def query_tenant(
    tenant_code: str,
    payload: QueryRequest,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """Query documents for the specified tenant."""
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)

    matches = search(
        tenant_code=caller.tenant.tenant_code,
        query=payload.question,
        top_k=payload.top_k,
        filter_user_code=caller.user.user_code if payload.user_filter else None
    )

    if not matches:
        return QueryAnswer(answer="I don't have enough information to answer that.", sources=[])

    contexts = [m.metadata.get("text", "") for m in matches if m.metadata]
    sources = [m.metadata.get("doc", "unknown") for m in matches if m.metadata]
    answer = synthesize_answer(payload.question, contexts)

    return QueryAnswer(answer=answer, sources=sources[:payload.top_k])

# ============ User Endpoints ============

@router.get("/{tenant_code}/users", response_model=List[UserOut])
def list_users_tenant(
    tenant_code: str,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """List all users for the specified tenant."""
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)

    users = db.query(User).filter(User.company_id == caller.tenant.id).order_by(User.created_at.desc()).all()
    return users

@router.post("/{tenant_code}/users", response_model=UserOut)
def create_user_tenant(
    tenant_code: str,
    payload: UserCreate,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """Create a new user for the specified tenant. Admin only."""
    caller = require_admin_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)

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

@router.get("/{tenant_code}/users/me", response_model=UserOut)
def get_current_user_tenant(
    tenant_code: str,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """Get the current authenticated user's information."""
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)
    return caller.user
