import csv
import json
import os
import shutil
import tomllib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import booklet
from api_types import APIResponse, Config, Event

eastern_tz = ZoneInfo("America/New_York")

with open("config.toml", "rb") as c:
    config: Config = tomllib.load(c)  # type: ignore


def process_dt_from_csv(time_string: str) -> str:
    """
    Uses the config setting `date_format` to convert a time string into ISO format
    """
    event_dt = datetime.strptime(time_string, config["csv"]["date_format"]).replace(
        tzinfo=eastern_tz
    )
    return event_dt.isoformat()


def process_csv(filename: str):
    events: list[Event] = []
    with open(filename, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for event in reader:
            if event["Published"] != "TRUE":
                continue
            events.append(
                {
                    "name": event["Event Name"].strip(),
                    "dorm": [
                        dorm.strip()
                        for dorm in event["Dorm"].split(",")
                        if dorm.strip()
                    ],
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
    api_response: APIResponse = {
        "name": config["name"],
        "published": datetime.now().astimezone(timezone.utc).isoformat(),
        "events": [],
        "dorms": [],
        "tags": [],
        "colors": config["colors"],
        "start": config["dates"]["start"],
        "end": config["dates"]["end"],
    }
    orientation_events: list[Event] = []
    for filename in os.listdir("events"):
        if not filename.endswith(".csv"):
            continue
        print(f"Processing {filename}...")
        if filename == config["orientation"]["filename"]:
            orientation_events = process_csv("events/" + filename)
        else:
            api_response["events"].extend(process_csv("events/" + filename))

    # Order events by start time, then by end time.
    api_response["events"].sort(key=lambda e: e["end"])
    api_response["events"].sort(key=lambda e: e["start"])

    # Add extra data from events and config file
    api_response["dorms"] = sorted(
        list(set(dorm for e in api_response["events"] for dorm in e["dorm"])),
        key=str.lower,
    )
    api_response["tags"] = sorted(
        list(set(t for e in api_response["events"] for t in e["tags"]))
    )

    booklet_only_events = (
        orientation_events if config["orientation"]["include_in_booklet"] else []
    )

    # Check for conflicts with mandatory events and invalid events
    errors: list[str] = []
    mandatory_events = list(
        event_to_check
        for event_to_check in (orientation_events + api_response["events"])
        if config["orientation"]["mandatory_tag"].strip().lower()
        in event_to_check["tags"]
    )
    for event in api_response["events"]:
        event_start = datetime.fromisoformat(event["start"])
        event_end = datetime.fromisoformat(event["end"])

        if event_end < event_start:
            errors.append(
                f"{event['name']} @ {', '.join(event['dorm'])} has an end time before its start time!"
            )
            # raise Exception(event["name"] + " has an end time before its start time!")
            continue

        for mandatory_event in mandatory_events:
            mandatory_event_start = datetime.fromisoformat(mandatory_event["start"])
            mandatory_event_end = datetime.fromisoformat(mandatory_event["end"])

            if (
                (mandatory_event_start <= event_start < mandatory_event_end)
                or (mandatory_event_start < event_end <= mandatory_event_end)
                or (event_start <= mandatory_event_start < event_end)
                or (event_start < mandatory_event_end <= event_end)
            ):
                errors.append(
                    f"{event['name']} @ {', '.join(event['dorm'])} conflicts with {mandatory_event['name']}"
                )
                continue

    print("Processing complete!")

    print("Generating the booklet...")
    booklet_html = booklet.generate_booklet(api_response, config, booklet_only_events)

    print("Processing index.md...")
    index_html = booklet.generate_index()

    print("Processing errors...")
    errors_html = booklet.generate_errors(errors, api_response["name"])

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
    with open("output/errors.html", "w", encoding="utf-8") as e:
        e.write(errors_html)

    print("Complete!")
