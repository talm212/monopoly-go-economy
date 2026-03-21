# AI Integration & Cool Features / שילוב AI ופיצ'רים מגניבים

---

## English

### How AI Is Woven Into the Platform

This isn't a project that "uses AI" as an add-on. AI is deeply integrated into the simulation workflow — from analysis to optimization to exploration. Every AI feature follows the same architecture: **feature-agnostic application services** backed by **protocol-based LLM abstraction** with **multi-provider support**.

---

### AI Architecture

```
┌─────────────────────────────────────────────────────┐
│                   UI Layer                          │
│  Model Selector → Tabs (Insights/Chat/Optimizer)    │
└───────────────────────┬─────────────────────────────┘
                        │
           ┌────────────┼────────────────┐
           │            │                │
    ┌──────v──────┐ ┌───v────┐  ┌───────v────────┐
    │ Insights    │ │  Chat  │  │  Optimizer     │
    │ Analyst     │ │ Assist │  │ (iterative     │
    │ (3-5 finds) │ │ (Q&A)  │  │  LLM loop)    │
    └──────┬──────┘ └───┬────┘  └───────┬────────┘
           └────────────┼───────────────┘
                        │
              ┌─────────v──────────┐
              │   LLMClient        │
              │   Protocol         │
              │   (async complete) │
              └─────────┬──────────┘
                        │
         ┌──────────────┼──────────────┐
         │                             │
    ┌────v────────┐           ┌────────v──────┐
    │  Bedrock    │           │  Anthropic    │
    │  Adapter    │           │  Adapter      │
    │  (prod)     │           │  (dev)        │
    │             │           │               │
    │ invoke_model│           │ AsyncAnthropic│
    │ + converse  │           │               │
    └─────────────┘           └───────────────┘
```

**Key principle**: Every AI service accepts plain dicts (`result_summary`, `distribution`, `config`, `kpi_metrics`) — not domain-specific objects. This means the same InsightsAnalyst works for coin flip today and loot tables tomorrow, without code changes.

---

### Feature 1: AI Insights Engine

**What it does**: Analyzes simulation results and generates 3-5 actionable findings, ranked by severity.

**How it works**:
1. Simulation data (KPIs, config, distribution) is formatted into a structured prompt
2. System prompt includes deep domain knowledge: how the coin flip mechanic works, what each parameter means, what each KPI measures
3. LLM returns a JSON array of insights
4. Robust parser handles: markdown-wrapped JSON, missing fields, invalid severity values
5. Each insight optionally includes a `SweepSuggestion` — a parameter sweep recommendation

**The system prompt knows your domain**: It explains to the AI that `p_success_3` means the probability at flip depth 3, that points are cumulative, that `avg_multiplier` scales the final reward, and that churn boost affects about-to-churn players. This domain context produces dramatically better insights than generic prompts.

**Smart fallbacks**: If the LLM returns malformed JSON, the parser tries stripping markdown fences, extracting JSON from mixed text, and defaulting missing fields — never crashing on bad LLM output.

---

### Feature 2: Insight → Sweep Pipeline

**The coolest UX feature**: Each AI insight can include a sweep suggestion button. One click and the Parameter Sweep section auto-fills with the AI's recommended experiment.

```
AI says: "p_success_4 at 30% creates a bottleneck — test values from 0.3 to 0.7"
     ↓
Button appears: [Sweep p_success_4: 0.3 → 0.7 (5 steps)]
     ↓
User clicks → Parameter Sweep form fills with start=0.3, end=0.7, steps=5
     ↓
User clicks "Run Sweep" → 5 simulations run → line chart shows KPI impact
```

This closes the loop from **"here's a problem"** to **"here's the experiment to fix it"** in two clicks.

**Technical implementation**: The insight card writes `sweep_prefill` to Streamlit session state. The parameter sweep section reads it and writes directly to widget session state keys (not the `value=` parameter, which Streamlit ignores for already-rendered widgets — a lesson learned in production).

---

### Feature 3: Conversational AI Chat

**What it does**: Q&A about your simulation results with full conversation history.

**How it works**:
- Conversation history maintained in `ChatAssistant` (configurable max turns, default 10)
- Each message includes the full simulation context (config, KPIs, distribution)
- System prompt teaches the AI to cite specific numbers and be actionable
- History is formatted as a multi-turn conversation in the prompt

**Example exchanges**:
- "Why is the median so much lower than the mean?" → AI explains right-skewed distribution from geometric point scaling
- "What if I set all probabilities to 50%?" → AI calculates expected outcomes
- "Which parameter has the biggest impact on total_points?" → AI identifies the dominant lever

---

### Feature 4: AI Config Optimizer

**What it does**: Automatically tunes simulation parameters to hit a KPI target.

**The optimization loop**:
```
┌────────────────────────────────────────────────────┐
│                                                    │
│  1. Simulate with current config                   │
│  2. Compute distance to target                     │
│  3. If converged (within 5% tolerance) → STOP      │
│  4. Send to LLM: "current config, metric value,    │
│     target value — suggest better config"           │
│  5. Apply guardrails on LLM suggestion:             │
│     - Cap probabilities at [0, 1]                   │
│     - Ensure positive point values                  │
│     - Protect max_successes from changes            │
│  6. Track if this is the best config so far         │
│  7. Go to step 1                                    │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Three optimization modes**:
- **Target**: Converge to an exact value (e.g., "make pct_above_threshold = 5%")
- **Maximize**: Push a metric as high as possible
- **Minimize**: Push a metric as low as possible

**Before/After comparison**: After optimization, the UI shows:
- Side-by-side KPI cards (original vs optimized, with delta)
- Side-by-side distribution charts
- Config diff (which parameters changed and by how much)
- One-click "Apply Best Config & Re-run" button

**Guardrails are critical**: The LLM sometimes suggests impossible configs (probability = 1.5, negative points, changing max_successes mid-optimization). Every suggestion is sanitized before use. The optimizer also tracks the best config seen across all iterations, so if the LLM oscillates, the best result is always available.

---

### Feature 5: Multi-Model Selection

**What it does**: Users pick which AI model powers insights, chat, and optimization — right in the dashboard.

**Available models** (via AWS Bedrock):

| Model | Provider | MATH Score | Best For |
|-------|----------|------------|----------|
| Claude Opus 4.6 | Anthropic | 96.4% | Complex optimization, nuanced analysis |
| Claude Sonnet 4.6 | Anthropic | 94% | Default — balanced speed/quality |
| DeepSeek R1 | DeepSeek | 90% | Cost-effective analysis |
| Llama 4 Maverick | Meta | 85% | Fast iterations |
| Amazon Nova Pro | Amazon | 80% | Budget-friendly |

**Technical detail**: The BedrockAdapter uses dual-API routing — `invoke_model` for Anthropic models (which use Anthropic's native API format), `converse` for non-Anthropic models (which use Bedrock's unified format). This routing is transparent to the application layer.

---

### Feature 6: Bedrock Dual-API Routing

A non-obvious technical achievement. AWS Bedrock has two invocation APIs:

- **invoke_model**: Raw model invocation — you construct the request body in the model provider's native format
- **converse**: Unified API — Bedrock translates to the model's native format

Anthropic models on Bedrock work best with `invoke_model` (native Anthropic JSON format). Non-Anthropic models (DeepSeek, Llama, Nova) need the `converse` API. The `BedrockAdapter` detects the model provider from the model ID string and routes accordingly:

```python
if "anthropic" in self._model_id:
    # invoke_model with Anthropic-native JSON body
else:
    # converse with Bedrock-unified format
```

This means adding a new model to the registry is one line — no adapter code changes needed.

---

### Feature 7: Feature-Agnostic AI Layer

The entire AI layer (insights, chat, optimizer) is **feature-agnostic**. It works with plain dicts, not coin-flip-specific objects:

```python
# Any feature can provide this context
FeatureAnalysisContext(
    feature_name="coin_flip",        # or "loot_table", "reward_dist"
    result_summary={...},            # from SimulationResult.to_summary_dict()
    distribution={...},              # from SimulationResult.get_distribution()
    config={...},                    # from SimulatorConfig.to_dict()
    kpi_metrics={...},               # from SimulationResult.get_kpi_metrics()
)
```

Each feature's result model owns a `to_analysis_context()` method that packages its domain-specific data (churn segments, distribution format, etc.) into this generic container. Adding a new feature to the AI layer = implementing one method.

---

### Other Cool Technical Features

#### Vectorized Churn Normalization

The `about_to_churn` CSV column comes in many formats: `"true"/"false"`, `"TRUE"/"FALSE"`, `0/1`, `True/False`, or missing entirely. One vectorized Polars operation normalizes all of these:

```python
# No Python loops — pure Polars expressions
df.with_columns(
    pl.col("about_to_churn").str.to_lowercase().eq("true").alias("about_to_churn")
)
```

#### Path Traversal Protection

Run IDs stored on disk are validated with a strict regex (`^[a-f0-9]{32}$`) before any file operation. This prevents path traversal attacks like `../../etc/passwd` being used as a run_id. Tested with 14 parametrized attack vectors.

#### Docker Multi-Stage Build

Production image is ~350MB (vs ~1.5GB with dev dependencies). Non-root `appuser` with explicit `HOME` directory. Health check on Streamlit's `/_stcore/health` endpoint.

#### Async-in-Sync Bridge

Streamlit is synchronous, but LLM calls are async. The `run_async()` helper uses `ThreadPoolExecutor` to bridge the gap without blocking Streamlit's main thread or conflicting with its event loop.

#### Session State Guards

Streamlit reruns the entire script on every interaction. Multiple guards prevent stale state:
- `_simulation_running` flag prevents double-click on Run Simulation
- `config_changed_since_run` flag warns when AI analysis is based on old results
- `clear_stale_ai_data()` cleans all AI-related session keys when config changes
- `sweep_prefill` is popped (consumed once) to prevent re-triggering

#### E2E Testing Against Live Production

Playwright E2E tests run against the actual deployed AWS URL — not just localhost. Full flow tested: upload → simulate → generate insights → click sweep → verify fields update.

#### Design Log Methodology

22 architecture decision records documenting every non-trivial decision. Each log captures: context, decision, rationale, outcome. This is the project's institutional memory — future developers understand not just *what* was built but *why*.

---

## Hebrew / עברית

### איך AI שזור לתוך הפלטפורמה

זה לא פרויקט ש"משתמש ב-AI" כתוספת. AI משולב עמוק בזרימת העבודה של הסימולציה — מניתוח ועד אופטימיזציה ועד חקירה. כל פיצ'ר AI עוקב אחרי אותה ארכיטקטורה: **שירותי אפליקציה אגנוסטיים לפיצ'ר** מגובים ב-**הפשטת LLM מבוססת פרוטוקולים** עם **תמיכה במספר ספקים**.

---

### ארכיטקטורת AI

**עיקרון מפתח**: כל שירות AI מקבל dicts פשוטים (`result_summary`, `distribution`, `config`, `kpi_metrics`) — לא אובייקטים ספציפיים לדומיין. כלומר אותו InsightsAnalyst עובד על coin flip היום ו-loot tables מחר, ללא שינויי קוד.

---

### פיצ'ר 1: מנוע תובנות AI

**מה הוא עושה**: מנתח תוצאות סימולציה ומייצר 3-5 ממצאים פעילים, מדורגים לפי חומרה.

**איך זה עובד**:
1. נתוני סימולציה (KPIs, קונפיג, התפלגות) מתפרמטים לפרומפט מובנה
2. System prompt כולל ידע דומיין עמוק: איך מכניקת ההטלה עובדת, מה כל פרמטר אומר, מה כל KPI מודד
3. ה-LLM מחזיר מערך JSON של תובנות
4. פרסר חסין מטפל ב: JSON עטוף ב-markdown, שדות חסרים, ערכי severity לא תקינים

**ה-system prompt מכיר את הדומיין שלכם**: הוא מסביר ל-AI ש-`p_success_3` זו ההסתברות בעומק הטלה 3, שנקודות הן מצטברות, ש-`avg_multiplier` משקלל את התגמול הסופי. הקשר דומיין זה מייצר תובנות דרמטית טובות יותר מפרומפטים גנריים.

---

### פיצ'ר 2: צינור תובנה → Sweep

**הפיצ'ר הכי מגניב מבחינת UX**: כל תובנת AI יכולה לכלול כפתור הצעת sweep. לחיצה אחת ומקטע סריקת הפרמטרים מתמלא אוטומטית עם הניסוי שה-AI ממליץ עליו.

```
AI אומר: "p_success_4 ב-30% יוצר צוואר בקבוק — בדקו ערכים מ-0.3 עד 0.7"
     ↓
כפתור מופיע: [Sweep p_success_4: 0.3 → 0.7 (5 צעדים)]
     ↓
המשתמש לוחץ → טופס סריקת פרמטרים מתמלא עם start=0.3, end=0.7, steps=5
     ↓
המשתמש לוחץ "Run Sweep" → 5 סימולציות רצות → גרף קו מראה השפעה על KPI
```

זה סוגר את המעגל מ-**"הנה בעיה"** ל-**"הנה הניסוי לתקן את זה"** בשתי לחיצות.

---

### פיצ'ר 3: צ'אט AI

- שיחה על תוצאות הסימולציה עם היסטוריית שיחה מלאה (עד 10 תורות)
- כל הודעה כוללת את כל הקשר הסימולציה (קונפיג, KPIs, התפלגות)
- ה-system prompt מלמד את ה-AI לצטט מספרים ספציפיים ולהיות פעיל

---

### פיצ'ר 4: אופטימייזר AI

**לולאת האופטימיזציה**:
1. הרץ סימולציה עם קונפיג נוכחי
2. חשב מרחק ליעד
3. אם התכנס (בטווח 5% סבילות) → עצור
4. שלח ל-LLM: "קונפיג נוכחי, ערך מדד, ערך יעד — הצע קונפיג טוב יותר"
5. החל guardrails על הצעת ה-LLM
6. עקוב האם זה הקונפיג הטוב ביותר עד כה
7. חזור לשלב 1

**שלושה מצבי אופטימיזציה**: Target (התכנסות לערך מדויק), Maximize, Minimize.

**השוואת לפני/אחרי**: כרטיסי KPI צד-לצד + גרפי התפלגות + דיף קונפיג + כפתור "החל קונפיג מיטבי".

**Guardrails קריטיים**: ה-LLM לפעמים מציע קונפיגים בלתי אפשריים (הסתברות 1.5, נקודות שליליות). כל הצעה מנוקה לפני שימוש.

---

### פיצ'ר 5: בחירת מודלים מרובים

5 מודלי AI זמינים בדשבורד, כולם דרך AWS Bedrock:

| מודל | ציון MATH | הכי מתאים ל- |
|------|-----------|-------------|
| Claude Opus 4.6 | 96.4% | אופטימיזציה מורכבת, ניתוח מנואנס |
| Claude Sonnet 4.6 | 94% | ברירת מחדל — איזון מהירות/איכות |
| DeepSeek R1 | 90% | ניתוח חסכוני |
| Llama 4 Maverick | 85% | איטרציות מהירות |
| Amazon Nova Pro | 80% | ידידותי לתקציב |

---

### פיצ'ר 6: ניתוב API כפול ב-Bedrock

הישג טכני לא טריוויאלי. ל-AWS Bedrock יש שתי APIs:
- **invoke_model**: קריאה ישירה בפורמט הנייטיבי של הספק
- **converse**: API אחיד — Bedrock מתרגם לפורמט הנייטיבי

מודלים של Anthropic עובדים הכי טוב עם `invoke_model`. מודלים אחרים (DeepSeek, Llama, Nova) צריכים `converse`. ה-`BedrockAdapter` מזהה את הספק מה-model ID ומנתב בהתאם. הוספת מודל חדש לרג'יסטרי = שורה אחת.

---

### פיצ'ר 7: שכבת AI אגנוסטית לפיצ'ר

כל שכבת ה-AI (תובנות, צ'אט, אופטימייזר) היא **אגנוסטית לפיצ'ר**. עובדת עם dicts פשוטים:

כל פיצ'ר מממש מתודת `to_analysis_context()` שאורזת את הנתונים הספציפיים שלו (סגמנטי נטישה, פורמט התפלגות) לתוך container גנרי. הוספת פיצ'ר חדש לשכבת ה-AI = מימוש מתודה אחת.

---

### פיצ'רים טכניים מגניבים נוספים

- **נרמול נטישה וקטורי** — עמודת about_to_churn בכל פורמט (string/int/bool/חסר) מנורמלת בפעולת Polars אחת
- **הגנה מפני path traversal** — run IDs מאומתים עם regex קפדני, נבדק עם 14 וקטורי תקיפה פרמטריים
- **Docker multi-stage** — תמונת פרודקשן ~350MB, משתמש non-root, health check
- **גשר async-in-sync** — LLM calls הם async, Streamlit סינכרוני. `run_async()` מגשר עם ThreadPoolExecutor
- **שומרי session state** — מניעת double-click, ניקוי נתוני AI ישנים, sweep_prefill נצרך פעם אחת
- **טסטים E2E נגד פרודקשן** — Playwright רץ נגד ה-URL של AWS בפועל
- **22 Design Logs** — כל החלטה ארכיטקטורית מתועדת: הקשר, החלטה, נימוק, תוצאה
