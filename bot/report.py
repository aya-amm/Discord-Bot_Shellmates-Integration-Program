"""Formatting of the /sync-roles result for Discord. Issue #5 (summary, section 3.3).

Pure functions (no Discord objects) so they are easy to test.
"""
from __future__ import annotations

from bot.discord_ops import SyncReport

# Discord messages are limited to 2000 characters; stay safely below.
MAX_MESSAGE_LENGTH = 1900
# How many errors/warnings are listed inline before the rest goes in the attached file.
MAX_INLINE_ISSUES = 10


def _summary_lines(report: SyncReport, duration: float) -> list[str]:
    if report.dry_run:
        title = "**Dry run: no changes were applied**"
        added, removed = "Roles that would be added", "Roles that would be removed"
    else:
        title = "**Synchronization complete**"
        added, removed = "Roles added", "Roles removed"
    return [
        title,
        f"Members processed: {report.processed}",
        f"{added}: {report.roles_added}",
        f"{removed}: {report.roles_removed}",
        f"Unchanged: {report.unchanged}",
        f"Skipped (not found): {report.skipped}",
        f"Errors: {len(report.errors)}",
        f"Duration: {duration:.1f}s",
    ]


def build_response(report: SyncReport, duration: float) -> tuple[str, str | None]:
    """Return ``(message, details)``.

    ``message`` always fits in one Discord message. ``details`` is the full
    report as text when something had to be cut (to attach as a .txt file),
    otherwise ``None``.
    """
    lines = _summary_lines(report, duration)
    issues = [f"- {e}" for e in report.errors] + [f"- (warning) {w}" for w in report.warnings]

    truncated = len(issues) > MAX_INLINE_ISSUES
    if issues:
        lines.append("")
        lines.append("**Errors and warnings:**")
        lines.extend(issues[:MAX_INLINE_ISSUES])
        if truncated:
            lines.append(f"...and {len(issues) - MAX_INLINE_ISSUES} more (see attached file).")

    message = "\n".join(lines)
    if len(message) > MAX_MESSAGE_LENGTH:
        truncated = True
        message = message[: MAX_MESSAGE_LENGTH - 40].rstrip() + "\n...(truncated, see attached file)"

    return message, (format_details(report, duration) if truncated else None)


def format_details(report: SyncReport, duration: float) -> str:
    """Full plain-text report (summary, every change, every error and warning)."""
    lines = [line.replace("**", "") for line in _summary_lines(report, duration)]

    lines += ["", f"Changes ({len(report.changes)} member(s)):"]
    if report.changes:
        for change in report.changes:
            parts = []
            if change.added:
                parts.append("+ " + ", ".join(change.added))
            if change.removed:
                parts.append("- " + ", ".join(change.removed))
            lines.append(f"  {change.username}: {'  '.join(parts)}")
    else:
        lines.append("  (none)")

    lines += ["", f"Errors ({len(report.errors)}):"]
    lines += [f"  {e}" for e in report.errors] or ["  (none)"]
    lines += ["", f"Warnings ({len(report.warnings)}):"]
    lines += [f"  {w}" for w in report.warnings] or ["  (none)"]
    return "\n".join(lines) + "\n"
