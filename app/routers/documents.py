import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Document
from ..security import require_caller, require_admin, Caller
from ..schemas import UploadResponse, DocumentOut
from typing import List
from ..rag import pdf_to_pinecone

UPLOAD_DIR = "uploaded_pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload", response_model=UploadResponse)
def upload_pdf(
    file: UploadFile = File(...),
    caller: Caller = Depends(require_caller),
    db: Session = Depends(get_db),
):
    # Only admin or active user can upload. If stricter: use require_admin
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Unique file naming: "<tenant>_<user>_<uuid>.pdf" - allows multiple PDFs per user
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

@router.get("", response_model=List[DocumentOut])
def list_documents(
    caller: Caller = Depends(require_caller),
    db: Session = Depends(get_db),
    my_docs_only: bool = False,
):
    """
    List documents in the tenant.
    - Admins can see all documents in their tenant
    - Regular users can see all tenant docs by default, or set my_docs_only=true to see only their uploads
    """
    query = db.query(Document).filter(Document.company_id == caller.tenant.id)

    # If user wants only their documents or if they're not an admin
    if my_docs_only or caller.user.role != "admin":
        query = query.filter(Document.uploader_id == caller.user.id)

    return query.order_by(Document.created_at.desc()).all()

@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    caller: Caller = Depends(require_caller),
    db: Session = Depends(get_db),
):
    """
    Delete a document. Users can only delete their own documents, admins can delete any document in their tenant.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check tenant isolation
    if doc.company_id != caller.tenant.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: This document belongs to a different tenant"
        )

    # Check authorization: owner or admin can delete
    if doc.uploader_id != caller.user.id and caller.user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only delete your own documents unless you are an admin"
        )

    # Delete the physical file
    file_path = os.path.join(UPLOAD_DIR, doc.filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            # Log but don't fail if file deletion fails
            print(f"Warning: Could not delete file {file_path}: {e}")

    # Delete from database
    db.delete(doc)
    db.commit()

    return {"message": "Document deleted successfully", "document_id": document_id}
