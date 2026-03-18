# Monopoly Go Economy

Economy simulation platform for Monopoly Go game mechanics. Built for the economy team to simulate, analyze, and tune game features at scale (1M+ players).

## Quick Start

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run coin flip simulation (after Feature #8)
poetry run simulate --input coin-flip-assignment/input_table.csv \
                    --config coin-flip-assignment/config_table.csv \
                    --threshold 100

# Run Streamlit dashboard (after Feature #9)
poetry run streamlit run src/ui/app.py
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Simulation Engine | Python 3.12+, NumPy (vectorized RNG), Polars (data processing) |
| Dashboard | Streamlit (multi-page, self-service) |
| AI | Claude via Bedrock (prod) / Anthropic API (dev) |
| Infrastructure | AWS CDK (Python) — ECS Fargate, S3, DynamoDB |
| Testing | pytest with TDD workflow |

## Project Structure

```
src/
├── domain/            # Pure business logic (no I/O)
│   ├── protocols.py   # SimulatorConfig, SimulationResult, Simulator interfaces
│   ├── models/        # Data models (CoinFlipConfig, etc.)
│   └── simulators/    # Simulation engines + registry
├── application/       # Use cases (RunSimulation, AnalyzeResults, etc.)
├── infrastructure/    # I/O (Polars CSV, S3, LLM clients, DynamoDB)
└── ui/                # Streamlit dashboard
tests/                 # Mirrors src/ structure
infra/                 # AWS CDK stacks
```

## Local Claude Code Setup

After cloning, install these local-only tools:

```bash
# Streamlit skills (17 sub-skills for dashboard development)
cd .claude/skills && git clone https://github.com/streamlit/agent-skills.git streamlit

# AutoForge commands (if using autoforge)
# These ship with the autoforge npm package — no manual install needed
```

## Architecture

See [docs/plans/2026-03-19-system-design.md](docs/plans/2026-03-19-system-design.md) for full system design.

**Key principle:** Every component is protocol-based and reusable. Adding a new game feature (loot tables, reward distributions) requires only implementing the `Simulator` protocol and one Streamlit page. Everything else (I/O, orchestration, AI, dashboard components) works automatically.

## Development

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov

# Type checking
poetry run mypy src/

# Linting
poetry run ruff check src/

# Format
poetry run ruff format src/
```

## Feature Tracking

Features are tracked in [AutoForge](https://github.com/AutoForgeAI/autoforge). See `PROJECT.md` for the full feature breakdown (23 features, 5 phases).
