from unittest.mock import MagicMock

import pytest

from bot import sheets
from bot.sheets import SheetsReadError, load_members, normalize_username

HEADERS = ["DISCORD USERNAME", "ROLE"]


def fake_sheet(monkeypatch, records, headers=HEADERS):
    """Replace the Google client with a fake worksheet (no network, no credentials)."""
    worksheet = MagicMock()
    worksheet.row_values.return_value = headers
    worksheet.get_all_records.return_value = records
    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value = worksheet
    client = MagicMock()
    client.open_by_key.return_value = spreadsheet
    monkeypatch.setattr(sheets.gspread, "service_account", lambda filename: client)


def row(username, role):
    return {"DISCORD USERNAME": username, "ROLE": role}


# ---------- username normalization ----------

def test_normalize_ignores_case_spaces_and_leading_at():
    assert normalize_username("  @Member1 ") == "member1"
    assert normalize_username("MEMBER1") == "member1"


def test_normalize_empty_values():
    assert normalize_username("") == ""
    assert normalize_username(None) == ""
    assert normalize_username("@") == ""


# ---------- reading the sheet ----------

def test_valid_rows_are_returned_normalized(monkeypatch):
    fake_sheet(monkeypatch, [row("@Member1", "Developer"), row("member2", "Designer, Content")])
    members, errors = load_members()
    assert errors == []
    assert members == [
        {"username": "member1", "roles": ["Developer"]},
        {"username": "member2", "roles": ["Designer", "Content"]},
    ]


def test_empty_username_row_is_skipped_and_reported(monkeypatch):
    fake_sheet(monkeypatch, [row("member1", "HR"), row("   ", "Developer")])
    members, errors = load_members()
    assert [m["username"] for m in members] == ["member1"]
    assert len(errors) == 1 and "Row 3" in errors[0]


def test_duplicate_username_is_skipped_and_reported(monkeypatch):
    fake_sheet(monkeypatch, [row("member1", "HR"), row("@MEMBER1", "Developer"), row("member2", "HR")])
    members, errors = load_members()
    assert [m["username"] for m in members] == ["member2"]
    assert len(errors) == 1 and "2" in errors[0] and "3" in errors[0]


def test_empty_role_cell_gives_no_roles(monkeypatch):
    fake_sheet(monkeypatch, [row("member1", "")])
    members, _ = load_members()
    assert members == [{"username": "member1", "roles": []}]


def test_numeric_username_cell_is_handled(monkeypatch):
    fake_sheet(monkeypatch, [row(12345, "HR")])
    members, _ = load_members()
    assert members[0]["username"] == "12345"


# ---------- sheet errors: clear message ----------

def test_missing_columns_raises_clear_error(monkeypatch):
    fake_sheet(monkeypatch, [], headers=["Foo", "Bar"])
    with pytest.raises(SheetsReadError, match="Missing required columns"):
        load_members()


def test_unreachable_sheet_raises_clear_error(monkeypatch):
    def boom(filename):
        raise OSError("no credentials")

    monkeypatch.setattr(sheets.gspread, "service_account", boom)
    with pytest.raises(SheetsReadError, match="Unable to access"):
        load_members()
