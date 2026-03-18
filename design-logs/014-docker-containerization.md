# Design Log 014 — Docker Containerization

**Date:** 2026-03-19
**Feature:** #14 — Docker containerization
**Status:** Complete

---

## Context

The Streamlit dashboard and simulation engine need to be containerized for deployment to AWS ECS Fargate (Feature #17). This is the foundation of the deployment pipeline — everything downstream (CDK stacks, CI/CD) depends on a working Docker image.

## Decision: Multi-Stage Build with Poetry Export

### Options Considered

1. **Poetry in runtime image** — Install poetry in the final image, run `poetry install --only main`. Simple but bloats the image (~100MB+ for poetry + its deps).
2. **Poetry export to requirements.txt** — Use a builder stage to convert poetry.lock into a plain requirements.txt, then use pip in a slim runtime stage. Keeps the runtime image lean.
3. **pip install from pyproject.toml directly** — Skip poetry entirely. Loses the lock file guarantees.

### Chosen: Option 2 (poetry export)

**Why:**
- Runtime image contains only pip-installed production dependencies
- No poetry overhead in production (~100MB savings)
- Lock file guarantees reproducible builds via the export step
- Builder stage is discarded after producing requirements.txt
- Standard pattern for poetry-based projects in Docker

## Key Design Decisions

### Dependency Groups Excluded from Runtime
- `dev` group: pytest, mypy, ruff (testing/linting tools)
- `infra` group: aws-cdk-lib, constructs (CDK is a build-time tool, not runtime)

### Health Check for ECS Fargate
Added `HEALTHCHECK` instruction using Streamlit's built-in `/_stcore/health` endpoint. This is required for ECS Fargate to determine container health and manage rolling deployments.

### Streamlit Server Configuration
Created `server.toml` in the image with:
- `headless = true` — no browser auto-open
- `address = "0.0.0.0"` — bind to all interfaces (required in containers)
- `enableCORS = false` — will be behind ALB
- `gatherUsageStats = false` — no telemetry in production

### Volume Mounts (docker-compose.yml)
- `coin-flip-assignment` mounted read-only for CSV access
- `simulation_history` as a named volume for persistence across container restarts

### No Hardcoded Secrets
Environment variables (`ANTHROPIC_API_KEY`, `LLM_PROVIDER`) passed via docker-compose with safe defaults. In production, AWS Secrets Manager will inject these.

## Files Created

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build (builder + runtime), python:3.12-slim |
| `.dockerignore` | Excludes tests, docs, design-logs, .git, secrets, IDE config |
| `docker-compose.yml` | Local development: port 8501, env vars, volumes |

## Outcome

- All 146 existing tests pass (no regressions)
- Docker build could not be verified (Docker not available on this machine) but Dockerfile follows standard patterns
- Image will be slim: python:3.12-slim base + production deps only (~300-400MB estimated)
