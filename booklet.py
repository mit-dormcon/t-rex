import jinja2
import datetime

env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))


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

    all_dates = set(get_date_bucket(e, config["dates"]["hour_cutoff"]) for e in api["events"])
    dates = {
        "before": sorted(list(filter(lambda d: d < start_date, all_dates))),
        "rex": sorted(list(filter(lambda d: start_date <= d <= end_date, all_dates))),
        "after": sorted(list(filter(lambda d: d > end_date, all_dates))),
    }

    tours = []
    # Sort events into date buckets
    by_dates = {d: [] for d in all_dates}
    for e in (api["events"] + extra_events):
        if "tour" in e["tags"]:
            tours.append(e)
        else:
            by_dates[get_date_bucket(e, config["dates"]["hour_cutoff"])].append(e)

    for date in by_dates:
        by_dates[date].sort(key=lambda e: datetime.datetime.fromisoformat(e["start"]))    

    return env.get_template("guide.html").render(
        api=api,
        by_dates=by_dates,
        tours=tours,
        dates=dates,
        start=start_date,
        end=end_date
    )
