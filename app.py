from flask import Flask, request, jsonify
from train_pipeline import TrainPipeline
import logging
from datetime import datetime
import os
import re
import json
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def load_station_codes():
    """Load station codes from file or return empty dict if file not found."""
    try:
        # Try multiple possible locations for stationcode.json
        possible_paths = [
            Path("stationcode.json"),  # Current directory
            Path("pipeline_output/stationcode.json"),  # pipeline_output directory
            Path("/app/pipeline_output/stationcode.json"),  # Docker container path
            Path(os.path.dirname(os.path.abspath(__file__))) / "stationcode.json"  # Script directory
        ]
        
        for path in possible_paths:
            if path.exists():
                logger.info(f"Loading station codes from {path}")
                with open(path, 'r') as f:
                    return json.load(f)
        
        logger.warning("Station codes file not found in any location, using empty dictionary")
        return {}
    except Exception as e:
        logger.error(f"Error loading station codes: {e}")
        return {}

# Initialize pipeline with error handling
try:
    pipeline = TrainPipeline()
except Exception as e:
    logger.error(f"Failed to initialize pipeline: {e}")
    pipeline = None

def validate_station_code(code):
    """Validate station code format."""
    if not code or not isinstance(code, str):
        return False
    # Station codes are typically 3-4 characters, alphanumeric
    return bool(re.match(r'^[A-Z0-9]{3,4}$', code.upper()))

@app.route('/api/trains-between', methods=['GET'])
def get_trains_between():
    try:
        if pipeline is None:
            return jsonify({
                'error': 'Service temporarily unavailable',
                'details': 'Train pipeline initialization failed'
            }), 503

        # Get parameters from query string
        source_name = request.args.get('source_name')
        source_code = request.args.get('source_code')
        destination_name = request.args.get('destination_name')
        destination_code = request.args.get('destination_code')
        date = request.args.get('date')
        
        # Validate required fields
        required_fields = {
            'source_name': source_name,
            'source_code': source_code,
            'destination_name': destination_name,
            'destination_code': destination_code,
            'date': date
        }
        
        for field, value in required_fields.items():
            if not value:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate station codes format
        if not validate_station_code(source_code):
            return jsonify({
                'error': 'Invalid source station code format',
                'details': 'Station code should be 3-4 alphanumeric characters'
            }), 400
            
        if not validate_station_code(destination_code):
            return jsonify({
                'error': 'Invalid destination station code format',
                'details': 'Station code should be 3-4 alphanumeric characters'
            }), 400
        
        # Validate date format (YYYYMMDD)
        try:
            datetime.strptime(date, '%Y%m%d')
        except ValueError:
            return jsonify({
                'error': 'Invalid date format',
                'details': 'Date should be in YYYYMMDD format'
            }), 400

        # Load station codes for validation
        station_codes = load_station_codes()
        
        # Check if stations exist in our database (if we have station codes)
        if station_codes:
            if source_code not in station_codes:
                return jsonify({
                    'error': 'Unknown source station',
                    'details': f'Station code {source_code} not found in database'
                }), 404
            if destination_code not in station_codes:
                return jsonify({
                    'error': 'Unknown destination station',
                    'details': f'Station code {destination_code} not found in database'
                }), 404
        
        # Get trains between stations
        try:
            trains = pipeline.get_trains_between_stations(
                source_name,
                source_code,
                destination_name,
                destination_code,
                date
            )
        except ValueError as e:
            if "unseen labels" in str(e):
                return jsonify({
                    'error': 'Unknown station in route',
                    'details': 'One or more stations in the route are not in our training data'
                }), 400
            raise
        
        if not trains:
            return jsonify({
                'error': 'No trains found between stations',
                'details': 'The stations may be invalid or there are no trains running between them on the specified date'
            }), 404
            
        return jsonify({
            'status': 'success',
            'data': trains
        })
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@app.route('/api/train-schedule', methods=['GET'])
def get_train_schedule():
    try:
        if pipeline is None:
            return jsonify({
                'error': 'Service temporarily unavailable',
                'details': 'Train pipeline initialization failed'
            }), 503

        # Get parameters from query string
        train_name = request.args.get('train_name')
        train_number = request.args.get('train_number')
        date = request.args.get('date')
        
        # Validate required fields
        required_fields = {
            'train_name': train_name,
            'train_number': train_number,
            'date': date
        }
        
        for field, value in required_fields.items():
            if not value:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get train schedule with delays
        schedule = pipeline.get_train_schedule(
            train_name,
            train_number,
            date
        )
        
        if not schedule:
            return jsonify({'error': 'Failed to get train schedule'}), 404
            
        return jsonify({
            'status': 'success',
            'data': schedule
        })
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    if pipeline is None:
        return jsonify({'status': 'unhealthy', 'details': 'Train pipeline initialization failed'}), 503
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 