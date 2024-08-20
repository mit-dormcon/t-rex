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


def get_main_dorm(dorm: str) -> str:
    if dorm in config["dorms"]["subdorms"]:
        return config["dorms"]["subdorms"][dorm]
    return dorm


def process_dt_from_csv(time_string: str) -> str:
    """
    Uses the config setting `date_format` to convert a time string into ISO format
    """
    event_dt = datetime.strptime(time_string, config["csv"]["date_format"]).replace(
        tzinfo=eastern_tz
    )
    return event_dt.isoformat()


def get_dorm_group(dorms: list[str]) -> str:
    return ", ".join(dorms)


def event_with_same_name_exists(event: Event, events: list[Event]) -> bool:
    for e in events:
        if (
            e["name"] == event["name"]
            and e["start"] != event["start"]
            and e["end"] != event["end"]
        ):
            return True
    return False


def check_if_events_conflict(
    event_one_start: datetime,
    event_one_end: datetime,
    event_two_start: datetime,
    event_two_end: datetime,
) -> bool:
    return (
        (event_two_start <= event_one_start < event_two_end)
        or (event_two_start < event_one_end <= event_two_end)
        or (event_one_start <= event_two_start < event_one_end)
        or (event_one_start < event_two_end <= event_one_end)
    )


def get_invalid_events(orientation_events: list[Event], api_response: APIResponse):
    """
    Get list of error messages for invalid events.
    Formatted as a dict, with dorms as the key and a tuple of the contact emails and list of events as the value.
    """

    errors: dict[str, tuple[list[str], list[str]]] = dict()

    # Check for conflicts with mandatory events and invalid events
    all_events = orientation_events + api_response["events"]
    mandatory_events = list(
        event_to_check
        for event_to_check in all_events
        if config["orientation"]["mandatory_tag"].strip().lower()
        in event_to_check["tags"]
    )

    def create_error_dorm_entry(dorms: list[str], error_string: str) -> None:
        dorms_list = [get_main_dorm(dorm) for dorm in dorms]
        error_key = get_dorm_group(dorms_list)

        if errors.get(error_key) is None:
            errors[error_key] = (
                [
                    config["dorms"]["rex_contact"][
                        dorm if dorm != config["rename_dormcon_to"] else "DormCon"
                    ]
                    + "@mit.edu"
                    for dorm in dorms_list
                ],
                [],
            )

        errors[error_key][1].append(error_string)

    for event in api_response["events"]:
        event_start = datetime.fromisoformat(event["start"])
        event_end = datetime.fromisoformat(event["end"])

        if event_end < event_start:
            event_date = (
                " on "
                + booklet.get_date_bucket(
                    event, config["dates"]["hour_cutoff"]
                ).strftime("%x")
                if event_with_same_name_exists(event, api_response["events"])
                else ""
            )
            create_error_dorm_entry(
                event["dorm"],
                f"{event['name']}{event_date} has an end time before its start time.",
            )
            continue

        for mandatory_event in mandatory_events:
            mandatory_event_start = datetime.fromisoformat(mandatory_event["start"])
            mandatory_event_end = datetime.fromisoformat(mandatory_event["end"])

            if check_if_events_conflict(
                event_start, event_end, mandatory_event_start, mandatory_event_end
            ):
                event_date = " on " + booklet.get_date_bucket(
                    event, config["dates"]["hour_cutoff"]
                ).strftime("%x")
                subdorms_if_needed = (
                    " ("
                    + ", ".join(
                        [dorm for dorm in event["dorm"] if dorm != get_main_dorm(dorm)]
                    )
                    + ") "
                    if [dorm for dorm in event["dorm"] if dorm != get_main_dorm(dorm)]
                    else " "
                )
                create_error_dorm_entry(
                    event["dorm"],
                    f"{event['name']}{subdorms_if_needed}conflicts with {mandatory_event['name']}{event_date}.",
                )
                continue

    if errors.get(config["rename_dormcon_to"]) is not None:
        errors["DormCon"] = errors.pop(config["rename_dormcon_to"])

    return errors


def process_csv(filename: str):
    events: list[Event] = []
    # NOTE: If you saved this with Excel as a CSV file with UTF-8 encoding, you might
    # need to open it with encoding="utf-8-sig" instead of "utf-8".
    with open(filename, encoding="utf-8") as f:
        reader = [row for row in csv.DictReader(f)]

        events_list: list[dict[str, str]] = []
        for index, row in enumerate(reader):
            events_list.append(dict())
            for key, val in row.items():
                events_list[index][key.strip()] = val.strip() if val else ""

        for event in events_list:
            if event["Published"] != "TRUE":
                continue
            events.append(
                {
                    "name": event["Event Name"],
                    "dorm": [
                        (
                            dorm.strip()
                            if dorm.strip().lower() != "dormcon"
                            else config["rename_dormcon_to"].strip()
                        )
                        for dorm in event["Dorm"].split(",")
                        if dorm
                    ],
                    "location": event["Event Location"],
                    "start": process_dt_from_csv(event["Start Date and Time"]),
                    "end": process_dt_from_csv(event["End Date and Time"]),
                    "description": event["Event Description"],
                    "tags": [
                        tag.strip().lower() for tag in event["Tags"].split(",") if tag
                    ],
                    "group": event["Group"] or None,
                }
            )
    return events


if __name__ == "__main__":
    api_response: APIResponse = {
        "name": config["name"],
        "published": datetime.now(timezone.utc).isoformat(),
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

    errors = get_invalid_events(orientation_events, api_response)

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
