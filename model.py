import pandas as pd
import numpy as np
import joblib
import xgboost as xgb
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

def prepare_features(df):
    """Prepare features for model training"""
    # Filter out extreme delays
    df = df[(df["delay_minutes"] > -30) & (df["delay_minutes"] < 120)]
    
    # Add date features
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    df["year"] = df["date"].dt.year
    df["day_of_week"] = df["date"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5,6]).astype(int)
    
    # Add cyclical features
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["day_sin"] = np.sin(2 * np.pi * df["day"] / 31)
    df["day_cos"] = np.cos(2 * np.pi * df["day"] / 31)
    
    # Encode stations
    encoder = LabelEncoder()
    df["station_encoded"] = encoder.fit_transform(df["station"])
    
    # Sort by station and date
    df = df.sort_values(["station", "date"])
    
    # Add lag features
    for lag in range(1, 4):
        df[f"prev_delay_{lag}"] = df.groupby("station")["delay_minutes"].shift(lag).fillna(0)
    
    # Add rolling features
    df["rolling_mean_3"] = df.groupby("station")["delay_minutes"].transform(lambda x: x.shift(1).rolling(3).mean()).fillna(0)
    df["rolling_median_7"] = df.groupby("station")["delay_minutes"].transform(lambda x: x.shift(1).rolling(7).median()).fillna(0)
    
    return df, encoder

def get_features():
    """Get list of features used in the model"""
    return [
        "station_encoded", "day", "month", "year", "day_of_week", "is_weekend",
        "month_sin", "month_cos", "day_sin", "day_cos",
        "prev_delay_1", "prev_delay_2", "prev_delay_3",
        "rolling_mean_3", "rolling_median_7"
    ]

def train_model(csv_file: str):
    """Train model for a specific train"""
    # Read data
    df = pd.read_csv(csv_file, parse_dates=["date"])
    
    # Prepare features
    df, encoder = prepare_features(df)
    
    # Get features
    features = get_features()
    X = df[features]
    y = df["delay_minutes"]
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train model
    model = xgb.XGBRegressor(
        objective='reg:squarederror',
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        random_state=42
    )
    model.fit(X_train, y_train)
    
    # Evaluate model
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    print(f"MAE:  {mae:.2f} minutes")
    print(f"RMSE: {rmse:.2f} minutes")
    print(f"R²:   {r2:.4f}")
    
    # Save model and encoder
    train_number = csv_file.split('.')[0]
    model_file = f"{train_number}_model.pkl"
    encoder_file = f"{train_number}_encoder.pkl"
    
    joblib.dump(model, model_file)
    joblib.dump(encoder, encoder_file)
    print(f"Model and encoder saved as {model_file} and {encoder_file}")
    
    return model, encoder

if __name__ == "__main__":
    # Example usage
    train_model("12303.csv")

