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
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    station = {
                        'station_name': cols[0].text.strip(),
                        'station_code': cols[1].text.strip(),
                        'scheduled_arrival': cols[2].text.strip(),
                        'actual_arrival': cols[3].text.strip(),
                        'delay': self._parse_delay(cols[3].text.strip())
                    }
                    stations_data.append(station)
            
            return stations_data
            
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

    def compare_with_prediction(self, live_status, predicted_delays):
        """Compare live status with predicted delays"""
        comparison_results = []
        
        for station in live_status:
            station_code = station['station_code']
            live_delay = station['delay']
            
            # Find predicted delay for this station
            predicted_delay = next(
                (delay for station_name, delay in predicted_delays.items() 
                 if station_name == station_code),
                None
            )
            
            if live_delay is not None and predicted_delay is not None:
                # Check if predictions are within ±15 minutes
                is_close = abs(live_delay - predicted_delay) <= 15
                
                comparison_results.append({
                    'station_code': station_code,
                    'station_name': station['station_name'],
                    'live_delay': live_delay,
                    'predicted_delay': predicted_delay,
                    'is_prediction_close': is_close,
                    'difference': live_delay - predicted_delay
                })
            else:
                comparison_results.append({
                    'station_code': station_code,
                    'station_name': station['station_name'],
                    'live_delay': live_delay,
                    'predicted_delay': predicted_delay,
                    'is_prediction_close': None,
                    'difference': None
                })
        
        return comparison_results 