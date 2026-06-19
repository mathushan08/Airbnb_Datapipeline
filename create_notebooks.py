import nbformat as nbf
import os

os.makedirs("notebooks", exist_ok=True)

# 01 Dataset Familiarization
nb_01 = nbf.v4.new_notebook()
nb_01['cells'] = [
    nbf.v4.new_markdown_cell("# Dataset Familiarization\nLoad the gold layer DuckDB tables and explore the data structure."),
    nbf.v4.new_code_cell("import duckdb\nimport pandas as pd\nimport matplotlib.pyplot as plt\nimport seaborn as sns\n\nconn = duckdb.connect('../data/gold/airbnb_london.duckdb')"),
    nbf.v4.new_code_cell("# View tables\nprint(conn.execute(\"SHOW TABLES\").df())"),
    nbf.v4.new_code_cell("# Load fact table\ndf_calendar = conn.execute(\"SELECT * FROM fact_calendar LIMIT 1000\").df()\ndf_calendar.head()")
]
nbf.write(nb_01, 'notebooks/01_dataset_familiarization.ipynb')

# 02 Data Profiling
nb_02 = nbf.v4.new_notebook()
nb_02['cells'] = [
    nbf.v4.new_markdown_cell("# Data Profiling\nGenerate a ydata-profiling report for the listings dimension."),
    nbf.v4.new_code_cell("import duckdb\nimport pandas as pd\nfrom ydata_profiling import ProfileReport\n\nconn = duckdb.connect('../data/gold/airbnb_london.duckdb')"),
    nbf.v4.new_code_cell("df_listings = conn.execute(\"SELECT * FROM dim_listings\").df()"),
    nbf.v4.new_code_cell("profile = ProfileReport(df_listings, title='London Airbnb Listings Profiling Report', minimal=True)\nprofile.to_file('../reports/listings_profile.html')")
]
nbf.write(nb_02, 'notebooks/02_data_profiling.ipynb')

# 03 EDA
nb_03 = nbf.v4.new_notebook()
nb_03['cells'] = [
    nbf.v4.new_markdown_cell("# Exploratory Data Analysis (EDA)\nAnalyze pricing trends, property distributions, and geographic hotspots."),
    nbf.v4.new_code_cell("import duckdb\nimport pandas as pd\nimport matplotlib.pyplot as plt\nimport seaborn as sns\n\nconn = duckdb.connect('../data/gold/airbnb_london.duckdb')"),
    nbf.v4.new_code_cell("df = conn.execute(\"SELECT * FROM dim_listings l JOIN dim_geography g ON l.listing_id = g.listing_id\").df()"),
    nbf.v4.new_code_cell("plt.figure(figsize=(10,6))\nsns.histplot(df[df['price'] < 1000]['price'], bins=50)\nplt.title('Distribution of Prices in London (<$1000)')\nplt.show()")
]
nbf.write(nb_03, 'notebooks/03_eda.ipynb')

# 04 Statistical Testing
nb_04 = nbf.v4.new_notebook()
nb_04['cells'] = [
    nbf.v4.new_markdown_cell("# Statistical Hypothesis Testing\nTest differences between superhosts and regular hosts, and property types."),
    nbf.v4.new_code_cell("import duckdb\nimport pandas as pd\nfrom scipy import stats\n\nconn = duckdb.connect('../data/gold/airbnb_london.duckdb')"),
    nbf.v4.new_code_cell("df = conn.execute(\"SELECT l.price, h.host_is_superhost FROM dim_listings l JOIN dim_hosts h ON l.host_id = h.host_id WHERE l.price < 2000\").df()"),
    nbf.v4.new_code_cell("superhost = df[df['host_is_superhost'] == True]['price'].dropna()\nregular = df[df['host_is_superhost'] == False]['price'].dropna()\nt_stat, p_val = stats.ttest_ind(superhost, regular, equal_var=False)\nprint(f'T-test p-value: {p_val}')")
]
nbf.write(nb_04, 'notebooks/04_statistical_testing.ipynb')

# 05 ML Modeling
nb_05 = nbf.v4.new_notebook()
nb_05['cells'] = [
    nbf.v4.new_markdown_cell("# Predictive Modeling\nPredict listing prices using XGBoost and SHAP for feature importance."),
    nbf.v4.new_code_cell("import duckdb\nimport pandas as pd\nfrom sklearn.model_selection import train_test_split\nimport xgboost as xgb\n\nconn = duckdb.connect('../data/gold/airbnb_london.duckdb')"),
    nbf.v4.new_code_cell("df = conn.execute(\"SELECT price, accommodates, bedrooms, bathrooms, has_wifi, has_ac FROM dim_listings WHERE price < 1500\").df()"),
    nbf.v4.new_code_cell("df = df.dropna()\nX = df.drop('price', axis=1)\ny = df['price']\nX_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)\n\nmodel = xgb.XGBRegressor()\nmodel.fit(X_train, y_train)\nprint(f'R^2 Score: {model.score(X_test, y_test)}')")
]
nbf.write(nb_05, 'notebooks/05_ml_modeling.ipynb')

print("Notebooks created successfully.")
