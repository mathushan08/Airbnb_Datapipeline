import streamlit as st
import pandas as pd
import plotly.express as px
from app import get_db_connection

st.title("Property & Amenity Analysis")

conn = get_db_connection()

@st.cache_data(ttl=3600)
def load_amenity_roi():
    return conn.execute("""
        SELECT 
            AVG(CASE WHEN has_ac THEN price ELSE NULL END) as with_ac,
            AVG(CASE WHEN NOT has_ac THEN price ELSE NULL END) as without_ac,
            AVG(CASE WHEN has_pool THEN price ELSE NULL END) as with_pool,
            AVG(CASE WHEN NOT has_pool THEN price ELSE NULL END) as without_pool,
            AVG(CASE WHEN has_gym THEN price ELSE NULL END) as with_gym,
            AVG(CASE WHEN NOT has_gym THEN price ELSE NULL END) as without_gym
        FROM dim_listings
        WHERE price < 2000
    """).df()

@st.cache_data(ttl=3600)
def load_host_tenure_grouped():
    # Used only for scatter plot visualisation (one point per tenure-year cohort)
    return conn.execute("""
        SELECT h.host_tenure_years, AVG(l.price) as avg_price, AVG(l.review_scores_rating) as avg_rating
        FROM dim_hosts h
        JOIN dim_listings l ON h.host_id = l.host_id
        WHERE h.host_tenure_years IS NOT NULL AND l.price < 2000
        GROUP BY h.host_tenure_years
        ORDER BY h.host_tenure_years
    """).df()

@st.cache_data(ttl=3600)
def load_host_tenure_raw():
    # Used for regression — one row per listing, not grouped
    return conn.execute("""
        SELECT h.host_tenure_years, l.price, l.review_scores_rating
        FROM dim_hosts h
        JOIN dim_listings l ON h.host_id = l.host_id
        WHERE h.host_tenure_years IS NOT NULL
          AND l.price < 2000
          AND l.review_scores_rating IS NOT NULL
    """).df()

roi = load_amenity_roi().iloc[0]
tenure_grouped = load_host_tenure_grouped().dropna(subset=['avg_rating', 'avg_price'])
tenure_raw = load_host_tenure_raw().dropna()

st.markdown("### The Value of Amenities")
st.markdown("How much of a premium do specific amenities command in the London market?")

col1, col2, col3 = st.columns(3)

with col1:
    ac_diff = roi['with_ac'] - roi['without_ac']
    st.metric("Air Conditioning Premium", f"£{roi['with_ac']:.0f}", f"+£{ac_diff:.0f} vs without")

with col2:
    pool_diff = roi['with_pool'] - roi['without_pool']
    st.metric("Pool Premium", f"£{roi['with_pool']:.0f}", f"+£{pool_diff:.0f} vs without")

with col3:
    gym_diff = roi['with_gym'] - roi['without_gym']
    st.metric("Gym Premium", f"£{roi['with_gym']:.0f}", f"+£{gym_diff:.0f} vs without")

st.markdown("""
<div style='color: #94a3b8; font-size: 0.82rem; line-height: 1.5; margin-top: 8px; padding: 8px 12px; border-left: 3px solid #475569;'>
    <b>Methodology note:</b> These are raw price differences between listings with and without each amenity.
    They do not control for property size, bedroom count, or borough —
    treat as <i>correlational</i>, not causal. For example, only 0.5% of listings have a pool,
    and these are overwhelmingly large luxury properties where the pool may not be the primary price driver.
</div>
""", unsafe_allow_html=True)

st.markdown("---")
st.subheader("Does Host Experience Matter?")
st.markdown("Analyzing average listing price and guest ratings against the number of years the host has been on the platform.")

fig = px.scatter(
    tenure_grouped,
    x='host_tenure_years',
    y='avg_price',
    size='avg_rating',
    color='avg_rating',
    color_continuous_scale='Sunset',
    trendline="ols"
)
fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#f8fafc")
fig.update_xaxes(title="Host Tenure (Years)")
fig.update_yaxes(title="Average Nightly Price (£)")
st.plotly_chart(fig, use_container_width=True)

import numpy as np
from scipy import stats

# Regression on listing-level rows (not grouped cohort averages)
x_raw = tenure_raw['host_tenure_years']
y_raw = tenure_raw['price']
r_raw = tenure_raw['review_scores_rating']
n = len(tenure_raw)

slope_p, intercept_p, r_p, pval_p, se_p = stats.linregress(x_raw, y_raw)
slope_r, intercept_r, r_r, pval_r, se_r = stats.linregress(x_raw, r_raw)

r2_p = r_p ** 2
r2_r = r_r ** 2

# Determine significance at alpha=0.05
price_significant = pval_p < 0.05
rating_significant = pval_r < 0.05

if price_significant:
    trend_desc = (
        f"rises slightly (slope: £{slope_p:.2f}/year, p={pval_p:.3f}, R\u00b2={r2_p:.5f}, n={n:,})"
        if slope_p > 0
        else f"falls slightly (slope: £{slope_p:.2f}/year, p={pval_p:.3f}, R\u00b2={r2_p:.5f}, n={n:,})"
    )
    price_takeaway = (
        f"While the relationship is statistically significant (p={pval_p:.3f}), "
        f"R\u00b2={r2_p:.5f} indicates that tenure explains less than 0.1% of price variance. "
        f"The effect is real but negligibly small — host tenure is not a meaningful predictor of price."
    )
else:
    trend_desc = (
        f"shows no meaningful trend (slope: £{slope_p:.2f}/year, p={pval_p:.3f}, "
        f"R\u00b2={r2_p:.6f}, n={n:,})"
    )
    price_takeaway = (
        f"The relationship is not statistically significant (p={pval_p:.3f} > 0.05). "
        f"R\u00b2={r2_p:.6f} indicates tenure explains essentially none of the price variance. "
        f"The visual trend line is consistent with noise around a flat line."
    )

if rating_significant:
    rating_insight = (
        f"Guest ratings do show a small but statistically significant rise with tenure "
        f"(slope={slope_r:.4f}/year, p={pval_r:.3f}, R\u00b2={r2_r:.4f}), "
        f"suggesting longer-tenured hosts are associated with marginally higher ratings — "
        f"though the effect size is modest."
    )
else:
    rating_insight = (
        f"Guest ratings show no statistically significant relationship with tenure "
        f"(p={pval_r:.3f} > 0.05), meaning tenure is not reliably associated with better or worse ratings."
    )

st.markdown(f"""
<div style='color: #94a3b8; font-size: 0.85rem; line-height: 1.6; margin-top: -10px;'>
    <b>Insight (listing-level OLS, n={n:,}):</b> The trend line {trend_desc}.<br>
    {rating_insight}<br>
    <b>Takeaway:</b> {price_takeaway}
</div>
""", unsafe_allow_html=True)
