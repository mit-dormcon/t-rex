# T-REX

The DormCon REX API, published to [rex.mit.edu](https://rex.mit.edu).

## config.toml

`config.toml` configures the process script.

- `name`: the name of the current running event
- `colors.dorms` and `colors.tags` control the colors of dorm and tag badges on the REX Events page
- `dates` controls the start and end dates of REX for the booklet, has no effect on the web UI.

## Events Spreadsheets

A template spreadsheet is provided in `template.csv`. Events spreadsheets must contain the following columns:

- `Event Name`: Name of the event
- `Dorm`: Dorm or living group hosting the event
- `Event Location`: Location of the event
- `Start Date and Time`: Start time in EDT formatted as `MM/DD/YYYY HH:MM`, in 24-hour time
- `End Date and Time`: End time in EDT formatted as `MM/DD/YYYY HH:MM`, in 24-hour time
- `Event Description`: A longer description of the event
- `Published`: Set to either `TRUE` or `FALSE`. Events not set to `TRUE` are not published to the API
- `Tags`: A comma-separated (no spaces) list of tags for the event

### Tag behavior

- Events tagged with `food` will be printed with a food icon in the booklet
- Events tagged with `mandatory` will be printed with a bold outline in the booklet
- Events tagged with `favorite` will be printed with a dashed outline to highlight them in the booklet
- Events tagged with `tour` will be separated out and placed at the beginning of the booklet

### Orientation Events

You can add orientation or official events to the booklet using the `events/orientation.csv` sheet. 
Set the dorm field to "Orientation" for these events, and add "mandatory" to the list of tags.

These events are **skipped** for generating the JSON that populates the web UI, but they will show up
in the booklet.