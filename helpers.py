"""
Helper functions for processing REX events.
"""

import csv
from collections.abc import Hashable
from functools import cache
from typing import TYPE_CHECKING, Annotated, TypeVar
from zoneinfo import ZoneInfo

from pydantic import AfterValidator, Field, ValidationError

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path
    from typing import Callable, Iterable, Sequence

    from pydantic import BaseModel

    from api_types import Event

TIMEZONE = ZoneInfo("America/New_York")

H = TypeVar("H", bound=Hashable)


def _validate_unique_list(v: list[H]) -> list[H]:
    if len(v) != len({*v}):
        raise ValidationError("List must be unique")
    return v


UniqueList = Annotated[
    list[H],
    AfterValidator(_validate_unique_list),
    Field(json_schema_extra={"uniqueItems": True}),
]


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


def event_with_same_name_exists(event: "Event", events: Iterable["Event"]) -> bool:
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


def validate_unique_events(events: Sequence["Event"]) -> list["Event"]:
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


def process_csv[M: BaseModel](
    filename: Path,
    model: type[M],
    validate: Callable[[Sequence[M]], list[M]],
    encoding: str = "utf-8",
) -> list[M]:
    """
    Processes a CSV file and yields Event objects.

    .. note::
        If you saved this with Excel as a CSV file with UTF-8 encoding, you might
        need to open it with encoding="utf-8-sig" instead of "utf-8".

    Args:
        filename (Path): The path to the CSV file to process.
        model (type[M]): The model type to validate each row against.
        validate (Callable[[Sequence[M]], list[M]]): A function to validate the list of models.
        encoding (str, optional): The encoding of the CSV file. Defaults to "utf-8".

    Returns:
        list[M]: A list of validated model objects for each row in the CSV file.
    """
    with open(filename, encoding=encoding, newline="") as f:
        reader = csv.DictReader(f, strict=True)
        models = tuple(model.model_validate(row) for row in reader)
        return validate(models)
