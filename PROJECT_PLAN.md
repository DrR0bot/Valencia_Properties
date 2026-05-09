# Valencia Properties — Data Analysis Stack

End-to-end pipeline turning raw fotocasa scrapes into an interactive tool to find, analyze, and price-check properties in Valencia Province.

## Vision

Help anyone (starting with me, later as a portfolio piece) answer questions like:
- *Is this listing fairly priced?*
- *Where do I get the most m² per €?*
- *Which neighborhoods are heating up?*
- *What features actually move the price (pool? terrace? floor)?*

## Architecture

```
┌─────────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐    ┌─────────────┐
│  scraper.py │───▶│ raw CSV  │───▶│ clean   │───▶│ features │───▶│ analysis    │
│ (fotocasa)  │    │          │    │ + dedup │    │ engineered│    │ + dashboard │
└─────────────┘    └──────────┘    └─────────┘    └──────────┘    └─────────────┘
                                                       │
                                                       ▼
                                                  ┌─────────┐
                                                  │ price ML│
                                                  │  model  │
                                                  └─────────┘
```

## Phases

### Phase 1 — Data quality & enrichment (`data_pipeline.py`)

**Goal:** Turn `valencia_houses.csv` into a clean, feature-rich dataset.

- [x] Fix `property_type` classification bug
- [ ] Drop duplicates by `id`
- [ ] Remove obvious outliers (price = 0, surface < 15m², price > 5M unless chalet)
- [ ] Impute missing `bedrooms`/`bathrooms` using subtype medians
- [ ] Add **derived features**:
  - `distance_to_valencia_km` (haversine from city center)
  - `distance_to_coast_km`
  - `is_coastal` (boolean, ≤5 km)
  - `feature_count` (sum of has_* booleans)
  - `price_segment` (quartile bucket)
  - `area_segment` (quartile bucket)
  - `region` (capital / metro / coast / interior — derived from county)
- [ ] Output `valencia_clean.parquet` (faster + smaller)

**Deliverable:** `data_pipeline.py` + `valencia_clean.parquet`

---

### Phase 2 — Exploratory Data Analysis (`notebooks/01_eda.ipynb`)

**Goal:** Surface insights & validate data.

- [ ] Distribution plots (price, m², €/m², bedrooms)
- [ ] Top 20 cities by listing count + median price
- [ ] Heatmap: price by city × subtype
- [ ] **Geographic map** with points colored by €/m²
- [ ] Feature impact on price (boxplots: with/without pool, parking, etc.)
- [ ] Listing freshness (how old are most listings?)
- [ ] Correlation matrix of numeric features
- [ ] **Key findings document** — bullet list of insights

**Deliverable:** Jupyter notebook + 1-page `INSIGHTS.md`

---

### Phase 3 — Price prediction model (`models/price_model.py`)

**Goal:** Predict fair market price → flag undervalued listings.

- [ ] Train/test split (stratified by city + subtype)
- [ ] Baseline: median €/m² × surface, by city
- [ ] Model: gradient boosting (LightGBM or XGBoost)
- [ ] Features: numeric + one-hot encoded categoricals + geographic
- [ ] Evaluation: MAE, MAPE, R² + residual plots
- [ ] **SHAP values** for feature importance
- [ ] Output: `predicted_price` and `bargain_score` columns
- [ ] Persist model: `models/price_model.pkl`

**Deliverable:** trained model + scoring script + evaluation report

---

### Phase 4 — Interactive dashboard (`app.py`)

**Goal:** Web app for browsing, filtering, finding bargains.

**Tech:** Streamlit (fast to build) → Plotly for charts, Folium for maps.

**Pages:**
1. **🏠 Browse** — Filter table (price, type, m², bedrooms, features, city)
2. **🗺️ Map** — Color-coded by €/m², click for details
3. **💰 Bargain Finder** — Listings priced N% below model prediction
4. **📊 Compare Areas** — City-level metrics side by side
5. **📈 Property Detail** — Single listing analysis (predicted price, comparables)

**Deliverable:** `app.py` runnable with `streamlit run app.py`

---

### Phase 5 — Tracking & history (`tracker.py`)

**Goal:** Track listings over time → detect price drops, new entries, removals.

- [ ] Schema: `listings_history` table with `(id, scraped_at, price)`
- [ ] Re-run scraper weekly via cron / GitHub Actions
- [ ] Compute deltas: price changes, days on market, removed listings
- [ ] **New listing alerts** matching saved criteria (email or just CSV)
- [ ] Dashboard tab: "Recent price drops"

**Deliverable:** scheduled pipeline + history database (SQLite)

---

## Tech Stack

| Concern | Tool |
|---|---|
| Scraping | `requests` + regex (already done) |
| Data wrangling | `pandas` + `pyarrow` (parquet) |
| Visualization | `plotly`, `folium`, `seaborn` |
| ML | `scikit-learn`, `lightgbm`, `shap` |
| Dashboard | `streamlit` |
| Storage | CSV → Parquet → SQLite (for history) |
| Scheduling | GitHub Actions (cron) |

## Repository Structure (target)

```
Valencia_House/
├── README.md
├── PROJECT_PLAN.md           # this file
├── INSIGHTS.md                # Phase 2 deliverable
├── requirements.txt
├── scraper.py                 # Phase 0 (done)
├── data_pipeline.py           # Phase 1
├── tracker.py                 # Phase 5
├── app.py                     # Phase 4
├── data/
│   ├── valencia_houses.csv    # raw scrape
│   ├── valencia_clean.parquet # processed
│   └── history.sqlite         # Phase 5
├── models/
│   ├── price_model.py
│   └── price_model.pkl
└── notebooks/
    ├── 01_eda.ipynb
    └── 02_model_dev.ipynb
```

## Milestones

- [x] **M1**: Plan + Phase 1 (data pipeline)
- [x] **M2**: Phase 2 — EDA notebook + INSIGHTS.md
- [x] **M3**: Phase 3 — price models + MODEL_REPORT.md
- [x] **M4**: Phase 4 — Streamlit dashboard with 6 pages
- [x] **M5**: Phase 5 — SQLite tracking + GitHub Actions weekly cron

## Open Questions

- Should the dashboard be deployed publicly (Streamlit Cloud) or just local?
- Acceptable "fresh" listing age? (drop > 6 months old?)
- Do we want bedrooms imputed when missing, or keep as null?
