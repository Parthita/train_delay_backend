import requests
import re
import json
from bs4 import BeautifulSoup

def download_html(train_name: str, train_number: str):
    url = f"https://etrain.info/train/{train_name.replace(' ', '-')}-{train_number}/history?d=1y"
    
    print(f"Downloading HTML for {train_name} ({train_number})...")
    
    response = requests.get(url)
    
    if response.status_code == 200:
        # Save the HTML content to a file
        html_file = f"{train_number}_history.html"
        with open(html_file, "w", encoding="utf-8") as file:
            file.write(response.text)
        print(f"HTML file saved as {html_file}")
        return html_file
    else:
        print(f"Failed to download the HTML. Status code: {response.status_code}")
        return None

def extract_delay_data_from_html(html_file: str):
    # Load the saved HTML file
    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()

    # Parse HTML using BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # Extract the <script> tag containing the `et.rsStat.tooltipData` JavaScript
    script_tag = soup.find("script", string=lambda text: text and 'et.rsStat.tooltipData' in text)
    if not script_tag:
        raise Exception("Could not find the JavaScript data in the script tag.")
    
    script_content = script_tag.string
    
    # Extract the tooltipData array (JS object assignment)
    match = re.search(r"et\.rsStat\.tooltipData\s*=\s*(\[[\s\S]+?\]);", script_content)
    if not match:
        raise Exception("Could not extract the tooltipData array.")
    
    js_array = match.group(1)

    # --- CLEANING STEP: Make JS data valid JSON ---
    # 1. Replace new Date(YYYY,MM,DD) with a proper ISO date string
    js_array = re.sub(r'new Date\((\d+),(\d+),(\d+)\)', lambda m: f'"{int(m[1])}-{int(m[2])+1:02d}-{int(m[3]):02d}"', js_array)

    # 2. Replace 'null' with '0' (as delays)
    js_array = js_array.replace("null", "0")

    # 3. Remove trailing commas in lists
    js_array = re.sub(r",\s*]", "]", js_array)
    js_array = re.sub(r",\s*}", "}", js_array)

    # 4. Convert single quotes to double quotes (standard JSON format)
    js_array = js_array.replace("'", '"')

    # Debug: Print cleaned JS array before parsing
    print("Cleaned JS Array:")
    print(js_array)

    # Try parsing the cleaned JSON
    try:
        data = json.loads(js_array)
    except json.JSONDecodeError as e:
        print("Failed to parse cleaned JSON from tooltipData.")
        print(f"Error: {e}")
        print("Here's the cleaned JS array that caused the issue:")
        print(js_array)
        return

    # --- PROCESS DATA ---
    # First row is column headers (station names)
    station_names = [entry["label"] for entry in data[0][1:]]

    # Remaining rows contain daily data
    records = []
    for row in data[1:]:
        date = row[0]
        for i, delay in enumerate(row[1:]):
            records.append({
                "date": date,
                "station": station_names[i],
                "delay_minutes": delay
            })

    # Output a few rows for debugging
    for r in records[:10]:
        print(f"{r['date']} - {r['station']} - {r['delay_minutes']} min")

    # Save to CSV
    import csv

    filename = f"{train_number}.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "station", "delay_minutes"])
        writer.writeheader()
        writer.writerows(records)
        print(f"\n✅ Delay data saved to {filename}")

    

# Example usage
if __name__ == "__main__":
    train_name = input("Enter train name (e.g., Poorva Express): ").strip()
    train_number = input("Enter train number (e.g., 12303): ").strip()

    # Download the HTML for the train
    html_file = download_html(train_name, train_number)

    # If HTML file is downloaded successfully, extract delay data
    if html_file:
        extract_delay_data_from_html(html_file)