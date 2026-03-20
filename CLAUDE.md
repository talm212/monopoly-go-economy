# Monopoly Go Economy — Project Instructions

## Overview
Economy simulation platform for Monopoly Go game mechanics. Built for the economy team to simulate, analyze, and tune game features (coin flip, loot tables, reward distributions) at scale — millions of players.

## Design Log Methodology
- **MANDATORY**: Update the design log in `/design-logs/` before executing any task
- Follow the Design Log methodology: https://design-log-methodology.vercel.app/
- Each design log is a numbered Markdown file (e.g., `001-design-log-setup.md`)
- Capture: decisions, thinking, failures, pivots, and outcomes

## Tech Stack
- **Python 3.12+** — simulation engine, all business logic
- **Polars** — data processing (NOT Pandas). Mandatory for any DataFrame work. 10-50x faster at scale.
- **NumPy** — vectorized random number generation for simulations
- **Streamlit** — economy team dashboard (upload CSVs, configure params, run sims, visualize)
- **AWS CDK (Python)** — infrastructure as code for deployment
- **pytest** — test runner with TDD workflow
- **Docker** — containerization for deployment

## Architecture Principles (Staff Engineer / Architect Level)
- **Clean Architecture**: Separate concerns — domain (simulation logic), application (orchestration), infrastructure (I/O, AWS)
- **SOLID Principles**: Single responsibility, open/closed, Liskov substitution, interface segregation, dependency inversion
- **TDD**: Write failing test first, confirm failure, implement, verify pass, refactor, commit
- **Dependency Injection**: Use DI for testability and loose coupling
- **Domain-Driven Design**: Model game mechanics as explicit domain objects
- **Interface-First**: Define contracts (protocols/ABCs) before implementations
- **Performance-First**: Vectorize operations with NumPy/Polars. Never loop over millions of rows in Python.

## Code Conventions
- Python with type hints everywhere (strict mypy)
- Use `dataclasses` or `pydantic` for data models
- Use `Protocol` / `ABC` for interfaces
- Use `logging` module — never `print()`
- No magic numbers — extract to named constants or config
- No hardcoded paths — use environment variables or config
- Docstrings on public APIs only (Google style)

## Testing
- **pytest** as test runner
- TDD workflow: Red → Green → Refactor
- Coverage targets: 80%+ for simulation engine, 70%+ overall
- Unit tests for pure simulation logic (deterministic with seeded RNG)
- Integration tests for CSV I/O and end-to-end flows
- Use `pytest.fixture` for test data, `pytest.mark.parametrize` for edge cases
- **Seed all random operations** in tests for reproducibility

## Performance Requirements
- Must handle 1M+ player rows efficiently
- Vectorize with NumPy for random number generation (generate all flips at once)
- Use Polars for data ingestion, aggregation, and output
- Target: <10 seconds for 1M players on local machine
- Profile before optimizing — use `cProfile` or `line_profiler`

## Project Structure
```
/                          # Project root
├── CLAUDE.md              # This file — project instructions
├── design-logs/           # Design decision documentation
├── coin-flip-assignment/  # Original assignment (PDF, CSVs)
├── src/                   # Source code
│   ├── domain/            # Pure business logic (simulation engines)
│   ├── application/       # Orchestration, use cases
│   ├── infrastructure/    # I/O, AWS, file handling
│   └── ui/                # Streamlit dashboard
├── tests/                 # Test suite (mirrors src/ structure)
├── infra/                 # AWS CDK stacks
├── .claude/               # Claude Code configuration
└── .mcp.json              # MCP server configuration (AutoForge)
```

## Feature Simulators (Planned)
1. **Coin Flip** — sequential flip chain with configurable probabilities and rewards (FIRST)
2. Future: Loot tables, reward distributions, event economies, etc.

## Tools & Integrations
- **AutoForge**: Feature/task tracking via MCP — use for planning phases and tracking features
- **Streamlit Skills**: 17 official sub-skills for building the dashboard (layouts, charts, performance, themes)
- **AWS CDK Skill**: Infrastructure best practices, construct patterns, deployment workflows
- **Deploy on AWS Skill**: Automated service selection, cost estimation, security defaults
- **Design Logs**: Decision documentation before every task

## Deployment Validation
- Before deploying: run `bash scripts/validate_docker.sh` to validate Docker build
- Always use `--platform linux/amd64` (production runs on x86 Fargate)
- Not a pre-commit hook — Docker builds are too slow for every commit
- Suitable for manual use and CI pipeline integration

## Key Domain Concepts (Coin Flip)
- **Interaction**: One coin-flip sequence triggered by landing on a tile. `interactions = rolls_sink / avg_multiplier`
- **Flip Chain**: Up to `max_successes` sequential flips. Each flip has independent probability. Stops on first tails.
- **Points**: Cumulative reward for successful flips in a chain. Final points multiplied by `avg_multiplier`.
- **Churn Boost**: Players with `about_to_churn=true` get 1.3x multiplier on success probabilities (capped at 1.0).
- **Config**: Probabilities and point values per flip depth (p_success_n, points_success_n).
