"""Configuration: loads secrets and settings from the .env file."""
import os

from dotenv import load_dotenv

load_dotenv()


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


# --- Discord ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID") or 0)  # test/club server ID

# --- Google Sheets ---
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
SHEET_ID = os.getenv("SHEET_ID", "")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "")  # empty = first worksheet

# --- Role management ---
# Only these roles are ever added/removed by the sync. Anything else
# (Admin, Moderator, ...) is never touched.
MANAGED_ROLES = _split(os.getenv("MANAGED_ROLES", "Developer,Designer,HR"))

# Members with one of these roles (or Administrator permission) may run commands.
AUTHORIZED_ROLES = _split(os.getenv("AUTHORIZED_ROLES", "HR"))


def validate() -> None:
    """Fail fast with a clear message if required settings are missing."""
    required = {
        "DISCORD_TOKEN": DISCORD_TOKEN,
        "GUILD_ID": GUILD_ID,
        "SHEET_ID": SHEET_ID,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            f"Missing required settings in .env: {', '.join(missing)}. "
            "Copy .env.example to .env and fill it in."
        )
