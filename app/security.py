from fastapi import Header, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from os import getenv
from .db import get_db
from .models import User, Company

SUPERADMIN_TOKEN = getenv("SUPERADMIN_TOKEN", "B946C6F2747914D24C1F6C74F5AB5291")

# Security schemes (Swagger will show both)
bearer_scheme = HTTPBearer(auto_error=False)
basic_scheme = HTTPBasic(auto_error=False)

class Caller:
    def __init__(self, user: User, tenant: Company):
        self.user = user
        self.tenant = tenant

def require_superadmin(
    bearer: HTTPAuthorizationCredentials = Security(bearer_scheme),
    basic: HTTPBasicCredentials = Security(basic_scheme),
):
    """
    Allow EITHER:
      - Bearer <SUPERADMIN_TOKEN>
      - Basic auth with username 'stixis' and password 'password'
    """
    # 1) Try Bearer (valid if matches env token)
    if bearer and (bearer.scheme or "").lower() == "bearer":
        if SUPERADMIN_TOKEN and bearer.credentials == SUPERADMIN_TOKEN:
            return
        # Don't immediately fail; maybe Basic is also supplied and valid.

    # 2) Try Basic (fixed creds for your local testing)
    if basic and basic.username == "stixis" and basic.password == "password":
        return

    # If we get here, neither method was valid
    # If bearer was provided but wrong -> 403; else -> 401
    if bearer:
        raise HTTPException(status_code=403, detail="Invalid superadmin token or credentials")
    raise HTTPException(status_code=401, detail="Missing or invalid superadmin credentials")

def require_caller(
    x_tenant_code: str = Header(..., alias="X-Tenant-Code"),
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Caller:
    tenant = db.query(Company).filter(Company.tenant_code == x_tenant_code).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Unknown tenant")

    user = db.query(User).filter(User.user_code == x_user_code, User.company_id == tenant.id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="User not found or inactive for this tenant")

    if user.api_key != x_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return Caller(user=user, tenant=tenant)

def require_admin(caller: Caller = Depends(require_caller)) -> Caller:
    if caller.user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return caller

def require_caller_with_tenant_in_path(
    tenant_code: str,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Caller:
    """
    Alternative to require_caller that takes tenant_code from URL path instead of header.
    This makes the API more RESTful and easier for frontend integration.
    """
    tenant = db.query(Company).filter(Company.tenant_code == tenant_code).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Unknown tenant: {tenant_code}")

    user = db.query(User).filter(User.user_code == x_user_code, User.company_id == tenant.id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=403,
            detail=f"User '{x_user_code}' not found or inactive for tenant '{tenant_code}'"
        )

    if user.api_key != x_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return Caller(user=user, tenant=tenant)

def require_admin_with_tenant_in_path(
    tenant_code: str,
    x_user_code: str = Header(..., alias="X-User-Code"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Caller:
    """
    Require admin role with tenant_code from URL path.
    """
    caller = require_caller_with_tenant_in_path(tenant_code, x_user_code, x_api_key, db)
    if caller.user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return caller
