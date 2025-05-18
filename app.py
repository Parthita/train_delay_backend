from flask import Flask, request, jsonify
from train_pipeline import TrainPipeline
import logging
from datetime import datetime
import os
from live_status_scraper import get_live_status
from predict import predict_delays

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

@app.route('/api/live-status', methods=['GET'])
def get_live_train_status():
    try:
        # Get parameters from query string
        train_name = request.args.get('train_name')
        train_number = request.args.get('train_number')
        
        # Validate required fields
        required_fields = {
            'train_name': train_name,
            'train_number': train_number
        }
        
        for field, value in required_fields.items():
            if not value:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get live status from website
        live_status = get_live_status(train_name, train_number)
        if not live_status:
            return jsonify({'error': 'Failed to get live status'}), 404
            
        # Get predicted delays for upcoming stations
        current_date = datetime.now().strftime('%Y-%m-%d')
        predicted_delays = predict_delays(train_number, current_date)
        
        if predicted_delays:
            # Compare predicted delays with actual delays
            current_delay = live_status['current_delay']
            if current_delay:
                try:
                    actual_delay = int(current_delay.replace('+', '').replace(' min', ''))
                    # Get predicted delay for current station
                    current_station = live_status['current_station']['station']
                    predicted_delay = predicted_delays.get(current_station, 0)
                    
                    # If prediction is within ±20 minutes of actual delay, use predictions for upcoming stations
                    if abs(predicted_delay - actual_delay) <= 20:
                        for station in live_status['upcoming_stations']:
                            station_name = station['station']
                            if station_name in predicted_delays:
                                station['predicted_delay'] = predicted_delays[station_name]
                            else:
                                station['predicted_delay'] = None
                except ValueError:
                    logger.warning(f"Could not parse current delay: {current_delay}")
        
        return jsonify({
            'status': 'success',
            'data': live_status
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