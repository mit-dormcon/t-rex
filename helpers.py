"""
Helper functions for processing REX events.
"""

from datetime import datetime
from functools import cache
from typing import Iterable

from pydantic import ValidationError, validate_call

from api_types import Event


@cache
def check_if_events_conflict(
    event_one_start: datetime,
    event_one_end: datetime,
    event_two_start: datetime,
    event_two_end: datetime,
) -> bool:
    """
    Checks if two events conflict with each other.

    Args:
        event_one_start (datetime): The start time of the first event.
        event_one_end (datetime): The end time of the first event.
        event_two_start (datetime): The start time of the second event.
        event_two_end (datetime): The end time of the second event.

    Returns:
        bool: True if the events conflict, False otherwise.
    """

    return (
        (event_two_start <= event_one_start < event_two_end)
        or (event_two_start < event_one_end <= event_two_end)
        or (event_one_start <= event_two_start < event_one_end)
        or (event_one_start < event_two_end <= event_one_end)
    )


@cache
def get_dorm_group(dorms: Iterable[str]) -> str:
    """
    Returns a comma-separated string from a list of dorm names.

    Args:
        dorms (Iterable[str]): A list of dorm names.

    Returns:
        str: A comma-separated string of dorm names.
    """
    return ", ".join(dorms)


def event_with_same_name_exists(event: Event, events: Iterable[Event]) -> bool:
    """
    Checks if an event with the same name exists in the list of events.

    Args:
        event (Event): The event to check for duplicates.
        events (Iterable[Event]): The list of events to check against.

    Returns:
        bool: True if a duplicate event exists, False otherwise.
    """
    for e in events:
        if e.name == event.name and e.start != event.start and e.end != event.end:
            return True
    return False


@validate_call
def validate_unique_events(*events: Event) -> list[Event]:
    """
    Validates that the events are unique by their ID.
    Args:
        *events (Event): The events to validate.

    Raises:
        ValueError: If the events are not unique by ID.

    Returns:
        list[Event]: The validated list of unique events.
    """
    if len(events) != len({event.id for event in events}):
        raise ValidationError("Events must be unique by ID")
    return list(events)
