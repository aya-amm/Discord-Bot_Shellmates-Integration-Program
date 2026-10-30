"""Authorization checks. Owner: issue #6."""
import discord


def is_authorized(interaction: discord.Interaction) -> bool:
    """True if the user has an authorized role (config.AUTHORIZED_ROLES) or is an administrator."""
    raise NotImplementedError
