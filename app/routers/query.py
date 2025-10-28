from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
# --- 1. Import new auth and models ---
from ..auth import get_current_user
from .. import models
from ..schemas import QueryRequest, QueryAnswer
from ..rag import search, synthesize_answer

# --- 2. REMOVED old auth imports (require_caller, Caller) ---

router = APIRouter(prefix="/query", tags=["Query"])

@router.post("", response_model=QueryAnswer)
def ask(
    payload: QueryRequest,
    # --- 3. USE new dependency ---
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db),
):
    # --- 4. UPDATE logic to use 'current_user' ---
    # Tenant-scoped search. Optional per-user filter.
    matches = search(
        # 'caller.tenant' is now 'current_user.company'
        tenant_code=current_user.company.tenant_code, # <-- Changed
        query=payload.question,
        top_k=payload.top_k,
        # 'caller.user' is now 'current_user'
        filter_user_code=current_user.user_code if payload.user_filter else None # <-- Changed
    )
    if not matches:
        return QueryAnswer(answer="I don't have enough information to answer that.", sources=[])

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
