import jinja2
import datetime

import pytz
import markdown
import frontmatter

env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))
eastern = pytz.timezone("US/Eastern")


def event_dt_format(start_string, end_string):
    """
    Formats the time string that gets displayed on the booklet
    """
    start = datetime.datetime.fromisoformat(start_string)
    end = datetime.datetime.fromisoformat(end_string)
    out = start.strftime("%a")

    time_strings = []
    for dt in (start, end):
        if dt.hour == 12 and dt.minute == 0:
            time_strings.append("noon")
        elif dt.hour == 24 and dt.minute == 0:
            time_strings.append("midnight")
        else:
            if dt.minute == 0:
                time_strings.append(dt.strftime("%l %p"))
            else:
                time_strings.append(dt.strftime("%l:%M %p"))
    out += " " + " - ".join(time_strings)

    return out


env.globals["format_date"] = event_dt_format


def get_date_bucket(event: dict, cutoff: int):
    """
    Returns the date that an event "occurs" on. This method treats all events starting
    before hour_cutoff as occurring on the date before.
    """
    dt = datetime.datetime.fromisoformat(event["start"])
    if dt.hour < cutoff:
        return dt.date() - datetime.timedelta(days=1)
    return dt.date()


def generate_booklet(api, config, extra_events):
    # Bucket events into dates
    start_date = datetime.date.fromisoformat(api["start"])
    end_date = datetime.date.fromisoformat(api["end"])

    all_events = [e.copy() for e in api["events"] + extra_events]

    all_dates = set(
        get_date_bucket(e, config["dates"]["hour_cutoff"]) for e in all_events
    )
    dates = {
        "before": sorted(list(filter(lambda d: d < start_date, all_dates))),
        "rex": sorted(list(filter(lambda d: start_date <= d <= end_date, all_dates))),
        "after": sorted(list(filter(lambda d: d > end_date, all_dates))),
    }

    tours = []
    # Sort events into date buckets, separating out tours
    by_dates = {d: [] for d in all_dates}
    for event in all_events:
        event["emoji"] = [
            config["tag_emoji"][tag]
            for tag in event["tags"]
            if tag in config["tag_emoji"]
        ]
        if "tour" in event["tags"]:
            tours.append(event)
        else:
            by_dates[get_date_bucket(event, config["dates"]["hour_cutoff"])].append(
                event
            )

    # Order inside buckets by start, then end.
    for date in by_dates:
        by_dates[date].sort(key=lambda e: datetime.datetime.fromisoformat(e["end"]))
        by_dates[date].sort(key=lambda e: datetime.datetime.fromisoformat(e["start"]))

    tours.sort(key=lambda e: datetime.datetime.fromisoformat(e["end"]))
    tours.sort(key=lambda e: datetime.datetime.fromisoformat(e["start"]))

    published_string = (
        datetime.datetime.fromisoformat(api["published"])
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
        cover_dorms=[d for d in api["dorms"] if d != "All dorms"],
    )


def generate_index():
    """
    Generates homepage index.html using the Markdown file at index.md,
    with the template at templates/index.html
    """
    page = frontmatter.load("index.md")
    content = markdown.markdown(page.content)

    return env.get_template("index.html").render(content=content, **page.metadata)
