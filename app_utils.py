"""Shared utilities for the Valencia Properties Streamlit dashboard."""

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "valencia_scored.parquet"


@st.cache_data(show_spinner="Loading Valencia listings...")
def load_data() -> pd.DataFrame:
    df = pd.read_parquet(DATA_PATH)
    return df


def fmt_eur(v) -> str:
    if pd.isna(v):
        return "—"
    return f"€{v:,.0f}"


def fmt_int(v) -> str:
    if pd.isna(v):
        return "—"
    return f"{int(v):,}"


def fmt_pct(v) -> str:
    if pd.isna(v):
        return "—"
    return f"{v:+.1f}%"


FEATURE_COLS = [
    ("has_elevator", "Elevator"),
    ("has_parking", "Parking"),
    ("has_terrace", "Terrace"),
    ("has_balcony", "Balcony"),
    ("has_air_conditioning", "Air conditioning"),
    ("has_heating", "Heating"),
    ("has_storage", "Storage"),
    ("is_furnished", "Furnished"),
]

DISPLAY_COLS = [
    "title",
    "property_subtype",
    "city",
    "district",
    "price_eur",
    "predicted_price",
    "bargain_pct",
    "surface_m2",
    "price_per_m2",
    "bedrooms",
    "bathrooms",
    "feature_count",
    "listing_age_days",
    "url",
]


def sidebar_filters(df: pd.DataFrame, key_prefix: str = "") -> pd.DataFrame:
    """Render comprehensive sidebar filters and return the filtered DataFrame."""
    st.sidebar.header("Filters")

    types = st.sidebar.multiselect(
        "Property type",
        options=sorted(df["property_type"].dropna().unique()),
        default=sorted(df["property_type"].dropna().unique()),
        key=f"{key_prefix}_type",
    )

    subtypes_available = sorted(df[df["property_type"].isin(types)]["property_subtype"].dropna().unique())
    subtypes = st.sidebar.multiselect(
        "Subtype",
        options=subtypes_available,
        default=subtypes_available,
        key=f"{key_prefix}_subtype",
    )

    regions = st.sidebar.multiselect(
        "Region",
        options=sorted(df["region"].dropna().unique()),
        default=sorted(df["region"].dropna().unique()),
        key=f"{key_prefix}_region",
    )

    region_mask = df["region"].isin(regions) if regions else pd.Series(True, index=df.index)
    cities_available = sorted(df.loc[region_mask, "city"].dropna().unique())
    cities = st.sidebar.multiselect(
        "City (leave empty = all)",
        options=cities_available,
        default=[],
        key=f"{key_prefix}_city",
    )

    price_min = int(df["price_eur"].min())
    price_max = int(df["price_eur"].max())
    price_range = st.sidebar.slider(
        "Price (€)",
        min_value=price_min,
        max_value=price_max,
        value=(price_min, min(price_max, 800_000)),
        step=10_000,
        format="€%d",
        key=f"{key_prefix}_price",
    )

    surface_max = int(df["surface_m2"].quantile(0.99))
    surface_range = st.sidebar.slider(
        "Surface (m²)",
        min_value=15,
        max_value=surface_max,
        value=(50, surface_max),
        step=10,
        key=f"{key_prefix}_surface",
    )

    bedrooms_options = ["Any", "1+", "2+", "3+", "4+"]
    bedrooms_choice = st.sidebar.selectbox(
        "Bedrooms (min)", bedrooms_options, key=f"{key_prefix}_beds"
    )

    age_max = int(df["listing_age_days"].max())
    age_max_filter = st.sidebar.slider(
        "Max listing age (days)",
        min_value=1,
        max_value=age_max,
        value=age_max,
        key=f"{key_prefix}_age",
    )

    bargain_status = st.sidebar.radio(
        "Pricing vs predicted",
        options=["Any", "Bargain (≥15% under)", "Fair (±15%)", "Overpriced (≥15% over)"],
        index=0,
        key=f"{key_prefix}_bargain",
    )

    st.sidebar.markdown("**Required features**")
    cols = st.sidebar.columns(2)
    feature_filters = {}
    for i, (col, label) in enumerate(FEATURE_COLS):
        with cols[i % 2]:
            feature_filters[col] = st.checkbox(label, value=False, key=f"{key_prefix}_{col}")

    out = df.copy()
    if types:
        out = out[out["property_type"].isin(types)]
    if subtypes:
        out = out[out["property_subtype"].isin(subtypes)]
    if regions:
        out = out[out["region"].isin(regions)]
    if cities:
        out = out[out["city"].isin(cities)]
    out = out[
        (out["price_eur"] >= price_range[0])
        & (out["price_eur"] <= price_range[1])
        & (out["surface_m2"] >= surface_range[0])
        & (out["surface_m2"] <= surface_range[1])
        & (out["listing_age_days"] <= age_max_filter)
    ]
    bed_min = {"Any": 0, "1+": 1, "2+": 2, "3+": 3, "4+": 4}[bedrooms_choice]
    if bed_min > 0:
        out = out[(out["bedrooms"] >= bed_min) | out["bedrooms"].isna()]

    if bargain_status == "Bargain (≥15% under)":
        out = out[out["is_bargain"]]
    elif bargain_status == "Fair (±15%)":
        out = out[~out["is_bargain"] & ~out["is_overpriced"]]
    elif bargain_status == "Overpriced (≥15% over)":
        out = out[out["is_overpriced"]]

    for col, required in feature_filters.items():
        if required:
            out = out[out[col]]

    st.sidebar.markdown("---")
    st.sidebar.metric("Listings shown", f"{len(out):,}")
    return out


def listing_card(row: pd.Series, expanded: bool = False) -> None:
    """Render a single listing as a styled section."""
    bargain = row.get("bargain_pct", 0) or 0
    color = "#10b981" if bargain >= 15 else ("#ef4444" if bargain <= -15 else "#6b7280")

    title = f"{row.get('property_subtype', '')} en {row.get('district') or row.get('city', '')}"
    with st.expander(f"{title} — {fmt_eur(row['price_eur'])}", expanded=expanded):
        c1, c2, c3 = st.columns(3)
        c1.metric("Price", fmt_eur(row["price_eur"]))
        c2.metric("Predicted", fmt_eur(row.get("predicted_price")))
        c3.metric("Bargain", fmt_pct(bargain))

        c1, c2, c3, c4 = st.columns(4)
        c1.write(f"**Surface**: {row['surface_m2']:.0f} m²")
        c2.write(f"**€/m²**: {fmt_eur(row['price_per_m2'])}")
        c3.write(f"**Bedrooms**: {fmt_int(row['bedrooms'])}")
        c4.write(f"**Bathrooms**: {fmt_int(row['bathrooms'])}")

        st.write(f"**City**: {row['city']} • **Region**: {row['region']} • **Listed**: {int(row['listing_age_days'])} days ago")

        st.markdown(f"[Open on fotocasa]({row['url']})")
