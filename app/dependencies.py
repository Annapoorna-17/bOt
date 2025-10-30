from fastapi import Query
from pydantic import BaseModel

class PaginationParams(BaseModel):
    page: int
    size: int

def get_pagination_params(
    page: int = Query(1, ge=1, description="Page number, 1-indexed"),
    size: int = Query(10, ge=1, le=100, description="Page size (default 10, max 100)")
) -> PaginationParams:
    """
    Reusable dependency for pagination parameters.
    Returns page and size.
    """
    return PaginationParams(page=page, size=size)