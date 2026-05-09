"""Browse page — filterable table view."""

import streamlit as st

from app_utils import DISPLAY_COLS, load_data, sidebar_filters

st.set_page_config(page_title="Browse", layout="wide")

st.title("Browse listings")

df = load_data()
filtered = sidebar_filters(df, key_prefix="browse")

if filtered.empty:
    st.warning("No listings match these filters. Try widening them.")
    st.stop()

st.markdown(f"**{len(filtered):,}** listings match your filters.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Median price", f"€{filtered['price_eur'].median():,.0f}")
c2.metric("Median €/m²", f"€{filtered['price_per_m2'].median():,.0f}")
c3.metric("Median surface", f"{filtered['surface_m2'].median():.0f} m²")
c4.metric("Bargains in selection", f"{int(filtered['is_bargain'].sum()):,}")

st.markdown("---")

sort_options = {
    "Price (low → high)": ("price_eur", True),
    "Price (high → low)": ("price_eur", False),
    "€/m² (low → high)": ("price_per_m2", True),
    "€/m² (high → low)": ("price_per_m2", False),
    "Bargain % (best deals first)": ("bargain_pct", False),
    "Surface (largest first)": ("surface_m2", False),
    "Newest listings": ("listing_age_days", True),
}
sort_choice = st.selectbox("Sort by", list(sort_options.keys()))
col, asc = sort_options[sort_choice]
shown = filtered.sort_values(col, ascending=asc)[DISPLAY_COLS].head(500)

st.dataframe(
    shown,
    use_container_width=True,
    hide_index=True,
    column_config={
        "title": st.column_config.TextColumn("Title", width="medium"),
        "property_subtype": st.column_config.TextColumn("Type", width="small"),
        "city": st.column_config.TextColumn("City", width="small"),
        "district": st.column_config.TextColumn("District", width="small"),
        "price_eur": st.column_config.NumberColumn("Price", format="€%d"),
        "predicted_price": st.column_config.NumberColumn("Predicted", format="€%d"),
        "bargain_pct": st.column_config.NumberColumn("Bargain %", format="%.1f%%"),
        "surface_m2": st.column_config.NumberColumn("m²", format="%d"),
        "price_per_m2": st.column_config.NumberColumn("€/m²", format="€%d"),
        "bedrooms": st.column_config.NumberColumn("Beds", format="%d"),
        "bathrooms": st.column_config.NumberColumn("Baths", format="%d"),
        "feature_count": st.column_config.NumberColumn("Features", format="%d"),
        "listing_age_days": st.column_config.NumberColumn("Days listed", format="%d"),
        "url": st.column_config.LinkColumn("Link", display_text="Open"),
    },
    height=600,
)

st.caption(f"Showing top 500 of {len(filtered):,} matching listings. Refine filters to narrow down.")
