import streamlit as st
import pandas as pd
import numpy as np
import joblib
import os
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import shap
from app import get_db_connection

st.title("Price Advisor")
st.markdown("Configure a hypothetical listing and get an instant data-backed nightly price estimate.")

MODEL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'price_model.pkl')
)


@st.cache_resource
def load_model():
    return joblib.load(MODEL_PATH)


@st.cache_data(ttl=3600)
def load_comparables(borough, room_type, bedrooms_val):
    conn = get_db_connection()
    return conn.execute("""
        SELECT
            l.listing_name,
            g.neighbourhood  AS borough,
            l.room_type,
            COALESCE(l.bedrooms, 1)  AS bedrooms,
            COALESCE(l.bathrooms, 1) AS bathrooms,
            l.accommodates,
            l.price,
            l.number_of_reviews,
            l.review_scores_rating
        FROM dim_listings l
        JOIN dim_geography g ON l.listing_id = g.listing_id
        WHERE g.neighbourhood = ?
          AND l.room_type     = ?
          AND ABS(COALESCE(l.bedrooms, 1) - ?) <= 1
          AND l.price BETWEEN 10 AND 2000
        ORDER BY ABS(COALESCE(l.bedrooms, 1) - ?) ASC,
                 l.number_of_reviews DESC
        LIMIT 5
    """, [borough, room_type, bedrooms_val, bedrooms_val]).df()


artifact = load_model()
model      = artifact['model']
le_room    = artifact['le_room']
le_borough = artifact['le_borough']
feat_cols  = artifact['feature_cols']
metrics    = artifact['metrics']
boroughs   = artifact['borough_list']
room_types = artifact['room_types']

with st.expander("ℹ️ About this model"):
    st.markdown(
        f"This price prediction engine is powered by an XGBoost machine learning model trained on **61,712** real London Airbnb listings. "
        f"When evaluated on a held-out test set, it achieved an **R² of {metrics['r2']:.2f}** and an average error (MAE) of **£{metrics['mae']:.0f}**."
    )

st.markdown("### Configure Your Listing")

col1, col2 = st.columns(2)

with col1:
    borough   = st.selectbox("Borough", boroughs, index=boroughs.index("Westminster"))
    room_type = st.selectbox("Room Type", room_types, index=room_types.index("Entire home/apt"))
    bedrooms  = st.slider("Bedrooms", 0, 10, 2)
    bathrooms = st.slider("Bathrooms", 1, 8, 1)

with col2:
    accommodates  = st.slider("Accommodates (guests)", 1, 16, 4)
    beds          = st.slider("Beds", 1, 12, 2)
    amenity_count = st.slider("Total Amenity Count", 0, 60, 20)

st.markdown("#### Amenities")
a1, a2, a3, a4, a5 = st.columns(5)
has_wifi        = a1.checkbox("WiFi",        value=True)
has_kitchen     = a2.checkbox("Kitchen",     value=True)
has_ac          = a3.checkbox("AC",          value=False)
has_parking     = a4.checkbox("Parking",     value=False)
has_washer      = a5.checkbox("Washer",      value=True)
has_tv          = a1.checkbox("TV",          value=True)
has_elevator    = a2.checkbox("Elevator",    value=False)
has_pool        = a3.checkbox("Pool",        value=False)
has_gym         = a4.checkbox("Gym",         value=False)
has_hot_tub     = a5.checkbox("Hot Tub",     value=False)
has_breakfast   = a1.checkbox("Breakfast",   value=False)
is_pet_friendly = a2.checkbox("Pet Friendly",value=False)
has_self_checkin= a3.checkbox("Self Check-in",value=True)

st.markdown("---")

if st.button("Get Price Estimate", type="primary", use_container_width=True):

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

    predicted = float(model.predict(input_row)[0])
    mae       = metrics['mae']
    low, high = max(10, predicted - mae), predicted + mae

    st.markdown("### Estimated Nightly Price")
    r1, r2, r3 = st.columns(3)
    r1.metric("Lower bound", f"£{low:.0f}")
    r2.metric("Predicted",   f"£{predicted:.0f}", delta="Model estimate")
    r3.metric("Upper bound", f"£{high:.0f}")

    st.markdown(
        f"<div style='color:#94a3b8; font-size:0.82rem;'>"
        f"Range based on model MAE of £{mae:.0f} on the held-out test set (R²={metrics['r2']:.2f})."
        f"</div>",
        unsafe_allow_html=True
    )

    # SHAP waterfall chart
    st.markdown("#### What drives this price?")
    explainer  = shap.TreeExplainer(model)
    shap_vals  = explainer.shap_values(input_row)
    shap_arr   = shap_vals[0]

    feature_labels = {
        'room_type_enc':    f'Room type ({room_type})',
        'bedrooms':         f'Bedrooms ({bedrooms})',
        'bathrooms':        f'Bathrooms ({bathrooms})',
        'accommodates':     f'Accommodates ({accommodates})',
        'beds':             f'Beds ({beds})',
        'amenity_count':    f'Amenity count ({amenity_count})',
        'neighbourhood_enc':f'Borough ({borough})',
        'has_wifi':         'WiFi',
        'has_kitchen':      'Kitchen',
        'has_parking':      'Parking',
        'has_ac':           'Air conditioning',
        'has_washer':       'Washer',
        'has_tv':           'TV',
        'has_elevator':     'Elevator',
        'has_pool':         'Pool',
        'has_gym':          'Gym',
        'has_hot_tub':      'Hot tub',
        'has_breakfast':    'Breakfast',
        'is_pet_friendly':  'Pet friendly',
        'has_self_checkin': 'Self check-in',
    }

    shap_df = pd.DataFrame({
        'Feature': [feature_labels.get(f, f) for f in feat_cols],
        'Impact':  shap_arr
    }).sort_values('Impact', key=abs, ascending=True).tail(12)

    shap_df['Color'] = shap_df['Impact'].apply(lambda v: '#38bdf8' if v >= 0 else '#f87171')

    fig = go.Figure(go.Bar(
        x=shap_df['Impact'],
        y=shap_df['Feature'],
        orientation='h',
        marker_color=shap_df['Color'],
    ))
    fig.add_vline(x=0, line_width=1, line_color='#475569')
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#f8fafc',
        xaxis_title='Price impact (£)',
        margin=dict(l=10, r=10, t=10, b=10),
        height=380
    )
    fig.update_xaxes(tickprefix='£')
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Blue bars push the price up. Red bars pull it down. Length = magnitude of impact.")

    # Comparable listings
    st.markdown("#### Comparable Listings on the Market")
    comps = load_comparables(borough, room_type, bedrooms)
    if not comps.empty:
        comps_display = comps.rename(columns={
            'listing_name':          'Listing Name',
            'borough':               'Borough',
            'room_type':             'Room Type',
            'bedrooms':              'Beds',
            'bathrooms':             'Baths',
            'accommodates':          'Guests',
            'price':                 'Price/night',
            'number_of_reviews':     'Reviews',
            'review_scores_rating':  'Rating'
        })
        comps_display['Price/night'] = comps_display['Price/night'].apply(lambda x: f"£{x:.0f}")
        comps_display['Rating'] = comps_display['Rating'].apply(
            lambda x: f"{x:.1f}" if pd.notnull(x) else "N/A"
        )
        st.dataframe(comps_display.reset_index(drop=True), use_container_width=True)

        actual_avg = comps['price'].mean()
        st.markdown(
            f"<div style='color:#94a3b8; font-size:0.82rem;'>"
            f"Average price of these {len(comps)} comparable listings: £{actual_avg:.0f}/night. "
            f"Model prediction of £{predicted:.0f} is "
            f"{'within' if abs(predicted - actual_avg) < mae else 'outside'} the MAE range."
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.info("No close comparables found for this exact configuration. Try adjusting borough or bedroom count.")
