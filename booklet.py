import jinja2

env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))

def generate_booklet(api):
    return env.get_template("guide.html").render(api=api, by_dates={})