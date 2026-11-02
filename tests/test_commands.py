import asyncio
from types import SimpleNamespace

import discord

from bot import commands as commands_module
from bot import sheets
from bot.commands import HRCommands
from bot.discord_ops import SyncReport
from bot.permissions import REFUSAL_MESSAGE


class FakeInteraction:
    def __init__(self):
        self.sent = []  
        self.deferred = False
        self.user = "hr#0001"
        self.guild = SimpleNamespace(chunked=True)
        self.response = SimpleNamespace(
            defer=self._defer, send_message=self._send, is_done=lambda: self.deferred or bool(self.sent)
        )
        self.followup = SimpleNamespace(send=self._send)

    async def _defer(self, **kwargs):
        self.deferred = True

    async def _send(self, text=None, **kwargs):
        self.sent.append((text, kwargs))


def test_sync_roles_command_is_registered_with_dry_run_option():
    cog = HRCommands(bot=None)
    commands = {c.name: c for c in cog.get_app_commands()}
    assert "sync-roles" in commands
    assert [p.name for p in commands["sync-roles"].parameters] == ["dry_run"]
    assert commands["sync-roles"].guild_only


def test_unreachable_sheet_gives_clear_error_and_no_changes(monkeypatch):
    def boom():
        raise sheets.SheetsReadError("Unable to access Google Sheets.")

    called = []

    async def fake_sync(*a, **k):
        called.append(1)

    monkeypatch.setattr(commands_module.sheets, "load_members", boom)
    monkeypatch.setattr(commands_module.discord_ops, "sync_members", fake_sync)

    inter = FakeInteraction()
    asyncio.run(HRCommands(bot=None)._run_sync(inter, dry_run=False))

    text, kwargs = inter.sent[-1]
    assert "Unable to access Google Sheets." in text and "No changes were applied" in text
    assert kwargs["ephemeral"] is True
    assert called == []  


def test_successful_sync_replies_ephemerally_with_summary(monkeypatch):
    monkeypatch.setattr(commands_module.sheets, "load_members", lambda: ([{"username": "a", "roles": []}], ["Row 3: Empty username."]))

    async def fake_sync(guild, members, managed, **kwargs):
        assert kwargs["dry_run"] is True and kwargs["actor"] == "hr#0001"
        return SyncReport(processed=1, roles_added=1, dry_run=True)

    monkeypatch.setattr(commands_module.discord_ops, "sync_members", fake_sync)

    inter = FakeInteraction()
    asyncio.run(HRCommands(bot=None)._run_sync(inter, dry_run=True))

    assert inter.deferred
    text, kwargs = inter.sent[-1]
    assert "Members processed: 1" in text
    assert "Row 3: Empty username." in text  # sheet errors are included
    assert kwargs["ephemeral"] is True


def test_second_sync_is_refused_while_one_is_running():
    cog = HRCommands(bot=None)

    async def scenario():
        await cog._sync_lock.acquire()
        inter = FakeInteraction()
        await cog._run_sync(inter, dry_run=False)
        return inter

    inter = asyncio.run(scenario())
    assert "already running" in inter.sent[0][0]


def test_check_failure_gets_polite_refusal():
    cog = HRCommands(bot=None)
    inter = FakeInteraction()
    asyncio.run(cog.cog_app_command_error(inter, discord.app_commands.CheckFailure("nope")))
    text, kwargs = inter.sent[0]
    assert text == REFUSAL_MESSAGE and kwargs["ephemeral"] is True


# preview-sync
def test_preview_sync_command_is_registered_with_no_options():
    cog = HRCommands(bot=None)
    commands = {c.name: c for c in cog.get_app_commands()}
    assert "preview-sync" in commands
    assert list(commands["preview-sync"].parameters) == []
    assert commands["preview-sync"].guild_only


def test_preview_sync_always_runs_a_dry_run(monkeypatch):
    seen = {}

    async def fake_run_sync(self, interaction, *, dry_run):
        seen["dry_run"] = dry_run

    monkeypatch.setattr(HRCommands, "_run_sync", fake_run_sync)
    cog = HRCommands(bot=None)
    asyncio.run(cog.preview_sync.callback(cog, FakeInteraction()))
    assert seen == {"dry_run": True}


def test_preview_sync_applies_nothing_end_to_end(monkeypatch):
    monkeypatch.setattr(commands_module.sheets, "load_members", lambda: ([{"username": "a", "roles": ["HR"]}], []))
    seen = {}

    async def fake_sync(guild, members, managed, **kwargs):
        seen.update(kwargs)
        return SyncReport(processed=1, dry_run=kwargs["dry_run"])

    monkeypatch.setattr(commands_module.discord_ops, "sync_members", fake_sync)
    cog = HRCommands(bot=None)
    inter = FakeInteraction()
    asyncio.run(cog.preview_sync.callback(cog, inter))
    assert seen["dry_run"] is True
    assert "no changes were applied" in inter.sent[-1][0]
