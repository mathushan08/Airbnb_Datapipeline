import streamlit as st
import duckdb
import os

st.set_page_config(
    page_title="Airbnb Market Intelligence",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply custom CSS
def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

try:
    load_css("dashboard/style.css")
except Exception:
    pass

# Helper function to get DuckDB connection
@st.cache_resource
def get_db_connection():
    # Construct absolute path to ensure reliability across environments
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'gold', 'airbnb_london.duckdb'))
    return duckdb.connect(db_path, read_only=True)

st.title("Airbnb Market Intelligence — London")
st.markdown("### 🇬🇧 Welcome to the Medallion Data Platform")

st.markdown("""
This executive dashboard serves as the **Gold Layer** presentation tier.
It queries a highly-optimized DuckDB star schema containing millions of cleaned and validated Airbnb records.

### Navigate the Platform:
👈 Use the **sidebar** to explore:
1. **Market Overview**: High-level KPIs and pricing trends.
2. **Geospatial Insights**: Interactive borough heatmaps.
3. **Property Analysis**: ROI breakdown by amenities and host types.
""")

st.info("💡 **Pro Tip**: The data driving this dashboard is refreshed directly from the underlying data warehouse.", icon="💡")

# Run a simple validation query to prove DB is connected
try:
    conn = get_db_connection()
    count = conn.execute("SELECT count(*) FROM dim_listings").fetchone()[0]
    st.success(f"✅ Warehouse Connected. Currently tracking **{count:,}** active listings.")
except Exception as e:
    st.error(f"❌ Could not connect to the Data Warehouse. Please ensure Phase 3 (dbt) has been executed. Error: {e}")
