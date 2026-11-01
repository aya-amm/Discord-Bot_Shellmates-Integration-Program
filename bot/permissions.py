"""Authorization checks. Issue #6.

Only members with an authorized role (``config.AUTHORIZED_ROLES``) or the
Administrator permission may run the bot's commands.
"""
from __future__ import annotations

import discord
from discord import app_commands

from bot import config

REFUSAL_MESSAGE = (
    "Sorry, you are not allowed to use this command. "
    "It is reserved for HR members and administrators."
)


def has_authorized_role(member: discord.Member, authorized_roles: list[str] | None = None) -> bool:
    """True if ``member`` is an administrator or has one of ``authorized_roles``.

    Role names are compared ignoring case. Kept free of ``Interaction`` so it
    can be tested without a Discord server.
    """
    if member.guild_permissions.administrator:
        return True
    names = config.AUTHORIZED_ROLES if authorized_roles is None else authorized_roles
    allowed = {name.casefold() for name in names}
    return any(role.name.casefold() in allowed for role in member.roles)


def is_authorized(interaction: discord.Interaction) -> bool:
    """True if the user has an authorized role (config.AUTHORIZED_ROLES) or is an administrator."""
    member = interaction.user
    # In a DM (or if the member isn't cached) there are no roles to check.
    if interaction.guild is None or not isinstance(member, discord.Member):
        return False
    return has_authorized_role(member)


def hr_only():
    """Slash-command decorator: refuse anyone who is not HR / an administrator.

    Failures raise ``app_commands.CheckFailure``; the cog's error handler
    turns that into the polite ``REFUSAL_MESSAGE``.
    """

    async def predicate(interaction: discord.Interaction) -> bool:
        if not is_authorized(interaction):
            raise app_commands.CheckFailure(REFUSAL_MESSAGE)
        return True

    return app_commands.check(predicate)
