"""
FastAPI entrypoint for the PSX MemoryAgent backend.

Modular web layer (auth / chats / memory routers) over the pure agent logic in `app/`.
Run:  uvicorn backend.main:app --host 0.0.0.0 --port 8086
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.db import init_tables
from backend.routers import auth, chats, memory

# Where make_graph writes chart PNGs; served read-only at /charts. Mounted as a Docker
# volume in production so historical charts survive rebuilds.
CHARTS_DIR = os.getenv("CHARTS_DIR", "charts")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create the app tables on startup (idempotent). Don't crash the whole app if the
    # DB is briefly unavailable — requests will surface a clear error instead.
    try:
        await init_tables()
        print("[startup] app tables ready")
    except Exception as e:
        print(f"[startup] WARNING: init_tables failed: {e}")
    yield


app = FastAPI(title="PSX MemoryAgent API", lifespan=lifespan)

# Bearer-token auth (no cookies) -> "*" origins are safe. Tighten before submission.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chats.router)
app.include_router(memory.router)

# Serve generated chart images. Create the dir first so the mount never fails on a fresh
# deploy (before any chart exists).
os.makedirs(CHARTS_DIR, exist_ok=True)
app.mount("/charts", StaticFiles(directory=CHARTS_DIR), name="charts")


@app.get("/health")
def health():
    return {"status": "ok", "agent": "psx_agent"}
