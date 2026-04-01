# Goofish Rent Watcher

Browser-driven watcher for Goofish/Xianyu rent-transfer listings.

This repository is intended to be publishable and reusable. User-specific paths,
login artifacts, and local automation references are excluded from the project.

## What It Does

- Opens a visible browser session and reuses a dedicated login profile
- Searches Goofish for rent-transfer listings
- Applies keyword, price, sort, and nearby-location filters
- Tracks previously seen item IDs to avoid duplicate notifications
- Outputs either human-readable text or machine-readable JSON

## Project Status

The current implementation is intentionally narrow and pragmatic:

- it relies on browser automation instead of a public API
- it is sensitive to page-structure changes
- it works best as a personal watcher that you configure for your own area
- it is primarily verified on macOS at the moment

## Environment Requirements

- Python 3.11+
- macOS, Linux, or Windows with a desktop session
- network access to Goofish/Xianyu
- Playwright browser dependencies installed locally

Note:

- the repository is currently tested mainly on macOS
- Linux and Windows may work, but are not fully verified yet
- on some macOS setups, Playwright Chromium may be unstable, so a local Chrome path may be preferable

## Setup

Fast path:

```bash
make setup
```

This does the following in one pass:

- creates `.venv` if missing
- installs Python dependencies
- installs Playwright Chromium
- creates `.env` from `.env.example`
- runs `env-check`

Then edit `.env` at least once:

```dotenv
GOOFISH_MIN_PRICE=1500
GOOFISH_MAX_PRICE=2600
GOOFISH_NEARBY_RADIUS_KM=10
GOOFISH_NEARBY_LOCATION=your own target location
```

Then run:

```bash
make env-check
python3 -m goofish_rent capture-state
python3 -m goofish_rent check
```

## Configuration

The project auto-loads `.env` from the repository root.

| Variable | Default | Meaning |
| --- | --- | --- |
| `GOOFISH_SEARCH_KEYWORD` | `转租` | Search keyword |
| `GOOFISH_MIN_PRICE` | `1800` | Minimum price |
| `GOOFISH_MAX_PRICE` | `2400` | Maximum price |
| `GOOFISH_NEARBY_RADIUS_KM` | `5` | Nearby search radius |
| `GOOFISH_NEARBY_LOCATION` | `示例地址` | Nearby location text to search |
| `GOOFISH_SORT_MODE` | `latest` | Logical sort mode used in baseline context |
| `GOOFISH_CHROME_PATH` | empty | Optional local Chrome executable path |

If Playwright Chromium is unstable on macOS, you can set:

```dotenv
GOOFISH_CHROME_PATH=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
```

## Environment Check

Run before first login:

```bash
make env-check
```

Equivalent command:

```bash
python3 -m goofish_rent env-check
```

The command prints:

- detected Python version
- whether `playwright` is importable
- which browser path will be used
- active search/filter configuration
- any blocking issues

## Common Commands

Create local config:

```bash
python3 -m goofish_rent init-config
```

Capture login state:

```bash
python3 -m goofish_rent capture-state
```

Run one check:

```bash
python3 -m goofish_rent check
```

Emit JSON:

```bash
python3 -m goofish_rent check --json
```

Stable JSON interface:

```bash
python3 -m goofish_rent skill-check
```

Optional fallback:

```bash
python3 -m goofish_rent import-state /path/to/cookies.json
```

## Output Contract

`check` text mode when new items are found:

```text
整租一居室 | ¥3200/月 | 某区域 | https://www.goofish.com/...
合租次卧 | ¥1800/月 | 某区域 | https://www.goofish.com/...
```

`check` text mode when nothing is new:

```text
暂无新的符合条件的租房信息
```

`skill-check` JSON example:

```json
{"status":"new_items_found","notify":true,"message":"发现 2 条新的符合条件的租房信息","items":[{"item_id":"123","title":"整租一居室","price":"¥3200/月","area":"某区域","url":"https://www.goofish.com/item?id=123"}]}
```

Possible statuses:

- `initialized`
- `no_new_items`
- `new_items_found`
- `needs_login`
- `error`

## Runtime Files

These files are generated locally and should not be committed:

- `auth/browser_profile/`
- `auth/storage_state.json`
- `auth/session_storage.json`
- `auth/auth_metadata.json`
- `data/latest_results.json`
- `data/seen_item_ids.json`
- `others/`

## Privacy and Publishing Notes

- Do not commit real runtime data under `auth/`, `data/`, or `others/`
- Do not publish your real watched address in docs or examples
- Imported auth metadata stores only the source file name, not the absolute path
- Keep private local integrations outside this public repository

## Testing

Run:

```bash
make test
```

Equivalent raw command:

```bash
python3 -m unittest discover -s tests -p 'test*.py' -q
```

The current tests cover helper functions and selected CLI behavior, not the full live browser workflow.
