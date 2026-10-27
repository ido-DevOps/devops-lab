"""URL shortener API.

Business endpoints:  POST /links, GET /r/{code}
Ops endpoints:       GET /health (liveness), GET /ready (readiness), GET /metrics (Prometheus)
"""

import os
import time
from typing import Annotated

import redis
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, HttpUrl

from app.storage import LinkStore

# Config comes from the environment (12-factor), so the same image runs on a laptop, in Compose and in Kubernetes.
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# from_url() doesn't connect yet; the first command does. A short timeout keeps requests from hanging if Redis is gone.
_redis = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)

# --- Prometheus metrics --------------------------------------------------------------------------
REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "route"])
LINKS_CREATED = Counter("links_created_total", "Short links created")
REDIRECTS = Counter("redirects_total", "Short link lookups", ["result"])  # result = found | not_found

app = FastAPI(title="devops-lab shortener")


def get_store() -> LinkStore:
    """FastAPI dependency. Tests replace it with a store backed by fakeredis."""
    return LinkStore(_redis)


Store = Annotated[LinkStore, Depends(get_store)]  # endpoints that need storage declare `store: Store`


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    # Label by route *template* ("/r/{code}"), not the real path ("/r/ab12xY"): one time series per route,
    # not one per link. Unbounded label values ("high cardinality") can take Prometheus down.
    route = request.scope.get("route")
    path = route.path if route else "unmatched"
    REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
    return response


@app.exception_handler(redis.RedisError)
async def redis_unavailable(request: Request, exc: redis.RedisError):
    # The database is down: answer "503 try later" instead of a generic 500 crash.
    return JSONResponse({"detail": "storage unavailable"}, status_code=503)


# --- Business endpoints --------------------------------------------------------------------------
class LinkIn(BaseModel):
    url: HttpUrl  # pydantic rejects anything that isn't an http(s) URL → FastAPI answers 422


@app.post("/links", status_code=201)
def create_link(body: LinkIn, request: Request, store: Store):
    code = store.create(str(body.url))
    LINKS_CREATED.inc()
    return {"code": code, "short_url": f"{request.base_url}r/{code}"}


@app.get("/r/{code}")
def follow_link(code: str, store: Store):
    url = store.get(code)
    if url is None:
        REDIRECTS.labels("not_found").inc()
        raise HTTPException(status_code=404, detail="link not found")
    REDIRECTS.labels("found").inc()
    return RedirectResponse(url, status_code=302)


# --- Ops endpoints -------------------------------------------------------------------------------
@app.get("/health")
def health():
    # Liveness: "is the process alive?" Deliberately does NOT check Redis. If Redis is down,
    # restarting this app wouldn't fix it.
    return {"status": "ok"}


@app.get("/ready")
def ready(store: Store):
    # Readiness: "can I serve real traffic right now?" Kubernetes stops routing traffic here while this is 503.
    if store.ping():
        return {"status": "ready"}
    return JSONResponse({"status": "redis unreachable"}, status_code=503)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
