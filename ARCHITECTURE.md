# LexAI Backend Architecture Guide

## How to Build a Scalable Yet Simple Backend

---

## Philosophy

This backend follows two rules that usually fight each other:

1. **Simple** — a new developer should understand the whole thing in an afternoon
2. **Scalable** — it should handle 10 users or 10,000 without a rewrite

The trick: **strict layering with narrow contracts**. Every layer does one thing and talks to the next through a thin, well-defined interface. You can swap any layer without touching the others.

---

## The 4-Layer Architecture

```
┌─────────────────────────────────────────────┐
│  ROUTES      (HTTP concerns only)            │
│  Parse request → call service → return JSON  │
├─────────────────────────────────────────────┤
│  SERVICES    (Business logic)                │
│  Orchestrate operations, enforce rules       │
├─────────────────────────────────────────────┤
│  MODELS      (Data shapes)                   │
│  Pydantic schemas — what data looks like     │
├─────────────────────────────────────────────┤
│  INFRA       (External systems)              │
│  MongoDB, Qdrant, AI APIs, file storage      │
└─────────────────────────────────────────────┘
```

The golden rule: **a layer only talks to the layer directly below it**. Routes never touch the database. Services never parse HTTP headers. This is what keeps it simple as it grows.

---

## Project Structure

```
backend/
│
├── main.py              ← FastAPI app factory, lifespan, CORS
├── config.py            ← All settings via pydantic-settings (env vars)
├── deps.py              ← FastAPI dependency injection (get_db, get_current_user)
├── requirements.txt
│
├── models/              ← Pydantic models (data shapes, not DB logic)
│   ├── user.py          ← User, UserCreate, UserLogin, Token
│   ├── case.py          ← Case, CaseCreate, CaseStatus
│   ├── document.py      ← Document, DocumentChunk
│   ├── analysis.py      ← AnalysisRequest, AnalysisResult
│   └── report.py        ← Report, ReportGenerate
│
├── routes/              ← Thin HTTP handlers (FastAPI routers)
│   ├── auth.py          ← POST /login, /register, /refresh
│   ├── cases.py         ← CRUD /cases
│   ├── documents.py     ← Upload, list, search /documents
│   ├── analysis.py      ← POST /analysis/run
│   ├── jury.py          ← Jury simulation endpoints
│   └── reports.py       ← Generate, export /reports
│
├── services/            ← Business logic (no HTTP awareness)
│   ├── auth_service.py      ← Hash passwords, issue JWT, verify tokens
│   ├── mongo_service.py     ← MongoDB connection, CRUD helpers
│   ├── qdrant_service.py    ← Vector store: upsert, search, delete
│   ├── ai_service.py        ← LLM calls (analysis, summarization, jury)
│   ├── document_service.py  ← Upload flow orchestration
│   ├── report_service.py    ← Report generation
│   │
│   └── ingestion/           ← Document ingestion pipeline
│       ├── document_ingestor.py   ← Pipeline orchestrator
│       ├── parser.py              ← PDF/DOCX/TXT → raw text
│       ├── ocr.py                 ← Image → text (Tesseract/EasyOCR)
│       ├── chunker.py             ← Text → overlapping chunks
│       ├── embedding.py           ← Chunks → vectors (sentence-transformers)
│       ├── metadata.py            ← Extract dates, parties, case numbers
│       └── storage.py             ← Save to Mongo + Qdrant
│
└── uploads/             ← Temporary file uploads (gitignored)
```

---

## Layer 1: Models (`models/`)

**What it is**: Pure data structures. Zero logic. Just Pydantic `BaseModel` classes.

**Why Pydantic**: FastAPI natively understands Pydantic. Your route says `def create_case(case: CaseCreate)` and you get automatic validation, JSON Schema docs, and type hints — all for free.

### The Document model (already built)

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class Document(BaseModel):
    id: Optional[str] = None          # None on create, set by Mongo
    case_id: str                      # Which case this belongs to
    filename: str                     # Original filename
    original_path: str                # Where it was uploaded
    case: str                         # Case reference number
    content_type: str                 # application/pdf, etc.
    file_size: int                    # Bytes
    pages: int = 0
    extracted_text: str = ""
    uploaded_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Pattern for other models

Separate **request** (what the client sends) from **response** (what you return) from **internal** (what you store):

```python
# models/case.py
class CaseCreate(BaseModel):
    """What the client sends"""
    title: str
    description: str
    case_number: str
    client_name: str

class Case(CaseCreate):
    """What you store and return"""
    id: str
    created_by: str
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### Why this scales

- Validation happens at the boundary (route layer) before anything touches your logic
- Type hints flow through the entire stack — your IDE catches bugs before runtime
- Adding a field means adding one line to a model — routes and services auto-inherit it
- No ORM. Pydantic models are plain objects. Serialize to dict for Mongo, no magic.

---

## Layer 2: Routes (`routes/`)

**What it is**: Thin HTTP handlers. 5-10 lines per endpoint.

**The contract**: A route does exactly three things:
1. Parse the request (body, params, auth) — FastAPI does this for you
2. Call the service
3. Return the response

### The pattern

```python
# routes/cases.py
from fastapi import APIRouter, Depends, HTTPException
from models.case import Case, CaseCreate
from deps import get_current_user
from services.mongo_service import MongoService

router = APIRouter(prefix="/cases", tags=["cases"])

@router.post("/", response_model=Case)
async def create_case(
    case_data: CaseCreate,
    user: dict = Depends(get_current_user),
    db: MongoService = Depends(get_db),      # injected via deps.py
):
    case = await db.create_case(case_data, user["id"])
    return case

@router.get("/{case_id}", response_model=Case)
async def get_case(
    case_id: str,
    user: dict = Depends(get_current_user),
    db: MongoService = Depends(get_db),
):
    case = await db.get_case(case_id, user["id"])
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case
```

### Why this scales

- Zero business logic in routes — you can add rate limiting, caching, or auth middleware without touching business code
- FastAPI's dependency injection (`Depends`) makes auth and DB connections declarative
- Each route file is independent — add a new feature domain by dropping in a new file
- `response_model` auto-filters your output — you can't accidentally leak internal fields

---

## Layer 3: Services (`services/`)

**What it is**: Where the actual work happens. Services orchestrate operations, enforce business rules, and call infrastructure.

**The contract**: Services receive plain data (dicts, Pydantic models, strings) and return plain data. They never touch `Request`, `Response`, or HTTP status codes.

### Infrastructure services (wrap external systems)

```python
# services/mongo_service.py
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

class MongoService:
    def __init__(self):
        self.client = AsyncIOMotorClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB]

    async def create_case(self, case_data, user_id):
        doc = case_data.model_dump()
        doc["created_by"] = user_id
        result = await self.db.cases.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        return doc

    async def get_case(self, case_id, user_id):
        from bson import ObjectId
        doc = await self.db.cases.find_one({
            "_id": ObjectId(case_id),
            "created_by": user_id
        })
        if doc:
            doc["id"] = str(doc.pop("_id"))
        return doc
```

```python
# services/qdrant_service.py
from qdrant_client import QdrantClient
from config import settings

class QdrantService:
    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL)

    async def upsert_chunks(self, document_id: str, chunks: list[dict]):
        """Store document chunks as vectors for semantic search"""
        points = [
            {
                "id": f"{document_id}_{i}",
                "vector": chunk["embedding"],
                "payload": {
                    "document_id": document_id,
                    "text": chunk["text"],
                    "chunk_index": i,
                }
            }
            for i, chunk in enumerate(chunks)
        ]
        self.client.upsert(
            collection_name="documents",
            points=points
        )

    async def search(self, query_vector: list[float], limit: int = 10):
        """Semantic search across all documents"""
        results = self.client.search(
            collection_name="documents",
            query_vector=query_vector,
            limit=limit,
        )
        return [hit.payload for hit in results]
```

### Business services (orchestrate infrastructure)

```python
# services/document_service.py
from services.ingestion.document_ingestor import DocumentIngestor
from services.mongo_service import MongoService

class DocumentService:
    def __init__(self, mongo: MongoService, ingestor: DocumentIngestor):
        self.mongo = mongo
        self.ingestor = ingestor

    async def upload_and_process(self, file, case_id: str, user_id: str):
        # 1. Save file to disk
        # 2. Run ingestion pipeline (parse → OCR → chunk → embed → store)
        # 3. Save document metadata to Mongo
        # 4. Return the processed document
        ...
```

### Why this scales

- Services are plain classes — test them with `pytest` without spinning up HTTP
- Swap MongoDB for Postgres? Change one file: `mongo_service.py`
- Add a cache layer? Wrap the service, don't touch routes or models
- The ingestion pipeline is a chain of single-responsibility steps — add a step without touching others

---

## Layer 4: The Document Ingestion Pipeline

This is the most complex subsystem. It's designed as a **pipeline pattern** — each step does one transformation and hands off to the next.

```
Uploaded File
    │
    ▼
┌──────────┐
│  PARSER   │  PDF → raw text (PyMuPDF)
│           │  DOCX → raw text (python-docx)
│           │  TXT  → raw text (passthrough)
└────┬─────┘
     │
     ▼
┌──────────┐
│   OCR     │  If parser found no text or file is scanned
│           │  Image → text (Tesseract or EasyOCR)
└────┬─────┘
     │
     ▼
┌──────────┐
│  CHUNKER  │  Split text into overlapping chunks
│           │  ~500 tokens per chunk, 50 token overlap
│           │  Smart split on paragraph/sentence boundaries
└────┬─────┘
     │
     ▼
┌──────────┐
│ METADATA  │  Extract structured data from text
│           │  Dates, case numbers, party names, citations
└────┬─────┘
     │
     ▼
┌──────────┐
│ EMBEDDING │  Chunk text → vector (768-dim)
│           │  Model: sentence-transformers/all-MiniLM-L6-v2
└────┬─────┘
     │
     ▼
┌──────────┐
│  STORAGE  │  Write to two places:
│           │  Mongo  → document metadata + chunks (text)
│           │  Qdrant → chunks (vectors) for semantic search
└──────────┘
```

### Pipeline orchestration

```python
# services/ingestion/document_ingestor.py
class DocumentIngestor:
    def __init__(self, parser, ocr, chunker, metadata, embedding, storage):
        self.parser = parser
        self.ocr = ocr
        self.chunker = chunker
        self.metadata = metadata
        self.embedding = embedding
        self.storage = storage

    async def ingest(self, file_path: str, document_id: str) -> dict:
        # Step 1: Extract text
        text = await self.parser.extract(file_path)

        # Step 2: OCR fallback if needed
        if not text or len(text.strip()) < 100:
            text = await self.ocr.extract(file_path)

        # Step 3: Chunk
        chunks = self.chunker.split(text)

        # Step 4: Extract metadata
        meta = await self.metadata.extract(text)

        # Step 5: Embed each chunk
        for chunk in chunks:
            chunk["embedding"] = await self.embedding.embed(chunk["text"])

        # Step 6: Store everything
        await self.storage.save(document_id, chunks, meta)

        return {"chunks": len(chunks), "metadata": meta}
```

### Why this scales

- Each step is independently testable and replaceable
- Want a better embedding model? Change one file
- Need to add translation? Insert a step between OCR and chunker
- The pipeline can be made async per-document — process 50 documents in parallel
- Large documents? Stream chunks through the pipeline instead of loading everything in memory

---

## Dependency Injection (`deps.py`)

This is the glue that makes the layers work without coupling them.

```python
# deps.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from services.mongo_service import MongoService
from services.qdrant_service import QdrantService
from services.ai_service import AIService
from services.auth_service import AuthService

# Singleton services (created once at startup)
_mongo = None
_qdrant = None
_ai = None

async def get_db():
    global _mongo
    if _mongo is None:
        _mongo = MongoService()
    return _mongo

async def get_qdrant():
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantService()
    return _qdrant

async def get_current_user(
    token: str = Depends(HTTPBearer()),
    db = Depends(get_db),
):
    """Validate JWT and return the current user"""
    auth = AuthService()
    user = await auth.verify_token(token.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
```

### Why this scales

- Services are created once and reused (connection pooling)
- Routes don't import services — they "ask" for them via `Depends`
- Testing: override `get_db` with a mock, everything else stays the same
- Adding a new dependency means one function in `deps.py` — zero changes to routes

---

## Configuration (`config.py`)

Every setting comes from environment variables. No hardcoded values.

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App
    APP_NAME: str = "LexAI"
    DEBUG: bool = False
    SECRET_KEY: str

    # MongoDB
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "lexai"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"

    # AI
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Auth
    JWT_EXPIRY_HOURS: int = 24

    class Config:
        env_file = ".env"

settings = Settings()
```

Use a `.env` file for local dev, Docker secrets or K8s configmaps for production. Same code, different values.

---

## The App Factory (`main.py`)

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to DBs, warm up models
    print(f"Starting {settings.APP_NAME}...")
    yield
    # Shutdown: close connections
    print("Shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from routes import auth, cases, documents, analysis, jury, reports
app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(documents.router)
app.include_router(analysis.router)
app.include_router(jury.router)
app.include_router(reports.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## Data Flow: Full Request Lifecycle

Here's what happens when a user uploads a document:

```
1. CLIENT
   POST /documents/upload
   Content-Type: multipart/form-data
   Authorization: Bearer <jwt>
   Body: file=contract.pdf, case_id=abc123

2. ROUTE (routes/documents.py)
   - FastAPI parses multipart form
   - Depends(get_current_user) validates JWT → user dict
   - Calls document_service.upload(file, case_id, user["id"])

3. SERVICE (services/document_service.py)
   - Saves file to uploads/{case_id}/{filename}
   - Calls ingestor.ingest(file_path, doc_id)
   - Saves document metadata to Mongo
   - Returns Document model

4. INGESTOR (services/ingestion/document_ingestor.py)
   - parser.extract() → raw text
   - chunker.split() → list of chunks
   - embedding.embed() → vectors
   - storage.save() → Mongo + Qdrant

5. RESPONSE
   201 Created
   {
     "id": "64a1b2c3...",
     "filename": "contract.pdf",
     "pages": 12,
     "chunks": 47,
     "status": "processed"
   }
```

---

## Testing Strategy

```
tests/
├── test_models/      ← Pydantic validation (fast, no deps)
├── test_routes/      ← HTTP via TestClient (mock services)
├── test_services/    ← Business logic (mock DB calls)
└── test_ingestion/   ← Pipeline steps (mock external APIs)
```

- **Models**: `assert CaseCreate(title="").model_validate()` raises error
- **Routes**: Use `TestClient` with overridden dependencies
- **Services**: Pass mock MongoService, verify it calls correct methods
- **Ingestion**: Test each step with sample files

---

## Scaling Checklist

| When you hit... | What to do |
|---|---|
| 100 concurrent uploads | Add a task queue (Celery/Redis) for ingestion |
| 10K documents | Add MongoDB indexes on `case_id`, `created_by` |
| 100K vector searches/day | Add Redis cache in front of Qdrant |
| Slow embedding | Run embedding on GPU, batch chunks |
| Team grows to 5 devs | Split services/ into separate packages |
| Multi-region | Add a load balancer, use MongoDB Atlas multi-region |

---

## Rules That Keep It Simple

1. **Routes never import from other routes** — each is self-contained
2. **Services never import from routes** — services don't know HTTP exists
3. **Models never import from services** — data shapes don't do work
4. **One model file per domain** — User, Case, Document, etc.
5. **One route file per domain** — matches models 1:1
6. **One service file per concern** — auth, mongo, qdrant, ai, documents
7. **No circular imports** — deps flow downward: routes → services → models

---

## Getting Started (Implementation Order)

Build in this order — each step produces something testable:

1. **`config.py`** — settings from env (5 minutes)
2. **`main.py`** — empty FastAPI app with health check (10 minutes)
3. **`models/`** — all Pydantic schemas (30 minutes)
4. **`services/mongo_service.py`** — connect, CRUD helpers (1 hour)
5. **`deps.py`** — dependency injection wiring (20 minutes)
6. **`routes/`** — one route at a time, starting with auth (2 hours)
7. **`services/auth_service.py`** — JWT, password hashing (1 hour)
8. **`services/ingestion/`** — pipeline steps one at a time (4 hours)
9. **`services/ai_service.py`** — LLM integration (2 hours)
10. **`services/qdrant_service.py`** — vector search (1 hour)

Each step is independently verifiable — you never have to build the whole thing before seeing if it works.