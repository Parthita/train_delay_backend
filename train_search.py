import requests
from bs4 import BeautifulSoup
import json
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/114.0.0.0 Safari/537.36"
}

def search_trains(source_station: str, dest_station: str, date: str):
    """
    Search for trains between source and destination stations on a given date.
    Returns a list of train details including train number, name, and schedule.
    """
    # Format the URL for train search
    url = f"https://etrain.info/trains/{source_station}-to-{dest_station}?date={date}"
    
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the train list table
        train_table = soup.find('table', {'class': 'table'})
        if not train_table:
            return []
            
        trains = []
        for row in train_table.find_all('tr')[1:]:  # Skip header row
            cols = row.find_all('td')
            if len(cols) >= 4:
                train_number = cols[0].text.strip()
                train_name = cols[1].text.strip()
                departure = cols[2].text.strip()
                arrival = cols[3].text.strip()
                
                # Extract train number from the text
                train_number_match = re.search(r'\d+', train_number)
                if train_number_match:
                    train_number = train_number_match.group()
                
                # Check for pantry availability
                has_pantry = False
                pantry_cell = row.find('td', {'class': 'pantry'})
                if pantry_cell:
                    # Look for pantry icon or text
                    pantry_icon = pantry_cell.find('i', {'class': 'icon-food'})
                    pantry_text = pantry_cell.text.strip().lower()
                    has_pantry = bool(pantry_icon) or 'pantry' in pantry_text or 'food' in pantry_text
                
                # Get available classes
                available_classes = []
                class_cells = row.find_all('td', {'class': lambda x: x and 'class' in x.lower()})
                for cell in class_cells:
                    if 'available' in cell.get('class', []):
                        class_name = cell.get('title', '').strip()
                        if class_name:
                            available_classes.append(class_name)
                
                train_info = {
                    'train_number': train_number,
                    'train_name': train_name,
                    'departure_time': departure,
                    'arrival_time': arrival,
                    'has_pantry': has_pantry,
                    'available_classes': available_classes
                }
                
                # Get additional train details
                try:
                    schedule_url = f"https://etrain.info/train/{train_name.replace(' ', '-')}-{train_number}/schedule"
                    schedule_response = requests.get(schedule_url, headers=HEADERS)
                    if schedule_response.status_code == 200:
                        schedule_soup = BeautifulSoup(schedule_response.text, 'html.parser')
                        
                        # Check for pantry in schedule page
                        pantry_info = schedule_soup.find('div', {'class': 'pantry-info'})
                        if pantry_info:
                            has_pantry = True
                        
                        # Get running days
                        running_days = schedule_soup.find('div', {'class': 'running-days'})
                        if running_days:
                            train_info['running_days'] = running_days.text.strip()
                        
                        # Get train type
                        train_type = schedule_soup.find('div', {'class': 'train-type'})
                        if train_type:
                            train_info['train_type'] = train_type.text.strip()
                except Exception as e:
                    print(f"Error getting additional details for train {train_number}: {e}")
                
                trains.append(train_info)
        
        return trains
        
    except Exception as e:
        print(f"Error searching trains: {str(e)}")
        return []

def get_train_schedule(train_name: str, train_number: str):
    """
    Get the complete schedule for a specific train.
    Returns a list of stations with arrival and departure times.
    """
    url = f"https://etrain.info/train/{train_name.replace(' ', '-')}-{train_number}/schedule"
    
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the schedule table
        schedule_table = soup.find('table', {'class': 'table'})
        if not schedule_table:
            return []
            
        schedule = []
        for row in schedule_table.find_all('tr')[1:]:  # Skip header row
            cols = row.find_all('td')
            if len(cols) >= 4:
                station = cols[1].text.strip()
                arrival = cols[2].text.strip()
                departure = cols[3].text.strip()
                
                # Check if station has pantry
                has_pantry = False
                pantry_cell = row.find('td', {'class': 'pantry'})
                if pantry_cell:
                    pantry_icon = pantry_cell.find('i', {'class': 'icon-food'})
                    pantry_text = pantry_cell.text.strip().lower()
                    has_pantry = bool(pantry_icon) or 'pantry' in pantry_text or 'food' in pantry_text
                
                schedule.append({
                    'station': station,
                    'arrival_time': arrival,
                    'departure_time': departure,
                    'has_pantry': has_pantry
                })
        
        return schedule
        
    except Exception as e:
        print(f"Error getting train schedule: {str(e)}")
        return [] 