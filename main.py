from fastapi import FastAPI
from routes.documents import router as documents_router
from routes.auth import router as auth_router
from routes.cases import router as cases_router
from routes.analysis import router as analysis_router
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload models on startup so first request isn't slow."""
    print("[startup] Preloading embedding model...")
    try:
        from services.ingestion.embedding import EmbeddingModel

        model = EmbeddingModel()
        # Warm up with a dummy text to trigger model download + GPU warmup
        model.embed(["warmup"])
        print(f"[startup] Embedding model ready (dim={model.dim})")
    except Exception as e:
        print(f"[startup] WARNING: Embedding model not preloaded: {e}")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(cases_router)
app.include_router(documents_router)
app.include_router(analysis_router)