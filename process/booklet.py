"""
This module contains functions to generate the REX booklet and index page.

It uses Jinja2 for templating and Markdown for rendering the index page.

It also includes functions to format event dates and handle errors.
"""

from datetime import datetime, timedelta
from operator import attrgetter
from typing import Optional
from zoneinfo import ZoneInfo

import jinja2
import markdown

from .api_types import APIResponse, Config, Event

env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))
eastern = ZoneInfo("America/New_York")


def event_dt_format(start: datetime, end: datetime, groups: Optional[list[str]] = None):
    """
    Formats the time string that gets displayed on the booklet
    """
    out = start.strftime("%a")

    if groups is None:
        groups = []

    time_strings = list[str]()
    for dt in (start, end):
        if dt.hour == 12 and dt.minute == 0:
            time_strings.append("noon")
        elif dt.hour == 24 and dt.minute == 0:
            time_strings.append("midnight")
        else:
            if dt.minute == 0:
                time_strings.append(dt.strftime("%I %p").lstrip("0"))
            elif dt.minute % 10 == 3 and bool(
                # If the group is B3rd or Burton Third, use "rd" for the time
                {group.lower() for group in groups} & {"b3rd", "burton third", "b3"}
            ):
                time_strings.append(
                    f"{dt.strftime('%I:%M').lstrip('0')}rd {dt.strftime('%p')}"
                )
            else:
                time_strings.append(dt.strftime("%I:%M %p").lstrip("0"))
    out += " " + " - ".join(time_strings)

    return out


env.globals["format_date"] = event_dt_format  # type:  ignore


def get_date_bucket(event: Event, cutoff: int):
    """
    Returns the date that an event "occurs" on. This method treats all events starting
    before `hour_cutoff` as occurring on the date before.

    Args:
        event (Event): The event to get the date bucket for.
        cutoff (int): The hour cutoff to determine the date bucket.

    Returns:
        date: The date that the event occurs on, adjusted for the hour cutoff.
    """
    dt = event.start
    if dt.hour < cutoff:
        return dt.date() - timedelta(days=1)
    return dt.date()


def generate_booklet(
    api: APIResponse, config: Config, extra_events: list[Event]
) -> str:
    """
    Generates the REX booklet HTML.

    Args:
        api (APIResponse): The API response object containing event data.
        config (Config): The configuration object.
        extra_events (list[Event]): A list of extra events to include in the booklet.

    Returns:
        str: The rendered HTML for the booklet.
    """

    # Bucket events into dates
    start_date = api.start
    end_date = api.end

    all_events = [e.model_copy() for e in api.events + extra_events]
    all_dates = {get_date_bucket(e, config.dates.hour_cutoff) for e in all_events}

    dates = {
        "before": sorted(filter(lambda d: d < start_date, all_dates)),
        "rex": sorted(filter(lambda d: start_date <= d <= end_date, all_dates)),
        "after": sorted(filter(lambda d: d > end_date, all_dates)),
    }

    tours = list[Event]()
    # Sort events into date buckets, separating out tours
    by_dates = {d: list[Event]() for d in all_dates}
    for event in all_events:
        # Tours are separated and put at the front of the booklet
        if "tour" in event.tags:
            tours.append(event)
        else:
            by_dates[get_date_bucket(event, config.dates.hour_cutoff)].append(event)

    # Order inside buckets by start, then end.
    for by_date in by_dates:
        by_dates[by_date].sort(key=attrgetter("start", "end"))

    tours.sort(key=attrgetter("start", "end"))

    published_string = api.published.astimezone(eastern).strftime(
        "%B %d, %Y at %I:%M %p"
    )

    cover_dorms = list[str]()
    for dorm in api.dorms:
        if dorm in config.dorms and config.dorms[dorm].include_on_cover:
            cover_dorms.append(dorm)
        else:
            # check if the dorm was renamed
            for dorm_name, dorm_config in config.dorms.items():
                if (
                    dorm in (dorm_config.rename_to, dorm_name)
                    and dorm_config.include_on_cover
                ):
                    cover_dorms.append(dorm)

    return env.get_template("guide.html").render(
        api=api,
        by_dates=by_dates,
        tours=tours,
        dates=dates,
        start=start_date,
        end=end_date,
        tags={tag for event in all_events for tag in event.tags},
        emojis={
            tag: config.tags[tag].emoji
            for tag in api.tags
            if tag in config.tags and config.tags[tag].emoji
        },
        published=published_string,
        cover_dorms=cover_dorms,
    )


def generate_index() -> str:
    """
    Generates homepage index.html using the Markdown file at index.md,
    with the template at templates/template.html

    Returns:
        str: The rendered HTML for the index page.
    """
    md = markdown.Markdown(extensions=["meta"])

    with open("templates/index.md", encoding="utf-8") as f:
        content = md.convert(f.read())

    metadata: dict[str, list[str]] = {
        k: (v[0] if isinstance(v, list) else v)
        for k, v in (md.Meta or {}).items()  # pylint: disable=no-member # type: ignore
    }
    return env.get_template("template.html").render(content=content, **metadata)


def generate_errors(errors: dict[str, tuple[list[str], list[str]]], name: str) -> str:
    """
    Generates the error page using the template at templates/errors.html

    Args:
        errors (dict[str, tuple[list[str], list[str]]]):
            A dictionary mapping event names to a tuple of (contact_emails, list_of_errors).

        name (str): The name of the event.

    Returns:
        str: The rendered HTML for the error page.
    """

    content = env.get_template("errors.html").render(errors=errors)

    return env.get_template("template.html").render(
        title=f"{name} Event Errors",
        content=content,
    )
