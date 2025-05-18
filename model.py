import pandas as pd
import numpy as np
import joblib
import xgboost as xgb
import os
from pathlib import Path
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

def train_model(train_number):
    """Train a model for predicting delays for a given train."""
    # Create output directory
    output_dir = Path("pipeline_output")
    output_dir.mkdir(exist_ok=True)
    
    # Initialize file paths
    train_file = Path(f"{train_number}.csv")
    model_file = output_dir / f"{train_number}_model.pkl"
    encoder_file = output_dir / f"{train_number}_encoder.pkl"
    
    # Load and preprocess data
    df = pd.read_csv(train_file, parse_dates=["date"])
    print(f"\nLoaded {len(df)} rows from {train_file}")
    print("\nSample data:")
    print(df.head())
    
    # Check if we have enough data
    if len(df) < 2:  # Need at least 2 samples for train/test split
        print(f"Not enough delay data for train {train_number} (only {len(df)} samples)")
        return None, None
    
    # Filter out extreme delays
    df = df[(df["delay_minutes"] > -30) & (df["delay_minutes"] < 120)]
    print(f"\nAfter filtering extreme delays: {len(df)} rows")
    print("\nDelay statistics:")
    print(df["delay_minutes"].describe())
    
    # Check if we still have enough data after filtering
    if len(df) < 2:
        print(f"Not enough valid delay data for train {train_number} after filtering (only {len(df)} samples)")
        return None, None
    
    # Add date features
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    df["year"] = df["date"].dt.year
    df["day_of_week"] = df["date"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5,6]).astype(int)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["day_sin"] = np.sin(2 * np.pi * df["day"] / 31)
    df["day_cos"] = np.cos(2 * np.pi * df["day"] / 31)
    
    # Encode stations
    encoder = LabelEncoder()
    df["station_encoded"] = encoder.fit_transform(df["station"])
    print("\nStation encoding:")
    for station, code in zip(encoder.classes_, range(len(encoder.classes_))):
        print(f"{station}: {code}")
    
    # Sort by station and date
    df = df.sort_values(["station", "date"])
    
    # Add lag features
    for lag in range(1, 4):
        df[f"prev_delay_{lag}"] = df.groupby("station")["delay_minutes"].shift(lag).fillna(0)
    
    # Add rolling features
    df["rolling_mean_3"] = df.groupby("station")["delay_minutes"].transform(lambda x: x.shift(1).rolling(3).mean()).fillna(0)
    df["rolling_median_7"] = df.groupby("station")["delay_minutes"].transform(lambda x: x.shift(1).rolling(7).median()).fillna(0)
    
    # Define features
    features = [
        "station_encoded", "day", "month", "year", "day_of_week", "is_weekend",
        "month_sin", "month_cos", "day_sin", "day_cos",
        "prev_delay_1", "prev_delay_2", "prev_delay_3",
        "rolling_mean_3", "rolling_median_7"
    ]
    
    X = df[features]
    y = df["delay_minutes"]
    
    print("\nFeature statistics:")
    print(X.describe())
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train model with better parameters
    model = xgb.XGBRegressor(
        objective='reg:squarederror',
        n_estimators=500,  # Increased from 200
        max_depth=8,       # Increased from 6
        learning_rate=0.05, # Decreased from 0.1
        min_child_weight=3,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42
    )
    model.fit(X_train, y_train)
    
    # Evaluate model
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    print(f"\nModel performance:")
    print(f"MAE:  {mae:.2f} minutes")
    print(f"RMSE: {rmse:.2f} minutes")
    print(f"R²:   {r2:.4f}")
    
    # Print feature importance
    feature_importance = pd.DataFrame({
        'feature': features,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    print("\nFeature importance:")
    print(feature_importance)
    
    # Save model and encoder
    joblib.dump(model, model_file)
    joblib.dump(encoder, encoder_file)
    print(f"\nModel and encoder saved for train {train_number}")
    
    return model, encoder

if __name__ == "__main__":
    # Example usage
    train_model("12303")