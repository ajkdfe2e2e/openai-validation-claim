"""FastAPI 主入口。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .routers import claim, mail, npo, orgs


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(title="OpenAI Validation Claim", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


app.include_router(claim.router)
app.include_router(npo.router)
app.include_router(orgs.router)
app.include_router(mail.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


# 静态资源
if (FRONTEND_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.exception_handler(Exception)
async def _all_exc(_request, exc):
    return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})