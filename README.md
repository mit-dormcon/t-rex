# T-REX

The DormCon REX API, published to [rex.mit.edu].

For public-facing information about this project, visit [rex.mit.edu] or read
the index.md file.

[rex.mit.edu]: https://rex.mit.edu

## config.toml

`config.toml` configures the process script.

- `name`: the name of the current running event
- `colors.dorms` and `colors.tags` control the colors of dorm and tag badges on
  the REX Events page
- `dates` controls the start and end dates of REX for the booklet, has no effect
  on the web UI.

## Events Spreadsheets

A template spreadsheet is provided in `template.csv`. Events spreadsheets must
contain the following columns:

- `Event Name`: Name of the event
- `Dorm`: Dorm or living group hosting the event
- `Event Location`: Location of the event
- `Start Date and Time`: Start time in EDT formatted as `MM/DD/YYYY HH:MM`, in
  24-hour time
- `End Date and Time`: End time in EDT formatted as `MM/DD/YYYY HH:MM`, in
  24-hour time
- `Event Description`: A longer description of the event
- `Published`: Set to either `TRUE` or `FALSE`. Events not set to `TRUE` are not
  published to the API
- `Tags`: A comma-separated (no spaces) list of tags for the event

### Tag behavior

- Events tagged with `food` will be printed with a food icon in the booklet
- Events tagged with `mandatory` will be printed with a bold outline in the
  booklet
- Events tagged with `signature` will be printed with a dashed outline to
  highlight them in the booklet
- Events tagged with `tour` will be separated out and placed at the beginning of
  the booklet

### Orientation Events

You can add orientation or official events to the booklet using the
`events/orientation.csv` sheet. Set the dorm field to "Orientation" for these
events, and add "mandatory" to the list of tags.

These events are **skipped** for generating the JSON that populates the web UI,
but they will show up in the booklet.

## Running a local server

When developing the REX API and/or booklet, it can be useful to run a local
server. One way to do this is to use the
[Live Server extension](https://marketplace.visualstudio.com/items?itemName=ritwickdey.LiveServer)
for VSCode and access the files under the `output` directory.

Another way to do this is to use Python's `http.server` like so:[^cors]

```shell
$ python -m http.server 8080 --directory output/
```

Then, every time you make changes, run

```shell
$ poetry run python process.py
```

and refresh the page to see the new output!

[^cors]:
    Note that `http.server` doesn't support
    [CORS](https://en.wikipedia.org/wiki/Cross-origin_resource_sharing), so it
    won't work if you're trying to run a local server while also editing the REX
    Events Page.

## Making the REX booklet

Here is an outline of the process used to make the REX booklets:

1. **Print booklet.html** (either on your computer with localhost or at
   https://rex.mit.edu/booklet.html) to a PDF using Chrome.
   - The CSS should have this set up to use an A3 page size (11.7 x 16.5 inches)
     by default, but you might need to adjust this option to use A3. We use A3
     because it is easier to scale down two A3 pages and put them side by side
     on a letter sheet of paper for the booklet.
2. **Check the number of pages.** We only get 32 pages in our booklet, and we
   want to maximize use of this space.
3. **Adjust the font size.** You'll want to adjust the font size under
   `@media print` in static/guide-bw.css. Change the font size under `body` to
   affect the entire booklet, and under `#booklet-info` for just the first page
   with all the background information on REX.
   - Try to get all the background information on the first page to all fit onto
     one page. You can adjust this font size separately under `#booklet-info`,
     or you can make edits to templates/guide_fm.html.
   - Try to use the largest font size you can without going over 32 pages. In
     the past, we've been able to get somewhere between 16pt and 18pt depending
     on the number of events.
   - Note that the font size will be roughly _halved_ on the actual booklet
     because the printer will take two pages and sit them side-by-side.
4. **Regenerate the booklet.** You can either wait for the booklet to update
   online after making changes, or follow the instructions under
   [Running a local server](#running-a-local-server) to do it locally. Then,
   repeat steps 2-4 until the booklet looks good.
5. **Add page numbers to the PDF.** I've (@camtheman256) been using Adobe
   Acrobat to do this, but you can do it however you want.
   - To do this in Acrobat, use Edit &rarr; Header and Footer &rarr; Add. There
     should be a button to put in a page number.
   - I like to leave the page number off the cover. In Acrobat, there should be
     an option to exclude the cover from the pages to add the footer to. You can
     also get fancy and put the page numbers on the outsides of the booklet,
     putting it on the left or right if it's an even or odd page.
   - The font we use in the booklet is
     [Noto Sans](https://fonts.google.com/noto/specimen/Noto+Sans). You don't
     have to match the page numbers to it, but I think it's nice.
6. **Mail it to Bob.** We've been using
   [Goodfellow Printing](https://goodfellowprinting.com/) for our booklets
   historically because of an old DormCon connection. They usually do a great
   job for a good price and can ship all the booklets to campus.
