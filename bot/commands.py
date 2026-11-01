"""Slash commands. Issue #5 adds /sync-roles here; #9, #11 add more."""
import asyncio
import io
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands

from bot import config, discord_ops, sheets
from bot.permissions import REFUSAL_MESSAGE, hr_only
from bot.report import build_response

log = logging.getLogger("hr-bot.commands")


class HRCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Simple lock: only one synchronization at a time.
        self._sync_lock = asyncio.Lock()

    @app_commands.command(name="ping", description="Check that the bot is alive")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Pong!", ephemeral=True)

    @app_commands.command(
        name="sync-roles",
        description="Synchronize members' Discord roles with the Google Sheet",
    )
    @app_commands.describe(dry_run="Only show what would change, without applying anything")
    @app_commands.guild_only()
    @hr_only()
    async def sync_roles(self, interaction: discord.Interaction, dry_run: bool = False) -> None:
        await self._run_sync(interaction, dry_run=dry_run)

    async def _run_sync(self, interaction: discord.Interaction, *, dry_run: bool) -> None:
        """Shared by /sync-roles (and later /preview-sync, issue #9)."""
        if self._sync_lock.locked():
            await interaction.response.send_message(
                "A synchronization is already running. Please wait for it to finish.",
                ephemeral=True,
            )
            return

        async with self._sync_lock:
            # A full sync can take longer than Discord's 3-second limit.
            await interaction.response.defer(ephemeral=True, thinking=True)
            started = time.monotonic()

            try:
                # gspread is blocking: run it in a thread so the bot stays responsive.
                sheet_members, sheet_errors = await asyncio.to_thread(sheets.load_members)
            except sheets.SheetsReadError as exc:
                log.warning("Sheet read failed: %s", exc)
                await interaction.followup.send(
                    f"Could not read the Google Sheet: {exc} No changes were applied.",
                    ephemeral=True,
                )
                return

            guild = interaction.guild
            if not guild.chunked:
                await guild.chunk()  # make sure the full member list is cached

            report = await discord_ops.sync_members(
                guild,
                sheet_members,
                config.MANAGED_ROLES,
                dry_run=dry_run,
                actor=str(interaction.user),
            )
            report.errors[:0] = sheet_errors  # sheet problems (empty/duplicate rows) first

            message, details = build_response(report, time.monotonic() - started)
            kwargs = {}
            if details is not None:
                kwargs["file"] = discord.File(io.BytesIO(details.encode("utf-8")), filename="sync-report.txt")
            # Ephemeral: the report contains member details.
            await interaction.followup.send(message, ephemeral=True, **kwargs)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            text = REFUSAL_MESSAGE  # polite refusal (also covers use outside a server)
        else:
            log.exception("Unhandled error in command", exc_info=error)
            text = "Something went wrong while running this command. Please try again or contact an admin."
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HRCommands(bot))
