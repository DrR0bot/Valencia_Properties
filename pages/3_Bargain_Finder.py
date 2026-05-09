"""Bargain Finder page — listings priced below model prediction."""

import plotly.express as px
import streamlit as st

from app_utils import DISPLAY_COLS, listing_card, load_data, sidebar_filters

st.set_page_config(page_title="Bargain Finder", layout="wide")

st.title("Bargain finder")
st.markdown(
    "Listings priced **below** their model-predicted fair value. "
    "A *Bargain %* of `+25%` means the listing is priced 25% below predicted price."
)
st.warning(
    "⚠️ The model only sees what's in the data. A 'bargain' might be a property in poor condition, "
    "with legal issues, or in a noisy spot. **Always inspect in person before buying.**"
)

df = load_data()
filtered = sidebar_filters(df, key_prefix="bargain")

bargains = filtered[filtered["is_bargain"]].copy()

if bargains.empty:
    st.info("No bargains match these filters. Widen the filters or try a different region.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Bargains found", f"{len(bargains):,}")
c2.metric("Avg bargain %", f"+{bargains['bargain_pct'].mean():.1f}%")
c3.metric("Avg savings vs predicted", f"€{bargains['bargain_eur'].mean():,.0f}")
c4.metric("Total potential savings", f"€{bargains['bargain_eur'].sum():,.0f}")

st.markdown("---")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Bargains by region")
    region_counts = (
        bargains.groupby("region")
        .agg(count=("id", "count"), avg_bargain_pct=("bargain_pct", "mean"))
        .reset_index()
        .sort_values("count", ascending=True)
    )
    fig = px.bar(
        region_counts,
        x="count",
        y="region",
        orientation="h",
        color="avg_bargain_pct",
        color_continuous_scale="Greens",
        text="count",
        labels={"avg_bargain_pct": "Avg bargain %"},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(height=350, margin={"t": 20})
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("Bargain distribution")
    fig = px.histogram(
        bargains,
        x="bargain_pct",
        nbins=30,
        color_discrete_sequence=["#10b981"],
    )
    fig.update_layout(
        height=350, margin={"t": 20},
        xaxis_title="Bargain %", yaxis_title="Listings",
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("Top bargains")

sort_choice = st.radio(
    "Sort by",
    ["Highest bargain %", "Highest savings (€)", "Newest listings"],
    horizontal=True,
)
sort_map = {
    "Highest bargain %": ("bargain_pct", False),
    "Highest savings (€)": ("bargain_eur", False),
    "Newest listings": ("listing_age_days", True),
}
col, asc = sort_map[sort_choice]
top_n = st.slider("How many to show", 10, 100, 30, step=10)

top = bargains.sort_values(col, ascending=asc).head(top_n)

view_mode = st.radio("View as", ["Table", "Cards"], horizontal=True)
if view_mode == "Table":
    st.dataframe(
        top[DISPLAY_COLS],
        use_container_width=True,
        hide_index=True,
        column_config={
            "price_eur": st.column_config.NumberColumn("Price", format="€%d"),
            "predicted_price": st.column_config.NumberColumn("Predicted", format="€%d"),
            "bargain_pct": st.column_config.NumberColumn("Bargain %", format="%.1f%%"),
            "surface_m2": st.column_config.NumberColumn("m²", format="%d"),
            "price_per_m2": st.column_config.NumberColumn("€/m²", format="€%d"),
            "url": st.column_config.LinkColumn("Link", display_text="Open"),
        },
        height=500,
    )
else:
    for _, row in top.iterrows():
        listing_card(row)
