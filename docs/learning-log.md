# Learning log

One entry per phase: what was built, why, the commands, the gotchas, and interview questions with answers.

---

## Phase 0 — Workstation setup

**Machine:** MacBook Air 15 (Apple M5, arm64), 32 GB RAM, macOS.

### What was installed and why
| Tool | Version | What it does |
|---|---|---|
| OrbStack | 2.2.5 | Runs a lightweight Linux VM with the Docker engine inside. Replaces Docker Desktop. |
| Docker CLI + Compose | 29.8 / 5.5 | Build and run containers; Compose runs multi-container stacks locally. |
| kubectl | 1.37 | CLI that talks to any Kubernetes API server. |
| k3d | 5.9 | Runs k3s (lightweight Kubernetes) inside Docker containers, so each node is a container. |
| Helm | 4.3 | Package manager for Kubernetes; charts are templated manifests. |
| Terraform | 1.17 | Declarative infrastructure as code with a state file. |
| Python 3.12 + uv | 3.12 / 0.13 | Modern Python plus a fast package/environment manager (macOS ships 3.9). |
| Trivy | 0.76 | Scans container images and dependencies for known vulnerabilities (CVEs). |

```bash
brew install --cask orbstack
brew install kubectl k3d helm python@3.12 uv trivy
brew tap hashicorp/tap && brew install hashicorp/tap/terraform
docker run --rm hello-world   # sanity check
```

### Gotchas
- **`docker: command not found` after installing OrbStack** — the CLI is only linked into `PATH` the first
  time the OrbStack app is opened.
- **Terraform is no longer in Homebrew core** (HashiCorp moved to the BSL licence in 2023), so it comes
  from HashiCorp's own tap. OpenTofu is the open-source fork.
- **Public repo + private reusable workflows don't mix.** This repo's CI calls reusable workflows in a
  separate `ido-pipeline` repo. While that repo was private, every run failed in 0 s with
  "workflow file issue": GitHub only lets a private repo's workflows be called by private repos of the
  same owner. Fix: make the central pipeline repo public.

### Interview questions
**Q: What is Docker Desktop actually doing on a Mac?**
Containers are not VMs — they are isolated processes that share the host's Linux kernel (namespaces for
isolation, cgroups for resource limits). macOS has no Linux kernel, so Docker Desktop runs a lightweight
Linux VM with the Docker engine inside and wires up the CLI, networking (`localhost` ports) and file
sharing so it feels native. OrbStack and Colima do the same job; I use OrbStack because it is lighter
on Apple Silicon and free for personal use (Docker Desktop needs a paid plan in larger companies).

**Q: Container vs virtual machine?**
A VM virtualises hardware and runs its own full kernel; a container shares the host kernel and only
packages the app and its userspace. Containers start in milliseconds and are much smaller, but give
weaker isolation than a VM.

**Q: Why k3d instead of minikube or kind?**
All three give a local cluster. k3d runs k3s — a certified, lightweight Kubernetes distribution — in
Docker, so multi-node clusters start in seconds, and it ships with an ingress controller (Traefik) and
a local-path storage provisioner out of the box.

**Q: How is CI organised across your projects?**
One central repo (`ido-pipeline`) holds reusable GitHub Actions workflows: secrets scan (gitleaks),
lint/tests, security scans (Semgrep, Bandit, pip-audit) and a "Conflict Guard" that warns when two PRs
change the same lines. Each project has a tiny `pipeline.yml` pinned to a `v1` tag, so a fix in one
place reaches every project, and a bad release can be rolled back by moving the tag.

---

## Phase 1 — The app

**What:** a URL shortener in FastAPI with Redis as storage, plus pytest tests. ~100 lines of Python.
The app is only a workload for the later phases, but it was built with ops in mind from day one.

### Files
| File | Role |
|---|---|
| `app/storage.py` | `LinkStore`: create/get links in Redis, `ping()` for readiness |
| `app/main.py` | endpoints, Prometheus metrics middleware, Redis-error → 503 handler |
| `tests/test_app.py` | 9 tests using `fakeredis` |
| `pyproject.toml` / `uv.lock` | dependencies; `uv.lock` pins exact versions for reproducible installs |

### Design decisions
- **Config from env vars (12-factor).** `REDIS_URL` decides where Redis is, so one image runs everywhere.
- **Liveness ≠ readiness.** `/health` never touches Redis; `/ready` does. If Redis dies, the pod should
  stop getting traffic, not be restarted in a loop (restarting the app can't fix the database).
- **Redis down → 503, not 500.** A 503 says "temporarily unavailable, retry"; a 500 says "bug".
- **Metrics labelled by route template** (`/r/{code}`), never by the real path. Every unique label value
  is a new time series in Prometheus; one per link would explode memory ("cardinality explosion").
- **`secrets` instead of `random`** for codes, so links can't be guessed. `SET ... NX` makes sure a rare
  code collision never overwrites an existing link.
- **Input validation with pydantic `HttpUrl`**: only http/https URLs are accepted (blocks `javascript:`
  links, which would otherwise make this an XSS/phishing tool). Invalid input → 422 automatically.
- **Redirects live under `/r/`** so a random code can never collide with `/health`, `/ready` or `/metrics`.
- **Dependency injection** (`Depends(get_store)`): tests swap the real Redis store for a fake one
  without touching app code.

### Commands
```bash
uv sync --extra dev && uv run pytest
docker run -d --rm --name lab-redis -p 6379:6379 redis:7-alpine
uv run uvicorn app.main:app --reload
curl -X POST localhost:8000/links -H 'content-type: application/json' -d '{"url":"https://github.com"}'
curl -i localhost:8000/r/<code>
docker exec lab-redis redis-cli GET link:<code>     # see the raw key in Redis
```

### Gotchas
- `GET /r/{code}` in tests: the test client follows redirects by default; pass `follow_redirects=False`
  to assert on the 302 itself.
- pydantic normalises URLs (`https://github.com` → `https://github.com/`), so compare carefully in tests.

### Interview questions
**Q: Difference between a liveness and a readiness probe?**
Liveness asks "is the process healthy?" — failing it makes Kubernetes restart the container. Readiness
asks "can it serve traffic now?" — failing it removes the pod from the Service's endpoints but does not
restart it. A dependency outage should fail readiness, not liveness, or you get pointless restart loops.

**Q: What is high cardinality in metrics and why does it matter?**
Each unique combination of label values is its own time series. Labels with unbounded values (user IDs,
raw URLs) create millions of series, which blows up Prometheus memory and query time. Use bounded labels
like route templates and status codes.

**Q: Why use a fake Redis in tests instead of a real one?**
Unit tests should be fast, isolated and runnable anywhere (CI has no Redis). fakeredis implements the
Redis API in memory. The trade-off: it can't catch real-server issues, so integration against real Redis
happens in docker-compose (Phase 2).

**Q: What is 12-factor config?**
Store config in the environment, not in code. The same build artifact is promoted through
dev → staging → prod, and only env vars change.
