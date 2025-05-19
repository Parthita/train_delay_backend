from flask import Flask, request, jsonify
from train_pipeline import TrainPipeline
import logging
from datetime import datetime
import os
import re

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

        # Validate required parameters
        if not all([train_number, station_name, date]):
            return jsonify({
                'error': 'Missing required fields: train_number, station_name, and date are required'
            }), 400

        # Get current running status
        running_status = get_running_status(train_number, station_name, date)
        if not running_status:
            return jsonify({
                'error': 'Failed to get running status'
            }), 500

        # Check if train journey is completed
        if not running_status.get('stations'):
            return jsonify({
                'status': 'success',
                'message': 'Train journey completed',
                'data': {
                    'stations': [],
                    'train_info': {
                        'number': train_number,
                        'scraped_at': running_status.get('scraped_at', '')
                    }
                }
            })

        # Find current station in running status
        current_station = None
        current_delay = 0
        for station in running_status.get('stations', []):
            if station.get('status') == 'Pending':
                current_station = station.get('station_name')
                delay_str = station.get('delay', '0 min')
                # Extract delay value from string (e.g., "15 min late" -> 15)
                delay_match = re.search(r'(\d+)', delay_str)
                if delay_match:
                    current_delay = int(delay_match.group(1))
                break

        if not current_station:
            return jsonify({
                'error': 'Could not determine current station'
            }), 500

        # Get predicted delays
        try:
            # Get train schedule first
            schedule = get_train_schedule(train_number, date)
            if not schedule:
                return jsonify({
                    'status': 'success',
                    'data': {
                        'current_status': running_status,
                        'current_station': current_station,
                        'current_delay': current_delay,
                        'prediction_available': False,
                        'message': 'No schedule available for this train'
                    }
                })

            # Find current station in schedule
            current_station_schedule = None
            for station in schedule.get('schedule', []):
                if station.get('station').lower() == current_station.lower():
                    current_station_schedule = station
                    break

            if not current_station_schedule:
                return jsonify({
                    'status': 'success',
                    'data': {
                        'current_status': running_status,
                        'current_station': current_station,
                        'current_delay': current_delay,
                        'prediction_available': False,
                        'message': 'Current station not found in schedule'
                    }
                })

            predicted_delay = current_station_schedule.get('predicted_delay', 0)
            delay_difference = abs(current_delay - predicted_delay)

            # Compare delays with 30-minute threshold
            is_prediction_reliable = delay_difference <= 30

            return jsonify({
                'status': 'success',
                'data': {
                    'current_status': running_status,
                    'current_station': current_station,
                    'current_delay': current_delay,
                    'predicted_delay': predicted_delay,
                    'delay_difference': delay_difference,
                    'is_prediction_reliable': is_prediction_reliable
                }
            })

        except Exception as e:
            return jsonify({
                'status': 'success',
                'data': {
                    'current_status': running_status,
                    'current_station': current_station,
                    'current_delay': current_delay,
                    'prediction_available': False,
                    'message': f'Error getting predictions: {str(e)}'
                }
            })

    except Exception as e:
        return jsonify({
            'error': f'Error processing request: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 