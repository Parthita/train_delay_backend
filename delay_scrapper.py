import requests
import re
import json
from bs4 import BeautifulSoup

def download_html(train_name: str, train_number: str):
    url = f"https://etrain.info/train/{train_name.replace(' ', '-')}-{train_number}/history?d=1y"
    
    print(f"Downloading HTML for {train_name} ({train_number})...")
    print(f"URL: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        if response.status_code == 200:
            # Save the HTML content to a file
            html_file = f"{train_number}_history.html"
            with open(html_file, "w", encoding="utf-8") as file:
                file.write(response.text)
            print(f"HTML file saved as {html_file}")
            print(f"Response size: {len(response.text)} bytes")
            return html_file
        else:
            print(f"Failed to download the HTML. Status code: {response.status_code}")
            print(f"Response content: {response.text[:500]}")  # Print first 500 chars of response
            return None
    except requests.exceptions.Timeout:
        print("Request timed out after 30 seconds")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

def extract_delay_data_from_html(html_file: str, train_number: str):
    # Load the saved HTML file
    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()

    # Parse HTML using BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # Find the script tag containing the delay data
    script_tags = soup.find_all("script")
    delay_data = None
    
    print(f"Searching for delay data in {len(script_tags)} script tags...")
    
    for script in script_tags:
        if script.string and "et.rsStat.tooltipData" in script.string:
            print("Found script tag with delay data")
            # Extract the JavaScript array
            match = re.search(r"et\.rsStat\.tooltipData\s*=\s*(\[[\s\S]+?\]);", script.string)
            if match:
                js_array = match.group(1)
                print("Successfully extracted JavaScript array")
                
                # Clean up the JavaScript array to make it valid JSON
                # Replace new Date() with ISO date string
                js_array = re.sub(r'new Date\((\d+),(\d+),(\d+)\)', 
                                lambda m: f'"{int(m[1])}-{int(m[2])+1:02d}-{int(m[3]):02d}"', 
                                js_array)
                
                # Replace null with 0
                js_array = js_array.replace("null", "0")
                
                # Remove trailing commas
                js_array = re.sub(r",\s*]", "]", js_array)
                js_array = re.sub(r",\s*}", "}", js_array)
                
                # Convert single quotes to double quotes
                js_array = js_array.replace("'", '"')
                
                try:
                    delay_data = json.loads(js_array)
                    print(f"Successfully parsed delay data with {len(delay_data)} rows")
                    break
                except json.JSONDecodeError as e:
                    print(f"Error parsing delay data: {e}")
                    print("Problematic JSON snippet:", js_array[:200])  # Print first 200 chars for debugging
                    continue

    if not delay_data:
        print("No delay data found in HTML")
        return False

    # Process the delay data
    # First row contains column headers (station names)
    station_names = [entry["label"] for entry in delay_data[0][1:]]
    print(f"Found {len(station_names)} stations in delay data")
    
    # Remaining rows contain daily data
    records = []
    for row in delay_data[1:]:
        date = row[0]
        for i, delay in enumerate(row[1:]):
            records.append({
                "date": date,
                "station": station_names[i],
                "delay_minutes": delay
            })

    print(f"Processed {len(records)} delay records")

    # Save to CSV
    import csv
    filename = f"{train_number}.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "station", "delay_minutes"])
        writer.writeheader()
        writer.writerows(records)
        print(f"\n✅ Delay data saved to {filename}")
    
    return True

if __name__ == "__main__":
    train_name = input("Enter train name (e.g., Poorva Express): ").strip()
    train_number = input("Enter train number (e.g., 12303): ").strip()

    # Download the HTML for the train
    html_file = download_html(train_name, train_number)

    # If HTML file is downloaded successfully, extract delay data
    if html_file:
        extract_delay_data_from_html(html_file, train_number)