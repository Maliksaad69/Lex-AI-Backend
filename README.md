# LexAI — Litigation Intelligence Platform

**AI-powered legal case analysis, document intelligence, and jury simulation.**

LexAI is a full‑stack litigation intelligence platform that helps legal professionals analyse case documents, extract structured legal insights, and simulate jury deliberations — all powered by large language models.

---

## Architecture

```
┌──────────────┐     ┌─────────────────────────────────────────────┐
│  Next.js     │     │            FastAPI Backend                  │
│  Frontend    │◄───►│                                             │
│  (port 3000) │     │  ┌─────────┐  ┌──────────┐  ┌───────────┐  │
└──────────────┘     │  │  Auth   │  │Document  │  │  Case     │  │
                     │  │  (JWT)  │  │Ingestion │  │ Analysis  │  │
                     │  └─────────┘  │ Pipeline  │  │ (7-agent) │  │
                     │               └──────────┘  └───────────┘  │
                     │                               ┌───────────┐  │
                     │                               │   Jury    │  │
                     │                               │Simulation │  │
                     │                               └───────────┘  │
                     └─────────────────────────────────────────────┘
                                │                  │
                         ┌──────▼──────┐    ┌──────┴──────┐
                         │ PostgreSQL  │    │   Qdrant    │
                         │   (data)    │    │ (vectors)   │
                         └─────────────┘    └─────────────┘
```

- **Backend**: FastAPI (Python) — RESTful API server
- **Database**: PostgreSQL 17 — case metadata, user accounts, analysis results
- **Vector Store**: Qdrant — semantic search over document chunks
- **LLM**: Mistral AI (primary) — powers all analysis agents and jury simulation
- **Frontend**: Next.js (App Router) with shadcn/ui components

---

## Core Modules

### 1. Document Ingestion Pipeline

Upload legal documents and automatically process them through a four‑stage pipeline:

```
 Upload ──► Parse ──► Chunk ──► Embed ──► Store (Qdrant + PostgreSQL)
```

**Supported formats:** PDF, DOCX, PPTX, XLSX, CSV, TXT, JSON, HTML, images (OCR via Tesseract)

**Chunking strategies:** sliding window, semantic, recursive, fixed — configurable per ingestion.

### 2. Case Analysis Pipeline

Orchestrates **7 specialised LLM agents** in a directed acyclic graph (DAG) to transform raw documents into a structured legal analysis:

| Agent | Extracts |
|-------|----------|
| **Facts** | Key factual statements from the document corpus |
| **Parties** | Named entities with roles (plaintiff, defendant, witness, expert) |
| **Claims** | Causes of action with supporting evidence and strength scoring |
| **Evidence Links** | Evidence-to-claim mappings with credibility assessments |
| **Timeline** | Chronological ordering of events across documents |
| **Contradictions** | Conflicting statements within and across sources |
| **Scoring** | Overall case strength assessment with reasoned rubric |

Results are persisted to PostgreSQL and returned as structured JSON for the frontend.

### 3. Jury Simulation

Generates a virtual jury panel using AI personas and simulates deliberation:

- **Persona Generator** — Creates diverse juror profiles (age, background, biases, profession) tailored to the case
- **Deliberation Agent** — Each persona debates the case based on the evidence
- **Aggregator** — Combines individual votes into a verdict prediction with confidence metrics
- **PDF Report** — Exports a professional jury report with full reasoning

---

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (for PostgreSQL + Qdrant)
- A Mistral AI API key (or Groq API key for fallback)

### 1. Clone & Environment Setup

```bash
git clone <repo-url>
cd litigation/backend

cp .env.example .env
# Edit .env with your API keys and database credentials
```

### 2. Start Infrastructure (PostgreSQL + Qdrant)

```bash
docker compose up -d
```

This starts:
- **PostgreSQL 17** on port `5432`
- **Qdrant** (vector DB) on port `6333`
- **pgAdmin4** on port `5050`

### 3. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Run Database Migrations

```bash
alembic upgrade head
```

### 5. Start the Backend

```bash
uvicorn main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 6. Start the Frontend

```bash
cd ../frontend
npm install
npm run dev
```

The UI is available at `http://localhost:3000`.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing secret |
| `MISTRAL_API_KEY` | Mistral AI API key |
| `MISTRAL_MODEL` | Mistral model name (default: `mistral-small-latest`) |
| `GROQ_API_KEY` | Groq API key (fallback) |
| `QDRANT_API_KEY` | Qdrant API key |
| `QDRANT_COLLECTION` | Qdrant collection name |
| `BACKEND_PORT` | API server port (default: `8000`) |
| `FRONTEND_PORT` | Frontend dev server port (default: `3000`) |

---

## API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/register` | Create user account |
| `POST` | `/token` | Login (JWT) |
| `POST` | `/upload-documents` | Upload case documents |
| `GET` | `/documents?case_id=` | List documents for a case |
| `GET` | `/documents/{id}/chunks` | Get document chunks from Qdrant |
| `DELETE` | `/documents/{id}` | Delete document |
| `POST` | `/cases/{id}/analyze` | Run 7-agent analysis pipeline |
| `GET` | `/cases/{id}/analysis` | Get analysis results |
| `POST` | `/cases/{id}/jury-simulation` | Run jury simulation |
| `GET` | `/cases/{id}/jury-simulation` | Get latest simulation |
| `GET` | `/juries/simulations/{id}` | Get simulation details |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **API Framework** | FastAPI |
| **ORM** | SQLModel (SQLAlchemy 2.0) |
| **Database** | PostgreSQL 17 |
| **Vector Database** | Qdrant |
| **LLM Provider** | Mistral AI (+ Groq fallback) |
| **Auth** | JWT (python-jose) + Argon2 |
| **Migrations** | Alembic |
| **Document Parsing** | PyMuPDF, python-docx, pytesseract, openpyxl |
| **Embeddings** | Sentence Transformers (local) / OpenAI |
| **Containerisation** | Docker, Docker Compose |
| **Frontend** | Next.js 15, shadcn/ui, Tailwind CSS |

---

## Project Structure

```
backend/
├── app/                    # Application code (copied into Docker image)
├── alembic/                # Database migration scripts
├── db/
│   ├── models/             # SQLModel ORM models
│   └── session.py          # Database session factory
├── models/                 # Pydantic request/response schemas
├── routes/                 # API route handlers
├── services/
│   ├── case_analysis/      # 7-agent analysis pipeline
│   │   ├── agents/         # Individual LLM agents
│   │   ├── graph/          # DAG orchestration + state management
│   │   ├── prompts/        # Agent system prompts
│   │   ├── repositories/   # Data persistence layer
│   │   └── services/       # LLM + Qdrant wrappers
│   ├── ingestion/          # Document upload → parse → chunk → embed → store
│   └── jury_simulation/    # AI jury deliberation engine
│       ├── agents/         # Persona generator, simulator, aggregator
│       ├── prompts/        # Jury system prompts
│       └── services/       # LLM, Qdrant, PDF report generation
├── uploads/                # Uploaded file storage
├── .env.example            # Environment template
├── docker-compose.yaml     # Infrastructure (PostgreSQL, Qdrant, pgAdmin)
├── Dockerfile              # API server container
└── requirements.txt        # Python dependencies
```

---

## Docker Deployment

```bash
# Build the API image
docker build -t lexai-backend .

# Full stack via Docker Compose
docker compose up -d
```

The Dockerfile uses a lightweight `python:3.12-alpine` base with `uvicorn` as the ASGI server.

---

## License

Proprietary — internal use.
