"""
Train XGBoost price prediction model on all Gold-layer listings.
Run once from the project root: python models/train_model.py
Saves the fitted model + feature columns to models/price_model.pkl
"""

import os
import sys
import joblib
import duckdb
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'data', 'gold', 'airbnb_london.duckdb')
)
MODEL_OUT = os.path.join(os.path.dirname(__file__), 'price_model.pkl')


def load_training_data(con):
    df = con.execute("""
        SELECT
            l.price,
            l.room_type,
            COALESCE(l.bedrooms, 1)       AS bedrooms,
            COALESCE(l.bathrooms, 1)      AS bathrooms,
            COALESCE(l.accommodates, 2)   AS accommodates,
            COALESCE(l.beds, 1)           AS beds,
            COALESCE(l.amenity_count, 0)  AS amenity_count,
            COALESCE(l.has_wifi,        FALSE) AS has_wifi,
            COALESCE(l.has_kitchen,     FALSE) AS has_kitchen,
            COALESCE(l.has_parking,     FALSE) AS has_parking,
            COALESCE(l.has_ac,          FALSE) AS has_ac,
            COALESCE(l.has_washer,      FALSE) AS has_washer,
            COALESCE(l.has_tv,          FALSE) AS has_tv,
            COALESCE(l.has_elevator,    FALSE) AS has_elevator,
            COALESCE(l.has_pool,        FALSE) AS has_pool,
            COALESCE(l.has_gym,         FALSE) AS has_gym,
            COALESCE(l.has_hot_tub,     FALSE) AS has_hot_tub,
            COALESCE(l.has_breakfast,   FALSE) AS has_breakfast,
            COALESCE(l.is_pet_friendly, FALSE) AS is_pet_friendly,
            COALESCE(l.has_self_checkin,FALSE) AS has_self_checkin,
            g.neighbourhood
        FROM dim_listings l
        JOIN dim_geography g ON l.listing_id = g.listing_id
        WHERE l.price BETWEEN 10 AND 2000
          AND l.room_type IS NOT NULL
    """).df()
    return df


def encode_features(df, le_room=None, le_borough=None, fit=True):
    df = df.copy()

    bool_cols = [
        'has_wifi', 'has_kitchen', 'has_parking', 'has_ac', 'has_washer',
        'has_tv', 'has_elevator', 'has_pool', 'has_gym', 'has_hot_tub',
        'has_breakfast', 'is_pet_friendly', 'has_self_checkin'
    ]
    for col in bool_cols:
        df[col] = df[col].astype(int)

    if fit:
        le_room = LabelEncoder()
        le_borough = LabelEncoder()
        df['room_type_enc']   = le_room.fit_transform(df['room_type'])
        df['neighbourhood_enc'] = le_borough.fit_transform(df['neighbourhood'])
    else:
        df['room_type_enc']   = le_room.transform(df['room_type'])
        df['neighbourhood_enc'] = le_borough.transform(df['neighbourhood'])

    return df, le_room, le_borough


FEATURE_COLS = [
    'room_type_enc', 'bedrooms', 'bathrooms', 'accommodates', 'beds',
    'amenity_count', 'neighbourhood_enc',
    'has_wifi', 'has_kitchen', 'has_parking', 'has_ac', 'has_washer',
    'has_tv', 'has_elevator', 'has_pool', 'has_gym', 'has_hot_tub',
    'has_breakfast', 'is_pet_friendly', 'has_self_checkin'
]


def train():
    print("Connecting to warehouse...")
    con = duckdb.connect(DB_PATH, read_only=True)

    print("Loading training data...")
    df = load_training_data(con)
    print(f"  Rows loaded: {len(df):,}")

    df_enc, le_room, le_borough = encode_features(df, fit=True)

    X = df_enc[FEATURE_COLS]
    y = df_enc['price']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )

    print("Training XGBoost model...")
    model = xgb.XGBRegressor(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        random_state=42,
        n_jobs=-1,
        verbosity=0
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )

    preds = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    mae  = mean_absolute_error(y_test, preds)
    r2   = r2_score(y_test, preds)

    print(f"\nModel evaluation (held-out 20% test set, n={len(y_test):,}):")
    print(f"  RMSE : £{rmse:.2f}")
    print(f"  MAE  : £{mae:.2f}")
    print(f"  R2   : {r2:.4f}")

    artifact = {
        'model':        model,
        'le_room':      le_room,
        'le_borough':   le_borough,
        'feature_cols': FEATURE_COLS,
        'metrics': {'rmse': rmse, 'mae': mae, 'r2': r2},
        'borough_list': sorted(df['neighbourhood'].unique().tolist()),
        'room_types':   sorted(df['room_type'].unique().tolist()),
    }

    joblib.dump(artifact, MODEL_OUT)
    print(f"\nModel saved to: {MODEL_OUT}")


if __name__ == '__main__':
    train()
