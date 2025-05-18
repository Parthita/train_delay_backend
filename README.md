# Train Delay Prediction System

A machine learning-based system for predicting train delays and providing real-time running status information. The system combines historical delay data with real-time running status to provide accurate delay predictions.

## Features

- Real-time train running status tracking
- Machine learning-based delay prediction
- Historical delay data analysis
- API endpoints for train information and predictions
- Support for multiple train routes and stations

## API Endpoints

### 1. Get Trains Between Stations
```
GET /api/trains-between
```
Parameters:
- `source_name`: Source station name
- `source_code`: Source station code
- `destination_name`: Destination station name
- `destination_code`: Destination station code
- `date`: Journey date (YYYYMMDD format)

Returns list of trains between stations with predicted delays.

### 2. Get Train Schedule
```
GET /api/train-schedule
```
Parameters:
- `train_name`: Name of the train
- `train_number`: Train number
- `date`: Journey date (YYYYMMDD format)

Returns complete train schedule with predicted delays for each station.

### 3. Get Train Running Status
```
GET /api/train-running-status
```
Parameters:
- `train_number`: Train number
- `station_name`: Current station name
- `date`: Journey date (YYYYMMDD format)

Returns current running status with delay predictions:
- Current delay from real-time data
- Predicted delay from ML model
- Comparison of delays
- Reliability indicator (if prediction is within 15 minutes)

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create necessary directories:
```bash
mkdir pipeline_output
mkdir temp
```

3. Run the Flask application:
```bash
python app.py
```

## Project Structure

- `app.py`: Main Flask application with API endpoints
- `train_pipeline.py`: Core pipeline for processing train data
- `model.py`: Machine learning model for delay prediction
- `predict.py`: Prediction functionality
- `confirmtkt_scraper.py`: Scraper for real-time train status
- `delay_scrapper.py`: Scraper for historical delay data
- `scrape_trains.py`: Scraper for train information
- `scrape_schedule.py`: Scraper for train schedules

## How It Works

1. **Data Collection**:
   - Historical delay data is collected from etrain.info
   - Real-time running status is fetched from confirmtkt.com

2. **Model Training**:
   - Historical delay data is processed and cleaned
   - Features are extracted (date, station, previous delays, etc.)
   - XGBoost model is trained to predict delays

3. **Prediction**:
   - Model predicts delays for each station
   - Predictions are compared with real-time delays
   - Reliability is determined based on prediction accuracy

4. **API Integration**:
   - Endpoints provide access to predictions and real-time data
   - Responses include both current status and predictions
   - Error handling for various scenarios

## Response Examples

### Train Running Status
```json
{
    "status": "success",
    "data": {
        "current_status": {
            "train_info": {
                "number": "12304",
                "scraped_at": "2024-03-18 10:30:00"
            },
            "stations": [...]
        },
        "current_station": "New Delhi",
        "current_delay": 15,
        "predicted_delay": 12,
        "delay_difference": 3,
        "is_prediction_reliable": true
    }
}
```

### Train Schedule
```json
{
    "status": "success",
    "data": {
        "train_info": {
            "name": "Poorva Express",
            "number": "12303"
        },
        "schedule": [
            {
                "station": "Howrah",
                "arrival": "23:00",
                "departure": "23:15",
                "predicted_delay": 0
            },
            ...
        ]
    }
}
```

## Error Handling

The system handles various error scenarios:
- Missing or invalid parameters
- Network errors during scraping
- Missing historical data
- Model prediction failures
- Station name mismatches

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 