"""
Phase 3: Price prediction model for Valencia properties.

Trains separate LightGBM regressors for Casa and Piso, persists them, scores
the cleaned dataset and writes valencia_scored.parquet with predicted price
and a bargain_score for each listing.

Usage:
    python models/price_model.py             # train + score
    python models/price_model.py --score-only  # use existing models to re-score
"""

import argparse
import json
import logging
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
INPUT_PARQUET = ROOT / "valencia_clean.parquet"
OUTPUT_PARQUET = ROOT / "valencia_scored.parquet"
MODELS_DIR = ROOT / "models"
METRICS_FILE = MODELS_DIR / "metrics.json"

NUMERIC_FEATURES = [
    "surface_m2",
    "bedrooms",
    "bathrooms",
    "floor",
    "distance_to_valencia_km",
    "distance_to_coast_km",
    "feature_count",
    "listing_age_days",
    "latitude",
    "longitude",
]

BOOLEAN_FEATURES = [
    "has_elevator",
    "has_parking",
    "has_terrace",
    "has_balcony",
    "has_air_conditioning",
    "has_heating",
    "has_storage",
    "is_furnished",
    "is_coastal",
    "price_dropped",
    "is_new_construction",
]

CATEGORICAL_FEATURES = ["region", "property_subtype", "conservation_status", "city"]

ALL_FEATURES = NUMERIC_FEATURES + BOOLEAN_FEATURES + CATEGORICAL_FEATURES


def prepare_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Build feature matrix and (log-transformed) target."""
    X = df[ALL_FEATURES].copy()

    for col in BOOLEAN_FEATURES:
        X[col] = X[col].fillna(False).astype("int8")

    for col in CATEGORICAL_FEATURES:
        X[col] = X[col].astype("category")

    y = np.log(df["price_eur"])
    return X, y


def train_one_model(df_subset: pd.DataFrame, name: str, random_state: int = 42):
    """Train a LightGBM model on a subset (e.g. Casa or Piso)."""
    log.info(f"\n{'=' * 60}\nTraining model: {name} ({len(df_subset)} rows)\n{'=' * 60}")

    X, y = prepare_features(df_subset)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=random_state
    )

    model = lgb.LGBMRegressor(
        n_estimators=1000,
        learning_rate=0.05,
        num_leaves=63,
        max_depth=-1,
        min_child_samples=20,
        reg_alpha=0.1,
        reg_lambda=0.1,
        random_state=random_state,
        n_jobs=-1,
        verbose=-1,
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        eval_metric="mae",
        categorical_feature=CATEGORICAL_FEATURES,
        callbacks=[lgb.early_stopping(30), lgb.log_evaluation(0)],
    )

    pred_log = model.predict(X_test)
    pred = np.exp(pred_log)
    actual = np.exp(y_test)

    mae_eur = mean_absolute_error(actual, pred)
    mape_pct = np.mean(np.abs((pred - actual) / actual)) * 100
    median_ape = np.median(np.abs((pred - actual) / actual)) * 100
    r2_log = r2_score(y_test, pred_log)

    metrics = {
        "name": name,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "mae_eur": round(float(mae_eur), 0),
        "mape_pct": round(float(mape_pct), 2),
        "median_ape_pct": round(float(median_ape), 2),
        "r2_log_scale": round(float(r2_log), 4),
        "best_iteration": int(model.booster_.best_iteration or model.n_estimators),
    }
    log.info(f"Metrics: MAE €{metrics['mae_eur']:,.0f}, "
             f"MAPE {metrics['mape_pct']:.1f}%, "
             f"Median APE {metrics['median_ape_pct']:.1f}%, "
             f"R²(log) {metrics['r2_log_scale']:.3f}")

    importances = pd.DataFrame({
        "feature": X.columns,
        "importance": model.booster_.feature_importance(importance_type="gain"),
    }).sort_values("importance", ascending=False)
    log.info(f"Top 10 features by gain:\n{importances.head(10).to_string(index=False)}")

    return model, metrics, importances


def score_dataset(df: pd.DataFrame, casa_model, piso_model) -> pd.DataFrame:
    """Add predicted_price, bargain_pct, bargain_score columns."""
    df = df.copy()
    df["predicted_price"] = np.nan

    for type_label, model in [("Casa", casa_model), ("Piso", piso_model)]:
        mask = df["property_type"] == type_label
        if mask.sum() == 0:
            continue
        X, _ = prepare_features(df.loc[mask])
        df.loc[mask, "predicted_price"] = np.exp(model.predict(X))

    df["predicted_price"] = df["predicted_price"].round()
    df["bargain_eur"] = (df["predicted_price"] - df["price_eur"]).round()
    df["bargain_pct"] = ((df["bargain_eur"] / df["predicted_price"]) * 100).round(2)
    df["is_bargain"] = df["bargain_pct"] >= 15.0
    df["is_overpriced"] = df["bargain_pct"] <= -15.0

    return df


def main(score_only: bool = False):
    log.info(f"Loading {INPUT_PARQUET}")
    df = pd.read_parquet(INPUT_PARQUET)
    log.info(f"Loaded {len(df)} rows")

    casa_path = MODELS_DIR / "price_model_casa.pkl"
    piso_path = MODELS_DIR / "price_model_piso.pkl"

    if score_only:
        log.info("Loading existing models...")
        casa_model = joblib.load(casa_path)
        piso_model = joblib.load(piso_path)
        all_metrics = json.loads(METRICS_FILE.read_text()) if METRICS_FILE.exists() else {}
    else:
        casa_df = df[df["property_type"] == "Casa"].copy()
        piso_df = df[df["property_type"] == "Piso"].copy()

        casa_model, casa_metrics, casa_imp = train_one_model(casa_df, "Casa")
        piso_model, piso_metrics, piso_imp = train_one_model(piso_df, "Piso")

        joblib.dump(casa_model, casa_path)
        joblib.dump(piso_model, piso_path)
        log.info(f"\nSaved models to {MODELS_DIR}/")

        all_metrics = {"casa": casa_metrics, "piso": piso_metrics}
        METRICS_FILE.write_text(json.dumps(all_metrics, indent=2))

        casa_imp.to_csv(MODELS_DIR / "feature_importance_casa.csv", index=False)
        piso_imp.to_csv(MODELS_DIR / "feature_importance_piso.csv", index=False)

    log.info("\nScoring full dataset...")
    scored = score_dataset(df, casa_model, piso_model)

    n_bargains = int(scored["is_bargain"].sum())
    n_overpriced = int(scored["is_overpriced"].sum())
    log.info(f"Bargains (≥15% under predicted): {n_bargains}")
    log.info(f"Overpriced (≥15% over predicted): {n_overpriced}")

    scored.to_parquet(OUTPUT_PARQUET, index=False, compression="snappy")
    log.info(f"\nSaved scored dataset to {OUTPUT_PARQUET}")
    log.info(f"File size: {OUTPUT_PARQUET.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-only", action="store_true",
                        help="Skip training, use existing models to score")
    args = parser.parse_args()
    main(score_only=args.score_only)
