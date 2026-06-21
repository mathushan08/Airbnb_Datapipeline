import streamlit as st
import duckdb
import os
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Home | Airbnb Market Intelligence",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

try:
    load_css("dashboard/style.css")
except Exception:
    pass

# Inject sidebar active-page highlight, clean up nav styling, and force full nav expansion
st.markdown("""
<style>
[data-testid="stSidebarNav"] li:first-child a {
    font-weight: 700 !important;
    border-left: 3px solid #38bdf8;
    padding-left: 8px;
    color: #f8fafc !important;
}
[data-testid="stSidebarNav"] li a {
    color: #94a3b8 !important;
    font-size: 0.95rem;
}
[data-testid="stSidebarNav"] li a:hover {
    color: #f8fafc !important;
}

/* Force all pages to always show — remove the collapse chevron */
[data-testid="stSidebarNav"] ul {
    max-height: none !important;
    overflow: visible !important;
}
[data-testid="stSidebarNavItems"] {
    max-height: none !important;
    overflow-y: visible !important;
}
[data-testid="stSidebarNavSeparator"],
[data-testid="stSidebarNav"] + div > button {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

# JavaScript: auto-click the sidebar nav expand button so all pages are always visible
components.html("""
<script>
(function expandSidebarNav() {
    function tryExpand() {
        // Find expand buttons inside the sidebar nav area in the parent frame
        var doc = window.parent.document;
        var btns = doc.querySelectorAll(
            '[data-testid="stSidebarNavSeparator"] button, ' +
            '[data-testid="stSidebarNav"] ~ div button'
        );
        btns.forEach(function(btn) { btn.click(); });
    }
    // Run at 300ms, 800ms and 1800ms to catch slow renders
    setTimeout(tryExpand, 300);
    setTimeout(tryExpand, 800);
    setTimeout(tryExpand, 1800);
})();
</script>
""", height=0, scrolling=False)



@st.cache_resource
def get_db_connection():
    db_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'data', 'gold', 'airbnb_london.duckdb')
    )
    return duckdb.connect(db_path, read_only=True)


st.title("Airbnb Market Intelligence: London")
st.markdown("### Welcome to the Medallion Data Platform")

try:
    conn = get_db_connection()

    listing_count  = conn.execute("SELECT count(*) FROM dim_listings").fetchone()[0]
    review_count   = conn.execute("SELECT count(*) FROM fact_reviews").fetchone()[0]
    calendar_count = conn.execute("SELECT count(*) FROM fact_calendar").fetchone()[0]
    total_records  = listing_count + review_count + calendar_count

    st.markdown(f"""
This executive dashboard is the **Gold Layer** presentation tier of a Medallion data pipeline.
It queries a highly-optimised DuckDB star schema containing **{total_records:,} records** across
reviews, pricing history, and calendar availability, covering **{listing_count:,} active listings**.

### Navigate the Platform:
Use the **sidebar** to explore:
1. **Market Overview**: High-level KPIs and pricing trends.
2. **Geospatial Insights**: Interactive borough heatmaps across London.
3. **Property Analysis**: ROI breakdown by amenities and host tenure.
4. **Price Advisor**: Get a data-backed nightly price estimate for any listing configuration.
5. **Investment Estimator**: Compare borough revenue potential and stress-test occupancy scenarios.
""")

    last_loaded = datetime.now().strftime("%d %b %Y, %H:%M")
    st.info(
        f"Data reflects the latest Inside Airbnb snapshot (updated quarterly by the source). "
        f"Dashboard last loaded: **{last_loaded}**.",
        icon="ℹ️"
    )

    st.success(
        f"Warehouse connected. Tracking **{listing_count:,}** active listings, "
        f"**{review_count:,}** reviews, and **{calendar_count:,}** calendar records."
    )

except Exception as e:
    st.markdown("""
This executive dashboard is the **Gold Layer** presentation tier of a Medallion data pipeline.
It queries a DuckDB star schema across reviews, pricing history, and calendar availability.
""")
    st.error(
        f"Could not connect to the data warehouse. "
        f"Please ensure Phase 3 (dbt run) has been executed first. Error: {e}"
    )

