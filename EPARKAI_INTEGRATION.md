# eParkai integration protocol and porting guide

This document describes the implementation in this repository as of interface
version 6 (2026-11-06). It is intended for implementing the same integration in
another project, without JUNG Visu Pro.

The integration uses the eParkai website's authenticated HTML forms and Drupal AJAX
responses. These are website endpoints, not a documented public API contract.
The user has confirmed successful retrieval through this integration, but a portal
change may still require changes to form names, fields or response parsing.
Examples below are synthetic and contain no real credentials or account data.

## 1. Components you need

The portable part is in [eparkai.py](eparkai.py):

| Component | Responsibility |
| --- | --- |
| `Client` | HTTP session, login, fetching generation data |
| `Forms` | Extract named input fields from HTML forms |
| `aggregate(..., hourly=True)` | Select newest complete day and produce hourly outputs |
| `Store` | Preserve readings and compute availability/staleness |
| `collect` | Run login and fetch each configured plant independently |

Python dependencies are `requests` and timezone data for `Europe/Vilnius` (`tzdata`
is bundled for Windows). Another language can implement the same HTTP protocol.

You do **not** need the JVP XML/Lua, `launch.ps1`, the bundled Windows interpreter,
the managed-worker heartbeat, or KNX forwarding to communicate with eParkai.
The current credential store uses Windows DPAPI; replace it with your application's
secret/session storage when porting to another platform.

## 2. Required configuration

| Value | Meaning / discovery |
| --- | --- |
| Username | eParkai login username/email |
| Password | eParkai login password |
| Client ID | Numeric component in `/user/12345/generation` after logging in |
| Plant ID | Value of the generation page's `generation_electricity` selector |
| Object address | Exact `address` selector value; needed to distinguish multiple objects |
| Interval minutes | Expected chart sampling interval: 60 by default; supported alternatives 15 and 30 |
| Local plant key | Your own unique key for storing this plant/object combination |

IDs should be treated as strings. Object address is an exact form value, not an
address to geocode or abbreviate. The implementation does not automatically discover
plant IDs or address choices; inspect the authenticated generation page to obtain
them. Two objects can share a plant ID, so do not key your cache by plant ID alone.

Example public configuration, with secrets stored separately:

```json
{
  "client_id": "12345",
  "plants": [
    {
      "key": "my_solar",
      "id": "123456",
      "object_address": "Exact selector value",
      "interval_minutes": 60
    }
  ]
}
```

## 3. HTTP session defaults

- Base URL: `https://www.eparkai.lt`.
- Keep a single cookie-aware HTTP session throughout login and all plant requests.
- Current User-Agent: `JVP-eParkai/1.0`; this is our identifier, not a required API key.
- Current timeouts: 10 seconds to connect and 30 seconds for reads. These are not
  a strict total request deadline.
- Verify HTTPS certificates. `requests` retains its default certificate checks.
- Login/navigation requests follow redirects; the generation AJAX POST does not.
- Send form bodies as `application/x-www-form-urlencoded`, not JSON.
- Treat HTTP errors as failures, but also validate content: a login page can return 200.

## 4. Login and session reuse

### Step A: Try saved cookies

Restore previously saved cookies, if available, then request:

```http
GET /user/12345/generation HTTP/1.1
Host: www.eparkai.lt
```

Parse the returned HTML and look for a form whose input named `form_id` has value
`product_generation_form`. Its presence is the current success check. Do not treat
HTTP 200 or a cookie's unexpired date as sufficient evidence of authentication.

If the generation form exists, reuse the session and proceed to fetching data.
Otherwise, perform a full login.

### Step B: Get the login form

```http
GET /user/login?destination=/user/12345/generation HTTP/1.1
Host: www.eparkai.lt
```

Find the form with `form_id=user_login_form`. Extract all its named input fields,
including hidden tokens. The current `Forms` parser collects `<input name=...
value=...>` inside each `<form>` and decodes HTML entities using Python's HTML parser.
It is not a general browser form serializer: it does not collect select options or
textarea contents, and duplicate input names overwrite earlier ones.

Missing login form means the page layout/flow changed; do not blindly post passwords
to some other form found on the page.

### Step C: Submit credentials

POST to the same login URL, retaining the extracted fields and overriding these:

| Form field | Value |
| --- | --- |
| `name` | Username/email |
| `pass` | Password |
| `login_type` | `1` |
| `form_id` | `user_login_form` from the extracted form |

Follow redirects, keep response cookies, and again require
`product_generation_form` in the resulting HTML.

If it is missing, report login required. Possible causes include incorrect
credentials or a portal contact-confirmation page requiring user interaction.
The implementation does not automate CAPTCHA, MFA or confirmation prompts.

### Step D: Persist session state

After a successful full login, save the session cookie jar. The current implementation
stores `name`, `value`, `domain`, `path`, `secure` and `expires` for each cookie.
Use your HTTP library's native cookie-jar serializer when available, to preserve
additional attributes too. Never invent a fixed cookie name or session lifetime.

In this repository cookies are encrypted in `session.bin` and credentials in
`credentials.bin`. A credential change invalidates the saved session. Persisted
cookies are currently saved after full login, not refreshed on every subsequent
successful request; a port may improve this by saving the updated jar after fetches.

## 5. Retrieve generation data for each plant

### Refresh the form tokens

Before **each plant's** fetch, GET `/user/{client_id}/generation` again and extract
`product_generation_form`. Tokens can change between requests; do not reuse one
plant's cached HTML form indefinitely.

If the generation form is missing, treat the session as expired. The current worker
pauses on this authentication failure until restarted; it does not repeatedly submit
credentials in a tight loop.

### Send the Drupal AJAX request

```http
POST /user/12345/generation?ajax_form=1&_wrapper_format=drupal_ajax HTTP/1.1
Host: www.eparkai.lt
X-Requested-With: XMLHttpRequest
Content-Type: application/x-www-form-urlencoded
```

| Form field | Value |
| --- | --- |
| `form_id` | Fresh extracted form ID, `product_generation_form` |
| `form_build_id` | Fresh extracted value, if present |
| `form_token` | Fresh extracted value, if present |
| `period` | `week` |
| `current_date` | Current calendar date in `Europe/Vilnius`, formatted `YYYY-MM-DD` |
| `generation_electricity` | Configured plant ID |
| `address` | Exact configured object address; omitted if empty |
| `_drupal_ajax` | `1` |
| `_triggering_element_name` | `period` |

Keep redirects disabled for this POST. A redirect is treated as an authentication
failure rather than followed to a login page and parsed as JSON.

The current implementation requests the week view to have several candidate days
available. It does not fetch arbitrary history or paginate older periods. If the
returned window contains no complete day, it retains its last valid reading.
Do not assume the day/year controls shown by the website accept the same payload
without checking the corresponding browser request.

## 6. Parse the AJAX response

The response is a JSON **array of Drupal commands**, not a plain readings object.
Look for entries with `command == "settings"`, then inspect
`settings.product_generation_form`. The parser requires exactly one matching series
with `labels` and `data` arrays of equal length.

Illustrative response fragment — deliberately incomplete, not a full-day fixture:

```json
[
  {
    "command": "settings",
    "settings": {
      "product_generation_form": {
        "labels": [
          ["2026", "Lapkričio", "05", "00:00"],
          ["2026", "Lapkričio", "05", "01:00"]
        ],
        "data": [0.0, 0.12]
      }
    }
  }
]
```

Pair each label with the data value at the same index. Labels may be a list of parts
or an already joined string. Their expected format is `year month-name day HH:MM`.

| Month number | Lithuanian name |
| --- | --- |
| 1 | Sausio |
| 2 | Vasario |
| 3 | Kovo |
| 4 | Balandžio |
| 5 | Gegužės |
| 6 | Birželio |
| 7 | Liepos |
| 8 | Rugpjūčio |
| 9 | Rugsėjo |
| 10 | Spalio |
| 11 | Lapkričio |
| 12 | Gruodžio |

The parser also normalizes the spelling `Rugsėo` to `Rugsėjo`, following the reference
integration's workaround. Do not rely on the host computer's date locale.

Values are interpreted as **interval energy in kWh**, not instantaneous kW or a
cumulative meter register. Preserve genuine numeric zero. Null, invalid, negative,
boolean or non-finite values must not be silently turned into zero.

## 7. Measurement time versus fetch time

The source label is interpreted in `Europe/Vilnius`. It does not contain a UTC
offset, so timezone rules must supply that offset.

- Measurement label: the date/hour reported by eParkai, potentially days old.
- Fetch timestamp: when your application successfully retrieved and validated data.
- Selected day: the date whose complete set of intervals is being published.

For example, data labelled `2026 Lapkričio 05 01:00` remains
`2026-11-05T01:00:00+02:00` even when fetched on November 6. Do not replace its date
with today or automatically add an hour to the displayed source label.

**Remaining semantic assumption:** completeness and subhourly bucketing currently
treat labels as interval starts. The portal's exact start-versus-end convention has
not been independently verified. Preserve raw labels in a new project's data model
and verify that convention before using the series for time-sensitive billing.

Fetching more often does not remove provider publication delay. The observed portal
can contain only a few early-hour samples for a day that has already ended.

## 8. Current complete-day and 24-hour selection rules

1. Group samples by their Lithuanian calendar date and local timestamp.
2. Examine dates before today, newest first; never select today's partial day.
3. Generate expected intervals from local midnight to next local midnight by walking
   in UTC using the configured 15-, 30- or 60-minute cadence.
4. Require exact label coverage and occurrence counts, with all values valid.
   Reject a day with missing/null intervals, extra timestamps or unexpected duplicates.
5. Select the first complete day, or report `No complete day available` and retain
   the previously published snapshot.
6. Sum energy into 24 local clock-hour buckets. Each bucket gets an energy value and
   its source date/hour label. Sum all intervals for `DailyEnergy`.

The current output includes:

```text
DataDate              2026-11-05
DailyEnergy           total kWh for the selected complete day
IsComplete            1
Hour00Energy          sum for local hour 00
Hour00Time            2026-11-05T00:00:00+02:00
...
Hour23Energy          sum for local hour 23
Hour23Time            2026-11-05T23:00:00+02:00
LatestDataTime        final source interval label within the selected day
LatestIntervalEnergy  energy in that final source interval
LastSuccessfulFetch   UTC collection timestamp
```

For subhourly inputs, `HourXXEnergy` is the sum of its constituent intervals, while
`LatestIntervalEnergy` still refers to one original interval.

### Daylight-saving transitions

Lithuanian local days can contain 23 or 25 hours. Do not require 24 input samples
unconditionally or attach the same fixed UTC offset throughout the year.

- Spring: the nonexistent clock-hour bucket has zero energy and an **empty timestamp**.
  This represents an absent hour, not a reported zero measurement.
- Autumn: combine the two occurrences of the repeated clock hour into one bucket.
  Its timestamp string contains both ISO labels, separated by ` / `, with their
  distinct offsets. Both occurrences must be present for the day to be complete.
- Repeated ambiguous labels are assigned in provider response order. That ordering
  is an assumption; if your provider payload supplies offsets, use them instead.

The 24 bucket energies always sum to the selected complete-day total. For a new
project without the fixed 24-point JVP requirement, retaining 23/24/25 individual
timestamped hours is preferable to combining the repeated hour.

## 9. Polling, errors and caching

The managed worker collects immediately after startup, then waits 3,600 seconds
after a successful collection. This is an hourly interval, not an alignment to the
top of every clock hour. There are no provider requests on each JVP polling cycle.

For one run with N plants, expect approximately:

- Valid saved session: one authentication-check GET, plus one GET and one POST per plant.
- Full login: add a login-page GET and credential POST, plus any redirect requests.

Transient failures retry after 5 minutes, doubling up to one hour. An authentication
failure pauses the managed collection loop until interface restart. A failure for
one plant retains that plant's previous data; other plants are still attempted.
Each run creates a new HTTP session and tries the persisted cookie jar first.

| Condition | Treatment |
| --- | --- |
| Bad credentials / missing authenticated form | Login required; no repeated automatic password attempts |
| Portal contact-confirmation prompt | User resolves it in the portal |
| Request timeout / HTTP failure / malformed JSON | Keep last data; bounded retry |
| Missing or ambiguous series | Schema/parse failure; keep last data |
| Incomplete latest day | Try the next older complete day in the response |
| No complete day in response | Keep last data and report the condition |
| Corrected historical values | Replace the selected snapshot; do not add totals again |

Persist snapshots atomically. In the JVP implementation, `HasData` indicates that a
valid reading exists. `IsStale` is true if no reading exists, DataDate is older than
yesterday in Lithuania, or there has been no successful fetch for three hours.
JVP also marks values stale when the helper is unavailable. A successful request
can therefore coexist with stale measurement data.

## 10. Suggested portable design

Keep these interfaces separate in your new application:

```text
SecretStore.loadCredentials(account)
SessionStore.loadCookieJar(account)
Provider.ensureAuthenticated(credentials, cookieJar)
Provider.fetchGeneration(clientId, plantId, objectAddress, date)
Parser.parseIntervals(drupalResponse, timezone)
Aggregator.latestCompleteDay(intervals, cadence, now)
ReadingStore.replaceSnapshot(plantKey, reading, fetchedAt)
Scheduler.runEveryHour()
```

Inject credentials and persistence into the provider rather than carrying over this
repository's module-global `STATE`. Preserve both original timestamps and UTC instants
where possible. Keep raw interval data separate from the 24 display buckets if the
new project needs charts, historical corrections or accounting.

Avoid logging passwords, cookies, form tokens, full account pages or command-line
credentials. The JVP password setting is a normal saved project field; DPAPI only
protects the helper's separate secret files. A new project should use its own secure
configuration UI and secret store.

The old standalone CLI/HTTP server functions still exist in `eparkai.py`, but they
are not used by the current JVP-managed integration. Do not mistake the local
`/v1/snapshot` endpoint for an eParkai website API.

## 11. Tests to bring into the new project

- Successful saved-session reuse and full form-based login.
- HTTP 200 containing a login page; expired-session AJAX redirect.
- Changed/missing form tokens, malformed JSON and missing generation series.
- Multiple plant/object combinations without sharing cached results accidentally.
- Genuine zeros versus null/missing intervals, duplicates and invalid numbers.
- Latest incomplete day falling back to an older complete day.
- 15/30-minute samples aggregated into hourly buckets.
- Month/year boundaries and 23/25-hour Lithuanian days.
- Provider revisions replacing previous values without double-counting.
- Network failure preserving cached data and updating status/freshness separately.
- A source timestamp from yesterday remaining yesterday after today's fetch.

Current synthetic tests are in [test_managed.py](test_managed.py) and
[developer/test_legacy.py](developer/test_legacy.py). Confirm real response shape,
units and timestamp convention against your own authenticated portal before relying
on the port for billing or operational control.

Protocol reference originally supplied for this project:
[algirdasc/hass-eparkai](https://github.com/algirdasc/hass-eparkai).
This document describes our implementation, including its assumptions and limits,
not an official eParkai API guarantee.
