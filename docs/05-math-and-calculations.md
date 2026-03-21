# Math & Calculations Reference

Complete reference for every formula, algorithm, and calculation in the simulation engine.

---

## Table of Contents

- [Coin Flip Simulation](#coin-flip-simulation)
  - [1. Interaction Count](#1-interaction-count-per-player)
  - [2. Churn Probability Boost](#2-churn-probability-boost)
  - [3. Random Number Generation](#3-random-number-generation)
  - [4. Success Chain (Consecutive Flips)](#4-success-chain-consecutive-flips)
  - [5. Points Calculation (Cumulative)](#5-points-calculation-cumulative)
  - [6. Points Scaling by Multiplier](#6-points-scaling-by-multiplier)
  - [7. Player Aggregation](#7-player-aggregation-total-points)
  - [8. Success Distribution](#8-success-distribution-histogram)
- [KPI Metrics](#kpi-metrics)
  - [9. Players Above Threshold](#9-players-above-threshold)
  - [10. Mean and Median Points](#10-mean-and-median-points)
  - [11. Percentage Above Threshold](#11-percentage-above-threshold)
- [Churn Segment Analysis](#churn-segment-analysis)
- [Parameter Sweep](#parameter-sweep)
- [AI Config Optimizer](#ai-config-optimizer)
  - [Convergence Check](#convergence-check)
  - [Guardrails](#guardrails-clipping)
- [Data Normalization](#data-normalization)
- [Default Config Values](#default-config-values)
- [Vectorization Strategy](#vectorization-strategy)

---

## Coin Flip Simulation

Source: `src/domain/simulators/coin_flip.py`

### 1. Interaction Count (Per Player)

Each player's number of coin-flip sequences is determined by how many rolls they've spent, divided by their multiplier.

**Formula:**

```
interactions = floor(rolls_sink / avg_multiplier)
```

**Example:** A player with `rolls_sink = 500` and `avg_multiplier = 10` gets `floor(500 / 10) = 50` interactions.

**Code:**
```python
players.with_columns(
    (pl.col("rolls_sink") // pl.col("avg_multiplier")).cast(pl.Int64).alias("interactions")
)
```

**Notes:**
- Uses integer floor division (`//`)
- `avg_multiplier` must be > 0 (validated before simulation)

---

### 2. Churn Probability Boost

Players flagged as `about_to_churn = true` get boosted success probabilities to keep them engaged.

**Formula:**

```
boosted_probability = min(p_success × churn_boost_multiplier, 1.0)
```

**Example with default config (churn_boost = 1.3):**

| Flip | Normal | Churn-Boosted |
|------|--------|---------------|
| 1    | 60%    | 78% (60% × 1.3) |
| 2    | 50%    | 65% (50% × 1.3) |
| 3    | 50%    | 65% (50% × 1.3) |
| 4    | 50%    | 65% (50% × 1.3) |
| 5    | 50%    | 65% (50% × 1.3) |

**Cap:** A probability of 90% boosted by 1.3x becomes `min(1.17, 1.0) = 100%`, not 117%.

**Code (vectorized):**
```python
prob_matrix = np.where(
    flat_churn[:, np.newaxis],      # Boolean mask: is this player churning?
    boosted_probs[np.newaxis, :],   # Yes → use boosted probabilities
    normal_probs[np.newaxis, :],    # No → use normal probabilities
)
```

---

### 3. Random Number Generation

All random values for the entire simulation are generated in a single NumPy call.

**Formula:**

```
random_matrix = rng.random(shape=(total_interactions, max_successes))
```

**Example:** For 100,000 interactions with 5 max flips → one call generates a 100,000 × 5 matrix of values in [0, 1).

**Code:**
```python
rng = np.random.default_rng(seed)
random_values = rng.random((total_interactions, max_successes))
```

**Notes:**
- Deterministic when `seed` is provided (reproducible results)
- Single allocation — no per-player or per-flip loops

---

### 4. Success Chain (Consecutive Flips)

A flip is "heads" if its random value is less than the probability. The chain stops at the first "tails."

**Formula:**

```
success[i] = 1 if random_value[i] < probability[i], else 0

depth = number of consecutive successes from flip 1
      = sum of cumulative product of success flags
```

**Step-by-step example:**

| Flip | Random | Probability | Success? | Cumulative Product |
|------|--------|-------------|----------|--------------------|
| 1    | 0.35   | 0.60        | 1 (heads) | 1                 |
| 2    | 0.42   | 0.50        | 1 (heads) | 1                 |
| 3    | 0.73   | 0.50        | 0 (tails) | 0                 |
| 4    | 0.21   | 0.50        | —         | 0                 |
| 5    | 0.88   | 0.50        | —         | 0                 |

**Depth = sum([1, 1, 0, 0, 0]) = 2** (even though flip 4 would have been heads, the chain already ended)

**Code:**
```python
success_matrix = random_values < prob_matrix                    # Boolean matrix
cum_successes = np.cumprod(success_matrix.astype(np.int8), axis=1)  # Zeros after first failure
success_depth = cum_successes.sum(axis=1)                       # Count consecutive successes
```

**Why `cumprod` works:** Multiplying [1, 1, 0, 1, 1] cumulatively gives [1, 1, 0, 0, 0] — once a 0 appears, everything after stays 0.

---

### 5. Points Calculation (Cumulative)

Points are **accumulated** across all successful flips. A player who reaches depth 3 earns points from flip 1 + flip 2 + flip 3.

**Formula:**

```
cumulative_points = cumsum(point_values)
points_at_depth = cumulative_points[depth]
points_at_depth_0 = 0 (no successes = no points)
```

**Example with default config:**

| Depth | Points per Flip | Cumulative Points |
|-------|----------------|-------------------|
| 0     | —              | 0                 |
| 1     | 1              | 1                 |
| 2     | 2              | 1 + 2 = 3        |
| 3     | 4              | 1 + 2 + 4 = 7    |
| 4     | 8              | 1 + 2 + 4 + 8 = 15 |
| 5     | 16             | 1 + 2 + 4 + 8 + 16 = 31 |

**Code:**
```python
cum_points = np.cumsum(config.point_values)          # [1, 3, 7, 15, 31]
points_lookup = np.zeros(max_successes + 1)          # [0, 1, 3, 7, 15, 31]
points_lookup[1:] = cum_points
interaction_points = points_lookup[success_depth]    # Vectorized lookup by depth
```

---

### 6. Points Scaling by Multiplier

Each interaction's points are multiplied by the player's `avg_multiplier`.

**Formula:**

```
scaled_points = cumulative_points_at_depth × avg_multiplier
```

**Example:** A player with `avg_multiplier = 10` who reaches depth 3 earns `7 × 10 = 70` points for that interaction.

**Code:**
```python
interaction_points_scaled = interaction_points * flat_multipliers
```

---

### 7. Player Aggregation (Total Points)

After computing scaled points for every interaction, results are grouped back to the player level.

**Formula:**

```
total_points_player = sum of scaled_points across all interactions for that player
```

**Example:** A player with 50 interactions, each earning between 0 and 310 points, gets the sum of all 50 results.

**Code:**
```python
interaction_df = pl.DataFrame({
    "player_idx": player_indices,
    "points": interaction_points_scaled,
})
agg_df = interaction_df.group_by("player_idx").agg(
    pl.col("points").sum().alias("total_points"),
    pl.col("points").count().alias("num_interactions"),
)
```

---

### 8. Success Distribution (Histogram)

Counts how many interactions ended at each depth (0 through max_successes).

**Formula:**

```
count_at_depth_d = number of interactions where success_depth == d
```

**Code:**
```python
counts = np.bincount(success_depth.astype(int), minlength=max_successes + 1)
success_counts = {depth: int(counts[depth]) for depth in range(max_successes + 1)}
```

**Example output:** `{0: 400000, 1: 240000, 2: 120000, 3: 60000, 4: 30000, 5: 15000}`

---

## KPI Metrics

Source: `src/domain/models/coin_flip.py`

### 9. Players Above Threshold

**Formula:**

```
players_above_threshold = count of players where total_points > reward_threshold
```

**Note:** Uses **strict greater-than** (`>`), not greater-than-or-equal.

**Code:**
```python
players_above = int(
    player_results.filter(pl.col("total_points") > config.reward_threshold).height
)
```

---

### 10. Mean and Median Points

**Formulas:**

```
mean  = sum(all player total_points) / number_of_players
median = middle value when all total_points are sorted
```

**Why both matter:** The coin flip produces a heavily right-skewed distribution. Most players earn little (median is low), but a few lucky players earn a lot (pulling the mean up). A large gap between mean and median signals inequality.

---

### 11. Percentage Above Threshold

**Formula:**

```
pct_above = players_above_threshold / total_players
```

**Code:**
```python
"pct_above_threshold": float(self.players_above_threshold) / float(len(self.player_results))
```

---

## Churn Segment Analysis

Source: `src/domain/models/coin_flip.py`

The simulation produces separate KPIs for churning vs non-churning players, enabling side-by-side comparison.

**Formulas (per segment):**

```
segment_mean   = mean(total_points) for players in segment
segment_median = median(total_points) for players in segment
segment_count  = number of players in segment
```

**Code:**
```python
churn_df = self.player_results.filter(pl.col("about_to_churn") == True)
non_churn_df = self.player_results.filter(pl.col("about_to_churn") == False)
```

---

## Parameter Sweep

Source: `src/application/parameter_sweep.py`

Runs N simulations, each with a different value for one parameter, to see how that parameter affects KPIs.

### Sweep Values Generation

**Formula:**

```
for i in range(steps):
    value = start + (end - start) × i / (steps - 1)
```

**Example:** Sweeping `p_success_1` from 0.3 to 0.7 in 5 steps → `[0.3, 0.4, 0.5, 0.6, 0.7]`

### Parameter Override

Parameters can be scalar or indexed into a list:

```
"reward_threshold"   → scalar override (config["reward_threshold"] = value)
"probabilities.2"    → list index override (config["probabilities"][2] = value)
"point_values.0"     → list index override (config["point_values"][0] = value)
```

### Seed Stability

Each sweep point gets a unique seed to avoid correlation:

```
point_seed = base_seed + step_index
```

---

## AI Config Optimizer

Source: `src/application/optimize_config.py`

Iteratively adjusts config parameters to hit a target KPI value.

### Convergence Check

Three optimization modes with different convergence criteria:

**Target mode** (hit a specific value):
```
if target_value == 0:
    converged = |current_value| <= tolerance
else:
    converged = |current_value - target_value| / |target_value| <= tolerance
```

**Maximize mode** (push a KPI up):
```
converged = current_value >= target_value
```

**Minimize mode** (push a KPI down):
```
converged = current_value <= target_value
```

**Default tolerance:** 0.05 (5% relative error)

### Distance Tracking

Tracks the best config seen across all iterations:

```
distance = |current_value - target_value|

if distance < best_distance:
    best_config = current_config
    best_distance = distance
```

### Guardrails (Clipping)

After the AI suggests a new config, guardrails prevent invalid values:

| Parameter | Constraint | Rule |
|-----------|-----------|------|
| Probabilities | [0.0, 1.0] | `max(0.0, min(p, 1.0))` |
| Point values | [0.0, +inf) | `max(0.0, v)` |
| max_successes | Immutable | Always restored to original value |

---

## Data Normalization

Source: `src/infrastructure/readers/normalize.py`

The `about_to_churn` column can arrive in different formats. The normalizer handles all of them:

| Input Format | Example | Normalized To |
|-------------|---------|---------------|
| Column missing | — | All `false` |
| Boolean | `true` / `false` | No change |
| String | `"TRUE"` / `"False"` | Case-insensitive → boolean |
| Integer | `1` / `0` | Cast to boolean |

---

## Default Config Values

From `coin-flip-assignment/config_table.csv`:

| Parameter | Value |
|-----------|-------|
| `max_successes` | 5 |
| `p_success_1` | 60% |
| `p_success_2` | 50% |
| `p_success_3` | 50% |
| `p_success_4` | 50% |
| `p_success_5` | 50% |
| `points_success_1` | 1 |
| `points_success_2` | 2 |
| `points_success_3` | 4 |
| `points_success_4` | 8 |
| `points_success_5` | 16 |
| `churn_boost_multiplier` | 1.3 (default) |
| `reward_threshold` | 100.0 (default) |

---

## Vectorization Strategy

The entire simulation runs without a single Python for-loop over data. Here's the pipeline:

```
Step 1: Polars integer division     → interactions per player
Step 2: np.repeat                   → flatten to interaction level
Step 3: rng.random((N, max_flips))  → ALL random numbers at once
Step 4: np.where(churn, boosted, normal) → assign correct probabilities
Step 5: random < probability        → boolean success matrix
Step 6: np.cumprod (axis=1)         → find first failure, zero everything after
Step 7: .sum(axis=1)                → success depth per interaction
Step 8: points_lookup[depth]        → map depth to cumulative points
Step 9: × avg_multiplier            → scale points
Step 10: Polars group_by().agg()    → aggregate back to player level
```

**Performance:** ~1M interactions/second. 100K players in ~2s. Linear scaling.

---

## End-to-End Example

**Player:** `rolls_sink = 1000`, `avg_multiplier = 10`, `about_to_churn = false`

1. **Interactions:** `floor(1000 / 10) = 100` coin-flip sequences
2. **Per interaction (example):**
   - Random values: `[0.35, 0.42, 0.73, 0.21, 0.88]`
   - Probabilities: `[0.60, 0.50, 0.50, 0.50, 0.50]`
   - Success: `[T, T, F, -, -]` → depth = 2
   - Cumulative points at depth 2: `1 + 2 = 3`
   - Scaled: `3 × 10 = 30` points
3. **Total:** Sum of 100 interaction results → player's `total_points`
4. **Threshold check:** `total_points > 100` → counted in `players_above_threshold`

---

*Source files: `src/domain/simulators/coin_flip.py`, `src/domain/models/coin_flip.py`, `src/application/parameter_sweep.py`, `src/application/optimize_config.py`, `src/infrastructure/readers/normalize.py`*
