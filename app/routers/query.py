from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
# --- 1. Import new auth and models ---
from ..auth import get_current_user
from .. import models
from ..schemas import QueryRequest, QueryAnswer
from ..rag import search, synthesize_answer

# --- 2. REMOVED old auth imports (require_caller, Caller)---

router = APIRouter(prefix="/query", tags=["Query"])

@router.post("", response_model=QueryAnswer)
def ask(
    payload: QueryRequest,
    # --- 3. USE new dependency - AUTHENTICATION REQUIRED FOR TENANT ISOLATION ---
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # --- 4. UPDATED logic to use 'current_user' for proper tenant isolation ---
    # Tenant-scoped search: Only query data from the authenticated user's company.
    # Optional per-user filter: If user_filter=True, only show content uploaded by this user.

    # === TENANT ISOLATION DEBUG LOGGING ===
    print("=" * 80)
    print("🔒 TENANT ISOLATION CHECK - QUERY ENDPOINT")
    print(f"📋 User: {current_user.user_code} ({current_user.display_name})")
    print(f"🏢 Company: {current_user.company.name}")
    print(f"🔑 Tenant Code: {current_user.company.tenant_code}")
    print(f"❓ Question: {payload.question[:100]}")
    print(f"🎯 User Filter: {payload.user_filter}")
    print(f"📂 Source Type: {payload.source_type}")
    print(f"🎚️  Min Score: {payload.min_score}")
    print("=" * 80)

    # Validate source_type
    if payload.source_type not in ["all", "documents", "websites"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source_type '{payload.source_type}'. Must be 'all', 'documents', or 'websites'."
        )

    # Validate min_score range
    if not (0.0 <= payload.min_score <= 1.0):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid min_score '{payload.min_score}'. Must be between 0.0 and 1.0."
        )

    matches = search(
        # CRITICAL: Use authenticated user's tenant_code for multi-tenant isolation
        tenant_code=current_user.company.tenant_code,
        query=payload.question,
        top_k=payload.top_k,
        # OPTIONAL: Filter by user if requested
        filter_user_code=current_user.user_code if payload.user_filter else None,
        source_type=payload.source_type,
        min_score=payload.min_score
    )

    # Check if no relevant results found after filtering
    if not matches:
        print("⚠️  No relevant results found after filtering")
        raise HTTPException(
            status_code=404,
            detail=f"No relevant information found in your company's documents/websites for this query. "
                   f"Try lowering the min_score threshold (currently {payload.min_score}) or upload more relevant content."
        )

    contexts = [m.metadata.get("text", "") for m in matches if m.metadata]

    # Handle both document and website sources
    sources = []
    for m in matches:
        if m.metadata:
            source_type = m.metadata.get("source_type", "document")
            if source_type == "website":
                sources.append(m.metadata.get("url", "unknown"))
            else:
                sources.append(m.metadata.get("doc", "unknown"))

    answer = synthesize_answer(payload.question, contexts)
    return QueryAnswer(answer=answer, sources=sources[:payload.top_k])
