"""FastAPI app: wraps Stage 1 (extraction) and Stage 2 (scoring) as direct
function imports — never shells out to the CLIs. Serves the built frontend
as static files from the same app so the whole thing runs with one command:

    uv run uvicorn backend.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import state
from backend.routers import chat, jds, jobs, resumes, shortlist

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.init_singletons()
    try:
        yield
    finally:
        state.shutdown_singletons()


app = FastAPI(title="Resume Shortlisting Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jds.router)
app.include_router(resumes.router)
app.include_router(shortlist.router)
app.include_router(jobs.router)
app.include_router(chat.router)

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
