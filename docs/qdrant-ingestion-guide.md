# Qdrant Document Ingestion Guide

This project uses **Qdrant** (vector database) running in Docker for semantic
search over document chunks. Documents go through: **parse → chunk → embed → store**.

---

## 1. Architecture

```
Upload (PDF/DOCX/etc.)
    │
    ▼
parser.py  ─── extracts text, tables, metadata from any format
    │
    ▼
chunker.py ─── splits text into overlapping chunks (sliding window)
    │
    ▼
embedding.py ── generates vector embeddings (local or OpenAI)
    │
    ▼
storage.py ─── upserts chunks + payloads into Qdrant
    │
    ▼
Qdrant (port 6333) ─── semantic search via /search endpoint
```

All files are in `D:\Internship\backend\services\ingestion\`.

---

## 2. Qdrant Setup

### Docker (already configured)

Qdrant runs via `docker-compose.yaml`:

```yaml
qdrant:
  image: qdrant/qdrant:latest
  container_name: qdrant
  ports:
    - "6333:6333"   # REST API
    - "6334:6334"   # gRPC
  volumes:
    - ./qdrant_data:/qdrant/storage
```

### Start/stop

```bash
cd D:\Internship\backend
docker compose up -d qdrant     # start
docker compose stop qdrant      # stop
docker compose logs qdrant      # check logs
```

### Verify it's running

```bash
curl http://localhost:6333/healthz
# → OK
```

### Dashboard (optional)

Access the Qdrant Web UI at http://localhost:6333/dashboard

---

## 3. Ingesting Documents

### Option A: Via API (recommended)

```bash
curl -X POST http://localhost:8000/upload-documents \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "files=@complaint.pdf" \
  -F "files=@exhibit_a.docx" \
  -F "case_id=1" \
  -F "store_in_qdrant=true"
```

Response per file:
```json
{
  "document_id": "uuid-here",
  "filename": "complaint.pdf",
  "chunks_count": 12,
  "stored_in_qdrant": 12,
  "metadata": {
    "title": "Complaint for Damages",
    "author": "John Smith",
    "word_count": 3500,
    "dates_found": ["01/15/2025"],
    "emails_found": ["counsel@firm.com"],
    "case_numbers": ["Case No. 2:25-cv-00123"]
  }
}
```

### Option B: Via Python directly

```python
from services.ingestion.pipeline import ingest_document

result = ingest_document(
    file_path="D:/docs/complaint.pdf",
    user_id=1,
    document_id="manual-doc-001",
    case_id=1,
    chunk_strategy="sliding_window",
    chunk_size=1024,
    chunk_overlap=128,
    store_in_qdrant=True,
)

print(f"Stored {result['stored_in_qdrant']} chunks")
print(f"Metadata: {result['metadata']}")
```

### Option C: Parse only (no Qdrant)

```python
# Just extract text without storing
result = ingest_document(
    file_path="D:/docs/complaint.pdf",
    user_id=1,
    document_id="doc-001",
    store_in_qdrant=False,   # skip Qdrant
)
# result["chunks_count"] = 12
# result["text_preview"] = "IN THE UNITED STATES DISTRICT COURT..."
```

---

## 4. Searching Documents

### Via Python

```python
from services.ingestion.embedding import embed
from services.ingestion.storage import QdrantStore

store = QdrantStore(collection_name="lexai_documents")

# Embed your query
query_vec = embed(["breach of fiduciary duty claim"])[0]

# Search
results = store.search(
    query_vector=query_vec,
    limit=5,
    score_threshold=0.5,
    filter_user_id=1,              # optional: restrict to user
    filter_document_id="doc-123",  # optional: restrict to document
)

for r in results:
    print(f"Score: {r['score']:.3f}")
    print(f"Text: {r['payload']['text'][:200]}")
    print(f"Doc: {r['payload']['filename']}")
    print()
```

### Via REST API

```bash
curl -X POST http://localhost:6333/collections/lexai_documents/points/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [0.1, 0.2, ...],
    "limit": 5,
    "with_payload": true
  }'
```

---

## 5. Chunking Strategies

You can choose a chunking strategy per document:

| Strategy | Best For | Config |
|----------|----------|--------|
| `sliding_window` (default) | General purpose, most legal docs | `chunk_size=1024, chunk_overlap=128` |
| `semantic` | Structured docs with headers/sections | Preserves section boundaries |
| `recursive` | Code, highly structured text | Breaks on paragraphs→sentences→chars |
| `fixed` | Fastest, simple split | `chunk_size=1024`, no overlap |

```python
from services.ingestion.chunker import chunk

chunks = chunk(text, strategy="semantic", max_chunk_size=2048)
```

---

## 6. Embedding Models

### Auto-detect (default)

If `OPENAI_API_KEY` is set → uses `text-embedding-3-small` (1536 dims).
Otherwise → uses local `all-MiniLM-L6-v2` (384 dims) via sentence-transformers.

### Force local

```python
from services.ingestion.embedding import EmbeddingModel

model = EmbeddingModel(provider="local", model_name="all-MiniLM-L6-v2")
```

### Force OpenAI

```python
model = EmbeddingModel(provider="openai", model_name="text-embedding-3-small")
```

---

## 7. Managing Qdrant

### List all collections

```python
from qdrant_client import QdrantClient
client = QdrantClient(url="http://localhost:6333")
for c in client.get_collections().collections:
    print(c.name)
```

### Delete a document's chunks

```python
from services.ingestion.storage import QdrantStore
store = QdrantStore(collection_name="lexai_documents")
store.delete_by_document("doc-uuid-here")
```

### Delete all chunks for a user

```python
store.delete_by_user(user_id=1)
```

### Get collection stats

```python
info = store.collection_info()
# {name, vectors_count, points_count, segments_count}
```

### Drop and recreate a collection

```python
client.delete_collection("lexai_documents")
# Next time QdrantStore is created, it will auto-recreate with correct vector size
```

---

## 8. Supported File Formats

| Format | Extensions | Method |
|--------|-----------|--------|
| PDF | `.pdf` | pymupdf (direct text + OCR fallback) |
| Word | `.docx`, `.doc` | python-docx |
| PowerPoint | `.pptx`, `.ppt` | python-pptx |
| Excel | `.xlsx`, `.xls` | pandas (all sheets) |
| CSV | `.csv` | pandas (auto-detect delimiter) |
| Plain text | `.txt` | UTF-8 read |
| JSON | `.json` | Pretty-printed |
| HTML | `.html`, `.htm` | BeautifulSoup (text extraction) |
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp`, `.gif`, `.webp` | Tesseract OCR |
| Everything else | any | textract fallback |

---

## 9. Troubleshooting

### "Collection not found"
The collection auto-creates on first use. Just call `ingest_document()` or instantiate `QdrantStore()`.

### "Dimension mismatch"
Delete and recreate: `client.delete_collection("lexai_documents")`. The next `QdrantStore()` call creates it with the correct `vector_size`.

### "Qdrant connection refused"
Make sure Docker is running:
```bash
docker compose up -d qdrant
```

### "Tesseract not found" (OCR)
Install Tesseract OCR for Windows:
1. Download: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default path (`C:\Program Files\Tesseract-OCR\`)
3. The code auto-detects it

### Slow embedding on first run
Local models download on first use (~80MB for MiniLM-L6-v2). Subsequent runs are cached.

---

## 10. File Reference

| File | Purpose |
|------|---------|
| `services/ingestion/parser.py` | Multi-format document parser |
| `services/ingestion/chunker.py` | Text chunking (4 strategies) |
| `services/ingestion/embedding.py` | Embedding (local + OpenAI) |
| `services/ingestion/storage.py` | Qdrant upsert/search/delete |
| `services/ingestion/metadata.py` | Metadata extraction |
| `services/ingestion/ocr.py` | Tesseract OCR helpers |
| `services/ingestion/pipeline.py` | Full pipeline orchestrator |
| `routes/documents.py` | Upload/search/delete API endpoints |