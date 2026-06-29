import asyncio
import re

import discord
from cachetools import LRUCache
from cogs.lancocog import LancoCog
from db import BaseModel
from discord import app_commands
from discord.ext import commands
from peewee import *


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

        config, _ = self._cog.config_model.get_or_create(guild_id=self._guild_id)
        config.handler_id = handler_id
        config.save()

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


class _BypassButtonView(discord.ui.View):
    def __init__(self, bypass_url: str, service_name: str):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label=f"Read via {service_name}",
                url=bypass_url,
                style=discord.ButtonStyle.link,
                emoji="🔓",
            )
        )


class EmbedFixConfigBase(BaseModel):
    guild_id = BigIntegerField(primary_key=True)
    enabled = BooleanField(default=False)
    handler_id = CharField(default="")


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
            service_url: str = None,
        ):
            self.id = id
            self.name = name
            self.description = description
            self.patterns = patterns
            # When set, bypass_button_mode uses this prefix instead of PatternReplacement
            self.service_url = service_url

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
        config_model: Model,
        skip_if_handled_by_discord: bool = False,
        wait_time: float = 2.5,
        bypass_button_mode: bool = False,
    ):
        super().__init__(bot)
        self.name = name
        self.handlers = handlers
        self.config_model = config_model
        self.skip_if_handled_by_discord = skip_if_handled_by_discord
        self.wait_time = wait_time
        self.bypass_button_mode = bypass_button_mode
        self.bot.database.create_tables([self.config_model])
        self.fixed_messages = LRUCache(maxsize=1000)  # message_id -> fixed_message_id

    def _bypass_embed(self, active: "EmbedFixCog.Handler") -> discord.Embed | None:
        return None

    def _active_handler(self, config) -> "EmbedFixCog.Handler":
        """Return the configured Handler for this guild, falling back to the first."""
        if config and config.handler_id:
            for h in self.handlers:
                if h.id == config.handler_id:
                    return h
        return self.handlers[0]

    async def toggle(self, interaction: discord.Interaction):
        config, created = self.config_model.get_or_create(guild_id=interaction.guild.id)
        if created or not config.enabled:
            config.enabled = True
            config.save()
            await interaction.response.send_message(
                f"{self.name} enabled for this server"
            )
        else:
            config.enabled = False
            config.save()
            await interaction.response.send_message(
                f"{self.name} disabled for this server"
            )

    async def _show_handler_select(self, interaction: discord.Interaction):
        config = self.config_model.get_or_none(guild_id=interaction.guild.id)
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

        embed_config = self.config_model.get_or_none(guild_id=message.guild.id)
        if not embed_config or not embed_config.enabled:
            self.logger.info("Embed fix not enabled for this server")
            return

        active = self._active_handler(embed_config)

        if self.bypass_button_mode and active.service_url:
            fixed_url = active.service_url + original_url
        else:
            pr = active.patterns[min(matched_idx, len(active.patterns) - 1)]
            fixed_url = original_url.replace(pr.original, pr.replacement)

        self.logger.info(
            f"Fixing URL with handler '{active.id}': {original_url} -> {fixed_url}"
        )

        if self.bypass_button_mode:
            view = _BypassButtonView(fixed_url, active.name)
            fixed_msg = await message.reply(
                embed=self._bypass_embed(active), view=view, mention_author=False
            )
        else:
            fixed_msg = await message.reply(fixed_url)
            # suppress the original embed if we can
            if message.channel.permissions_for(message.guild.me).manage_messages:
                await message.edit(suppress=True)

        self.fixed_messages[message.id] = fixed_msg.id

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        fixed_message_id = self.fixed_messages.pop(message.id, None)
        if fixed_message_id:
            fixed_message = await message.channel.fetch_message(fixed_message_id)
            await fixed_message.delete()
