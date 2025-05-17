import pandas as pd
import numpy as np
import joblib
from datetime import datetime
from model import prepare_features, get_features

def predict_delays(train_number: str, target_date: str = None):
    """
    Predict delays for a specific train on a given date.
    Returns a list of predictions for each station.
    """
    if target_date is None:
        target_date = datetime.now().strftime('%Y-%m-%d')
    
    # Load model and encoder
    model_file = f"{train_number}_model.pkl"
    encoder_file = f"{train_number}_encoder.pkl"
    
    try:
        model = joblib.load(model_file)
        encoder = joblib.load(encoder_file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Model files not found for train {train_number}")
    
    # Load history data to get stations
    history_file = f"{train_number}.csv"
    try:
        history = pd.read_csv(history_file, parse_dates=["date"])
    except FileNotFoundError:
        raise FileNotFoundError(f"History file not found for train {train_number}")
    
    # Get unique stations
    stations = history["station"].unique()
    
    # Convert target date to datetime
    target_date = pd.to_datetime(target_date)
    
    # Prepare base DataFrame for prediction
    predict_df = pd.DataFrame({"station": stations})
    predict_df["date"] = target_date
    
    # Add date features
    predict_df["month"] = predict_df["date"].dt.month
    predict_df["day"] = predict_df["date"].dt.day
    predict_df["year"] = predict_df["date"].dt.year
    predict_df["day_of_week"] = predict_df["date"].dt.dayofweek
    predict_df["is_weekend"] = predict_df["day_of_week"].isin([5,6]).astype(int)
    
    # Add cyclical features
    predict_df["month_sin"] = np.sin(2 * np.pi * predict_df["month"] / 12)
    predict_df["month_cos"] = np.cos(2 * np.pi * predict_df["month"] / 12)
    predict_df["day_sin"] = np.sin(2 * np.pi * predict_df["day"] / 31)
    predict_df["day_cos"] = np.cos(2 * np.pi * predict_df["day"] / 31)
    
    # Encode stations
    predict_df["station_encoded"] = encoder.transform(predict_df["station"])
    
    # Get lag features from history
    history_sorted = history.sort_values(["station", "date"])
    lags = [1, 2, 3]
    
    for lag in lags:
        lag_date = target_date - pd.Timedelta(days=lag)
        lag_data = history_sorted[history_sorted["date"] == lag_date][["station", "delay_minutes"]]
        lag_data = lag_data.rename(columns={"delay_minutes": f"prev_delay_{lag}"})
        predict_df = predict_df.merge(lag_data, on="station", how="left")
        predict_df[f"prev_delay_{lag}"] = predict_df[f"prev_delay_{lag}"].fillna(0)
    
    # Calculate rolling features
    def get_rolling_feature(station, date, window, agg_func):
        s = history_sorted[(history_sorted["station"] == station) & (history_sorted["date"] < date)]
        if len(s) < window:
            return 0
        if agg_func == "mean":
            return s.tail(window)["delay_minutes"].mean()
        if agg_func == "median":
            return s.tail(window)["delay_minutes"].median()
        return 0
    
    rolling_means = []
    rolling_medians = []
    
    for st in stations:
        rm = get_rolling_feature(st, target_date, 3, "mean")
        rolling_means.append(rm)
        rmd = get_rolling_feature(st, target_date, 7, "median")
        rolling_medians.append(rmd)
    
    predict_df["rolling_mean_3"] = rolling_means
    predict_df["rolling_median_7"] = rolling_medians
    
    # Get features
    features = get_features()
    X_pred = predict_df[features]
    
    # Make predictions
    predicted = model.predict(X_pred)
    predicted = np.round(predicted, 2)
    
    # Fix source station negative delay
    source = stations[0]
    if predict_df.loc[predict_df["station"] == source, "predicted_delay"].values[0] < 0:
        predict_df.loc[predict_df["station"] == source, "predicted_delay"] = 0.0
    
    # Clip negative predictions
    predict_df["predicted_delay"] = predict_df["predicted_delay"].clip(lower=0)
    
    # Format results
    results = []
    for _, row in predict_df.iterrows():
        results.append({
            "station": row["station"],
            "delay": float(row["predicted_delay"])
        })
    
    return results

if __name__ == "__main__":
    # Example usage
    predictions = predict_delays("12303", "2025-05-21")
    for pred in predictions:
        print(f"Station: {pred['station']}, Predicted Delay: {pred['delay']} minutes")

