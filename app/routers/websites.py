# app/routers/websites.py
import hashlib
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Website
from ..schemas import WebsiteSubmit, WebsiteSubmitBatch, WebsiteResponse, WebsiteBatchResponse, WebsiteOut
from ..auth import get_current_user
from ..security import require_superadmin
from ..scraper import scrape_and_index_website, delete_website_vectors
from .. import models

router = APIRouter(prefix="/websites", tags=["Websites"])


# Background task to process website
async def process_website_background(website_id: int, url: str, tenant_code: str, user_code: str):
    """
    Background task to scrape and index a website, updating its status.
    This allows immediate response to user while processing happens asynchronously.
    """
    from ..db import SessionLocal

    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            print(f"ERROR: Website {website_id} not found for processing")
            return

        # Update status to processing
        website.status = "processing"
        db.commit()

        try:
            # Scrape and index the website
            title, chunks = await scrape_and_index_website(
                url=url,
                tenant_code=tenant_code,
                user_code=user_code,
                max_images=10,
                max_concurrent_images=3
            )

            # Update status to completed
            website.status = "completed"
            website.num_chunks = chunks
            website.title = title
            website.error_message = None
            db.commit()
            print(f"INFO: Successfully processed website {website_id} ({url}): {chunks} chunks")

        except Exception as e:
            # Update status to error
            website.status = "error"
            website.error_message = str(e)
            db.commit()
            print(f"ERROR: Failed to process website {website_id} ({url}): {e}")

    except Exception as e:
        print(f"ERROR: Background processing failed for website {website_id}: {e}")
    finally:
        db.close()


@router.post("/scrape/single", response_model=WebsiteResponse)
async def scrape_single_website(
    payload: WebsiteSubmit,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Scrape and index a single website (backward compatibility endpoint).
    Processing happens in the background.
    Returns immediately with status "pending".
    Use GET /websites to check processing status.
    """
    # Compute URL hash for uniqueness checking
    url_hash = hashlib.sha256(payload.url.encode()).hexdigest()

    # Check if URL already exists for this tenant
    existing = db.query(Website).filter(
        Website.company_id == current_user.company_id,
        Website.url_hash == url_hash
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This website has already been scraped by your tenant. Delete the old entry first if you want to re-scrape."
        )

    # Create website record with "pending" status
    website = Website(
        company_id=current_user.company_id,
        uploader_id=current_user.id,
        tenant_code=current_user.company.tenant_code,
        user_code=current_user.user_code,
        url=payload.url,
        url_hash=url_hash,
        title=None,  # Will be set during processing
        num_chunks=0,
        status="pending",  # Start with pending status
    )
    db.add(website)
    db.commit()
    db.refresh(website)

    # Schedule background processing
    background_tasks.add_task(
        process_website_background,
        website.id,
        payload.url,
        current_user.company.tenant_code,
        current_user.user_code
    )

    return WebsiteResponse(
        website_id=website.id,
        url=website.url,
        title="",  # Will be set during processing
        chunks_indexed=0
    )


@router.post("/scrape", response_model=WebsiteBatchResponse)
async def scrape_websites(
    payload: WebsiteSubmitBatch,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Scrape and index one or multiple websites. Processing happens in the background.
    Returns immediately with status "pending" for each website.
    Use GET /websites to check processing status.
    """
    results = []
    errors = []
    successful = 0

    for url in payload.urls:
        try:
            # Compute URL hash for uniqueness checking
            url_hash = hashlib.sha256(url.encode()).hexdigest()

            # Check if URL already exists for this tenant
            existing = db.query(Website).filter(
                Website.company_id == current_user.company_id,
                Website.url_hash == url_hash
            ).first()

            if existing:
                errors.append({
                    "url": url,
                    "error": "This website has already been scraped by your tenant. Delete the old entry first if you want to re-scrape."
                })
                continue

            # Create website record with "pending" status
            website = Website(
                company_id=current_user.company_id,
                uploader_id=current_user.id,
                tenant_code=current_user.company.tenant_code,
                user_code=current_user.user_code,
                url=url,
                url_hash=url_hash,
                title=None,  # Will be set during processing
                num_chunks=0,
                status="pending",  # Start with pending status
            )
            db.add(website)
            db.commit()
            db.refresh(website)

            # Schedule background processing
            background_tasks.add_task(
                process_website_background,
                website.id,
                url,
                current_user.company.tenant_code,
                current_user.user_code
            )

            results.append(WebsiteResponse(
                website_id=website.id,
                url=website.url,
                title="",  # Will be set during processing
                chunks_indexed=0
            ))
            successful += 1

        except Exception as e:
            errors.append({
                "url": url,
                "error": str(e)
            })

    return WebsiteBatchResponse(
        results=results,
        total=len(payload.urls),
        successful=successful,
        failed=len(errors),
        errors=errors
    )


@router.get("", response_model=List[WebsiteOut])
def list_websites(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    my_websites_only: bool = False,
):
    """
    List scraped websites in your tenant.
    - Admins can see all websites in their tenant
    - Regular users can see all tenant websites by default, or set my_websites_only=true
    """
    query = db.query(Website).filter(Website.company_id == current_user.company_id)

    if my_websites_only or current_user.role not in ["admin", "superadmin"]:
        query = query.filter(Website.uploader_id == current_user.id)

    websites = query.order_by(Website.created_at.desc()).all()

    # Add user name and company name to each website
    result = []
    for website in websites:
        website_dict = {
            "id": website.id,
            "url": website.url,
            "title": website.title,
            "uploader_id": website.uploader_id,
            "user_code": website.user_code,
            "user_name": website.uploader.display_name if website.uploader else None,
            "company_name": website.uploader.company.name if website.uploader and website.uploader.company else None,
            "num_chunks": website.num_chunks,
            "status": website.status,
            "created_at": website.created_at,
            "error_message": website.error_message
        }
        result.append(website_dict)

    return result


@router.delete("/{website_id}")
def delete_website(
    website_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a scraped website.
    Users can only delete their own websites, admins can delete any website in their tenant.
    """
    website = db.query(Website).filter(Website.id == website_id).first()

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found"
        )

    # Check tenant isolation
    if website.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This website belongs to a different tenant"
        )

    # Check authorization: owner or admin can delete
    if website.uploader_id != current_user.id and current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only delete your own websites unless you are an admin"
        )

    # Delete vectors from Pinecone first
    try:
        deleted_vectors = delete_website_vectors(website.tenant_code, website.url)
        print(f"INFO: Deleted {deleted_vectors} vectors from Pinecone for website {website.url}")
    except Exception as e:
        print(f"WARNING: Failed to delete vectors from Pinecone: {e}")
        # Continue with deletion even if Pinecone cleanup fails

    # Delete from database
    db.delete(website)
    db.commit()

    return {"message": "Website deleted successfully", "website_id": website_id}


@router.get("/superadmin/all", response_model=List[WebsiteOut], dependencies=[Depends(require_superadmin)])
def list_all_websites_superadmin(
    db: Session = Depends(get_db),
    tenant_code: Optional[str] = None,
):
    """
    List all websites across all companies. Superadmin only.

    Query Parameters:
    - tenant_code: Optional filter to show websites from a specific company by tenant code
    """
    query = db.query(Website)

    # Filter by tenant code if provided
    if tenant_code:
        query = query.join(Website.uploader).join(models.User.company).filter(
            models.Company.tenant_code == tenant_code
        )

    websites = query.order_by(Website.created_at.desc()).all()

    # Build response with user name and company name
    result = []
    for website in websites:
        website_dict = {
            "id": website.id,
            "url": website.url,
            "title": website.title,
            "uploader_id": website.uploader_id,
            "user_code": website.user_code,
            "user_name": website.uploader.display_name if website.uploader else None,
            "company_name": website.uploader.company.name if website.uploader and website.uploader.company else None,
            "num_chunks": website.num_chunks,
            "status": website.status,
            "created_at": website.created_at,
            "error_message": website.error_message
        }
        result.append(website_dict)

    return result
