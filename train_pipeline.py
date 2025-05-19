import json
import os
from datetime import datetime
import numpy as np
import time
import logging
from pathlib import Path
import shutil
from scrape_trains import scrape_trains_between
from scrape_schedule import scrape_train_schedule
from delay_scrapper import download_html, extract_delay_data_from_html
from model import train_model
from predict import predict_delays
import pandas as pd

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

class TrainPipeline:
    def __init__(self):
        # Use absolute paths for production deployment
        self.base_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.output_dir = self.base_dir / "pipeline_output"
        self.temp_dir = self.base_dir / "temp"
        
        # Create necessary directories
        self.output_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
        
        # Load station codes
        self.station_codes = {}
        try:
            with open(self.output_dir / 'stationcode.json', 'r') as f:
                self.station_codes = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load station codes: {e}")
        
        logger.info(f"Initialized pipeline with output_dir: {self.output_dir}")
        
    def _get_model_paths(self, train_number):
        """Get model file paths for a specific train."""
        return {
            'model': self.output_dir / f"{train_number}_model.pkl",
            'encoder': self.output_dir / f"{train_number}_encoder.pkl"
        }
        
    def _cleanup_files(self, files):
        """Clean up temporary files."""
        for file in files:
            if file and os.path.exists(file):
                try:
                    os.remove(file)
                    logger.debug(f"Cleaned up file: {file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {file}: {e}")
    
    def _wait_for_file(self, file_path, timeout=10, check_interval=0.5):
        """Wait for a file to exist with timeout."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if os.path.exists(file_path):
                return True
            time.sleep(check_interval)
        return False
        
    def process_train(self, train_info, date):
        """Process a single train: get history, train model, predict delays."""
        train_number = train_info['train_number']
        train_name = train_info['train_name']
        
        logger.info(f"Processing {train_name} ({train_number})...")
        
        # Initialize file paths
        html_file = None
        csv_file = Path(f"{train_number}.csv")  # Keep in current directory for model.py
        model_paths = self._get_model_paths(train_number)
        
        try:
            # Step 1: Get delay history
            logger.info(f"Downloading HTML for {train_name} ({train_number})...")
            html_file = download_html(train_name, train_number)
            if not html_file:
                logger.warning(f"No HTML data available for train {train_number}")
                return {
                    'train_number': train_number,
                    'train_name': train_name,
                    'status': 'no_data',
                    'message': 'No historical data available'
                }
                
            # Step 2: Extract delay data
            logger.info(f"Extracting delay data from HTML...")
            if not extract_delay_data_from_html(html_file, train_number):
                logger.warning(f"No delay data found for train {train_number}")
                return {
                    'train_number': train_number,
                    'train_name': train_name,
                    'status': 'no_data',
                    'message': 'No delay data found in history'
                }
            
            # Wait for CSV file to exist
            if not self._wait_for_file(csv_file):
                logger.warning(f"No delay history found for train {train_number}")
                return {
                    'train_number': train_number,
                    'train_name': train_name,
                    'status': 'no_data',
                    'message': 'No delay history available'
                }
            
            # Check if we have enough data
            df = pd.read_csv(csv_file)
            if len(df) < 2:  # Need at least 2 samples for train/test split
                logger.warning(f"Not enough delay data for train {train_number} (only {len(df)} samples)")
                return {
                    'train_number': train_number,
                    'train_name': train_name,
                    'status': 'insufficient_data',
                    'message': f'Only {len(df)} samples available, need at least 2'
                }
            
            # Step 3: Train model
            logger.info(f"Training model for train {train_number}...")
            model_result = train_model(train_number)  # model.py expects CSV in current directory
            if not model_result:
                logger.warning(f"Could not train model for train {train_number}")
                return {
                    'train_number': train_number,
                    'train_name': train_name,
                    'status': 'model_failed',
                    'message': 'Failed to train prediction model'
                }
            
            # Wait for model files to be saved
            if not all(self._wait_for_file(path) for path in model_paths.values()):
                logger.error(f"Model files not found for train {train_number}")
                return {
                    'train_number': train_number,
                    'train_name': train_name,
                    'status': 'model_failed',
                    'message': 'Model files not found'
                }
            
            # Step 4: Predict delays
            logger.info(f"Predicting delays for train {train_number} on {date}...")
            delays = predict_delays(train_number, date)
            if not delays:
                logger.error(f"Failed to predict delays for train {train_number}")
                return {
                    'train_number': train_number,
                    'train_name': train_name,
                    'status': 'prediction_failed',
                    'message': 'Failed to predict delays'
                }
            
            # Debug logging for delays
            logger.info("\nRaw delays from model:")
            for station, delay in delays.items():
                logger.info(f"{station}: {delay}")
            
            # Ensure source station has no negative delay
            source_station = next((station for station in train_info.get('stations', []) 
                                 if station.get('is_source', False)), None)
            if source_station:
                source_code = source_station.get('code')
                if source_code in delays and delays[source_code] < 0:
                    delays[source_code] = 0
                    logger.info(f"Adjusted source station {source_code} delay to 0")
            
            # Add predicted delays to train info
            train_info['predicted_delays'] = delays
            train_info['status'] = 'success'
            
            return train_info
            
        except Exception as e:
            logger.error(f"Error processing train {train_number}: {str(e)}")
            return {
                'train_number': train_number,
                'train_name': train_name,
                'status': 'error',
                'message': str(e)
            }
        finally:
            # Clean up temporary files
            self._cleanup_files([html_file, csv_file])
            # Don't delete model files until after prediction is done
            self._cleanup_files(model_paths.values())
    
    def get_trains_between_stations(self, src_name, src_code, dst_name, dst_code, date):
        """Get all trains between stations with their predicted delays."""
        logger.info(f"Fetching trains between {src_name} and {dst_name}...")
        
        try:
            # Step 1: Get all trains between stations
            trains = scrape_trains_between(src_name, src_code, dst_name, dst_code, date)
            if not trains:
                logger.warning("No trains found between stations")
                return {
                    'status': 'no_trains',
                    'message': 'No trains found between the specified stations',
                    'data': []
                }
                
            # Step 2: Process each train
            processed_trains = []
            for train in trains:
                # Add source and destination info
                train['stations'] = [
                    {'code': src_code, 'name': src_name, 'is_source': True},
                    {'code': dst_code, 'name': dst_name, 'is_destination': True}
                ]
                
                result = self.process_train(train, date)
                if result:
                    processed_trains.append(result)
            
            if not processed_trains:
                return {
                    'status': 'no_data',
                    'message': 'No train data could be processed',
                    'data': []
                }
            
            # Step 3: Save results to two different files
            # File 1: All train details with delays
            output_file = self.output_dir / 'trains_between_stations.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(processed_trains, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
            logger.info(f"Saved {len(processed_trains)} trains to {output_file}")
            
            # File 2: Simplified version with just essential info and delays
            simplified_trains = []
            for train in processed_trains:
                if train.get('status') == 'success':
                    simplified = {
                        'train_number': train['train_number'],
                        'train_name': train['train_name'],
                        'source': train['source'],
                        'departure_time': train['departure_time'],
                        'destination': train['destination'],
                        'arrival_time': train['arrival_time'],
                        'source_delay': train.get('source_delay', 0),
                        'destination_delay': train.get('destination_delay', 0)
                    }
                    simplified_trains.append(simplified)
            
            return {
                'status': 'success',
                'data': simplified_trains
            }
            
        except Exception as e:
            logger.error(f"Error getting trains between stations: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'data': []
            }
    
    def get_train_schedule(self, train_name, train_number, date):
        """Get train schedule with predicted delays."""
        try:
            # Get train schedule
            schedule = scrape_train_schedule(train_name, train_number, date)
            if not schedule:
                return {
                    'status': 'no_schedule',
                    'message': 'No schedule found for the train',
                    'data': None
                }
            
            # Process train for delay predictions
            result = self.process_train({
                'train_number': train_number,
                'train_name': train_name,
                'stations': schedule.get('stations', [])
            }, date)
            
            if result.get('status') == 'success':
                # Add delays to schedule
                schedule['predicted_delays'] = result.get('predicted_delays', {})
                return {
                    'status': 'success',
                    'data': schedule
                }
            else:
                return {
                    'status': result.get('status', 'error'),
                    'message': result.get('message', 'Failed to get train schedule'),
                    'data': schedule
                }
                
        except Exception as e:
            logger.error(f"Error getting train schedule: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'data': None
            }

def main():
    # Example usage
    pipeline = TrainPipeline()
    result = pipeline.get_trains_between_stations(
        "Howrah", "HWH",
        "New Delhi", "NDLS",
        "2024-05-20"
    )
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main() 