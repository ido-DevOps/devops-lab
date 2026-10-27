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
