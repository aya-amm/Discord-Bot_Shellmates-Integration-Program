"""Discord-side operations: match sheet members to server members and apply role changes.

Issue #4. The pure add/remove computation lives in ``bot.sync``; this module
talks to Discord. ``sync_members`` is the entry point used by the
``/sync-roles`` command (issue #5) and returns a ``SyncReport`` that the
command can turn into the summary message.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import discord

from bot.sheets import normalize_username
from bot.sync import compute_changes

log = logging.getLogger("hr-bot.discord_ops")

# Small pause after each member that needed API calls, to stay well below
# Discord's rate limits. (discord.py also waits and retries on HTTP 429.)
DEFAULT_DELAY = 0.5


@dataclass
class RoleChange:
    """The role changes applied (or planned, in dry-run) for one member."""

    username: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


@dataclass
class SyncReport:
    """Everything the /sync-roles summary needs."""

    processed: int = 0  # sheet members handled (found in the server)
    roles_added: int = 0
    roles_removed: int = 0
    unchanged: int = 0  # found, but already up to date
    skipped: int = 0  # not found in the server
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    changes: list[RoleChange] = field(default_factory=list)
    dry_run: bool = False


# --------------------------------------------------------------------------- #
# Lookups
# --------------------------------------------------------------------------- #
def build_member_index(guild: discord.Guild) -> dict[str, discord.Member]:
    """Map normalized account usernames to members.

    Uses ``member.name`` (the unique username), NOT the display name or
    server nickname. Requires the Server Members Intent.
    """
    index: dict[str, discord.Member] = {}
    for member in guild.members:
        index.setdefault(normalize_username(member.name), member)
    return index


def find_member(index: dict[str, discord.Member], username: str) -> discord.Member | None:
    """Find a member by username, ignoring case, extra spaces and a leading '@'."""
    key = normalize_username(username)
    return index.get(key) if key else None


def build_role_index(guild: discord.Guild) -> dict[str, discord.Role]:
    """Map lower-cased role names to roles (the @everyone role is excluded)."""
    return {
        role.name.casefold(): role
        for role in guild.roles
        if not role.is_default()
    }


# --------------------------------------------------------------------------- #
# Role operations
# --------------------------------------------------------------------------- #
def check_assignable(role: discord.Role, bot_member: discord.Member) -> str | None:
    """Return an error message if the bot cannot add/remove ``role``, else None."""
    if role.managed:
        return f"Role '{role.name}' is managed by an integration and cannot be assigned."
    if role.position >= bot_member.top_role.position:
        return (
            f"Role '{role.name}' is higher than or equal to the bot's highest role "
            f"('{bot_member.top_role.name}'). Move the bot's role above the managed roles."
        )
    return None


async def apply_role_changes(
    member: discord.Member,
    to_add: list[discord.Role],
    to_remove: list[discord.Role],
    bot_member: discord.Member,
    *,
    reason: str,
    dry_run: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    """Add/remove roles on one member.

    Returns ``(added_names, removed_names, errors)``. A failure on one role
    group never raises: it is reported and the other group is still tried.
    In dry-run mode permissions are still checked but nothing is changed.
    """
    errors: list[str] = []
    who = member.name

    def usable(roles: list[discord.Role]) -> list[discord.Role]:
        ok = []
        for role in roles:
            problem = check_assignable(role, bot_member)
            if problem:
                errors.append(f"{who}: {problem}")
            else:
                ok.append(role)
        return ok

    adds, removes = usable(to_add), usable(to_remove)
    added: list[str] = []
    removed: list[str] = []

    if dry_run:
        return [r.name for r in adds], [r.name for r in removes], errors

    for action, roles, done in (
        ("add", adds, added),
        ("remove", removes, removed),
    ):
        if not roles:
            continue
        try:
            if action == "add":
                await member.add_roles(*roles, reason=reason)
            else:
                await member.remove_roles(*roles, reason=reason)
            done.extend(r.name for r in roles)
        except discord.Forbidden:
            errors.append(f"{who}: missing permission to {action} roles ({_names(roles)}).")
        except discord.HTTPException as exc:
            errors.append(f"{who}: Discord API error while trying to {action} roles ({_names(roles)}): {exc}")
    return added, removed, errors


def _names(roles: list[discord.Role]) -> str:
    return ", ".join(r.name for r in roles)


# --------------------------------------------------------------------------- #
# Full synchronization
# --------------------------------------------------------------------------- #
async def sync_members(
    guild: discord.Guild,
    sheet_members: list[dict],
    managed_role_names: list[str],
    *,
    dry_run: bool = False,
    actor: str = "bot",
    delay: float = DEFAULT_DELAY,
) -> SyncReport:
    """Synchronize ``guild`` members' managed roles with ``sheet_members``.

    ``sheet_members`` is the list returned by ``bot.sheets.load_members()``:
    ``[{"username": "member1", "roles": ["Developer", ...]}, ...]``.

    Members or roles that cannot be found, and permission / API errors, are
    skipped and reported; they never abort the whole run. Roles outside
    ``managed_role_names`` are never added or removed.
    """
    report = SyncReport(dry_run=dry_run)
    me = guild.me

    if me is None:
        report.errors.append("The bot is not a member of this server.")
        return report
    if not me.guild_permissions.manage_roles:
        report.errors.append("The bot is missing the 'Manage Roles' permission. No changes were made.")
        return report

    members = build_member_index(guild)
    roles = build_role_index(guild)

    # Managed roles that actually exist on Discord, keyed by their real name.
    managed_roles: dict[str, discord.Role] = {}
    for name in managed_role_names:
        role = roles.get(name.casefold())
        if role is None:
            report.errors.append(f"Managed role '{name}' does not exist on this server.")
        else:
            managed_roles[role.name] = role
    managed_names = set(managed_roles)

    missing_roles: dict[str, int] = {}  # sheet role name -> number of members referencing it
    unmanaged_roles: dict[str, int] = {}
    reason = f"HR role sync by {actor}"

    for entry in sheet_members:
        username = entry["username"]
        member = find_member(members, username)
        if member is None:
            report.skipped += 1
            report.errors.append(f"Member '{username}' was not found in the server (skipped).")
            continue

        # Resolve the sheet's role names to real Discord roles.
        wanted: set[str] = set()
        for role_name in entry.get("roles", []):
            role = roles.get(role_name.casefold())
            if role is None:
                missing_roles[role_name] = missing_roles.get(role_name, 0) + 1
            elif role.name not in managed_names:
                unmanaged_roles[role.name] = unmanaged_roles.get(role.name, 0) + 1
            else:
                wanted.add(role.name)

        current = {r.name for r in member.roles if not r.is_default()}
        add_names, remove_names = compute_changes(current, wanted, managed_names)
        report.processed += 1

        if not add_names and not remove_names:
            report.unchanged += 1
            continue

        added, removed, errors = await apply_role_changes(
            member,
            [managed_roles[n] for n in sorted(add_names)],
            [managed_roles[n] for n in sorted(remove_names)],
            me,
            reason=reason,
            dry_run=dry_run,
        )
        report.errors.extend(errors)
        if added or removed:
            report.roles_added += len(added)
            report.roles_removed += len(removed)
            report.changes.append(RoleChange(username, added, removed))
            log.info(
                "%s %s: +%s -%s",
                "Would update" if dry_run else "Updated",
                username, added, removed,
            )
        elif errors:
            pass  # everything for this member failed; already reported
        else:
            report.unchanged += 1

        if not dry_run and delay:
            await asyncio.sleep(delay)

    for name, count in sorted(missing_roles.items()):
        report.errors.append(
            f"Role '{name}' does not exist on Discord (used by {count} member(s)); that role was skipped."
        )
    for name, count in sorted(unmanaged_roles.items()):
        report.warnings.append(
            f"Role '{name}' is in the sheet but is not a managed role, so it was ignored "
            f"({count} member(s))."
        )
    return report
