from __future__ import annotations

from bot.discord_ops import SyncReport

# Limitations
MAX_MESSAGE_LENGTH = 1900
MAX_INLINE_ISSUES = 10
MAX_INLINE_CHANGES = 10


def _describe(change) -> str:
    """e.g. 'member1: +Developer -Designer'."""
    parts = [f"+{name}" for name in change.added] + [f"-{name}" for name in change.removed]
    return f"{change.username}: {' '.join(parts)}"


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
    # Return message, details 
    lines = _summary_lines(report, duration)
    issues = [f"- {e}" for e in report.errors] + [f"- (warning) {w}" for w in report.warnings]

    truncated = len(issues) > MAX_INLINE_ISSUES

    # A preview must show WHO would get WHAT so el HR can verify before applying.
    if report.dry_run and report.changes:
        lines.append("")
        lines.append("**Planned changes:**")
        lines.extend(f"- {_describe(c)}" for c in report.changes[:MAX_INLINE_CHANGES])
        if len(report.changes) > MAX_INLINE_CHANGES:
            truncated = True
            lines.append(f"...and {len(report.changes) - MAX_INLINE_CHANGES} more member(s) (see attached file).")

    if issues:
        lines.append("")
        lines.append("**Errors and warnings:**")
        lines.extend(issues[:MAX_INLINE_ISSUES])
        if len(issues) > MAX_INLINE_ISSUES:
            lines.append(f"...and {len(issues) - MAX_INLINE_ISSUES} more (see attached file).")

    if report.dry_run and report.changes:
        lines.append("")
        lines.append("Looks right? Run `/sync-roles` to apply these changes.")

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
