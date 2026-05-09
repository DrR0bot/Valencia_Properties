"""Property Detail page — analyze a single listing."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app_utils import FEATURE_COLS, fmt_eur, fmt_int, fmt_pct, load_data

st.set_page_config(page_title="Property Detail", layout="wide")

st.title("Property detail")
st.caption("Pick a listing to see its prediction breakdown and comparable properties nearby.")

df = load_data()

c1, c2 = st.columns([1, 1])
with c1:
    method = st.radio(
        "Find listing by",
        ["URL or ID", "Search & pick from dropdown"],
        horizontal=True,
    )

selected = None

if method == "URL or ID":
    user_input = st.text_input(
        "Paste a fotocasa URL or listing ID",
        placeholder="e.g. 189116357 or https://www.fotocasa.es/.../189116357/d",
    )
    if user_input:
        ident = user_input.strip()
        digits = "".join(ch for ch in ident if ch.isdigit())
        match = df[df["id"] == int(digits)] if digits else df.iloc[0:0]
        if match.empty:
            st.error("No listing found with that ID. It may have been removed or scraped under a different ID.")
        else:
            selected = match.iloc[0]
else:
    cities = sorted(df["city"].dropna().unique())
    chosen_city = st.selectbox("City", cities, index=cities.index("Valencia Capital") if "Valencia Capital" in cities else 0)
    listings_in_city = df[df["city"] == chosen_city].copy()
    listings_in_city["label"] = (
        listings_in_city["property_subtype"]
        + " • " + listings_in_city["district"].fillna("—")
        + " • " + listings_in_city["price_eur"].map(lambda v: f"€{v:,.0f}")
        + " • " + listings_in_city["surface_m2"].astype(int).astype(str) + " m²"
    )
    chosen = st.selectbox("Listing", listings_in_city["label"].tolist())
    if chosen:
        selected = listings_in_city[listings_in_city["label"] == chosen].iloc[0]

if selected is None:
    st.info("Pick a listing above to see its details.")
    st.stop()

st.markdown("---")
st.subheader(f"{selected.get('property_subtype', '')} en {selected.get('district') or selected.get('city', '')}")
st.markdown(f"[Open original listing on fotocasa →]({selected['url']})")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Asking price", fmt_eur(selected["price_eur"]))
c2.metric("Predicted price", fmt_eur(selected.get("predicted_price")))
delta = selected.get("bargain_pct", 0) or 0
c3.metric("Bargain %", fmt_pct(delta), delta_color="normal" if delta > 0 else "inverse")
c4.metric("€/m²", fmt_eur(selected["price_per_m2"]))

st.markdown("---")
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("**Specs**")
    st.write(f"Surface: **{selected['surface_m2']:.0f} m²**")
    st.write(f"Bedrooms: **{fmt_int(selected['bedrooms'])}**")
    st.write(f"Bathrooms: **{fmt_int(selected['bathrooms'])}**")
    st.write(f"Floor: **{fmt_int(selected['floor'])}**")
    st.write(f"Subtype: **{selected['property_subtype']}**")
    st.write(f"Conservation: **{selected.get('conservation_status') or '—'}**")
    st.write(f"Antiquity (years): **{fmt_int(selected.get('antiquity'))}**")

with c2:
    st.markdown("**Location**")
    st.write(f"City: **{selected['city']}**")
    st.write(f"District: **{selected.get('district') or '—'}**")
    st.write(f"Region: **{selected['region']}**")
    st.write(f"County: **{selected.get('county') or '—'}**")
    st.write(f"Distance to Valencia: **{selected['distance_to_valencia_km']:.1f} km**")
    st.write(f"Distance to coast: **{selected['distance_to_coast_km']:.1f} km**")

with c3:
    st.markdown("**Features present**")
    present = [label for col, label in FEATURE_COLS if selected.get(col)]
    if present:
        for label in present:
            st.write(f"✓ {label}")
    else:
        st.write("No standard amenities listed.")

st.markdown("---")
st.subheader("Mini-map")

lat, lon = selected["latitude"], selected["longitude"]
nearby = df[
    (abs(df["latitude"] - lat) < 0.05)
    & (abs(df["longitude"] - lon) < 0.05)
    & (df["id"] != selected["id"])
].copy()
nearby["highlight"] = "Comparable"
this_one = pd.DataFrame([selected]).copy()
this_one["highlight"] = "This listing"
combo = pd.concat([nearby, this_one], ignore_index=True)

fig = px.scatter_mapbox(
    combo,
    lat="latitude",
    lon="longitude",
    color="highlight",
    size="surface_m2",
    size_max=18,
    hover_data={
        "city": True,
        "price_eur": ":,.0f",
        "surface_m2": True,
        "bargain_pct": ":.1f",
    },
    color_discrete_map={"This listing": "#ef4444", "Comparable": "#3b82f6"},
    zoom=13,
    center={"lat": lat, "lon": lon},
    height=450,
)
fig.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("Comparable listings (≤5km, same property type)")

comparable = df[
    (df["property_type"] == selected["property_type"])
    & (((df["latitude"] - lat) ** 2 + (df["longitude"] - lon) ** 2) ** 0.5 < 0.05)
    & (df["id"] != selected["id"])
].copy()

if comparable.empty:
    st.info("No comparable listings found nearby.")
else:
    comparable["surface_diff"] = (comparable["surface_m2"] - selected["surface_m2"]).abs()
    closest = comparable.nsmallest(10, "surface_diff")[
        ["property_subtype", "city", "district", "price_eur",
         "predicted_price", "bargain_pct", "surface_m2",
         "price_per_m2", "bedrooms", "url"]
    ]
    st.dataframe(
        closest,
        use_container_width=True,
        hide_index=True,
        column_config={
            "price_eur": st.column_config.NumberColumn("Price", format="€%d"),
            "predicted_price": st.column_config.NumberColumn("Predicted", format="€%d"),
            "bargain_pct": st.column_config.NumberColumn("Bargain %", format="%.1f%%"),
            "surface_m2": st.column_config.NumberColumn("m²", format="%d"),
            "price_per_m2": st.column_config.NumberColumn("€/m²", format="€%d"),
            "bedrooms": st.column_config.NumberColumn("Beds", format="%d"),
            "url": st.column_config.LinkColumn("Link", display_text="Open"),
        },
    )

    st.markdown("**€/m² distribution of nearby comparables (red line = this listing)**")
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=comparable["price_per_m2"],
        nbinsx=20,
        marker_color="#3b82f6",
        name="Comparables",
    ))
    fig.add_vline(
        x=selected["price_per_m2"],
        line_color="red",
        line_width=2,
        annotation_text=f"This: €{selected['price_per_m2']:,.0f}/m²",
        annotation_position="top right",
    )
    fig.update_layout(
        height=350,
        xaxis_title="€/m²", yaxis_title="Comparable count",
        margin={"t": 20},
    )
    st.plotly_chart(fig, use_container_width=True)
