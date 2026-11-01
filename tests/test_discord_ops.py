"""Tests for bot.discord_ops (issue #4), using small fakes instead of a real Discord server."""
import asyncio
from types import SimpleNamespace

import discord

from bot.discord_ops import (
    apply_role_changes,
    build_member_index,
    check_assignable,
    find_member,
    sync_members,
)


# ----------------------------- fakes ---------------------------------------
class FakeRole:
    def __init__(self, name, position=1, managed=False, default=False):
        self.name = name
        self.position = position
        self.managed = managed
        self._default = default

    def is_default(self):
        return self._default


class FakeMember:
    def __init__(self, name, roles=(), fail_with=None):
        self.name = name
        self.roles = [FakeRole("@everyone", 0, default=True), *roles]
        self.fail_with = fail_with
        self.calls = []  # ("add"/"remove", [role names])

    async def add_roles(self, *roles, reason=None):
        self.calls.append(("add", [r.name for r in roles]))
        if self.fail_with:
            raise self.fail_with
        self.roles.extend(roles)

    async def remove_roles(self, *roles, reason=None):
        self.calls.append(("remove", [r.name for r in roles]))
        if self.fail_with:
            raise self.fail_with
        self.roles = [r for r in self.roles if r not in roles]

    def role_names(self):
        return {r.name for r in self.roles if not r.is_default()}


def make_bot(top_position=10, manage_roles=True):
    top = FakeRole("Bot", top_position)
    return SimpleNamespace(
        name="hrbot",
        top_role=top,
        guild_permissions=SimpleNamespace(manage_roles=manage_roles),
    )


def make_guild(members, roles, bot=None):
    return SimpleNamespace(
        members=members,
        roles=[FakeRole("@everyone", 0, default=True), *roles],
        me=bot or make_bot(),
    )


def http_error(cls):
    return cls(SimpleNamespace(status=403 if cls is discord.Forbidden else 500, reason="x"), "boom")


def run(coro):
    return asyncio.run(coro)


DEV, DES, HR = FakeRole("Developer", 2), FakeRole("Designer", 3), FakeRole("HR", 4)
ADMIN = FakeRole("Admin", 5)
MANAGED = ["Developer", "Designer", "HR"]


# ----------------------------- member matching ------------------------------
def test_find_member_ignores_case_spaces_and_at_sign():
    alice = FakeMember("Alice_99")
    index = build_member_index(make_guild([alice], []))
    assert find_member(index, "  @ALICE_99 ") is alice
    assert find_member(index, "alice_99") is alice


def test_find_member_unknown_or_empty_returns_none():
    index = build_member_index(make_guild([FakeMember("alice")], []))
    assert find_member(index, "bob") is None
    assert find_member(index, "") is None
    assert find_member(index, "   @ ") is None


# ----------------------------- role changes ---------------------------------
def test_matching_member_gets_correct_changes():
    m = FakeMember("member1", [DES])
    guild = make_guild([m], [DEV, DES, HR])
    report = run(sync_members(guild, [{"username": "member1", "roles": ["Developer"]}], MANAGED, delay=0))
    assert m.role_names() == {"Developer"}
    assert (report.roles_added, report.roles_removed, report.processed) == (1, 1, 1)
    assert not report.errors


def test_unmanaged_roles_are_never_modified():
    m = FakeMember("member1", [ADMIN, DEV])
    guild = make_guild([m], [DEV, DES, HR, ADMIN])
    # The sheet asks for Admin (unmanaged) and no Developer.
    report = run(sync_members(guild, [{"username": "member1", "roles": ["Admin"]}], MANAGED, delay=0))
    assert m.role_names() == {"Admin"}  # Admin kept, not re-added; Developer removed
    assert all("Admin" not in names for _, names in m.calls)
    assert any("Admin" in w for w in report.warnings)


def test_role_name_matching_is_case_insensitive():
    m = FakeMember("member1")
    guild = make_guild([m], [DEV, DES, HR])
    run(sync_members(guild, [{"username": "member1", "roles": ["developer"]}], MANAGED, delay=0))
    assert m.role_names() == {"Developer"}


def test_multiple_roles_per_member():
    m = FakeMember("member1")
    guild = make_guild([m], [DEV, DES, HR])
    run(sync_members(guild, [{"username": "member1", "roles": ["Designer", "HR"]}], MANAGED, delay=0))
    assert m.role_names() == {"Designer", "HR"}


def test_already_up_to_date_counts_as_unchanged():
    m = FakeMember("member1", [DEV])
    guild = make_guild([m], [DEV, DES, HR])
    report = run(sync_members(guild, [{"username": "member1", "roles": ["Developer"]}], MANAGED, delay=0))
    assert m.calls == []
    assert (report.unchanged, report.roles_added, report.roles_removed) == (1, 0, 0)


# ----------------------------- missing members / roles ----------------------
def test_missing_member_is_skipped_and_reported_without_stopping_sync():
    m = FakeMember("member2")
    guild = make_guild([m], [DEV, DES, HR])
    sheet = [
        {"username": "ghost", "roles": ["Developer"]},
        {"username": "member2", "roles": ["Designer"]},
    ]
    report = run(sync_members(guild, sheet, MANAGED, delay=0))
    assert report.skipped == 1
    assert any("ghost" in e for e in report.errors)
    assert m.role_names() == {"Designer"}


def test_missing_role_is_skipped_and_reported_other_roles_still_applied():
    m = FakeMember("member1")
    guild = make_guild([m], [DEV, DES, HR])
    report = run(sync_members(guild, [{"username": "member1", "roles": ["Wizard", "Developer"]}], MANAGED, delay=0))
    assert m.role_names() == {"Developer"}
    assert any("Wizard" in e for e in report.errors)


def test_managed_role_missing_on_server_is_reported():
    m = FakeMember("member1")
    guild = make_guild([m], [DEV, DES])  # no HR role on the server
    report = run(sync_members(guild, [{"username": "member1", "roles": ["Developer"]}], MANAGED, delay=0))
    assert m.role_names() == {"Developer"}
    assert any("'HR'" in e for e in report.errors)


# ----------------------------- permissions / hierarchy ----------------------
def test_role_above_bot_reports_error_and_makes_no_api_call():
    m = FakeMember("member1")
    guild = make_guild([m], [DEV, DES, HR], bot=make_bot(top_position=3))  # Designer(3) not allowed
    report = run(sync_members(guild, [{"username": "member1", "roles": ["Designer"]}], MANAGED, delay=0))
    assert m.calls == []
    assert any("Designer" in e and "higher" in e for e in report.errors)
    assert report.roles_added == 0


def test_integration_managed_role_cannot_be_assigned():
    bot_role = FakeRole("BotIntegration", 1, managed=True)
    assert "integration" in check_assignable(bot_role, make_bot())


def test_missing_manage_roles_permission_aborts_with_no_changes():
    m = FakeMember("member1")
    guild = make_guild([m], [DEV, DES, HR], bot=make_bot(manage_roles=False))
    report = run(sync_members(guild, [{"username": "member1", "roles": ["Developer"]}], MANAGED, delay=0))
    assert m.calls == []
    assert any("Manage Roles" in e for e in report.errors)


# ----------------------------- Discord API errors ---------------------------
def test_forbidden_error_on_one_member_does_not_stop_the_sync():
    bad = FakeMember("bad", fail_with=http_error(discord.Forbidden))
    good = FakeMember("good")
    guild = make_guild([bad, good], [DEV, DES, HR])
    sheet = [
        {"username": "bad", "roles": ["Developer"]},
        {"username": "good", "roles": ["Developer"]},
    ]
    report = run(sync_members(guild, sheet, MANAGED, delay=0))
    assert good.role_names() == {"Developer"}
    assert bad.role_names() == set()
    assert report.roles_added == 1
    assert any("bad" in e and "permission" in e for e in report.errors)


def test_http_exception_is_reported_not_raised():
    m = FakeMember("member1", fail_with=http_error(discord.HTTPException))
    guild = make_guild([m], [DEV, DES, HR])
    report = run(sync_members(guild, [{"username": "member1", "roles": ["Developer"]}], MANAGED, delay=0))
    assert any("Discord API error" in e for e in report.errors)


def test_failed_add_still_attempts_removal():
    m = FakeMember("member1", [DES])
    guild = make_guild([m], [DEV, DES, HR])
    # Fail only on add.
    async def failing_add(*roles, reason=None):
        raise http_error(discord.Forbidden)
    m.add_roles = failing_add
    report = run(sync_members(guild, [{"username": "member1", "roles": ["Developer"]}], MANAGED, delay=0))
    assert m.role_names() == set()  # Designer removed even though Developer could not be added
    assert (report.roles_added, report.roles_removed) == (0, 1)


# ----------------------------- dry run --------------------------------------
def test_dry_run_reports_changes_but_applies_nothing():
    m = FakeMember("member1", [DES])
    guild = make_guild([m], [DEV, DES, HR])
    report = run(sync_members(guild, [{"username": "member1", "roles": ["Developer"]}], MANAGED, dry_run=True, delay=0))
    assert m.calls == []
    assert m.role_names() == {"Designer"}
    assert report.dry_run
    assert (report.roles_added, report.roles_removed) == (1, 1)
    assert report.changes[0].added == ["Developer"] and report.changes[0].removed == ["Designer"]


def test_apply_role_changes_dry_run_still_checks_hierarchy():
    m = FakeMember("member1")
    bot = make_bot(top_position=2)
    added, removed, errors = run(apply_role_changes(m, [DEV], [], bot, reason="t", dry_run=True))
    assert added == [] and errors  # Developer (2) is not below the bot's top role (2)
