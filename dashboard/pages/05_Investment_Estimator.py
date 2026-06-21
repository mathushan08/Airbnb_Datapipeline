import streamlit as st
import pandas as pd
import numpy as np
import joblib
import os
import plotly.express as px
import plotly.graph_objects as go
from app import get_db_connection

st.title("Investment Estimator")
st.markdown(
    "Evaluate the revenue potential of an Airbnb property in any London borough. "
    "Configure a hypothetical property, then adjust the occupancy assumption to stress-test your scenario."
)

MODEL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'price_model.pkl')
)

@st.cache_resource
def load_model():
    return joblib.load(MODEL_PATH)

@st.cache_data(ttl=3600)
def load_borough_occupancy():
    conn = get_db_connection()
    return conn.execute("""
        SELECT
            g.neighbourhood                                               AS borough,
            COUNT(CASE WHEN NOT fc.available THEN 1 END) * 1.0 / COUNT(*) AS occupancy_rate,
            COUNT(DISTINCT fc.listing_id)                                 AS listing_count
        FROM fact_calendar fc
        JOIN dim_geography g ON fc.listing_id = g.listing_id
        GROUP BY g.neighbourhood
        ORDER BY occupancy_rate DESC
    """).df()

@st.cache_data(ttl=3600)
def load_borough_avg_prices():
    conn = get_db_connection()
    return conn.execute("""
        SELECT
            g.neighbourhood AS borough,
            l.room_type,
            AVG(l.price)    AS avg_price,
            COUNT(*)        AS listing_count
        FROM dim_listings l
        JOIN dim_geography g ON l.listing_id = g.listing_id
        WHERE l.price BETWEEN 10 AND 2000
        GROUP BY g.neighbourhood, l.room_type
    """).df()

artifact      = load_model()
model         = artifact['model']
le_room       = artifact['le_room']
le_borough    = artifact['le_borough']
feat_cols     = artifact['feature_cols']
metrics       = artifact['metrics']
boroughs      = artifact['borough_list']
room_types    = artifact['room_types']
occ_df        = load_borough_occupancy()
avg_price_df  = load_borough_avg_prices()

occ_map = dict(zip(occ_df['borough'], occ_df['occupancy_rate']))

st.sidebar.markdown("---")
st.sidebar.markdown(
    f"**Model quality (test set)**  \n"
    f"MAE: £{metrics['mae']:.0f} &nbsp; R²: {metrics['r2']:.2f}"
)

st.markdown("### Property Configuration")
col1, col2 = st.columns(2)

with col1:
    borough   = st.selectbox("Target Borough", boroughs, index=boroughs.index("Westminster"))
    room_type = st.selectbox("Room Type", room_types, index=room_types.index("Entire home/apt"))
    bedrooms  = st.slider("Bedrooms", 0, 10, 2)
    bathrooms = st.slider("Bathrooms", 1, 8, 1)

with col2:
    accommodates  = st.slider("Accommodates (guests)", 1, 16, 4)
    beds          = st.slider("Beds", 1, 12, 2)
    amenity_count = st.slider("Total Amenity Count", 0, 60, 25)

st.markdown("#### Standard Amenities")
a1, a2, a3, a4 = st.columns(4)
has_wifi        = a1.checkbox("WiFi",         value=True)
has_kitchen     = a2.checkbox("Kitchen",      value=True)
has_ac          = a3.checkbox("AC",           value=False)
has_washer      = a4.checkbox("Washer",       value=True)
has_tv          = a1.checkbox("TV",           value=True)
has_elevator    = a2.checkbox("Elevator",     value=False)
has_parking     = a3.checkbox("Parking",      value=False)
has_self_checkin= a4.checkbox("Self Check-in",value=True)
has_pool        = a1.checkbox("Pool",         value=False)
has_gym         = a2.checkbox("Gym",          value=False)
has_hot_tub     = a3.checkbox("Hot Tub",      value=False)
has_breakfast   = a4.checkbox("Breakfast",    value=False)
is_pet_friendly = a1.checkbox("Pet Friendly", value=False)

st.markdown("---")
st.markdown("### Occupancy Assumption")

calendar_occ = occ_map.get(borough, 0.45)
calendar_occ_pct = round(calendar_occ * 100)  # convert to integer % for display

st.caption(
    f"Historical occupancy for **{borough}** (from calendar data across {len(occ_df):,} borough records): "
    f"**{calendar_occ:.1%}**. "
    f"Adjust the slider below to stress-test different scenarios. "
    f"Note: this figure is based on availability flags, not confirmed bookings — it may slightly overstate true occupancy."
)

occupancy_pct = st.slider(
    "Occupancy Rate",
    min_value=30,
    max_value=95,
    value=max(30, min(95, calendar_occ_pct)),
    step=1,
    format="%d%%",
    help="Percentage of nights per month the property is booked. Based on Inside Airbnb calendar data — drag to model best/worst case scenarios."
)
occupancy = occupancy_pct / 100  # convert back to decimal for revenue calculations

st.markdown("---")

if st.button("Calculate Revenue Potential", type="primary", use_container_width=True):

    room_enc    = le_room.transform([room_type])[0]
    borough_enc = le_borough.transform([borough])[0]

    input_row = pd.DataFrame([{
        'room_type_enc':    room_enc,
        'bedrooms':         bedrooms,
        'bathrooms':        bathrooms,
        'accommodates':     accommodates,
        'beds':             beds,
        'amenity_count':    amenity_count,
        'neighbourhood_enc':borough_enc,
        'has_wifi':         int(has_wifi),
        'has_kitchen':      int(has_kitchen),
        'has_parking':      int(has_parking),
        'has_ac':           int(has_ac),
        'has_washer':       int(has_washer),
        'has_tv':           int(has_tv),
        'has_elevator':     int(has_elevator),
        'has_pool':         int(has_pool),
        'has_gym':          int(has_gym),
        'has_hot_tub':      int(has_hot_tub),
        'has_breakfast':    int(has_breakfast),
        'is_pet_friendly':  int(is_pet_friendly),
        'has_self_checkin': int(has_self_checkin),
    }])

    predicted_price = float(model.predict(input_row)[0])
    booked_days_pm  = 30 * occupancy
    monthly_rev     = predicted_price * booked_days_pm
    annual_rev      = monthly_rev * 12

    st.markdown("### Revenue Projections")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Predicted Nightly Rate", f"£{predicted_price:.0f}")
    m2.metric("Occupancy (assumed)",    f"{occupancy:.0%}")
    m3.metric("Est. Monthly Revenue",   f"£{monthly_rev:,.0f}")
    m4.metric("Est. Annual Revenue",    f"£{annual_rev:,.0f}")

    st.markdown(
        f"<div style='color:#94a3b8; font-size:0.82rem; margin-top:4px;'>"
        f"Based on {booked_days_pm:.0f} booked nights/month at £{predicted_price:.0f}/night. "
        f"Excludes platform fees (~3%), cleaning costs, and taxes."
        f"</div>",
        unsafe_allow_html=True
    )

    # Borough comparison chart
    st.markdown("### Borough Comparison")
    st.caption(
        f"Predicted nightly rate for a **{bedrooms}-bed {room_type}** across all London boroughs, "
        f"multiplied by each borough's actual historical occupancy rate."
    )

    rows = []
    for b in boroughs:
        try:
            b_enc = le_borough.transform([b])[0]
        except Exception:
            continue
        row = input_row.copy()
        row['neighbourhood_enc'] = b_enc
        price_b  = float(model.predict(row)[0])
        occ_b    = occ_map.get(b, calendar_occ)
        rev_b    = price_b * 30 * occ_b
        rows.append({
            'Borough':           b,
            'Predicted Price':   price_b,
            'Occupancy':         occ_b,
            'Monthly Revenue':   rev_b,
            'Selected':          b == borough
        })

    comp_df = pd.DataFrame(rows).sort_values('Monthly Revenue', ascending=True)
    comp_df['Label'] = comp_df['Borough'].apply(
        lambda x: f"<b>{x}</b>" if x == borough else x
    )

    bar_colors = comp_df['Selected'].apply(
        lambda s: '#38bdf8' if s else '#475569'
    ).tolist()

    fig = go.Figure(go.Bar(
        x=comp_df['Monthly Revenue'],
        y=comp_df['Borough'],
        orientation='h',
        marker_color=bar_colors,
        text=comp_df['Monthly Revenue'].apply(lambda v: f"£{v:,.0f}"),
        textposition='outside'
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#f8fafc',
        xaxis_title='Estimated Monthly Revenue (£)',
        height=700,
        margin=dict(l=10, r=80, t=10, b=10)
    )
    fig.update_xaxes(tickprefix='£')
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Highlighted bar = your selected borough. Revenue = predicted price x borough occupancy x 30 days. "
        "Occupancy figures are derived from Inside Airbnb calendar data and may include host-blocked dates."
    )

    # Summary table
    summary = comp_df[['Borough', 'Predicted Price', 'Occupancy', 'Monthly Revenue']].copy()
    summary = summary.sort_values('Monthly Revenue', ascending=False).reset_index(drop=True)
    summary['Predicted Price']  = summary['Predicted Price'].apply(lambda v: f"£{v:.0f}")
    summary['Occupancy']        = summary['Occupancy'].apply(lambda v: f"{v:.1%}")
    summary['Monthly Revenue']  = summary['Monthly Revenue'].apply(lambda v: f"£{v:,.0f}")
    summary.index += 1

    selected_rank = summary.index[summary['Borough'] == borough].tolist()
    st.markdown(
        f"**{borough}** ranks **#{selected_rank[0] if selected_rank else 'N/A'}** "
        f"out of {len(boroughs)} boroughs for this property configuration."
    )
    st.dataframe(summary, use_container_width=True)
