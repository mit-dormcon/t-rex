import csv
import datetime
import json
import os
import shutil

import pytz
import toml

import booklet

config = toml.load("config.toml")
eastern_tz = pytz.timezone("US/Eastern")


def process_dt_from_csv(time_string: str) -> str:
    """
    Uses the config setting `date_format` to convert a time string into ISO format
    """
    event_dt = eastern_tz.localize(
        datetime.datetime.strptime(time_string, config["csv"]["date_format"])
    )
    return event_dt.isoformat()


def process_csv(filename: str) -> list[dict]:
    events = []
    with open(filename, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for event in reader:
            if event["Published"] != "TRUE":
                continue
            events.append(
                {
                    "name": event["Event Name"].strip(),
                    "dorm": event["Dorm"].strip(),
                    "location": event["Event Location"].strip(),
                    "start": process_dt_from_csv(event["Start Date and Time"]),
                    "end": process_dt_from_csv(event["End Date and Time"]),
                    "description": event["Event Description"],
                    "tags": [
                        tag.strip().lower()
                        for tag in event["Tags"].split(",")
                        if tag.strip()
                    ],
                    "group": event["Group"].strip() or None,
                }
            )
    return events


if __name__ == "__main__":
    api_response = {
        "name": config["name"],
        "published": datetime.datetime.now().astimezone(pytz.utc).isoformat(),
        "events": [],
    }
    orientation_events = []
    for filename in os.listdir("events"):
        if not filename.endswith(".csv"):
            continue
        print(f"Processing {filename}...")
        if filename == "orientation.csv":
            orientation_events = process_csv("events/" + filename)
        else:
            api_response["events"].extend(process_csv("events/" + filename))

    # Order events by start time, then by end time.
    api_response["events"].sort(key=lambda e: e["end"])
    api_response["events"].sort(key=lambda e: e["start"])

    # Add extra data from events and config file
    api_response["dorms"] = sorted(
        list(set(e["dorm"] for e in api_response["events"])), key=str.lower
    )
    api_response["tags"] = sorted(
        list(set(t for e in api_response["events"] for t in e["tags"]))
    )
    api_response["colors"] = config["colors"]
    api_response["start"] = config["dates"]["start"]
    api_response["end"] = config["dates"]["end"]

    booklet_only_events = orientation_events

    print("Processing complete!")

    print("Generating the booklet...")
    booklet_html = booklet.generate_booklet(api_response, config, booklet_only_events)

    print("Processing index.md...")
    index_html = booklet.generate_index()

    print("Outputting booklet and JSON...")

    if os.path.exists("output"):
        shutil.rmtree("output")
    os.mkdir("output")
    shutil.copytree("static", "output/static")
    with open("output/api.json", "w", encoding="utf-8") as w:
        json.dump(api_response, w)
    with open("output/booklet.html", "w", encoding="utf-8") as b:
        b.write(booklet_html)
    with open("output/index.html", "w", encoding="utf-8") as i:
        i.write(index_html)

    print("Complete!")
