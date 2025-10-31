# app/routers/websites.py
import hashlib
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Website
from ..schemas import WebsiteSubmit, WebsiteResponse, WebsiteOut
from ..auth import get_current_user
from ..security import require_superadmin
from ..scraper import scrape_and_index_website
from .. import models

router = APIRouter(prefix="/websites", tags=["Websites"])


@router.post("/scrape", response_model=WebsiteResponse)
async def scrape_website(
    payload: WebsiteSubmit,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Scrape and index a website.
    Extracts text and analyzes images using GPT-4 Vision.
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

    # Scrape and index FIRST to validate the URL (async with concurrent image processing)
    try:
        title, chunks = await scrape_and_index_website(
            url=payload.url,
            tenant_code=current_user.company.tenant_code,
            user_code=current_user.user_code,
            max_images=10,  # Process up to 10 images
            max_concurrent_images=3  # Process 3 images at a time
        )
    except Exception as e:
        # URL is invalid or scraping failed - don't save to database
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scraping failed: {e}"
        )

    # Only create website record if scraping succeeded
    website = Website(
        company_id=current_user.company_id,
        uploader_id=current_user.id,
        tenant_code=current_user.company.tenant_code,
        user_code=current_user.user_code,
        url=payload.url,
        url_hash=url_hash,
        title=title,
        num_chunks=chunks,
        status="indexed",
    )
    db.add(website)
    db.commit()
    db.refresh(website)

    return WebsiteResponse(
        website_id=website.id,
        url=website.url,
        title=website.title or "",
        chunks_indexed=website.num_chunks
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

    # Delete from database (vectors stay in Pinecone but won't be listed)
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
