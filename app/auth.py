from passlib.context import CryptContext

# Use bcrypt_sha256 to avoid the 72-byte limit safely
pwd_ctx = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")

def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def role_name(role: int) -> str:
    return {1: "Super Admin", 2: "Admin", 3: "User"}.get(role, "Unknown")
