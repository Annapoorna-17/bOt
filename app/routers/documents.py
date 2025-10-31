import os,mimetypes
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Document # We get the User model from 'models'
from .. import models          # <--- 1. Import 'models'
from ..schemas import UploadResponse, DocumentOut
from typing import List, Optional
from ..rag import document_to_pinecone
from ..auth import get_current_user  # <--- 2. Import your new auth function
from ..security import require_superadmin  # Import superadmin auth

# --- 3. REMOVED old auth imports (require_caller, require_admin, Caller) ---

UPLOAD_DIR = "uploaded_documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    '.pdf', '.docx', '.doc', '.xlsx', '.xls',
    '.pptx', '.ppt', '.txt', '.csv', '.md',
    '.rst', '.log'
}

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload", response_model=UploadResponse)
def upload_document(
    file: UploadFile = File(...),
    # --- 4. USE the new dependency ---
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    file_ext = os.path.splitext(file.filename.lower())[1]
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # --- 5. UPDATE logic to use 'current_user' ---
    # The 'tenant' is now 'current_user.company'
    user_suffix = current_user.user_code.split('-', 1)[1] if '-' in current_user.user_code else current_user.user_code
    unique_id = uuid.uuid4().hex[:8]
    stored_name = f"{current_user.company.tenant_code}_{user_suffix}_{unique_id}{file_ext}"
    path = os.path.join(UPLOAD_DIR, stored_name)

    content = file.file.read()
    with open(path, "wb") as f:
        f.write(content)

    doc = Document(
        company_id=current_user.company_id,      # <-- Changed
        uploader_id=current_user.id,             # <-- Changed
        tenant_code=current_user.company.tenant_code, # <-- Changed
        user_code=current_user.user_code,        # <-- Changed
        filename=stored_name,
        original_name=file.filename,
        mime_type=file.content_type or "application/octet-stream",
        status="indexed",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        chunks = document_to_pinecone(
            path,
            current_user.company.tenant_code, # <-- Changed
            current_user.user_code,           # <-- Changed
            stored_name
        )
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
    # --- 6. USE new dependency ---
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    my_docs_only: bool = False,
):
    """
    List documents in the tenant.
    - Admins can see all documents in their tenant
    - Regular users can see all tenant docs by default, or set my_docs_only=true to see only their uploads
    """
    # --- 7. UPDATE logic to use 'current_user' ---
    query = db.query(Document).filter(Document.company_id == current_user.company_id) # <-- Changed

    # If user wants only their documents or if they're not an admin
    if my_docs_only or current_user.role not in ["admin", "superadmin"]: # <-- Changed
        query = query.filter(Document.uploader_id == current_user.id) # <-- Changed

    documents = query.order_by(Document.created_at.desc()).all()

    # Add filepath, user name, and company name to each document
    result = []
    for doc in documents:
        doc_dict = {
            "id": doc.id,
            "filename": doc.filename,
            "original_name": doc.original_name,
            "filepath": os.path.join(UPLOAD_DIR, doc.filename),
            "uploader_id": doc.uploader_id,
            "user_code": doc.user_code,
            "user_name": doc.uploader.display_name if doc.uploader else None,
            "company_name": doc.uploader.company.name if doc.uploader and doc.uploader.company else None,
            "num_chunks": doc.num_chunks,
            "status": doc.status,
            "created_at": doc.created_at,
            "error_message": doc.error_message
        }
        result.append(doc_dict)

    return result

@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    # --- 8. USE new dependency ---
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db),
):
    """
    Delete a document. Users can only delete their own documents, admins can delete any document in their tenant.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # --- 9. UPDATE logic to use 'current_user' ---
    # Check tenant isolation
    if doc.company_id != current_user.company_id: # <-- Changed
        raise HTTPException(
            status_code=403,
            detail="Access denied: This document belongs to a different tenant"
        )

    # Check authorization: owner or admin can delete
    if doc.uploader_id != current_user.id and current_user.role not in ["admin", "superadmin"]: # <-- Changed
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


@router.get("/{document_id}/preview")
def preview_document(
    document_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Preview/download a document.
    Users can preview documents in their tenant. Admins can preview any document in their tenant.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check tenant isolation
    if doc.company_id != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: This document belongs to a different tenant"
        )

    # Find the file in the correct directory
    file_path = get_document_path(doc.filename)

    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    # Debug logging
    print(f"DEBUG - Preview request (normal user):")
    print(f"  Document ID: {document_id}")
    print(f"  Filename: {doc.filename}")
    print(f"  UPLOAD_DIR: {UPLOAD_DIR}")
    print(f"  UPLOAD_DIR_PDFS: {UPLOAD_DIR_PDFS}")
    print(f"  Found path: {file_path}")

    # Check if file exists
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="Document file not found on server"
        )

    # Return file for preview/download
    return FileResponse(
        path=file_path,
        filename=doc.original_name,  # Use original filename for download
        media_type=mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{doc.original_name}"',  # 👈 allows preview
            "Accept-Ranges": "bytes",  # allows partial loading
        }
    )


@router.get("/superadmin/all", response_model=List[DocumentOut], dependencies=[Depends(require_superadmin)])
def list_all_documents_superadmin(
    db: Session = Depends(get_db),
    tenant_code: Optional[str] = None,
):
    """
    List all documents across all companies. Superadmin only.

    Query Parameters:
    - tenant_code: Optional filter to show documents from a specific company by tenant code
    """
    query = db.query(Document)

    # Filter by tenant code if provided
    if tenant_code:
        query = query.join(Document.uploader).join(models.User.company).filter(
            models.Company.tenant_code == tenant_code
        )

    documents = query.order_by(Document.created_at.desc()).all()

    # Build response with user name and company name
    result = []
    for doc in documents:
        doc_dict = {
            "id": doc.id,
            "filename": doc.filename,
            "original_name": doc.original_name,
            "filepath": os.path.join(UPLOAD_DIR, doc.filename),
            "uploader_id": doc.uploader_id,
            "user_code": doc.user_code,
            "user_name": doc.uploader.display_name if doc.uploader else None,
            "company_name": doc.uploader.company.name if doc.uploader and doc.uploader.company else None,
            "num_chunks": doc.num_chunks,
            "status": doc.status,
            "created_at": doc.created_at,
            "error_message": doc.error_message
        }
        result.append(doc_dict)

    return result


@router.get("/superadmin/{document_id}/preview", dependencies=[Depends(require_superadmin)])
def preview_document_superadmin(
    document_id: int,
    db: Session = Depends(get_db),
):
    """
    Preview/download any document. Superadmin only.
    Allows superadmin to preview documents from any company.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Find the file in the correct directory
    file_path = get_document_path(doc.filename)

    # Guess MIME type based on file extension
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    # Debug logging
    print(f"DEBUG - Preview request (superadmin):")
    print(f"  Document ID: {document_id}")
    print(f"  Filename: {doc.filename}")
    print(f"  UPLOAD_DIR: {UPLOAD_DIR}")
    print(f"  UPLOAD_DIR_PDFS: {UPLOAD_DIR_PDFS}")
    print(f"  Found path: {file_path}")

    # Check if file exists
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="Document file not found on server"
        )

    # Return file for preview/download
    return FileResponse(
        path=file_path,
        filename=doc.original_name,  # Use original filename for download
        media_type=mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{doc.original_name}"',  # 👈 allows preview
            "Accept-Ranges": "bytes",  # allows partial loading
        }
    )

