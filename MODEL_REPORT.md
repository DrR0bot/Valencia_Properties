# Price Prediction Model — Evaluation Report

Phase 3 deliverable. Two **LightGBM** regressors trained to predict log(price) for properties in Valencia Province. Output: `valencia_scored.parquet` with `predicted_price`, `bargain_eur`, `bargain_pct`, `is_bargain`, and `is_overpriced` columns.

## Approach

| Choice | Rationale |
|---|---|
| **LightGBM** | Handles missing values + categoricals natively; strong on tabular data |
| **Two models** (Casa / Piso) | Property types have different price drivers and value ranges |
| **Target = log(price)** | Right-skewed distribution → log makes errors symmetric |
| **80/20 random split** | Standard hold-out evaluation |
| **Early stopping (30 rounds)** | Prevents overfitting; auto-tunes iterations |

## Features used (29 total)

**Numeric (10)**: surface, bedrooms, bathrooms, floor, distance to Valencia, distance to coast, feature count, listing age, latitude, longitude

**Boolean (11)**: has_elevator, has_parking, has_terrace, has_balcony, has_air_conditioning, has_heating, has_storage, is_furnished, is_coastal, price_dropped, is_new_construction

**Categorical (4)**: region, property_subtype, conservation_status, city

> *`has_pool` and `has_garden` were excluded (data quality issue — see INSIGHTS.md). Will be available after re-scrape.*

## Results

| Model | Train | Test | MAE | MAPE | Median APE | R² (log) | Best iter |
|---|---|---|---|---|---|---|---|
| **Casa** | 2,568 | 642 | €103,827 | 27.3% | 19.3% | 0.790 | 178 |
| **Piso** | 4,440 | 1,111 | **€46,060** | **15.0%** | **10.2%** | **0.876** | 550 |

**Interpretation**

- **Pisos**: Half of predictions are within 10% of true price. Strong fit (R²=0.88).
- **Casas**: Higher errors — chalets are uniquely priced based on land, condition, build quality (less captured in our features). Median APE 19% means typical prediction is within ±€40k–€80k of mid-priced casas.

## Top features

### Casa model (top 5 by gain)
1. **bathrooms** — strong signal in chalets (premium ones have 3+ bathrooms)
2. **surface_m2** — bigger = more expensive (linear-ish in casas)
3. **city** — drives 30%+ of price variation
4. **distance_to_valencia_km** — strong negative correlation with price
5. **has_parking** — meaningful for chalets (some don't have it)

### Piso model (top 5 by gain)
1. **city** — dominant: location, location, location
2. **surface_m2** — second-strongest factor
3. **distance_to_valencia_km** — penalty for being far
4. **bathrooms** — premium for 2+ bathroom flats
5. **distance_to_coast_km** — coastal premium captured

## Bargain detection

Threshold: `bargain_pct ≥ 15%` (price ≥ 15% below predicted) → `is_bargain = True`.

| Group | Count |
|---|---|
| **Bargains** (≥15% under predicted) | **667** |
| **Overpriced** (≥15% over predicted) | 808 |
| Fair (within ±15%) | 7,286 |

## Important caveats

⚠️ **Bargains are candidates, not guarantees.** Reasons a "bargain" might be priced low:
- **Genuine deal** ← what we want
- Bad condition, refurbishment needed
- Top-floor walk-up (no elevator), basement, north-facing
- Unresolved legal issues, occupancy
- Unobserved factors (no light, noisy street)
- **Stale listing** the seller didn't update

⚠️ The model is **descriptive, not causal**. SHAP values show "elevator" as positive — but elevators correlate with city flats (already expensive). The pure causal effect of installing an elevator is much smaller.

⚠️ **Test data is from the same time period as training data.** Future prices may shift due to market dynamics. Re-train periodically (Phase 5).

## How to use

```python
import joblib, pandas as pd
from models.price_model import score_dataset

casa_model = joblib.load("models/price_model_casa.pkl")
piso_model = joblib.load("models/price_model_piso.pkl")

df = pd.read_parquet("valencia_clean.parquet")
scored = score_dataset(df, casa_model, piso_model)

bargains = scored[scored["is_bargain"]].sort_values("bargain_pct", ascending=False)
```

Or simpler: `python models/price_model.py --score-only`.

## Files produced

| File | Purpose |
|---|---|
| `models/price_model_casa.pkl` | Trained Casa regressor |
| `models/price_model_piso.pkl` | Trained Piso regressor |
| `models/metrics.json` | Evaluation metrics |
| `models/feature_importance_casa.csv` | Gain-based importance |
| `models/feature_importance_piso.csv` | Gain-based importance |
| `valencia_scored.parquet` | Cleaned dataset + predictions |
| `notebooks/02_model_dev.ipynb` | Interactive analysis with SHAP |
