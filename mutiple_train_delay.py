import requests
import re
import json
from bs4 import BeautifulSoup
import csv
import time

# Predefined trains: (train_name, train_number)
TRAINS = [
    ("Poorva Express", "12303"),
    ("Howrah Rajdhani", "12306"),
    ("Sealdah Duronto", "12213"),
    ("Shatabdi Express", "12002"),
    ("Humsafar Express", "12371"),
    ("Garib Rath", "12907"),
    ("Sampark Kranti", "12910"),
    ("Rajdhani Express", "12435"),
    ("Duronto Express", "12260"),
    ("Tejas Express", "22119"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/114.0.0.0 Safari/537.36"
}

def download_html(train_name: str, train_number: str):
    url = f"https://etrain.info/train/{train_name.replace(' ', '-')}-{train_number}/history?d=1y"
    print(f"Downloading HTML for {train_name} ({train_number})...")
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.text
    else:
        print(f"Failed to download {train_name} ({train_number}), status: {response.status_code}")
        return None

def extract_delay_data(html_content: str, train_number: str):
    soup = BeautifulSoup(html_content, "html.parser")
    script_tag = soup.find("script", string=lambda s: s and 'et.rsStat.tooltipData' in s)
    if not script_tag:
        print(f"⚠️ Could not find delay data for train {train_number}")
        return []

    script_content = script_tag.string
    match = re.search(r"et\.rsStat\.tooltipData\s*=\s*(\[[\s\S]+?\]);", script_content)
    if not match:
        print(f"⚠️ Could not extract delay array for train {train_number}")
        return []

    js_array = match.group(1)

    # Clean JS to JSON
    js_array = re.sub(
        r'new Date\((\d+),(\d+),(\d+)\)',
        lambda m: f'"{int(m[1])}-{int(m[2])+1:02d}-{int(m[3]):02d}"',
        js_array
    )
    js_array = js_array.replace("null", "0")
    js_array = re.sub(r",\s*]", "]", js_array)
    js_array = re.sub(r",\s*}", "}", js_array)
    js_array = js_array.replace("'", '"')

    try:
        data = json.loads(js_array)
    except json.JSONDecodeError as e:
        print(f"JSON decode error for train {train_number}: {e}")
        return []

    # First row has station info (skip first element which is date column)
    station_names = [entry["label"] for entry in data[0][1:]]

    records = []
    for row in data[1:]:
        date = row[0]
        for i, delay in enumerate(row[1:]):
            records.append({
                "date": date,
                "station": station_names[i],
                "delay_minutes": delay,
                "train_number": train_number
            })
    return records

def main():
    all_records = []
    for train_name, train_number in TRAINS:
        html = download_html(train_name, train_number)
        if html:
            records = extract_delay_data(html, train_number)
            if records:
                all_records.extend(records)
        # To be polite to server
        time.sleep(3)

    # Save all data into one CSV
    csv_filename = "combined_train_delay_data.csv"
    with open(csv_filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "station", "delay_minutes", "train_number"])
        writer.writeheader()
        writer.writerows(all_records)
    print(f"\n✅ Combined delay data saved to {csv_filename}")

if __name__ == "__main__":
    main()
