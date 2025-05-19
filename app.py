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
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}',
                    'data': None
                }), 400
        
        # Get trains between stations
        result = pipeline.get_trains_between_stations(
            source_name,
            source_code,
            destination_name,
            destination_code,
            date
        )
        
        # Handle different response statuses
        if result['status'] == 'no_trains':
            return jsonify({
                'status': 'success',
                'message': 'No trains found between stations',
                'data': []
            })
        elif result['status'] == 'error':
            return jsonify({
                'status': 'error',
                'message': result['message'],
                'data': None
            }), 500
        else:
            return jsonify(result)
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'data': None
        }), 500

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
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}',
                    'data': None
                }), 400
        
        # Get train schedule with delays
        result = pipeline.get_train_schedule(
            train_name,
            train_number,
            date
        )
        
        # Handle different response statuses
        if result['status'] == 'no_schedule':
            return jsonify({
                'status': 'success',
                'message': 'No schedule found for the train',
                'data': None
            })
        elif result['status'] == 'error':
            return jsonify({
                'status': 'error',
                'message': result['message'],
                'data': None
            }), 500
        else:
            return jsonify(result)
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'data': None
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'success',
        'message': 'Service is healthy',
        'data': {
            'timestamp': datetime.utcnow().isoformat()
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 