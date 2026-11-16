"""
Archives a year's REX booklet so it stays viewable after the next REX.

Takes the generated booklet (output/booklet.html), embeds its local assets
(stylesheets and images) so the page doesn't depend on files that may change
in later years, and saves it to static/archive/<year>.html. main.py copies
static/ into the deployed site, so the archive is published on the next build.

Usage:
    uv run main.py          # generate output/booklet.html first
    uv run archive.py 2026  # then archive it to static/archive/2026.html
"""

import argparse
import base64
import mimetypes
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_PATH = Path(__file__).resolve().parent
OUTPUT_PATH = SCRIPT_PATH / "output"
ARCHIVE_PATH = SCRIPT_PATH / "static" / "archive"


class LocalAssetFinder(HTMLParser):
    """
    Collects <link rel="stylesheet"> and <img> tags that point at local files.

    Each entry is (original tag text, path), so the tag can be swapped out
    with a plain string replace.

    Attributes:
        stylesheets (list[tuple[str, str]]): Local stylesheet <link> tags.
        images (list[tuple[str, str]]): Local <img> tags.
    """

    def __init__(self):
        super().__init__()
        self.stylesheets: list[tuple[str, str]] = []
        self.images: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """
        Records the tag if it's a stylesheet link or image with a local path.

        Called by HTMLParser for every opening (and self-closing) tag.

        Args:
            tag (str): The lowercased tag name.
            attrs (list[tuple[str, str | None]]): The tag's attributes.
        """
        attr = dict(attrs)
        tag_text = self.get_starttag_text() or ""
        if tag == "link" and attr.get("rel") == "stylesheet":
            if href := local_ref(attr.get("href")):
                self.stylesheets.append((tag_text, href))
        elif tag == "img" and (src := local_ref(attr.get("src"))):
            self.images.append((tag_text, src))


def local_ref(ref: str | None) -> str | None:
    """
    Checks whether an href/src attribute points at a local file.

    Args:
        ref (str | None): The attribute value, or None if the attribute is missing.

    Returns:
        str | None: ref if it's a relative file path like assets/qrcode.png,
            otherwise None (for URLs, data URIs, anchors, or a missing attribute).
    """
    if not ref or ref.startswith("#"):
        return None
    parsed = urlparse(ref)
    return None if parsed.scheme or parsed.netloc else ref


def get_booklet_year() -> str:
    """
    Prompts for the booklet year until a 4-digit year is entered.

    Returns:
        str: The year, e.g. "2026".
    """
    year = input("Enter the booklet year to archive: ").strip()

    if not year.isdigit() or len(year) != 4:
        print("Invalid year. Please enter a 4-digit year.")
        return get_booklet_year()

    return year


def get_current_booklet_path() -> Path:
    """
    Finds the most recently generated booklet.

    Returns:
        Path: The path to output/booklet.html.

    Raises:
        FileNotFoundError: If the booklet hasn't been generated yet.
    """
    booklet_path = OUTPUT_PATH / "booklet.html"

    if not booklet_path.exists():
        raise FileNotFoundError(
            "Current booklet not found. Run `uv run main.py` to generate it first."
        )

    return booklet_path


def to_data_uri(path: Path) -> str:
    """
    Encodes a file as a base64 data URI, guessing its MIME type from the extension.

    Args:
        path (Path): The file to encode.

    Returns:
        str: A data URI, e.g. "data:image/png;base64,...".
    """
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def clean_booklet(booklet: Path) -> str:
    """
    Removes local references by inlining CSS and using data URIs for images.

    Remote references (e.g. Google Fonts, links to dormcon.mit.edu) are kept
    as-is. Local paths are resolved relative to the booklet's directory.
    Prints a warning if an inlined stylesheet uses url(...), since those
    references are not embedded.

    Args:
        booklet (Path): The booklet HTML file to clean.

    Returns:
        str: The self-contained booklet HTML.
    """
    content = booklet.read_text(encoding="utf-8")
    base_dir = booklet.parent

    finder = LocalAssetFinder()
    finder.feed(content)

    for tag_text, href in finder.stylesheets:
        css = (base_dir / href).read_text(encoding="utf-8")
        if "url(" in css:
            print(f"  Warning: {href} uses url(...), which won't be embedded")
        content = content.replace(tag_text, f"<style>\n{css.strip()}\n    </style>")
        print(f"  inlined stylesheet {href}")

    for tag_text, src in finder.images:
        data_uri = to_data_uri(base_dir / src)
        content = content.replace(tag_text, tag_text.replace(src, data_uri))
        print(f"  embedded image {src}")

    return content


def main():
    """
    Archives the current booklet to static/archive/<year>.html.

    Reads the year from the command line (or prompts for it), and refuses to
    overwrite an existing archive unless --force is passed. Warns if the
    booklet doesn't look like it's for the given year.
    """
    parser = argparse.ArgumentParser(description="Archive the current REX booklet.")
    parser.add_argument("year", nargs="?", help="4-digit booklet year, e.g. 2026")
    parser.add_argument(
        "-f", "--force", action="store_true", help="overwrite an existing archive"
    )
    args = parser.parse_args()

    year = args.year
    if year is None:
        year = get_booklet_year()
    elif not year.isdigit() or len(year) != 4:
        parser.error("year must be a 4-digit year")

    archive_path = ARCHIVE_PATH / f"{year}.html"
    if archive_path.exists() and not args.force:
        sys.exit(f"{archive_path} already exists. Use --force to overwrite it.")

    booklet_path = get_current_booklet_path()
    if f"REX {year}" not in booklet_path.read_text(encoding="utf-8"):
        print(
            f"Warning: the current booklet doesn't mention 'REX {year}'. "
            "Make sure config.toml has the right event name."
        )

    print(f"Archiving booklet for the year {year}...")
    booklet_content = clean_booklet(booklet_path)

    ARCHIVE_PATH.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(booklet_content, encoding="utf-8")
    print(f"Booklet archived to {archive_path.relative_to(SCRIPT_PATH)}")


if __name__ == "__main__":
    main()
