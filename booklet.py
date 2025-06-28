from datetime import date, datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo

import frontmatter
import jinja2
import markdown

from api_types import APIResponse, Config, Event, EventWithEmoji

env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))
eastern = ZoneInfo("America/New_York")


def event_dt_format(start_string: str, end_string: str, group=""):
    """
    Formats the time string that gets displayed on the booklet
    """
    start = datetime.fromisoformat(start_string)
    end = datetime.fromisoformat(end_string)
    out = start.strftime("%a")

    time_strings: list[str] = []
    for dt in (start, end):
        if dt.hour == 12 and dt.minute == 0:
            time_strings.append("noon")
        elif dt.hour == 24 and dt.minute == 0:
            time_strings.append("midnight")
        else:
            if dt.minute == 0:
                time_strings.append(dt.strftime("%I %p").lstrip("0"))
            elif dt.minute % 10 == 3 and group.lower() in ["b3rd", "burton third"]:
                time_strings.append(
                    f"{dt.strftime('%I:%M').lstrip('0')}rd {dt.strftime('%p')}"
                )
            else:
                time_strings.append(dt.strftime("%I:%M %p").lstrip("0"))
    out += " " + " - ".join(time_strings)

    return out


env.globals["format_date"] = event_dt_format


def get_date_bucket(event: Event, cutoff: int):
    """
    Returns the date that an event "occurs" on. This method treats all events starting
    before hour_cutoff as occurring on the date before.
    """
    dt = datetime.fromisoformat(event["start"])
    if dt.hour < cutoff:
        return dt.date() - timedelta(days=1)
    return dt.date()


def generate_booklet(api: APIResponse, config: Config, extra_events: list[Event]):
    # Bucket events into dates
    start_date = date.fromisoformat(api["start"])
    end_date = date.fromisoformat(api["end"])

    all_events = [e.copy() for e in api["events"] + extra_events]

    all_dates = set(
        get_date_bucket(e, config["dates"]["hour_cutoff"]) for e in all_events
    )
    dates = {
        "before": sorted(list(filter(lambda d: d < start_date, all_dates))),
        "rex": sorted(list(filter(lambda d: start_date <= d <= end_date, all_dates))),
        "after": sorted(list(filter(lambda d: d > end_date, all_dates))),
    }

    tours: list[Event] = []
    # Sort events into date buckets, separating out tours
    by_dates: dict[date, list[Event]] = {d: [] for d in all_dates}
    for event in all_events:
        event = cast(
            EventWithEmoji,
            dict(
                event,
                emoji=[
                    config["tag_emoji"][tag]
                    for tag in event["tags"]
                    if tag in config["tag_emoji"]
                ],
            ),
        )

        # Tours are separated and put at the front of the booklet
        if "tour" in event["tags"]:
            tours.append(event)
        else:
            by_dates[get_date_bucket(event, config["dates"]["hour_cutoff"])].append(
                event
            )

    # Order inside buckets by start, then end.
    for by_date in by_dates:
        by_dates[by_date].sort(key=lambda e: datetime.fromisoformat(e["end"]))
        by_dates[by_date].sort(key=lambda e: datetime.fromisoformat(e["start"]))

    tours.sort(key=lambda e: datetime.fromisoformat(e["end"]))
    tours.sort(key=lambda e: datetime.fromisoformat(e["start"]))

    published_string = (
        datetime.fromisoformat(api["published"])
        .astimezone(eastern)
        .strftime("%B %d, %Y at %I:%M %p")
    )

    return env.get_template("guide.html").render(
        api=api,
        by_dates=by_dates,
        tours=tours,
        dates=dates,
        start=start_date,
        end=end_date,
        emoji=config["tag_emoji"],
        published=published_string,
        cover_dorms=[
            d
            for d in api["dorms"]
            if d != config["rename_dormcon_to"] and d not in config["dorms"]["subdorms"]
        ],
    )


def generate_index():
    """
    Generates homepage index.html using the Markdown file at index.md,
    with the template at templates/index.html
    """
    page = frontmatter.load("index.md")
    content = markdown.markdown(page.content)

    return env.get_template("index.html").render(content=content, **page.metadata)


def generate_errors(errors: dict[str, tuple[list[str], list[str]]], name: str):
    """
    Generates the error page using the template at templates/errors.html
    """
    return env.get_template("errors.html").render(errors=errors, name=name)
