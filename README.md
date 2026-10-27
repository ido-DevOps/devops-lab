# DevOps Lab

A hands-on DevOps portfolio project that runs entirely on a laptop: a small service taken from
code → container → CI → Kubernetes → GitOps → observability → infrastructure as code.

🚧 Work in progress — built phase by phase. See [`docs/learning-log.md`](docs/learning-log.md).

## The workload: a tiny URL shortener
FastAPI + Redis. The app is deliberately small; the point is everything around it.

| Endpoint | Purpose |
|---|---|
| `POST /links` `{"url": "..."}` | create a short link → `{"code", "short_url"}` |
| `GET /r/{code}` | 302 redirect to the original URL (404 if unknown) |
| `GET /health` | liveness: the process is up |
| `GET /ready` | readiness: Redis is reachable (503 if not) |
| `GET /metrics` | Prometheus metrics (request count/latency per route, links created, redirects) |

### Run locally
```bash
uv sync --extra dev                                    # create .venv and install deps
uv run pytest                                          # tests (use fakeredis, no Redis needed)
docker run -d --rm --name lab-redis -p 6379:6379 redis:7-alpine
uv run uvicorn app.main:app --reload                   # http://localhost:8000/docs
```
Config: `REDIS_URL` (default `redis://localhost:6379/0`).

## Progress
- [x] Phase 0 — workstation setup (OrbStack, kubectl, k3d, Helm, Terraform)
- [x] Phase 1 — the app + tests, CI via a central reusable pipeline
- [ ] Phase 2 — containers (multi-stage Dockerfile, docker-compose)
- [ ] Phase 3 — CI: build, scan (Trivy), push image to GHCR
- [ ] Phase 4 — Kubernetes (k3d): raw manifests, then Helm
- [ ] Phase 5 — GitOps with Argo CD
- [ ] Phase 6 — Observability: Prometheus + Grafana
- [ ] Phase 7 — Terraform: whole lab from zero with one command
