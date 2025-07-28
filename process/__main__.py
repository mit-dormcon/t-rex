"""
Primary script for processing REX events and generating the booklet.

This script reads event data from CSV files, validates the events,
and generates HTML files for the booklet, index, and errors.

It also generates an OpenAPI schema for the API response.
"""

import csv
import shutil
from operator import attrgetter
from pathlib import Path

import yaml

from .api_types import APIResponse, Event, get_api_schema, load_config
from .booklet import generate_booklet, generate_errors, generate_index, get_date_bucket
from .helpers import (
    check_if_events_conflict,
    event_with_same_name_exists,
    get_dorm_group,
    validate_unique_events,
)

config = load_config()


def get_main_dorm(dorm_main: str) -> str:
    """
    Get the main dorm name, considering renames in the configuration.

    Args:
        dorm_main (str): The main dorm name to check.

    Returns:
        str: The main dorm name, or the renamed version if it exists in the config.
    """
    if dorm_main in config.dorms:
        return config.dorms[dorm_main].rename_to or dorm_main

    return dorm_main


def get_invalid_events(
    api_events: list[Event], extra_events: list[Event]
) -> dict[str, tuple[list[str], list[str]]]:
    """
    Get list of error messages for invalid events.

    Formatted as a dict, with dorms as the key and
    a tuple of the contact emails and list of events as the value.

    Args:
        api_events (list[Event]): The list of API events to check.
        extra_events (list[Event]): The list of extra events to check.

    Returns:
        dict[str, tuple[list[str], list[str]]]: A dictionary with dorms as the key
        and a tuple of the contact emails and list of events as the value.
    """

    event_errors: dict[str, tuple[list[str], list[str]]] = {}

    # Check for conflicts with mandatory events and invalid events
    combined_events = api_events + extra_events
    mandatory_events = [
        event_to_check
        for event_to_check in combined_events
        if config.orientation.mandatory_tag in event_to_check.tags
    ]

    def create_error_dorm_entry(dorms: list[str], error_string: str) -> None:
        dorms_list = frozenset(get_main_dorm(dorm) for dorm in dorms)
        error_key = get_dorm_group(dorms_list)

        if event_errors.get(error_key) is None:
            contact_emails = list[str]()

            for check_dorm in dorms_list:
                if check_dorm in config.dorms:
                    contact_emails.append(config.dorms[check_dorm].contact)
                else:
                    # If the dorm is not in the config, find if it was renamed
                    for dorm_name, dorm_config in config.dorms.items():
                        if check_dorm in (dorm_config.rename_to, dorm_name):
                            contact_emails.append(dorm_config.contact)
                            break

            event_errors[error_key] = (
                contact_emails,
                [],
            )

        event_errors[error_key][1].append(error_string)

    for event in api_events:
        if event.end < event.start:
            event_date = (
                " on " + get_date_bucket(event, config.dates.hour_cutoff).strftime("%x")
                if event_with_same_name_exists(event, api_events)
                else ""
            )
            create_error_dorm_entry(
                event.dorm,
                f"{event.name} ({event.id}) {event_date} has an end time before its start time.",
            )
            continue

        for mandatory_event in mandatory_events:
            if check_if_events_conflict(
                event.start, event.end, mandatory_event.start, mandatory_event.end
            ):
                event_date = " on " + get_date_bucket(
                    event, config.dates.hour_cutoff
                ).strftime("%x")
                create_error_dorm_entry(
                    event.dorm,
                    f"{event.name} ({event.id}) conflicts with "
                    f"{mandatory_event.name} ({mandatory_event.id}){event_date}.",
                )
                continue

    for dorm_to_check in config.dorms:
        dorm_config = config.dorms[dorm_to_check]
        if dorm_config.rename_to:
            # If the dorm has a rename_to, check if it exists in the event_errors dict
            if event_errors.get(dorm_config.rename_to) is not None:
                # If it does, move the errors to the original name
                event_errors[dorm_to_check] = event_errors.pop(dorm_config.rename_to)

    return event_errors


def process_csv(filename: Path, encoding: str = "utf-8") -> list[Event]:
    """
    Processes a CSV file and yields Event objects.

    .. note::
        If you saved this with Excel as a CSV file with UTF-8 encoding, you might
        need to open it with encoding="utf-8-sig" instead of "utf-8".

    Args:
        filename (Path): The path to the CSV file to process.
        encoding (str, optional): The encoding of the CSV file. Defaults to "utf-8".

    Returns:
        list[Event]: A list of Event objects for each row in the CSV file.
    """
    with open(filename, encoding=encoding) as f:
        reader = csv.DictReader(f, strict=True)
        return validate_unique_events(*(Event.model_validate(row) for row in reader))


if __name__ == "__main__":
    api_response = APIResponse()

    # Get orientation events if they exist
    orientation_events = list[Event]()
    if config.orientation.file_name:
        print(f"Processing orientation events from {config.orientation.file_name}...")
        orientation_events = process_csv(config.orientation.file_name)

    event_files = {
        event_file
        for event_file in Path.iterdir(Path("events"))
        if event_file.name.endswith(".csv")
        and event_file != config.orientation.file_name
    }
    print(f"Processing events from {', '.join(str(f) for f in event_files)}...")

    all_events = [
        event for event_file in event_files for event in process_csv(event_file)
    ]

    api_response.events = sorted(
        # Get all events from other CSV files
        # Order events by start time, then by end time.
        (event for event in all_events if event.published),
        key=attrgetter("start", "end"),
    )

    # Add extra data from events and config file
    api_response.dorms = sorted(
        {dorm for e in api_response.events for dorm in e.dorm},
        key=str.lower,
    )

    for dorm in api_response.dorms:
        groups = sorted(
            {
                group
                for e in api_response.events
                if dorm in e.dorm and e.group
                for group in e.group
            },
            key=str.lower,
        )
        if groups:
            api_response.groups[dorm] = groups

    api_response.tags = sorted({t for e in api_response.events for t in e.tags})

    api_response.colors.dorms = {
        (config.dorms[dorm].rename_to or dorm): dorm_val.color
        for dorm, dorm_val in config.dorms.items()
        if ((config.dorms[dorm].rename_to or dorm) in api_response.dorms)
    }

    api_response.colors.tags = {
        tag: tag_val.color
        for tag, tag_val in config.tags.items()
        if tag_val.color and tag in api_response.tags
    }
    api_response.colors.groups = {
        (config.dorms[dorm].rename_to or dorm): {
            group: group_val.color
            for group, group_val in dorm_val.groups.items()
            if group
            in api_response.groups.get((config.dorms[dorm].rename_to or dorm), [])
        }
        for dorm, dorm_val in config.dorms.items()
        if dorm_val.groups
        and (config.dorms[dorm].rename_to or dorm) in api_response.dorms
    }

    errors = get_invalid_events(all_events, orientation_events)

    booklet_only_events = (
        [
            orientation_event
            for orientation_event in orientation_events
            if orientation_event.published
        ]
        if config.orientation.include_in_booklet
        else []
    )

    api_schema = get_api_schema().model_dump(
        mode="json", by_alias=True, exclude_none=True
    )

    print("Processing complete!")

    print("Generating the booklet..")
    booklet_html = generate_booklet(api_response, config, booklet_only_events)

    print("Processing index.md...")
    index_html = generate_index()

    print("Processing errors...")
    errors_html = generate_errors(errors, api_response.name)

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
        yaml.dump(api_schema, o)

    print("Complete!")
