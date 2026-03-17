"""
Logistics Pro — FastAPI Application
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Entry point. Registers routers, middleware, and startup hooks.

Run:
    uvicorn app.main:app --reload --port 8000

Interactive docs:
    http://localhost:8000/docs      (Swagger UI)
    http://localhost:8000/redoc     (ReDoc)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database import engine
from app.models.models import Base
from app.routers import auth, shipments, tracking, copilot

# ── Create tables on startup (idempotent) ────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title       = settings.APP_NAME,
    version     = settings.APP_VERSION,
    description = """
## Logistics Booking & Tracking System API

### Features
- 📦 **Shipment Booking** — Create bookings with auto-generated docket numbers
- 🔢 **Docket Generation** — Format: `LGS{YYYYMMDD}{NNNNN}` — unique, sequential, transaction-safe
- 📍 **Status Updates** — Full lifecycle tracking with history events
- 🌐 **Public Tracking** — Anyone can track a shipment by docket number (no login needed)
- 🔐 **Role-based Auth** — JWT tokens, Admin and Staff roles

### Quick Start
1. **Seed the DB**: `python -m app.seed`
2. **Login**: `POST /auth/login` with `admin@logistics.com` / `Admin@123`
3. **Book a shipment**: `POST /shipments` with Bearer token
4. **Track publicly**: `GET /track/{docket_number}`
""",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],   # Restrict in production
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(shipments.router)
app.include_router(tracking.router)
app.include_router(copilot.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"], summary="Health check")
def root():
    return {
        "status":  "ok",
        "app":     settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs":    "/docs",
    }


@app.get("/health", tags=["Health"], summary="Liveness probe")
def health():
    return {"status": "healthy"}
