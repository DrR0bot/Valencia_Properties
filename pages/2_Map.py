"""Map page — geographic view of listings."""

import plotly.express as px
import streamlit as st

from app_utils import load_data, sidebar_filters

st.set_page_config(page_title="Map", layout="wide")

st.title("Map view")
st.caption("Each dot = one listing. Color by selected metric, size by surface area.")

df = load_data()
filtered = sidebar_filters(df, key_prefix="map")

if filtered.empty:
    st.warning("No listings match these filters.")
    st.stop()

color_options = {
    "€/m² (capped at 5000)": ("price_per_m2", "Turbo", 5000),
    "Total price": ("price_eur", "Turbo", None),
    "Bargain %": ("bargain_pct", "RdYlGn", None),
    "Listing age (days)": ("listing_age_days", "OrRd", None),
    "Surface (m²)": ("surface_m2", "Viridis", None),
}
color_choice = st.selectbox("Color by", list(color_options.keys()))
col, scale, cap = color_options[color_choice]

map_df = filtered.copy()
plot_col = col
if cap is not None:
    map_df["_color_capped"] = map_df[col].clip(upper=cap)
    plot_col = "_color_capped"

fig = px.scatter_mapbox(
    map_df,
    lat="latitude",
    lon="longitude",
    color=plot_col,
    size="surface_m2",
    size_max=14,
    hover_name="title",
    hover_data={
        "city": True,
        "district": True,
        "price_eur": ":,.0f",
        "predicted_price": ":,.0f",
        "bargain_pct": ":.1f",
        "surface_m2": True,
        "bedrooms": True,
        "url": False,
        plot_col: False,
    },
    color_continuous_scale=scale,
    color_continuous_midpoint=0 if col == "bargain_pct" else None,
    zoom=8,
    center={"lat": 39.4699, "lon": -0.3763},
    height=720,
)
fig.update_layout(
    mapbox_style="open-street-map",
    margin={"r": 0, "t": 0, "l": 0, "b": 0},
    coloraxis_colorbar=dict(title=color_choice),
)
st.plotly_chart(fig, use_container_width=True)

st.caption(f"Showing {len(filtered):,} listings.")
