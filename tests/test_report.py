"""Tests for bot.report (issue #5 summary)."""
from bot.discord_ops import RoleChange, SyncReport
from bot.report import MAX_INLINE_ISSUES, MAX_MESSAGE_LENGTH, build_response


def test_summary_shows_required_numbers():
    report = SyncReport(processed=5, roles_added=3, roles_removed=2, unchanged=1, skipped=1)
    message, details = build_response(report, 1.234)
    assert "Members processed: 5" in message
    assert "Roles added: 3" in message
    assert "Roles removed: 2" in message
    assert "Unchanged: 1" in message
    assert "Skipped (not found): 1" in message
    assert "Duration: 1.2s" in message
    assert details is None


def test_errors_are_listed():
    report = SyncReport(errors=["Member 'ghost' was not found in the server (skipped)."])
    message, _ = build_response(report, 0)
    assert "Errors: 1" in message
    assert "ghost" in message


def test_dry_run_is_clearly_labelled():
    message, _ = build_response(SyncReport(dry_run=True, roles_added=2), 0)
    assert "no changes were applied" in message
    assert "would be added: 2" in message


def test_many_errors_are_truncated_and_full_details_attached():
    report = SyncReport(errors=[f"Member 'user{i}' was not found in the server (skipped)." for i in range(50)])
    message, details = build_response(report, 0)
    assert len(message) <= MAX_MESSAGE_LENGTH
    assert f"...and {50 - MAX_INLINE_ISSUES} more" in message
    assert details is not None
    assert "user49" in details  # nothing is lost in the attachment


def test_very_long_messages_are_cut_to_fit_discord_limit():
    report = SyncReport(errors=["x" * 500 for _ in range(MAX_INLINE_ISSUES)])
    message, details = build_response(report, 0)
    assert len(message) <= MAX_MESSAGE_LENGTH
    assert details is not None


def test_details_list_every_change():
    report = SyncReport(changes=[RoleChange("member1", ["Developer"], ["Designer"])])
    report.errors = [f"e{i}" for i in range(MAX_INLINE_ISSUES + 1)]
    _, details = build_response(report, 0)
    assert "member1" in details and "+ Developer" in details and "- Designer" in details
