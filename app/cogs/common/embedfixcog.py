import asyncio
import re

import discord
from cachetools import LRUCache
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from tortoise import fields
from tortoise.exceptions import IntegrityError
from tortoise.models import Model


class _HandlerSelect(discord.ui.Select):
    def __init__(self, cog: "EmbedFixCog", guild_id: int, active_id: str):
        self._cog = cog
        self._guild_id = guild_id
        options = [
            discord.SelectOption(
                label=h.name,
                description=h.description[:100],
                value=h.id,
                default=(h.id == active_id),
            )
            for h in cog.handlers
        ]
        super().__init__(placeholder="Select a handler…", options=options)

    async def callback(self, interaction: discord.Interaction):
        handler_id = self.values[0]
        handler = next(h for h in self._cog.handlers if h.id == handler_id)

        try:
            config, _ = await self._cog.config_model.get_or_create(
                guild_id=self._guild_id
            )
        except IntegrityError:
            # Kept post-Tortoise: get_or_create is still a non-atomic
            # SELECT-then-INSERT, so two concurrent invocations can still race.
            config = await self._cog.config_model.get_or_none(guild_id=self._guild_id)
        config.handler_id = handler_id
        await config.save()

        await interaction.response.edit_message(
            content=f"Handler set to **{handler.name}** — {handler.description}.",
            view=None,
        )


class _HandlerSelectView(discord.ui.View):
    def __init__(
        self, cog: "EmbedFixCog", guild_id: int, active_id: str, invoker_id: int
    ):
        super().__init__(timeout=60)
        self._invoker_id = invoker_id
        self.add_item(_HandlerSelect(cog, guild_id, active_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._invoker_id:
            await interaction.response.send_message(
                "Only the person who ran this command can use this menu.",
                ephemeral=True,
            )
            return False
        return True


class EmbedFixConfigBase(Model):
    """Columns shared by every embed-fix config table.

    handler_id is VARCHAR(255) to match what already exists in the database
    (Peewee's bare CharField); widening or narrowing it would only produce a
    pointless ALTER against live tables.
    """

    enabled = fields.BooleanField(default=False)
    handler_id = fields.CharField(max_length=255, default="")

    class Meta:
        abstract = True


class GuildPkEmbedFixConfig(EmbedFixConfigBase):
    """Tables whose primary key IS the guild id."""

    guild_id = fields.BigIntField(primary_key=True, generated=False)

    class Meta:
        abstract = True


class SurrogatePkEmbedFixConfig(EmbedFixConfigBase):
    """Tables carrying a surrogate `id` PK with guild_id merely UNIQUE.

    Not a design choice -- it is what instaembed/tiktokembed/twitterembed
    actually look like in the live database. They predate the switch to
    guild-id-as-primary-key and were renamed (migrations 001-003) rather than
    rebuilt, and Peewee's CREATE TABLE IF NOT EXISTS never reshapes an existing
    table, so the model and the table have simply disagreed ever since.

    Behaviourally identical for this cog's purposes: guild_id carries a UNIQUE
    index, and every query here addresses rows by guild_id, never by pk.
    Modelling the table as it really is keeps the Aerich baseline honest
    instead of provoking a table rebuild for no functional gain.
    """

    id = fields.IntField(primary_key=True)
    guild_id = fields.BigIntField(unique=True)

    class Meta:
        abstract = True


class EmbedFixCog(LancoCog, name="EmbedFixCog", description="Abstract embed fix cog"):
    """Abstract class for fixing embeds to be extended by other cogs"""

    class PatternReplacement:
        """A URL pattern and its domain replacement"""

        def __init__(self, pattern: re.Pattern, original: str, replacement: str):
            self.pattern = pattern
            self.original = original
            self.replacement = replacement

    class Handler:
        """A named embed-fix handler with its own set of pattern replacements"""

        def __init__(
            self,
            id: str,
            name: str,
            description: str,
            patterns: list,
        ):
            self.id = id
            self.name = name
            self.description = description
            self.patterns = patterns

    @staticmethod
    def _is_within_angle_brackets(content: str, match: re.Match) -> bool:
        """Return True when a URL match is wrapped as <url> to suppress embeds."""
        start, end = match.span()
        if start == 0 or content[start - 1] != "<":
            return False

        # Some regex patterns include the trailing '>' in the match (e.g. via \S+).
        if end > start and content[end - 1] == ">":
            return True

        return end < len(content) and content[end] == ">"

    @staticmethod
    def _is_within_spoiler_tags(content: str, match: re.Match) -> bool:
        """Return True when the matched URL is inside a ||spoiler|| segment."""
        match_start, match_end = match.span()
        search_index = 0

        while True:
            spoiler_start = content.find("||", search_index)
            if spoiler_start == -1:
                return False

            spoiler_end = content.find("||", spoiler_start + 2)
            if spoiler_end == -1:
                return False

            # Match can include the closing spoiler marker for broad patterns like \S+.
            if match_start >= spoiler_start + 2 and match_end <= spoiler_end + 2:
                return True

            search_index = spoiler_end + 2

    def __init__(
        self,
        bot: commands.Bot,
        name: str,
        handlers: list,
        config_model: type[Model],
        skip_if_handled_by_discord: bool = False,
        wait_time: float = 2.5,
    ):
        super().__init__(bot)
        self.name = name
        self.handlers = handlers
        self.config_model = config_model
        self.skip_if_handled_by_discord = skip_if_handled_by_discord
        self.wait_time = wait_time
        # No create_tables() here: Tortoise generates the schema centrally at
        # startup (see main.init_tortoise), so every model must be registered
        # in app/models.py rather than created ad hoc per cog.
        self.fixed_messages = LRUCache(maxsize=1000)  # message_id -> fixed_message_id

    def _active_handler(self, config) -> "EmbedFixCog.Handler":
        """Return the configured Handler for this guild, falling back to the first."""
        if config and config.handler_id:
            for h in self.handlers:
                if h.id == config.handler_id:
                    return h
        return self.handlers[0]

    async def toggle(self, interaction: discord.Interaction):
        try:
            config, created = await self.config_model.get_or_create(
                guild_id=interaction.guild.id
            )
        except IntegrityError:
            # Kept post-Tortoise: see _HandlerSelect.callback above.
            config = await self.config_model.get_or_none(guild_id=interaction.guild.id)
            created = False

        if created or not config.enabled:
            config.enabled = True
            await config.save()
            await interaction.response.send_message(
                f"{self.name} enabled for this server"
            )
        else:
            config.enabled = False
            await config.save()
            await interaction.response.send_message(
                f"{self.name} disabled for this server"
            )

    async def _show_handler_select(self, interaction: discord.Interaction):
        config = await self.config_model.get_or_none(guild_id=interaction.guild.id)
        active = self._active_handler(config)

        if len(self.handlers) == 1:
            await interaction.response.send_message(
                f"**{self.name}** — current handler: **{active.name}** ({active.description})\n"
                "*No alternative handlers are configured.*"
            )
            return

        view = _HandlerSelectView(
            self, interaction.guild.id, active.id, interaction.user.id
        )
        await interaction.response.send_message(
            f"**{self.name}** — current handler: **{active.name}**\nSelect a handler to switch:",
            view=view,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.guild:
            return

        if not message.channel.permissions_for(message.guild.me).embed_links:
            return

        # Detect using the first handler's patterns (all handlers share the same
        # regex shapes — only the replacement domain differs between handlers).
        matched_idx = None
        original_url = None

        for i, pr in enumerate(self.handlers[0].patterns):
            match = pr.pattern.search(message.content)
            if match:
                if self._is_within_angle_brackets(message.content, match):
                    self.logger.info("URL is within angle brackets, ignoring")
                    return

                if self._is_within_spoiler_tags(message.content, match):
                    self.logger.info("URL is within spoiler tags, ignoring")
                    return

                original_url = match.group(0)
                matched_idx = i
                break

        if matched_idx is None:
            return

        self.logger.info(
            f"Found URL matching pattern for {self.name}: {original_url} - waiting {self.wait_time}s"
        )

        await asyncio.sleep(self.wait_time)

        # re-fetch the message to get the latest content
        message = await message.channel.fetch_message(message.id)
        if message.embeds and self.skip_if_handled_by_discord:
            self.logger.info("Discord embedded the link, no need to fix it")
            return

        embed_config = await self.config_model.get_or_none(guild_id=message.guild.id)
        if not embed_config or not embed_config.enabled:
            self.logger.info("Embed fix not enabled for this server")
            return

        active = self._active_handler(embed_config)
        pr = active.patterns[min(matched_idx, len(active.patterns) - 1)]
        fixed_url = original_url.replace(pr.original, pr.replacement)

        self.logger.info(
            f"Fixing URL with handler '{active.id}': {original_url} -> {fixed_url}"
        )

        fixed_msg = await message.reply(fixed_url)
        if message.channel.permissions_for(message.guild.me).manage_messages:
            await message.edit(suppress=True)

        self.fixed_messages[message.id] = fixed_msg.id

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        fixed_message_id = self.fixed_messages.pop(message.id, None)
        if fixed_message_id:
            fixed_message = await message.channel.fetch_message(fixed_message_id)
            await fixed_message.delete()
