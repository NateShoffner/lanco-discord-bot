import asyncio
import inspect
import logging
import re
import time
from abc import abstractmethod
from math import floor
from pathlib import Path
from typing import Generic, TypeVar

import discord
from discord import app_commands
from discord.ext import commands
from pydantic import BaseModel
from utils.roundgame.session import RoundGameSession

TSession = TypeVar("TSession", bound=RoundGameSession)


class LancoCog(commands.Cog, name="LancoCog", description="Base class for all cogs"):
    @property
    def bot(self) -> commands.Bot:
        return self._bot

    def __init__(self, bot: commands.Bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bot = bot
        self.logger = logging.getLogger(self.get_cog_name())
        self.context_menus = []
        self._tracked_tasks = []

    def track_task(self, task):
        """Register a background task to be cancelled on cog unload."""
        self._tracked_tasks.append(task)
        return task

    async def cog_load(self):
        self.logger.info(f"{self.get_cog_name()} cog loaded")

    def get_cog_name(self):
        return self.qualified_name

    def get_cog_data_directory(self):
        return f"data/{self.get_cog_name()}"

    def get_cog_file_path(self, relative: bool = False) -> Path:
        path = Path(inspect.getfile(self.__class__))
        if relative:
            path = path.relative_to(Path.cwd() / "app")
        return path

    def get_cog_directory(self, relative: bool = False) -> Path:
        return self.get_cog_file_path(relative).parent

    def register_context_menu(self, name: str, callback, errback=None, **kwargs):
        ctx_menu = app_commands.ContextMenu(name=name, callback=callback, **kwargs)
        if errback:
            ctx_menu.error(errback)
        self.bot.tree.add_command(ctx_menu)
        self.context_menus.append(ctx_menu)

    async def cog_unload(self):
        self.logger.info(f"{self.get_cog_name()} cog unloaded")

        for task in self._tracked_tasks:
            task.cancel()
        self._tracked_tasks.clear()

        for ctx_menu in self.context_menus:
            self.bot.tree.remove_command(ctx_menu.name, type=ctx_menu.type)

        self.bot.url_handlers = [h for h in self.bot.url_handlers if h.cog is not self]
        self.bot.image_processors = [
            i for i in self.bot.image_processors if i.cog is not self
        ]


class RoundGameCog(LancoCog, Generic[TSession]):
    GAME_NAME: str = ""
    SCORING_VERSION: int = 1
    GUESS_TIME: int = 20
    TIME_BETWEEN_ROUNDS: int = 10

    @property
    def WARNING_TIME(self) -> int:
        return floor(self.GUESS_TIME / 2)

    @property
    @abstractmethod
    def active_sessions(self) -> dict:
        raise NotImplementedError

    @property
    @abstractmethod
    def sessions_starting(self) -> list:
        raise NotImplementedError

    def get_session(self, channel) -> TSession | None:
        channel_id = channel.id if hasattr(channel, "id") else channel
        return self.active_sessions.get(channel_id)

    def _is_stale_interaction(self, interaction: discord.Interaction) -> bool:
        return interaction.created_at.timestamp() < self._ready_at

    @abstractmethod
    async def build_round_embed(
        self, session: TSession, intro: bool
    ) -> tuple[discord.Embed, list[discord.File]]:
        raise NotImplementedError

    @abstractmethod
    def build_results_embed(
        self, session: TSession, next_round_time: int | None
    ) -> discord.Embed:
        raise NotImplementedError

    @abstractmethod
    def build_final_embed(self, session: TSession) -> discord.Embed:
        raise NotImplementedError

    @abstractmethod
    def should_record_guess(self, message: discord.Message) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def process_guess(
        self, session: TSession, member: discord.Member, guess: str
    ):
        raise NotImplementedError

    async def on_round_end(self, session: TSession):
        pass

    async def on_game_end(self, session: TSession):
        pass

    def build_leaderboard(self, session: TSession) -> str:
        if not session.members:
            return "No scores yet"
        sorted_players = sorted(
            session.members.items(), key=lambda x: x[1], reverse=True
        )
        lines = []
        for player_id, score in sorted_players:
            if score <= 0:
                continue
            member = session.channel.guild.get_member(player_id)
            name = member.display_name if member else f"<{player_id}>"
            lines.append(f"{len(lines) + 1}. `{name}` ({score:.0f})")
            if len(lines) >= 10:
                break
        return "\n".join(lines) if lines else "No scores yet"

    async def post_round_warning(self, session: TSession):
        if session.cancelled:
            return
        deadline = int(session.round_deadline)
        await asyncio.sleep(self.WARNING_TIME)
        if session.cancelled:
            return
        session.round_warning_message = await session.channel.send(
            f"Guessing closes <t:{deadline}:R>!"
        )

    async def post_current_round(
        self, session: TSession, immediate: bool = False, intro: bool = False
    ):
        if session.cancelled:
            return
        if not immediate:
            await asyncio.sleep(self.TIME_BETWEEN_ROUNDS)
        if session.cancelled:
            return

        # strip "Next round" countdown from the previous result/skip embed
        for attr in ("round_results_message", "skip_message"):
            msg = getattr(session, attr, None)
            if msg:
                try:
                    prev_embed = msg.embeds[0]
                    prev_embed._fields = [
                        f for f in prev_embed._fields if f["name"] != "Next round"
                    ]
                    await msg.edit(embed=prev_embed)
                except discord.HTTPException:
                    pass
                setattr(session, attr, None)

        current_round = session.get_current_round()
        if not current_round:
            return

        self.logger.info(
            f"[{self.GAME_NAME}] Round {session.current_round + 1}/{len(session.rounds)} "
            f"starting in #{session.channel}"
        )

        embed, files = await self.build_round_embed(session, intro)

        send_kwargs = {"embed": embed}
        if files:
            send_kwargs["files"] = files

        session.current_round_message = await session.channel.send(**send_kwargs)

        deadline = int(time.time()) + self.GUESS_TIME
        session.round_deadline = deadline
        embed.add_field(name="Guessing closes", value=f"<t:{deadline}:R>", inline=True)
        await session.current_round_message.edit(embed=embed)

        session.warning_task = asyncio.create_task(self.post_round_warning(session))

        if session.has_next_round():
            session.round_task = asyncio.create_task(self._advance_round(session))
        else:
            session.round_task = asyncio.create_task(self.post_final_results(session))

    async def post_round_results(self, session: TSession, skip_wait: bool = False):
        if session.cancelled:
            return
        if not skip_wait:
            await asyncio.sleep(self.GUESS_TIME)
        if session.cancelled:
            return

        session.round_deadline = 0.0
        await self.on_round_end(session)

        next_round_time = (
            int(time.time()) + self.TIME_BETWEEN_ROUNDS
            if session.has_next_round()
            else None
        )

        self.logger.info(
            f"[{self.GAME_NAME}] Round {session.current_round + 1}/{len(session.rounds)} "
            f"ended in #{session.channel}"
        )

        if session.current_round_message:
            try:
                old = session.current_round_message.embeds[0]
                frozen = discord.Embed(
                    title=old.title, description=old.description, color=old.color.value
                )
                frozen.add_field(
                    name="Round",
                    value=f"{session.current_round + 1} / {len(session.rounds)}",
                    inline=True,
                )
                frozen.add_field(
                    name="Guessing closed", value="Round ended", inline=True
                )
                await session.current_round_message.edit(embed=frozen, attachments=[])
            except discord.HTTPException as e:
                self.logger.warning(f"Failed to freeze round embed: {e}")

        if session.round_warning_message:
            try:
                await session.round_warning_message.delete()
            except discord.HTTPException:
                pass
            session.round_warning_message = None

        embed = self.build_results_embed(session, next_round_time)
        session.round_results_message = await session.channel.send(embed=embed)

    async def post_final_results(self, session: TSession, skipped: bool = False):
        if session.cancelled:
            return

        await self.post_round_results(session, skip_wait=skipped)
        if session.cancelled:
            return

        self.active_sessions.pop(session.channel.id, None)
        self.logger.info(
            f"[{self.GAME_NAME}] Game ended in #{session.channel} — "
            f"{len(session.members)} player(s), {len(session.rounds)} rounds"
        )

        await self.on_game_end(session)

        embed = self.build_final_embed(session)
        await session.channel.send(embed=embed)

    async def _advance_round(self, session: TSession):
        await self.post_round_results(session)
        if not session.cancelled:
            session.next()
            asyncio.create_task(self.post_current_round(session, False))

    async def _cleanup_stopped_session(self, session: TSession):
        if session.current_round_message:
            try:
                old = session.current_round_message.embeds[0]
                stopped = discord.Embed(
                    title=old.title,
                    description="Session stopped.",
                    color=old.color.value,
                )
                await session.current_round_message.edit(embed=stopped, attachments=[])
            except discord.HTTPException as e:
                self.logger.warning(f"Failed to edit round embed on stop: {e}")

        if session.round_warning_message:
            try:
                await session.round_warning_message.delete()
            except discord.HTTPException:
                pass
            session.round_warning_message = None

        rounds_played = session.current_round + 1
        embed = discord.Embed(title="Game Stopped", color=discord.Color.red())
        embed.add_field(
            name="Rounds played",
            value=f"{rounds_played} of {len(session.rounds)}",
            inline=True,
        )
        leaderboard = self.build_leaderboard(session)
        if leaderboard != "No scores yet":
            embed.add_field(name="Standings", value=leaderboard, inline=False)
        await session.channel.send(embed=embed)

    def get_guess_reaction(self, result) -> str | None:
        return "✅"

    async def _handle_guess_message(self, message: discord.Message):
        if message.author.bot:
            return
        session = self.get_session(message.channel)
        if not session:
            return

        now = time.time()
        if now > session.round_deadline:
            return
        if not session.get_current_round():
            return
        if session.has_guessed(message.author.id):
            return
        if not self.should_record_guess(message):
            return

        round_at_submit = session.current_round
        result = await self.process_guess(
            session, message.author, message.content.strip()
        )

        if session.current_round != round_at_submit:
            return
        if result is None:
            return

        reaction = self.get_guess_reaction(result)
        if reaction:
            await message.add_reaction(reaction)


class UrlHandler(BaseModel):
    url_pattern: re.Pattern
    cog: LancoCog
    example_url: str

    class Config:
        arbitrary_types_allowed = True
