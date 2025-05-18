import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import sys

def get_train_status(train_number, station_name, date):
    """Scrape train running status from confirmtkt.com."""
    url = f"https://www.confirmtkt.com/train-running-status/{train_number}?StationName={station_name}&Date={date}"
    
    print(f"Fetching URL: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"Response status code: {response.status_code}")
    except requests.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None

    print("Parsing HTML response...")
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Initialize the result dictionary
    result = {
        "train_info": {
            "number": train_number,
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "stations": []
    }
    
    # Find all station rows
    station_rows = soup.find_all('div', class_='rs__station-row')
    print(f"Found {len(station_rows)} station rows")
    
    for row in station_rows:
        try:
            # Get station name
            station_name_div = row.find('div', class_='rs__station-grid')
            station_name = station_name_div.find('span', class_='rs__station-name').text.strip() if station_name_div else ""
            
            # Get date info
            date_div = row.find_all('div', class_='col-xs-3')[1]
            day = date_div.find('span').text.strip() if date_div else ""
            date = date_div.find_all('span')[1].text.strip() if date_div and len(date_div.find_all('span')) > 1 else ""
            
            # Get arrival time
            arrival_div = row.find_all('div', class_='col-xs-2')[0]
            arrival = arrival_div.find('span').text.strip() if arrival_div else ""
            
            # Get departure time
            departure_div = row.find_all('div', class_='col-xs-2')[1]
            departure = departure_div.find('span').text.strip() if departure_div else ""
            
            # Get delay info
            delay_div = row.find('div', class_='rs__station-delay')
            delay = delay_div.text.strip() if delay_div else ""
            
            # Get status (check if station is completed)
            status = "Completed" if row.find('svg', class_='bi-check-circle') else "Pending"
            
            station_data = {
                "station_name": station_name,
                "day": day,
                "date": date,
                "arrival": arrival,
                "departure": departure,
                "delay": delay,
                "status": status
            }
            
            result["stations"].append(station_data)
            print(f"Processed station: {station_name}")
            
        except Exception as e:
            print(f"Error processing station row: {e}")
            continue
    
    return result

def save_to_json(data, filename):
    """Save the scraped data to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data saved to {filename}")
    except Exception as e:
        print(f"Error saving to JSON: {e}")

def main():
    try:
        # Example train details
        train_number = "12304"  # Poorva Express
        station_name = "New-Delhi-NDLS"
        date = "18-May-2025"
        
        print(f"Fetching running status for train {train_number} from {station_name} on {date}...")
        
        # Get train status
        status_data = get_train_status(train_number, station_name, date)
        
        if status_data:
            # Save to JSON file
            output_file = f"{train_number}_running_status.json"
            save_to_json(status_data, output_file)
            
            # Print summary
            print("\nTrain Information:")
            print(json.dumps(status_data["train_info"], indent=2))
            
            print("\nFirst few stations:")
            for station in status_data["stations"][:3]:
                print(json.dumps(station, indent=2))
        else:
            print("Failed to get train status")
            
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 