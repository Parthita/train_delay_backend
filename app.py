from flask import Flask, request, jsonify
from train_search import search_trains, get_train_schedule
from delay_scrapper import download_html, extract_delay_data_from_html
from model import train_model
from predict import predict_delays
import os
import pandas as pd
import json
from datetime import datetime
import threading
import queue

app = Flask(__name__)

# Queue for background tasks
task_queue = queue.Queue()

def process_train_delay(train_name: str, train_number: str):
    """Process train delay data in the background"""
    try:
        # Download and process delay data
        html_file = download_html(train_name, train_number)
        if html_file:
            extract_delay_data_from_html(html_file)
            
            # Train model for this train
            train_model(f"{train_number}.csv")
            
            # Clean up HTML file
            os.remove(html_file)
    except Exception as e:
        print(f"Error processing train {train_number}: {str(e)}")

def background_worker():
    """Background worker to process train delay data"""
    while True:
        task = task_queue.get()
        if task is None:
            break
        process_train_delay(task['train_name'], task['train_number'])
        task_queue.task_done()

# Start background worker
worker_thread = threading.Thread(target=background_worker, daemon=True)
worker_thread.start()

@app.route('/api/search', methods=['GET'])
def search():
    """Search for trains between stations"""
    source = request.args.get('source')
    dest = request.args.get('dest')
    date = request.args.get('date')
    
    if not all([source, dest, date]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    trains = search_trains(source, dest, date)
    return jsonify({'trains': trains})

@app.route('/api/schedule', methods=['GET'])
def schedule():
    """Get schedule for a specific train"""
    train_name = request.args.get('train_name')
    train_number = request.args.get('train_number')
    
    if not all([train_name, train_number]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    schedule = get_train_schedule(train_name, train_number)
    return jsonify({'schedule': schedule})

@app.route('/api/delays', methods=['GET'])
def delays():
    """Get delay predictions for a specific train"""
    train_name = request.args.get('train_name')
    train_number = request.args.get('train_number')
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    if not all([train_name, train_number]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    # Check if model exists for this train
    model_file = f"{train_number}_model.pkl"
    encoder_file = f"{train_number}_encoder.pkl"
    
    if not (os.path.exists(model_file) and os.path.exists(encoder_file)):
        # Queue the train for processing
        task_queue.put({'train_name': train_name, 'train_number': train_number})
        return jsonify({'message': 'Train data is being processed. Please try again in a few minutes.'}), 202
    
    # Get delay predictions
    predictions = predict_delays(train_number, date)
    return jsonify({'predictions': predictions})

@app.route('/api/route-delays', methods=['GET'])
def route_delays():
    """Get delay predictions for entire route of a train"""
    train_name = request.args.get('train_name')
    train_number = request.args.get('train_number')
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    if not all([train_name, train_number]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    # Get schedule first
    schedule = get_train_schedule(train_name, train_number)
    if not schedule:
        return jsonify({'error': 'Could not fetch train schedule'}), 404
    
    # Get delay predictions
    predictions = predict_delays(train_number, date)
    
    # Combine schedule with predictions
    route_delays = []
    for station in schedule:
        station_name = station['station']
        delay = next((p['delay'] for p in predictions if p['station'] == station_name), None)
        
        route_delays.append({
            'station': station_name,
            'arrival_time': station['arrival_time'],
            'departure_time': station['departure_time'],
            'predicted_delay': delay
        })
    
    return jsonify({'route_delays': route_delays})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 