import requests
from bs4 import BeautifulSoup
import json
import re

def get_station_info(station_cell):
    """Extract station information from a table cell."""
    station_name = station_cell.find('div', class_='fixwelps').text.strip()
    
    # Get distance and platform info
    info_div = station_cell.find('div', class_='nowrap')
    distance = info_div.find('div', class_='fixw70').text.strip()
    platform = info_div.find('small').text.strip().replace('Platform: ', '')
    
    # Check if station has WiFi
    has_wifi = bool(station_cell.find('i', class_='icon-wifi'))
    
    return {
        'name': station_name,
        'distance': distance,
        'platform': platform,
        'has_wifi': has_wifi
    }

def get_timing_info(timing_cell):
    """Extract arrival and departure timing information."""
    timing_divs = timing_cell.find_all('div', class_='nowrap')
    arrival = timing_divs[0].text.strip()
    departure = timing_divs[1].text.strip()
    
    # Extract day information if present
    arrival_day = re.search(r'\(Day (\d+)\)', arrival)
    departure_day = re.search(r'\(Day (\d+)\)', departure)
    
    # Clean up the timing strings
    arrival = re.sub(r'\(Day \d+\)', '', arrival).strip()
    departure = re.sub(r'\(Day \d+\)', '', departure).strip()
    
    return {
        'arrival': arrival,
        'arrival_day': int(arrival_day.group(1)) if arrival_day else 1,
        'departure': departure,
        'departure_day': int(departure_day.group(1)) if departure_day else 1
    }

def get_train_info(soup):
    """Extract train information from the page header."""
    train_info = {}
    
    # Get train name and number
    train_header = soup.find('div', class_='bx3_bgm')
    if train_header:
        train_text = train_header.text.strip()
        train_info['name'] = train_text.split('(')[0].strip()
        train_info['number'] = train_text.split('(')[1].split(')')[0].strip()
    
    # Get running days
    running_days = soup.find('b', string='Running Days:')
    if running_days:
        train_info['running_days'] = running_days.next_sibling.strip()
    
    # Get train type and zone
    type_info = soup.find('b', string='Type:')
    if type_info:
        train_info['type'] = type_info.next_sibling.strip()
    
    zone_info = soup.find('b', string='Zone:')
    if zone_info:
        train_info['zone'] = zone_info.next_sibling.strip()
    
    # Get available classes
    classes_info = soup.find('b', string='Available Classes:')
    if classes_info:
        train_info['available_classes'] = classes_info.next_sibling.strip()
    
    # Check if pantry is available
    train_info['has_pantry'] = bool(soup.find('b', string='Pantry Available'))
    
    return train_info

def scrape_train_schedule(url):
    """Scrape train schedule from the given URL."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Get train information
    train_info = get_train_info(soup)
    
    # Find the schedule table
    schedule_table = soup.find('table', class_='fullw nocps nolrborder bx3_brl')
    if not schedule_table:
        print("Schedule table not found")
        return None
    
    # Get all station rows (excluding header)
    station_rows = schedule_table.find_all('tr')[1:]  # Skip header row
    
    schedule = []
    for row in station_rows:
        # Get station number and code
        num_cell = row.find('td', class_='txt-center')
        station_num = num_cell.find('div', class_='pdl5').text.strip()
        station_code = num_cell.find('small').find('div', class_='pdl5').text.strip()
        
        # Get station details
        station_cell = row.find('td', class_='intstnCont')
        station_info = get_station_info(station_cell)
        
        # Get timing information
        timing_cell = row.find_all('td')[-1]  # Last cell contains timing info
        timing_info = get_timing_info(timing_cell)
        
        # Combine all information
        station_data = {
            'station_number': int(station_num),
            'station_code': station_code,
            **station_info,
            **timing_info
        }
        
        schedule.append(station_data)
    
    return {
        'train_info': train_info,
        'schedule': schedule
    }

def save_schedule_to_json(data, output_file):
    """Save schedule data to a JSON file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Schedule saved to {output_file}")

def main():
    url = "https://etrain.info/train/Poorva-Express-12303/schedule"
    print(f"Fetching schedule from: {url}")
    
    data = scrape_train_schedule(url)
    if data:
        save_schedule_to_json(data, 'train_schedule.json')
        
        # Print train info and first few stations for verification
        print("\nTrain Information:")
        print(json.dumps(data['train_info'], indent=2))
        
        print("\nFirst 3 stations in schedule:")
        for station in data['schedule'][:3]:
            print(json.dumps(station, indent=2))

if __name__ == "__main__":
    main() 