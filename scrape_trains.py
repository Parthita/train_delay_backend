import requests
from bs4 import BeautifulSoup
import json
import re

# --- HARDCODED INPUTS ---
src_name = "Howrah Jn"
src_code = "HWH"
dst_name = "Chittaranjan"
dst_code = "CRJ"
date = "20250521"  # Format: YYYYMMDD or None

def slugify(name, code):
    # Converts "Howrah Jn", "HWH" -> "Howrah-Jn-HWH"
    return f"{name.strip().replace(' ', '-')}-{code.strip().upper()}"

def build_url(src_name, src_code, dst_name, dst_code, date=None):
    # Updated URL format: https://etrain.info/trains/Howrah-Jn-HWH-to-Chittaranjan-CRJ?date=20250521
    src_slug = slugify(src_name, src_code)
    dst_slug = slugify(dst_name, dst_code)
    url = f"https://etrain.info/trains/{src_slug}-to-{dst_slug}"
    if date:
        url += f"?date={date}"
    return url

def get_available_classes(row):
    classes = []
    # Check each class column (indices 7-13 in the row)
    class_columns = row.find_all('td', class_=lambda x: x and 'wd22' in x)
    for col in class_columns:
        if 'bgrn' in col.get('class', []):  # Green background indicates available class
            classes.append(col.get('title', ''))
    return classes

def get_booking_classes(row):
    classes = []
    booking_div = row.find('div', class_='flexRow')
    if booking_div:
        for link in booking_div.find_all('a', class_='cavlink'):
            classes.append(link.text.strip())
    return classes

def get_train_info(row):
    try:
        # Parse the data-train attribute which contains train info in JSON format
        train_data = json.loads(row['data-train'])
        
        # Get additional attributes
        booking_available = row.get('book', '0') == '1'
        advance_reservation_period = row.get('ar', '0')
        start_date = row.get('sd', '')
        end_date = row.get('ed', '')
        
        # Get available classes and booking classes
        available_classes = get_available_classes(row)
        booking_classes = get_booking_classes(row)
        
        # Get notices/remarks if any
        notices = []
        notice_icons = row.find_all('i', class_='icon-info-circled')
        for icon in notice_icons:
            if 'etitle' in icon.attrs:
                notice = icon['etitle']
                # Clean up the notice text
                notice = re.sub(r'<[^>]+>', '', notice)
                notice = notice.replace('&quot;', '"')
                notices.append(notice)
        
        # Get pantry availability
        has_pantry = bool(row.find('i', class_='icon-food'))
        
        # Get limited run info
        limited_run = bool(row.find('i', class_='icon-date'))
        
        return {
            'train_number': train_data.get('num', ''),
            'train_name': train_data.get('name', ''),
            'train_type': train_data.get('typ', ''),
            'source': train_data.get('s', ''),
            'departure_time': train_data.get('st', ''),
            'destination': train_data.get('d', ''),
            'arrival_time': train_data.get('dt', ''),
            'duration': train_data.get('tt', ''),
            'running_days': train_data.get('dy', ''),
            'booking_available': booking_available,
            'advance_reservation_period': advance_reservation_period,
            'start_date': start_date,
            'end_date': end_date,
            'available_classes': available_classes,
            'booking_classes': booking_classes,
            'notices': notices,
            'has_pantry': has_pantry,
            'is_limited_run': limited_run
        }
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error processing row: {e}")
        return None

def scrape_trains_between(src_name, src_code, dst_name, dst_code, date=None, output_json=None):
    url = build_url(src_name, src_code, dst_name, dst_code, date)
    print(f"Fetching: {url}")
    
    # Add headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch page: {response.status_code}")
        return None

    # Parse HTML using BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Find all train rows
    train_rows = soup.find_all('tr', attrs={'data-train': True})
    if not train_rows:
        print("No train data found in the page.")
        return None
    
    # Process the train data
    trains = []
    for row in train_rows:
        train_info = get_train_info(row)
        if train_info:
            trains.append(train_info)
    
    # Print first 3 trains for debug
    print("\nFirst 3 trains found:")
    for train in trains[:3]:
        print(json.dumps(train, indent=2))
    
    if output_json:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(trains, f, indent=2, ensure_ascii=False)
        print(f"\nSaved data to {output_json}")
    
    return trains  # Make sure to return the trains list

if __name__ == "__main__":
    # You can change the output filename if you want to save as JSON
    output_json = "trains_between.json"
    scrape_trains_between(src_name, src_code, dst_name, dst_code, date, output_json)