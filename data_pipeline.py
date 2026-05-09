"""
Data cleaning & enrichment pipeline.

Reads raw CSV from scraper, applies quality fixes, computes derived geographic
and segmentation features, writes a clean Parquet file ready for analysis.

Usage:
    python data_pipeline.py
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

INPUT_CSV = Path("valencia_houses.csv")
OUTPUT_PARQUET = Path("valencia_clean.parquet")

# Valencia city center (Plaza del Ayuntamiento)
VALENCIA_CENTER = (39.4699, -0.3763)

# Coastal reference points along the Valencia province coast (lat, lon)
COAST_POINTS = [
    (39.7250, -0.2200),  # Sagunto / El Puig
    (39.4900, -0.3300),  # Valencia city beach (Malvarrosa)
    (39.3300, -0.3200),  # El Saler / Albufera
    (39.1700, -0.2400),  # Cullera
    (39.0000, -0.1700),  # Tavernes / Xeraco
    (38.9700, -0.1500),  # Gandia
    (38.9200, -0.1000),  # Oliva
]

CRITICAL_COLS = ["id", "price_eur", "surface_m2", "latitude", "longitude", "property_subtype"]

# County → broad region
COASTAL_COUNTIES = {"La Safor", "Ribera Baixa", "Camp de Morvedre"}
METRO_COUNTIES = {"Horta Nord", "Horta Sud", "Camp de Túria"}
CAPITAL_COUNTY = "Valencia, Zona de"


def haversine_km(lat1, lon1, lat2, lon2):
    """Vectorized haversine distance in kilometers."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def distance_to_coast(df: pd.DataFrame) -> pd.Series:
    """Min distance from each property to any coast reference point."""
    distances = []
    for lat_c, lon_c in COAST_POINTS:
        d = haversine_km(df["latitude"].values, df["longitude"].values, lat_c, lon_c)
        distances.append(d)
    return pd.Series(np.min(distances, axis=0), index=df.index)


def assign_region(row) -> str:
    if row["city"] == "Valencia Capital":
        return "Valencia Capital"
    county = row["county"]
    if county == CAPITAL_COUNTY:
        return "Valencia Metro"
    if county in METRO_COUNTIES:
        return "Valencia Metro"
    if county in COASTAL_COUNTIES:
        return "Coast"
    return "Interior"


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    log.info("Computing derived features...")

    df["distance_to_valencia_km"] = haversine_km(
        df["latitude"], df["longitude"], *VALENCIA_CENTER
    ).round(2)

    df["distance_to_coast_km"] = distance_to_coast(df).round(2)
    df["is_coastal"] = df["distance_to_coast_km"] <= 5.0

    df["region"] = df.apply(assign_region, axis=1)

    feature_cols = [
        "has_elevator", "has_parking", "has_terrace", "has_balcony",
        "has_pool", "has_garden", "has_air_conditioning", "has_heating",
        "has_storage", "is_furnished",
    ]
    df["feature_count"] = df[feature_cols].sum(axis=1)

    df["price_per_m2"] = (df["price_eur"] / df["surface_m2"]).round().astype("Int64")

    df["price_segment"] = pd.qcut(
        df["price_eur"],
        q=4,
        labels=["budget", "mid", "premium", "luxury"],
    )
    df["area_segment"] = pd.qcut(
        df["surface_m2"],
        q=4,
        labels=["small", "medium", "large", "xl"],
    )

    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    n0 = len(df)
    log.info(f"Loaded {n0} rows")

    # 1. Strip whitespace from string cols (some have leading spaces from API)
    for col in df.columns:
        if pd.api.types.is_string_dtype(df[col]) or df[col].dtype == "object":
            df[col] = df[col].astype("string").str.strip()

    # 2. Drop duplicates by id (keep latest scrape)
    if "scraped_at" in df.columns:
        df = df.sort_values("scraped_at").drop_duplicates(subset=["id"], keep="last")
    else:
        df = df.drop_duplicates(subset=["id"], keep="last")
    log.info(f"After dedup by id: {len(df)} rows ({n0 - len(df)} dupes removed)")

    # 3. Drop rows missing critical fields
    n_before = len(df)
    df = df.dropna(subset=CRITICAL_COLS)
    log.info(f"After dropping critical-null rows: {len(df)} ({n_before - len(df)} dropped)")

    # 4. Outlier removal
    n_before = len(df)
    df = df[
        (df["surface_m2"] >= 15) & (df["surface_m2"] <= 2500)
        & (df["price_eur"] >= 30_000) & (df["price_eur"] <= 5_000_000)
    ]
    log.info(f"After surface/price outlier removal: {len(df)} ({n_before - len(df)} dropped)")

    # Recompute price_per_m2 for sanity bounds check
    ppm = df["price_eur"] / df["surface_m2"]
    n_before = len(df)
    df = df[(ppm >= 200) & (ppm <= 15_000)]
    log.info(f"After €/m² outlier removal: {len(df)} ({n_before - len(df)} dropped)")

    # 5. Type conversions
    df["bedrooms"] = df["bedrooms"].astype("Int64")
    df["bathrooms"] = df["bathrooms"].astype("Int64")
    df["floor"] = df["floor"].astype("Int64")
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")

    return df.reset_index(drop=True)


def main():
    log.info(f"Reading {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV)

    df = clean(df)
    df = add_derived_features(df)

    # Summary
    log.info("\n--- SUMMARY ---")
    log.info(f"Final row count: {len(df)}")
    log.info(f"Columns: {len(df.columns)}")
    log.info(f"Property types: {df['property_type'].value_counts().to_dict()}")
    log.info(f"Regions: {df['region'].value_counts().to_dict()}")
    log.info(f"Price range: €{df['price_eur'].min():,.0f} – €{df['price_eur'].max():,.0f}")
    log.info(f"Median €/m²: {df['price_per_m2'].median():.0f}")
    log.info(f"Coastal listings: {df['is_coastal'].sum()} ({df['is_coastal'].mean()*100:.1f}%)")

    df.to_parquet(OUTPUT_PARQUET, index=False, compression="snappy")
    log.info(f"\nSaved {len(df)} clean listings to {OUTPUT_PARQUET}")
    log.info(f"File size: {OUTPUT_PARQUET.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
