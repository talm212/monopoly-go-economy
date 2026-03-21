# Architecture Guide / מדריך ארכיטקטורה

---

## English

### Overview

The Monopoly Go Economy Simulator is built using **Clean Architecture** principles, separating the system into four layers with strict dependency rules: the inner layers (Domain) have zero knowledge of the outer layers (UI, Infrastructure).

```
┌──────────────────────────────────────────────────────┐
│                    Streamlit UI                       │
│           (pages, components, session state)          │
├──────────────────────────────────────────────────────┤
│                 Application Layer                     │
│  (use cases: RunSimulation, Insights, Optimizer...)   │
├──────────────────────────────────────────────────────┤
│               Infrastructure Layer                    │
│     (CSV readers, LLM adapters, local store)          │
├──────────────────────────────────────────────────────┤
│                   Domain Layer                        │
│ (models, simulators, protocols — pure business logic) │
└──────────────────────────────────────────────────────┘
```

Dependencies point **inward only**: UI → Application → Domain; Infrastructure → Domain. The Application layer never imports from UI. The Domain layer imports from nothing external.

---

### Layer-by-Layer Breakdown

#### 1. Domain Layer (`src/domain/`)

The heart of the system. Pure Python, zero I/O, no framework dependencies.

**Models (`src/domain/models/`)**

| Model | Type | Purpose |
|-------|------|---------|
| `CoinFlipConfig` | Frozen dataclass | Immutable simulation parameters: probabilities, point values, churn boost, threshold |
| `CoinFlipResult` | Dataclass | Per-player results DataFrame + aggregate KPIs, distribution, segments |
| `Insight` | Frozen dataclass | AI-generated finding with severity, recommendation, sweep suggestion |
| `SweepSuggestion` | Frozen dataclass | Parameter sweep recommendation (param, start, end, steps) |
| `OptimizationTarget` | Frozen dataclass | What to optimize: metric, target value, direction |
| `OptimizationStep` | Dataclass | One iteration's record: config tried, metric observed, distance to target |

**Protocols (`src/domain/protocols/`)**

All interfaces are defined as `@runtime_checkable Protocol` classes, enabling duck typing with runtime verification:

| Protocol | Methods | Purpose |
|----------|---------|---------|
| `SimulatorConfig` | `validate()`, `to_dict()`, `from_dict()` | Any feature's config contract |
| `SimulationResult` | `to_summary_dict()`, `to_dataframe()`, `get_distribution()`, `get_kpi_metrics()` | Any feature's result contract |
| `Simulator` | `simulate(players, config, seed)`, `validate_input(players)` | Any simulator's contract |
| `LLMClient` | `complete(prompt, system)` | LLM provider abstraction |
| `FeatureAnalysisContext` | (dataclass) | Packages all AI-relevant data from any feature |

**Simulators (`src/domain/simulators/`)**

| Simulator | Strategy | Performance |
|-----------|----------|-------------|
| `CoinFlipSimulator` | Fully vectorized NumPy + Polars | 1M players < 10s |
| `SimulatorRegistry` | Self-registration dict | O(1) lookup by feature name |

**Errors (`src/domain/errors.py`)**

Custom exception hierarchy: `SimulationError` → `InvalidConfigError` / `InvalidPlayerDataError`. All inherit from `ValueError` for backward compatibility.

#### 2. Application Layer (`src/application/`)

Orchestrates domain objects and infrastructure. No I/O of its own — receives everything via dependency injection.

| Use Case | Responsibility |
|----------|---------------|
| `RunSimulationUseCase` | Read → Validate → Simulate → Write → Store. Two paths: file-based (`execute`) and in-memory (`execute_from_dataframe`) |
| `InsightsAnalyst` | Send simulation data to LLM, parse JSON response into `list[Insight]` |
| `ChatAssistant` | Conversational Q&A with history tracking, context-aware answers |
| `ConfigOptimizer` | Iterative loop: simulate → evaluate → LLM suggests → apply guardrails → repeat |
| `ParameterSweep` | Run N simulations sweeping one parameter, return `SweepResult` DataFrame |
| `ReportGenerator` | Generate PDF report from simulation results |
| `config_conversion` | Convert between display dicts and raw config dicts |

#### 3. Infrastructure Layer (`src/infrastructure/`)

All external I/O lives here. Each adapter implements a domain protocol.

**LLM Adapters (`src/infrastructure/llm/`)**

```
get_llm_client() factory
  ├── LLM_PROVIDER=bedrock  → BedrockAdapter (default, no API key needed)
  └── LLM_PROVIDER=anthropic → AnthropicAdapter (needs ANTHROPIC_API_KEY)
```

- **BedrockAdapter**: Dual-API routing — `invoke_model` for Anthropic models, `converse` for non-Anthropic models (DeepSeek, Llama, Nova)
- **AnthropicAdapter**: Direct `AsyncAnthropic` SDK call
- **Model Registry** (`registry.py`): 5 models with MATH benchmark scores for user selection

**Data I/O (`src/infrastructure/readers/`, `writers/`, `store/`)**

| Component | What It Does |
|-----------|-------------|
| `LocalDataReader` | CSV → Polars DataFrame, validates schema + data quality |
| `LocalDataWriter` | Polars DataFrame → CSV |
| `LocalSimulationStore` | JSON metadata + Parquet DataFrames, auto-rebuilding index |
| `normalize_churn_column` | Vectorized normalization: string/int/bool → boolean (no Python loops) |

#### 4. UI Layer (`src/ui/`)

Streamlit single-page application with feature routing.

**Structure:**
```
app.py                    ← Main entry: layout, session state, routing
feature_router.py         ← Feature registry + URL-based routing
session_utils.py          ← Shared session state helpers
async_helper.py           ← run_async() for calling async LLM code from sync Streamlit
sections/
  ├── results_section.py  ← Charts, churn analysis, data table tabs
  ├── ai_analysis.py      ← Insights, chat, optimizer tabs
  ├── parameter_sweep.py  ← Sweep form + results chart
  └── sidebar_history.py  ← Past runs, load/delete/compare
components/
  ├── upload_widget.py    ← File uploaders + CSV preview
  ├── config_editor.py    ← Dynamic form from config dict
  ├── kpi_cards.py        ← Metric cards in responsive grid
  ├── insight_cards.py    ← Color-coded insight cards + sweep buttons
  ├── ai_chat_panel.py    ← Chat interface with history
  └── optimizer_comparison.py ← Side-by-side before/after view
```

---

### Vectorization Strategy (How We Handle 1M+ Players)

The core performance innovation. Zero Python for-loops over data:

```
Step 1: Polars integer division → interactions per player
Step 2: np.repeat → flatten to interaction-level array
Step 3: rng.random((N, max_successes)) → ALL random numbers at once
Step 4: np.where(churn, boosted_probs, normal_probs) → probability assignment
Step 5: random < probs → boolean matrix; np.cumprod → consecutive successes
Step 6: Lookup table → depth to cumulative points (O(1) vectorized)
Step 7: Polars group_by().agg() → aggregate back to player level
```

| Scale | Time | Rate |
|-------|------|------|
| 10K players | 100ms | 1M interactions/s |
| 100K players | ~2s | 1M interactions/s |
| 1M players | ~10s | 1M interactions/s |

---

### Deployment Architecture (AWS)

5 CDK stacks, deployable independently:

```
┌────────────────┐   ┌──────────────┐   ┌────────────────┐
│ NetworkStack   │   │  DataStack   │   │  AuthStack     │
│ VPC, Subnets   │   │ S3, DynamoDB │   │ Cognito (opt)  │
│ NAT, ECR       │   │              │   │                │
└───────┬────────┘   └──────┬───────┘   └────────────────┘
        │                   │
        └─────────┬─────────┘
                  │
         ┌────────v────────┐       ┌──────────────────┐
         │ ComputeStack    │       │ PipelineStack    │
         │ ECS Fargate     │◄──────│ GitHub → ECR →   │
         │ ALB (port 80)   │       │ Fargate deploy   │
         │ Auto-scale 1-4  │       │                  │
         └─────────────────┘       └──────────────────┘
```

**Container**: Multi-stage Docker build (Python 3.12-slim), non-root user, health check on `/_stcore/health`.

---

### Testing Architecture

672 tests across 5 categories:

| Category | Tests | Strategy |
|----------|-------|----------|
| Unit (domain) | ~150 | Pure logic, seeded RNG, no I/O |
| Application | ~150 | Mocked I/O, protocol verification |
| Infrastructure | ~120 | tmp_path fixtures, real file I/O |
| UI | ~100 | Session state mocking, component rendering |
| Integration | ~50 | Full CSV → simulate → CSV roundtrip |
| E2E (Playwright) | 14 | Real browser, headless Chromium |
| Benchmark | 5 | 1M player performance (@pytest.mark.slow) |

**Key Patterns:**
- All RNG seeded with `seed=42` for determinism
- `pytest.fixture` for shared test data
- `pytest.mark.parametrize` for edge cases
- Security tests: path traversal prevention on run_id validation

---

### Key Architecture Patterns

| Pattern | Where | Why |
|---------|-------|-----|
| Dependency Injection | All use cases receive I/O via constructor | Testability, swappable adapters |
| Protocol (interface) | Domain protocols for Simulator, LLMClient, Config | Duck typing with runtime checking |
| Factory Method | `get_llm_client()`, `SimulatorRegistry` | Env-based provider selection |
| Strategy | `BedrockAdapter` vs `AnthropicAdapter` | Same interface, different backends |
| Registry | `SimulatorRegistry`, `FEATURE_REGISTRY` | Self-registering features + simulators |
| Observer | Streamlit session state + `st.rerun()` | Reactive UI updates |
| Adapter | LLM adapters wrap different APIs behind `LLMClient` | Infrastructure isolation |
| Guard Clause | Config validation, run_id validation | Fail fast, clear error messages |

---

## Hebrew / עברית

### סקירה כללית

סימולטור הכלכלה של מונופולי Go בנוי על עקרונות **Clean Architecture** — הפרדה לארבע שכבות עם כללי תלות קפדניים: השכבות הפנימיות (Domain) לא מכירות את השכבות החיצוניות (UI, Infrastructure).

```
┌──────────────────────────────────────────────────────┐
│                  ממשק משתמש (Streamlit)               │
│           (דפים, קומפוננטות, session state)            │
├──────────────────────────────────────────────────────┤
│                    שכבת אפליקציה                      │
│  (תרחישי שימוש: הרצת סימולציה, תובנות, אופטימייזר)    │
├──────────────────────────────────────────────────────┤
│                  שכבת תשתית                           │
│     (קוראי CSV, מתאמי LLM, אחסון מקומי)               │
├──────────────────────────────────────────────────────┤
│                  שכבת דומיין                           │
│ (מודלים, סימולטורים, פרוטוקולים — לוגיקה עסקית טהורה)  │
└──────────────────────────────────────────────────────┘
```

תלויות מצביעות **פנימה בלבד**: UI → Application → Domain. שכבת ה-Domain לא מייבאת כלום חיצוני.

---

### פירוט שכבה אחר שכבה

#### 1. שכבת הדומיין (`src/domain/`)

הלב של המערכת. Python טהור, אפס I/O, אפס תלויות בפריימוורק.

**מודלים:**
- `CoinFlipConfig` — dataclass קפוא (immutable). מכיל: הסתברויות, ערכי נקודות, מכפיל נטישה, סף תגמול
- `CoinFlipResult` — תוצאות לכל שחקן כ-DataFrame + KPIs מצטברים, התפלגות, סגמנטים
- `Insight` — ממצא AI עם חומרה, המלצה, הצעת sweep
- `OptimizationTarget` / `OptimizationStep` — מודלים לאופטימיזציה איטרטיבית

**פרוטוקולים (ממשקים):**

כל הממשקים מוגדרים כ-`@runtime_checkable Protocol` — duck typing עם אימות בזמן ריצה:

- `Simulator` — חוזה לכל סימולטור: `simulate()`, `validate_input()`
- `LLMClient` — הפשטה של ספק LLM: `complete(prompt, system)`
- `SimulatorConfig` / `SimulationResult` — חוזים לכל פיצ'ר
- `FeatureAnalysisContext` — אורז את כל הנתונים הרלוונטיים ל-AI מכל פיצ'ר

**סימולטורים:**

- `CoinFlipSimulator` — וקטוריזציה מלאה עם NumPy + Polars. מיליון שחקנים תוך פחות מ-10 שניות
- `SimulatorRegistry` — רישום עצמי: כל סימולטור נרשם אוטומטית בייבוא

#### 2. שכבת האפליקציה (`src/application/`)

מתזמרת אובייקטים מהדומיין והתשתית. ללא I/O עצמאי — הכל מוזרק דרך DI.

| תרחיש שימוש | אחריות |
|-------------|--------|
| `RunSimulationUseCase` | קריאה → ולידציה → סימולציה → כתיבה → אחסון |
| `InsightsAnalyst` | שליחת נתוני סימולציה ל-LLM, פירוק JSON לרשימת `Insight` |
| `ChatAssistant` | שיחה עם היסטוריה, תשובות מודעות הקשר |
| `ConfigOptimizer` | לולאה איטרטיבית: סימולציה → הערכה → הצעת LLM → guardrails → חזרה |
| `ParameterSweep` | הרצת N סימולציות על טווח פרמטר אחד |

#### 3. שכבת התשתית (`src/infrastructure/`)

כל ה-I/O החיצוני חי כאן. כל מתאם מממש פרוטוקול מהדומיין.

**מתאמי LLM:**
- `BedrockAdapter` — ניתוב כפול: `invoke_model` למודלים של Anthropic, `converse` לשאר (DeepSeek, Llama, Nova)
- `AnthropicAdapter` — SDK ישיר של `AsyncAnthropic`
- **רג'יסטרי מודלים**: 5 מודלים עם ציוני MATH benchmark לבחירת המשתמש

**I/O נתונים:**
- `LocalDataReader` — CSV → Polars DataFrame, ולידציה של סכמה ואיכות נתונים
- `LocalSimulationStore` — JSON metadata + Parquet DataFrames, אינדקס שמתבנה מחדש אוטומטית

#### 4. שכבת UI (`src/ui/`)

אפליקציית Streamlit חד-עמודית עם ניתוב פיצ'רים.

- `app.py` — נקודת כניסה ראשית: layout, session state, ניתוב
- `feature_router.py` — רג'יסטרי פיצ'רים + ניתוב מבוסס URL
- `sections/` — מקטעי עמוד (תוצאות, AI, sweep, היסטוריה)
- `components/` — קומפוננטות לשימוש חוזר (כרטיסי KPI, עורך config, צ'אט)

---

### אסטרטגיית וקטוריזציה (איך מטפלים במיליון+ שחקנים)

החידוש המרכזי בביצועים. אפס לולאות Python על נתונים:

1. חלוקת מספרים שלמים ב-Polars → אינטראקציות לכל שחקן
2. `np.repeat` → שטיח לרמת אינטראקציה
3. `rng.random((N, max_successes))` → כל המספרים האקראיים בבת אחת
4. `np.where` → הקצאת הסתברויות (רגילות / מוגברות)
5. מטריצת בוליאנים + `np.cumprod` → הצלחות רצופות
6. טבלת lookup → עומק לנקודות מצטברות
7. `Polars group_by().agg()` → צבירה חזרה לרמת שחקן

---

### ארכיטקטורת פריסה (AWS)

5 stacks CDK, ניתנים לפריסה עצמאית:

- **NetworkStack** — VPC, subnets, NAT, ECR
- **DataStack** — S3 bucket, DynamoDB (עם termination protection)
- **AuthStack** — Cognito (אופציונלי, דורש HTTPS)
- **ComputeStack** — ECS Fargate + ALB, auto-scaling 1-4 tasks
- **PipelineStack** — CodePipeline: GitHub → ECR → Fargate

**Container**: Docker build רב-שלבי (Python 3.12-slim), משתמש non-root, health check.

---

### ארכיטקטורת טסטים

672 טסטים ב-5 קטגוריות:

| קטגוריה | טסטים | אסטרטגיה |
|---------|-------|----------|
| יחידה (דומיין) | ~150 | לוגיקה טהורה, RNG עם seed, ללא I/O |
| אפליקציה | ~150 | I/O ממוקאפ, אימות פרוטוקולים |
| תשתית | ~120 | fixtures עם tmp_path, I/O אמיתי |
| UI | ~100 | מוקינג של session state |
| אינטגרציה | ~50 | roundtrip מלא: CSV → סימולציה → CSV |
| E2E (Playwright) | 14 | דפדפן אמיתי, Chromium headless |
| ביצועים | 5 | מיליון שחקנים (@pytest.mark.slow) |

**דפוסים מרכזיים:**
- כל ה-RNG עם `seed=42` לדטרמיניזם
- TDD: כתיבת טסט → כישלון אדום → מימוש → ירוק → רפקטור
- טסטי אבטחה: מניעת path traversal על run_id
