# Hotel Data Scraper

A modular Playwright-based hotel search data collector. Extracts basic listing data from
a search page, then processes every hotel's detail page in parallel to pull room-level
pricing, cancellation policy, and breakfast inclusion, and exports everything to a
formatted Excel workbook. Currently targets booking.com's search results format.

## Features

- **Two-phase scraping** — fast batched extraction of the search results page, then
  parallel per-hotel detail extraction using multiple worker processes.
- **Anti-detection** — user-agent rotation, stealth browser flags, randomized delays,
  staggered worker startup, per-worker fingerprint variation.
- **Excel export** — styled workbook with color-coded booleans, clickable hotel links,
  and a "Search Parameters" sheet parsed from the search URL.
- **Retry tooling** — re-run extraction for only the rows that failed in a previous run.
- **Failure analysis** — scans the day's log and asks GPT to summarize what broke.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- An OpenAI API key (optional — only needed for breakfast-inclusion analysis and the
  failure analyzer; the scraper itself runs fine without one)

## Quick Start

```bash
# Install dependencies (creates .venv automatically)
uv sync

# Install the Chromium browser Playwright needs
uv run playwright install chromium

# Optional: enable breakfast-inclusion analysis
cp .env.example .env
# then edit .env and set OPENAI_API_KEY

# Run the scraper
uv run python main.py
```

You'll be prompted for a Booking.com search results URL
(`https://www.booking.com/searchresults.html?ss=...`). Results are saved as a timestamped
`.xlsx` file in `Booking_Data/`.

## Architecture

```
main.py                      # CLI entry point — prompts for URL, drives the run
scraper/
  coordinator.py             # Orchestrates phase 1 -> phase 2
  search_page/
    basic_extractor.py       # Loads the search page, scrolls/paginates
    extractor.py             # Per-card and batched JS extraction (name, price, reviews...)
    locators.py               # CSS selectors for the search results page
  hotel_page/
    process_based_extractor.py  # Spawns worker processes, queue-based hotel distribution
    detailed_extractor.py       # Navigates a hotel page, extracts room rows, analyzes prices
    locators.py                  # CSS/JS selectors for the hotel detail page
browser/
  core.py                    # Page creation with stealth config + resource blocking
  navigation.py               # Scrolling, "load more" clicking, wait helpers
utils/
  anti_detection.py          # User-agent rotation, launch options, stealth scripts
  helpers.py                  # Safe element extraction, price cleaning
  url_parser.py                # Parses search parameters out of a booking.com URL
  logger.py                    # File + console logging
export/
  excel.py                   # Styled .xlsx export
analyzers/
  breakfast.py                # GPT-based "is breakfast actually free" classifier
config.py                    # All tunables (workers, timeouts, delays, output dirs)
retry_failed_hotels.py       # Standalone: re-scrape only the failed rows in a workbook
fail_analyzer.py             # Standalone: GPT summary of today's extraction failures
scheduled/
  search_recipe.json         # Destination + filters for the automated monthly run
  url_generator.py           # Builds this run's 3 search URLs from the recipe + today's date
  run_batch.py                # Non-interactive: runs all 3 searches, tolerates one failing
  email_template.json         # Subject/greeting/closing text for the report email
  send_report.py              # Emails results (or a failure alert) via SMTP
.github/workflows/
  monthly-scrape.yml          # Scheduled CI job: test gate -> batch scrape -> email
```

### Scraping flow

1. **Phase 1 (search page):** load the search URL, scroll/click "Load more" until all
   property cards are loaded, batch-extract name/link/address/price/review/star data in a
   single JS pass.
2. **Phase 2 (hotel pages):** distribute hotels across `MAX_WORKERS` worker processes
   (each with its own browser + one reused page), extract room rows per hotel, compute
   min price / min 2-person price / free cancellation / non-refundable / breakfast
   included.
3. **Export:** write everything to a styled Excel workbook, with an "Execution Error"
   column flagging rows that failed extraction.

## Configuration

Edit [`config.py`](config.py) directly — these are plain constants, not environment
variables:

| Setting | Default | Description |
|---|---|---|
| `MAX_WORKERS` | `6` | Parallel scraping processes |
| `HEADLESS` | `False` | Headless browser mode. Overridable via the `HEADLESS` env var (e.g. `HEADLESS=true`) for unattended environments with no display, like CI |
| `OUTPUT_DIR` | `Booking_Data` | Where result `.xlsx` files are saved |
| `LOG_DIR` | `logs` | Where log files are saved |
| `AUTO_FILLING_ENABLED` | `True` | Retry hotels with missing price data automatically |
| `RETRY_COUNT` | `2` | Retries per failed hotel-page extraction |

`.env` only needs `OPENAI_API_KEY` (see `.env.example`).

## Retrying failed hotels

If a run finishes with some rows flagged `Execution Error = True`, re-run just those:

```bash
uv run python retry_failed_hotels.py                 # defaults to the newest file in Booking_Data/
uv run python retry_failed_hotels.py path/to/file.xlsx --max-retries 4
```

## Analyzing failures

```bash
uv run python fail_analyzer.py
```

Scans the most recent scraping session in `logs/` and asks GPT to summarize failure
patterns and likely causes.

## Scheduled monthly run

A GitHub Actions workflow ([`.github/workflows/monthly-scrape.yml`](.github/workflows/monthly-scrape.yml))
runs automatically on the 1st of every month: it runs the test suite as a gate, then (only
if tests pass) runs 3 searches and emails the results.

**How the 3 searches are chosen:** [`scheduled/search_recipe.json`](scheduled/search_recipe.json)
holds a fixed destination + filters (currently: Georgia, hotels only, 2 adults, 1 room).
[`scheduled/url_generator.py`](scheduled/url_generator.py) builds one URL per entry in the
recipe's `months_ahead` list (default `[0, 1, 2]`, meaning "whatever month this runs in,
plus the next 2"), each dated `checkin_day`→`checkout_day` (default 15th→16th) of that
month. Nothing needs manual editing month to month — the dates are computed from the date
the job actually runs on. To change the destination, filters, or date range, edit
`search_recipe.json` directly; no code changes needed.

**How the email is built:** [`scheduled/email_template.json`](scheduled/email_template.json)
holds the subject, greeting, and closing text. [`scheduled/send_report.py`](scheduled/send_report.py)
fills in a bullet per successful search (e.g. `* 15-16 July, hotels`) and attaches the
corresponding `.xlsx` file. If the test gate fails, a different alert email is sent instead
(no scraping is attempted) so a broken scraper doesn't go unnoticed for a month.

**Required GitHub Actions secrets** (repo Settings → Secrets and variables → Actions):

| Secret | Example | Notes |
|---|---|---|
| `OPENAI_API_KEY` | `sk-...` | Same key used locally for breakfast analysis |
| `SMTP_HOST` | `smtp.gmail.com` | `smtp.gmail.com` for Gmail/Google Workspace, `smtp.office365.com` for Microsoft 365 |
| `SMTP_PORT` | `465` | SMTP over SSL |
| `SMTP_USERNAME` | `you@yourdomain.com` | The sending account |
| `SMTP_PASSWORD` | *(app password)* | An **app password**, not your login password — for Gmail/Workspace: Google Account → Security → 2-Step Verification → App Passwords |
| `REPORT_RECIPIENT` | `someone@example.com` | Comma-separated for multiple recipients |

**Testing locally before relying on the schedule:**

```bash
# See what URLs would be generated today
uv run python scheduled/url_generator.py

# Run the batch scrape for real (takes a while - see note below) and write scheduled_results.json
uv run python scheduled/run_batch.py

# Preview the email body/subject without sending anything
uv run python -c "
from scheduled.send_report import build_success_report
import json
results = json.load(open('scheduled_results.json'))
print(build_success_report(results)['body'])
"

# Actually send it (requires the SMTP_* env vars set locally, e.g. via .env + export)
uv run python scheduled/send_report.py success scheduled_results.json
```

You can also trigger the real workflow on demand from the GitHub Actions tab (it has a
`workflow_dispatch` trigger) instead of waiting for the 1st of the month.

**Note on run time:** the default recipe searches all of Georgia (`dest_type=country`),
which returns far more hotels than a single-city search — this repo's own local runs
against a single town returned dozens to low hundreds of hotels; a whole-country search is
plausibly much larger. Watch the first couple of scheduled/manual runs in the Actions tab
to see actual timing before trusting the monthly schedule unattended, and narrow
`search_recipe.json`'s filters (e.g. add a price or star-rating filter) if a run turns out
to take multiple hours.

## Testing

Booking.com's DOM changes without notice, so the test suite is split into two layers:

```bash
uv run pytest              # fast: unit tests + fixture-based selector regression tests
uv run pytest -m live      # slow, opt-in: hits real booking.com to check selectors are still valid
```

- **Unit tests** (`tests/test_*.py` for `helpers`, `url_parser`, `anti_detection`) cover
  pure logic with no browser involved.
- **Fixture-based regression tests** (`tests/test_search_page_extraction.py`,
  `tests/test_hotel_page_extraction.py`) load saved local HTML snapshots into a real
  headless Chromium page and run the actual extraction functions against them. These
  catch regressions in *our* code but won't detect drift on the live site, since the
  fixtures are static.
- **Live smoke test** (`tests/test_live_smoke.py`, marked `@pytest.mark.live`, skipped by
  default) hits the real booking.com site and asserts the selectors still resolve. This
  is the one that actually catches "booking.com changed their markup." Run it manually
  every so often, or before relying on a fresh scrape for anything important.
- If the live test fails, refresh the fixtures from a real page and diff:
  ```bash
  uv run python tests/refresh_fixtures.py "<a real search results URL>" "<a real hotel URL>"
  ```
  then update `scraper/*/locators.py` and the extraction JS to match what changed.

## Anti-Detection

- 5 rotating desktop user agents (Chrome/Firefox/Safari/Edge)
- Stealth init scripts (hides `navigator.webdriver`, spoofs plugins/languages)
- Randomized delays between actions and staggered worker startup (`worker_id * 2s`)
- Per-worker Chromium flag variation (image loading, logging, plugins) to diversify
  fingerprints across parallel workers

None of this guarantees you won't get blocked — if you do, reduce `MAX_WORKERS` and
increase delays in `config.py`.

## Troubleshooting

**Browser not installed:**
```bash
uv run playwright install chromium
```

**No hotels found / extraction failing across the board:** booking.com likely changed
their markup. Run the live test (`uv run pytest -m live`) to confirm, then refresh
fixtures and update locators as described above.

**Debugging a specific run:** set `HEADLESS = False` in `config.py` to watch the browser,
or `LOG_LEVEL = logging.DEBUG` for verbose logs in `logs/scraper_<date>.log`.

## Disclaimer

This tool is for research and educational purposes. Users are responsible for complying
with booking.com's terms of service, robots.txt, and applicable law. The authors are not
responsible for misuse.
