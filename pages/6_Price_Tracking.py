"""Price Tracking page — historical price changes."""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from tracker import (
    get_listing_history,
    get_market_trend,
    get_price_drops,
    get_stats,
)

st.set_page_config(page_title="Price Tracking", layout="wide")

st.title("Price tracking")
st.caption("Historical price changes recorded each time the scraper runs.")

stats = get_stats()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Snapshots", stats["snapshots"])
c2.metric("Unique listings", f"{stats['unique_listings']:,}")
c3.metric("First snapshot", stats["earliest"] or "—")
c4.metric("Latest snapshot", stats["latest"] or "—")

if stats["snapshots"] < 2:
    st.info(
        "Only one snapshot recorded so far. Re-run the scraper + tracker after the next "
        "weekly run to populate the history. (Or trigger the GitHub Actions workflow manually.)"
    )

st.markdown("---")

st.subheader("Recent price drops")

c1, c2 = st.columns([1, 1])
with c1:
    min_days = st.slider("Min days between snapshots", 1, 90, 7)
with c2:
    min_pct = st.slider("Min drop %", 0.5, 30.0, 1.0, step=0.5)

drops = get_price_drops(min_days=min_days, min_drop_pct=min_pct)

if drops.empty:
    st.info(
        "No price drops detected. Either there's only one snapshot, no listings have dropped, "
        "or the filter thresholds are too strict."
    )
else:
    st.success(f"**{len(drops):,}** listings have dropped price by ≥{min_pct}% since the previous snapshot.")
    total_savings = drops["drop_eur"].sum()
    st.metric("Total advertised reductions", f"€{total_savings:,.0f}")

    st.dataframe(
        drops,
        hide_index=True,
        use_container_width=True,
        column_config={
            "listing_id": "ID",
            "title": st.column_config.TextColumn("Title", width="medium"),
            "url": st.column_config.LinkColumn("Link", display_text="Open"),
            "city": "City",
            "region": "Region",
            "property_subtype": "Type",
            "prev_price": st.column_config.NumberColumn("Was", format="€%d"),
            "curr_price": st.column_config.NumberColumn("Now", format="€%d"),
            "drop_eur": st.column_config.NumberColumn("Drop", format="€%d"),
            "drop_pct": st.column_config.NumberColumn("Drop %", format="%.1f%%"),
            "surface_m2": st.column_config.NumberColumn("m²", format="%d"),
            "bargain_pct": st.column_config.NumberColumn("Bargain %", format="%.1f%%"),
            "listing_age_days": st.column_config.NumberColumn("Days listed", format="%d"),
        },
        height=500,
    )

st.markdown("---")
st.subheader("Market trend over time")

trend = get_market_trend()
if len(trend) < 2:
    st.info("Need at least 2 snapshots to show a trend.")
else:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trend["snapshot_at"],
        y=trend["mean_price"],
        mode="lines+markers",
        name="Mean price",
        line=dict(color="#3b82f6", width=2),
    ))
    fig.update_layout(
        title="Mean listing price over time",
        height=400,
        margin={"t": 50},
        xaxis_title="Snapshot date",
        yaxis_title="Mean price (€)",
    )
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.bar(
        trend,
        x="snapshot_at",
        y="n_listings",
        text="n_listings",
        color="n_bargains",
        color_continuous_scale="Greens",
        title="Listings & bargains per snapshot",
    )
    fig2.update_traces(textposition="outside")
    fig2.update_layout(height=400, margin={"t": 50})
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")
st.subheader("Track a specific listing")

listing_id_input = st.text_input(
    "Listing ID",
    placeholder="e.g. 189116357",
    help="Find a listing ID on the Property Detail page or in the URL on fotocasa.",
)

if listing_id_input:
    try:
        lid = int("".join(ch for ch in listing_id_input if ch.isdigit()))
        history = get_listing_history(lid)
        if history.empty:
            st.error(f"No history found for listing {lid}.")
        else:
            st.dataframe(history, hide_index=True, use_container_width=True)
            if len(history) > 1:
                fig = px.line(
                    history,
                    x="snapshot_at",
                    y="price_eur",
                    markers=True,
                    title=f"Price history for listing {lid}",
                )
                fig.update_layout(height=350, margin={"t": 50})
                st.plotly_chart(fig, use_container_width=True)
    except ValueError:
        st.error("Invalid listing ID.")
