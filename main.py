"""
Primary script for processing REX events and generating the booklet.

This script reads event data from CSV files, validates the events,
and generates HTML files for the booklet, index, and errors.

It also generates an OpenAPI schema for the API response.
"""

import shutil
from pathlib import Path

import yaml

from api_types import APIResponse, Config, get_api_schema
from booklet import generate_booklet, generate_errors, generate_index


def main() -> None:
    """
    Main function to process events and generate the booklet.
    Reads event data from CSV files, validates the events, and generates HTML files
    for the booklet, index, and errors. Also generates an OpenAPI schema for the API response.
    """
    api_response = APIResponse()
    config = Config()  # type: ignore

    api_schema = get_api_schema().model_dump(
        mode="json", by_alias=True, exclude_none=True
    )

    print("Generating the booklet..")
    booklet_html = generate_booklet(api_response, config)

    print("Processing index.md...")
    index_html = generate_index()

    print("Processing errors...")
    errors = api_response.get_invalid_events()
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


if __name__ == "__main__":
    main()
