"""Slash commands. Issue #5 adds /sync-roles here; #9, #11 add more."""
import discord
from discord import app_commands
from discord.ext import commands


class HRCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Check that the bot is alive")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Pong!", ephemeral=True)

    # TODO (#5): /sync-roles


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HRCommands(bot))
