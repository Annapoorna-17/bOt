from fastapi import APIRouter, Depends, HTTPException, status
# app/routers/users.py
import os
import uuid
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from PIL import Image
from ..db import get_db
from ..models import Company, User
from ..schemas import UserCreate, UserOut

# --- 1. Import new auth and models ---
from ..auth import get_current_user, hash_password
from .. import models

# --- 2. REMOVED old auth imports (require_admin, require_caller, Caller) ---
from ..schemas import UserCreate, UserOut, UserUpdate
from ..security import require_admin, require_caller, Caller

router = APIRouter(prefix="/users", tags=["Users & Admin"])

# Directory for storing profile images
PROFILE_IMAGES_DIR = "profile_images"
os.makedirs(PROFILE_IMAGES_DIR, exist_ok=True)

# Allowed image extensions
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_IMAGE_SIZE_MB = 5

@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    # --- 3. USE new dependency ---
    current_admin: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db),
):
    """
    Create a new user. Only an 'admin' can do this.
    """
    
    # --- 4. ADD check to ensure current user is an admin ---
    if current_admin.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create users"
        )
    
    # --- 5. UPDATE logic to use 'current_admin' ---
    if current_admin.company.tenant_code != payload.tenant_code:
        raise HTTPException(status_code=403, detail="Cannot create user in another tenant")

    if not payload.user_code.startswith(payload.tenant_code + "-"):
        raise HTTPException(status_code=400, detail="user_code must start with '<tenant_code>-'")

    # Check if email or user_code already exists
    existing = db.query(User).filter(
        (User.email == payload.email) | (User.user_code == payload.user_code)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="User with this email or user_code already exists")

    # --- 6. UPDATE to hash password (no more api_key) ---
    hashed_pass = hash_password(payload.password)

    u = User(
        company_id=current_admin.company_id, # <-- Changed
        display_name=payload.display_name,
        user_code=payload.user_code,
        role=payload.role,
        hashed_password=hashed_pass, # <-- Changed
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
    # --- 7. USE new dependency ---
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db),
):
    """
    List all users in the caller's tenant. Any authenticated user can see the user list.
    """
    # --- 8. UPDATE logic ---
    users = db.query(User).filter(User.company_id == current_user.company_id).order_by(User.created_at.desc()).all()
    return users

@router.get("/me", response_model=UserOut)
def get_logged_in_user(
    # --- 9. USE new dependency ---
    current_user: models.User = Depends(get_current_user)
):
    """
    Get the current authenticated user's information.
    """
    # --- 10. UPDATE logic ---
    return current_user
    return caller.user


@router.put("/me", response_model=UserOut)
def update_current_user(
    payload: UserUpdate,
    caller: Caller = Depends(require_caller),
    db: Session = Depends(get_db),
):
    """
    Update the current authenticated user's profile information.
    Users can update: display_name, email, address, contact_number
    """
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


def _validate_and_save_image(file: UploadFile, user_code: str) -> str:
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


@router.post("/me/profile-image", response_model=UserOut)
def upload_profile_image(
    file: UploadFile = File(...),
    caller: Caller = Depends(require_caller),
    db: Session = Depends(get_db),
):
    """
    Upload or update the current user's profile image.
    Accepts: JPG, PNG, GIF, WEBP (max 5MB)
    """
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
    filename = _validate_and_save_image(file, user.user_code)

    # Update user record
    user.profile_image = filename
    db.commit()
    db.refresh(user)

    return user


@router.delete("/me/profile-image", response_model=UserOut)
def delete_profile_image(
    caller: Caller = Depends(require_caller),
    db: Session = Depends(get_db),
):
    """
    Delete the current user's profile image.
    """
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
