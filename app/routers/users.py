# app/routers/users.py
import os
import uuid
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
from PIL import Image

from ..db import get_db
from ..models import User
from ..schemas import UserCreate, UserOut, UserUpdate, AdminUserUpdate
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
        firstname=payload.firstname,
        lastname=payload.lastname,
        email=payload.email,
        contact_number=payload.contact_number,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        country=payload.country
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.get("", response_model=List[UserOut])
def list_users(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    include_inactive: bool = False
):
    """
    List users.
    - Superadmins can see all users across all tenants.
    - Admins can only see users within their own tenant.
    By default, only active users are returned. Use ?include_inactive=true to see all.
    """
    
    # 1. Start the base query (no filters yet)
    users_query = db.query(models.User) # <-- Start with just the User model

    # 2. Conditionally apply tenant filter based on role
    if current_user.role != "superadmin":
        # If NOT superadmin, restrict to their own company
        users_query = users_query.filter(models.User.company_id == current_user.company_id)
    
    # 3. Conditionally apply active filter
    if not include_inactive:
        users_query = users_query.filter(models.User.is_active == True) 

    # 4. Apply ordering and execute the query
    users = users_query.order_by(models.User.created_at.desc()).all()

    # 5. Format the result
    result = []
    for user in users:
        user_dict = {
            "id": user.id,
            "display_name": user.display_name,
            "user_code": user.user_code,
            "role": user.role,
            "api_key": user.api_key, 
            "email": user.email if user.email else None,
            "api_key": user.api_key,
            # Convert empty string to None for proper validation
            "email": user.email if user.email else None,
            "firstname": user.firstname,
            "lastname": user.lastname,            
            "contact_number": user.contact_number,
            "profile_image": user.profile_image,
            "company_name": user.company.name if user.company else None,
            
            "address": user.address,
            "city": user.city,
            "state": user.state,
            "country": user.country
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

# ============================================================
# --- NEW ADMIN-SPECIFIC USER MANAGEMENT ENDPOINTS START HERE ---
# ============================================================

@router.get("/{user_id}", response_model=UserOut)
def get_user_by_id(
    user_id: int,
    current_user: models.User = Depends(get_current_user), # Authenticates and gets user
    db: Session = Depends(get_db),
):
    """
    Get details for a specific user by ID.
    - Admins can only view users within their own tenant.
    - Superadmins can view users from any tenant.
    """
    # Role check (Admin or Superadmin required)
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Superadmin role required to view other user details"
        )

    # Find the target user
    target_user = db.query(models.User).filter(models.User.id == user_id).first()

    # Check if user exists
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # --- MODIFIED Tenant Isolation Check ---
    # Allow superadmin to bypass tenant check
    if current_user.role != "superadmin":
        if target_user.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot view users from another tenant"
            )
    # --- END MODIFICATION ---

    return target_user


@router.put("/{user_id}", response_model=UserOut)
def update_user_by_id(
    user_id: int,
    payload: AdminUserUpdate, # Use the schema for admin updates
    current_user: models.User = Depends(get_current_user), # Authenticates and gets user
    db: Session = Depends(get_db),
):
    """
    Update another user's details by ID.
    - Admins can only update users within their own tenant.
    - Superadmins can update users from any tenant.
    Admins/Superadmins cannot modify themselves via this endpoint.
    """
    # Role check (Admin or Superadmin required)
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Superadmin role required to update users"
        )

    # Find the target user
    target_user = db.query(models.User).filter(models.User.id == user_id).first()

    # Check if user exists
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # --- MODIFIED Tenant Isolation Check ---
    # Allow superadmin to bypass tenant check
    if current_user.role != "superadmin":
        if target_user.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot update users from another tenant"
            )
    # --- END MODIFICATION ---

    # Prevent modifying self via this endpoint
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify your own account using this endpoint. Use PUT /users/me instead."
        )

    # --- Business Logic Checks (Keep or Adjust as needed) ---
    # Example: Prevent removing the last admin in the *target* tenant
    if payload.role == 'user' and target_user.role == 'admin':
        # Count other admins in the *target user's* company
        admin_count = db.query(User).filter(
            User.company_id == target_user.company_id, # Check in target tenant
            User.role == 'admin',
            User.id != target_user.id
        ).count()
        if admin_count == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the last admin role from the target tenant.")
    # --- End Business Logic Checks ---

    # Update fields present in the payload
    update_data = payload.dict(exclude_unset=True)
    updated = False
    for key, value in update_data.items():
        if hasattr(target_user, key):
            # Special handling for role if needed (e.g., logging role changes)
            # if key == 'role' and value != target_user.role:
            #    print(f"Admin {current_user.user_code} changing role of user {target_user.user_code} to {value}")
            setattr(target_user, key, value)
            updated = True

    if updated:
        try:
            db.commit()
            db.refresh(target_user)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to update user: {e}")

    return target_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_user_by_id( # Renamed function for clarity (optional)
    user_id: int,
    current_user: models.User = Depends(get_current_user), # Authenticates and gets admin/superadmin
    db: Session = Depends(get_db),
):
    """
    Soft delete (deactivate) a user by ID. Admin/Superadmin only.
    Admins/Superadmins cannot deactivate themselves using this endpoint.
    Documents and websites uploaded by the user remain associated.
    """
    # Role check (Admin or Superadmin required)
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Superadmin role required to deactivate users"
        )

    # Find the target user
    target_user = db.query(models.User).filter(models.User.id == user_id).first()

    # Check if user exists
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Tenant Isolation Check (Allow superadmin to bypass)
    if current_user.role != "superadmin":
        if target_user.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot deactivate users from another tenant"
            )

    # CRITICAL: Prevent deleting self
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account via this endpoint."
        )

    # --- Soft Delete Logic ---
    if target_user.is_active:
        target_user.is_active = False
        try:
            # Optional: Clear sensitive data like API key or hashed_password if needed upon deactivation
            # target_user.api_key = None
            # target_user.hashed_password = None # Be careful if you need reactivation

            db.commit()
            print(f"User {target_user.user_code} (ID: {user_id}) deactivated.") # Optional logging
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to deactivate user: {e}")
    else:
        # User is already inactive, maybe return success or a specific message
        print(f"User {target_user.user_code} (ID: {user_id}) is already inactive.") # Optional logging
        pass # Still return 204

    # No need to delete profile image file for soft delete

    return None

# ============================================================
# --- END OF NEW ADMIN-SPECIFIC ENDPOINTS ---
# ============================================================




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
    if payload.firstname is not None:
        current_user.firstname = payload.firstname
    if payload.lastname is not None:
        current_user.lastname = payload.lastname
    if payload.email is not None:
        current_user.email = payload.email
    
    if payload.contact_number is not None:
        current_user.contact_number = payload.contact_number
    if payload.firstname is not None:
        current_user.firstname = payload.firstname
    if payload.lastname is not None:
        current_user.lastname = payload.lastname
    if payload.address is not None:
        current_user.address = payload.address
    if payload.city is not None:
        current_user.city = payload.city
    if payload.state is not None:
        current_user.state = payload.state
    if payload.country is not None:
        current_user.country = payload.country

    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/image")
def get_profile_image(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get your profile image.
    Returns the image file with proper content type headers.

    This endpoint provides the same functionality as the static file endpoint
    but with authentication and returns the actual image file.
    """
    if not current_user.profile_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile image found"
        )

    # Build file path
    filepath = os.path.join(PROFILE_IMAGES_DIR, current_user.profile_image)

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile image file not found on server"
        )

    # Determine media type from file extension
    file_ext = os.path.splitext(current_user.profile_image)[1].lower()
    media_type_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp"
    }
    media_type = media_type_map.get(file_ext, "application/octet-stream")

    # Return the file with metadata in headers
    return FileResponse(
        path=filepath,
        media_type=media_type,
        filename=current_user.profile_image,
        headers={
            "X-User-Code": current_user.user_code,
            "X-Display-Name": current_user.display_name,
            "X-Profile-Image-Filename": current_user.profile_image
        }
    )


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
