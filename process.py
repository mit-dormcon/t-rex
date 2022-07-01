import csv
import os
import shutil
import toml
import datetime
import pytz
import json

import booklet

config = toml.load("config.toml")

def process_time(time_string: str) -> str:
    eastern_tz = pytz.timezone("US/Eastern")
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
                "name": event["Event Name"],
                "dorm": event["Dorm"],
                "location": event["Event Location"],
                "start": process_time(event["Start Date and Time"]),
                "end": process_time(event["End Date and Time"]),
                "description": event["Event Description"],
                "tags": [tag for tag in event["Tags"].lower().split(",") if tag]
            })
    return events
            



if __name__ == "__main__":
    api_response = {
        "name": config["name"],
        "published": datetime.datetime.now().astimezone(pytz.utc).isoformat(),
        "events": []
    }
    for filename in os.listdir("events"):
        print(f"Processing {filename}...")
        api_response["events"].extend(process_csv("events/" + filename))
    
    api_response["events"].sort(key=lambda e: e["start"])
    api_response["dorms"] = sorted(list(set(e["dorm"] for e in api_response["events"])))
    api_response["tags"] = sorted(list(set(t for e in api_response["events"] for t in e["tags"])))
    api_response["colors"] = config["colors"]

    print("Processing complete!")

    booklet_html = booklet.generate_booklet(api_response)

    print("Outputting booklet and JSON...")
    
    if os.path.exists("output"): shutil.rmtree("output")
    os.mkdir("output")
    shutil.copytree("static", "output/static")
    with open("output/api.json", "w") as w:
        json.dump(api_response, w)
    with open("output/booklet.html", "w") as b:
        b.write(booklet_html)
    
    print("Complete!")