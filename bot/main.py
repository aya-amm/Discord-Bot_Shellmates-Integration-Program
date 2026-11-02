import logging

import discord
from discord.ext import commands

from bot import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("hr-bot")

# setup intents
intents = discord.Intents.default()
intents.members = True


class HRBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await self.load_extension("bot.commands")
        # Sync commands
        guild = discord.Object(id=config.GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)


def main() -> None:
    HRBot().run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
