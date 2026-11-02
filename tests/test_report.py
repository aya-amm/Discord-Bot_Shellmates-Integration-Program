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


# preview 
def test_preview_lists_who_gets_what():
    report = SyncReport(
        dry_run=True,
        roles_added=2,
        roles_removed=1,
        changes=[
            RoleChange("member1", ["Developer"], ["Designer"]),
            RoleChange("member2", ["HR"], []),
        ],
    )
    message, details = build_response(report, 0)
    assert "Planned changes" in message
    assert "member1: +Developer -Designer" in message
    assert "member2: +HR" in message
    assert "/sync-roles" in message  
    assert details is None


def test_real_sync_does_not_use_preview_wording():
    report = SyncReport(changes=[RoleChange("member1", ["Developer"], [])], roles_added=1)
    message, _ = build_response(report, 0)
    assert "Planned changes" not in message
    assert "Run `/sync-roles`" not in message


def test_preview_with_nothing_to_change_has_no_apply_hint():
    message, _ = build_response(SyncReport(dry_run=True, unchanged=3), 0)
    assert "Planned changes" not in message
    assert "Run `/sync-roles`" not in message


def test_long_preview_is_truncated_and_full_list_attached():
    changes = [RoleChange(f"user{i}", ["Developer"], []) for i in range(40)]
    report = SyncReport(dry_run=True, roles_added=40, changes=changes)
    message, details = build_response(report, 0)
    assert len(message) <= MAX_MESSAGE_LENGTH
    assert "...and 30 more member(s)" in message
    assert "(see attached file)" in message
    assert "...and -" not in message  # no bogus negative counts for errors
    assert details is not None and "user39: + Developer" in details
