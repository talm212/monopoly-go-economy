# Coin Flip Economy Simulator -- Product Redesign Spec

**Author:** Product + Design
**Date:** 2026-03-20
**Status:** Proposed
**Audience:** Engineering team, economy team stakeholders

---

## 1. Problem Statement

The current app splits functionality across three Streamlit pages (Coin Flip, AI Insights, History) with a sidebar acting as both navigation and branding. The user complaint is "too many things in the sidebar." The deeper problem: the multi-page architecture forces users to hop between pages for a workflow that is fundamentally linear. Every simulation follows the same path: load data, configure, run, analyze, iterate. Splitting this across pages breaks flow and hides context.

The AI features (insights, chat, optimizer) live on a separate page, disconnected from the results they analyze. History lives on yet another page. The user has to carry mental context across three pages that should feel like one workspace.

---

## 2. Design Philosophy

**One screen, one purpose.** This tool does one thing: simulate coin flip economics and help the team understand the results. The entire experience should live on a single scrollable page with clear visual sections. No sidebar navigation. No page switching.

Design principles for this redesign:

1. **Linear workflow, not a dashboard.** The page reads top-to-bottom like a document: setup at the top, results below, AI at the bottom.
2. **Progressive disclosure.** Show only what matters at each stage. Before a simulation runs, the results section is collapsed. Before data is uploaded, config is disabled.
3. **Context always visible.** KPI summary and config summary should be glanceable from anywhere on the page.
4. **AI is secondary to data.** The charts and KPIs are the primary output. AI features augment analysis -- they do not replace it.
5. **History is background.** Comparing past runs is a less frequent action. It should not compete with the current simulation.

---

## 3. Layout Architecture

### 3.1 Wireframe -- Full Page (Post-Simulation State)

```
+============================================================================+
|  HEADER BAR                                                                |
|  Coin Flip Simulator            [Last run: 2 min ago]  [History (drawer)]  |
+============================================================================+
|                                                                            |
|  +-- SETUP SECTION (collapsible after first run) ----------------------+   |
|  |                                                                     |   |
|  |  +--- Upload Area ----+  +--- Config Summary -----+                 |   |
|  |  | Player CSV          |  | Max Successes: 5       |                 |   |
|  |  | [file_upload]       |  | Churn Boost: 1.3x      |                 |   |
|  |  | 100,000 rows loaded |  | Threshold: 50,000      |                 |   |
|  |  +--------------------+  | [Edit Config...]        |                 |   |
|  |                          +------------------------+                 |   |
|  |  Config CSV: [file_upload]                                          |   |
|  |                                                                     |   |
|  |  +-- Run Controls -----------------------------------------------+  |   |
|  |  | Seed: [_______]   [>>> Run Simulation]           Ready: YES   |  |   |
|  |  +---------------------------------------------------------------+  |   |
|  +---------------------------------------------------------------------+   |
|                                                                            |
|  +-- KPI BAR (sticky/prominent) ------------------------------------+      |
|  |  Mean Pts    Median Pts    Total Pts    % Above Threshold        |      |
|  |  12,345      8,901         1.2B         4.7%                     |      |
|  +------------------------------------------------------------------+      |
|                                                                            |
|  +-- RESULTS SECTION -----------------------------------------------+      |
|  |                                                                   |      |
|  |  [Charts]  [Churn Analysis]  [Data Table]         <-- sub-tabs    |      |
|  |                                                                   |      |
|  |  +-- Charts Tab (default) -----------------------------------+    |      |
|  |  |                                                           |    |      |
|  |  |  Success Depth Distribution          Points Distribution  |    |      |
|  |  |  +--- bar chart --------+   +--- histogram ---------+    |    |      |
|  |  |  |                      |   |                        |    |    |      |
|  |  |  |                      |   |                        |    |    |      |
|  |  |  +----------------------+   +------------------------+    |    |      |
|  |  |                                                           |    |      |
|  |  +-----------------------------------------------------------+    |      |
|  |                                                                   |      |
|  |  +-- Churn Analysis Tab -----------------------------------------+|      |
|  |  |  [side-by-side churn vs non-churn metrics + overlaid chart]   ||      |
|  |  +---------------------------------------------------------------+|      |
|  |                                                                   |      |
|  |  +-- Data Table Tab ---------------------------------------------+|      |
|  |  |  [full player results dataframe + CSV download button]        ||      |
|  |  +---------------------------------------------------------------+|      |
|  +-------------------------------------------------------------------+      |
|                                                                            |
|  +-- AI SECTION --------------------------------------------------------+  |
|  |                                                                       |  |
|  |  [Insights]  [Ask a Question]  [Optimizer]            <-- sub-tabs    |  |
|  |                                                                       |  |
|  |  +-- Insights Tab (default) ---+  +-- Status Sidebar ---+            |  |
|  |  | [Generate Insights]          |  | 3 insights found    |            |  |
|  |  |                              |  | 1 critical          |            |  |
|  |  | CRITICAL: 12% of players...  |  | 1 warning           |            |  |
|  |  | WARNING: Churn boost...      |  | 1 info              |            |  |
|  |  | INFO: Distribution is...     |  +---------------------+            |  |
|  |  +------------------------------+                                     |  |
|  |                                                                       |  |
|  |  +-- Ask a Question Tab ----------------------------------------+     |  |
|  |  | [chat interface with st.chat_message]                        |     |  |
|  |  | User: What % of churners hit max flips?                      |     |  |
|  |  | AI: Based on the simulation, 8.3% of about-to-churn...       |     |  |
|  |  | [chat input box]                                             |     |  |
|  |  +--------------------------------------------------------------+     |  |
|  |                                                                       |  |
|  |  +-- Optimizer Tab ----------------------------------------------+    |  |
|  |  | Target metric: [pct_above_threshold v]                        |    |  |
|  |  | Target value:  [5.0    ]                                      |    |  |
|  |  | Direction:     [Target v]                                     |    |  |
|  |  | Max iterations:[10     ]                                      |    |  |
|  |  | [>>> Run Optimizer]                                           |    |  |
|  |  |                                                               |    |  |
|  |  | Iteration Log:                                                |    |  |
|  |  | #1: 4.7% (distance: 0.3) | #2: 4.9% (distance: 0.1) | ...   |    |  |
|  |  | Best config found: [Apply to Current Config]                  |    |  |
|  |  +---------------------------------------------------------------+    |  |
|  +-----------------------------------------------------------------------+  |
|                                                                            |
|  +-- FOOTER (subtle) ---------------------------------------------------+  |
|  |  [Download Results CSV]   Last saved: 2026-03-20 14:32                |  |
|  +----------------------------------------------------------------------+  |
+============================================================================+

HISTORY DRAWER (slides in from right when [History] is clicked):
+==================================+
|  History                    [X]  |
|  --------------------------------|
|  Filter: [All v]                 |
|  --------------------------------|
|  Run 1: Mar 20, 14:32           |
|  coin_flip | 1.2B pts           |
|  [Load] [Compare]               |
|  --------------------------------|
|  Run 2: Mar 20, 11:15           |
|  coin_flip | 980M pts           |
|  [Load] [Compare]               |
|  --------------------------------|
|  Run 3: Mar 19, 16:44           |
|  coin_flip | 1.1B pts           |
|  [Load] [Compare]               |
|  --------------------------------|
|  Compare Mode:                   |
|  Run A: [Run 1 v]               |
|  Run B: [Run 2 v]               |
|  [>>> Compare Side-by-Side]     |
|  --------------------------------|
|  [Manage / Delete Runs]         |
+==================================+
```

### 3.2 Wireframe -- Empty State (First Load)

```
+============================================================================+
|  HEADER BAR                                                                |
|  Coin Flip Simulator                                   [History (drawer)]  |
+============================================================================+
|                                                                            |
|  +-- SETUP SECTION (expanded, prominent) ---------------------------+      |
|  |                                                                   |      |
|  |  Step 1: Upload Player Data                                       |      |
|  |  +----------------------------------------------------+          |      |
|  |  |  Drag and drop your player CSV here                |          |      |
|  |  |  (user_id, rolls_sink, avg_multiplier,             |          |      |
|  |  |   about_to_churn)                                  |          |      |
|  |  +----------------------------------------------------+          |      |
|  |                                                                   |      |
|  |  Step 2: Upload Config  (disabled/grayed until step 1 complete)   |      |
|  |  +----------------------------------------------------+          |      |
|  |  |  Drag and drop config CSV (Input, Value)           |          |      |
|  |  +----------------------------------------------------+          |      |
|  |                                                                   |      |
|  |  Step 3: Run  (disabled until steps 1+2 complete)                 |      |
|  |  [>>> Run Simulation]  (grayed out)                               |      |
|  +-------------------------------------------------------------------+      |
|                                                                            |
|  +-- PLACEHOLDER (where results will appear) -----------------------+      |
|  |                                                                   |      |
|  |      No simulation results yet.                                   |      |
|  |      Upload data and config above, then run a simulation.         |      |
|  |                                                                   |      |
|  +-------------------------------------------------------------------+      |
+============================================================================+
```

---

## 4. Component Inventory

### 4.1 Header Bar

| Element | Type | Behavior |
|---------|------|----------|
| App title | `st.title` or custom HTML | Static. "Coin Flip Simulator" |
| Last run timestamp | `st.caption` | Shows when the current results were generated. Hidden on first load. |
| History button | `st.button` | Opens the history drawer (implemented as sidebar). Only button in the header area. |

### 4.2 Setup Section

| Element | Type | Behavior |
|---------|------|----------|
| Section container | `st.container` + `st.expander` | Expanded on first load. After a successful simulation run, auto-collapses to a summary line showing "100K players, 5 flip depths, threshold 50K". User can re-expand to change inputs. |
| Player CSV upload | `st.file_uploader` | Accepts .csv. On upload: validates columns, shows row count + preview (5 rows). Stores in session state. |
| Player data summary | `st.metric` + `st.dataframe` | Shows row count. Preview in collapsed expander. |
| Config CSV upload | `st.file_uploader` | Accepts .csv. Parses Input/Value format. Populates the config editor. |
| Config summary | Inline metrics | Shows max_successes, churn_boost, threshold at a glance. |
| Config editor toggle | `st.expander` labeled "Edit Config" | Opens the full parameter editor (sliders for probabilities, number inputs for points). Only visible after config CSV is uploaded. |
| Config editor | `render_config_editor` (existing component) | Full editable form. Lives inside an expander so it does not dominate the page. |
| Seed input | `st.number_input` | Optional. Compact, on the same row as the Run button. |
| Run button | `st.button(type="primary")` | Prominent. Disabled until both data and config are loaded. Full width within its container. |
| Readiness indicator | Inline text/icon | Simple "Ready" / "Missing data" / "Missing config" status next to the run button. Not a separate section. |

### 4.3 KPI Bar

| Element | Type | Behavior |
|---------|------|----------|
| KPI cards row | `st.columns(4)` + `st.metric` | 4 metrics in a row: Mean Points/Player, Median Points/Player, Total Points, % Above Threshold. |
| Visual treatment | Container with border | Subtle background differentiation to make it scan as a dashboard summary bar. Use `st.container(border=True)`. |
| Visibility | Conditional | Only visible after simulation has run. |

### 4.4 Results Section

| Element | Type | Behavior |
|---------|------|----------|
| Section header | `st.subheader` | "Results" |
| Sub-tabs | `st.tabs(["Charts", "Churn Analysis", "Data Table"])` | Three tabs within the results section. |

**Charts tab (default):**

| Element | Type | Behavior |
|---------|------|----------|
| Success depth distribution | `render_distribution_chart` (existing) | Bar chart. Full width or left half of a two-column layout. |
| Points distribution histogram | Altair histogram (existing) | Histogram with 30 bins. Right half or below the depth chart. |
| Layout | `st.columns(2)` | Side-by-side on wide screens. Both charts use `use_container_width=True`. |

**Churn Analysis tab:**

| Element | Type | Behavior |
|---------|------|----------|
| Churn vs non-churn metrics | `st.columns(2)` with `st.metric` | Side-by-side comparison: player count, avg points, median points, total points for each segment. |
| Overlaid distribution | Altair layered chart | Two-color bar chart comparing churn vs non-churn success distributions. |

**Data Table tab:**

| Element | Type | Behavior |
|---------|------|----------|
| Download CSV button | `st.download_button` | Top of tab. Downloads full player results. |
| Full dataframe | `st.dataframe` | Scrollable, full width. All player rows with results. |
| Row count caption | `st.caption` | "Showing 100,000 player rows" |

### 4.5 AI Section

| Element | Type | Behavior |
|---------|------|----------|
| Section header | `st.subheader` | "AI Analysis" |
| Sub-tabs | `st.tabs(["Insights", "Ask a Question", "Optimizer"])` | Three AI features as peer tabs. |
| Prerequisite guard | Conditional rendering | Entire section shows "Run a simulation first" placeholder when no results exist. |
| API key guard | `st.error` | Shown at top of AI section if ANTHROPIC_API_KEY is missing and provider is anthropic. |

**Insights tab:**

| Element | Type | Behavior |
|---------|------|----------|
| Generate button | `st.button(type="primary")` | "Generate Insights" / "Regenerate Insights" depending on state. |
| Insight cards | Custom component (existing `_render_insight_card`) | Severity badge + finding + recommendation + expandable metrics. Rendered in a scrollable container. |
| Insight count summary | `st.caption` | "3 insights: 1 critical, 1 warning, 1 info" |

**Ask a Question tab:**

| Element | Type | Behavior |
|---------|------|----------|
| Chat history | `st.chat_message` | Scrollable list of user/assistant message pairs. Context-aware: knows the current simulation results, config, and KPIs. |
| Chat input | `st.chat_input` | Fixed at bottom of the tab. Placeholder: "Ask about the simulation results..." |
| Context indicator | `st.caption` | "AI has context of your current simulation (100K players, config v3)" |

**Optimizer tab:**

| Element | Type | Behavior |
|---------|------|----------|
| Target metric selector | `st.selectbox` | Options: pct_above_threshold, mean_points_per_player, total_points. |
| Target value | `st.number_input` | The desired target value. |
| Direction | `st.selectbox` | Maximize / Minimize / Target. |
| Max iterations | `st.number_input` | Default 10, range 1-20. |
| Run Optimizer button | `st.button(type="primary")` | Triggers the optimization loop. |
| Iteration log | `st.dataframe` or custom rendering | Table showing iteration #, metric value, distance to target. Updates progressively if possible (Streamlit limitation: may need to show all at once). |
| Best config result | `st.json` or formatted display | Shows the best config found. |
| Apply button | `st.button` | "Apply Best Config" -- writes the optimized config back to session state and scrolls user to the setup section to re-run. |
| Convergence status | `st.success` / `st.warning` | "Converged at iteration 7" or "Did not converge within 10 iterations. Best result: 4.9%." |

### 4.6 History Drawer

The history feature moves from a separate page into the **Streamlit sidebar**, repurposed as a slide-out drawer. The sidebar is collapsed by default and only opens when the user clicks "History."

| Element | Type | Behavior |
|---------|------|----------|
| Drawer trigger | `st.button` in header | Toggles sidebar open/closed via `st.session_state`. |
| Run list | `st.container(border=True)` per run | Compact cards: timestamp, total points, interaction count. |
| Load button | `st.button` per run | Loads that run's config + results into session state, replacing current state. Closes drawer. |
| Compare selector | Two `st.selectbox` | Select Run A and Run B for comparison. |
| Compare button | `st.button(type="primary")` | Opens comparison view in the main content area (replaces results section temporarily). |
| Delete management | `st.expander("Manage")` | Multi-select + delete, tucked away in an expander at the bottom. |
| Filter | `st.selectbox` | Filter by feature (future-proofing, though currently only coin_flip). |

### 4.7 Footer

| Element | Type | Behavior |
|---------|------|----------|
| Download CSV | `st.download_button` | Redundant shortcut for downloading results. |
| Last saved timestamp | `st.caption` | When results were auto-saved to history. |

---

## 5. User Flow

### 5.1 Primary Flow: First Simulation

```
Page loads
  |
  v
Setup Section is expanded, Results/AI sections show empty placeholders
  |
  v
User uploads player CSV --> validation runs --> row count shown
  |
  v
User uploads config CSV --> parsed --> config summary appears, editor populated
  |
  v
(Optional) User clicks "Edit Config" expander --> tweaks probabilities/points
  |
  v
Run button becomes enabled (green, prominent)
  |
  v
User clicks "Run Simulation"
  |
  v
Spinner appears on the button area (1-3 seconds)
  |
  v
Results populate:
  - KPI bar appears with 4 metrics
  - Setup section auto-collapses to summary
  - Charts tab shows distributions
  - AI section becomes active
  - Run is auto-saved to history
  |
  v
User scrolls down to review charts, clicks through tabs
  |
  v
User clicks "AI Analysis" > "Generate Insights"
  |
  v
3-5 insight cards appear with severity badges
  |
  v
User clicks "Ask a Question" tab, types a natural language question
  |
  v
AI responds with data-grounded answer
  |
  v
(Optional) User clicks "Optimizer" tab, sets target, runs optimization
  |
  v
Optimizer shows iteration history, user clicks "Apply Best Config"
  |
  v
Config updates in session state, setup section expands, user re-runs
```

### 5.2 Returning User Flow

```
Page loads
  |
  v
Session state is empty (browser was refreshed)
  |
  v
User clicks "History" in header
  |
  v
Sidebar opens with list of past runs
  |
  v
User clicks "Load" on the most recent run
  |
  v
Config and result summary load into session state
  |
  v
Page populates with that run's KPIs and config
User still needs to re-upload player CSV to re-run (CSV data is not persisted)
  |
  v
User uploads CSV, clicks "Run Simulation" with the loaded config
```

### 5.3 Comparison Flow

```
User clicks "History" in header
  |
  v
Sidebar opens with run list
  |
  v
User selects Run A and Run B from dropdowns
  |
  v
Clicks "Compare Side-by-Side"
  |
  v
Main content area shows comparison view:
  - KPI metrics with delta indicators
  - Overlaid distribution chart
  - Config diff table
  |
  v
User clicks "Back to Current" button to return to normal results view
```

---

## 6. State Management

### 6.1 Session State Keys

| Key | Type | Set By | Cleared By |
|-----|------|--------|------------|
| `player_data` | `pl.DataFrame` | Player CSV upload | New upload, page refresh |
| `config_dict` | `dict[str, Any]` | Config CSV upload or editor | New upload, optimizer apply |
| `config` | `CoinFlipConfig` | Config validation | Config edit that fails validation |
| `simulation_result` | `CoinFlipResult` | Successful simulation run | New simulation run |
| `ai_insights` | `list[Insight]` | AI insights generation | New simulation run (stale data) |
| `chat_history` | `list[dict]` | Chat interactions | New simulation run (stale context) |
| `optimizer_steps` | `list[OptimizationStep]` | Optimizer run | New optimizer run |
| `optimizer_best_config` | `dict` | Optimizer completion | New optimizer run |
| `setup_collapsed` | `bool` | Successful simulation | User manually expands |
| `comparison_mode` | `bool` | Compare button in history | "Back to Current" button |
| `comparison_runs` | `tuple[dict, dict]` | Compare button | Exiting comparison mode |

### 6.2 Persistence Strategy

| Data | Storage | Survives Refresh? |
|------|---------|-------------------|
| Player CSV | Session state only | No. User must re-upload. This is intentional -- CSVs can be large and change between sessions. |
| Config | Session state + saved with each run in LocalSimulationStore | Config survives via history "Load" action. |
| Simulation results (summary) | LocalSimulationStore (JSON on disk) | Yes, via history. Full player-level results do not persist (too large). |
| AI insights | Session state only | No. Must regenerate. Fast enough that this is acceptable. |
| Chat history | Session state only | No. Conversations are ephemeral by design. |
| Run history | LocalSimulationStore (disk) | Yes. Survives refresh, restart, reboot. |

### 6.3 Stale Data Handling

When the user runs a new simulation:
- `ai_insights` is cleared (they apply to the old results).
- `chat_history` is cleared (context changed).
- `optimizer_steps` is cleared.
- A toast/info message appears: "Previous AI insights cleared. Generate new insights for updated results."

When the user edits config after a simulation:
- Results remain visible but a warning banner appears: "Config has changed since last run. Re-run to update results."
- AI section shows the same warning.

---

## 7. AI Features Placement -- Rationale

### Why AI lives below results, not beside them:

1. **Reading order.** Users need to see the raw numbers before AI analysis. Placing AI above results would invert the trust hierarchy -- you should form your own impression before reading the AI's.

2. **Frequency of use.** KPIs and charts are checked on every single run. AI insights are generated selectively. Placing AI lower respects this usage pattern.

3. **Screen real estate.** Charts need full width. AI insights are text-heavy and work well in a narrower, full-width column below.

### Why three AI features are tabs, not separate sections:

1. **They share the same prerequisite** (simulation results must exist).
2. **They share the same mental context** ("I'm now analyzing these results with AI help").
3. **Users will rarely use all three in one session.** Tabs let them pick without scrolling past features they do not need.

### Why Insights is the default AI tab:

Insights is one-click, passive analysis. It has the lowest barrier. Chat and Optimizer require the user to formulate a question or target, which is a higher-effort action. Default to the easiest entry point.

### Why Chat uses st.chat_message:

Streamlit's chat components provide the familiar message-bubble pattern. The chat is contextual -- the AI has the simulation results, config, and KPIs in its system prompt. This is not a general chatbot; it is a simulation results analyst.

---

## 8. Responsive Behavior

Streamlit has limited responsive control, but we can optimize within its constraints.

### Wide screen (1200px+):

- Charts in Results section render side-by-side in `st.columns(2)`.
- KPI bar uses 4 columns.
- Churn comparison uses 2 columns.
- Config summary and upload area use `st.columns([1, 1])`.

### Medium screen (768px-1200px):

- Charts stack vertically (single column).
- KPI bar stays as 4 columns (Streamlit handles wrapping).
- Everything else flows naturally since Streamlit uses full-width containers.

### Narrow screen (<768px):

- All content stacks vertically.
- KPI bar wraps to 2 columns (render in two rows of 2).
- Sidebar (history drawer) takes full screen width when open.
- This is an internal tool used on desktop -- narrow screen is a secondary concern.

### Streamlit-specific notes:

- Use `layout="wide"` in page config (already set).
- Set `initial_sidebar_state="collapsed"` -- sidebar is the history drawer, hidden by default.
- All charts use `use_container_width=True`.
- All dataframes use `use_container_width=True`.

---

## 9. Visual Design Tokens

These are not custom CSS -- they are choices that can be expressed through Streamlit's native components and Altair chart configuration.

### Colors

| Purpose | Value | Usage |
|---------|-------|-------|
| Primary brand / chart bars | `#FF6B35` (warm orange) | Distribution charts, primary actions |
| Churn segment | `#E63946` (red) | Churn player data |
| Non-churn segment | `#457B9D` (steel blue) | Non-churn player data |
| Comparison Run A | `#FF6B35` | First run in comparison |
| Comparison Run B | `#457B9D` | Second run in comparison |
| Severity: Critical | `#E53935` | Insight badges |
| Severity: Warning | `#FB8C00` | Insight badges |
| Severity: Info | `#1E88E5` | Insight badges |

### Typography

Streamlit controls typography. We use its built-in hierarchy:
- `st.title` -- page title (1 instance)
- `st.subheader` -- section headers (Setup, Results, AI Analysis)
- `st.markdown("####")` -- sub-section headers within tabs
- `st.caption` -- metadata, timestamps, counts
- `st.metric` -- KPI values (uses Streamlit's large-number formatting)

### Spacing

Streamlit handles spacing automatically. Our layout choices:
- Horizontal rules (`st.markdown("---")`) between major sections REMOVED. Use `st.container(border=True)` for visual separation instead.
- Each major section (Setup, KPI Bar, Results, AI) wrapped in `st.container(border=True)`.
- Expanders for secondary content (data previews, config editor, raw data).

---

## 10. Interaction Details

### 10.1 The Run Button

The Run button is the most important interaction on the page. Design choices:

- **Always visible** within the setup section, even when collapsed (the collapsed summary row includes a "Re-run" button).
- **Type "primary"** (Streamlit's colored button style).
- **Full container width** within its column.
- **Disabled state:** grayed out with tooltip-like text explaining what is missing ("Upload player data to enable").
- **Loading state:** `st.spinner` wraps the simulation execution.
- **Success state:** green success message with summary stats, then auto-scroll to results.

### 10.2 The Setup Section Collapse

After the first successful simulation:
- The setup section auto-collapses to a single-line summary.
- Summary format: `100,000 players | 5 flip depths | Threshold: 50,000 | Churn boost: 1.3x`
- An "Expand" affordance (expander arrow or "Edit Setup" button) lets the user re-open it.
- Expanding does NOT clear existing results.

Implementation: Use `st.expander("Setup: 100K players, 5 depths, threshold 50K", expanded=not has_results)`.

### 10.3 History Drawer

Streamlit does not have a native drawer component. We repurpose the sidebar:

- `initial_sidebar_state="collapsed"` on page load.
- The "History" button in the header sets `st.session_state["show_history"] = True` and triggers `st.rerun()`.
- The sidebar checks this state and renders history content.
- Sidebar title is "History" (not "Economy Simulator").
- The sidebar "X" (native Streamlit collapse) closes the drawer.

### 10.4 Config Editor UX

Current: The config editor renders all parameters as a flat list of sliders/inputs. This works but is verbose.

Improvement: Group parameters logically:

```
Edit Config
  +-- Flip Probabilities (collapsible group)
  |   p_success_1: [====60%====]
  |   p_success_2: [===50%===]
  |   p_success_3: [==40%==]
  |   p_success_4: [=30%=]
  |   p_success_5: [20%]
  |
  +-- Point Values (collapsible group)
  |   points_success_1: [100  ]
  |   points_success_2: [250  ]
  |   points_success_3: [500  ]
  |   points_success_4: [1000 ]
  |   points_success_5: [5000 ]
  |
  +-- Thresholds & Multipliers (collapsible group)
      max_successes:     [5   ]
      reward_threshold:  [50000]
      churn_boost_mult:  [1.3 ]
```

This requires modifying `render_config_editor` to accept a grouping schema, or building the grouping in the page layout by calling the editor per group.

### 10.5 Optimizer "Apply Best Config"

When the user clicks "Apply Best Config" in the optimizer:
1. The optimized config dict replaces `st.session_state["config_dict"]` and `st.session_state["config"]`.
2. The setup section expander label updates to reflect the new config.
3. A success toast appears: "Optimized config applied. Click 'Run Simulation' to see results."
4. The setup section auto-expands so the user can see the new values and hit Run.
5. Previous simulation results are NOT cleared -- they stay as a reference until the user re-runs.

---

## 11. Edge Cases

| Scenario | Behavior |
|----------|----------|
| User uploads new player CSV after simulation | Warning: "Player data changed. Re-run simulation to update results." Results remain visible but marked stale. |
| User uploads config CSV that fails validation | Error message in the config area. Run button remains disabled. Previous valid config is NOT overwritten. |
| Simulation fails (engine error) | Error message in the setup section. Results section is not affected (keeps previous results if any). |
| AI generation fails (API error) | Error message within the AI section only. Does not affect results or other tabs. |
| User tries to generate insights with no results | The entire AI section shows a single info message: "Run a simulation first to enable AI analysis." |
| Very large dataset (1M rows) | Upload widget shows row count immediately. Preview limited to 5 rows. Simulation runs with spinner. No special handling needed -- engine is vectorized. |
| History has 50+ runs | List is capped at 50 (most recent). Pagination is not needed for an internal tool with 5-10 users. |
| Browser refresh mid-simulation | Simulation is lost (Streamlit limitation). User must re-upload and re-run. This is acceptable -- simulations take 2 seconds. |
| Two users running simultaneously | LocalSimulationStore uses file-based storage per run_id (UUID). No conflicts. Session state is per-browser-session. |

---

## 12. What We Are NOT Building

Decisions on what to explicitly exclude:

1. **Multi-page navigation.** The app is one page. No sidebar nav links.
2. **Persistent CSV storage.** Player data is not saved to disk. Too large, changes often.
3. **User accounts or authentication.** Internal tool for 5-10 people. No login.
4. **Real-time collaboration.** Each user sees their own session.
5. **Custom CSS/themes.** Streamlit's default theme is sufficient. No custom styling beyond what Altair chart config provides.
6. **Notification system.** No alerts, no email, no Slack integration.
7. **Export to PDF/PowerPoint.** CSV download is sufficient. If needed, users screenshot.
8. **Undo/redo.** Config changes are immediate. History provides the "go back" mechanism.
9. **Dark mode toggle.** Streamlit follows system preference. We do not add a manual toggle.
10. **Mobile optimization.** This is a desktop tool. Mobile works (Streamlit is responsive) but is not optimized for.

---

## 13. Implementation Priority

The redesign can be implemented incrementally. Suggested order:

### Phase 1: Single-Page Consolidation (Day 1-2)
- Merge the three pages (Coin Flip, AI Insights, History) into a single page.
- Establish the Setup > KPI Bar > Results > AI vertical flow.
- Move history into the sidebar drawer.
- Remove multi-page navigation from `app.py`.
- All existing components are reused, just relocated.

### Phase 2: Progressive Disclosure (Day 2-3)
- Implement the collapsible setup section with summary line.
- Add the KPI bar as a distinct visual container.
- Implement the Results sub-tabs (Charts, Churn Analysis, Data Table).
- Implement the AI sub-tabs (Insights, Ask a Question, Optimizer).

### Phase 3: AI Chat + Optimizer UI (Day 3-4)
- Build the chat interface in the "Ask a Question" tab (new component).
- Build the optimizer UI in the "Optimizer" tab (new component, wiring to existing `ConfigOptimizer`).
- Implement the "Apply Best Config" flow.

### Phase 4: Polish (Day 4-5)
- Stale data warnings.
- Config editor grouping.
- History drawer UX (load, compare flows).
- Empty states for all sections.
- Edge case handling.

---

## 14. Success Criteria

The redesign is successful when:

1. The economy team can go from "open app" to "see simulation results" in under 60 seconds (upload + run).
2. No one asks "where do I find X?" -- every feature is discoverable from the main page.
3. The sidebar is only used for history, not for navigation or settings.
4. AI features feel like natural extensions of the analysis, not separate tools.
5. A returning user can load a past config and re-run in under 30 seconds.
6. The page does not feel cluttered despite containing all features -- progressive disclosure keeps it clean.

---

## 15. Open Questions

1. **Should config presets be supported?** e.g., "Conservative", "Aggressive", "Balanced" quick-select buttons above the config editor. Low effort, potentially high value for the team. Decision deferred.
2. **Should the chat context include ALL past runs or just the current one?** Current design: only current simulation. Including history would require more prompt engineering.
3. **Should the optimizer run the simulation silently or show a live progress bar?** Streamlit's `st.progress` could work for the iteration loop, but the simulation itself is fast (~2s). The LLM calls dominate. Decision: show iteration count as it progresses.
4. **Should comparison mode replace the main content area or open in a modal?** Current design says replace. A modal (using `st.dialog`) could work but Streamlit dialogs are limited. Decision: replace main content with a "Back" button.
