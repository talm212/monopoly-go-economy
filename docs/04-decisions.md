# Key Decisions & Why / החלטות מפתח ולמה

---

## English

### Decision 1: Polars Over Pandas

**Context**: The platform processes player DataFrames with potentially millions of rows. Pandas is the Python data ecosystem default.

**Decision**: Use **Polars** exclusively. Never Pandas.

**Why**:
- Polars is 10-50x faster than Pandas for aggregation and group-by operations at scale
- Polars has true lazy evaluation — operations can be optimized before execution
- Polars has a Rust backend — no GIL bottleneck on CPU-bound work
- Polars has stricter types (no silent NaN coercion like Pandas)
- Memory usage is significantly lower for large DataFrames

**Tradeoff**: Smaller ecosystem, less Stack Overflow answers, some Streamlit components expect Pandas (we convert at the boundary with `.to_pandas()` only where Streamlit requires it, like `st.line_chart`).

---

### Decision 2: Vectorized NumPy Over Python Loops

**Context**: A coin flip simulation with 1M players and 10M+ interactions needs to run in seconds, not minutes.

**Decision**: Generate ALL random numbers in a single `rng.random((N, max_successes))` call. Use boolean matrix operations and `np.cumprod` for success chain detection. Zero Python for-loops over data.

**Why**:
- Python for-loops over millions of rows = minutes
- NumPy vectorized operations = seconds (1M interactions/second)
- Single allocation pattern: one big matrix instead of millions of small arrays
- `np.cumprod` on int8 finds consecutive successes without branching — elegant and fast

**Tradeoff**: Code is harder to read than a simple `for player in players: for flip in range(max_successes)` loop. Worth it for 1000x speedup.

**Alternative considered**: Numba JIT compilation. Rejected because it adds a compilation step, dependency complexity, and NumPy vectorization was already fast enough.

---

### Decision 3: Clean Architecture (4 Layers)

**Context**: First instinct for a "simulation dashboard" might be a single script: read CSV, simulate, display.

**Decision**: Full Clean Architecture with domain/application/infrastructure/UI separation. Protocols for all interfaces.

**Why**:
- The platform will support multiple game features (coin flip first, then loot tables, reward distributions)
- Each feature should plug into the same dashboard, AI analysis, and deployment without rewriting infrastructure
- Testing pure domain logic is trivial when it has no I/O dependencies
- Swapping Bedrock for Anthropic (or adding OpenAI) is a one-line change in the factory

**Tradeoff**: More files, more indirection, slower initial velocity. But the payoff is real: adding the AI layer required zero changes to the simulation engine. Adding multi-model support required zero changes to the application layer.

---

### Decision 4: Protocol (Duck Typing) Over ABC (Inheritance)

**Context**: Python offers two ways to define interfaces: `ABC` (abstract base class, requires explicit inheritance) and `Protocol` (structural subtyping, duck typing).

**Decision**: Use `@runtime_checkable Protocol` for all interfaces.

**Why**:
- Protocols don't require explicit inheritance — any class that has the right methods satisfies the protocol
- This aligns with Python's duck typing philosophy
- `@runtime_checkable` allows `isinstance()` checks in tests and at runtime
- Decouples the interface definition from its implementations (infrastructure doesn't need to import domain protocols to satisfy them — though we do import for clarity)

**Tradeoff**: Runtime checking is slower than compile-time (mypy catches most mismatches statically). Some developers find `Protocol` less discoverable than `ABC`.

---

### Decision 5: Bedrock as Default LLM Provider (Not Direct Anthropic API)

**Context**: The platform needs AI capabilities. Two options: Anthropic API directly, or AWS Bedrock.

**Decision**: Default to **Bedrock** in production. Anthropic adapter available for local development.

**Why**:
- **No API keys in production**: ECS Fargate tasks get IAM role permissions automatically. No secrets management needed.
- **Multi-model access**: Bedrock provides Claude, DeepSeek, Llama, Nova — users can choose in the dashboard
- **AWS ecosystem**: The platform already runs on AWS (ECS, S3, DynamoDB). Bedrock is native.
- **Billing**: AI costs go through the same AWS account — no separate vendor billing

**Tradeoff**: Bedrock sometimes lags behind Anthropic's latest model releases. The Anthropic adapter exists as a fallback and for developers who prefer direct API access.

---

### Decision 6: Dual-API Routing in BedrockAdapter

**Context**: Bedrock has two invocation APIs: `invoke_model` (raw, provider-native format) and `converse` (unified format).

**Decision**: Route Anthropic models to `invoke_model`, non-Anthropic models to `converse`. Detect automatically from model ID.

**Why**:
- Anthropic models on Bedrock work best with their native JSON format via `invoke_model`
- Non-Anthropic models (DeepSeek, Llama, Nova) use different native formats — `converse` API abstracts this away
- Detection is simple: `if "anthropic" in model_id`
- Adding a new model = one line in the registry, zero adapter code changes

**Tradeoff**: Two code paths to maintain. But each is simple and well-tested (parametrized tests cover both paths).

---

### Decision 7: Domain Exceptions Inherit from ValueError

**Context**: Custom domain exceptions (`InvalidConfigError`, `InvalidPlayerDataError`) were introduced to replace generic `ValueError` usage.

**Decision**: Make domain exceptions inherit from **both** `SimulationError` AND `ValueError`.

**Why**:
- Existing code had `except ValueError` blocks and `pytest.raises(ValueError)` assertions
- Changing all of those would be a breaking refactor across many files
- Multiple inheritance (`class InvalidConfigError(SimulationError, ValueError)`) means:
  - `except ValueError` still catches them (backward compat)
  - `except InvalidConfigError` catches them (new, specific handling)
  - `except SimulationError` catches all domain errors (grouped handling)

**Tradeoff**: Multiple inheritance is sometimes considered a code smell. Here it's a pragmatic bridge — all tests pass without changes, and new code can use the specific exceptions.

---

### Decision 8: JSON + Parquet for Simulation History (Not SQLite)

**Context**: Simulation runs need persistence. Options: SQLite database, JSON files, or cloud database.

**Decision**: JSON files for metadata, Parquet files for player DataFrames. File-based, no database.

**Why**:
- JSON is human-readable — developers can inspect runs manually
- Parquet is the best format for columnar DataFrames (fast, compressed, schema-preserving)
- No database dependency to install or manage
- Auto-rebuilding index means corrupted state is self-healing
- Fits the containerized deployment model (local disk or mounted volume)

**Tradeoff**: No query capability (can't do "find all runs where total_points > 1M" without loading all files). Acceptable for the current use case (dozens of runs, not millions).

---

### Decision 9: Feature-Agnostic AI Layer via FeatureAnalysisContext

**Context**: The AI layer (insights, chat, optimizer) was initially built for coin flip only. But future features (loot tables, rewards) need the same AI capabilities.

**Decision**: Introduce `FeatureAnalysisContext` — a generic frozen dataclass that packages any feature's data for AI consumption. Each feature's result model implements `to_analysis_context()`.

**Why**:
- Avoids copy-pasting AI integration code for each new feature
- The AI services (InsightsAnalyst, ChatAssistant, ConfigOptimizer) don't change at all
- Domain logic stays in the domain: churn segment computation lives in `CoinFlipResult.to_analysis_context()`, not in the UI layer
- New feature = implement `to_analysis_context()` → AI just works

**Tradeoff**: Extra abstraction layer. But it eliminated 3 duplicate context-building functions that were already diverging.

---

### Decision 10: Streamlit Over React/Vue

**Context**: The dashboard could be built with any frontend framework.

**Decision**: **Streamlit** — Python-only, no JavaScript.

**Why**:
- Economy team designers are Python-literate, not frontend developers
- Streamlit handles state management, layout, and reactivity in pure Python
- Upload widgets, sliders, charts, tables — all built-in
- Hot reload for rapid iteration
- Deploys as a simple Docker container (no build step, no Node.js)

**Tradeoff**: Limited UI customization. No component-level interactivity (everything triggers a full re-run). Session state management has gotchas (widget keys, prefill timing). We mitigated these with `session_utils.py` and learned patterns like "write to session state keys directly, not via `value=` parameter."

---

### Decision 11: Non-Root Docker Container

**Context**: By default, Docker runs as root. Security best practices require non-root.

**Decision**: Create a system user `appuser` with explicit home directory and file permissions.

**Why**:
- Security: compromised container can't write to system files
- AWS Fargate best practice
- Aligns with principle of least privilege

**What went wrong**: Twice.
1. First attempt: `appuser` couldn't write to `.simulation_history` → fixed by pre-creating + `chown`
2. Second attempt: Streamlit crashed because `HOME=/nonexistent` → fixed by `--home /app/home` + `ENV HOME="/app/home"`

**Lesson**: Non-root containers need explicit writable directories for every service that writes files (Streamlit writes config, cache, and session data).

---

### Decision 12: Design Log Methodology

**Context**: Software decisions are often undocumented — future developers wonder "why was this done this way?"

**Decision**: Mandatory design log before every non-trivial task. 22 logs created during the project.

**Why**:
- Forces thinking before coding
- Creates institutional memory
- Captures not just what was built, but why alternatives were rejected
- Makes code review easier (reviewer can read the decision document, not just the diff)
- Helps the next developer (or AI assistant) understand context

**Format**: Numbered markdown files in `/design-logs/`. Each log: Context → Decision → Rationale → Outcome.

---

### Decision 13: TDD (Red → Green → Refactor)

**Context**: Testing can be done after implementation ("write code, then add tests") or before ("write failing test, then implement").

**Decision**: Strict TDD — write the failing test first, confirm it fails, implement to make it pass, refactor.

**Why**:
- Catches design issues early (if a test is hard to write, the interface is wrong)
- Forces thinking about edge cases before implementation
- Every line of production code has a reason to exist (it makes a test pass)
- Prevents "works on my machine" — tests are the contract
- 672 tests provide confidence for refactoring

**How enforced**: CLAUDE.md mandates TDD. Test files created before implementation files. Commit messages reference which tests were added.

---

### Decision 14: Parallel Agent Development (Git Worktrees)

**Context**: During a major refactoring phase, 8 independent tasks needed to be done (generic config editor, feature routing, session utils, etc.).

**Decision**: Use **git worktrees** — 8 Claude Code agents working in parallel on isolated copies of the repo.

**Why**:
- Each agent works in isolation (no merge conflicts during work)
- All 8 tasks completed in the time of ~2 sequential tasks
- Each branch independently testable before merge
- Merge conflicts resolved once, at the end, with full context

**What went wrong**: `.claude/worktrees/` directory was accidentally committed via `git add -A`. Fixed by adding to `.gitignore`.

**Lesson**: Parallel agent development with worktrees is powerful but requires careful commit hygiene. Never `git add -A` — always add specific files.

---

## Hebrew / עברית

### החלטה 1: Polars במקום Pandas

**הקשר**: הפלטפורמה מעבדת DataFrames של שחקנים עם פוטנציאל של מיליוני שורות.

**החלטה**: שימוש ב-**Polars** בלבד. אף פעם Pandas.

**למה**:
- Polars מהיר פי 10-50 מ-Pandas לפעולות צבירה ו-group-by בקנה מידה
- ל-Polars יש הערכה עצלה אמיתית — פעולות אופטימליות לפני ביצוע
- Backend ב-Rust — ללא צוואר בקבוק GIL
- סוגים קפדניים יותר (ללא כפייה שקטה ל-NaN כמו ב-Pandas)

**פשרה**: אקוסיסטם קטן יותר, פחות תשובות ב-Stack Overflow. חלק מקומפוננטות Streamlit מצפות ל-Pandas — ממירים בגבול עם `.to_pandas()` רק היכן ש-Streamlit דורש.

---

### החלטה 2: NumPy וקטורי במקום לולאות Python

**הקשר**: סימולציית הטלת מטבע עם מיליון שחקנים ו-10 מיליון+ אינטראקציות צריכה לרוץ בשניות, לא דקות.

**החלטה**: ייצור כל המספרים האקראיים בקריאה אחת של `rng.random((N, max_successes))`. שימוש בפעולות מטריצת בוליאנים ו-`np.cumprod` לזיהוי שרשרות הצלחה. אפס לולאות Python.

**למה**:
- לולאות Python על מיליוני שורות = דקות
- פעולות NumPy וקטוריות = שניות (מיליון אינטראקציות/שנייה)
- האצה של פי 1000

**פשרה**: הקוד קשה יותר לקריאה מלולאה פשוטה. שווה את זה בשביל ביצועים.

---

### החלטה 3: Clean Architecture (4 שכבות)

**הקשר**: האינסטינקט הראשון ל"דשבורד סימולציה" יכול להיות סקריפט אחד.

**החלטה**: Clean Architecture מלא עם הפרדת domain/application/infrastructure/UI.

**למה**:
- הפלטפורמה תתמוך במספר פיצ'רי משחק (הטלת מטבע קודם, אח"כ loot tables, חלוקת תגמולים)
- כל פיצ'ר צריך להתחבר לאותו דשבורד, ניתוח AI ופריסה ללא שכתוב תשתית
- בדיקת לוגיקת דומיין טהורה טריוויאלית כשאין תלויות I/O
- החלפת Bedrock ב-Anthropic = שינוי שורה אחת ב-factory

**פשרה**: יותר קבצים, יותר הפניות עקיפות. אבל ההחזר אמיתי: הוספת שכבת AI דרשה אפס שינויים במנוע הסימולציה.

---

### החלטה 4: Protocol (Duck Typing) במקום ABC

**הקשר**: Python מציעה שתי דרכים להגדרת ממשקים.

**החלטה**: שימוש ב-`@runtime_checkable Protocol` לכל הממשקים.

**למה**:
- Protocols לא דורשים ירושה מפורשת — כל מחלקה עם המתודות הנכונות מקיימת את הפרוטוקול
- תואם לפילוסופיית duck typing של Python
- `@runtime_checkable` מאפשר בדיקות `isinstance()` בטסטים ובזמן ריצה

---

### החלטה 5: Bedrock כספק LLM ברירת מחדל

**הקשר**: הפלטפורמה צריכה יכולות AI. שתי אפשרויות: Anthropic API ישירות, או AWS Bedrock.

**החלטה**: Bedrock כברירת מחדל בפרודקשן.

**למה**:
- **ללא מפתחות API בפרודקשן**: tasks של ECS Fargate מקבלים הרשאות IAM role אוטומטית
- **גישה למספר מודלים**: Bedrock מספק Claude, DeepSeek, Llama, Nova — המשתמשים בוחרים בדשבורד
- **אקוסיסטם AWS**: הפלטפורמה כבר רצה על AWS
- **חיוב**: עלויות AI עוברות דרך אותו חשבון AWS

---

### החלטה 6: ניתוב API כפול ב-BedrockAdapter

**החלטה**: ניתוב מודלים של Anthropic ל-`invoke_model`, מודלים אחרים ל-`converse`. זיהוי אוטומטי מ-model ID.

**למה**:
- מודלים של Anthropic עובדים הכי טוב עם הפורמט הנייטיבי שלהם
- מודלים אחרים משתמשים בפורמטים שונים — `converse` מפשט
- הוספת מודל חדש = שורה אחת ברג'יסטרי

---

### החלטה 7: חריגות דומיין יורשות מ-ValueError

**החלטה**: `class InvalidConfigError(SimulationError, ValueError)` — ירושה מרובה.

**למה**:
- קוד קיים עם `except ValueError` ו-`pytest.raises(ValueError)` — ממשיך לעבוד
- קוד חדש יכול לתפוס `except InvalidConfigError` — ספציפי יותר
- `except SimulationError` — תופס את כל שגיאות הדומיין

**פשרה**: ירושה מרובה לפעמים נחשבת code smell. כאן זה גשר פרגמטי — כל הטסטים עוברים ללא שינויים.

---

### החלטה 8: JSON + Parquet להיסטוריה (לא SQLite)

**החלטה**: קבצי JSON למטאדאטה, Parquet ל-DataFrames. מבוסס קבצים, ללא בסיס נתונים.

**למה**:
- JSON קריא — מפתחים יכולים לבדוק הרצות ידנית
- Parquet הפורמט הטוב ביותר ל-DataFrames עמודתיים
- ללא תלות בבסיס נתונים
- אינדקס שמתבנה מחדש אוטומטית = ריפוי עצמי

---

### החלטה 9: שכבת AI אגנוסטית דרך FeatureAnalysisContext

**החלטה**: dataclass גנרי שאורז נתונים מכל פיצ'ר לצריכת AI.

**למה**:
- מונע העתק-הדבק של קוד אינטגרציית AI לכל פיצ'ר חדש
- שירותי AI (InsightsAnalyst, ChatAssistant, ConfigOptimizer) לא משתנים בכלל
- פיצ'ר חדש = מימוש `to_analysis_context()` → AI פשוט עובד

---

### החלטה 10: Streamlit במקום React/Vue

**החלטה**: **Streamlit** — Python בלבד, ללא JavaScript.

**למה**:
- צוות הכלכלה יודע Python, לא פיתוח frontend
- העלאת קבצים, סליידרים, גרפים, טבלאות — הכל מובנה
- פריסה כ-Docker container פשוט (ללא build step, ללא Node.js)

**פשרה**: התאמה אישית מוגבלת של UI. ניהול session state עם gotchas. פתרנו עם `session_utils.py` ודפוסים שלמדנו (כתיבה ישירה ל-session state keys).

---

### החלטה 11: Container Docker ללא root

**החלטה**: יצירת משתמש מערכת `appuser` עם home directory מפורש והרשאות קבצים.

**מה השתבש**: פעמיים.
1. `appuser` לא יכל לכתוב ל-`.simulation_history` → תוקן עם pre-creating + `chown`
2. Streamlit קרס כי `HOME=/nonexistent` → תוקן עם `--home /app/home`

**לקח**: containers ללא root צריכים ספריות כתיבה מפורשות לכל שירות שכותב קבצים.

---

### החלטה 12: מתודולוגיית Design Log

**החלטה**: Design log חובה לפני כל משימה לא-טריוויאלית. 22 לוגים נוצרו.

**למה**:
- מאלץ חשיבה לפני קידוד
- יוצר זיכרון מוסדי
- לוכד לא רק מה נבנה, אלא למה חלופות נדחו
- עוזר למפתח הבא (או עוזר AI) להבין הקשר

---

### החלטה 13: TDD (אדום → ירוק → רפקטור)

**החלטה**: TDD קפדני — כתיבת טסט כושל קודם, אישור כישלון, מימוש, אימות.

**למה**:
- תופס בעיות עיצוב מוקדם
- מאלץ חשיבה על edge cases לפני מימוש
- 672 טסטים נותנים ביטחון לרפקטורינג

---

### החלטה 14: פיתוח סוכנים מקבילי (Git Worktrees)

**הקשר**: במהלך שלב רפקטורינג גדול, 8 משימות עצמאיות נדרשו.

**החלטה**: שימוש ב-**git worktrees** — 8 סוכני Claude Code עובדים במקביל על עותקים מבודדים של הריפו.

**למה**:
- כל סוכן עובד בבידוד (ללא merge conflicts בזמן עבודה)
- כל 8 המשימות הושלמו בזמן של ~2 משימות סדרתיות
- קונפליקטים של merge נפתרו פעם אחת, בסוף, עם הקשר מלא

**מה השתבש**: ספריית `.claude/worktrees/` הוכנסה בטעות לקומיט דרך `git add -A`. תוקן עם הוספה ל-`.gitignore`.

**לקח**: פיתוח מקבילי עם worktrees הוא חזק אבל דורש היגיינת קומיט זהירה. לעולם אל תעשו `git add -A` — תמיד הוסיפו קבצים ספציפיים.
