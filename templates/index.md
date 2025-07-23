Title: T-REX, the DormCon REX API  
Description: This website hosts raw data about DormCon REX Events.

GitHub: [mit-dormcon/t-rex][repo]

> **If you're looking to learn more about REX or see what events are happening,
> please visit the official site at [dormcon.mit.edu/rex][rex]. **

## What's this website?

This website hosts the backend of the [REX Events page][events] on the DormCon
website. The code that generates this website produces a few files:

- [index.html](./index.html) - This is the page you're reading right now!
- [api.json](./api.json) - This structured data is provided to the [REX Events
  page][events]. Feel free to use it for your own purposes! The structure of the
  JSON is documented on the [main DormCon website][docs], and you can also look
  at the schema by viewing [openapi.yaml](./openapi.yaml).
- [booklet.html](./booklet.html) - This is the web version of the REX booklet,
  always up to date with the latest changes.
- [errors.html](./errors.html) - This contains a list of all errors present in
  the submitted REX events, including events with invalid times and events that
  conflict with mandatory orientation events.

## Can I use the API data for my own project?

Sure, you're more than welcome to!

If you have any questions or feedback on the API, feel free to contact me at
<dormcon-tech-chair@mit.edu>, though unfortunately, I don't have the bandwidth
to offer tech support for any derivative projects.

This website is a project of the DormCon Tech Chair.

[repo]: https://github.com/mit-dormcon/t-rex
[rex]: https://dormcon.mit.edu/rex
[events]: https://dormcon.mit.edu/rex/events
[docs]: https://dormcon.mit.edu/rex/api
