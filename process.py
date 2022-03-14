import csv
import os
import shutil
import toml
import datetime
import pytz
import json

config = toml.load("config.toml")

def process_time(time_string: str) -> str:
    eastern_tz = pytz.timezone("US/Eastern")
    event_dt = datetime.datetime.strptime(time_string, "%m/%d/%Y %H:%M").astimezone(eastern_tz)
    return event_dt.isoformat()

def process_csv(filename: str) -> list[dict]:
    events = []
    with open(filename) as f:
        reader = csv.DictReader(f)
        for event in reader:
            if event["Published"] != "TRUE":
                continue
            events.append({
                "name": event["Event Name"],
                "dorm": event["Dorm"],
                "location": event["Event Location"],
                "start": process_time(event["Start Date and Time"]),
                "end": process_time(event["End Date and Time"]),
                "description": event["Event Description"]
            })
    return events
            



if __name__ == "__main__":
    api_response = {
        "name": config["name"],
        "published": datetime.datetime.now().isoformat(),
        "events": []
    }
    for filename in os.listdir("events"):
        print(f"Processing {filename}...")
        api_response["events"].extend(process_csv("events/" + filename))
    
    api_response["dorms"] = list(set(e["dorm"] for e in api_response["events"]))

    print("Processing complete! Creating API JSON...")
    
    if os.path.exists("output"): shutil.rmtree("output")
    os.mkdir("output")
    with open("output/api.json", "w") as w:
        json.dump(api_response, w)
    
    print("Complete!")