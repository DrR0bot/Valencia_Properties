"""Compare Areas page — city-level metrics side-by-side."""

import plotly.express as px
import streamlit as st

from app_utils import load_data

st.set_page_config(page_title="Compare Areas", layout="wide")

st.title("Compare areas")
st.caption("Side-by-side analytics for cities and regions in Valencia Province.")

df = load_data()

st.markdown("### Filters")
c1, c2 = st.columns([1, 2])
with c1:
    min_listings = st.slider("Minimum listings per city", 5, 200, 30, step=5)
with c2:
    types = st.multiselect(
        "Property types",
        options=sorted(df["property_type"].unique()),
        default=sorted(df["property_type"].unique()),
    )

scope = df[df["property_type"].isin(types)]

city_stats = (
    scope.groupby("city")
    .agg(
        listings=("id", "count"),
        median_price=("price_eur", "median"),
        median_ppm2=("price_per_m2", "median"),
        median_m2=("surface_m2", "median"),
        median_dist_valencia=("distance_to_valencia_km", "median"),
        median_dist_coast=("distance_to_coast_km", "median"),
        bargains=("is_bargain", "sum"),
    )
    .reset_index()
)
city_stats = city_stats[city_stats["listings"] >= min_listings]

if city_stats.empty:
    st.warning("No cities meet the minimum listing threshold. Lower it.")
    st.stop()

st.markdown("---")
st.subheader("City picker — pick cities to compare")

picker = st.multiselect(
    "Select cities (leave empty for top 10 by listing count)",
    options=sorted(city_stats["city"].tolist()),
    default=[],
)
if picker:
    selection = city_stats[city_stats["city"].isin(picker)]
else:
    selection = city_stats.nlargest(10, "listings")

st.markdown(f"**Comparing {len(selection)} cities**")

st.dataframe(
    selection.sort_values("median_ppm2", ascending=False),
    hide_index=True,
    use_container_width=True,
    column_config={
        "city": "City",
        "listings": st.column_config.NumberColumn("Listings", format="%d"),
        "median_price": st.column_config.NumberColumn("Median price", format="€%d"),
        "median_ppm2": st.column_config.NumberColumn("Median €/m²", format="€%d"),
        "median_m2": st.column_config.NumberColumn("Median m²", format="%d"),
        "median_dist_valencia": st.column_config.NumberColumn("km to Valencia", format="%.1f"),
        "median_dist_coast": st.column_config.NumberColumn("km to coast", format="%.1f"),
        "bargains": st.column_config.NumberColumn("Bargains", format="%d"),
    },
)

st.markdown("---")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Median €/m² by city")
    fig = px.bar(
        selection.sort_values("median_ppm2"),
        x="median_ppm2",
        y="city",
        orientation="h",
        text="median_ppm2",
        color="median_ppm2",
        color_continuous_scale="Viridis",
    )
    fig.update_traces(texttemplate="€%{text:,.0f}", textposition="outside")
    fig.update_layout(height=500, margin={"t": 20}, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("Listings & bargain count")
    fig = px.bar(
        selection.sort_values("listings"),
        x="city",
        y=["listings", "bargains"],
        barmode="group",
        labels={"value": "Count", "variable": "Metric"},
        color_discrete_map={"listings": "#3b82f6", "bargains": "#10b981"},
    )
    fig.update_layout(height=500, margin={"t": 20}, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("Distance vs price")

fig = px.scatter(
    city_stats,
    x="median_dist_valencia",
    y="median_ppm2",
    size="listings",
    color="median_dist_coast",
    hover_name="city",
    color_continuous_scale="Cividis_r",
    labels={
        "median_dist_valencia": "km to Valencia",
        "median_ppm2": "Median €/m²",
        "median_dist_coast": "km to coast",
        "listings": "Listings",
    },
    title="Each circle = one city. Y-axis = €/m², X-axis = distance to Valencia, color = distance to coast",
)
fig.update_layout(height=500, margin={"t": 50})
st.plotly_chart(fig, use_container_width=True)
