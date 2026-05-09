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

### Phase 1 — Data quality & enrichment (`data_pipeline.py`) ✅

**Goal:** Turn `valencia_houses.csv` into a clean, feature-rich dataset.

- [x] Fix `property_type` classification bug
- [x] Drop duplicates by `id` (~6,020 dupes removed)
- [x] Remove obvious outliers (surface < 15m², price < €30k or > €5M, €/m² < 200 or > 15,000)
- [x] ~~Impute missing `bedrooms`/`bathrooms`~~ → **changed to drop rows missing critical fields** (user decision)
- [x] Add **derived features**:
  - [x] `distance_to_valencia_km` (haversine from city center)
  - [x] `distance_to_coast_km`
  - [x] `is_coastal` (boolean, ≤5 km)
  - [x] `feature_count` (sum of has_* booleans)
  - [x] `price_segment` (quartile bucket)
  - [x] `area_segment` (quartile bucket)
  - [x] `region` (capital / metro / coast / interior — derived from county)
- [x] Output `valencia_clean.parquet` (faster + smaller)

**Result:** 14,880 raw → 8,761 unique clean listings (47 columns, 724 KB parquet)

**Deliverable:** `data_pipeline.py` + `valencia_clean.parquet`

---

### Phase 2 — Exploratory Data Analysis (`notebooks/01_eda.ipynb`) ✅

**Goal:** Surface insights & validate data.

- [x] Distribution plots (price, m², €/m², bedrooms)
- [x] Top 20 cities by listing count + median price
- [x] Heatmap → ended up using **grouped bar charts** (region × subtype) — same insight, clearer
- [x] **Geographic map** with points colored by €/m²
- [x] Feature impact on price (uplift % bar chart)
- [x] Listing freshness (age distribution + price-drop stats)
- [x] Correlation matrix of numeric features
- [x] Distance-to-coast / distance-to-Valencia gradient analysis (extra)
- [x] Bargain leaderboards by region (extra)
- [x] **Key findings document** — `INSIGHTS.md` with quantified findings
- [x] Discovered & fixed `swimming_pool`/`private_garden` feature-key bug during EDA

**Deliverable:** Jupyter notebook (11 sections) + `INSIGHTS.md`

---

### Phase 3 — Price prediction model (`models/price_model.py`) ✅

**Goal:** Predict fair market price → flag undervalued listings.

- [x] Train/test split — random 80/20 (effective stratification by training **separate models per type**)
- [ ] ~~Baseline: median €/m² × surface, by city~~ → **skipped** (LightGBM ran fast enough; can add later if needed)
- [x] Model: **LightGBM** with early stopping
- [x] Features: 29 total (numeric + boolean + LightGBM-native categorical handling, no one-hot needed)
- [x] Evaluation: MAE, MAPE, median APE, R² + residual plots in notebook
- [x] **SHAP values** for feature importance (beeswarm + summary plots)
- [x] Output: `predicted_price`, `bargain_eur`, `bargain_pct`, `is_bargain`, `is_overpriced` columns
- [x] Persist models: `models/price_model_casa.pkl` + `models/price_model_piso.pkl`
- [x] **Two separate models** (Casa & Piso) — better accuracy than a single combined model

**Result:** Piso MAPE 15.0% / median APE 10.2%, Casa MAPE 27.3% / median APE 19.3%. 667 bargains flagged.

**Deliverable:** trained models + scoring script + `MODEL_REPORT.md` + `02_model_dev.ipynb`

---

### Phase 4 — Interactive dashboard (`app.py`) ✅

**Goal:** Web app for browsing, filtering, finding bargains.

**Tech:** Streamlit + Plotly (used `scatter_mapbox` instead of Folium — same result, no extra dep)

**Pages:**
- [x] **Browse** — sortable filter table (price, type, m², bedrooms, features, city, age, bargain status)
- [x] **Map** — color-coded by €/m² / bargain / age; size by surface
- [x] **Bargain Finder** — sorted leaderboard, table or card view, region histogram
- [x] **Compare Areas** — city-level metrics + distance-vs-price scatter
- [x] **Property Detail** — single listing with mini-map + nearby comparables + €/m² distribution
- [x] **Price Tracking** — bonus 6th page added in Phase 5
- [x] Shared comprehensive sidebar filters via `app_utils.sidebar_filters`
- [x] Custom green theme via `.streamlit/config.toml`
- [ ] **Deploy to Streamlit Cloud** ← only remaining manual step

**Deliverable:** `app.py` runnable with `streamlit run app.py`

---

### Phase 5 — Tracking & history (`tracker.py`) ✅

**Goal:** Track listings over time → detect price drops, new entries, removals.

- [x] Schema: `snapshots(snapshot_at, listing_id, price_eur, ...)` + `listings_meta(listing_id, first_seen, last_seen, ...)`
- [x] Re-run scraper weekly via GitHub Actions (`.github/workflows/weekly_update.yml`, Mon 06:00 UTC)
- [x] Compute deltas: `get_price_drops()`, `get_market_trend()`, `get_listing_history()`
- [ ] ~~**New listing alerts** via email~~ → **deferred** (no SMTP wired up; manual via dashboard for now)
- [x] Dashboard tab: "Price Tracking" with drops, market trend, per-listing history
- [x] Initial snapshot recorded (8,761 listings, 2.9 MB SQLite)

**Deliverable:** scheduled pipeline + `history.sqlite` + `tracker.py` CLI

---

## Tech Stack (final)

| Concern | Tool |
|---|---|
| Scraping | `requests` + regex on embedded `__INITIAL_PROPS__` JSON |
| Data wrangling | `pandas` + `pyarrow` (parquet) |
| Visualization | `plotly` (charts + mapbox) — Folium dropped, not needed |
| ML | `lightgbm` + `scikit-learn` + `shap` + `joblib` |
| Dashboard | `streamlit` (multi-page) |
| Storage | CSV (raw) → Parquet (clean & scored) → SQLite (history) |
| Scheduling | GitHub Actions (cron) |

## Repository Structure (actual)

```
Valencia_Properties/
├── README.md                       ✅
├── PROJECT_PLAN.md                 ✅ (this file)
├── INSIGHTS.md                     ✅ Phase 2 findings
├── MODEL_REPORT.md                 ✅ Phase 3 evaluation
├── requirements.txt                ✅
├── scraper.py                      ✅ Phase 0
├── data_pipeline.py                ✅ Phase 1
├── tracker.py                      ✅ Phase 5
├── app.py                          ✅ Phase 4
├── app_utils.py                    ✅ shared dashboard helpers
├── valencia_houses.csv             ✅ raw scrape (root, not data/)
├── valencia_clean.parquet          ✅ Phase 1 output
├── valencia_scored.parquet         ✅ Phase 3 output
├── history.sqlite                  ✅ Phase 5 storage
├── .streamlit/config.toml          ✅ theme
├── .github/workflows/
│   └── weekly_update.yml           ✅ Phase 5 cron
├── models/
│   ├── price_model.py              ✅
│   ├── price_model_casa.pkl        ✅
│   ├── price_model_piso.pkl        ✅
│   ├── metrics.json                ✅
│   └── feature_importance_*.csv    ✅
├── pages/
│   ├── 1_Browse.py                 ✅
│   ├── 2_Map.py                    ✅
│   ├── 3_Bargain_Finder.py         ✅
│   ├── 4_Compare_Areas.py          ✅
│   ├── 5_Property_Detail.py        ✅
│   └── 6_Price_Tracking.py         ✅
└── notebooks/
    ├── 01_eda.ipynb                ✅
    └── 02_model_dev.ipynb          ✅
```

> Note: data files live at the repo root (not in `data/`) since they were already there
> when the project started. Refactoring into `data/` is optional cleanup.

## Milestones

- [x] **M1**: Plan + Phase 1 (data pipeline)
- [x] **M2**: Phase 2 — EDA notebook + INSIGHTS.md
- [x] **M3**: Phase 3 — price models + MODEL_REPORT.md
- [x] **M4**: Phase 4 — Streamlit dashboard with 6 pages
- [x] **M5**: Phase 5 — SQLite tracking + GitHub Actions weekly cron

## Decisions Made (originally open questions)

- ~~Should the dashboard be deployed publicly?~~ → **Streamlit Cloud** (decided; deployment pending)
- ~~Acceptable "fresh" listing age?~~ → **Keep all listings** (no age filter)
- ~~Do we want bedrooms imputed when missing?~~ → **Drop rows missing critical fields** instead of imputing

## Known Gaps & Optional Follow-ups

- [ ] Deploy live to Streamlit Cloud (manual ~5 min step)
- [ ] Re-scrape with the `swimming_pool` / `private_garden` fix → re-train models for likely accuracy bump
- [ ] Add a baseline price model (median €/m² × surface by city) for sanity comparison vs LightGBM
- [ ] Email alerts on new listings matching saved criteria
- [ ] NLP on listing descriptions (capture "needs renovation" vs "fully renovated" signals)
- [ ] Extend scraper to cover other Spanish provinces
