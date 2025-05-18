# Train Delay Prediction Backend

This is a Flask-based backend service for predicting train delays and comparing them with live status from etrain.info.

## Features

- Get trains between stations
- Get train schedules with predicted delays
- Compare predicted delays with live status from etrain.info
- Health check endpoint

## API Endpoints

### 1. Get Trains Between Stations
```http
GET /api/trains-between?source_name=Howrah%20Jn&source_code=HWH&destination_name=New%20Delhi&destination_code=NDLS&date=20250521
```

Response:
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
        }
    ]
}
```

### 2. Get Train Schedule with Delays
```http
GET /api/train-schedule?train_name=Poorva%20Express&train_number=12303&date=20250521
```

Response:
```json
{
    "status": "success",
    "data": {
        "train_number": "12303",
        "train_name": "Poorva Express",
        "schedule": [
            {
                "name": "Howrah Jn",
                "station_code": "HWH",
                "arrival": "Source",
                "departure": "08:00",
                "predicted_delay": 0.0,
                "is_source": true
            }
        ]
    }
}
```

### 3. Get Live Status and Compare with Predictions
```http
GET /api/live-status?train_number=12303
```

Response:
```json
{
    "status": "success",
    "data": {
        "live_status": "On time",
        "predicted_delay": 0.0,
        "comparison": "On time",
        "accuracy": "Predicted delay is within ±15 minutes of actual delay"
    }
}
```

### 4. Health Check
```http
GET /health
```

Response:
```json
{
    "status": "healthy"
}
```

## Setup Instructions

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

## Deployment on Render

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Configure the service:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
   - Python Version: 3.11.11

## Directory Structure
```
api/
├── app.py              # Main Flask application
├── train_pipeline.py   # Core train processing logic
├── model.py           # Model training
├── predict.py         # Prediction logic
├── scrape_trains.py   # Train scraping
├── delay_scrapper.py  # Delay scraping
├── scrape_schedule.py # Schedule scraping
├── requirements.txt   # Python dependencies
├── runtime.txt       # Python version
├── Procfile          # Render deployment configuration
└── README.md         # This documentation
```

## Error Handling

The API returns appropriate HTTP status codes:
- 200: Success
- 400: Bad Request (missing required fields)
- 404: Not Found (no trains/schedule found)
- 500: Internal Server Error

Error Response Format:
```json
{
    "error": "Error message description"
}
```

## Environment Variables

- PORT: Port number for the Flask application (default: 5000)

## Dependencies

- Flask: Web framework
- Requests: HTTP library
- BeautifulSoup4: HTML parsing
- Pandas: Data manipulation
- NumPy: Numerical computing
- Scikit-learn: Machine learning
- Gunicorn: WSGI HTTP Server

## Notes

- The live status comparison feature scrapes data from etrain.info
- Predictions are considered accurate if they are within ±15 minutes of actual delays
- The service includes error handling and logging 