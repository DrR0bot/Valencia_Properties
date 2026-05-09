# Valencia Properties — Market Intelligence

End-to-end data analysis stack for the **Valencia Province** real estate market.
From raw fotocasa scrapes to an interactive dashboard with bargain detection,
geographic analysis, and price tracking over time.

> 🌐 **Live demo**: deploy with one click to [Streamlit Community Cloud](https://share.streamlit.io)

## What this does

| Capability | Details |
|---|---|
| 🕷️ **Scraping** | Pulls all listings for Valencia Province from fotocasa.es (~9k unique properties) |
| 🧹 **Cleaning** | Dedup, outlier removal, geo-enrichment (distance to coast & city center) |
| 📊 **Analysis** | EDA notebook + insights document with key market findings |
| 🤖 **Prediction** | Two LightGBM models (Casa & Piso) forecast fair price; SHAP explainability |
| 💎 **Bargain detection** | Flags listings priced ≥15% below predicted fair value |
| 🌍 **Dashboard** | Streamlit app with 6 pages: browse, map, bargains, compare areas, property detail, price tracking |
| 📈 **Tracking** | Weekly snapshots in SQLite track price changes per listing over time |
| 🤖 **Automation** | GitHub Actions cron runs the entire pipeline weekly |

## Quick start

```bash
git clone https://github.com/DrR0bot/Valencia_Properties.git
cd Valencia_Properties

python -m venv venv
source venv/Scripts/activate    # Windows: source venv/Scripts/activate
pip install -r requirements.txt

streamlit run app.py
```

Open `http://localhost:8501` in your browser.

## Architecture

```
┌─────────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐    ┌─────────────┐
│  scraper.py │───▶│ raw CSV  │───▶│ clean   │───▶│ predict  │───▶│ dashboard   │
│ (fotocasa)  │    │          │    │ + dedup │    │ + score  │    │ (streamlit) │
└─────────────┘    └──────────┘    └─────────┘    └──────────┘    └─────────────┘
                                                       │
                                                       ▼
                                                  ┌─────────┐
                                                  │ tracker │
                                                  │ SQLite  │
                                                  └─────────┘
```

## Repository structure

```
Valencia_Properties/
├── app.py                       # Streamlit entry point
├── app_utils.py                 # Shared dashboard utilities
├── pages/
│   ├── 1_Browse.py              # Filterable table
│   ├── 2_Map.py                 # Interactive geo scatter
│   ├── 3_Bargain_Finder.py      # Listings priced under predicted
│   ├── 4_Compare_Areas.py       # City-level comparisons
│   ├── 5_Property_Detail.py     # Single-listing analysis
│   └── 6_Price_Tracking.py      # Historical price drops & trends
├── scraper.py                   # fotocasa.es scraper
├── data_pipeline.py             # CSV → cleaned parquet (dedup, enrich)
├── models/
│   ├── price_model.py           # Train + score
│   ├── price_model_casa.pkl     # Trained Casa model
│   ├── price_model_piso.pkl     # Trained Piso model
│   └── metrics.json             # Eval metrics
├── tracker.py                   # SQLite snapshot + delta logic
├── notebooks/
│   ├── 01_eda.ipynb             # Exploratory analysis
│   └── 02_model_dev.ipynb       # Model development & SHAP
├── .github/workflows/
│   └── weekly_update.yml        # Cron: scrape + pipeline + score + snapshot
├── valencia_houses.csv          # Raw scrape (~9k listings × 41 cols)
├── valencia_clean.parquet       # Cleaned + enriched (47 cols)
├── valencia_scored.parquet      # + predicted_price + bargain_score
├── history.sqlite               # Price history per listing
├── PROJECT_PLAN.md              # 5-phase roadmap
├── INSIGHTS.md                  # EDA findings
└── MODEL_REPORT.md              # Model evaluation
```

## Pipeline commands

| Step | Command |
|---|---|
| Scrape (full, ~3 hours) | `python scraper.py` |
| Scrape (limited) | `python scraper.py --max-pages 50` |
| Clean & enrich | `python data_pipeline.py` |
| Train models | `python models/price_model.py` |
| Score only (re-use models) | `python models/price_model.py --score-only` |
| Record snapshot | `python tracker.py snapshot` |
| Show price drops | `python tracker.py drops --days 7 --pct 5` |
| Show DB stats | `python tracker.py stats` |
| Run dashboard | `streamlit run app.py` |

## Key findings (from `INSIGHTS.md`)

- **Distance to Valencia center** is the strongest price predictor (r=−0.50)
- **Interior is 3× cheaper per m²** than the capital (€1,142 vs €3,623)
- **Counterintuitive coast premium**: 2–5 km inland costs more than 0–2 km
- **Soft market**: 28% of listings 6+ months old, 22% have already cut prices
- **€66M in advertised price drops** across 1,962 listings

## Model performance (from `MODEL_REPORT.md`)

| Model | Test MAPE | Median APE | R² (log) |
|---|---|---|---|
| **Piso** (n=5,551) | **15.0%** | **10.2%** | **0.876** |
| **Casa** (n=3,210) | 27.3% | 19.3% | 0.790 |

Half of all Piso predictions are within ±10% of true price.

## Deploying to Streamlit Cloud

1. Push the repo to GitHub (already done)
2. Go to [share.streamlit.io](https://share.streamlit.io) → "New app"
3. Pick the repo, branch `main`, file `app.py`
4. Deploy

The dashboard will be live at `https://<your-app>.streamlit.app/`.

## Updating the data

Two options:

**Option A — Manual** (recommended for first time):

```bash
python scraper.py
python data_pipeline.py
python models/price_model.py --score-only
python tracker.py snapshot
git add valencia_houses.csv valencia_clean.parquet valencia_scored.parquet history.sqlite
git commit -m "Update data $(date +%Y-%m-%d)"
git push
```

**Option B — Automatic** (via GitHub Actions):

The workflow `.github/workflows/weekly_update.yml` runs every Monday at 06:00 UTC.
Trigger manually from the Actions tab → "Weekly Valencia Properties Update" → "Run workflow".

⚠️ Note: scraping from GitHub-hosted runners may get blocked by fotocasa's anti-bot measures.
If automated runs fail, run the scraper locally and commit the CSV — the workflow will still
process and snapshot the data.

## Disclaimer

This project is for **educational and personal-research purposes**. Predictions are
descriptive (not causal) and a "bargain" flag does not imply a property is actually
worth buying. Properties may have hidden defects (legal issues, condition, location)
that the model cannot see. **Always inspect any property in person before purchasing.**

Data is scraped from fotocasa.es; respect their robots.txt and terms of service.

## License

MIT — see LICENSE if added.

---

Built as a learning project. Open issues on GitHub if you spot bugs or have ideas.
