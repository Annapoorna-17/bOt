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
import hashlib
import io
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Header
from sqlalchemy.orm import Session
from secrets import token_urlsafe
from PIL import Image
from ..db import get_db
from ..models import Document, User, Website
from ..security import require_caller_with_tenant_in_path, require_admin_with_tenant_in_path, Caller
from ..schemas import (
    UploadResponse, DocumentOut, QueryRequest, QueryAnswer,
    UserCreate, UserOut, UserUpdate, WebsiteSubmit, WebsiteResponse, WebsiteOut
)
from ..rag import document_to_pinecone, search, synthesize_answer
from ..scraper import scrape_and_index_website

UPLOAD_DIR = "uploaded_documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    '.pdf', '.docx', '.doc', '.xlsx', '.xls',
    '.pptx', '.ppt', '.txt', '.csv', '.md',
    '.rst', '.log'
}

PROFILE_IMAGES_DIR = "profile_images"
os.makedirs(PROFILE_IMAGES_DIR, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_IMAGE_SIZE_MB = 5

router = APIRouter(prefix="/t", tags=["Tenant-Scoped API"])

# ============ Document Endpoints ============

@router.post("/{tenant_code}/documents/upload", response_model=UploadResponse)
def upload_document_tenant(
    tenant_code: str,
    file: UploadFile = File(...),
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """Upload a document for the specified tenant. Supports PDF, DOCX, XLSX, PPTX, CSV, TXT, MD, and more."""
    # Get caller using tenant from path
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)

    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    file_ext = os.path.splitext(file.filename.lower())[1]
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Unique file naming: "<tenant>_<user>_<uuid>.<ext>"
    user_suffix = caller.user.user_code.split('-', 1)[1] if '-' in caller.user.user_code else caller.user.user_code
    unique_id = uuid.uuid4().hex[:8]
    stored_name = f"{caller.tenant.tenant_code}_{user_suffix}_{unique_id}{file_ext}"
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
        mime_type=file.content_type or "application/octet-stream",
        status="indexed",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        chunks = document_to_pinecone(path, caller.tenant.tenant_code, caller.user.user_code, stored_name)
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

# ============ Website Endpoints ============

@router.post("/{tenant_code}/websites/scrape", response_model=WebsiteResponse)
async def scrape_website_tenant(
    tenant_code: str,
    payload: WebsiteSubmit,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """Scrape and index a website for the specified tenant. Now uses async processing."""
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)

    # Compute URL hash for uniqueness checking
    url_hash = hashlib.sha256(payload.url.encode()).hexdigest()

    # Check if URL already exists for this tenant
    existing = db.query(Website).filter(
        Website.company_id == caller.tenant.id,
        Website.url_hash == url_hash
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="This website has already been scraped by your tenant. Delete the old entry first if you want to re-scrape."
        )

    # Create website record
    website = Website(
        company_id=caller.tenant.id,
        uploader_id=caller.user.id,
        tenant_code=caller.tenant.tenant_code,
        user_code=caller.user.user_code,
        url=payload.url,
        url_hash=url_hash,
        status="indexed",
    )
    db.add(website)
    db.commit()
    db.refresh(website)

    # Scrape and index (now async with concurrent image processing)
    try:
        title, chunks = await scrape_and_index_website(
            url=payload.url,
            tenant_code=caller.tenant.tenant_code,
            user_code=caller.user.user_code,
            max_images=10,  # Process up to 10 images
            max_concurrent_images=3  # Process 3 images at a time
        )
        website.title = title
        website.num_chunks = chunks
        db.commit()
    except Exception as e:
        website.status = "error"
        website.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Scraping/indexing failed: {e}")

    return WebsiteResponse(
        website_id=website.id,
        url=website.url,
        title=website.title or "",
        chunks_indexed=website.num_chunks
    )

@router.get("/{tenant_code}/websites", response_model=List[WebsiteOut])
def list_websites_tenant(
    tenant_code: str,
    my_websites_only: bool = False,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """List websites for the specified tenant."""
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)

    query = db.query(Website).filter(Website.company_id == caller.tenant.id)

    if my_websites_only or caller.user.role != "admin":
        query = query.filter(Website.uploader_id == caller.user.id)

    return query.order_by(Website.created_at.desc()).all()

@router.delete("/{tenant_code}/websites/{website_id}")
def delete_website_tenant(
    tenant_code: str,
    website_id: int,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """Delete a website from the specified tenant."""
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)

    website = db.query(Website).filter(Website.id == website_id).first()

    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    if website.company_id != caller.tenant.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: This website belongs to a different tenant"
        )

    if website.uploader_id != caller.user.id and caller.user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only delete your own websites unless you are an admin"
        )

    # Delete from database (vectors stay in Pinecone but won't be listed)
    db.delete(website)
    db.commit()

    return {"message": "Website deleted successfully", "website_id": website_id}

# ============ Query Endpoint ============

@router.post("/{tenant_code}/query", response_model=QueryAnswer)
def query_tenant(
    tenant_code: str,
    payload: QueryRequest,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """Query documents and websites for the specified tenant."""
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

    # Handle both document and website sources
    sources = []
    for m in matches:
        if m.metadata:
            source_type = m.metadata.get("source_type", "document")
            if source_type == "website":
                sources.append(m.metadata.get("url", "unknown"))
            else:
                sources.append(m.metadata.get("doc", "unknown"))

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
        email=payload.email,
        address=payload.address,
        contact_number=payload.contact_number,
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


@router.put("/{tenant_code}/users/me", response_model=UserOut)
def update_current_user_tenant(
    tenant_code: str,
    payload: UserUpdate,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """
    Update the current authenticated user's profile information.
    Users can update: display_name, email, address, contact_number
    """
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)
    user = caller.user

    # Check if email is being changed and if it's already taken
    if payload.email and payload.email != user.email:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use by another user")

    # Update fields if provided
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.email is not None:
        user.email = payload.email
    if payload.address is not None:
        user.address = payload.address
    if payload.contact_number is not None:
        user.contact_number = payload.contact_number

    db.commit()
    db.refresh(user)
    return user


def _validate_and_save_profile_image(file: UploadFile, user_code: str) -> str:
    """
    Validate image file and save it to disk.
    Returns the filename of the saved image.
    """
    # Check file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )

    # Read file content
    content = file.file.read()

    # Check if content is empty
    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty"
        )

    # Check file size (max 5MB)
    if len(content) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_IMAGE_SIZE_MB}MB"
        )

    # Validate it's actually an image using BytesIO
    try:
        img_io = io.BytesIO(content)
        img = Image.open(img_io)
        img.verify()  # Verify it's a valid image

        # Re-open for actual processing (verify corrupts the image object)
        img_io = io.BytesIO(content)
        img = Image.open(img_io)
    except Exception as e:
        # Provide helpful error message about actual file type
        if content[:4] == b'\x00\x00\x00\x1c' or b'ftyp' in content[:20]:
            raise HTTPException(
                status_code=400,
                detail="File appears to be AVIF/HEIF format. Please convert to JPG, PNG, GIF, or WEBP."
            )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid or corrupted image file. Please ensure it's a valid JPG, PNG, GIF, or WEBP image."
        )

    # Generate unique filename
    unique_id = uuid.uuid4().hex[:12]
    filename = f"{user_code}_{unique_id}{file_ext}"
    filepath = os.path.join(PROFILE_IMAGES_DIR, filename)

    # Optionally resize image if too large (max 1024x1024)
    max_size = (1024, 1024)
    if img.width > max_size[0] or img.height > max_size[1]:
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

    # Convert RGBA to RGB if needed (for JPEG)
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background

    # Save image
    img.save(filepath, quality=85, optimize=True)

    return filename


@router.post("/{tenant_code}/users/me/profile-image", response_model=UserOut)
def upload_profile_image_tenant(
    tenant_code: str,
    file: UploadFile = File(...),
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """
    Upload or update the current user's profile image.
    Accepts: JPG, PNG, GIF, WEBP (max 5MB)
    """
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)
    user = caller.user

    # Delete old profile image if exists
    if user.profile_image:
        old_filepath = os.path.join(PROFILE_IMAGES_DIR, user.profile_image)
        if os.path.exists(old_filepath):
            try:
                os.remove(old_filepath)
            except Exception as e:
                print(f"Warning: Could not delete old profile image: {e}")

    # Validate and save new image
    filename = _validate_and_save_profile_image(file, user.user_code)

    # Update user record
    user.profile_image = filename
    db.commit()
    db.refresh(user)

    return user


@router.delete("/{tenant_code}/users/me/profile-image", response_model=UserOut)
def delete_profile_image_tenant(
    tenant_code: str,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """
    Delete the current user's profile image.
    """
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)
    user = caller.user

    if not user.profile_image:
        raise HTTPException(status_code=404, detail="No profile image to delete")

    # Delete physical file
    filepath = os.path.join(PROFILE_IMAGES_DIR, user.profile_image)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Warning: Could not delete profile image file: {e}")

    # Update user record
    user.profile_image = None
    db.commit()
    db.refresh(user)

    return user
