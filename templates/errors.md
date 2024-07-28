---
title: {{name}} Event Errors
description: This website contains errors found when processing REX events.
---

[_Back to main page_](./index.html)

> The following is a list of all errors found when processing {{name}} events.
> If there are any issues, please reach out to <dormcon-rex-chairs@mit.edu>.

{% for error in errors %}
- {{error}} {% endfor %}
