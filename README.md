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

Example Request:
```bash
curl "http://localhost:5000/api/trains-between?source_name=Howrah%20Jn&source_code=HWH&destination_name=New%20Delhi&destination_code=NDLS&date=20240318"
```

Example Response:
```json
{
    "status": "success",
    "data": [
        {
            "train_number": "12303",
            "train_name": "Poorva Express",
            "source": "Howrah Jn",
            "departure_time": "08:00",
            "destination": "New Delhi",
            "arrival_time": "08:00",
            "duration": "24:00",
            "source_delay": 0.0,
            "destination_delay": 17.14,
            "running_days": ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"],
            "booking_classes": ["1A", "2A", "3A", "SL"],
            "has_pantry": true
        },
        {
            "train_number": "12304",
            "train_name": "Poorva Express",
            "source": "New Delhi",
            "departure_time": "08:00",
            "destination": "Howrah Jn",
            "arrival_time": "08:00",
            "duration": "24:00",
            "source_delay": 0.0,
            "destination_delay": 15.25,
            "running_days": ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"],
            "booking_classes": ["1A", "2A", "3A", "SL"],
            "has_pantry": true
        }
    ]
}
```

### 2. Get Train Schedule
```
GET /api/train-schedule
```
Parameters:
- `train_name`: Name of the train
- `train_number`: Train number
- `date`: Journey date (YYYYMMDD format)

Example Request:
```bash
curl "http://localhost:5000/api/train-schedule?train_name=Poorva%20Express&train_number=12303&date=20240318"
```

Example Response:
```json
{
    "status": "success",
    "data": {
        "train_info": {
            "name": "Poorva Express",
            "number": "12303",
            "type": "Superfast Express"
        },
        "schedule": [
            {
                "station": "Howrah Jn",
                "station_code": "HWH",
                "arrival": "Source",
                "departure": "08:00",
                "predicted_delay": 0.0,
                "is_source": true
            },
            {
                "station": "Asansol Jn",
                "station_code": "ASN",
                "arrival": "10:45",
                "departure": "10:50",
                "predicted_delay": 5.2
            },
            {
                "station": "New Delhi",
                "station_code": "NDLS",
                "arrival": "08:00",
                "departure": "Destination",
                "predicted_delay": 17.14,
                "is_destination": true
            }
        ]
    }
}
```

### 3. Get Train Running Status
```
GET /api/train-running-status
```
Parameters:
- `train_number`: Train number
- `station_name`: Current station name
- `date`: Journey date (YYYYMMDD format)

Example Request:
```bash
curl "http://localhost:5000/api/train-running-status?train_number=12303&station_name=New-Delhi-NDLS&date=20240318"
```

Example Response (When Train Journey is Completed):
```json
{
    "status": "success",
    "message": "Train journey completed",
    "data": {
        "stations": [],
        "train_info": {
            "number": "12303",
            "scraped_at": "2025-05-19 00:03:53"
        }
    }
}
```

Example Response (When Prediction is Reliable):
```json
{
    "status": "success",
    "data": {
        "current_status": {
            "train_info": {
                "number": "12303",
                "scraped_at": "2024-03-18 10:30:00"
            },
            "stations": [
                {
                    "station_name": "Howrah Jn",
                    "day": "Day 1",
                    "date": "18 Mar",
                    "arrival": "Source",
                    "departure": "08:00",
                    "delay": "0 min",
                    "status": "Completed"
                },
                {
                    "station_name": "New Delhi",
                    "day": "Day 2",
                    "date": "19 Mar",
                    "arrival": "08:00",
                    "departure": "Destination",
                    "delay": "15 min late",
                    "status": "Pending"
                }
            ]
        },
        "current_station": "New Delhi",
        "current_delay": 15,
        "predicted_delay": 12,
        "delay_difference": 3,
        "is_prediction_reliable": true
    }
}
```

Example Response (When Prediction is Not Reliable):
```json
{
    "status": "success",
    "data": {
        "current_status": {
            "train_info": {
                "number": "12303",
                "scraped_at": "2024-03-18 10:30:00"
            },
            "stations": [...]
        },
        "current_station": "New Delhi",
        "current_delay": 45,
        "predicted_delay": 12,
        "delay_difference": 33,
        "is_prediction_reliable": false
    }
}
```

Example Response (When No Prediction Available):
```json
{
    "status": "success",
    "data": {
        "current_status": {
            "train_info": {
                "number": "12303",
                "scraped_at": "2024-03-18 10:30:00"
            },
            "stations": [...]
        },
        "current_station": "New Delhi",
        "current_delay": 15,
        "prediction_available": false,
        "message": "No predictions available for this train"
    }
}
```

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

## Error Handling

The system handles various error scenarios:
- Missing or invalid parameters
- Network errors during scraping
- Missing historical data
- Model prediction failures
- Station name mismatches

Error Response Example:
```json
{
    "error": "Missing required field: train_number"
}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.