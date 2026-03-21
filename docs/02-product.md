# Product Guide / מדריך מוצר

---

## English

### What Is This?

A **self-service simulation platform** for the Monopoly Go economy team. Upload player data, configure game mechanics, run simulations at scale, and get AI-powered insights — all from a web dashboard. No engineering support needed.

---

### Core User Flow

```
Upload Player CSV → Upload Config CSV → Edit Parameters → Run Simulation
    ↓                                                          ↓
Review KPIs ← Distribution Charts ← Churn Segments ← Per-Player Data Table
    ↓
AI Insights → Sweep Suggestions → Parameter Sweep → Compare Configs
    ↓
AI Chat (Q&A) → AI Optimizer (auto-tune) → Download PDF Report
    ↓
Save to History → Load Past Runs → Compare Two Runs Side-by-Side
```

---

### Features

#### 1. Data Upload & Validation

- **Player CSV**: `user_id`, `rolls_sink`, `avg_multiplier`, `about_to_churn`
- **Config CSV**: `Input/Value` format with `p_success_N`, `points_success_N`, `max_successes`, etc.
- Automatic validation on upload: missing columns, invalid values, data types
- Churn column auto-normalization: accepts `true/false`, `0/1`, `TRUE/FALSE`, missing → `False`
- Preview of parsed data immediately after upload

#### 2. Interactive Config Editor

- Dynamic form generated from config structure — no hardcoded fields
- **Flip Configuration** tab: probabilities (as percentage sliders), point values
- **Simulation Settings** tab: reward threshold, churn boost multiplier, max successes
- Tooltips on every field explaining what it does and its valid range
- Tracks changes since last simulation (warns when AI analysis is stale)

#### 3. Simulation Engine

- Runs in seconds even for 1M+ players
- Deterministic with optional seed (reproducible results)
- Fully vectorized — no Python loops over data
- Computes per-player results: `total_points`, `num_interactions`, `about_to_churn`
- Produces distribution histogram of success depths

#### 4. Results Dashboard

**Three tabs:**

| Tab | Content |
|-----|---------|
| **Charts** | Success depth bar chart + points distribution histogram |
| **Churn Analysis** | Side-by-side comparison: churning vs non-churning player segments (mean/median points, count, total) |
| **Data Table** | Full per-player results table with CSV download |

**KPI Cards** (always visible):
- Total Points (economy-wide inflation indicator)
- Mean Points / Player
- Median Points / Player
- % Above Threshold (fraction earning more than reward_threshold)
- Total Interactions
- Players Above Threshold (count)

#### 5. AI-Powered Insights

Click "Generate Insights" → AI analyzes your simulation and returns 3-5 actionable findings:

- **Severity badges**: INFO (blue), WARNING (orange), CRITICAL (red)
- Each insight includes: finding (with specific numbers), recommendation, supporting metrics
- **Sweep suggestions**: "Sweep p_success_4 from 0.3 to 0.7 in 5 steps" — click the button and the Parameter Sweep section auto-fills

**Example insight:**
> **WARNING**: The mean_points_per_player (1379.8) is nearly 7x the median (200.0), indicating a severely right-skewed distribution. A tiny minority of players reaching depths 4-5 are massively inflating the average.
>
> *Recommendation:* Flatten the points curve to reduce tail inflation. Consider changing point_values from the current geometric doubling (1, 2, 4, 8, 16) to a more linear scale (1, 1.5, 2, 3, 5).

#### 6. AI Chat (Ask a Question)

- Conversational Q&A about your simulation results
- Maintains conversation history (up to 10 turns)
- Context-aware: knows your config, KPIs, distribution, churn segments
- Ask things like: "What would happen if I doubled p_success_3?" or "Why is the median so much lower than the mean?"

#### 7. AI Config Optimizer

- Set a target: "Make pct_above_threshold = 5%" or "Maximize mean_points_per_player"
- AI iteratively adjusts config parameters, runs simulation, evaluates, adjusts again
- Guardrails: probabilities capped at [0,1], positive point values, max_successes protected
- Convergence tracking: stops when within 5% of target
- **Before/After comparison**: side-by-side KPI cards + distribution charts
- One-click "Apply Best Config" to load the optimized config

#### 8. Parameter Sweep

- Pick any config parameter (p_success_1..N, points_success_1..N, reward_threshold)
- Set start, end, number of steps
- Runs one full simulation per step
- Results: line chart (parameter value vs KPI) + data table + CSV download
- Pre-fill from AI insight sweep suggestions

#### 9. Simulation History

- Every run saved automatically (JSON metadata + Parquet player data)
- Sidebar drawer: browse past runs sorted by date
- **Load**: restore a past run's results to the dashboard
- **Delete**: remove a run permanently
- **Compare**: select two runs and see KPI differences side-by-side

#### 10. Multi-Model AI

Users can select from 5 AI models in the dashboard:

| Model | Benchmark (MATH) |
|-------|------------------|
| Claude Opus 4.6 | 96.4% |
| Claude Sonnet 4.6 | 94% (default) |
| DeepSeek R1 | 90% |
| Meta Llama 4 Maverick | 85% |
| Amazon Nova Pro | 80% |

All models run via AWS Bedrock — no API keys to manage in production.

#### 11. PDF Report Download

- Generate a downloadable PDF with simulation summary, config, KPIs
- Shareable with stakeholders who don't use the dashboard

#### 12. CLI Interface

Command-line interface for batch processing:
```bash
poetry run python -m src.cli \
    --players coin-flip-assignment/input_table.csv \
    --config coin-flip-assignment/config_table.csv \
    --output results.csv \
    --seed 42
```

---

### What Makes This Product Special

1. **Self-service for economy designers** — no engineering tickets needed to test a config change
2. **Real-time AI analysis** — not just data, but actionable recommendations with severity levels
3. **Closed-loop optimization** — AI doesn't just suggest, it auto-tunes and shows before/after proof
4. **Insight → Sweep pipeline** — one click from "you should investigate p_success_4" to running the experiment
5. **Scale without pain** — 1M players processes in seconds, not minutes
6. **Multi-model choice** — pick the AI model that fits your speed/quality tradeoff
7. **Full history** — every simulation is saved, comparable, reproducible

---

## Hebrew / עברית

### מה זה?

**פלטפורמת סימולציה בשירות עצמי** לצוות הכלכלה של מונופולי Go. העלו נתוני שחקנים, הגדירו מכניקות משחק, הריצו סימולציות בקנה מידה גדול, וקבלו תובנות מבוססות AI — הכל מדשבורד ווב. ללא צורך בתמיכת הנדסה.

---

### זרימת שימוש מרכזית

```
העלאת CSV שחקנים → העלאת CSV קונפיג → עריכת פרמטרים → הרצת סימולציה
    ↓                                                          ↓
סקירת KPIs ← גרפי התפלגות ← סגמנטי נטישה ← טבלת נתונים לכל שחקן
    ↓
תובנות AI → הצעות sweep → סריקת פרמטרים → השוואת קונפיגורציות
    ↓
צ'אט AI (שאלות ותשובות) → אופטימייזר AI (כיוונון אוטומטי) → הורדת PDF
    ↓
שמירה בהיסטוריה → טעינת הרצות קודמות → השוואה צד-לצד
```

---

### פיצ'רים

#### 1. העלאת נתונים וולידציה

- **CSV שחקנים**: `user_id`, `rolls_sink`, `avg_multiplier`, `about_to_churn`
- **CSV קונפיג**: פורמט `Input/Value` עם `p_success_N`, `points_success_N` וכו'
- ולידציה אוטומטית בהעלאה: עמודות חסרות, ערכים לא תקינים, סוגי נתונים
- נרמול אוטומטי של עמודת נטישה: מקבל `true/false`, `0/1`, חסר → `False`
- תצוגה מקדימה של הנתונים מיד אחרי ההעלאה

#### 2. עורך קונפיגורציה אינטראקטיבי

- טופס דינמי שנוצר ממבנה הקונפיג — ללא שדות hardcoded
- **הגדרות הטלה**: הסתברויות (כסליידר אחוזים), ערכי נקודות
- **הגדרות סימולציה**: סף תגמול, מכפיל נטישה, מקסימום הצלחות
- טולטיפים על כל שדה שמסבירים מה הוא עושה והטווח התקין
- מעקב אחרי שינויים מאז הסימולציה האחרונה

#### 3. מנוע סימולציה

- רץ בשניות גם על מיליון+ שחקנים
- דטרמיניסטי עם seed אופציונלי (תוצאות ניתנות לשחזור)
- וקטוריזציה מלאה — אפס לולאות Python על נתונים
- מחשב תוצאות לכל שחקן: `total_points`, `num_interactions`, `about_to_churn`

#### 4. דשבורד תוצאות

**שלושה טאבים:**
- **גרפים** — היסטוגרמת עומקי הצלחה + התפלגות נקודות
- **ניתוח נטישה** — השוואה צד-לצד: שחקנים נוטשים מול לא נוטשים
- **טבלת נתונים** — כל התוצאות לכל שחקן עם הורדת CSV

**כרטיסי KPI** (תמיד נראים): סה"כ נקודות, ממוצע, חציון, אחוז מעל סף, אינטראקציות, ספירה מעל סף.

#### 5. תובנות AI

לחצו "Generate Insights" → ה-AI מנתח את הסימולציה ומחזיר 3-5 ממצאים פעילים:

- **תגיות חומרה**: INFO (כחול), WARNING (כתום), CRITICAL (אדום)
- כל תובנה כוללת: ממצא (עם מספרים ספציפיים), המלצה, מדדים תומכים
- **הצעות sweep**: "סרקו p_success_4 מ-0.3 עד 0.7 ב-5 צעדים" — לחצו על הכפתור וסריקת הפרמטרים מתמלאת אוטומטית

#### 6. צ'אט AI (שאלו שאלה)

- שיחה על תוצאות הסימולציה שלכם
- שומר היסטוריית שיחה (עד 10 תורות)
- מודע להקשר: מכיר את הקונפיג, KPIs, התפלגות, סגמנטי נטישה

#### 7. אופטימייזר AI

- הגדירו יעד: "הביאו את pct_above_threshold ל-5%" או "מקסמו mean_points_per_player"
- ה-AI מתאים פרמטרים באופן איטרטיבי, מריץ סימולציה, מעריך, מתאים שוב
- Guardrails: הסתברויות מוגבלות ל-[0,1], ערכי נקודות חיוביים
- **השוואת לפני/אחרי**: כרטיסי KPI + גרפי התפלגות צד-לצד
- כפתור "החל קונפיג מיטבי" בלחיצה אחת

#### 8. סריקת פרמטרים (Parameter Sweep)

- בחרו פרמטר כלשהו, הגדירו התחלה, סוף, מספר צעדים
- כל צעד = סימולציה מלאה
- תוצאות: גרף קו (ערך פרמטר מול KPI) + טבלה + הורדת CSV
- מילוי מראש מהצעות sweep של תובנות AI

#### 9. היסטוריית סימולציות

- כל הרצה נשמרת אוטומטית (JSON metadata + Parquet נתוני שחקנים)
- מגירה צדדית: עיינו בהרצות קודמות ממוינות לפי תאריך
- **טעינה**: שחזרו תוצאות הרצה קודמת לדשבורד
- **מחיקה**: הסירו הרצה לצמיתות
- **השוואה**: בחרו שתי הרצות וראו הבדלי KPI צד-לצד

#### 10. בחירת מודל AI

5 מודלי AI זמינים בדשבורד:

| מודל | ציון (MATH) |
|------|-------------|
| Claude Opus 4.6 | 96.4% |
| Claude Sonnet 4.6 | 94% (ברירת מחדל) |
| DeepSeek R1 | 90% |
| Meta Llama 4 Maverick | 85% |
| Amazon Nova Pro | 80% |

כל המודלים רצים דרך AWS Bedrock — ללא צורך בניהול מפתחות API בפרודקשן.

---

### מה מיוחד במוצר הזה

1. **שירות עצמי למעצבי כלכלה** — ללא צורך בפתיחת טיקט הנדסי כדי לבדוק שינוי קונפיג
2. **ניתוח AI בזמן אמת** — לא רק נתונים, אלא המלצות פעילות עם רמות חומרה
3. **אופטימיזציה במעגל סגור** — ה-AI לא רק מציע, הוא מכוונן אוטומטית ומראה הוכחה לפני/אחרי
4. **צינור תובנה → sweep** — לחיצה אחת מ"כדאי לחקור p_success_4" להרצת הניסוי
5. **קנה מידה ללא כאב** — מיליון שחקנים מעובדים בשניות, לא דקות
6. **בחירת מודלים** — בחרו את מודל ה-AI שמתאים ליחס מהירות/איכות
7. **היסטוריה מלאה** — כל סימולציה נשמרת, ניתנת להשוואה, ניתנת לשחזור
