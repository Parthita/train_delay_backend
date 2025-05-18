import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

def get_live_status(train_name: str, train_number: str):
    """
    Get live running status of a train from etrain.info
    Returns a dictionary containing:
    - Current station and status
    - Passed stations with actual times
    - Upcoming stations with scheduled times
    - Current delay
    """
    url = f"https://etrain.info/train/{train_name.replace(' ', '-')}-{train_number}/live"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the live status table - it's in a div with class 'bx3_brd'
        status_div = soup.find('div', {'class': 'bx3_brd'})
        if not status_div:
            print("Could not find status div")
            return None
            
        # Find the table inside the div
        status_table = status_div.find('table', {'class': 'nocps'})
        if not status_table:
            print("Could not find status table")
            return None
            
        # Initialize lists for different station categories
        passed_stations = []
        current_station = None
        upcoming_stations = []
        
        # Process each row in the table
        for row in status_table.find_all('tr')[1:]:  # Skip header row
            cols = row.find_all('td')
            if len(cols) >= 4:
                # Get station name and code
                station_cell = cols[1]
                station_name = station_cell.find('div', class_='fixwelps').text.strip() if station_cell.find('div', class_='fixwelps') else station_cell.text.strip()
                
                # Get scheduled times
                scheduled_arrival = cols[2].text.strip()
                scheduled_departure = cols[3].text.strip()
                
                # Get actual times and delay if available
                actual_arrival = None
                actual_departure = None
                delay = None
                
                if len(cols) > 4:
                    actual_arrival = cols[4].text.strip()
                if len(cols) > 5:
                    actual_departure = cols[5].text.strip()
                if len(cols) > 6:
                    delay = cols[6].text.strip()
                
                # Determine station status
                if actual_arrival and actual_departure:
                    # Station has been passed
                    passed_stations.append({
                        'station': station_name,
                        'scheduled_arrival': scheduled_arrival,
                        'scheduled_departure': scheduled_departure,
                        'actual_arrival': actual_arrival,
                        'actual_departure': actual_departure,
                        'delay': delay
                    })
                elif actual_arrival and not actual_departure:
                    # Current station
                    current_station = {
                        'station': station_name,
                        'scheduled_arrival': scheduled_arrival,
                        'scheduled_departure': scheduled_departure,
                        'actual_arrival': actual_arrival,
                        'delay': delay
                    }
                else:
                    # Upcoming station
                    upcoming_stations.append({
                        'station': station_name,
                        'scheduled_arrival': scheduled_arrival,
                        'scheduled_departure': scheduled_departure
                    })
        
        # Get current delay
        current_delay = None
        if current_station:
            current_delay = current_station['delay']
        elif passed_stations:
            current_delay = passed_stations[-1]['delay']
            
        # Get train info from the header
        train_info = {}
        header_div = soup.find('div', {'class': 'bx3_bgm'})
        if header_div:
            train_info['name'] = header_div.text.strip()
            
        return {
            'train_name': train_name,
            'train_number': train_number,
            'current_delay': current_delay,
            'current_station': current_station,
            'passed_stations': passed_stations,
            'upcoming_stations': upcoming_stations
        }
        
    except Exception as e:
        print(f"Error getting live status: {str(e)}")
        return None 