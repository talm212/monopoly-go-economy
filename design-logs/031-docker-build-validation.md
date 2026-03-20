# 031 — Docker Build Validation

**Date:** 2026-03-21
**Status:** Complete
**Feature:** #30 — Pre-commit hook: Docker build validation

## Context

Multiple deployment bugs stemmed from Docker build issues (missing files, dependency
mismatches, stage failures) that were not caught until deployment to ECS Fargate. We
need a validation step that developers can run before pushing deployment changes.

## Decision

Create a standalone validation script (`scripts/validate_docker.sh`) rather than a
pre-commit hook. Rationale:

1. **Docker builds are slow** — a full `--no-cache` build takes 30-60+ seconds. Making
   this mandatory on every commit would destroy developer velocity.
2. **Docker daemon dependency** — pre-commit hooks should not require Docker to be
   running. Developers working on non-Docker changes should not be blocked.
3. **Explicit > implicit** — a script that developers consciously run before deployment
   changes is clearer than an automatic hook that might be skipped with `--no-verify`.

## Implementation

- `scripts/validate_docker.sh` — builds the image for `linux/amd64` (production
  architecture on ECS Fargate) with `--no-cache` to catch missing dependencies.
- Validates Docker availability and daemon status before attempting the build.
- Documents the script in CLAUDE.md and README.md so it is discoverable.

## Outcome

Deployment-breaking Docker issues can now be caught locally before pushing. The script
is suitable for both manual use and CI pipeline integration.
