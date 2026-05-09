"""Valencia Properties — multi-page Streamlit dashboard.

Run with:
    streamlit run app.py
"""

import plotly.express as px
import streamlit as st

from app_utils import fmt_eur, load_data

st.set_page_config(
    page_title="Valencia Properties",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Valencia Properties — Market Intelligence")
st.markdown(
    "An interactive analysis of **8,761 unique listings** scraped from fotocasa.es "
    "for the province of Valencia. Use the pages on the left to browse the catalog, "
    "explore the geography, find bargains, compare areas, or analyze a specific property."
)

df = load_data()

st.markdown("### Market snapshot")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total listings", f"{len(df):,}")
c2.metric("Median price", fmt_eur(df["price_eur"].median()))
c3.metric("Median €/m²", fmt_eur(df["price_per_m2"].median()))
c4.metric("Bargains found", f"{int(df['is_bargain'].sum()):,}")

st.markdown("---")

c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("Median €/m² by region")
    region_stats = (
        df.groupby(["region", "property_type"])["price_per_m2"]
        .median()
        .reset_index()
    )
    fig = px.bar(
        region_stats,
        x="region",
        y="price_per_m2",
        color="property_type",
        barmode="group",
        text="price_per_m2",
        color_discrete_map={"Casa": "#10b981", "Piso": "#3b82f6"},
        labels={"price_per_m2": "€/m²", "property_type": "Type"},
    )
    fig.update_traces(texttemplate="€%{text:,.0f}", textposition="outside")
    fig.update_layout(height=400, margin={"t": 20})
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("Property mix")
    mix = df["property_subtype"].value_counts().reset_index()
    mix.columns = ["subtype", "count"]
    fig = px.pie(
        mix,
        values="count",
        names="subtype",
        hole=0.4,
    )
    fig.update_layout(height=400, margin={"t": 20}, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("How to use this dashboard")
st.markdown(
    """
- **Browse** — filter the catalog by price, type, location, features
- **Map** — see prices geographically; spot affordable pockets
- **Bargain Finder** — listings the model thinks are priced ≥15% below fair value
- **Compare Areas** — side-by-side metrics for cities and regions
- **Property Detail** — drill into a single listing with prediction breakdown

> Data source: fotocasa.es. Price predictions: LightGBM (separate Casa & Piso models).
> See `INSIGHTS.md` and `MODEL_REPORT.md` for the analysis.
"""
)
