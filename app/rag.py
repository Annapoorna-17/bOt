import os
from typing import List, Dict
from pypdf import PdfReader
from openai import OpenAI
from pinecone import Pinecone
import re, hashlib

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
# Support either var name; prefer your PINECONE_INDEX_NAME
PINECONE_INDEX = os.getenv("PINECONE_INDEX_NAME", "bot-multi") or os.getenv("PINECONE_INDEX")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing")
if not PINECONE_API_KEY or not PINECONE_INDEX:
    raise RuntimeError("Pinecone API key or index name missing")

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)
oai = OpenAI(api_key=OPENAI_API_KEY)

def _read_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    return "\n".join([page.extract_text() or "" for page in reader.pages])

def _chunk_text(text: str, max_chars: int = 3000, overlap: int = 400):
    """
    Simple, fast chunker that respects sentence boundaries when possible.
    - max_chars ~ roughly 750 tokens (4 chars/token heuristic), adjust as needed.
    - overlap keeps a bit of context between chunks.
    """
    text = re.sub(r'\s+', ' ', text).strip()

    if len(text) <= max_chars:
        return [text] if text else []

    chunks = []
    start = 0
    end = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        # try to cut at the last sentence boundary within the window
        window = text[start:end]
        cut = max(window.rfind('. '), window.rfind('? '), window.rfind('! '))
        if cut == -1 or end == len(text):
            cut = len(window)
        chunk = window[:cut].strip()
        if chunk:
            chunks.append(chunk)
        # move start forward with overlap
        start = start + cut
        start = max(0, start - overlap)

        # avoid infinite loop on very small residuals
        if end == len(text):
            break

    # dedupe / clean
    out = []
    last = ""
    for c in chunks:
        if c and c != last:
            out.append(c)
            last = c
    return out

def embed_chunks(chunks: List[str]) -> List[List[float]]:
    resp = oai.embeddings.create(model=EMBED_MODEL, input=chunks)
    return [d.embedding for d in resp.data]

def upsert_chunks(tenant_code: str, user_code: str, doc_filename: str, chunks: List[str]) -> int:
    embs = embed_chunks(chunks)
    vectors = []
    for i, (chunk, vec) in enumerate(zip(chunks, embs)):
        vid = hashlib.sha256(f"{tenant_code}:{doc_filename}:{i}".encode()).hexdigest()
        vectors.append({
            "id": vid,
            "values": vec,
            "metadata": {
                "tenant_code": tenant_code,
                "user_code": user_code,
                "doc": doc_filename,
                "chunk_index": i,
                "text": chunk
            }
        })
    index.upsert(vectors=vectors, namespace=tenant_code)
    return len(vectors)

def pdf_to_pinecone(file_path: str, tenant_code: str, user_code: str, stored_filename: str) -> int:
    text = _read_pdf_text(file_path)
    if not text.strip():
        return 0
    chunks = _chunk_text(text)
    return upsert_chunks(tenant_code, user_code, stored_filename, chunks)

def search(tenant_code: str, query: str, top_k: int = 8, filter_user_code: str | None = None):
    q_emb = oai.embeddings.create(model=EMBED_MODEL, input=[query]).data[0].embedding
    flt = {"tenant_code": {"$eq": tenant_code}}
    if filter_user_code:
        flt = {"$and": [flt, {"user_code": {"$eq": filter_user_code}}]}
    res = index.query(
        vector=q_emb, top_k=top_k, namespace=tenant_code,
        filter=flt, include_metadata=True
    )
    return res.matches or []

def synthesize_answer(question: str, contexts: List[str]) -> str:
    prompt = (
        "Answer the question ONLY using the provided context. "
        "If the answer isn't in the context, say you don't have enough information.\n\n"
        f"Question:\n{question}\n\n"
        "Context:\n" + "\n\n---\n".join(contexts[:12])
    )
    chat = oai.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return chat.choices[0].message.content.strip()
