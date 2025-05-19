import pandas as pd
import numpy as np
import joblib
import os
from pathlib import Path
import logging
from sklearn.preprocessing import LabelEncoder
import signal
from functools import wraps
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")

def timeout(seconds):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Set the signal handler and a timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                # Disable the alarm
                signal.alarm(0)
            return result
        return wrapper
    return decorator

def predict_delays(train_number, target_date):
    """Predict delays for a train on a given date."""
    logger.info(f"Starting prediction for train {train_number} on {target_date}")
    
    # Initialize file paths
    output_dir = Path("pipeline_output")
    model_file = output_dir / f"{train_number}_model.pkl"
    encoder_file = output_dir / f"{train_number}_encoder.pkl"
    history_file = Path(f"{train_number}.csv")
    
    try:
        # Load model and encoder
        logger.info(f"Loading model and encoder for train {train_number}")
        model = joblib.load(model_file)
        encoder = joblib.load(encoder_file)
        
        # Load and validate history data
        logger.info(f"Loading history data from {history_file}")
        if not history_file.exists():
            logger.error(f"History file not found: {history_file}")
            return None
            
        history = pd.read_csv(history_file, parse_dates=["date"])
        if history.empty:
            logger.error("History data is empty")
            return None
            
        logger.info(f"Loaded {len(history)} rows from history file")

    except FileNotFoundError as e:
        logger.error(f"Required file not found: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading files: {e}")
        return None

    # Filter stations from history - these define the train's route
    stations = history["station"].unique()
    target_date = pd.to_datetime(target_date)
    
    logger.info(f"Processing {len(stations)} stations for prediction")

    # Prepare base DataFrame for prediction, one row per station for the target date
    predict_df = pd.DataFrame({"station": stations})
    predict_df["date"] = target_date

    try:
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

        # Encode stations with handling for unseen stations
        logger.info("Encoding stations")
        try:
            predict_df["station_encoded"] = encoder.transform(predict_df["station"])
        except ValueError as e:
            if "unseen labels" in str(e):
                logger.warning("Found stations not in training data, using fallback encoding")
                # Create a new encoder for unseen stations
                new_encoder = LabelEncoder()
                new_encoder.fit(history["station"])
                # Transform using the new encoder
                predict_df["station_encoded"] = new_encoder.transform(predict_df["station"])
            else:
                raise
    except Exception as e:
        logger.error(f"Error preparing features: {e}")
        return {station: "no data found" for station in stations}

    # To get lag features, merge with history delays for past days for each station
    history_sorted = history.sort_values(["station", "date"])
    lags = [1, 2, 3]

    try:
        # For each lag, get delay from target_date - lag days
        for lag in lags:
            lag_date = target_date - pd.Timedelta(days=lag)
            lag_data = history_sorted[history_sorted["date"] == lag_date][["station", "delay_minutes"]]
            lag_data = lag_data.rename(columns={"delay_minutes": f"prev_delay_{lag}"})
            predict_df = predict_df.merge(lag_data, on="station", how="left")

        # Fill missing lag delays with median of that station's delays
        station_medians = history_sorted.groupby("station")["delay_minutes"].median()
        for lag in lags:
            col = f"prev_delay_{lag}"
            predict_df[col] = predict_df.apply(
                lambda row: station_medians.get(row["station"], 0) 
                if pd.isna(row[col]) else row[col], 
                axis=1
            )
    except Exception as e:
        logger.error(f"Error calculating lag features: {e}")
        return {station: "no data found" for station in stations}

    # Rolling features: rolling mean (3 days), rolling median (7 days) before target date
    def get_rolling_feature(station, date, window, agg_func):
        try:
            # filter dates before target date
            s = history_sorted[(history_sorted["station"] == station) & (history_sorted["date"] < date)]
            if len(s) < window:
                # Use median of all delays for this station if not enough history
                return s["delay_minutes"].median() if not s.empty else 0
            if agg_func == "mean":
                return s.tail(window)["delay_minutes"].mean()
            if agg_func == "median":
                return s.tail(window)["delay_minutes"].median()
            return 0
        except Exception as e:
            logger.error(f"Error calculating rolling feature for station {station}: {e}")
            return 0

    try:
        logger.info("Calculating rolling features")
        # Calculate rolling features for all stations at once
        rolling_features = []
        for st in stations:
            rm = get_rolling_feature(st, target_date, 3, "mean")
            rmd = get_rolling_feature(st, target_date, 7, "median")
            rolling_features.append((rm, rmd))
        
        predict_df["rolling_mean_3"] = [x[0] for x in rolling_features]
        predict_df["rolling_median_7"] = [x[1] for x in rolling_features]
    except Exception as e:
        logger.error(f"Error calculating rolling features: {e}")
        return {station: "no data found" for station in stations}

    # Prepare feature list same as training
    features = [
        "station_encoded", "day", "month", "year", "day_of_week", "is_weekend",
        "month_sin", "month_cos", "day_sin", "day_cos",
        "prev_delay_1", "prev_delay_2", "prev_delay_3",
        "rolling_mean_3", "rolling_median_7"
    ]

    X_pred = predict_df[features]

    try:
        # Predict delays
        logger.info("Making predictions")
        predicted = model.predict(X_pred)
        predicted = np.round(predicted, 2)
        predict_df["predicted_delay"] = predicted
    except Exception as e:
        logger.error(f"Error predicting delays: {e}")
        return {station: "no data found" for station in stations}

    # Convert to dictionary of station -> delay
    delays = dict(zip(predict_df["station"], predict_df["predicted_delay"]))
    
    # Log predictions
    logger.info("\nPredicted delays:")
    for station, delay in delays.items():
        logger.info(f"{station}: {delay:.2f} minutes")
    
    return delays