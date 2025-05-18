from flask import Flask, request, jsonify
from train_pipeline import TrainPipeline
from live_status import LiveTrainStatus
import logging
from datetime import datetime
import os
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create necessary directories
BASE_DIR = Path(__file__).parent
PIPELINE_OUTPUT_DIR = BASE_DIR / "pipeline_output"
PIPELINE_OUTPUT_DIR.mkdir(exist_ok=True)

# Create default stationcode.json if it doesn't exist
STATION_CODE_FILE = PIPELINE_OUTPUT_DIR / "stationcode.json"
if not STATION_CODE_FILE.exists():
    default_station_codes = {
        "HOWRAH JN": "HWH",
        "NEW DELHI": "NDLS",
        "BARDDHAMAN JN": "BWN",
        "DURGAPUR": "DGR",
        "ASANSOL JN": "ASN",
        "CHITTARANJAN": "CRJ",
        "JAMTARA": "JMT",
        "MADHUPUR JN": "MDP",
        "JASIDIH JN": "JSME",
        "JHAJHA": "JAJ",
        "JAMUI": "JMU",
        "KIUL JN": "KIUL",
        "MOKAMEH JN": "MKA",
        "BARH": "BARH",
        "BAKHTIYARPUR JN": "BKP",
        "PATNA JN": "PNBE",
        "DANAPUR": "DNR",
        "ARA": "ARA",
        "BUXAR": "BXR",
        "PT DEEN DAYAL UPADHYAY JN": "DDU",
        "PRAYAGRAJ JN": "PRYJ",
        "KANPUR CENTRAL": "CNB",
        "ETAWAH": "ETW",
        "TUNDLA JN": "TDL",
        "ALIGARH JN": "ALJN"
    }
    import json
    with open(STATION_CODE_FILE, 'w', encoding='utf-8') as f:
        json.dump(default_station_codes, f, indent=2, ensure_ascii=False)
    logger.info(f"Created default stationcode.json at {STATION_CODE_FILE}")

app = Flask(__name__)
pipeline = TrainPipeline()

@app.route('/')
def home():
    return "Welcome to the Train API! Try /api/trains-between or /api/train-schedule"

@app.route('/api/trains-between', methods=['GET'])
def get_trains_between():
    try:
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
        
        # Get trains between stations
        trains = pipeline.get_trains_between_stations(
            source_name,
            source_code,
            destination_name,
            destination_code,
            date
        )
        
        if not trains:
            return jsonify({'error': 'No trains found between stations'}), 404
            
        return jsonify({
            'status': 'success',
            'data': trains
        })
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/train-schedule', methods=['GET'])
def get_train_schedule():
    try:
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

@app.route('/api/live-status', methods=['GET'])
def get_live_status():
    try:
        # Get parameters from query string
        train_number = request.args.get('train_number')
        
        # Validate required fields
        if not train_number:
            return jsonify({'error': 'Missing required field: train_number'}), 400
        
        # Initialize live status checker
        live_status = LiveTrainStatus()
        
        # Get live status from etrain.info
        current_status = live_status.get_live_status(train_number)
        if not current_status:
            return jsonify({'error': 'Failed to get live status'}), 404
            
        # Get predicted delays from pipeline
        predicted_delays = pipeline.get_predicted_delays(train_number)
        
        # Compare live status with predictions
        comparison_results = live_status.compare_with_prediction(
            current_status,
            predicted_delays
        )
        
        # Prepare the response
        response_data = {
            'train_number': train_number,
            'train_status': current_status['train_status'],
            'current_location': {
                'station': current_status['current_station']['station_name'] if current_status['current_station'] else None,
                'station_code': current_status['current_station']['station_code'] if current_status['current_station'] else None,
                'current_delay': current_status['current_station']['delay'] if current_status['current_station'] else None,
                'predicted_delay': comparison_results['current_station']['predicted_delay'] if comparison_results['current_station'] else None
            },
            'passed_stations': comparison_results['passed_stations'],
            'upcoming_stations': comparison_results['upcoming_stations'],
            'prediction_accuracy': {
                'total_stations': len(comparison_results['passed_stations']),
                'accurate_predictions': sum(1 for station in comparison_results['passed_stations'] 
                                         if station.get('is_prediction_close') is True),
                'accuracy_percentage': round(
                    sum(1 for station in comparison_results['passed_stations'] 
                        if station.get('is_prediction_close') is True) * 100 / 
                    len(comparison_results['passed_stations'])
                    if comparison_results['passed_stations'] else 0, 2
                )
            }
        }
        
        return jsonify({
            'status': 'success',
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
