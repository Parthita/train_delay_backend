import pandas as pd
import numpy as np
import joblib
import os
from pathlib import Path
from model import StationEncoder

def predict_delays(train_number, target_date):
    """Predict delays for a train on a given date."""
    # Initialize file paths
    output_dir = Path("pipeline_output")
    model_file = output_dir / f"{train_number}_model.pkl"
    encoder_file = output_dir / f"{train_number}_encoder.pkl"
    history_file = Path(f"{train_number}.csv")
    
    try:
        model = joblib.load(model_file)
        encoder = joblib.load(encoder_file)
        history = pd.read_csv(history_file, parse_dates=["date"])
    except Exception as e:
        print(f"Error loading files: {e}")
        return None

    # Get stations in their route order by finding the first occurrence of each station
    route_order = history.sort_values('date').groupby('station').first().sort_values('date').index.tolist()
    target_date = pd.to_datetime(target_date)

    # Prepare base DataFrame for prediction, one row per station for the target date
    predict_df = pd.DataFrame({"station": route_order})
    predict_df["date"] = target_date

    # Add date features same as training
    predict_df["month"] = predict_df["date"].dt.month
    predict_df["day"] = predict_df["date"].dt.day
    predict_df["year"] = predict_df["date"].dt.year
    predict_df["day_of_week"] = predict_df["date"].dt.dayofweek
    predict_df["is_weekend"] = predict_df["day_of_week"].isin([5,6]).astype(int)
    predict_df["month_sin"] = np.sin(2 * np.pi * predict_df["month"] / 12)
    predict_df["month_cos"] = np.cos(2 * np.pi * predict_df["month"] / 12)
    predict_df["day_sin"] = np.sin(2 * np.pi * predict_df["day"] / 31)
    predict_df["day_cos"] = np.cos(2 * np.pi * predict_df["day"] / 31)

    # Encode stations using the custom encoder
    predict_df["station_encoded"] = encoder.transform(predict_df["station"])

    # To get lag features, merge with history delays for past days for each station
    history_sorted = history.sort_values(["station", "date"])
    lags = [1, 2, 3]

    # For each lag, get delay from target_date - lag days
    for lag in lags:
        lag_date = target_date - pd.Timedelta(days=lag)
        lag_data = history_sorted[history_sorted["date"] == lag_date][["station", "delay_minutes"]]
        lag_data = lag_data.rename(columns={"delay_minutes": f"prev_delay_{lag}"})
        predict_df = predict_df.merge(lag_data, on="station", how="left")

    # Fill missing lag delays with median of that station's delays
    for lag in lags:
        col = f"prev_delay_{lag}"
        station_medians = history_sorted.groupby("station")["delay_minutes"].median()
        for station in predict_df["station"].unique():
            mask = predict_df["station"] == station
            if station in station_medians:
                predict_df.loc[mask, col] = predict_df.loc[mask, col].fillna(station_medians[station])
            else:
                # For unknown stations, use the overall median delay
                predict_df.loc[mask, col] = predict_df.loc[mask, col].fillna(history_sorted["delay_minutes"].median())

    # Rolling features: rolling mean (3 days), rolling median (7 days) before target date
    def get_rolling_feature(station, date, window, agg_func):
        # filter dates before target date
        s = history_sorted[(history_sorted["station"] == station) & (history_sorted["date"] < date)]
        if len(s) < window:
            # Use median of all delays for this station if not enough history
            return s["delay_minutes"].median() if not s.empty else history_sorted["delay_minutes"].median()
        if agg_func == "mean":
            return s.tail(window)["delay_minutes"].mean()
        if agg_func == "median":
            return s.tail(window)["delay_minutes"].median()
        return history_sorted["delay_minutes"].median()

    rolling_means = []
    rolling_medians = []

    for st in route_order:  # Use route_order instead of stations
        rm = get_rolling_feature(st, target_date, 3, "mean")
        rolling_means.append(rm)
        rmd = get_rolling_feature(st, target_date, 7, "median")
        rolling_medians.append(rmd)

    predict_df["rolling_mean_3"] = rolling_means
    predict_df["rolling_median_7"] = rolling_medians

    # Prepare feature list same as training
    features = [
        "station_encoded", "day", "month", "year", "day_of_week", "is_weekend",
        "month_sin", "month_cos", "day_sin", "day_cos",
        "prev_delay_1", "prev_delay_2", "prev_delay_3",
        "rolling_mean_3", "rolling_median_7"
    ]

    X_pred = predict_df[features]

    # Predict delays
    predicted = model.predict(X_pred)
    predicted = np.round(predicted, 2)
    predict_df["predicted_delay"] = predicted

    # Convert to dictionary of station -> delay, maintaining route order
    delays = dict(zip(predict_df["station"], predict_df["predicted_delay"]))
    
    # Print predictions for debugging
    print("\nPredicted delays (in route order):")
    for station, delay in delays.items():
        print(f"{station}: {delay:.2f} minutes")
    
    return delays
