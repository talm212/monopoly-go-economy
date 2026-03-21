# Monopoly Go Economy Simulator

> AI-powered economy simulation platform. Upload player data, configure game mechanics, run simulations at scale (1M+ players in seconds), and get AI-generated insights with actionable recommendations.

**[Live Demo](http://Monopo-Strea-OsO4hfpMoUBg-1013735711.us-east-1.elb.amazonaws.com)** | **[Deep Dive Podcast (NotebookLM)](https://notebooklm.google.com/notebook/20fcf794-c3c1-4411-afd5-a152ce64fbd6?artifactId=5aa12e7d-6179-4de0-9242-c094d1196ffb)** | **[Documentation](docs/)**

---

## Assignment Deliverables

| # | Requirement | Status | Where |
|---|------------|--------|-------|
| 1 | **Code that reads inputs, runs simulation at scale, writes output CSV** | Done | `src/cli.py` reads player + config CSVs, runs vectorized simulation (1M+ players in ~10s), writes `results_summary.csv` + `results_players.csv` |
| 2 | **Runnable CLI to set reward threshold** | Done | `--threshold` / `-t` flag (default 100.0) — [Quick Start](#quick-start) |
| 3 | **CLI option for churn multiplier** | Done | `--churn-boost` / `-c` flag (default 1.3) — [Quick Start](#quick-start) |
| 4 | **README: how to run** | Done | [Quick Start](#quick-start) — `poetry install`, CLI command with all flags, Docker, Streamlit dashboard |
| 5 | **README: assumptions** | Done | [Assumptions](#assumptions-coin-flip) — integer interactions, cumulative points, churn cap, default churn |
| 6 | **README: how `about_to_churn` affects probabilities** | Done | [Dedicated section](#how-about_to_churn-affects-probabilities) — 1.3x multiplier, cap at 1.0, concrete examples |
| 7 | **Tests covering core rules** (optional) | Done | 672 tests — sequential successes, churn boost, points calculation, edge cases, integration, E2E |

### Beyond the Assignment

| Feature | What It Adds |
|---------|-------------|
| **Web Dashboard** | Self-service UI — no CLI needed, upload CSVs, edit config with sliders, visualize results |
| **AI Insights** | 3-5 actionable findings per run, ranked by severity |
| **AI Chat** | Ask questions about results in natural language |
| **AI Config Optimizer** | Set a target KPI → AI iteratively tunes config |
| **Insight-to-Sweep Pipeline** | Two clicks from "AI found a problem" to "here's the data" |
| **5 AI Models** | Claude Opus, Sonnet, DeepSeek R1, Llama 4, Nova Pro — all via Bedrock |
| **Parameter Sweep** | Sweep any parameter, see KPI impact as line chart |
| **Run Comparison** | Side-by-side KPI diff, distribution overlay, config delta |
| **PDF Report** | One-click export with KPIs, charts, config, AI insights |
| **Simulation History** | Every run saved, browsable, loadable |
| **AWS Deployment** | Live on ECS Fargate, 5 CDK stacks, CI/CD pipeline |
| **Clean Architecture** | 4 layers, Protocol-based interfaces, extensible for new game features |

---

## Table of Contents

- [Assignment Deliverables](#assignment-deliverables) — Each requirement mapped to its implementation
- [Product](#product) — Problem, Solution, Key Features, Coin Flip Mechanic
- [Technical Architecture](#technical-architecture) — Clean Architecture, Vectorization, AWS, Tech Stack, Testing
- [Key Decisions](#key-decisions) — 14 architectural choices with rationale
- [Roadmap](#roadmap-whats-next) — 5 phases from new simulators to team collaboration
- [Quick Start](#quick-start) — Install, run, deploy
- [Project Structure](#project-structure) — Source layout
- [How `about_to_churn` Affects Probabilities](#how-about_to_churn-affects-probabilities) — Churn boost mechanic explained
- [Assumptions](#assumptions-coin-flip) — Coin Flip domain rules
- [Documentation](#documentation) — Deep dives, design logs

---

## Product

### The Problem

Economy designers need to test configuration changes before pushing them to millions of real players. The current process: change a probability value, ask an engineer to run a script, wait for results, look at a spreadsheet, repeat. This takes days for what should be a 30-second experiment.

### The Solution

A self-service web dashboard where economy designers can:

1. **Upload** player data (CSV) and game config (CSV)
2. **Edit** any parameter with an interactive form — probabilities as sliders, point values, thresholds
3. **Run** a simulation that processes 1M+ players in under 10 seconds
4. **Analyze** results with KPI cards, distribution charts, and churn vs non-churn comparisons
5. **Get AI insights** — 3-5 actionable findings ranked by severity (INFO / WARNING / CRITICAL)
6. **Run experiments** — AI suggests parameter sweeps, one click to execute them
7. **Auto-tune** — AI optimizer iteratively adjusts config to hit a target KPI
8. **Chat** — ask questions about your results in natural language
9. **Compare** — save runs to history, load past results, compare two runs side-by-side
10. **Export** — download results as CSV or PDF report

### Key Features

| Feature | What It Does |
|---------|-------------|
| **Simulation Engine** | Vectorized NumPy — 1M players in ~10 seconds, fully deterministic with seed |
| **AI Insights** | Analyzes KPIs, flags issues, suggests specific parameter sweeps to investigate |
| **Insight-to-Sweep Pipeline** | Click an AI suggestion → Parameter Sweep auto-fills → run the experiment. Two clicks from "problem" to "data" |
| **AI Config Optimizer** | Set a target KPI → AI iteratively tunes config → shows before/after comparison with proof |
| **AI Chat** | Conversational Q&A about results — "Why is median so much lower than mean?" |
| **Multi-Model Selection** | 5 AI models in the dashboard: Claude Opus 4.6, Claude Sonnet 4.6, DeepSeek R1, Llama 4, Nova Pro |
| **Parameter Sweep** | Sweep any parameter across a range, see KPI impact as a line chart |
| **Churn Analysis** | Side-by-side comparison of churning vs non-churning player segments |
| **Run Comparison** | Select two saved runs → side-by-side KPI diff, distribution overlay, config delta highlighting |
| **Report Creator** | One-click PDF report with KPIs, charts, config, and AI insights — or export raw results as CSV |
| **Simulation History** | Every run saved, browsable, loadable, comparable |
| **Config Editor** | Dynamic form with tooltips, percentage sliders, change tracking |

### Coin Flip Mechanic (First Feature)

Players land on a tile → trigger a coin-flip chain → each flip has independent probability → points are cumulative by depth → multiplied by player's `avg_multiplier`. Churn-risk players get 1.3x probability boost (capped at 100%).

```
Flip 1: 60% → 1 pt  |  Flip 2: 50% → +2 pts  |  Flip 3: 40% → +4 pts  |  ...
Reach depth 3 = 1+2+4 = 7 base points × avg_multiplier
```

---

## Technical Architecture

### Clean Architecture (4 Layers)

```
UI (Streamlit)  →  Application (Use Cases)  →  Domain (Pure Logic)
                                              ↑
                   Infrastructure (I/O)  ─────┘
```

Dependencies point inward only. Domain has zero I/O, zero framework dependencies.

| Layer | Contents |
|-------|----------|
| **Domain** | `CoinFlipConfig`, `CoinFlipResult`, `CoinFlipSimulator`, protocols (`Simulator`, `LLMClient`, `SimulatorConfig`), custom exceptions |
| **Application** | `RunSimulationUseCase`, `InsightsAnalyst`, `ChatAssistant`, `ConfigOptimizer`, `ParameterSweep`, `ReportGenerator` |
| **Infrastructure** | `BedrockAdapter` (dual-API routing), `AnthropicAdapter`, `LocalDataReader` (Polars), `LocalSimulationStore` (JSON+Parquet), churn normalizer |
| **UI** | Streamlit app with feature routing, section modules, reusable components, session state management |

### Vectorization Strategy

Zero Python for-loops over data. Everything is matrix operations:

```
Polars int division → np.repeat (flatten) → rng.random((N, max_successes))
→ np.where (churn boost) → boolean comparison → np.cumprod (first failure)
→ lookup table (depth→points) → Polars group_by().agg() (player totals)
```

**Result**: ~1M interactions/second. 100K players in ~2s. Linear scaling.

### AWS Deployment (5 CDK Stacks)

```
NetworkStack (VPC, ECR) → DataStack (S3, DynamoDB) → ComputeStack (ECS Fargate, ALB)
                                                    → AuthStack (Cognito, optional)
                                                    → PipelineStack (GitHub → ECR → Fargate)
```

- ECS Fargate: 512 CPU, 1GB RAM, auto-scaling 1-4 tasks
- Docker multi-stage build (~350MB), non-root user, health check
- Bedrock: no API keys needed (IAM role), 5 models available

### Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3.12+ | Team expertise, data science ecosystem |
| Data Processing | **Polars** (not Pandas) | 10-50x faster at scale, Rust backend |
| Simulation | NumPy | Vectorized RNG, matrix operations |
| Dashboard | Streamlit | Python-only, self-service for designers |
| AI Provider | AWS Bedrock | Multi-model, no API keys, IAM-integrated |
| Infrastructure | AWS CDK (Python) | IaC, 5 stacks |
| Container | Docker (multi-stage) | ~350MB image, non-root |
| Compute | ECS Fargate | Serverless, auto-scaling |
| Storage | S3 + DynamoDB | Data lake + run history |
| Testing | pytest + Playwright | 672 tests + 14 E2E browser tests |

### Testing

672 tests across 38 files. TDD workflow (red → green → refactor).

| Category | Count | Strategy |
|----------|-------|----------|
| Unit (domain) | ~150 | Pure logic, seeded RNG, no I/O |
| Application | ~150 | Mocked I/O, protocol verification |
| Infrastructure | ~120 | Real file I/O with tmp_path |
| UI | ~100 | Session state mocking |
| Integration | ~50 | Full CSV → simulate → CSV roundtrip |
| E2E (Playwright) | 14 | Real browser against live URL |
| Benchmark | 5 | 1M player performance |

---

## Key Decisions

| Decision | Choice | Why | Tradeoff |
|----------|--------|-----|----------|
| Data processing | **Polars** over Pandas | 10-50x faster, Rust backend, strict types | Smaller ecosystem, convert at Streamlit boundary |
| Simulation | **Vectorized NumPy** over Python loops | 1000x speedup (minutes → seconds) | Harder to read than a simple for-loop |
| Architecture | **Clean Architecture** (4 layers) | Extensible: AI layer added with zero simulation changes | More files, more indirection |
| Interfaces | **Protocol** over ABC | Duck typing, no forced inheritance, `@runtime_checkable` | Less discoverable than ABC |
| LLM Provider | **Bedrock** default (Anthropic for dev) | No API keys in prod (IAM), multi-model, same AWS billing | Sometimes lags behind latest Anthropic releases |
| API routing | **Dual-API** in BedrockAdapter | `invoke_model` for Anthropic, `converse` for others — adding a model = 1 line | Two code paths to maintain |
| Exceptions | **Multiple inheritance** (`SimulationError` + `ValueError`) | Backward compat: existing `except ValueError` blocks keep working | Multiple inheritance is unusual |
| History storage | **JSON + Parquet** (not SQLite) | Human-readable metadata, fast columnar DataFrames, no DB dependency | No query capability |
| AI layer | **Feature-agnostic** via `FeatureAnalysisContext` | New feature = implement one method, get all 4 AI features free | Extra abstraction layer |
| Frontend | **Streamlit** over React/Vue | Python-only, economy team self-service, no build step | Limited UI customization, session state gotchas |
| Container | **Non-root Docker user** | Security best practice for Fargate | Broke twice — learned: explicit writable dirs for every service |
| Development | **TDD** (red → green → refactor) | 672 tests give refactoring confidence | Slower initial velocity |
| Documentation | **Design Log methodology** | 22 logs capturing every decision with rationale | Overhead per task |
| Parallel dev | **Git worktrees** + 8 Claude Code agents | 8 tasks in the time of ~2 sequential | Merge conflicts at the end, careful `git add` needed |

---

## Roadmap: What's Next

### Phase 1: Additional Simulators

- [ ] **Loot Table Simulator** — weighted pool with rarity tiers and pity system
- [ ] **Reward Distribution Simulator** — cumulative, event-based, seasonal mechanics
- [ ] **Event Economy Simulator** — time-limited events with separate currency pools
- [ ] **Board Progression Simulator** — dice rolls, tile effects, building upgrades

### Phase 2: Production Data Integration

- [ ] **Data warehouse connector** — pull player data from Snowflake/BigQuery/Redshift instead of CSV uploads
- [ ] **Real-time player segments** — connect to live player segmentation (churn ML model, whale detection)
- [ ] **Config management** — version-controlled configs with diff tracking, approval workflow
- [ ] **Scheduled simulations** — run nightly with latest player data, alert on KPI drift

### Phase 3: Multi-Feature Economy Model

- [ ] **Cross-feature simulation** — coin flip points feed into building upgrades feed into tournaments
- [ ] **Economy-wide inflation tracking** — aggregate currency inflow/outflow across all features
- [ ] **Systemic risk alerts** — detect when one feature change cascades to break another
- [ ] **Player journey simulation** — model a player's full session, not just one feature

### Phase 4: A/B Test Integration

- [ ] **Experiment framework** — define config variants, split player populations
- [ ] **Live results comparison** — compare simulation predictions vs actual A/B test outcomes
- [ ] **Confidence scoring** — statistical significance on simulated KPI differences
- [ ] **Auto-recommendation** — AI suggests which config to ship based on simulation + live data

### Phase 5: Team & Collaboration

- [ ] **Authentication** — Cognito integration (CDK stack ready, needs HTTPS + domain)
- [ ] **Multi-user** — shared simulation history, team annotations on runs
- [ ] **Approval workflow** — designer proposes config change, lead reviews simulation results, approves
- [ ] **Audit trail** — who changed what, when, with what simulation backing

---

## Quick Start

```bash
# Install dependencies
poetry install

# Run tests (672 tests)
poetry run pytest

# Run Streamlit dashboard
poetry run streamlit run src/ui/app.py

# CLI simulation
poetry run python -m src.cli coin-flip-assignment/input_table.csv \
                              coin-flip-assignment/config_table.csv \
                              --output results_summary.csv \
                              --output-players results_players.csv \
                              --threshold 100 --seed 42

# Docker
docker compose up
```

### AI Setup

```bash
# Production — AWS Bedrock (no API key needed, uses IAM)
export LLM_PROVIDER=bedrock

# Local dev — Anthropic API
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=your-key
```

### Deploy to AWS

```bash
cdk deploy --all --app "poetry run python infra/app.py"
```

### Validate Docker Build

```bash
bash scripts/validate_docker.sh
```

---

## Project Structure

```
src/
├── domain/                # Pure business logic (zero I/O)
│   ├── models/            # CoinFlipConfig, CoinFlipResult, Insight, Optimization
│   ├── simulators/        # CoinFlipSimulator + Registry (vectorized NumPy)
│   ├── protocols/         # Simulator, LLMClient, SimulatorConfig, FeatureAnalysisContext
│   └── errors.py          # SimulationError, InvalidConfigError, InvalidPlayerDataError
├── application/           # Use cases (orchestration)
│   ├── run_simulation.py  # Read → Validate → Simulate → Write → Store
│   ├── analyze_results.py # AI insights (3-5 findings per run)
│   ├── chat_assistant.py  # Conversational Q&A with history
│   ├── optimize_config.py # Iterative AI config tuning
│   └── parameter_sweep.py # Sweep one param across a range
├── infrastructure/        # I/O boundary
│   ├── llm/               # Bedrock (dual-API) + Anthropic adapters, model registry
│   ├── readers/            # CSV → Polars, churn normalization
│   ├── writers/            # Polars → CSV
│   └── store/             # JSON metadata + Parquet DataFrames
├── ui/                    # Streamlit dashboard
│   ├── app.py             # Main entry, feature routing, session state
│   ├── sections/          # Results, AI Analysis, Parameter Sweep, History
│   └── components/        # Upload, Config Editor, KPI Cards, Insight Cards, Chat
└── cli.py                 # CLI entrypoint

tests/                     # 672 tests (unit, integration, E2E, benchmark)
infra/                     # AWS CDK (5 stacks: Network, Data, Auth, Compute, Pipeline)
design-logs/               # 22 architecture decision records
docs/                      # Deep dive documentation (EN + HE)
```

---

## How `about_to_churn` Affects Probabilities

Players flagged as `about_to_churn = true` (from a churn-prediction ML model) receive a **1.3x multiplier** on every flip probability in the chain, giving them better odds to keep them engaged:

```
Normal player:      p_success_1 = 0.60, p_success_2 = 0.50, p_success_3 = 0.40
Churn-risk player:  p_success_1 = 0.78, p_success_2 = 0.65, p_success_3 = 0.52
```

The boost is **capped at 1.0** — a 90% probability boosted by 1.3x becomes 100%, not 117%. This prevents impossible probabilities while still giving at-risk players meaningfully better outcomes.

The multiplier is configurable via CLI (`--churn-boost`, default 1.3) and the dashboard config editor.

---

## Assumptions (Coin Flip)

1. **Integer interactions**: `interactions = rolls_sink // avg_multiplier` (floor division)
2. **Cumulative points**: Depth 3 earns `points[0] + points[1] + points[2]`, multiplied by `avg_multiplier`
3. **Churn boost capped at 1.0**: `boosted = min(probability * 1.3, 1.0)`
4. **Default churn**: Missing `about_to_churn` column → all players default to `false`

---

## Documentation

| Document | Content |
|----------|---------|
| [Deep Dive (EN)](docs/00-project-deep-dive.md) | Complete project narrative — architecture, product, AI, decisions |
| [Deep Dive (HE)](docs/00-project-deep-dive-he.md) | Same in Hebrew |
| [Architecture](docs/01-architecture.md) | Technical architecture deep dive (EN + HE) |
| [Product](docs/02-product.md) | All features and user flows (EN + HE) |
| [AI Integration](docs/03-ai-integration.md) | AI features and technical details (EN + HE) |
| [Decisions](docs/04-decisions.md) | 14 key decisions with rationale (EN + HE) |
| [Math & Calculations](docs/05-math-and-calculations.md) | Every formula, algorithm, and calculation with examples |
| [Design Logs](design-logs/) | 22 architecture decision records |
