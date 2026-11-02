import asyncio
from types import SimpleNamespace

import discord
import pytest
from discord import app_commands

from bot import permissions
from bot.permissions import has_authorized_role, is_authorized


class FakeMember(discord.Member):
    """A real discord.Member subclass with settable roles/permissions """

    def __init__(self, role_names, admin):
        self._roles = [SimpleNamespace(name=n) for n in ("@everyone", *role_names)]
        self._admin = admin

    roles = property(lambda self: self._roles)
    guild_permissions = property(lambda self: SimpleNamespace(administrator=self._admin))


def member(role_names=(), admin=False):
    return FakeMember(role_names, admin)


def test_hr_role_is_authorized():
    assert has_authorized_role(member(["HR"]), ["HR"])


def test_role_match_ignores_case():
    assert has_authorized_role(member(["hr"]), ["HR"])


def test_administrator_is_authorized_without_role():
    assert has_authorized_role(member([], admin=True), ["HR"])


def test_other_roles_are_refused():
    assert not has_authorized_role(member(["Developer", "Moderator"]), ["HR"])


def test_no_roles_is_refused():
    assert not has_authorized_role(member([]), ["HR"])


def test_default_uses_config_authorized_roles(monkeypatch):
    monkeypatch.setattr(permissions.config, "AUTHORIZED_ROLES", ["Board"])
    assert has_authorized_role(member(["Board"]))
    assert not has_authorized_role(member(["HR"]))


def interaction(user, guild=object()):
    return SimpleNamespace(user=user, guild=guild)


def test_is_authorized_refuses_outside_a_server():
    assert not is_authorized(interaction(member(["HR"]), guild=None))


def test_is_authorized_refuses_non_member_user():
    assert not is_authorized(interaction(SimpleNamespace(), guild=object()))


def test_is_authorized_accepts_hr_member(monkeypatch):
    monkeypatch.setattr(permissions.config, "AUTHORIZED_ROLES", ["HR"])
    assert is_authorized(interaction(member(["HR"])))


def test_hr_only_check_raises_polite_refusal(monkeypatch):
    monkeypatch.setattr(permissions.config, "AUTHORIZED_ROLES", ["HR"])

    async def cmd(interaction):  # a dummy command body
        pass

    decorated = permissions.hr_only()(app_commands.Command(name="x", description="x", callback=cmd))
    check = decorated.checks[0]
    with pytest.raises(app_commands.CheckFailure):
        asyncio.run(check(interaction(member(["Developer"]))))
    assert asyncio.run(check(interaction(member(["HR"])))) is True
