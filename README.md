# Discord HR Role Management Bot

Synchronizes Discord roles with a Google Sheet (Shellmates Club).

## Setup

1. `python -m venv .venv` then activate it
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in the values
4. In the Discord Developer Portal, enable **Server Members Intent** (Bot tab -> Privileged Gateway Intents)
5. Place the Google service-account JSON at the path set in `GOOGLE_CREDENTIALS_FILE`
   and share the sheet with the service account's email
6. Run: `python -m bot.main`

## Tests

`python -m pytest`

_(Full documentation: issue #8)_
