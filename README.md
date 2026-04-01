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

## Environment Requirements

- Python 3.11+
- macOS, Linux, or Windows with a desktop session
- network access to Goofish/Xianyu
- Playwright browser dependencies installed locally

## Setup

Fast path:

```bash
make setup
```

This does four things in one pass:

- creates `.venv` if missing
- installs Python dependencies
- installs Playwright Chromium
- creates `.env` from `.env.example`
- runs `env-check`

Manual path:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium
```

Create a local config file once:

```bash
python3 -m goofish_rent init-config
```

This project auto-loads `.env` from the repository root if the file exists.
You can still override values with shell environment variables.

## Environment Check

Run this before the first login:

```bash
python3 -m goofish_rent env-check
```

The command prints:

- detected Python version
- whether the `playwright` package is importable
- which browser path will be used
- active search/filter configuration
- any blocking issues found during the check

## Configuration

All user-specific search settings are configurable through environment variables.

| Variable | Default | Meaning |
| --- | --- | --- |
| `GOOFISH_SEARCH_KEYWORD` | `转租` | Search keyword |
| `GOOFISH_MIN_PRICE` | `1800` | Minimum price |
| `GOOFISH_MAX_PRICE` | `2400` | Maximum price |
| `GOOFISH_NEARBY_RADIUS_KM` | `5` | Nearby search radius |
| `GOOFISH_NEARBY_LOCATION` | `示例地址` | Nearby location text to search |
| `GOOFISH_SORT_MODE` | `latest` | Logical sort mode used in baseline context |
| `GOOFISH_CHROME_PATH` | empty | Optional local Chrome executable path |

Example:

```bash
cat .env
```

Typical first edit:

```dotenv
GOOFISH_SEARCH_KEYWORD=转租
GOOFISH_MIN_PRICE=1500
GOOFISH_MAX_PRICE=2600
GOOFISH_NEARBY_RADIUS_KM=10
GOOFISH_NEARBY_LOCATION=某小区或地标
```

## Usage

Recommended first-run flow:

1. Run `make setup`
2. Edit `.env` once with your own location and price range
3. Run `make env-check`
4. Run `python3 -m goofish_rent capture-state`
5. Run `python3 -m goofish_rent check`

1. Capture login state in a dedicated browser profile:

```bash
python3 -m goofish_rent capture-state
```

2. Run a one-shot check:

```bash
python3 -m goofish_rent check
```

3. Get machine-readable JSON:

```bash
python3 -m goofish_rent check --json
```

4. Use the stable integration-oriented JSON mode:

```bash
python3 -m goofish_rent skill-check
```

5. Optional fallback: import exported cookie state:

```bash
python3 -m goofish_rent import-state /path/to/cookies.json
```

## Runtime Files

These files are generated locally and are ignored by git:

- `auth/browser_profile/`: reusable browser profile
- `auth/storage_state.json`: exported browser storage state
- `auth/session_storage.json`: session storage snapshot
- `auth/auth_metadata.json`: non-secret auth metadata
- `data/latest_results.json`: last captured result set
- `data/seen_item_ids.json`: historical seen IDs
- `others/`: debug screenshots and temporary artifacts

## Privacy and Publishing Notes

- Do not commit anything under `auth/`, `data/`, or `others/`.
- Do not publish your real nearby address in example commands or docs.
- Imported auth metadata stores only the source file name, not the absolute path.
- If you add local automation integrations, keep them in separate private docs.

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

Possible `skill-check` statuses:

- `initialized`
- `no_new_items`
- `new_items_found`
- `needs_login`
- `error`

## Testing

Run tests with the Python standard library test runner:

```bash
make test
```

Equivalent raw command:

```bash
python3 -m unittest discover -s tests -p 'test*.py' -q
```

The current tests cover small helper functions and JSON output behavior. They do
not cover the live browser workflow end to end.

## Known Limitations

- Goofish may change selectors or interaction flow at any time.
- The watcher runs in a visible browser because this flow is not reliable in headless mode.
- Nearby search logic still depends on brittle UI structure.
- `GOOFISH_SORT_MODE` currently affects baseline context tracking more than UI behavior.

## Migration Notes

If you used an older local-only version of this project:

- move hardcoded search values into environment variables
- stop relying on absolute local paths in documentation
- use `python3 -m goofish_rent env-check` before first run
- keep any private OpenClaw or local automation scripts outside this public repo
