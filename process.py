import csv
import os
import shutil
import toml
import datetime
import pytz
import json
import re
import string

config = toml.load("config.toml")

def tex_escape(text):
    """
        :param text: a plain text message
        :return: the message escaped to appear correctly in LaTeX
    """
    conv = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
        '<': r'\textless{}',
        '>': r'\textgreater{}',
    }
    regex = re.compile('|'.join(re.escape(str(key)) for key in sorted(conv.keys(), key = lambda item: - len(item))))
    return ''.join(filter(lambda c: c in string.printable, regex.sub(lambda match: conv[match.group()], text)))


def process_time(time_string: str) -> str:
    eastern_tz = pytz.timezone("US/Eastern")
    event_dt = eastern_tz.localize(datetime.datetime.strptime(time_string, "%m/%d/%Y %H:%M"))
    return event_dt.isoformat()

def process_csv(filename: str) -> list[dict]:
    events = []
    with open(filename) as f:
        reader = csv.DictReader(f)
        for event in reader:
            if event["Published"] != "TRUE":
                continue
            events.append({
                "name": event["Event Name"],
                "dorm": event["Dorm"],
                "location": event["Event Location"],
                "start": process_time(event["Start Date and Time"]),
                "end": process_time(event["End Date and Time"]),
                "description": event["Event Description"]
            })
    return events

def create_booklet(data: dict):
    if os.path.exists("compiled"): shutil.rmtree("compiled")
    os.mkdir("compiled")
    with open("compiled/properties.tex", "w") as f:
        f.write("\\newcommand{\eventtitle}{" + data["name"] + "}\n")
        f.write("\\newcommand{\eventdescription}{" + data["description"] + "}\n")
    
    with open("compiled/events.tex", "w") as f:
        for event in data["events"]:
            format = "%D %l:%M %p"
            start = datetime.datetime.fromisoformat(event["start"])
            end = datetime.datetime.fromisoformat(event["end"])
            f.write(f"{{\\Large \\bf {tex_escape(event['name'])} \\large \\rm at {tex_escape(event['location'])} }} \\hfill \\textbf{{{event['dorm']}}} \\\\ \n")
            f.write(f"{{\\it Runs {start.strftime(format)} to {end.strftime(format)}}} \\\\\n")
            f.write(f"{tex_escape(event['description'])}\n\n")
            f.write("\\vspace{16pt}\n")


if __name__ == "__main__":
    api_response = {
        "name": config["name"],
        "description": config["description"],
        "published": datetime.datetime.now().isoformat(),
        "events": []
    }
    for filename in os.listdir("events"):
        print(f"Processing {filename}...")
        api_response["events"].extend(process_csv("events/" + filename))
    
    api_response["events"].sort(key=lambda e: e["start"])
    api_response["dorms"] = sorted(list(set(e["dorm"] for e in api_response["events"])))

    print("Processing complete! Creating API JSON...")

    
    if os.path.exists("output"): shutil.rmtree("output")
    os.mkdir("output")
    with open("output/api.json", "w") as w:
        json.dump(api_response, w)

    print("JSON complete! Creating LaTeX for booklet...")

    create_booklet(api_response)
    
    print("Complete!")