# Monopoly Go Economy — Project Details

> **Living document.** Updated every time changes are made to the project.
> Last updated: 2026-03-19 (Feature #14: Docker containerization)

---

## Purpose
Economy simulation platform for the Monopoly Go game. Enables the economy team to simulate, analyze, and tune game features at scale (millions of players) through a self-service dashboard with AI-powered insights, chat, and config optimization.

## Tech Stack

| Layer | Technology | Version | Why |
|-------|-----------|---------|-----|
| Language | Python | 3.12+ | Type hints, performance, ecosystem |
| Data Processing | Polars | latest | 10-50x faster than Pandas at scale (Rust-based) |
| Random Generation | NumPy | latest | Vectorized RNG — no Python loops over millions of rows |
| Dashboard | Streamlit | latest | Economy team self-service: upload, configure, simulate, visualize |
| AI (local dev) | Anthropic API (Claude) | latest | Direct API for development, easy iteration |
| AI (production) | AWS Bedrock (Claude) | latest | IAM auth, no API keys, VPC endpoint |
| Infrastructure | AWS CDK (Python) | latest | IaC for Fargate, S3, ALB, DynamoDB, Bedrock |
| Testing | pytest | latest | TDD with seeded RNG for reproducibility |
| Containerization | Docker | latest | Reproducible deployment |

## Architecture

```
src/
├── domain/                    # Pure business logic — NO I/O, NO framework deps
│   ├── protocols.py           # SimulatorConfig, SimulationResult, Simulator protocols
│   ├── models/
│   │   ├── coin_flip.py       # CoinFlipConfig, CoinFlipResult
│   │   └── optimization.py    # OptimizationTarget
│   └── simulators/
│       ├── registry.py        # SimulatorRegistry (discover + register)
│       └── coin_flip.py       # CoinFlipSimulator (vectorized NumPy)
├── application/               # Orchestration layer (use cases)
│   ├── run_simulation.py      # RunSimulationUseCase (generic)
│   ├── analyze_results.py     # AnalyzeResultsUseCase + InsightsAnalyst
│   ├── chat_assistant.py      # ChatAssistant (NL queries)
│   └── optimize_config.py     # ConfigOptimizer (target-based)
├── infrastructure/            # I/O boundary
│   ├── readers/               # LocalDataReader, S3DataReader (Polars)
│   ├── writers/               # LocalDataWriter, S3DataWriter
│   ├── llm/                   # LLMClient protocol + Anthropic/Bedrock adapters
│   └── store/                 # LocalSimulationStore, DynamoDBSimulationStore
└── ui/                        # Streamlit dashboard
    ├── app.py                 # Entry point, st.navigation
    ├── components/            # Reusable: upload, config editor, KPIs, charts, AI chat
    └── pages/                 # Upload, Run, Results, AI Insights, History

tests/                         # Mirrors src/ structure
infra/                         # AWS CDK stacks (network, data, compute, AI, pipeline)
docs/plans/                    # System design, architecture documents
design-logs/                   # Decision documentation
coin-flip-assignment/          # Original assignment materials
```

## Reusability Strategy

**Every component is protocol-based.** Adding a new game feature requires only:
1. Create `NewFeatureConfig` (implements `SimulatorConfig`)
2. Create `NewFeatureSimulator` (implements `Simulator`)
3. Create `NewFeatureResult` (implements `SimulationResult`)
4. Register in `SimulatorRegistry`
5. Add one Streamlit page for feature-specific UI

Everything else works automatically: I/O, orchestration, dashboard components, AI insights, chat, optimizer, export, history, comparison.

**10 of 23 features are reusable** — built once, used by every future simulator.

## Feature Simulators

### 1. Coin Flip (CURRENT)
**Status:** Not started — Feature #6 in AutoForge
**Assignment:** `/coin-flip-assignment/Tech_Test.pdf`

**Mechanic:**
- Player lands on tile → triggers coin flip sequence
- Up to `max_successes` (5) sequential flips
- Each flip has independent probability (configurable per depth)
- Heads → accumulate points, continue. Tails → sequence ends.
- Points per flip are cumulative (1, 2, 4, 8, 16)
- `interactions = rolls_sink / avg_multiplier`
- Final points per interaction multiplied by `avg_multiplier`
- Churn boost: `about_to_churn=true` → probabilities × 1.3 (capped at 1.0)

**Config (config_table.csv):**
| Parameter | Value |
|-----------|-------|
| max_successes | 5 |
| p_success_1 | 60% |
| p_success_2-5 | 50% each |
| points_success_1-5 | 1, 2, 4, 8, 16 |

**Input (input_table.csv):**
- 10,000 players (sample), designed for 1M+
- Columns: `user_id`, `rolls_sink`, `avg_multiplier`, `about_to_churn`

**Required Output (CSV):**
- `total_roll_interactions` — total interactions simulated
- `success_0_count` ... `success_5_count` — distribution of outcomes
- `total_points` — total points awarded across all players
- `players_above_threshold` — players exceeding a configurable reward threshold

**Performance Target:** <10 seconds for 1M players

### 2. Future Features (Planned)
- Loot tables (FTUE, Normal, Seasonal, Events, Flash/Boosted)
- Reward distribution analysis
- Event economy tuning
- Cross-feature economy modeling

## AI Features (Phase 5)

| Feature | Purpose | How It Works |
|---------|---------|-------------|
| **Insights Analyst** | Auto-analyze simulation results | LLM receives config + result summary, generates findings, anomalies, recommendations |
| **Chat Assistant** | NL queries about data | Economy team asks questions, LLM answers grounded in actual simulation data |
| **Config Optimizer** | Suggest optimal parameters | Iterative loop: LLM suggests config → simulate → compare to target → repeat |

**AI Infrastructure:** `LLMClient` protocol with swappable adapters:
- Local dev: `AnthropicAdapter` (direct API, `ANTHROPIC_API_KEY`)
- Production: `BedrockAdapter` (IAM auth, no keys, VPC endpoint)
- Switch via `LLM_PROVIDER` environment variable

## AutoForge Feature Tracker

### Phase 1: Foundation (3 features)
| ID | Feature | Status | Depends On |
|----|---------|--------|------------|
| 1 | Python project setup | Pending | — |
| 2 | Testing infrastructure | Blocked | 1 |
| 3 | System design document | Blocked | 1 |

### Phase 2: Simulator Core (5 features)
| ID | Feature | Reusable? | Status | Depends On |
|----|---------|-----------|--------|------------|
| 4 | Simulator protocols & base models | YES | Blocked | 2, 3 |
| 5 | Generic data I/O layer | YES | Blocked | 4 |
| 6 | Coin flip models & simulation engine | No | Blocked | 4 |
| 7 | Application orchestrator | YES | Blocked | 5, 6 |
| 8 | CLI entrypoint | No | Blocked | 7 |

### Phase 3: Streamlit Dashboard (5 features)
| ID | Feature | Reusable? | Status | Depends On |
|----|---------|-----------|--------|------------|
| 9 | App scaffold & base components | YES | Blocked | 1 |
| 10 | Upload & config editor page | YES | Blocked | 5, 9 |
| 11 | Simulation runner page | No | Blocked | 7, 10 |
| 12 | Results visualization & KPI dashboard | YES | Blocked | 11 |
| 13 | Export, download & comparison | YES | Blocked | 12 |

### Phase 4: AWS Infrastructure (5 features)
| ID | Feature | Status | Depends On |
|----|---------|--------|------------|
| 14 | Docker containerization | Complete | 8, 13 |
| 15 | CDK base stack (VPC, ECR) | Blocked | 14 |
| 16 | Data stack (S3, DynamoDB) | Blocked | 15 |
| 17 | Compute stack (Fargate + ALB) | Blocked | 15, 16 |
| 18 | CI/CD pipeline + secrets | Blocked | 17 |

### Phase 5: AI Features (5 features)
| ID | Feature | Reusable? | Status | Depends On |
|----|---------|-----------|--------|------------|
| 19 | AI infra (LLM client + adapters) | YES | Blocked | 18 |
| 20 | Insights analyst engine | YES | Blocked | 7, 19 |
| 21 | AI insights dashboard page | No | Blocked | 12, 20 |
| 22 | Chat assistant | YES | Blocked | 20 |
| 23 | Config optimizer | YES | Blocked | 20 |

## AWS Infrastructure

| Resource | Purpose | CDK Stack |
|----------|---------|-----------|
| VPC (2 AZs) | Network isolation | NetworkStack |
| ECR | Container registry | NetworkStack |
| S3 (data) | Player CSVs, results | DataStack |
| DynamoDB | Simulation run history | DataStack |
| ECS Fargate | Streamlit runtime | ComputeStack |
| ALB (HTTPS) | Load balancer | ComputeStack |
| Bedrock access | LLM for AI features | AIStack (IAM) |
| Secrets Manager | API keys | PipelineStack |
| CodePipeline | CI/CD | PipelineStack |

## Tools & Integrations

| Tool | Type | Purpose |
|------|------|---------|
| AutoForge | MCP Server | Feature/task tracking (23 features, 5 phases) |
| Streamlit Skills | Skill (17 sub-skills) | Dashboard development |
| AWS CDK Skill | Skill | CDK best practices |
| Deploy on AWS Skill | Skill | Automated AWS deployment |
| superpowers | Plugin | Core Claude enhancements |
| document-skills | Plugin | Document generation |
| everything-claude-code | Plugin | Comprehensive toolkit |
| aws-cdk | Plugin | CDK expertise + security checks |
| aws-cost-ops | Plugin | Pre-deployment cost estimation |
| deploy-on-aws | Plugin | Automated AWS deployment |
| Design Logs | Methodology | Decision documentation before every task |

## Design Decisions Log

| # | Date | Title | Status |
|---|------|-------|--------|
| 001 | 2026-03-19 | Design Log Setup | Complete |
| 002 | 2026-03-19 | Architecture & Tooling | Complete |
| 003 | 2026-03-19 | System Design & Project Planning | Complete |
| 014 | 2026-03-19 | Docker Containerization | Complete |

## Documents

| Document | Path | Description |
|----------|------|-------------|
| System Design | `docs/plans/2026-03-19-system-design.md` | Full HLD + LLD: protocols, data flow, AWS, AI |
| Tech Test PDF | `coin-flip-assignment/Tech_Test.pdf` | Original assignment specification |

## Dependencies
```
# Core
polars
numpy
pydantic

# Dashboard
streamlit

# AI
anthropic
boto3

# Infrastructure
aws-cdk-lib
constructs

# Testing
pytest
pytest-cov
pytest-asyncio

# Dev
mypy
ruff
```

## Key Principles
1. **Polars, not Pandas** — mandatory for all DataFrame work
2. **Vectorize everything** — NumPy for RNG, Polars for aggregation, no Python loops at scale
3. **Design log before code** — document decisions before implementation
4. **TDD** — failing test first, then implement
5. **Seed all randomness** in tests for reproducibility
6. **Reusable simulator pattern** — protocol-based, every new feature plugs in
7. **LLM client abstraction** — Bedrock in prod, Anthropic API in dev, swap via env var
8. **Clean Architecture** — domain has zero I/O dependencies
