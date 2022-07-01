# T-REX

The DormCon REX API

## config.toml

`config.toml` configures the process script.

- `name`: the name of the current running event
- `colors.dorms` and `colors.tags` control the colors of dorm and tag badges on the REX Events page

## Events Spreadsheets

Events spreadsheets must contain the following columns:

- `Event Name`: Name of the event
- `Dorm`: Dorm or living group hosting the event
- `Event Location`: Location of the event
- `Start Date and Time`: Start time in EDT formatted as `MM/DD/YYYY HH:MM`, in 24-hour time
- `End Date and Time`: End time in EDT formatted as `MM/DD/YYYY HH:MM`, in 24-hour time
- `Event Description`: A longer description of the event
- `Published`: Set to either `TRUE` or `FALSE`. Events not set to `TRUE` are not published to the API
- `Tags`: A comma-separated (no spaces) list of tags for the event
