from flask import Flask, request, jsonify
from train_pipeline import TrainPipeline
import logging
from datetime import datetime
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
pipeline = TrainPipeline()

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

@app.route('/api/train-running-status', methods=['GET'])
def get_train_running_status():
    try:
        # Get parameters from query string
        train_number = request.args.get('train_number')
        station_name = request.args.get('station_name')
        date = request.args.get('date')
        
        # Validate required fields
        required_fields = {
            'train_number': train_number,
            'station_name': station_name,
            'date': date
        }
        
        for field, value in required_fields.items():
            if not value:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get current running status from confirmtkt
        from confirmtkt_scraper import get_train_status
        current_status = get_train_status(train_number, station_name, date)
        
        if not current_status:
            return jsonify({'error': 'Failed to get current running status'}), 404
            
        # Find current station in the status
        current_station = None
        for station in current_status['stations']:
            if station['status'] == 'Pending':
                current_station = station
                break
                
        if not current_station:
            return jsonify({
                'status': 'success',
                'message': 'Train journey completed',
                'data': current_status
            })
            
        # Get current delay from confirmtkt
        current_delay = current_station.get('delay', '0')
        if isinstance(current_delay, str):
            # Extract numeric value from delay string (e.g., "15 min late" -> 15)
            import re
            delay_match = re.search(r'(\d+)', current_delay)
            current_delay = int(delay_match.group(1)) if delay_match else 0
            
        # Try to get predicted delays
        try:
            from predict import predict_delays
            predicted_delays = predict_delays(train_number, date)
            
            if predicted_delays:
                # Try to find matching station in predicted delays
                # First try exact match
                predicted_delay = predicted_delays.get(current_station['station_name'])
                
                # If no exact match, try case-insensitive match
                if predicted_delay is None:
                    station_lower = current_station['station_name'].lower()
                    for pred_station, delay in predicted_delays.items():
                        if pred_station.lower() == station_lower:
                            predicted_delay = delay
                            break
                
                if predicted_delay is not None:
                    # Compare delays
                    delay_diff = abs(predicted_delay - current_delay)
                    
                    response_data = {
                        'current_status': current_status,
                        'current_station': current_station['station_name'],
                        'current_delay': current_delay,
                        'predicted_delay': predicted_delay,
                        'delay_difference': delay_diff,
                        'is_prediction_reliable': delay_diff <= 15
                    }
                else:
                    # No matching station found in predictions
                    response_data = {
                        'current_status': current_status,
                        'current_station': current_station['station_name'],
                        'current_delay': current_delay,
                        'prediction_available': False,
                        'message': 'No prediction available for current station'
                    }
            else:
                # No predictions available
                response_data = {
                    'current_status': current_status,
                    'current_station': current_station['station_name'],
                    'current_delay': current_delay,
                    'prediction_available': False,
                    'message': 'No predictions available for this train'
                }
        except Exception as e:
            logger.error(f"Error getting predictions: {str(e)}")
            # Return current status without predictions
            response_data = {
                'current_status': current_status,
                'current_station': current_station['station_name'],
                'current_delay': current_delay,
                'prediction_available': False,
                'message': 'Error getting predictions'
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