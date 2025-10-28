from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..security import require_caller, Caller
from ..schemas import QueryRequest, QueryAnswer
from ..rag import search, synthesize_answer

router = APIRouter(prefix="/query", tags=["Query"])

@router.post("", response_model=QueryAnswer)
def ask(
    payload: QueryRequest,
    caller: Caller = Depends(require_caller),
    db: Session = Depends(get_db),
):
    # Tenant-scoped search. Optional per-user filter.
    matches = search(
        tenant_code=caller.tenant.tenant_code,
        query=payload.question,
        top_k=payload.top_k,
        filter_user_code=caller.user.user_code if payload.user_filter else None
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
