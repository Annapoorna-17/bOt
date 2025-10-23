from fastapi import HTTPException, status
import secrets
import string

def generate_short_uid(n: int = 8) -> str:
    """
    URL-safe short id, default length 8.
    Uses a-zA-Z0-9; collision chance is tiny, but we still check in DB at create time.
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def conflict(message: str):
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)

def bad_request(message: str):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

def unauthorized(message: str = "Invalid credentials"):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)