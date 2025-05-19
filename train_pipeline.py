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
        self._load_station_codes()
        
        logger.info(f"Initialized pipeline with output_dir: {self.output_dir}")
        
    def _load_station_codes(self):
        """Load and validate station codes from JSON file."""
        station_file = self.output_dir / 'stationcode.json'
        
        try:
            if not station_file.exists():
                logger.error(f"Station code file not found: {station_file}")
                return
                
            with open(station_file, 'r', encoding='utf-8') as f:
                try:
                    station_data = json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in station code file: {e}")
                    return
                
                if not isinstance(station_data, dict):
                    logger.error("Station data must be a dictionary")
                    return
                    
                stations = station_data.get('stations', [])
                if not isinstance(stations, list):
                    logger.error("Stations must be a list")
                    return
                
                # Convert to dictionary with stnCode as key
                for station in stations:
                    if not isinstance(station, dict):
                        logger.warning(f"Invalid station entry: {station}")
                        continue
                        
                    stn_code = station.get('stnCode')
                    if not stn_code:
                        logger.warning(f"Station missing code: {station}")
                        continue
                        
                    self.station_codes[stn_code] = station
                
                logger.info(f"Successfully loaded {len(self.station_codes)} station codes")
                
        except Exception as e:
            logger.error(f"Failed to load station codes: {e}")
            # Don't raise the exception, just log it and continue with empty station codes
        
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
        csv_file = Path(f"{train_number}.csv")
        model_paths = self._get_model_paths(train_number)
        
        # Check if we already have a model and history
        if all(path.exists() for path in model_paths.values()) and csv_file.exists():
            logger.info(f"Using existing model and history for train {train_number}")
            try:
                # Step 4: Predict delays using existing model
                logger.info(f"Predicting delays for train {train_number} on {date}...")
                delays = predict_delays(train_number, date)
                if delays:
                    train_info['predicted_delays'] = delays
                    return train_info
            except Exception as e:
                logger.error(f"Error using existing model for train {train_number}: {e}")
        
        try:
            # Step 1: Get delay history with timeout
            logger.info(f"Downloading HTML for {train_name} ({train_number})...")
            try:
                html_file = download_html(train_name, train_number)
                if not html_file:
                    logger.error(f"Failed to download HTML for train {train_number}")
                    return self._create_empty_response(train_info)
            except TimeoutError:
                logger.error(f"Timeout while downloading HTML for train {train_number}")
                return self._create_empty_response(train_info)
            except Exception as e:
                logger.error(f"Error downloading HTML for train {train_number}: {e}")
                return self._create_empty_response(train_info)
                
            # Step 2: Extract delay data with timeout
            logger.info(f"Extracting delay data from HTML...")
            try:
                if not extract_delay_data_from_html(html_file, train_number):
                    logger.warning(f"No delay data found in HTML for train {train_number}")
                    return self._create_empty_response(train_info)
            except TimeoutError:
                logger.error(f"Timeout while extracting delay data for train {train_number}")
                return self._create_empty_response(train_info)
            except Exception as e:
                logger.error(f"Error extracting delay data for train {train_number}: {e}")
                return self._create_empty_response(train_info)
            
            # Wait for CSV file to exist
            if not self._wait_for_file(csv_file, timeout=5):  # Reduced timeout
                logger.error(f"No delay history found for train {train_number}")
                return self._create_empty_response(train_info)
            
            # Check if we have enough data
            df = pd.read_csv(csv_file)
            if len(df) < 2:  # Need at least 2 samples for train/test split
                logger.warning(f"Not enough delay data for train {train_number} (only {len(df)} samples)")
                return self._create_empty_response(train_info)
            
            # Step 3: Train model
            logger.info(f"Training model for train {train_number}...")
            model_result = train_model(train_number)
            if not model_result:
                logger.warning(f"Could not train model for train {train_number} - skipping")
                return self._create_empty_response(train_info)
            
            # Wait for model files to be saved
            if not all(self._wait_for_file(path, timeout=5) for path in model_paths.values()):  # Reduced timeout
                logger.error(f"Model files not found for train {train_number}")
                return self._create_empty_response(train_info)
            
            # Step 4: Predict delays
            logger.info(f"Predicting delays for train {train_number} on {date}...")
            delays = predict_delays(train_number, date)
            if not delays:
                logger.error(f"Failed to predict delays for train {train_number}")
                return self._create_empty_response(train_info)
            
            # Debug logging for delays
            logger.info("\nRaw delays from model:")
            for station, delay in delays.items():
                logger.info(f"{station}: {delay}")
            
            # Add predicted delays to train info
            train_info['predicted_delays'] = delays
            return train_info
            
        except Exception as e:
            logger.error(f"Error processing train {train_number}: {e}")
            return self._create_empty_response(train_info)
        finally:
            # Clean up temporary files
            self._cleanup_files([html_file, csv_file])
            # Don't delete model files until after prediction is done
            self._cleanup_files(model_paths.values())
    
    def _create_empty_response(self, train_info):
        """Create a response with 'no data found' for all stations."""
        train_info['predicted_delays'] = {station['code']: "no data found" 
                                        for station in train_info.get('stations', [])}
        return train_info

    def _get_station_info(self, station_code):
        """Get station information from stationcode.json."""
        if not station_code:
            logger.warning("Empty station code provided")
            return None
            
        if station_code in self.station_codes:
            return self.station_codes[station_code]
            
        logger.warning(f"Unknown station code: {station_code}")
        return None

    def get_trains_between_stations(self, src_name, src_code, dst_name, dst_code, date):
        """Get all trains between stations with their predicted delays."""
        logger.info(f"Fetching trains between {src_name} and {dst_name}...")
        
        # Step 1: Get all trains between stations
        trains = scrape_trains_between(src_name, src_code, dst_name, dst_code, date)
        if not trains:
            logger.warning("No trains found between stations")
            return None
            
        # Step 2: Process each train
        processed_trains = []
        for train in trains:
            try:
                # Add source and destination info
                train['stations'] = [
                    {'code': src_code, 'name': src_name, 'is_source': True},
                    {'code': dst_code, 'name': dst_name, 'is_destination': True}
                ]
                
                result = self.process_train(train, date)
                if result:
                    # Add source and destination delays to train info
                    delays = result.get('predicted_delays', {})
                    train['source_delay'] = delays.get(src_code, "no data found")
                    train['destination_delay'] = delays.get(dst_code, "no data found")
                    processed_trains.append(train)
            except Exception as e:
                logger.error(f"Error processing train {train.get('train_number', 'unknown')}: {e}")
                # Add train with "no data found" for delays
                train['source_delay'] = "no data found"
                train['destination_delay'] = "no data found"
                processed_trains.append(train)
        
        # Step 3: Save results to two different files
        if processed_trains:
            # File 1: All train details with delays
            output_file = self.output_dir / 'trains_between_stations.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(processed_trains, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
            logger.info(f"Saved {len(processed_trains)} trains to {output_file}")
            
            # File 2: Simplified version with just essential info and delays
            simplified_trains = []
            for train in processed_trains:
                simplified = {
                    'train_number': train['train_number'],
                    'train_name': train['train_name'],
                    'source': train['source'],
                    'departure_time': train['departure_time'],
                    'destination': train['destination'],
                    'arrival_time': train['arrival_time'],
                    'duration': train['duration'],
                    'source_delay': train['source_delay'],
                    'destination_delay': train['destination_delay'],
                    'running_days': train['running_days'],
                    'booking_classes': train['booking_classes'],
                    'has_pantry': train['has_pantry']
                }
                simplified_trains.append(simplified)
            
            simplified_file = self.output_dir / 'trains_with_delays.json'
            with open(simplified_file, 'w', encoding='utf-8') as f:
                json.dump(simplified_trains, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
            logger.info(f"Saved simplified train data with delays to {simplified_file}")
        
        return processed_trains
    
    def get_train_schedule(self, train_name, train_number, date):
        """Get complete train schedule with predicted delays."""
        logger.info(f"Fetching schedule for {train_name} ({train_number})...")
        
        try:
            # Step 1: Get train schedule
            url = f"https://etrain.info/train/{train_name.replace(' ', '-')}-{train_number}/schedule"
            schedule_data = scrape_train_schedule(url)
            
            if not schedule_data:
                logger.error(f"Failed to get schedule for train {train_number}")
                return None
                
            # Set source and destination flags in schedule
            if schedule_data['schedule']:
                schedule_data['schedule'][0]['is_source'] = True
                schedule_data['schedule'][-1]['is_destination'] = True
                
            # Step 2: Process train (get history, train model, predict delays)
            train_info = {
                'train_number': train_number,
                'train_name': train_name,
                'stations': []  # Initialize stations list
            }
            
            # Add all stations from schedule to train_info using their codes
            for station in schedule_data['schedule']:
                if 'station_code' in station:  # Use the code directly from schedule
                    train_info['stations'].append({
                        'code': station['station_code'],
                        'name': station['name'],
                        'is_source': station.get('is_source', False),
                        'is_destination': station.get('is_destination', False)
                    })
                    logger.info(f"Added station to train_info: {station['name']} (code: {station['station_code']})")
            
            result = self.process_train(train_info, date)
            if not result:
                # If processing fails, set all delays to "no data found"
                for station in schedule_data['schedule']:
                    station['predicted_delay'] = "no data found"
                return schedule_data
                
            # Step 3: Add predicted delays to schedule
            delays = result.get('predicted_delays', {})
            logger.info("\nPredicted delays from model:")
            for station, delay in delays.items():
                logger.info(f"{station}: {delay}")
                
            for station in schedule_data['schedule']:
                if 'station_code' in station:
                    # Get delay using station code directly from schedule
                    delay = delays.get(station['station_code'], "no data found")
                    station['predicted_delay'] = delay
                    logger.info(f"Added delay for {station['name']} (code: {station['station_code']}): {delay}")
                else:
                    logger.warning(f"No station code found for {station['name']}")
                    station['predicted_delay'] = "no data found"
            
            # Step 4: Save results
            output_file = self.output_dir / 'train_schedule_with_delays.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(schedule_data, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
            logger.info(f"Saved schedule with delays to {output_file}")
            
            return schedule_data
            
        except Exception as e:
            logger.error(f"Error getting train schedule: {e}")
            # Return schedule with "no data found" for all stations
            if schedule_data and 'schedule' in schedule_data:
                for station in schedule_data['schedule']:
                    station['predicted_delay'] = "no data found"
            return schedule_data

def main():
    pipeline = TrainPipeline()
    
    # Example 1: Get trains between stations with predicted delays
    src_name = "Howrah Jn"
    src_code = "HWH"
    dst_name = "New Delhi"
    dst_code = "NDLS"
    date = "20250521"
    
    logger.info("=== Getting trains between stations ===")
    trains_data = pipeline.get_trains_between_stations(
        src_name, src_code, dst_name, dst_code, date
    )
    
    if trains_data:
        logger.info("\nSample of trains found:")
        for train in trains_data[:3]:
            logger.info(f"\nTrain: {train['train_name']} ({train['train_number']})")
            logger.info(f"Source delay: {train['source_delay']} minutes")
            logger.info(f"Destination delay: {train['destination_delay']} minutes")
    
    # Example 2: Get complete schedule with predicted delays
    logger.info("\n=== Getting complete schedule ===")
    train_name = "Poorva Express"
    train_number = "12303"
    
    schedule_data = pipeline.get_train_schedule(train_name, train_number, date)
    
    if schedule_data:
        logger.info("\nSample of schedule with delays:")
        for station in schedule_data['schedule'][:3]:
            logger.info(f"\nStation: {station['name']}")
            logger.info(f"Arrival: {station['arrival']}")
            logger.info(f"Departure: {station['departure']}")
            logger.info(f"Predicted delay: {station['predicted_delay']} minutes")

if __name__ == "__main__":
    main() 