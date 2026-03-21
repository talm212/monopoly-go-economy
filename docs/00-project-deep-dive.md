# Monopoly Go Economy Simulator — The Complete Story

## What We Built and Why

We built a production-grade economy simulation platform for the Monopoly Go game. The economy team — designers who tune game mechanics like coin flips, loot tables, and reward distributions — needed a way to test configuration changes at scale before pushing them to millions of real players.

Before this platform existed, the process was painful: an economy designer would change a probability value, ask an engineer to run a simulation script, wait for results, look at a spreadsheet, and repeat. This could take days for what should be a 30-second experiment.

Now they open a web dashboard, upload their player data CSV and config CSV, click "Run Simulation," and in seconds they see KPI cards, distribution charts, churn analysis, and AI-generated insights telling them exactly what their config change would do to the game economy.

The platform handles over a million players in under 10 seconds. It runs on AWS. It has 672 automated tests. And it was built in about a week using Claude Code as an AI pair programmer, with every architectural decision documented in design logs.

---

## The Game Mechanic: Coin Flip

The first feature simulated is the Coin Flip. Here's how it works in the game:

A player lands on a special tile and triggers a coin-flip chain. They flip a coin — if it's heads, they earn points and get to flip again. If it's tails, the chain ends. Each flip has its own independent probability of success, and each depth in the chain awards different point values.

For example, with 5 maximum flips:
- Flip 1: 60% chance of heads → earns 1 point
- Flip 2: 50% chance → earns 2 more points (cumulative: 3)
- Flip 3: 40% chance → earns 4 more points (cumulative: 7)
- Flip 4: 30% chance → earns 8 more points (cumulative: 15)
- Flip 5: 20% chance → earns 16 more points (cumulative: 31)

A player who gets lucky and reaches depth 5 earns 31 points times their personal multiplier. A player who gets tails on flip 1 earns nothing. This creates a heavily right-skewed distribution — most players earn a little, a tiny fraction earns a lot.

The economy team's job is to tune these probabilities and point values so the overall economy stays balanced. Too generous = inflation. Too stingy = player frustration and churn.

There's also a churn boost mechanic: players flagged as "about to churn" (from a machine learning model) get a 1.3x multiplier on their flip probabilities, capped at 100%. This gives at-risk players better odds, trying to keep them engaged without being obvious about it.

---

## The Architecture: Staff Engineer Grade

This isn't a script. It's a proper software system built to Staff Engineer / Architect standards.

### Clean Architecture (4 Layers)

The system is split into four layers with strict dependency rules:

**Domain Layer** (innermost — pure business logic, zero I/O):
- `CoinFlipConfig`: An immutable frozen dataclass holding all tunable parameters — probabilities, point values, churn boost multiplier, reward threshold. Validates itself on construction.
- `CoinFlipResult`: Per-player simulation results as a Polars DataFrame, plus aggregate KPIs, distribution histograms, and churn segment breakdowns.
- `CoinFlipSimulator`: The engine itself — fully vectorized with NumPy, no Python for-loops.
- Protocols: `Simulator`, `SimulatorConfig`, `SimulationResult`, `LLMClient` — all defined as `@runtime_checkable Protocol` classes for duck typing with runtime verification.

**Application Layer** (orchestration, no I/O of its own):
- `RunSimulationUseCase`: Read → Validate → Simulate → Write → Store
- `InsightsAnalyst`: Send data to LLM, parse JSON response into structured insights
- `ChatAssistant`: Conversational Q&A with history tracking
- `ConfigOptimizer`: Iterative loop — simulate, evaluate, ask LLM for better config, apply guardrails, repeat
- `ParameterSweep`: Run N simulations varying one parameter across a range

**Infrastructure Layer** (all external I/O):
- LLM adapters: Bedrock (production default, no API keys needed) and Anthropic (development)
- CSV readers/writers using Polars
- Local simulation store: JSON metadata + Parquet DataFrames with auto-rebuilding index
- Churn column normalizer: handles string, integer, boolean, and missing values

**UI Layer** (Streamlit dashboard):
- Single-page application with feature routing
- Upload widgets, config editor, KPI cards, result tabs, AI analysis tabs
- Session state management with guards against stale data and double-clicks

### Why This Matters

The Clean Architecture pays off when you add features. When we added the AI layer (insights, chat, optimizer), we changed zero lines of simulation code. When we added multi-model support (5 different AI models), we changed zero lines of application code. When we added parameter sweep, it plugged into the existing simulator without modification.

Each layer is independently testable. Domain tests are pure math — no mocking, no I/O, just "given these inputs, verify these outputs." Application tests mock the I/O boundaries. Infrastructure tests use real files in temporary directories. E2E tests use a real browser.

---

## The Performance Story: Vectorization

The most technically interesting aspect of the project. When you have a million players, each with potentially dozens of interactions, you're looking at tens of millions of coin flip simulations. In Python.

A naive implementation — `for player in players: for interaction in range(num_interactions): for flip in range(max_successes)` — would take minutes. We needed seconds.

### The Vectorized Approach

Instead of looping, we do everything as matrix operations:

**Step 1**: Compute interactions per player using Polars integer division: `rolls_sink // avg_multiplier`. This gives us an array like `[10, 25, 8, 15, ...]` for each player.

**Step 2**: Flatten to interaction level using `np.repeat`. If player A has 10 interactions and player B has 25, we create an array of 35 elements where the first 10 "belong to" player A and the next 25 "belong to" player B.

**Step 3**: Generate ALL random numbers at once. One single call: `rng.random((total_interactions, max_successes))`. For a million interactions with 5 max flips, this creates a 1,000,000 × 5 matrix of random numbers between 0 and 1. One NumPy operation.

**Step 4**: Assign probabilities. Players flagged as about-to-churn get boosted probabilities (1.3x, capped at 1.0). We use `np.where(is_churn[:, np.newaxis], boosted_probs, normal_probs)` to broadcast the correct probability row for each interaction.

**Step 5**: Determine success depths. Compare the random matrix against the probability matrix element-wise: `success_matrix = random_values < probabilities`. This gives a boolean matrix. Then use `np.cumprod(success_matrix.astype(int8), axis=1)` — cumulative product along the flip axis. A `cumprod` of [True, True, False, True, True] becomes [1, 1, 0, 0, 0] — it naturally finds the first failure and zeros everything after it. Sum across axis 1 gives the depth reached.

**Step 6**: Map depth to points using a lookup table. Pre-compute cumulative points: `points_lookup = [0, 1, 3, 7, 15, 31]`. Then `total_points = points_lookup[depth_array]` — vectorized index lookup.

**Step 7**: Aggregate back to player level using Polars `group_by().agg(sum)`.

The result: 100,000 players process in about 2 seconds. It scales linearly — 1 million players in about 10 seconds. That's roughly 1 million interactions processed per second. No Numba. No Cython. No multiprocessing. Just NumPy broadcasting and Polars aggregation.

---

## The AI Integration: Not an Afterthought

AI isn't bolted on. It's woven into the simulation workflow at four levels.

### Level 1: AI Insights

After running a simulation, the user clicks "Generate Insights." The system sends the KPIs, distribution, and config to an LLM with a carefully crafted system prompt that includes deep domain knowledge — what each parameter means, how the coin flip mechanic works, what each KPI measures.

The LLM returns 3-5 actionable findings as structured JSON, each with a severity level (INFO, WARNING, CRITICAL), specific numbers cited from the results, and a recommendation.

For example, the AI might say: "WARNING: The mean_points_per_player (1379.8) is nearly 7x the median (200.0), indicating a severely right-skewed distribution. A tiny minority of players reaching depths 4-5 are massively inflating the average. Recommendation: Flatten the points curve to reduce tail inflation."

### Level 2: Insight → Sweep Pipeline

This is the coolest UX feature. Each AI insight can include a "sweep suggestion" — a specific experiment to test. The insight card renders a button like "Sweep p_success_4: 0.3 → 0.7 (5 steps)." One click, and the Parameter Sweep section auto-fills with those values. Another click to "Run Sweep," and 5 simulations execute, producing a line chart showing exactly how that parameter affects the KPIs.

Two clicks from "here's a problem" to "here's the data to make a decision." That's what makes this platform transformative for the economy team — it doesn't just show data, it accelerates the decision cycle.

### Level 3: AI Chat

A conversational interface where the economy designer can ask questions about their simulation results. "Why is the median so much lower than the mean?" "What would happen if I set all probabilities to 50%?" "Which parameter has the biggest impact on total_points?"

The chat maintains conversation history (up to 10 turns) and includes the full simulation context in every message — config, KPIs, distribution, churn segments.

### Level 4: AI Config Optimizer

The most ambitious AI feature. Set a target — "make pct_above_threshold = 5%" or "maximize mean_points_per_player" — and the AI iteratively tunes the config to get there.

The loop: simulate with current config → compute distance to target → ask LLM for a better config → apply guardrails (cap probabilities at [0,1], ensure positive points, protect max_successes) → repeat. It tracks the best config seen across all iterations, shows a convergence chart, and presents a before/after comparison with side-by-side KPIs and distribution charts.

### Multi-Model Selection

Users choose from 5 AI models right in the dashboard:
- Claude Opus 4.6 (MATH benchmark: 96.4%) — best quality
- Claude Sonnet 4.6 (94%) — balanced default
- DeepSeek R1 (90%) — cost-effective
- Meta Llama 4 Maverick (85%) — fast
- Amazon Nova Pro (80%) — budget-friendly

All models run through AWS Bedrock, so no API keys to manage. The Bedrock adapter handles dual-API routing transparently — `invoke_model` for Anthropic models (native format), `converse` for non-Anthropic models (unified format).

### Feature-Agnostic Design

The entire AI layer works with plain dictionaries, not coin-flip-specific objects. A `FeatureAnalysisContext` dataclass packages any feature's data for AI consumption. When loot tables are added, they just implement `to_analysis_context()` and get all four AI features for free.

---

## Key Decisions and Their Stories

### Polars Over Pandas

Pandas is the Python data default. But at a million rows, Pandas is painfully slow for aggregation operations. Polars, built on Apache Arrow with a Rust backend, is 10-50x faster. The tradeoff: smaller ecosystem, fewer Stack Overflow answers, some Streamlit components expect Pandas. We convert at the boundary only where Streamlit requires it.

### Protocols Over Abstract Base Classes

Python offers two ways to define interfaces: ABC (requires explicit inheritance) and Protocol (structural subtyping — if it has the right methods, it satisfies the protocol). We chose Protocol because it aligns with Python's duck typing philosophy, doesn't force inheritance hierarchies, and supports runtime checking with `@runtime_checkable`.

### Bedrock Over Direct Anthropic API

Bedrock is the default in production because: (1) no API keys needed — ECS Fargate tasks get IAM role permissions automatically, (2) multi-model access from a single adapter, (3) billing through the same AWS account. The Anthropic adapter exists for local development.

### Domain Exceptions with Multiple Inheritance

When we introduced custom exceptions (`InvalidConfigError`), we made them inherit from both `SimulationError` AND `ValueError`. This meant all existing `except ValueError` blocks and `pytest.raises(ValueError)` assertions kept working. Pragmatic backward compatibility through multiple inheritance.

### JSON + Parquet for History (Not SQLite)

Simulation history uses JSON files for metadata (human-readable, inspectable) and Parquet files for player DataFrames (fast, compressed, schema-preserving). No database dependency. The index auto-rebuilds from disk if corrupted.

### Git Worktrees for Parallel Development

During a major refactoring, 8 independent tasks were parallelized using git worktrees — 8 Claude Code agents working simultaneously on isolated copies of the repository. All 8 completed in the time of ~2 sequential tasks. Merge conflicts resolved once at the end with full context.

### Non-Root Docker Container (Learned the Hard Way)

We created a non-root `appuser` for security. It broke twice: first because the simulation history directory wasn't writable, then because Streamlit's HOME was `/nonexistent` (the default for system users). Fixed by pre-creating directories with correct ownership and setting `ENV HOME="/app/home"`. Lesson: non-root containers need explicit writable directories for every service that writes files.

---

## The Numbers

- **672 tests** across 38 test files
- **22 design logs** documenting every architectural decision
- **5 AWS CDK stacks**: Network, Data, Auth, Compute, Pipeline
- **5 AI models** available in the dashboard
- **4 AI features**: Insights, Chat, Optimizer, Parameter Sweep
- **1M+ players** processed in under 10 seconds
- **~350MB** production Docker image
- **0 Python for-loops** over simulation data

---

## The Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3.12+ | Team expertise, data science ecosystem |
| Data Processing | Polars | 10-50x faster than Pandas at scale |
| Simulation Engine | NumPy | Vectorized random number generation |
| Dashboard | Streamlit | Python-only, economy team self-service |
| AI Provider | AWS Bedrock | Multi-model, no API keys, IAM-integrated |
| Infrastructure | AWS CDK (Python) | Infrastructure as code, 5 stacks |
| Container | Docker (multi-stage) | Lean ~350MB image, non-root user |
| Compute | ECS Fargate | Serverless containers, auto-scaling 1-4 |
| Storage | S3 + DynamoDB | Data lake + run history |
| Testing | pytest + Playwright | 672 unit/integration tests + 14 E2E browser tests |
| Dependencies | Poetry | Reproducible builds, lock file |
| Documentation | Design Logs | 22 architecture decision records |

---

## What's Next

The platform is designed for multiple game features. Coin Flip is the first. Planned additions:
- **Loot Table Simulator** — weighted pool with rarity tiers and pity system
- **Reward Distributions** — cumulative, event-based, seasonal mechanics
- **Event Economies** — time-limited events with separate currency pools
- **Cognito Authentication** — ALB-integrated auth (requires HTTPS + custom domain)
- **Advanced Analytics** — cohort analysis, player segmentation, A/B test simulation

Each new feature plugs into the existing architecture: implement `Simulator` and `SimulatorConfig` protocols, add `to_analysis_context()` for AI, register in the feature router, and the dashboard, AI analysis, history, and deployment all work automatically.

---

## How This Was Built

This entire platform was built collaboratively with Claude Code, Anthropic's AI coding assistant. The development followed a strict TDD workflow: write failing test → confirm failure → implement → verify pass → refactor → commit.

Key development patterns:
- **Design Log Methodology**: Every non-trivial task starts with a design log documenting context, decision, and rationale
- **Parallel Agent Development**: 8 simultaneous agents working in git worktrees for major refactoring
- **E2E Testing Against Production**: Playwright tests running against the live AWS URL, not just localhost
- **Continuous Deployment**: `cdk deploy` after every feature, with Docker validation before pushing

The collaboration style was staff-engineer level: clean architecture, SOLID principles, protocol-based interfaces, dependency injection, vectorized computation, comprehensive testing, and thorough documentation. Every architectural decision has a documented rationale.
