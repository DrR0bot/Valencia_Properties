# Valencia Properties — Key Insights

Findings from EDA on **8,761 unique listings** across **236 cities** in Valencia Province (after dedup, outlier removal, critical-null filtering).

> See `notebooks/01_eda.ipynb` for the full analysis with interactive charts.

---

## Market shape

- **63% pisos** (apartments / flats / áticos / dúplex), **37% casas** (chalets / adosadas / rústicas)
- Most common subtype: **Piso (4,437 listings)**, then **Casa o chalet (2,309)**
- Median listing price: **€250,000**, median surface: **126 m²**, median **€2,147 / m²**
- Top 10% of listings cost **€645k+**, top 5% cost **€840k+**

## Where it's expensive

| Region | Median €/m² |
|---|---|
| Valencia Capital | **€3,623** |
| Valencia Metro | €2,102 |
| Coast | €1,931 |
| Interior | **€1,142** |

Interior is **3.2× cheaper per m²** than the capital.

### Most expensive cities (≥30 listings)

1. **Alboraya** — €3,976 / m² (51 listings)
2. **Valencia Capital** — €3,623 / m² (2,196)
3. **Godella** — €3,392 / m² (65)
4. **La Pobla de Farnals** — €2,733 / m²
5. **L'Eliana** — €2,688 / m²

> *Insight: Alboraya tops Valencia Capital in €/m² — driven by beachfront supply.*

### Cheapest cities (≥30 listings)

1. **Requena** — €809 / m² (45 listings)
2. **L'Olleria** — €917 / m²
3. **Alberic** — €1,016 / m²
4. **Carcaixent** — €1,079 / m²
5. **Algemesí** — €1,091 / m²

## What predicts price

Pearson correlation with €/m²:

| Feature | Correlation |
|---|---|
| Distance to Valencia (km) | **−0.50** |
| Distance to coast (km) | **−0.43** |
| Surface (m²) | −0.26 |
| Bedrooms | −0.25 |
| Feature count | +0.22 |
| Floor | +0.15 |
| Bathrooms | ≈ 0 |

> *Distance to Valencia is the single strongest predictor — every km from the center reduces €/m² meaningfully.*

## The Valencia premium curve

| Distance to center | Median €/m² |
|---|---|
| 0–5 km | **€3,594** |
| 5–10 km | €2,195 |
| 10–20 km | €2,167 |
| 20–30 km | €1,734 |
| 30–50 km | €1,427 |
| 50+ km | €1,450 |

**Sharpest drop happens in the first 5 km.** After ~30 km, prices flatten.

## The coastal premium

| Distance to coast | Median €/m² |
|---|---|
| 0–2 km | €2,585 |
| **2–5 km** | **€3,140** ← highest! |
| 5–10 km | €2,468 |
| 10–20 km | €1,796 |
| 20+ km | €1,234 |

> *Counterintuitive finding: 2–5 km from coast is more expensive than directly on the beach. Reason: the 2–5 km band overlaps with Valencia city center and Alboraya/Pobla de Farnals (premium suburbs near beach). Direct-beach listings include cheaper coastal towns like Cullera and Sagunto outskirts.*

## Feature impact (€/m² uplift when present)

| Feature | Uplift | Listings with |
|---|---|---|
| **Elevator** | **+68%** | 3,525 |
| Air conditioning | +33% | 4,514 |
| Heating | +25% | 2,536 |
| Balcony | +3% | 3,417 |
| Furnished | +4% | 2,247 |
| Parking | −3% | 3,072 |
| Terrace | −9% | 4,502 |
| Storage | −15% | 2,501 |

> *⚠️ These are **descriptive** uplifts, not causal. "Elevator +68%" mostly reflects that elevators correlate with city flats (= expensive Valencia Capital). A proper causal estimate needs the price model in Phase 3.*

> *Negative uplifts make sense: terraces & parking are common in cheaper sub-/exurban properties.*

## Market temperature

- **Median listing age: 84 days** — properties sit ~3 months on average
- **27.6%** of listings are older than 6 months → soft market with overhang
- **22.4%** of listings have advertised a price drop
- **Total advertised price reductions: €66.6 M** across 1,962 listings

## Known data gaps

- ⚠️ `has_pool` and `has_garden` are **all False** in the current scrape — feature keys in the API are `swimming_pool` / `private_garden`, scraper now fixed but the existing CSV needs a re-scrape to populate these.
- ~12% missing bedrooms / bathrooms (kept as NULL in cleaned data)

## Implications for the price model (Phase 3)

The strong distance gradients + the dominance of region effects mean the model should:

- One-hot encode `region` and high-frequency cities
- Include both distance features (they correlate but each adds signal)
- Apply log-transform on price (right-skewed)
- Use surface × region interaction (€/m² varies dramatically by region)

## Bargain-hunter shortlists

Once the model exists, surface flag candidates as:

- Listings priced > 15% below predicted fair value
- Within target region & feature requirements
- Recent listings (< 30 days, less likely already-rejected stale stock)
