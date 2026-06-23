import streamlit as st
import pandas as pd
import plotly.express as px
from Home import get_db_connection

st.title("Market Overview")
conn = get_db_connection()


# Load high-level KPIs
@st.cache_data(ttl=3600)
def load_kpis():
    total = conn.execute("""
        SELECT COUNT(*) as total_listings
        FROM dim_listings
    """).df()
    stats = conn.execute("""
        SELECT
            AVG(price) as avg_price,
            AVG(number_of_reviews) as avg_reviews
        FROM dim_listings
        WHERE price < 5000
    """).df()
    return total.join(stats)

@st.cache_data(ttl=3600)
def load_room_types():
    return conn.execute("""
        SELECT room_type, COUNT(*) as count, AVG(price) as avg_price
        FROM dim_listings
        GROUP BY room_type
        ORDER BY count DESC
    """).df()

@st.cache_data(ttl=3600)
def load_superhost_stats():
    return conn.execute("""
        SELECT h.host_is_superhost, COUNT(*) as count
        FROM dim_listings l
        JOIN dim_hosts h ON l.host_id = h.host_id
        GROUP BY h.host_is_superhost
    """).df()

kpis = load_kpis()
room_types = load_room_types()
superhosts = load_superhost_stats()

# Metrics Row
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Active Listings", f"{kpis['total_listings'][0]:,}")
with col2:
    st.metric("Average Nightly Price", f"£{kpis['avg_price'][0]:.2f}")
with col3:
    st.metric("Average Reviews per Property", f"{kpis['avg_reviews'][0]:.1f}")

st.markdown("---")

# Charts Row
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("Inventory by Room Type")
    fig1 = px.pie(
        room_types, 
        values='count', 
        names='room_type',
        hole=0.4,
        color_discrete_sequence=['#38bdf8', '#818cf8', '#fbbf24', '#f87171']
    )
    fig1.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#f8fafc")
    st.plotly_chart(fig1, use_container_width=True)
    
    room_types['pct'] = room_types['count'] / room_types['count'].sum() * 100
    top_room = room_types.iloc[0]['room_type']
    top_pct = room_types.iloc[0]['pct']
    bottom_pct = room_types.iloc[-1]['pct']
    second_bottom_pct = room_types.iloc[-2]['pct'] if len(room_types) > 2 else 0

    st.markdown(f"""
    <div style='color: #94a3b8; font-size: 0.85rem; line-height: 1.5; margin-top: -10px;'>
        <b>Insight:</b> '{top_room}' dominates the inventory, making up {top_pct:.1f}% of all properties. The two smallest categories are negligible, accounting for ~{(bottom_pct + second_bottom_pct):.1f}% combined.
    </div>
    """, unsafe_allow_html=True)

with col_chart2:
    st.subheader("Superhost Market Share")
    sh_labels = superhosts['host_is_superhost'].map({True: 'Superhost', False: 'Regular Host', None: 'Unknown'})
    fig2 = px.bar(
        superhosts,
        x=sh_labels,
        y='count',
        color=sh_labels,
        color_discrete_sequence=['#38bdf8', '#475569', '#1e293b']
    )
    fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#f8fafc", showlegend=False)
    fig2.update_yaxes(title="Total Listings")
    fig2.update_xaxes(title="")
    st.plotly_chart(fig2, use_container_width=True)
    
    sh_total = superhosts['count'].sum()
    sh_count = superhosts[superhosts['host_is_superhost'] == True]['count'].sum()
    reg_count = superhosts[superhosts['host_is_superhost'] == False]['count'].sum()
    
    st.markdown(f"""
    <div style='color: #94a3b8; font-size: 0.85rem; line-height: 1.5; margin-top: -10px;'>
        <b>Insight:</b> Regular hosts account for {(reg_count / sh_total * 100):.1f}% of the total active inventory, compared to {(sh_count / sh_total * 100):.1f}% managed by Superhosts. Note this reflects the share of <i>listings</i>, not individual hosts or revenue.
    </div>
    """, unsafe_allow_html=True)
