import queue
import threading
import time
import logging
from pathlib import Path
import json
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TrainQueue:
    def __init__(self, output_dir, process_train_func):
        self.queue = queue.Queue()
        self.results = {}
        self.processing = False
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.lock = threading.Lock()
        self.process_train_func = process_train_func
        
    def add_trains(self, trains, src_code, dst_code, date):
        """Add trains to the processing queue."""
        for train in trains:
            train['stations'] = [
                {'code': src_code, 'name': train['source'], 'is_source': True},
                {'code': dst_code, 'name': train['destination'], 'is_destination': True}
            ]
            self.queue.put((train, date))
        
        # Start processing if not already running
        if not self.processing:
            self.start_processing()
    
    def start_processing(self):
        """Start the processing thread."""
        self.processing = True
        self.worker_thread = threading.Thread(target=self._process_queue)
        self.worker_thread.daemon = True
        self.worker_thread.start()
    
    def _process_queue(self):
        """Process trains in the queue."""
        while not self.queue.empty():
            try:
                train, date = self.queue.get()
                train_number = train['train_number']
                
                # Process the train using the provided function
                result = self.process_train_func(train, date)
                
                if result:
                    # Add delays to train info
                    delays = result.get('predicted_delays', {})
                    train['source_delay'] = delays.get(train['stations'][0]['code'], "no data found")
                    train['destination_delay'] = delays.get(train['stations'][1]['code'], "no data found")
                else:
                    train['source_delay'] = "no data found"
                    train['destination_delay'] = "no data found"
                
                # Save result
                with self.lock:
                    self.results[train_number] = train
                    self._save_results()
                
                # Mark task as done
                self.queue.task_done()
                
                # Small delay to prevent overwhelming the system
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing train {train.get('train_number', 'unknown')}: {e}")
                # Mark task as done even if it failed
                self.queue.task_done()
        
        self.processing = False
    
    def _save_results(self):
        """Save current results to files."""
        try:
            # Save full results
            output_file = self.output_dir / 'trains_between_stations.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.results.values()), f, indent=2, ensure_ascii=False)
            
            # Save simplified results
            simplified_trains = []
            for train in self.results.values():
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
                json.dump(simplified_trains, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def get_results(self):
        """Get current results."""
        with self.lock:
            return list(self.results.values())
    
    def is_processing(self):
        """Check if queue is still being processed."""
        return self.processing or not self.queue.empty() 