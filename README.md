# Monopoly Go Economy

Economy simulation platform for Monopoly Go game mechanics. Built for the economy team to simulate, analyze, and tune game features at scale (1M+ players) with AI-powered insights.

## Quick Start

```bash
# Install dependencies
poetry install

# Run tests (274 tests)
poetry run pytest

# Run coin flip simulation via CLI
poetry run python -m src.cli coin-flip-assignment/input_table.csv \
                              coin-flip-assignment/config_table.csv \
                              --threshold 100 --seed 42

# Write required summary CSV output
poetry run python -m src.cli coin-flip-assignment/input_table.csv \
                              coin-flip-assignment/config_table.csv \
                              --output results_summary.csv \
                              --output-players results_players.csv \
                              --threshold 100 --seed 42

# Run Streamlit dashboard
poetry run streamlit run src/ui/app.py

# Docker
docker compose up
```

## Output Format

The `--output` flag writes a **summary CSV** with the exact columns specified in the assignment:

```csv
total_roll_interactions,success_0_count,success_1_count,...,success_N_count,total_points,players_above_threshold
```

The `--output-players` flag writes a **per-player CSV** with detailed results:

```csv
user_id,rolls_sink,avg_multiplier,about_to_churn,total_points,num_interactions
```

## Assumptions

1. **Integer interactions**: `interactions = rolls_sink // avg_multiplier` uses floor division. A player with `rolls_sink=15, avg_multiplier=10` gets 1 interaction (not 1.5). This matches the game mechanic where each interaction costs exactly `avg_multiplier` rolls.

2. **Cumulative points**: Points are accumulated across flips in a chain. With `point_values=[1, 2, 4, 8, 16]`, achieving depth 3 (three consecutive heads) earns `1 + 2 + 4 = 7` points per interaction.

3. **Points scaled by multiplier**: After computing the base points for an interaction, the result is multiplied by the player's `avg_multiplier`. A player with `avg_multiplier=10` who earns 7 base points gets `7 × 10 = 70` points for that interaction.

4. **Churn boost capped at 1.0**: The `about_to_churn` boost multiplies each flip probability by 1.3 (configurable), but caps at 1.0 since probabilities cannot exceed 100%.

5. **Default churn status**: If the `about_to_churn` column is absent from the input CSV, all players default to `false` (no boost applied).

## How `about_to_churn` Affects Probabilities

Players flagged with `about_to_churn=true` receive boosted success probabilities:

```
boosted_probability = min(base_probability × churn_boost_multiplier, 1.0)
```

With the default config (`churn_boost_multiplier=1.3`):

| Flip Depth | Base Probability | Boosted (Churn) | Cap Applied? |
|------------|-----------------|-----------------|--------------|
| 1 | 60% | 78% | No |
| 2 | 50% | 65% | No |
| 3 | 50% | 65% | No |
| 4 | 50% | 65% | No |
| 5 | 50% | 65% | No |

This means churning players are more likely to get deeper flip chains, earning more points on average. The boost is configurable via `--churn-boost` on the CLI (default 1.3).

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Simulation Engine | Python 3.12+, NumPy (vectorized RNG), Polars (data processing) |
| Dashboard | Streamlit (multi-page: upload, run, results, AI insights, history) |
| AI | Claude via Bedrock (prod) / Anthropic API (dev) — insights, chat, optimizer |
| Infrastructure | AWS CDK (Python) — VPC, ECS Fargate, ALB, S3, DynamoDB, Secrets Manager |
| Testing | pytest (274 tests), TDD workflow, 100K players in ~2s |

## Features

### Coin Flip Simulator
- Vectorized NumPy engine processing 1M+ players in <10 seconds
- Configurable probabilities, point values, churn boost (1.3x, capped at 1.0)
- CLI with threshold, seed, summary output, and per-player output options

### Streamlit Dashboard
- Upload player data + config CSVs
- Run simulations with optional seed
- KPI cards, success distribution charts, points histograms
- Churn vs non-churn comparison
- CSV export, simulation history, run comparison

### AI Features
- **Insights Analyst** — auto-analyzes results, generates findings + recommendations
- **Chat Assistant** — natural language Q&A about simulation data
- **Config Optimizer** — iterative LLM + simulation loop to hit target outcomes

### AWS Infrastructure (CDK)
- VPC (2 AZs), ECS Fargate + ALB, S3, DynamoDB
- Secrets Manager, SSM Parameters, CloudWatch alarms
- Docker multi-stage build with health checks

## Project Structure

```
src/
├── domain/            # Pure business logic (no I/O)
│   ├── protocols.py   # SimulatorConfig, SimulationResult, Simulator interfaces
│   ├── models/        # CoinFlipConfig, CoinFlipResult, Insight, OptimizationTarget
│   └── simulators/    # CoinFlipSimulator + SimulatorRegistry
├── application/       # Use cases
│   ├── run_simulation.py    # Generic orchestrator (works with any simulator)
│   ├── analyze_results.py   # AI insights analyst
│   ├── chat_assistant.py    # AI chat Q&A
│   └── optimize_config.py   # AI config optimizer
├── infrastructure/    # I/O boundary
│   ├── readers/       # LocalDataReader (Polars CSV)
│   ├── writers/       # LocalDataWriter
│   ├── llm/           # LLMClient protocol + Anthropic/Bedrock adapters
│   └── store/         # LocalSimulationStore (JSON files)
├── ui/                # Streamlit dashboard
│   ├── app.py         # Entry point
│   ├── components/    # Reusable: upload, config editor, KPIs, charts, chat panel
│   └── pages/         # Coin Flip, AI Insights, History
└── cli.py             # CLI entrypoint
tests/                 # 274 tests mirroring src/
infra/                 # AWS CDK stacks (network, data, compute, pipeline)
```

## Architecture

See [docs/plans/2026-03-19-system-design.md](docs/plans/2026-03-19-system-design.md) for full HLD + LLD.

**Key principle:** Protocol-based and reusable. Adding a new game feature requires only:
1. Implement `Simulator` protocol (config + result + engine)
2. Register in `SimulatorRegistry`
3. Add one Streamlit page

Everything else (I/O, orchestration, AI, dashboard components) works automatically.

## Development

```bash
poetry run pytest              # Run all 274 tests
poetry run pytest --cov        # With coverage report
poetry run pytest -m unit      # Unit tests only
poetry run pytest -m slow      # Performance tests
poetry run mypy src/           # Type checking
poetry run ruff check src/     # Linting
poetry run ruff format src/    # Format
```

## Deployment Validation

Before pushing changes that affect `Dockerfile`, dependencies, or deployment config:

```bash
bash scripts/validate_docker.sh
```

This builds the Docker image for `linux/amd64` (production architecture on ECS Fargate)
with `--no-cache` to catch missing files, dependency mismatches, and stage failures.
Not run on every commit — only before deployment changes.

## AI Setup

```bash
# Local dev — Anthropic API
export ANTHROPIC_API_KEY=your-key
export LLM_PROVIDER=anthropic

# Production — AWS Bedrock (no API key needed, uses IAM)
export LLM_PROVIDER=bedrock
```

## Local Claude Code Setup

After cloning, install these local-only tools:

```bash
# Streamlit skills (17 sub-skills for dashboard development)
cd .claude/skills && git clone https://github.com/streamlit/agent-skills.git streamlit
```

## Feature Tracking

All 23 features tracked in [AutoForge](https://github.com/AutoForgeAI/autoforge). See `PROJECT.md` for details.
