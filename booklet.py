import jinja2
import datetime

env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))

def generate_booklet(api, config):
    # Bucket events into dates
    start_date = datetime.date.fromisoformat(api["start"])
    end_date = datetime.date.fromisoformat(api["end"])

    return env.get_template("guide.html").render(api=api, by_dates={}, start=start_date, end=end_date)