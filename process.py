import csv
import shutil
import tomllib
from datetime import datetime, timezone
from operator import attrgetter
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

import booklet
from api_types import APIResponse, Config, Event, get_api_schema

eastern_tz = ZoneInfo("America/New_York")

with open("config.toml", "rb") as c:
    config = Config.model_validate(tomllib.load(c))


def get_main_dorm(dorm: str) -> str:
    if dorm in config.dorms:
        return config.dorms[dorm].rename_to or dorm

    return dorm


def process_dt_from_csv(time_string: str) -> datetime:
    """
    Uses the config setting `date_format` to convert a time string into ISO format
    """
    return datetime.strptime(time_string, config.csv.date_format).replace(
        tzinfo=eastern_tz
    )


def get_dorm_group(dorms: list[str]) -> str:
    return ", ".join(dorms)


def event_with_same_name_exists(event: Event, events: list[Event]) -> bool:
    for e in events:
        if e.name == event.name and e.start != event.start and e.end != event.end:
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
    all_events = orientation_events + api_response.events
    mandatory_events = list(
        event_to_check
        for event_to_check in all_events
        if config.orientation.mandatory_tag.strip().lower() in event_to_check.tags
    )

    def create_error_dorm_entry(dorms: list[str], error_string: str) -> None:
        dorms_list = [get_main_dorm(dorm) for dorm in dorms]
        error_key = get_dorm_group(dorms_list)

        if errors.get(error_key) is None:
            contact_emails = []

            for dorm in dorms_list:
                if dorm in config.dorms:
                    contact_emails.append(config.dorms[dorm].contact)
                else:
                    # If the dorm is not in the config, find if it was renamed
                    for dorm_name, dorm_config in config.dorms.items():
                        if dorm == dorm_config.rename_to or dorm_name == dorm:
                            contact_emails.append(dorm_config.contact)
                            break

            errors[error_key] = (
                contact_emails,
                [],
            )

        errors[error_key][1].append(error_string)

    for event in api_response.events:
        event_start = event.start
        event_end = event.end

        if event_end < event_start:
            event_date = (
                " on "
                + booklet.get_date_bucket(event, config.dates.hour_cutoff).strftime(
                    "%x"
                )
                if event_with_same_name_exists(event, api_response.events)
                else ""
            )
            create_error_dorm_entry(
                event.dorm,
                f"{event.name}{event_date} has an end time before its start time.",
            )
            continue

        for mandatory_event in mandatory_events:
            mandatory_event_start = mandatory_event.start
            mandatory_event_end = mandatory_event.end

            if check_if_events_conflict(
                event_start, event_end, mandatory_event_start, mandatory_event_end
            ):
                event_date = " on " + booklet.get_date_bucket(
                    event, config.dates.hour_cutoff
                ).strftime("%x")
                create_error_dorm_entry(
                    event.dorm,
                    f"{event.name} conflicts with {mandatory_event.name}{event_date}.",
                )
                continue

    for dorm in config.dorms:
        dorm_config = config.dorms[dorm]
        if dorm_config.rename_to:
            # If the dorm has a rename_to, check if it exists in the errors dict
            if errors.get(dorm_config.rename_to) is not None:
                # If it does, move the errors to the renamed dorm
                errors[dorm] = errors.pop(dorm_config.rename_to)

    return errors


def process_csv(filename: Path) -> list[Event]:
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
                Event.model_validate(
                    {
                        "name": event["Event Name"],
                        "dorm": [
                            (
                                dorm.strip()
                                if config.dorms.get(dorm.strip()) is None
                                else config.dorms[dorm.strip()].rename_to
                                or dorm.strip()
                            )
                            for dorm in event["Dorm"].split(",")
                            if dorm
                        ],
                        "location": event["Event Location"],
                        "start": process_dt_from_csv(event["Start Date and Time"]),
                        "end": process_dt_from_csv(event["End Date and Time"]),
                        "description": event["Event Description"],
                        "tags": [
                            tag.strip().lower()
                            for tag in event["Tags"].split(",")
                            if tag
                        ],
                        "group": (
                            [group.strip() for group in event["Group"].split(",")]
                            if event["Group"]
                            else None
                        ),
                    }
                )
            )
    return events


if __name__ == "__main__":
    api_response = APIResponse.model_validate(
        {
            "name": config.name,
            "published": datetime.now(timezone.utc),
            "events": [],
            "dorms": [],
            "groups": {},
            "tags": [],
            "colors": {
                "dorms": {
                    dorm: dorm_val.color for dorm, dorm_val in config.dorms.items()
                },
                "tags": {
                    tag: tag_val.color
                    for tag, tag_val in config.tags.items()
                    if tag_val.color
                },
            },
            "start": config.dates.start,
            "end": config.dates.end,
        }
    )
    orientation_events: list[Event] = []
    for filename in Path.iterdir(Path("events")):
        if not filename.name.endswith(".csv"):
            continue
        print(f"Processing {filename}...")
        if filename == config.orientation.file_name:
            orientation_events = process_csv(filename)
        else:
            api_response.events.extend(process_csv(filename))

    # Order events by start time, then by end time.
    # api_response.events.sort(key=lambda e: e["end"])
    # api_response.events.sort(key=lambda e: e["start"])
    api_response.events.sort(key=attrgetter("start", "end"))

    # Add extra data from events and config file
    api_response.dorms = sorted(
        list(set(dorm for e in api_response.events for dorm in e.dorm)),
        key=str.lower,
    )
    for dorm in config.dorms:
        rename_to = config.dorms[dorm].rename_to
        if rename_to in api_response.dorms:
            # If the dorm has a rename_to, put that at the front of the list
            api_response.dorms.remove(rename_to)
            api_response.dorms.insert(0, rename_to)

    for dorm in api_response.dorms:
        groups = sorted(
            list(
                set(
                    group.strip()
                    for e in api_response.events
                    if dorm in e.dorm and e.group
                    for group in e.group
                )
            ),
            key=str.lower,
        )
        if groups:
            api_response.groups[dorm] = groups

    api_response.tags = sorted(
        list(set(t for e in api_response.events for t in e.tags))
    )

    booklet_only_events = (
        orientation_events if config.orientation.include_in_booklet else []
    )

    errors = get_invalid_events(orientation_events, api_response)

    print("Processing complete!")

    print("Generating the booklet...")
    booklet_html = booklet.generate_booklet(api_response, config, booklet_only_events)

    print("Processing index.md...")
    index_html = booklet.generate_index()

    print("Processing errors...")
    errors_html = booklet.generate_errors(errors, api_response.name)

    print("Outputting booklet and JSON...")

    output_dir = Path("output")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(exist_ok=True)
    shutil.copytree("static", output_dir, dirs_exist_ok=True)
    with open(output_dir / "api.json", "w", encoding="utf-8") as w:
        w.write(api_response.model_dump_json())
    with open(output_dir / "booklet.html", "w", encoding="utf-8") as b:
        b.write(booklet_html)
    with open(output_dir / "index.html", "w", encoding="utf-8") as i:
        i.write(index_html)
    with open(output_dir / "errors.html", "w", encoding="utf-8") as e:
        e.write(errors_html)
    with open(output_dir / "openapi.yaml", "w", encoding="utf-8") as o:
        yaml.dump(
            get_api_schema().model_dump(mode="json", by_alias=True, exclude_none=True),
            o,
        )

    print("Complete!")
