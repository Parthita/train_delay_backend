import requests
from bs4 import BeautifulSoup
import json
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class LiveTrainStatus:
    def __init__(self):
        self.base_url = "https://etrain.info/train"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def get_live_status(self, train_number):
        """Get live status of a train from etrain.info"""
        try:
            url = f"{self.base_url}/{train_number}/live"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the table containing live status
            status_table = soup.find('table', {'class': 'table'})
            if not status_table:
                return None
                
            stations_data = []
            rows = status_table.find_all('tr')[1:]  # Skip header row
            current_station_index = -1
            
            for idx, row in enumerate(rows):
                cols = row.find_all('td')
                if len(cols) >= 4:
                    status_text = cols[3].text.strip()
                    is_current = 'Just' in status_text or 'Now' in status_text
                    
                    if is_current:
                        current_station_index = idx
                    
                    station = {
                        'station_name': cols[0].text.strip(),
                        'station_code': cols[1].text.strip(),
                        'scheduled_arrival': cols[2].text.strip(),
                        'actual_arrival': status_text,
                        'delay': self._parse_delay(status_text),
                        'is_current_station': is_current,
                        'status': self._get_station_status(status_text)
                    }
                    stations_data.append(station)
            
            # Organize stations into passed, current, and upcoming
            passed_stations = stations_data[:current_station_index] if current_station_index > 0 else []
            current_station = stations_data[current_station_index] if current_station_index >= 0 else None
            upcoming_stations = stations_data[current_station_index + 1:] if current_station_index >= 0 else stations_data
            
            return {
                'passed_stations': passed_stations,
                'current_station': current_station,
                'upcoming_stations': upcoming_stations,
                'train_status': self._get_train_status(current_station, passed_stations)
            }
            
        except Exception as e:
            logger.error(f"Error fetching live status: {str(e)}")
            return None

    def _parse_delay(self, delay_text):
        """Parse delay text to get delay in minutes"""
        try:
            if 'Not Started' in delay_text or 'Not Arrived' in delay_text:
                return None
                
            # Extract delay in minutes using regex
            delay_match = re.search(r'(\d+)\s*min', delay_text)
            if delay_match:
                return int(delay_match.group(1))
            return 0
        except:
            return None

    def _get_station_status(self, status_text):
        """Get the status of a station"""
        if 'Not Started' in status_text:
            return 'not_started'
        elif 'Not Arrived' in status_text:
            return 'not_arrived'
        elif 'Just' in status_text or 'Now' in status_text:
            return 'current'
        elif 'Departed' in status_text:
            return 'departed'
        elif 'Arrived' in status_text:
            return 'arrived'
        else:
            return 'unknown'

    def _get_train_status(self, current_station, passed_stations):
        """Get overall train status"""
        if not current_station:
            return 'not_started'
        
        if current_station['status'] == 'current':
            return 'running'
        
        if len(passed_stations) > 0:
            return 'running'
            
        return 'unknown'

    def compare_with_prediction(self, live_status, predicted_delays):
        """Compare live status with predicted delays"""
        comparison_results = {
            'passed_stations': [],
            'current_station': None,
            'upcoming_stations': []
        }
        
        # Process passed stations
        for station in live_status['passed_stations']:
            station_code = station['station_code']
            live_delay = station['delay']
            predicted_delay = predicted_delays.get(station_code)
            
            comparison = self._create_comparison(station, live_delay, predicted_delay)
            comparison_results['passed_stations'].append(comparison)
        
        # Process current station
        if live_status['current_station']:
            station = live_status['current_station']
            station_code = station['station_code']
            live_delay = station['delay']
            predicted_delay = predicted_delays.get(station_code)
            
            comparison_results['current_station'] = self._create_comparison(
                station, live_delay, predicted_delay
            )
        
        # Process upcoming stations
        for station in live_status['upcoming_stations']:
            station_code = station['station_code']
            live_delay = station['delay']
            predicted_delay = predicted_delays.get(station_code)
            
            comparison = self._create_comparison(station, live_delay, predicted_delay)
            comparison_results['upcoming_stations'].append(comparison)
        
        return comparison_results

    def _create_comparison(self, station, live_delay, predicted_delay):
        """Create a comparison entry for a station"""
        comparison = {
            'station_code': station['station_code'],
            'station_name': station['station_name'],
            'scheduled_arrival': station['scheduled_arrival'],
            'actual_arrival': station['actual_arrival'],
            'live_delay': live_delay,
            'predicted_delay': predicted_delay,
            'status': station['status'],
            'is_current_station': station['is_current_station']
        }
        
        if live_delay is not None and predicted_delay is not None:
            comparison.update({
                'is_prediction_close': abs(live_delay - predicted_delay) <= 15,
                'difference': live_delay - predicted_delay
            })
        else:
            comparison.update({
                'is_prediction_close': None,
                'difference': None
            })
            
        return comparison 