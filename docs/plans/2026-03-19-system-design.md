# System Design — Monopoly Go Economy Platform

> **Status:** Approved
> **Date:** 2026-03-19
> **Author:** Architecture session with Claude

---

## 1. Overview

Economy simulation platform for Monopoly Go. The economy team uploads player data, configures game mechanic parameters, runs simulations at scale (1M+ players), and uses AI to analyze results and optimize configurations.

**First feature:** Coin Flip simulator.
**Architecture goal:** Every component is reusable — adding a new game feature (loot tables, reward distributions) requires only implementing the simulator + its UI page. All infrastructure, I/O, dashboard components, and AI features work automatically.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   STREAMLIT DASHBOARD                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Upload & │ │ Run Sim  │ │ Results  │ │ AI Assistant │  │
│  │ Configure│ │ Page     │ │ & Charts │ │ & Insights   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘  │
│       └─────────────┴────────────┴──────────────┘           │
│              Uses: Reusable Dashboard Components             │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                  APPLICATION LAYER                            │
│  ┌───────────────┐ ┌────────────────┐ ┌──────────────────┐ │
│  │RunSimulation  │ │AnalyzeResults  │ │ OptimizeConfig   │ │
│  │  (generic)    │ │   (generic)    │ │   (generic)      │ │
│  └───────┬───────┘ └───────┬────────┘ └────────┬─────────┘ │
└──────────┼─────────────────┼───────────────────┼────────────┘
           │                 │                   │
┌──────────┴─────────────────┴───────────────────┴────────────┐
│                    DOMAIN LAYER (Pure Logic)                  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           SimulatorProtocol[TConfig, TResult]           │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │ │
│  │  │  CoinFlip    │ │  LootTable   │ │  RewardDist  │   │ │
│  │  │  Simulator   │ │  (future)    │ │  (future)    │   │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘   │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ BaseConfig   │  │ BaseResult   │  │ PlayerData      │   │
│  │ (Protocol)   │  │ (Protocol)   │  │ (Protocol)      │   │
│  └──────────────┘  └──────────────┘  └─────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                 INFRASTRUCTURE LAYER                          │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐ │
│  │DataReader│  │S3 Client │  │ LLM Client │  │ DynamoDB │ │
│  │ (Polars) │  │          │  │ (Protocol) │  │ Client   │ │
│  └──────────┘  └──────────┘  └─────┬──────┘  └──────────┘ │
│                               ┌────┴─────┐  ┌───────────┐  │
│                               │ Bedrock  │  │ Anthropic │  │
│                               │ Adapter  │  │ Adapter   │  │
│                               └──────────┘  └───────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                  AWS INFRASTRUCTURE (CDK)                     │
│  ┌──────┐ ┌────────┐ ┌─────┐ ┌────────┐ ┌───────────────┐ │
│  │  S3  │ │Fargate │ │ ALB │ │DynamoDB│ │Bedrock / SSM  │ │
│  └──────┘ └────────┘ └─────┘ └────────┘ └───────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Low-Level Design — Domain Layer

### 3.1 Core Protocols (Reusable)

Every game feature simulator implements these protocols. This is what makes the platform extensible.

```python
from typing import Protocol, TypeVar, Any, runtime_checkable
import polars as pl

TConfig = TypeVar("TConfig", bound="SimulatorConfig")
TResult = TypeVar("TResult", bound="SimulationResult")


@runtime_checkable
class SimulatorConfig(Protocol):
    """Base config contract. Every feature config implements this."""

    def validate(self) -> None:
        """Raise ValueError if config is invalid."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage/comparison."""
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimulatorConfig":
        """Deserialize from storage."""
        ...


@runtime_checkable
class SimulationResult(Protocol):
    """Base result contract. Every simulation produces this shape."""

    def to_summary_dict(self) -> dict[str, Any]:
        """Per-player aggregated output (for CSV export)."""
        ...

    def to_dataframe(self) -> pl.DataFrame:
        """Full result as Polars DataFrame."""
        ...

    def get_distribution(self) -> dict[str, int]:
        """Outcome distribution (for charts)."""
        ...

    def get_kpi_metrics(self) -> dict[str, float]:
        """Key metrics for dashboard KPI cards."""
        ...


@runtime_checkable
class Simulator(Protocol[TConfig, TResult]):
    """THE core interface. Every game feature implements this."""

    def simulate(
        self,
        players: pl.DataFrame,
        config: TConfig,
        seed: int | None = None,
    ) -> TResult:
        """Run simulation. Must be vectorized for 1M+ rows."""
        ...

    def validate_input(self, players: pl.DataFrame) -> list[str]:
        """Validate player DataFrame. Return list of errors (empty = valid)."""
        ...
```

### 3.2 Coin Flip Models (Feature-Specific)

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CoinFlipConfig:
    """Configuration for coin flip simulation."""

    max_successes: int
    probabilities: list[float]      # p_success_1 .. p_success_N
    point_values: list[float]       # points_success_1 .. points_success_N
    churn_boost_multiplier: float = 1.3
    reward_threshold: float = 100.0

    def validate(self) -> None:
        if len(self.probabilities) != self.max_successes:
            raise ValueError("probabilities length must match max_successes")
        if len(self.point_values) != self.max_successes:
            raise ValueError("point_values length must match max_successes")
        if any(p < 0 or p > 1 for p in self.probabilities):
            raise ValueError("probabilities must be between 0 and 1")
        if self.churn_boost_multiplier < 1.0:
            raise ValueError("churn_boost_multiplier must be >= 1.0")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_csv(cls, path: str) -> "CoinFlipConfig": ...


@dataclass
class CoinFlipResult:
    """Result of coin flip simulation."""

    player_results: pl.DataFrame      # per-player: user_id, interactions, points, success_depth
    total_interactions: int
    success_counts: dict[int, int]    # {0: N, 1: N, 2: N, ...}
    total_points: float
    players_above_threshold: int
    threshold: float

    def to_summary_dict(self) -> dict[str, Any]: ...
    def to_dataframe(self) -> pl.DataFrame: ...
    def get_distribution(self) -> dict[str, int]: ...
    def get_kpi_metrics(self) -> dict[str, float]: ...
```

### 3.3 Simulation Engine (Performance-Critical)

```python
class CoinFlipSimulator:
    """Vectorized coin flip simulation.

    Performance strategy:
    1. Compute interactions per player: rolls_sink / avg_multiplier (Polars)
    2. Expand into interaction-level array (NumPy)
    3. Generate ALL random numbers at once: np.random.random(total_interactions, max_successes)
    4. Vectorized comparison against probability thresholds
    5. Compute success depth and points via cumulative operations
    6. Aggregate back to player level (Polars)

    Target: <10 seconds for 1M players.
    """

    def simulate(self, players: pl.DataFrame, config: CoinFlipConfig, seed: int | None = None) -> CoinFlipResult:
        rng = np.random.default_rng(seed)

        # Step 1: Compute interactions per player (Polars)
        interactions = (players["rolls_sink"] / players["avg_multiplier"]).cast(pl.Int64)

        # Step 2: Build probability arrays (handle churn boost)
        # ... vectorized probability matrix construction

        # Step 3: Generate all flips at once
        total_flips = interactions.sum() * config.max_successes
        random_values = rng.random(total_flips)

        # Step 4: Vectorized success determination
        # ... compare random_values against probability thresholds

        # Step 5: Compute points per interaction
        # ... cumulative point values based on success depth

        # Step 6: Aggregate to player level (Polars)
        # ... group by user_id, sum points, count success depths
```

---

## 4. Low-Level Design — Infrastructure Layer

### 4.1 Data I/O (Reusable)

```python
@runtime_checkable
class DataReader(Protocol):
    """Reads data from any source. Local CSV and S3 implementations."""

    def read_players(self, source: str) -> pl.DataFrame:
        """Read player data. Source can be local path or s3:// URI."""
        ...

    def read_config(self, source: str) -> dict[str, Any]:
        """Read config CSV/JSON."""
        ...


class LocalDataReader:
    """Reads from local filesystem using Polars."""

    def read_players(self, source: str) -> pl.DataFrame:
        return pl.read_csv(source)

    def read_config(self, source: str) -> dict[str, Any]:
        df = pl.read_csv(source)
        return dict(zip(df["Input"].to_list(), df["Value"].to_list()))


class S3DataReader:
    """Reads from S3 using Polars + boto3."""

    def __init__(self, s3_client): ...
    def read_players(self, source: str) -> pl.DataFrame: ...
    def read_config(self, source: str) -> dict[str, Any]: ...


class DataWriter(Protocol):
    """Writes simulation results."""

    def write_results(self, result: SimulationResult, destination: str) -> None: ...


class LocalDataWriter:
    def write_results(self, result: SimulationResult, destination: str) -> None:
        result.to_dataframe().write_csv(destination)


class S3DataWriter:
    def __init__(self, s3_client): ...
    def write_results(self, result: SimulationResult, destination: str) -> None: ...
```

### 4.2 LLM Client (Reusable)

```python
class LLMClient(Protocol):
    """Abstract LLM access. Swap Bedrock/Anthropic via env var."""

    async def complete(self, prompt: str, system: str = "") -> str: ...
    async def stream(self, prompt: str, system: str = "") -> AsyncIterator[str]: ...


class AnthropicAdapter:
    """Direct Anthropic API. Used for local development."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"): ...
    async def complete(self, prompt: str, system: str = "") -> str: ...


class BedrockAdapter:
    """AWS Bedrock. Used in production — IAM auth, no API keys."""

    def __init__(self, region: str = "us-east-1", model_id: str = "anthropic.claude-sonnet-4-20250514-v1:0"): ...
    async def complete(self, prompt: str, system: str = "") -> str: ...


def get_llm_client() -> LLMClient:
    """Factory — reads LLM_PROVIDER env var."""
    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    if provider == "bedrock":
        return BedrockAdapter()
    return AnthropicAdapter(api_key=os.environ["ANTHROPIC_API_KEY"])
```

### 4.3 Simulation Store (Reusable)

```python
class SimulationStore(Protocol):
    """Persists simulation runs for history and comparison."""

    def save_run(self, run: SimulationRun) -> str:
        """Save run, return run_id."""
        ...

    def get_run(self, run_id: str) -> SimulationRun: ...
    def list_runs(self, feature: str, limit: int = 20) -> list[SimulationRunSummary]: ...


@dataclass
class SimulationRun:
    run_id: str
    feature: str              # "coin_flip", "loot_table", etc.
    config: dict[str, Any]
    result_summary: dict[str, Any]
    created_at: datetime
    metadata: dict[str, Any]  # user, notes, tags


class LocalSimulationStore:
    """JSON files on disk. Used for local dev."""
    ...

class DynamoDBSimulationStore:
    """DynamoDB table. Used in production."""
    ...
```

---

## 5. Low-Level Design — Application Layer

### 5.1 Use Cases (Reusable)

```python
class RunSimulationUseCase:
    """Orchestrates: read data → validate → simulate → store → return."""

    def __init__(
        self,
        reader: DataReader,
        simulator: Simulator,
        writer: DataWriter,
        store: SimulationStore | None = None,
    ): ...

    def execute(
        self,
        player_source: str,
        config: SimulatorConfig,
        output_destination: str | None = None,
        seed: int | None = None,
    ) -> SimulationResult: ...


class AnalyzeResultsUseCase:
    """Generates AI insights for any simulation result."""

    def __init__(self, llm_client: LLMClient): ...

    async def execute(
        self,
        result: SimulationResult,
        config: SimulatorConfig,
        feature_name: str,
    ) -> list[Insight]: ...


class OptimizeConfigUseCase:
    """Finds config params that achieve a target outcome."""

    def __init__(self, simulator: Simulator, llm_client: LLMClient): ...

    async def execute(
        self,
        players: pl.DataFrame,
        current_config: SimulatorConfig,
        target: OptimizationTarget,
    ) -> SimulatorConfig: ...
```

---

## 6. Low-Level Design — Streamlit Dashboard

### 6.1 Reusable Components

```python
# src/ui/components/upload_widget.py
def render_upload_widget(
    accepted_types: list[str] = ["csv"],
    label: str = "Upload player data",
) -> pl.DataFrame | None:
    """Reusable file upload → Polars DataFrame."""
    ...

# src/ui/components/config_editor.py
def render_config_editor(config: SimulatorConfig) -> SimulatorConfig:
    """Dynamic form generated from any SimulatorConfig dataclass."""
    ...

# src/ui/components/kpi_cards.py
def render_kpi_cards(metrics: dict[str, float]) -> None:
    """Render a row of KPI metric cards."""
    ...

# src/ui/components/distribution_chart.py
def render_distribution_chart(distribution: dict[str, int], title: str) -> None:
    """Bar/histogram chart for any outcome distribution."""
    ...

# src/ui/components/comparison_view.py
def render_comparison_view(run_a: SimulationRun, run_b: SimulationRun) -> None:
    """Side-by-side comparison of two simulation runs."""
    ...

# src/ui/components/ai_chat_panel.py
async def render_ai_chat_panel(assistant: AIChatAssistant, context: SimulationResult) -> None:
    """Chat interface for asking questions about simulation data."""
    ...
```

### 6.2 Page Structure

```
src/ui/
├── app.py                    # Entry point, st.navigation
├── pages/
│   ├── 1_upload_configure.py # Upload CSVs + edit config (reusable widgets)
│   ├── 2_run_simulation.py   # Run sim + progress bar
│   ├── 3_results.py          # KPIs + charts + distribution
│   ├── 4_ai_insights.py      # AI analysis + chat + optimizer
│   └── 5_history.py          # Past runs, comparison
└── components/               # Reusable widgets (above)
```

---

## 7. AWS Infrastructure Design

### 7.1 CDK Stack Decomposition

```
infra/
├── app.py                    # CDK app entry
├── stacks/
│   ├── network_stack.py      # VPC, subnets, security groups
│   ├── data_stack.py         # S3 buckets, DynamoDB tables
│   ├── compute_stack.py      # ECS Fargate, ALB, ECR
│   ├── ai_stack.py           # Bedrock access, SSM params
│   └── pipeline_stack.py     # CodePipeline CI/CD
```

### 7.2 Resource Map

| Resource | Purpose | CDK Construct |
|----------|---------|---------------|
| VPC | Network isolation | `ec2.Vpc` |
| S3 (data) | Player CSVs, config files, results | `s3.Bucket` |
| S3 (artifacts) | Docker images, build artifacts | `s3.Bucket` |
| DynamoDB | Simulation run history | `dynamodb.Table` |
| ECR | Container registry | `ecr.Repository` |
| ECS Fargate | Streamlit app runtime | `ecs_patterns.ApplicationLoadBalancedFargateService` |
| ALB | HTTPS load balancer | (included in Fargate pattern) |
| Bedrock | LLM access (Claude) | IAM policy |
| SSM Parameter Store | Non-secret config | `ssm.StringParameter` |
| Secrets Manager | API keys (if using Anthropic direct) | `secretsmanager.Secret` |
| CloudWatch | Logs, metrics, alarms | (auto-created by ECS) |

### 7.3 Networking

```
VPC (10.0.0.0/16)
├── Public Subnets (2 AZs)
│   └── ALB (internet-facing, HTTPS)
├── Private Subnets (2 AZs)
│   └── ECS Fargate Tasks (Streamlit)
└── Isolated Subnets (optional)
    └── DynamoDB VPC Endpoint
```

---

## 8. AI Feature Design

### 8.1 Insights Analyst

```python
class InsightsAnalyst:
    """Analyzes any SimulationResult and generates actionable insights."""

    SYSTEM_PROMPT = """You are an economy analyst for Monopoly Go.
    Analyze simulation results and provide:
    1. Key findings (what happened)
    2. Anomalies (what's unexpected)
    3. Recommendations (what to change)
    Be specific with numbers. Reference the config parameters."""

    def __init__(self, llm_client: LLMClient): ...

    async def generate_insights(
        self,
        result: SimulationResult,
        config: SimulatorConfig,
        feature_name: str,
    ) -> list[Insight]:
        prompt = self._build_prompt(result, config, feature_name)
        response = await self.llm_client.complete(prompt, self.SYSTEM_PROMPT)
        return self._parse_insights(response)
```

### 8.2 Chat Assistant

```python
class ChatAssistant:
    """Natural language Q&A about simulation data."""

    SYSTEM_PROMPT = """You are a data analyst assistant for the Monopoly Go economy team.
    Answer questions about simulation results using the provided data context.
    Always cite specific numbers. If you can't answer from the data, say so."""

    async def answer(
        self,
        question: str,
        result: SimulationResult,
        config: SimulatorConfig,
        history: list[Message] | None = None,
    ) -> str: ...
```

### 8.3 Config Optimizer

```python
@dataclass
class OptimizationTarget:
    metric: str           # "players_above_threshold", "total_points", "success_5_pct"
    target_value: float   # desired value
    direction: str        # "maximize", "minimize", "target" (get close to value)

class ConfigOptimizer:
    """Uses LLM + simulation loop to find optimal config."""

    async def optimize(
        self,
        simulator: Simulator,
        players: pl.DataFrame,
        current_config: SimulatorConfig,
        target: OptimizationTarget,
        max_iterations: int = 10,
    ) -> tuple[SimulatorConfig, SimulationResult]:
        """
        Loop:
        1. Ask LLM to suggest config changes based on current results vs target
        2. Run simulation with suggested config
        3. Compare result to target
        4. If close enough or max iterations, return best config
        """
        ...
```

---

## 9. Data Flow

### 9.1 Simulation Flow

```
CSV Upload → Polars Read → Validate → Simulate (NumPy) → Aggregate (Polars) → Result
                                                                                  │
                                                              ┌───────────────────┤
                                                              ▼                   ▼
                                                         Dashboard            CSV Export
                                                         (Charts)            (Download)
                                                              │
                                                              ▼
                                                        AI Analysis
                                                     (Insights + Chat)
```

### 9.2 Reusability Flow (Adding a New Feature)

```
1. Create NewFeatureConfig (implements SimulatorConfig)
2. Create NewFeatureSimulator (implements Simulator)
3. Create NewFeatureResult (implements SimulationResult)
4. Register in simulator_registry
5. Add one Streamlit page for feature-specific UI

Everything else (upload, config editor, charts, KPIs, export,
AI insights, chat, optimizer, S3 I/O, history) works automatically.
```

---

## 10. Directory Structure (Final)

```
monopoly-go-economy/
├── CLAUDE.md                          # Claude Code instructions
├── PROJECT.md                         # Living project details
├── pyproject.toml                     # uv/poetry config
├── Dockerfile                         # Container for deployment
├── docs/
│   └── plans/
│       └── 2026-03-19-system-design.md  # This file
├── design-logs/                       # Decision documentation
├── coin-flip-assignment/              # Original assignment
├── src/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── protocols.py               # SimulatorConfig, SimulationResult, Simulator
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── coin_flip.py           # CoinFlipConfig, CoinFlipResult
│   │   └── simulators/
│   │       ├── __init__.py
│   │       ├── registry.py            # SimulatorRegistry (discover + register)
│   │       └── coin_flip.py           # CoinFlipSimulator
│   ├── application/
│   │   ├── __init__.py
│   │   ├── run_simulation.py          # RunSimulationUseCase
│   │   ├── analyze_results.py         # AnalyzeResultsUseCase
│   │   └── optimize_config.py         # OptimizeConfigUseCase
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── readers/
│   │   │   ├── __init__.py
│   │   │   ├── local_reader.py        # LocalDataReader (Polars)
│   │   │   └── s3_reader.py           # S3DataReader
│   │   ├── writers/
│   │   │   ├── __init__.py
│   │   │   ├── local_writer.py
│   │   │   └── s3_writer.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── client.py              # LLMClient protocol + factory
│   │   │   ├── anthropic_adapter.py
│   │   │   └── bedrock_adapter.py
│   │   └── store/
│   │       ├── __init__.py
│   │       ├── local_store.py         # JSON file store
│   │       └── dynamodb_store.py      # DynamoDB store
│   └── ui/
│       ├── app.py                     # Streamlit entry point
│       ├── components/
│       │   ├── __init__.py
│       │   ├── upload_widget.py
│       │   ├── config_editor.py
│       │   ├── kpi_cards.py
│       │   ├── distribution_chart.py
│       │   ├── comparison_view.py
│       │   └── ai_chat_panel.py
│       └── pages/
│           ├── 1_upload_configure.py
│           ├── 2_run_simulation.py
│           ├── 3_results.py
│           ├── 4_ai_insights.py
│           └── 5_history.py
├── tests/
│   ├── conftest.py                    # Shared fixtures, seeded RNG
│   ├── domain/
│   │   ├── test_protocols.py
│   │   ├── test_coin_flip_config.py
│   │   ├── test_coin_flip_simulator.py
│   │   └── test_registry.py
│   ├── application/
│   │   ├── test_run_simulation.py
│   │   └── test_analyze_results.py
│   ├── infrastructure/
│   │   ├── test_local_reader.py
│   │   ├── test_local_writer.py
│   │   └── test_llm_client.py
│   └── ui/
│       └── test_components.py
├── infra/
│   ├── app.py                         # CDK app entry
│   └── stacks/
│       ├── network_stack.py
│       ├── data_stack.py
│       ├── compute_stack.py
│       ├── ai_stack.py
│       └── pipeline_stack.py
├── .claude/                           # Claude Code config
├── .mcp.json                          # AutoForge MCP
└── .gitignore
```

---

## 11. Performance Strategy

| Operation | Strategy | Target |
|-----------|----------|--------|
| CSV ingestion | `pl.read_csv()` / `pl.scan_csv()` lazy | <2s for 1M rows |
| Random generation | `np.random.default_rng().random(N, K)` — single call | <1s for 1M |
| Flip chain logic | Vectorized cumulative comparison (no Python loops) | <3s for 1M |
| Aggregation | Polars `group_by().agg()` | <1s for 1M |
| Total simulation | End-to-end | **<10s for 1M players** |

---

## 12. Testing Strategy

| Layer | Test Type | Tools | Coverage Target |
|-------|-----------|-------|-----------------|
| Domain | Unit (deterministic, seeded RNG) | pytest, NumPy seeds | 90%+ |
| Application | Integration (use case orchestration) | pytest, fixtures | 80%+ |
| Infrastructure | Integration (I/O boundaries) | pytest, tmp_path, moto | 70%+ |
| UI | Smoke tests | streamlit testing | 60%+ |
| CDK | Snapshot + assertion | pytest, cdk assertions | 80%+ |

---

## 13. Security Considerations

- Encryption at rest: S3 (SSE-S3), DynamoDB (AWS managed)
- Encryption in transit: HTTPS via ALB
- Network: Fargate in private subnets, ALB in public
- IAM: Least privilege roles per service
- Secrets: SSM Parameter Store (config), Secrets Manager (API keys)
- No credentials in code or environment variables in CDK
- Bedrock access via IAM role (no API keys needed in production)
