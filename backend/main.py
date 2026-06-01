import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from db.init_db import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build BM25 index on startup if missing
    try:
        from services.bm25_index import build_index, load_index, save_index

        if load_index() is None:
            logger.info("BM25 index not found, building...")
            bm25, meta = build_index()
            save_index(bm25, meta)
            logger.info("BM25 index built with %d docs", len(meta))
    except Exception as exc:
        logger.warning("BM25 index build failed (continuing without it): %s", exc)
    # FastAPI handles startup event
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)