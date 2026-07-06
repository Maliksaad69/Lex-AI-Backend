# Document Ingestion Pipeline — Architecture & Implementation Guide

> **Target:** Store uploaded legal documents in Qdrant for semantic search.  
> **Scope:** `routes/documents.py` and the `services/ingestion/` pipeline.  
> **Status:** Text extraction works. Chunking, embedding, and Qdrant storage are stubs.

---

## 1. Current State (What You Already Have)

### 1.1 Route: `POST /upload-documents`

**File:** `routes/documents.py`

| Step | What happens | Status |
|------|-------------|--------|
| 1 | Receives `List[UploadFile]` via multipart | Done |
| 2 | Reads file size, saves to `backend/uploads/` via `save_file()` | Done |
| 3 | Routes by file type (`.pdf`, `.docx`, `.csv`, `.txt`, `.json`) | Done |
| 4 | Extracts raw text using the appropriate parser | Done |
| 5 | Returns extracted text inline in the JSON response | Done |
| 6 | Chunk text into semantic units | **MISSING** |
| 7 | Generate embeddings for each chunk | **MISSING** |
| 8 | Upsert chunks + vectors into Qdrant | **MISSING** |
| 9 | Store document metadata in MongoDB (optional) | **MISSING** |

**Critical gap:** The route returns extracted text to the client and then discards it. Nothing is persisted for search. The text must flow through the ingestion pipeline into Qdrant.

### 1.2 Extraction Engine: `services/ingestion/document_ingestor.py`

This is the **only fully working module** in the ingestion package.

| Function | Tech | Capability |
|----------|------|------------|
| `extract_text_from_pdf()` | PyMuPDF (fitz) | Digital PDFs: direct text extraction. Scanned/image PDFs: automatic OCR fallback via Tesseract (if installed) |
| `extract_text_from_docx()` | python-docx | Paragraphs + table extraction |
| `save_file()` | stdlib shutil | Writes upload to `backend/uploads/` |

Also handles: `_clean_text()` for whitespace normalization, OCR via `pytesseract`, and a 30-char threshold to detect scanned pages.

### 1.3 Stub Modules (all return `"Hello from X"`)

Every other file in `services/ingestion/` is a placeholder:

| File | Intended purpose | Current content |
|------|-----------------|-----------------|
| `chunker.py` | Split long text into overlapping chunks | Stub |
| `embedding.py` | Call embedding model API, return vectors | Stub |
| `storage.py` | Upsert into Qdrant + Mongo | Stub (comment says "Mongo + Qdrant") |
| `metadata.py` | Extract case metadata from text | Stub |
| `parser.py` | PDF/DOCX/TXT extraction | Stub (logic is in document_ingestor) |
| `ocr.py` | OCR fallback | Stub (logic is in document_ingestor) |

Similarly, `services/qdrant_service.py` and `services/mongo_service.py` are stubs.

### 1.4 Infrastructure

| Component | Status | Notes |
|-----------|--------|-------|
| PostgreSQL | Running | Users, Cases tables via SQLModel + Alembic |
| MongoDB | Referenced, not configured | No connection string in `.env`, no pymongo usage |
| Qdrant | API key in `.env`, no URL | Only `QDRANT_API_KEY` exists — need `QDRANT_URL` too |
| Embedding model | Not selected | Need to choose: OpenAI `text-embedding-3-small`, local via llama.cpp/sentence-transformers, or an API |

---

## 2. Target Pipeline Architecture

```
┌──────────┐    ┌──────────────┐    ┌──────────┐    ┌───────────────┐    ┌────────┐
│  Upload  │───▶│   Extract    │───▶│   Chunk  │───▶│   Embedding   │───▶│ Qdrant │
│  (route) │    │   (ingestor) │    │ (chunker)│    │   (embedding) │    │(vector)│
└──────────┘    └──────────────┘    └──────────┘    └───────────────┘    └────────┘
                                             │                                  │
                                             ▼                                  │
                                      ┌──────────┐                             │
                                      │ Metadata │                             │
                                      │  (meta)  │                             │
                                      └──────────┘                             │
                                             │                                  │
                                             ▼                                  ▼
                                      ┌──────────────────────────────────────────┐
                                      │              MongoDB (optional)           │
                                      │  document metadata + chunk references    │
                                      └──────────────────────────────────────────┘
```

### 2.1 Six Stages (in order)

| # | Stage | Input | Output | Module |
|---|-------|-------|--------|--------|
| 1 | **Upload** | Multipart file bytes | File saved to `uploads/` | `routes/documents.py` |
| 2 | **Extract** | File path | Raw text string | `services/ingestion/document_ingestor.py` |
| 3 | **Chunk** | Raw text | List of `{text, chunk_index, metadata}` | `services/ingestion/chunker.py` |
| 4 | **Embed** | List of chunk texts | List of float vectors (1536-d for OpenAI) | `services/ingestion/embedding.py` |
| 5 | **Store** | Chunks + vectors + metadata | Qdrant points ingested | `services/ingestion/storage.py` |
| 6 | **Respond** | Document ID + status | JSON response to client | `routes/documents.py` |

---

## 3. Module Design (What to Write in Each File)

### 3.1 `chunker.py` — Text Chunking

**Goal:** Split raw legal document text into semantically meaningful, overlapping chunks suitable for embedding.

**Recommended approach:** LangChain's `RecursiveCharacterTextSplitter` or a custom implementation.

```
Parameters:
  - chunk_size: 1000 tokens (~4000 chars for English legal text)
  - chunk_overlap: 200 tokens (~800 chars) — preserves context across boundaries
  - separators: ["\n\n", "\n", ". ", " ", ""] — try double-newline first (paragraphs), then single newline, then sentences, then words

Output per chunk:
  {
    "text": "The extracted text segment...",
    "chunk_index": 0,
    "start_char": 0,
    "end_char": 3892,
    "token_count": 980
  }
```

**Why overlap matters:** Legal documents have cross-references and clauses that span paragraph boundaries. Overlap ensures no semantic unit is split across chunks.

**Edge cases to handle:**
- Documents shorter than `chunk_size`: single chunk, no splitting
- Very long documents (500+ pages): process in streaming fashion to avoid memory pressure
- Documents with no extractable text (scanned PDF where OCR also failed): return empty list, log warning

**Dependency:** `pip install langchain-text-splitters` (lightweight, no full LangChain needed) or write the splitter manually.

### 3.2 `embedding.py` — Vector Generation

**Goal:** Convert each text chunk into a dense vector embedding.

**Recommended approach (3 options, pick one):**

| Option | Model | Dims | Cost | Latency |
|--------|-------|------|------|---------|
| A | OpenAI `text-embedding-3-small` | 1536 | ~$0.02/1M tokens | ~200ms/batch |
| B | Local `sentence-transformers` (e.g. `all-MiniLM-L6-v2`) | 384 | Free | ~10ms/chunk |
| C | Qdrant FastEmbed (built-in) | 384 | Free | ~10ms/chunk |

**Recommendation:** Start with Option A (OpenAI) for quality, then optionally add a local fallback for cost savings. Legal text has nuanced semantics — the 1536-dim model captures more than the 384-dim local models.

**Implementation sketch:**
```python
# embedding.py — pseudocode
from openai import OpenAI

EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 20  # OpenAI allows up to 2048 inputs per request

def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Batch-embed chunks. Returns vectors in same order."""
    all_embeddings = []
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        all_embeddings.extend([item.embedding for item in response.data])
    return all_embeddings
```

**Key design decisions:**
- Embedding model name and dimension should be configurable via env vars (`EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`)
- Batch chunks to minimize API round-trips (OpenAI charges per-token, not per-request)
- Add retry logic with exponential backoff for API rate limits

### 3.3 `storage.py` — Qdrant Upsert

**Goal:** Store chunks, their vectors, and metadata into Qdrant.

**Qdrant collection design:**

```
Collection name: "legal_documents"

Vector config:
  size: 1536 (or 384, depending on embedding model)
  distance: Cosine

Payload schema (per point):
  {
    "document_id": "uuid-...",       # parent document UUID
    "case_id": "123",                # which case this belongs to
    "filename": "complaint.pdf",    # original filename
    "chunk_index": 0,               # order within document
    "text": "The actual chunk...",  # the text (for retrieval)
    "page": 1,                      # source page (for PDFs)
    "file_type": ".pdf",            # original file type
    "uploaded_at": "2026-07-04T...",# timestamp
    "user_id": 42                   # who uploaded it
  }
```

**Why store text in the payload:** When you search and get results back, the text is already there — no need for a second database lookup to display the matching chunk.

**Implementation sketch:**
```python
# storage.py — pseudocode
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

COLLECTION_NAME = "legal_documents"

def ensure_collection_exists(client, vector_size):
    """Create collection if it doesn't exist."""
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

def upsert_chunks(
    client: QdrantClient,
    document_id: str,
    chunks: list[dict],      # [{text, chunk_index, ...}]
    embeddings: list[list[float]],
    metadata: dict,           # {case_id, filename, user_id, ...}
) -> int:
    """Insert all chunks for a document into Qdrant. Returns point count."""
    points = []
    for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        point_id = uuid5(NAMESPACE_DOCUMENTS, f"{document_id}:{i}")
        points.append(PointStruct(
            id=str(point_id),
            vector=vector,
            payload={
                "document_id": document_id,
                "chunk_index": i,
                "text": chunk["text"],
                **metadata,
            },
        ))
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(points)
```

**Point ID strategy:** Use deterministic UUIDs (`uuid5`) based on `document_id + chunk_index`. This makes re-uploading a document an idempotent upsert — it overwrites rather than creating duplicates.

### 3.4 `metadata.py` — Metadata Extraction

**Goal:** Extract structured metadata from the document text for filtering and categorisation.

**What to extract (legal-specific):**
- Court name (e.g., "United States District Court")
- Case number / docket number
- Plaintiff / Defendant names
- Date of filing
- Document type (complaint, motion, order, etc.)
- Jurisdiction

**Approach:** Use regex patterns for known legal document formats, optionally enhanced with LLM classification for ambiguous cases.

**Start simple:** A `document_type` classifier based on filename/keywords covers 80% of use cases. The LLM approach can be added later.

### 3.5 `services/qdrant_service.py` — Qdrant Client Singleton

**Goal:** One configured Qdrant client shared across the app.

```python
# Pattern:
from qdrant_client import QdrantClient

_qdrant_client: QdrantClient | None = None

def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
        )
    return _qdrant_client
```

### 3.6 MongoDB (Optional)

**Purpose:** Store document-level metadata (not chunks) for the documents list in the UI — filename, case_id, size, pages, status, upload date.

**Why not just use PostgreSQL?** You can. The existing Postgres `cases` table already tracks `document_count`. You could add a `documents` table there. The stub references to Mongo suggest the original plan was Mongo for unstructured document metadata and Postgres for structured case data. Either works — pick one and be consistent.

---

## 4. Wiring It All Together: `routes/documents.py`

The route becomes the orchestrator. Here's how the flow changes:

```
CURRENT (broken after step 2):
  Upload → Extract → Return text to client (text discarded)

FUTURE (full pipeline):
  Upload → Extract → Chunk → Embed → Store Qdrant → Return doc ID + status
```

### 4.1 Route Pseudocode (what to implement)

```python
@router.post("/upload-documents")
async def upload_documents(
    files: List[UploadFile] = File(...),
    case_id: str = Form(...),          # NEW: which case
    user_id: int = Depends(...),       # NEW: from auth
):
    results = []

    for file in files:
        # --- Stage 1: Save ---
        file_path = save_file(file)

        # --- Stage 2: Extract ---
        text, pages = extract_text(file_path, file_type)

        # --- Stage 3: Chunk ---
        chunks = chunk_text(text)       # calls chunker.py

        # --- Stage 4: Embed ---
        chunk_texts = [c["text"] for c in chunks]
        vectors = embed_chunks(chunk_texts)  # calls embedding.py

        # --- Stage 5: Store in Qdrant ---
        doc_id = str(uuid4())
        upsert_chunks(
            client=get_qdrant_client(),
            document_id=doc_id,
            chunks=chunks,
            embeddings=vectors,
            metadata={
                "case_id": case_id,
                "filename": file.filename,
                "user_id": user_id,
                "pages": pages,
                "file_type": file_type,
            },
        )

        # --- Stage 6: Update case document_count in Postgres ---
        # increment Case.document_count

        results.append({
            "document_id": doc_id,
            "filename": file.filename,
            "status": "ingested",
            "chunks": len(chunks),
        })

    return results
```

### 4.2 What Changes in the Route

| Current | Future |
|---------|--------|
| `POST /upload-documents` — no params beyond files | Add `case_id` (Form) and auth dependency |
| Returns raw extracted text | Returns document_id + chunk count |
| No persistence | Full Qdrant persistence |
| No chunking/embedding | Full pipeline |

---

## 5. Configuration Checklist

### 5.1 Environment Variables (`.env` additions)

```env
# --- Qdrant ---
QDRANT_URL=http://localhost:6333          # or your Qdrant Cloud URL
QDRANT_API_KEY=qawsedrftgyhujiknvgfd...   # already exists

# --- Embedding ---
EMBEDDING_PROVIDER=openai                 # or "local"
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
OPENAI_API_KEY=sk-...                     # needed if using OpenAI embeddings

# --- MongoDB (optional) ---
MONGO_URI=mongodb://localhost:27017
MONGO_DB=litigation
```

### 5.2 Python Dependencies (`pip install`)

```
qdrant-client>=1.9        # Qdrant Python client
openai>=1.0               # For embedding API (if using OpenAI)
langchain-text-splitters  # For RecursiveCharacterTextSplitter (optional)
pymongo>=4.0              # If using MongoDB
```

### 5.3 Infrastructure (Docker / local)

| Service | How to run |
|---------|-----------|
| Qdrant | `docker run -p 6333:6333 qdrant/qdrant` |
| MongoDB (optional) | `docker run -p 27017:27017 mongo` |

---

## 6. Error Handling & Resilience

### 6.1 Per-document isolation

If one document fails (e.g., embedding API error), it should NOT block other documents in the same batch upload. Wrap each document's pipeline in try/except and return per-document status:

```json
{
  "document_id": "uuid-...",
  "filename": "complaint.pdf",
  "status": "ingested",
  "chunks": 42
},
{
  "document_id": "uuid-...",
  "filename": "broken.pdf",
  "status": "failed",
  "error": "Embedding API rate limit exceeded"
}
```

### 6.2 Partial failure in Qdrant upsert

Qdrant upserts are atomic per-batch. If one point fails, the whole batch fails. For large documents, split into sub-batches of 100 points to limit blast radius.

### 6.3 Idempotency

Re-uploading the same file should overwrite, not duplicate. The `uuid5(document_id + chunk_index)` point ID strategy handles this. If you want to prevent accidental re-upload, hash the file content and check for existing documents with the same hash before processing.

---

## 7. Implementation Order (Recommended Sequence)

| Step | What | Files | Effort |
|------|------|-------|--------|
| 1 | Install `qdrant-client` + `openai` + `langchain-text-splitters` | - | 2 min |
| 2 | Stand up Qdrant locally (Docker) | - | 2 min |
| 3 | Write `services/qdrant_service.py` — client singleton | 1 file | 10 min |
| 4 | Write `services/ingestion/chunker.py` | 1 file | 20 min |
| 5 | Write `services/ingestion/embedding.py` | 1 file | 20 min |
| 6 | Write `services/ingestion/storage.py` — Qdrant upsert | 1 file | 20 min |
| 7 | Rewire `routes/documents.py` — full pipeline | 1 file | 30 min |
| 8 | Add `.env` config | 1 file | 2 min |
| 9 | Test end-to-end with a small PDF | - | 15 min |
| 10 | Add search endpoint `GET /search?q=...&case_id=...` | new route or documents.py | 30 min |

**Total effort:** ~2.5 hours for a working end-to-end pipeline + search.

---

## 8. What NOT To Do

- **Don't embed the entire document as one vector.** Long documents lose semantic precision. Always chunk.
- **Don't store vectors in PostgreSQL.** Use Qdrant — it's purpose-built for vector search (HNSW index, payload filtering, etc.)
- **Don't skip overlap in chunking.** Legal documents have cross-references that span chunk boundaries.
- **Don't hardcode the embedding dimension.** Read it from env or detect from the model — if you later switch models, you don't want to rebuild.
- **Don't return raw text in the upload response.** The client doesn't need the extracted text back; just confirm ingestion status. Let the search endpoint return text when requested.

---

## 9. The Search Side (Quick Preview)

Once ingestion works, you need retrieval:

```
GET /documents/search?q=breach of contract&case_id=123&top_k=5
```

Flow:
1. Embed the query string with the same model used for documents
2. Query Qdrant with the query vector + payload filter (`case_id=123`)
3. Return top-k chunks with metadata and similarity scores

This is a separate piece of work but uses the same building blocks (embedding model, Qdrant client). The search endpoint can go in `routes/documents.py` or a separate search route.

---

## 10. File Map (After Implementation)

```
backend/
├── routes/
│   └── documents.py          ← Orchestrator: upload → pipeline → respond
├── services/
│   ├── ingestion/
│   │   ├── document_ingestor.py  ← extract_text_from_pdf(), extract_text_from_docx(), save_file()
│   │   ├── chunker.py            ← chunk_text() → List[{text, index, ...}]
│   │   ├── embedding.py          ← embed_chunks(texts) → List[vector]
│   │   └── storage.py            ← upsert_chunks(client, doc_id, chunks, vectors, metadata)
│   ├── qdrant_service.py         ← get_qdrant_client() singleton
│   └── mongo_service.py          ← optional document metadata CRUD
├── models/
│   └── document.py               ← Pydantic models (already exists)
├── .env                          ← QDRANT_URL, QDRANT_API_KEY, EMBEDDING_MODEL, etc.
└── uploads/                      ← temporary file storage
```