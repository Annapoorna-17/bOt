# app/routers/users.py
import os
import uuid
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from typing import List
from PIL import Image

from ..db import get_db
from ..models import User
from ..schemas import UserCreate, UserOut, UserUpdate
from ..auth import get_current_user, hash_password
from ..security import SUPERADMIN_SYSTEM_TENANT
from .. import models

router = APIRouter(prefix="/users", tags=["Users"])

# Directory for storing profile images
PROFILE_IMAGES_DIR = "profile_images"
os.makedirs(PROFILE_IMAGES_DIR, exist_ok=True)

# Allowed image extensions
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_IMAGE_SIZE_MB = 5


# ============================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================

@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new user. Only admins can do this.
    Requires: Bearer token authentication
    """
    # Check if current user is an admin or superadmin
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create users"
        )

    # Prevent creating users in the reserved superadmin tenant
    if payload.tenant_code.upper() == SUPERADMIN_SYSTEM_TENANT.upper():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot create users in the reserved tenant '{SUPERADMIN_SYSTEM_TENANT}'. Use POST /superadmin/companies/superadmin to create superadmin users."
        )

    # Verify tenant matches
    if current_user.company.tenant_code != payload.tenant_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create user in another tenant"
        )

    if not payload.user_code.startswith(payload.tenant_code + "-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_code must start with '<tenant_code>-'"
        )

    # Check if email or user_code already exists
    existing = db.query(User).filter(
        (User.email == payload.email) | (User.user_code == payload.user_code)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email or user_code already exists"
        )

    # Hash password
    hashed_pass = hash_password(payload.password)

    u = User(
        company_id=current_user.company_id,
        display_name=payload.display_name,
        user_code=payload.user_code,
        role=payload.role,
        hashed_password=hashed_pass,
        email=payload.email,
        address=payload.address,
        contact_number=payload.contact_number,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.get("", response_model=List[UserOut])
def list_users(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all users in your tenant.
    Any authenticated user can see the user list.
    """
    users = db.query(User).filter(
        User.company_id == current_user.company_id
    ).order_by(User.created_at.desc()).all()

    # Add company_name to each user
    result = []
    for user in users:
        user_dict = {
            "id": user.id,
            "display_name": user.display_name,
            "user_code": user.user_code,
            "role": user.role,
            "api_key": user.api_key,
            "email": user.email,
            "address": user.address,
            "contact_number": user.contact_number,
            "profile_image": user.profile_image,
            "company_name": user.company.name if user.company else None
        }
        result.append(user_dict)

    return result


@router.get("/me", response_model=UserOut)
def get_current_user_info(
    current_user: models.User = Depends(get_current_user)
):
    """
    Get your own user information.
    """
    return current_user


@router.put("/me", response_model=UserOut)
def update_profile(
    payload: UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update your own profile information.
    You can update: display_name, email, address, contact_number
    """
    # Check if email is being changed and if it's already taken
    if payload.email and payload.email != current_user.email:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use by another user"
            )

    # Update fields if provided
    if payload.display_name is not None:
        current_user.display_name = payload.display_name
    if payload.email is not None:
        current_user.email = payload.email
    if payload.address is not None:
        current_user.address = payload.address
    if payload.contact_number is not None:
        current_user.contact_number = payload.contact_number

    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/image", response_model=UserOut)
def upload_profile_image(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload or update your profile image.
    Accepts: JPG, PNG, GIF, WEBP (max 5MB)
    """
    # Delete old profile image if exists
    if current_user.profile_image:
        old_filepath = os.path.join(PROFILE_IMAGES_DIR, current_user.profile_image)
        if os.path.exists(old_filepath):
            try:
                os.remove(old_filepath)
            except Exception as e:
                print(f"Warning: Could not delete old profile image: {e}")

    # Validate and save new image
    filename = _validate_and_save_image(file, current_user.user_code)

    # Update user record
    current_user.profile_image = filename
    db.commit()
    db.refresh(current_user)

    return current_user


@router.delete("/me/image", response_model=UserOut)
def delete_profile_image(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete your profile image.
    """
    if not current_user.profile_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile image to delete"
        )

    # Delete physical file
    filepath = os.path.join(PROFILE_IMAGES_DIR, current_user.profile_image)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Warning: Could not delete profile image file: {e}")

    # Update user record
    current_user.profile_image = None
    db.commit()
    db.refresh(current_user)

    return current_user


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _validate_and_save_image(file: UploadFile, user_code: str) -> str:
    """
    Validate image file and save it to disk.
    Returns the filename of the saved image.
    """
    # Check file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )

    # Read file content
    content = file.file.read()

    # Check if content is empty
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty"
        )

    # Check file size (max 5MB)
    if len(content) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File appears to be AVIF/HEIF format. Please convert to JPG, PNG, GIF, or WEBP."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted image file. Please ensure it's a valid JPG, PNG, GIF, or WEBP image."
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
