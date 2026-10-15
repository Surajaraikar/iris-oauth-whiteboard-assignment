import json
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import router
from app.core.config import get_settings
from app.db.session import engine

logging.basicConfig(level=logging.INFO, format='%(message)s')
app = FastAPI(title="iris OAuth Whiteboard API", version="0.1.0")
cfg = get_settings()
_limits: dict[str, list[float]] = {}
app.add_middleware(CORSMiddleware, allow_origins=[cfg.frontend_origin], allow_credentials=True, allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token", "X-Idempotency-Key"])

@app.middleware("http")
async def correlation(request: Request, call_next):
    started = time.monotonic()
    sensitive = request.url.path in {"/api/v1/auth/google/start", "/api/v1/auth/google/callback", "/api/v1/search-console/inspect", "/api/v1/indexing/notifications"} or (request.method == "DELETE" and request.url.path.startswith("/api/v1/connections/"))
    if sensitive:
        route_group = "/api/v1/connections/{id}" if request.url.path.startswith("/api/v1/connections/") else request.url.path
        bucket = str(request.client.host if request.client else "unknown") + route_group
        now = time.monotonic(); recent = [t for t in _limits.get(bucket, []) if now - t < 60]
        if len(recent) >= 30:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded; retry shortly"})
        recent.append(now); _limits[bucket] = recent
    request.state.correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    logging.getLogger("iris.request").info(json.dumps({"event": "http_request", "correlation_id": request.state.correlation_id, "method": request.method, "path": request.url.path, "status": response.status_code, "duration_ms": round((time.monotonic() - started) * 1000, 2)}))
    if "iris_csrf" not in request.cookies:
        import secrets
        response.set_cookie("iris_csrf", secrets.token_urlsafe(32), httponly=False, secure=cfg.secure_cookies, samesite="lax", max_age=43200, path="/")
    return response

@app.get("/health")
async def health(): return {"status": "ok"}

@app.get("/ready")
async def ready():
    try:
        async with engine.connect() as connection: await connection.exec_driver_sql("SELECT 1")
        return {"status": "ready", "database": "ok"}
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable"})

app.include_router(router)
