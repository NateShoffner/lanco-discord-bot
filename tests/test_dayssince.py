"""DaysSince tracker tests.

The command callbacks, the modal, and the prefix listener are driven directly
against the in-memory database, since what is worth pinning is the tracker's
rules rather than Discord's plumbing: streak and record arithmetic, name
normalization, one name per guild (including across a rename), and that the
prefix listener only answers for the right guild, name, and channel.
"""

import datetime
from types import SimpleNamespace

import discord
import pytest
from cogs.dayssince.dayssince import (
    COMMAND_NAME_PATTERN,
    DaysSince,
    TrackerModal,
    get_record,
    get_streak,
    normalize_command_name,
)
from cogs.dayssince.models import DaysSinceTracker

from tests.test_bot import test_db  # noqa: F401  (fixture)

GUILD_ID = 1001
OTHER_GUILD_ID = 1002
CHANNEL_ID = 2001
PREFIX = "!"


class FakeResponse:
    def __init__(self):
        self.messages = []
        self.modal = None

    async def send_message(self, content=None, *, embed=None, ephemeral=False):
        self.messages.append(
            SimpleNamespace(content=content, embed=embed, ephemeral=ephemeral)
        )

    async def send_modal(self, modal):
        self.modal = modal


class FakeChannel:
    def __init__(self, channel_id):
        self.id = channel_id
        self.sent = []

    async def send(self, content=None, *, embed=None):
        self.sent.append(embed)
        return SimpleNamespace(id=len(self.sent))


def make_interaction(guild_id=GUILD_ID, user_id=42):
    return SimpleNamespace(
        guild_id=guild_id,
        guild=SimpleNamespace(id=guild_id),
        user=SimpleNamespace(id=user_id),
        client=SimpleNamespace(get_guild_prefix=lambda guild: PREFIX),
        response=FakeResponse(),
    )


def make_message(content, *, guild_id=GUILD_ID, channel_id=CHANNEL_ID, bot=False):
    return SimpleNamespace(
        content=content,
        author=SimpleNamespace(bot=bot, id=7),
        guild=None if guild_id is None else SimpleNamespace(id=guild_id),
        channel=FakeChannel(channel_id),
    )


def make_tracker(name="coffeespill", guild_id=GUILD_ID, **fields):
    values = {"title": "Office Coffee Machine", "event_label": "coffee spill"}
    values.update(fields)
    return DaysSinceTracker.create(guild_id=guild_id, command_name=name, **values)


def days_ago(days, hours=0):
    return datetime.datetime.now() - datetime.timedelta(days=days, hours=hours)


def fill(modal, *, name, title="Office Coffee Machine", event="coffee spill", total=""):
    # A real submit populates _value through _refresh_state. Setting .default
    # only changes what the form shows, so it cannot stand in for a submission.
    modal.command_name._value = name
    modal.tracker_title._value = title
    modal.event_label._value = event
    modal.total_count._value = total
    return modal


def select_channel(modal, channel_id):
    modal.channel_selection.component._values = (
        [SimpleNamespace(id=channel_id, mention=f"<#{channel_id}>")]
        if channel_id
        else []
    )
    return modal


def reload(tracker):
    return DaysSinceTracker.get_by_id(tracker.id)


@pytest.fixture(autouse=True)
def tables(test_db):
    test_db.create_tables([DaysSinceTracker])


@pytest.fixture
def cog(test_db):
    bot = SimpleNamespace(database=test_db, get_guild_prefix=lambda guild: PREFIX)
    return DaysSince(bot)


# ---------------------------------------------------------------------------
# Names and arithmetic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,normalized,valid",
    [
        ("coffeespill", "coffeespill", True),
        ("!Coffeespill", "coffeespill", True),
        ("  COFFEE_spill ", "coffee_spill", True),
        ("ok-name", "ok-name", True),
        ("bad name", "bad name", False),
        ("", "", False),
        ("a" * 33, "a" * 33, False),
    ],
)
def test_normalize_and_validate_command_name(raw, normalized, valid):
    assert normalize_command_name(raw) == normalized
    assert bool(COMMAND_NAME_PATTERN.match(normalized)) is valid


def test_streak_is_none_until_something_happens():
    tracker = make_tracker(record_days=5)
    assert get_streak(tracker) is None
    assert get_record(tracker) == 5


@pytest.mark.parametrize(
    "when,expected",
    [(days_ago(12, hours=3), 12), (days_ago(1, hours=1), 1), (days_ago(0, 23), 0)],
)
def test_streak_counts_whole_days(when, expected):
    assert get_streak(make_tracker(last_event_at=when)) == expected


def test_record_includes_a_running_streak():
    assert (
        get_record(make_tracker("a", last_event_at=days_ago(12), record_days=5)) == 12
    )
    assert (
        get_record(make_tracker("b", last_event_at=days_ago(12), record_days=50)) == 50
    )


def test_status_embed_wording_and_color(cog):
    fresh = cog.build_status_embed(make_tracker("fresh"))
    assert fresh.description == "No coffee spill recorded yet."
    assert "Last occurrence" not in [f.name for f in fresh.fields]

    today = cog.build_status_embed(make_tracker("today", last_event_at=days_ago(0, 2)))
    assert today.description == "**0 days** since the last coffee spill."
    assert today.color == discord.Color.red()

    one = cog.build_status_embed(make_tracker("one", last_event_at=days_ago(1, 1)))
    assert one.description == "**1 day** since the last coffee spill."
    assert one.color == discord.Color.orange()

    long = cog.build_status_embed(
        make_tracker("long", last_event_at=days_ago(30), total_count=4, record_days=9)
    )
    assert long.color == discord.Color.green()
    fields = {f.name: f.value for f in long.fields}
    assert fields["Total"] == "4"
    assert fields["Record"] == "30 days"
    assert fields["Last occurrence"].startswith("<t:")


# ---------------------------------------------------------------------------
# Modal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modal_creates_a_tracker():
    interaction = make_interaction()
    modal = fill(
        TrackerModal(), name="!CoffeeSpill", title="  Tank  ", event=" coffee spill "
    )
    await modal.on_submit(interaction)

    tracker = DaysSinceTracker.get(guild_id=GUILD_ID)
    assert tracker.command_name == "coffeespill"
    assert tracker.title == "Tank"
    assert tracker.event_label == "coffee spill"
    assert tracker.channel_id is None
    assert tracker.author == 42

    reply = interaction.response.messages[-1]
    assert reply.ephemeral
    assert reply.embed.title == "Tracker Created"
    assert {f.name: f.value for f in reply.embed.fields}["Command"] == "!coffeespill"


@pytest.mark.asyncio
async def test_modal_seeds_the_total():
    interaction = make_interaction()
    await fill(TrackerModal(), name="coffeespill", total="47").on_submit(interaction)

    assert DaysSinceTracker.get(guild_id=GUILD_ID).total_count == 47
    fields = {f.name: f.value for f in interaction.response.messages[-1].embed.fields}
    assert fields["Total"] == "47"


@pytest.mark.asyncio
async def test_modal_defaults_the_total_to_zero():
    interaction = make_interaction()
    await fill(TrackerModal(), name="coffeespill").on_submit(interaction)

    assert DaysSinceTracker.get(guild_id=GUILD_ID).total_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["-1", "1.5", "abc", "1234567890", "4 7"])
async def test_modal_rejects_a_bad_total(bad):
    interaction = make_interaction()
    await fill(TrackerModal(), name="coffeespill", total=bad).on_submit(interaction)

    assert DaysSinceTracker.select().count() == 0
    reply = interaction.response.messages[-1]
    assert reply.ephemeral
    assert "Total must be" in reply.content


@pytest.mark.asyncio
async def test_modal_corrects_the_total_on_edit():
    tracker = make_tracker(total_count=37)
    interaction = make_interaction()
    modal = fill(TrackerModal(tracker=tracker), name="coffeespill", total="40")
    await modal.on_submit(interaction)

    assert reload(tracker).total_count == 40


@pytest.mark.asyncio
async def test_a_cleared_total_keeps_the_running_count():
    # The field is prefilled on edit, so a blank submission must not read as a
    # reset: an edit to fix a typo would otherwise wipe the history.
    tracker = make_tracker(total_count=37)
    interaction = make_interaction()
    modal = fill(TrackerModal(tracker=tracker), name="coffeespill", total="")
    await modal.on_submit(interaction)

    assert reload(tracker).total_count == 37


@pytest.mark.asyncio
async def test_modal_rejects_an_invalid_name():
    interaction = make_interaction()
    await fill(TrackerModal(), name="bad name").on_submit(interaction)

    assert DaysSinceTracker.select().count() == 0
    reply = interaction.response.messages[-1]
    assert reply.ephemeral
    assert "Command names must be" in reply.content


@pytest.mark.asyncio
async def test_modal_rejects_a_duplicate_name_in_the_same_guild():
    make_tracker()
    interaction = make_interaction()
    await fill(TrackerModal(), name="coffeespill").on_submit(interaction)

    assert DaysSinceTracker.select().count() == 1
    assert "already exists" in interaction.response.messages[-1].content


@pytest.mark.asyncio
async def test_the_same_name_is_allowed_in_another_guild():
    make_tracker()
    interaction = make_interaction(guild_id=OTHER_GUILD_ID)
    await fill(TrackerModal(), name="coffeespill").on_submit(interaction)

    assert DaysSinceTracker.select().count() == 2


@pytest.mark.asyncio
async def test_edit_prefills_the_modal(cog):
    make_tracker(channel_id=CHANNEL_ID, total_count=37)
    interaction = make_interaction()
    await DaysSince.edit.callback(cog, interaction, "coffeespill")

    modal = interaction.response.modal
    assert isinstance(modal, TrackerModal)
    assert modal.command_name.default == "coffeespill"
    assert modal.tracker_title.default == "Office Coffee Machine"
    assert modal.event_label.default == "coffee spill"
    assert modal.total_count.default == "37"
    assert [v.id for v in modal.channel_selection.component.default_values] == [
        CHANNEL_ID
    ]


@pytest.mark.asyncio
async def test_rename_updates_the_row_in_place():
    tracker = make_tracker(total_count=37, last_event_at=days_ago(12))
    interaction = make_interaction()
    await fill(TrackerModal(tracker=tracker), name="burntoast").on_submit(interaction)

    assert DaysSinceTracker.select().count() == 1
    renamed = reload(tracker)
    assert renamed.command_name == "burntoast"
    # Counters belong to the tracker, not the name, so a rename keeps them.
    assert renamed.total_count == 37
    assert get_streak(renamed) == 12
    assert interaction.response.messages[-1].embed.title == "Tracker Updated"


@pytest.mark.asyncio
async def test_rename_onto_an_existing_name_is_rejected():
    first = make_tracker("first")
    make_tracker("second")
    interaction = make_interaction()
    await fill(TrackerModal(tracker=first), name="second").on_submit(interaction)

    assert reload(first).command_name == "first"
    assert "already exists" in interaction.response.messages[-1].content


@pytest.mark.asyncio
async def test_editing_without_renaming_is_not_a_collision():
    tracker = make_tracker()
    interaction = make_interaction()
    modal = fill(TrackerModal(tracker=tracker), name="coffeespill", title="New Title")
    await modal.on_submit(interaction)

    assert reload(tracker).title == "New Title"
    assert interaction.response.messages[-1].embed.title == "Tracker Updated"


@pytest.mark.asyncio
async def test_channel_restriction_is_saved_and_cleared():
    interaction = make_interaction()
    modal = select_channel(fill(TrackerModal(), name="coffeespill"), CHANNEL_ID)
    await modal.on_submit(interaction)
    tracker = DaysSinceTracker.get(guild_id=GUILD_ID)
    assert tracker.channel_id == CHANNEL_ID

    modal = select_channel(
        fill(TrackerModal(tracker=tracker), name="coffeespill"), None
    )
    await modal.on_submit(make_interaction())
    assert reload(tracker).channel_id is None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incident_resets_the_streak_and_promotes_the_record(cog):
    tracker = make_tracker(last_event_at=days_ago(12), record_days=5, total_count=37)
    interaction = make_interaction()
    await DaysSince.incident.callback(cog, interaction, "coffeespill")

    updated = reload(tracker)
    assert updated.total_count == 38
    assert updated.record_days == 12
    assert get_streak(updated) == 0

    reply = interaction.response.messages[-1]
    assert not reply.ephemeral
    assert "**12 days**" in reply.embed.description
    assert "new record" in reply.embed.description
    assert "Total: **38**" in reply.embed.description


@pytest.mark.asyncio
async def test_incident_on_a_short_streak_keeps_the_record(cog):
    tracker = make_tracker(last_event_at=days_ago(3), record_days=30)
    interaction = make_interaction()
    await DaysSince.incident.callback(cog, interaction, "coffeespill")

    assert reload(tracker).record_days == 30
    assert "new record" not in interaction.response.messages[-1].embed.description


@pytest.mark.asyncio
async def test_first_incident_has_no_previous_streak(cog):
    tracker = make_tracker()
    interaction = make_interaction()
    await DaysSince.incident.callback(cog, interaction, "coffeespill")

    updated = reload(tracker)
    assert updated.total_count == 1
    assert updated.record_days == 0
    assert "previous streak" not in interaction.response.messages[-1].embed.description


@pytest.mark.asyncio
async def test_commands_accept_a_prefixed_mixed_case_name(cog):
    tracker = make_tracker()
    await DaysSince.incident.callback(cog, make_interaction(), "!CoffeeSpill")
    assert reload(tracker).total_count == 1


@pytest.mark.asyncio
async def test_set_backdates_and_overrides(cog):
    tracker = make_tracker()
    interaction = make_interaction()
    await DaysSince.set_values.callback(
        cog, interaction, "coffeespill", days=4, total=9, record=20
    )

    updated = reload(tracker)
    assert get_streak(updated) == 4
    assert updated.total_count == 9
    assert updated.record_days == 20
    assert interaction.response.messages[-1].ephemeral


@pytest.mark.asyncio
async def test_set_with_nothing_to_set_changes_nothing(cog):
    tracker = make_tracker(total_count=3)
    interaction = make_interaction()
    await DaysSince.set_values.callback(cog, interaction, "coffeespill")

    assert reload(tracker).total_count == 3
    assert "at least one of" in interaction.response.messages[-1].content


@pytest.mark.asyncio
async def test_delete_removes_the_tracker(cog):
    make_tracker()
    interaction = make_interaction()
    await DaysSince.delete.callback(cog, interaction, "coffeespill")

    assert DaysSinceTracker.select().count() == 0
    assert interaction.response.messages[-1].ephemeral


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command,extra",
    [("edit", {}), ("delete", {}), ("incident", {}), ("set_values", {"days": 1})],
)
async def test_an_unknown_tracker_is_reported(cog, command, extra):
    interaction = make_interaction()
    await getattr(DaysSince, command).callback(cog, interaction, "nope", **extra)

    reply = interaction.response.messages[-1]
    assert reply.ephemeral
    assert "No tracker named `nope`" in reply.content
    assert interaction.response.modal is None


@pytest.mark.asyncio
async def test_a_tracker_in_another_guild_is_out_of_reach(cog):
    make_tracker(guild_id=OTHER_GUILD_ID)
    interaction = make_interaction()
    await DaysSince.delete.callback(cog, interaction, "coffeespill")

    assert DaysSinceTracker.select().count() == 1
    assert "No tracker named" in interaction.response.messages[-1].content


@pytest.mark.asyncio
async def test_list_with_no_trackers(cog):
    interaction = make_interaction()
    await DaysSince.list_trackers.callback(cog, interaction)

    reply = interaction.response.messages[-1]
    assert reply.ephemeral
    assert "No trackers yet" in reply.content


@pytest.mark.asyncio
async def test_list_shows_only_this_guild_sorted(cog):
    make_tracker("coffeespill", last_event_at=days_ago(3), total_count=2)
    make_tracker("burntoast", channel_id=CHANNEL_ID)
    make_tracker("elsewhere", guild_id=OTHER_GUILD_ID)
    interaction = make_interaction()
    await DaysSince.list_trackers.callback(cog, interaction)

    embed = interaction.response.messages[-1].embed
    assert [f.name for f in embed.fields] == ["!burntoast", "!coffeespill"]
    burntoast, coffeespill = (f.value for f in embed.fields)
    assert "Nothing recorded yet" in burntoast
    assert f"Only in <#{CHANNEL_ID}>" in burntoast
    assert "3 days since the last coffee spill" in coffeespill
    assert "total 2" in coffeespill


# ---------------------------------------------------------------------------
# Autocomplete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_autocomplete_filters_by_guild_and_substring(cog):
    make_tracker("coffeespill")
    make_tracker("burntoast")
    make_tracker("coffeepot", guild_id=OTHER_GUILD_ID)
    interaction = make_interaction()

    matches = await cog.tracker_autocomplete(interaction, "COF")
    assert [c.value for c in matches] == ["coffeespill"]

    everything = await cog.tracker_autocomplete(interaction, "")
    assert [c.value for c in everything] == ["burntoast", "coffeespill"]


@pytest.mark.parametrize("command", ["edit", "delete", "incident", "set_values"])
def test_autocomplete_is_wired_to_every_name_parameter(command):
    assert getattr(DaysSince, command)._params["name"].autocomplete is not None


# ---------------------------------------------------------------------------
# Prefix listener
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content,message_kwargs,restrict_to,answers",
    [
        pytest.param("!coffeespill", {}, None, True, id="exact"),
        pytest.param("!COFFEESPILL  ", {}, None, True, id="case-and-whitespace"),
        pytest.param("coffeespill", {}, None, False, id="no-prefix"),
        pytest.param("!", {}, None, False, id="prefix-only"),
        pytest.param("!coffeespill now", {}, None, False, id="trailing-words"),
        pytest.param("!unknown", {}, None, False, id="unknown-name"),
        pytest.param("!coffeespill", {"bot": True}, None, False, id="bot-author"),
        pytest.param("!coffeespill", {"guild_id": None}, None, False, id="dm"),
        pytest.param(
            "!coffeespill", {"guild_id": OTHER_GUILD_ID}, None, False, id="other-guild"
        ),
        pytest.param(
            "!coffeespill", {"channel_id": 9999}, CHANNEL_ID, False, id="wrong-channel"
        ),
        pytest.param("!coffeespill", {}, CHANNEL_ID, True, id="allowed-channel"),
    ],
)
async def test_prefix_listener(cog, content, message_kwargs, restrict_to, answers):
    make_tracker(channel_id=restrict_to)
    message = make_message(content, **message_kwargs)
    result = await cog.on_message(message)

    if answers:
        assert len(message.channel.sent) == 1
        assert message.channel.sent[0].title == "Office Coffee Machine"
        assert result is not None
    else:
        assert message.channel.sent == []
        assert result is None
