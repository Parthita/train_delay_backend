# Train Delay Predictor Backend

A Flask-based backend service that predicts train delays using historical data and machine learning.

## Features

- Search for trains between stations
- Get train schedules
- Predict delays for specific trains
- Get delay predictions for entire train routes
- Automatic model training for new trains

## API Endpoints

### Search Trains
```
GET /api/search?source=STATION_CODE&dest=STATION_CODE&date=YYYY-MM-DD
```
Returns a list of trains running between source and destination stations on the specified date.

### Get Train Schedule
```
GET /api/schedule?train_name=TRAIN_NAME&train_number=TRAIN_NUMBER
```
Returns the complete schedule for a specific train.

### Get Delay Predictions
```
GET /api/delays?train_name=TRAIN_NAME&train_number=TRAIN_NUMBER&date=YYYY-MM-DD
```
Returns predicted delays for a specific train on the specified date.

### Get Route Delays
```
GET /api/route-delays?train_name=TRAIN_NAME&train_number=TRAIN_NUMBER&date=YYYY-MM-DD
```
Returns predicted delays for all stations in the train's route.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the Flask application:
```bash
python app.py
```

For production deployment on Render:
1. Create a new Web Service
2. Connect your GitHub repository
3. Set the build command: `pip install -r requirements.txt`
4. Set the start command: `gunicorn app:app`

## Project Structure

- `app.py`: Main Flask application
- `train_search.py`: Train search and schedule functionality
- `delay_scrapper.py`: Scrapes train delay data
- `model.py`: Machine learning model for delay prediction
- `predict.py`: Delay prediction functionality

## Data Flow

1. When a train is first requested:
   - Scrape historical delay data
   - Train a machine learning model
   - Save model and data for future use

2. For subsequent requests:
   - Load saved model and data
   - Make predictions based on historical patterns

## Notes

- The system automatically handles new trains by scraping their data and training models
- Predictions are based on historical delay patterns and various features like day of week, month, etc.
- The system uses XGBoost for machine learning predictions
- All data is stored locally in CSV and pickle files 