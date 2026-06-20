import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from app import get_db_connection

st.set_page_config(page_title="Geospatial Insights", page_icon="🗺️", layout="wide")
st.title("🗺️ Geospatial Insights")

conn = get_db_connection()

@st.cache_data(ttl=3600)
def load_geo_data():
    return conn.execute("""
        SELECT 
            g.neighbourhood,
            AVG(l.price) as avg_price,
            COUNT(*) as listing_count
        FROM dim_geography g
        JOIN dim_listings l ON g.listing_id = l.listing_id
        WHERE l.price < 5000
        GROUP BY g.neighbourhood
        ORDER BY avg_price DESC
    """).df()

@st.cache_data(ttl=3600)
def load_sample_points():
    return conn.execute("""
        SELECT g.latitude, g.longitude, l.price, l.property_type
        FROM dim_geography g
        JOIN dim_listings l ON g.listing_id = l.listing_id
        WHERE l.price < 1000
        USING SAMPLE 2000
    """).df()

geo_stats = load_geo_data()
points = load_sample_points()

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Borough Pricing Hierarchy")
    fig = px.bar(
        geo_stats.head(15),
        x='avg_price',
        y='neighbourhood',
        orientation='h',
        color='avg_price',
        color_continuous_scale='Teal',
        labels={'avg_price': 'Average Price (£)', 'neighbourhood': 'Borough'}
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", 
        paper_bgcolor="rgba(0,0,0,0)", 
        font_color="#f8fafc", 
        yaxis={'categoryorder':'total ascending'},
        coloraxis_colorbar_title_text='Avg Price (£)'
    )
    fig.update_xaxes(tickprefix="£", title="Average Nightly Price (£)")
    fig.update_yaxes(title="")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("London Listing Density (Sample)")
    
    # Create base map centered on London
    m = folium.Map(location=[51.5074, -0.1278], zoom_start=11, tiles="CartoDB dark_matter")
    
    # Add points
    for idx, row in points.iterrows():
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=2,
            color="#38bdf8",
            fill=True,
            fill_opacity=0.7,
            tooltip=f"£{row['price']} - {row['property_type']}"
        ).add_to(m)
        
    st_folium(m, width=700, height=500, returned_objects=[])
