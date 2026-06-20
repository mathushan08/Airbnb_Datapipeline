import streamlit as st
import pandas as pd
import plotly.express as px
from app import get_db_connection

st.set_page_config(page_title="Property Analysis", page_icon="🏠", layout="wide")
st.title("🏠 Property & Amenity Analysis")

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
def load_host_tenure():
    return conn.execute("""
        SELECT h.host_tenure_years, AVG(l.price) as avg_price, AVG(l.review_scores_rating) as avg_rating
        FROM dim_hosts h
        JOIN dim_listings l ON h.host_id = l.host_id
        WHERE h.host_tenure_years IS NOT NULL AND l.price < 2000
        GROUP BY h.host_tenure_years
        ORDER BY h.host_tenure_years
    """).df()

roi = load_amenity_roi().iloc[0]
tenure = load_host_tenure().dropna(subset=['avg_rating', 'avg_price'])

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

st.markdown("---")
st.subheader("Does Host Experience Matter?")
st.markdown("Analyzing average listing price and guest ratings against the number of years the host has been on the platform.")

fig = px.scatter(
    tenure, 
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
x = tenure['host_tenure_years']
y = tenure['avg_price']
rating = tenure['avg_rating']

if len(x) > 1:
    slope, intercept = np.polyfit(x, y, 1)
    corr = np.corrcoef(x, rating)[0, 1]
else:
    slope, corr = 0, 0

trend_direction = "rises significantly" if slope > 5 else "falls significantly" if slope < -5 else "stays roughly flat"

if corr > 0.3:
    color_insight = "Longer-tenured hosts are associated with slightly higher ratings."
elif corr < -0.3:
    color_insight = "Longer-tenured hosts are associated with lower average ratings."
else:
    color_insight = "The color distribution shows no clear pattern, meaning tenure isn't strongly associated with better guest ratings."

st.markdown(f"""
<div style='color: #94a3b8; font-size: 0.85rem; line-height: 1.5; margin-top: -10px;'>
    <b>Insight:</b> The trend line shows that the average nightly price {trend_direction} (slope: £{slope:.2f}/year) as host tenure increases. 
    {color_insight} 
    <b>Takeaway:</b> Host experience (years on the platform) does not automatically translate into higher market power or superior guest satisfaction.
</div>
""", unsafe_allow_html=True)
