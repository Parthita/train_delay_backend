from flask import Flask, request, jsonify, g
from train_pipeline import TrainPipeline
import logging
from datetime import datetime
import os
import signal
from functools import wraps
import time
import uuid
import threading
from werkzeug.exceptions import RequestTimeout

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
pipeline = TrainPipeline()

# Global timeout value in seconds
REQUEST_TIMEOUT = 36000  # 1 hour

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Request timed out")

def timeout(seconds):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Set the signal handler and a timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                # Disable the alarm
                signal.alarm(0)
            return result
        return wrapper
    return decorator

@app.before_request
def before_request():
    # Generate a unique request ID
    g.request_id = str(uuid.uuid4())
    g.start_time = time.time()
    logger.info(f"Request started - ID: {g.request_id}")

@app.after_request
def after_request(response):
    # Calculate request duration
    duration = time.time() - g.start_time
    logger.info(f"Request completed - ID: {g.request_id} - Duration: {duration:.2f}s")
    return response

@app.errorhandler(RequestTimeout)
def handle_timeout(e):
    logger.error(f"Request timed out - ID: {g.request_id}")
    return jsonify({
        'status': 'error',
        'code': 504,
        'message': 'Request timed out. Please try again.',
        'request_id': g.request_id
    }), 504

@app.errorhandler(Exception)
def handle_error(e):
    logger.error(f"Error processing request - ID: {g.request_id}: {str(e)}")
    return jsonify({
        'status': 'error',
        'code': 500,
        'message': str(e),
        'request_id': g.request_id
    }), 500

@app.route('/api/trains-between', methods=['GET'])
@timeout(REQUEST_TIMEOUT)
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
                    'code': 400,
                    'message': f'Missing required field: {field}',
                    'request_id': g.request_id
                }), 400
        
        # Get trains between stations
        trains = pipeline.get_trains_between_stations(
            source_name,
            source_code,
            destination_name,
            destination_code,
            date
        )
        
        if not trains:
            return jsonify({
                'status': 'error',
                'code': 404,
                'message': 'No trains found between stations',
                'request_id': g.request_id
            }), 404
            
        return jsonify({
            'status': 'success',
            'data': trains,
            'request_id': g.request_id
        })
        
    except TimeoutError:
        logger.error(f"Request timed out - ID: {g.request_id}")
        return jsonify({
            'status': 'error',
            'code': 504,
            'message': 'Request timed out. Please try again.',
            'request_id': g.request_id
        }), 504
    except Exception as e:
        logger.error(f"Error processing request - ID: {g.request_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'code': 500,
            'message': str(e),
            'request_id': g.request_id
        }), 500

@app.route('/api/train-schedule', methods=['GET'])
@timeout(REQUEST_TIMEOUT)
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
                    'code': 400,
                    'message': f'Missing required field: {field}',
                    'request_id': g.request_id
                }), 400
        
        # Get train schedule with delays
        schedule = pipeline.get_train_schedule(
            train_name,
            train_number,
            date
        )
        
        if not schedule:
            return jsonify({
                'status': 'error',
                'code': 404,
                'message': 'Failed to get train schedule',
                'request_id': g.request_id
            }), 404
            
        return jsonify({
            'status': 'success',
            'data': schedule,
            'request_id': g.request_id
        })
        
    except TimeoutError:
        logger.error(f"Request timed out - ID: {g.request_id}")
        return jsonify({
            'status': 'error',
            'code': 504,
            'message': 'Request timed out. Please try again.',
            'request_id': g.request_id
        }), 504
    except Exception as e:
        logger.error(f"Error processing request - ID: {g.request_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'code': 500,
            'message': str(e),
            'request_id': g.request_id
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'request_id': g.request_id
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Set timeout for the server
    app.config['TIMEOUT'] = REQUEST_TIMEOUT
    app.run(host='0.0.0.0', port=port, threaded=True) 
