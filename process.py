import csv
import os
import shutil
import toml
import datetime
import pytz
import json

import booklet

config = toml.load("config.toml")
eastern_tz = pytz.timezone("US/Eastern")

def process_dt_from_csv(time_string: str) -> str:
    event_dt = eastern_tz.localize(datetime.datetime.strptime(time_string, "%m/%d/%Y %H:%M"))
    return event_dt.isoformat()

def process_csv(filename: str) -> list[dict]:
    events = []
    with open(filename) as f:
        reader = csv.DictReader(f)
        for event in reader:
            if event["Published"] != "TRUE":
                continue
            events.append({
                "name": event["Event Name"].strip(),
                "dorm": event["Dorm"].strip(),
                "location": event["Event Location"].strip(),
                "start": process_dt_from_csv(event["Start Date and Time"]),
                "end": process_dt_from_csv(event["End Date and Time"]),
                "description": event["Event Description"],
                "tags": [tag.strip().lower() for tag in event["Tags"].split(",") if tag.strip()]
            })
    return events
            



if __name__ == "__main__":
    api_response = {
        "name": config["name"],
        "published": datetime.datetime.now().astimezone(pytz.utc).isoformat(),
        "events": []
    }
    orientation_events = []
    for filename in os.listdir("events"):
        print(f"Processing {filename}...")
        if filename == "orientation.csv":
            orientation_events = process_csv("events/" + filename)
        else:
            api_response["events"].extend(process_csv("events/" + filename))
    
    api_response["events"].sort(key=lambda e: e["start"])

    # Add extra data from events and config file
    api_response["dorms"] = sorted(list(set(e["dorm"] for e in api_response["events"])))
    api_response["tags"] = sorted(list(set(t for e in api_response["events"] for t in e["tags"])))
    api_response["colors"] = config["colors"]
    api_response["start"] = config["dates"]["start"]
    api_response["end"] = config["dates"]["end"]

    booklet_only_events = orientation_events

    print("Processing complete!")

    booklet_html = booklet.generate_booklet(api_response, config, booklet_only_events)

    print("Outputting booklet and JSON...")
    
    if os.path.exists("output"): shutil.rmtree("output")
    os.mkdir("output")
    shutil.copytree("static", "output/static")
    with open("output/api.json", "w") as w:
        json.dump(api_response, w)
    with open("output/booklet.html", "w") as b:
        b.write(booklet_html)
    
    print("Complete!")
