from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import timedelta

# Import all your helper functions, models, and schemas
# (Adjust paths if your structure is different)
from .. import schemas, models, auth
from ..db import get_db
from ..security import SUPERADMIN_SYSTEM_TENANT

router = APIRouter(
    prefix="/auth",  # All routes in this file will start with /auth
    tags=["Authentication"] # This groups them in your API docs
)

# -----------------------------------------------
# Endpoint 1: Register New User
# -----------------------------------------------
@router.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register_user(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.
    """
    # Prevent registering users in the reserved superadmin tenant
    if user_data.tenant_code.upper() == SUPERADMIN_SYSTEM_TENANT.upper():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot register users in the reserved tenant '{SUPERADMIN_SYSTEM_TENANT}'. Use POST /superadmin/companies/superadmin to create superadmin users."
        )

    # Check if user already exists
    db_user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if tenant exists
    company = db.query(models.Company).filter(models.Company.tenant_code == user_data.tenant_code).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant with code '{user_data.tenant_code}' not found."
        )

    # Hash the password
    hashed_password = auth.hash_password(user_data.password)
    
    # Create new user
    new_user = models.User(
        email=user_data.email,
        hashed_password=hashed_password,
        company_id=company.id,
        display_name=user_data.display_name,
        user_code=user_data.user_code,
        role=user_data.role,
        address=user_data.address,
        contact_number=user_data.contact_number,
        is_active=True  # Activate user on creation
    )
    
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create user. Error: {str(e)}"
        )
    
    return new_user

# -----------------------------------------------
# Endpoint 2: Login
# -----------------------------------------------
@router.post("/login", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """
    Log in a user. Uses OAuth2 form data (username & password).
    Note: The 'username' field is actually the user's email.
    """
    # Find user by email
    user = db.query(models.User).filter(models.User.email == form_data.username).first()

    # Check if user exists and password is correct
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )
    
    # Data to encode in the tokens
    token_data = {"sub": user.email}
    
    # Create tokens
    access_token = auth.create_access_token(data=token_data)
    refresh_token = auth.create_refresh_token(data=token_data)
    
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token, 
        "token_type": "bearer"
    }

# -----------------------------------------------
# Endpoint 3: Refresh Token
# -----------------------------------------------
@router.post("/refresh-token", response_model=schemas.Token)
def refresh_access_token(refresh_token: str, db: Session = Depends(get_db)):
    """
    Use a refresh token to get a new access token and a new refresh token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(refresh_token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        
        # Check if it's a refresh token
        if payload.get("type") != "refresh":
            raise credentials_exception
            
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None or not user.is_active:
        raise credentials_exception
    
    # Issue new tokens
    new_token_data = {"sub": user.email}
    new_access_token = auth.create_access_token(data=new_token_data)
    new_refresh_token = auth.create_refresh_token(data=new_token_data)
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }

# -----------------------------------------------
# Endpoint 4: Request Password Reset
# -----------------------------------------------
@router.post("/request-password-reset")
def request_password_reset(
    request: schemas.PasswordResetRequest, 
    db: Session = Depends(get_db)
):
    """
    User requests a password reset.
    In a real app, this would email them a token.
    """
    user = db.query(models.User).filter(models.User.email == request.email).first()
    
    # Don't reveal if the user exists or not for security.
    if not user:
        return {"msg": "If an account with this email exists, a reset link has been sent."}

    # Create a special, short-lived token for password reset
    reset_token_expires = timedelta(minutes=15) # 15 minutes
    reset_data = {"sub": user.email, "type": "reset"}
    
    password_reset_token = auth.create_access_token(
        data=reset_data, expires_delta=reset_token_expires
    )
    
    #
    # --- !! IN A REAL APP, EMAIL THIS TOKEN !! ---
    # You would use a service like SendGrid, Mailgun, or smtplib
    # print(f"Password reset link: http://your-frontend.com/reset-password?token={password_reset_token}")
    #
    
    # For now, we return the token directly so you can test.
    # In production, just return the message.
    return {
        "msg": "Password reset token generated. In a real app, this would be emailed.",
        "reset_token": password_reset_token
    }

# -----------------------------------------------
# Endpoint 5: Confirm Password Reset
# -----------------------------------------------
@router.post("/reset-password")
def reset_password(
    token: str, 
    request: schemas.PasswordResetConfirm, 
    db: Session = Depends(get_db)
):
    """
    Reset a user's password using a valid reset token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate token. It may be invalid or expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        
        # Check if it's a reset token
        if payload.get("type") != "reset":
            raise credentials_exception
            
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
            
    except JWTError: # Catches expired tokens
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
        
    # All checks passed. Hash and set the new password.
    hashed_password = auth.hash_password(request.new_password)
    user.hashed_password = hashed_password
    db.commit()
    
    return {"msg": "Password has been reset successfully."}