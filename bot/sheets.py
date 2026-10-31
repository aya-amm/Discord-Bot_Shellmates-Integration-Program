import gspread
from bot import config


class SheetsReadError(Exception):
    pass


def normalize_username(username):
    if not username:
        return ""
    username = str(username).strip()
    if username.startswith("@"):
        username = username[1:].strip()
    return username.casefold()


def load_members():
    try:
        gc = gspread.service_account(
            filename=config.GOOGLE_CREDENTIALS_FILE)
        spreadsheet = gc.open_by_key(config.SHEET_ID)
        worksheet = spreadsheet.worksheet("Members")
        headers = worksheet.row_values(1)
        if not {"DISCORD USERNAME", "ROLE"}.issubset(headers):
            raise SheetsReadError("Missing required columns.")
        records = worksheet.get_all_records()
    except SheetsReadError:
        raise SheetsReadError("Missing required columns.")

    except Exception as exc:
        raise SheetsReadError( "Unable to access Google Sheets.") from exc

    grouped = {}
    errors = []

    for row_number, row in enumerate(records, start=2):

        username = normalize_username(
            row.get("DISCORD USERNAME")
        )

        if not username:
            errors.append(f"Row {row_number}: Empty username.")
            continue

        roles = [
            role.strip()
            for role in str(row.get("ROLE") or "").split(",")
            if role.strip()
        ]

        if username not in grouped:
            grouped[username] = []

        grouped[username].append({
            "row_number": row_number,
            "roles": roles
        })

    valid_members = []

    for username, rows in grouped.items():

        if len(rows) > 1:
            row_numbers = [
                str(row["row_number"]) for row in rows
            ]

            errors.append(
                f"Duplicate username '{username}' "f"in rows: {', '.join(row_numbers)}." )
            continue

        valid_members.append({
            "username": username,
            "roles": rows[0]["roles"]
        })

    return valid_members, errors