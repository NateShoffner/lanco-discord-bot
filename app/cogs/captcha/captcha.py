import asyncio
import time
from io import BytesIO

import discord
from cogs.lancocog import RoundGameCog
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View
from utils.roundgame.dbmodels import RoundGameResult

from .captcha_gen import generate_captcha
from .models import (
    AlphanumericMode,
    CaptchaMode,
    CaptchaRound,
    DictionaryMode,
    LancasterMode,
)
from .session import CaptchaSession

SCORING_VERSION = 1
# Version history:
# 1 - place-based scoring (100/75/50/25) + proportional time bonus (max 20)

_active_sessions: dict = {}
_sessions_starting: list = []


class CaptchaCog(
    RoundGameCog[CaptchaSession], name="Captcha", description="Captcha guessing game"
):
    GAME_NAME = "captcha"
    SCORING_VERSION = SCORING_VERSION
    GUESS_TIME = 15
    TIME_BETWEEN_ROUNDS = 3

    captcha_group = app_commands.Group(
        name="captcha", description="Captcha game commands"
    )

    MODES: list[CaptchaMode] = [
        AlphanumericMode(),
        DictionaryMode(),
        LancasterMode(),
    ]

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self._ready_at: float = 0.0
        self.bot.database.create_tables([RoundGameResult])

    async def cog_load(self):
        await super().cog_load()
        self._ready_at = time.time()

    @property
    def active_sessions(self):
        return _active_sessions

    @property
    def sessions_starting(self):
        return _sessions_starting

    # ── RoundGameCog implementations ──────────────────────────────────────────

    def should_record_guess(self, message: discord.Message) -> bool:
        return 1 <= len(message.content.strip()) <= 100

    async def process_guess(
        self, session: CaptchaSession, member: discord.Member, guess: str
    ):
        result = await asyncio.to_thread(session.handle_guess, member, guess)
        if result:
            status = (
                f"correct (place {result.place}, +{result.score:.0f})"
                if result.correct
                else "wrong"
            )
            self.logger.info(f"{member} guessed '{guess}' — {status}")
        return result

    async def build_round_embed(self, session: CaptchaSession, intro: bool):
        current_round = session.get_current_round()
        challenge = current_round.challenge

        if intro:
            title = f"Captcha ({session.mode.icon} {session.mode.name})"
            description = (
                f"**{session.host.display_name}** has started a new game!\n\n"
                f"Type what you see in the image.\n"
                f"First correct answer gets the most points — be fast!\n\n"
                f"**One guess per round.**\n"
                f"✅ = answer recorded  ❌ = wrong answer\n\n"
                f"The host can skip with `/captcha skip`."
            )
        else:
            title = f"Round {session.current_round + 1} of {len(session.rounds)}"
            description = None

        embed = discord.Embed(title=title, description=description, color=0x5865F2)
        embed.add_field(
            name="Round",
            value=f"{session.current_round + 1} / {len(session.rounds)}",
            inline=True,
        )
        embed.set_image(url="attachment://captcha.png")

        file = discord.File(BytesIO(challenge.image_bytes), filename="captcha.png")
        return embed, [file]

    def build_results_embed(
        self, session: CaptchaSession, next_round_time: int | None
    ) -> discord.Embed:
        r = session.get_current_round()
        answer = r.challenge.answer

        embed = discord.Embed(title="End of the round", color=0x5865F2)
        embed.add_field(
            name="Round", value=f"{r.number + 1} of {len(session.rounds)}", inline=True
        )
        embed.add_field(name="Answer", value=f"`{answer}`", inline=True)

        # list correct guessers in order
        correct_lines = []
        place_medals = ["🥇", "🥈", "🥉"]
        for user_id, result in r.guesses.items():
            if result.correct:
                member = session.channel.guild.get_member(user_id)
                name = member.display_name if member else f"<{user_id}>"
                medal = (
                    place_medals[result.place - 1]
                    if result.place <= 3
                    else f"{result.place}."
                )
                correct_lines.append(f"{medal} `{name}` (+{result.score:.0f})")

        if correct_lines:
            embed.add_field(
                name="Got it!", value="\n".join(correct_lines), inline=False
            )
        else:
            embed.add_field(
                name="Got it!", value="Nobody got it this round.", inline=False
            )

        leaderboard = self.build_leaderboard(session)
        embed.add_field(name="Standings", value=leaderboard, inline=False)

        if next_round_time:
            embed.add_field(
                name="Next round", value=f"<t:{next_round_time}:R>", inline=False
            )

        return embed

    def build_final_embed(self, session: CaptchaSession) -> discord.Embed:
        leaderboard = self.build_leaderboard(session)
        winner = None
        if session.members:
            top_id = max(session.members, key=lambda uid: session.members[uid])
            if session.members[top_id] > 0:
                winner = session.channel.guild.get_member(top_id)

        title = f"{winner.display_name} wins!" if winner else "Game Over"
        description = f"{session.mode.icon} **{session.mode.name}** — {len(session.rounds)} rounds"
        embed = discord.Embed(title=title, description=description, color=0x5865F2)
        embed.add_field(name="Final Standings", value=leaderboard, inline=False)
        return embed

    def get_guess_reaction(self, result) -> str | None:
        if result is None:
            return None
        return "✅" if result.correct else "❌"

    async def on_round_end(self, session: CaptchaSession):
        # React ❌ to wrong guesses so players know before the reveal
        r = session.get_current_round()
        if not r:
            return
        for user_id, result in r.guesses.items():
            if not result.correct:
                # We don't hold message references per-guess, so we skip this;
                # the result embed will show the answer.
                pass

    async def on_game_end(self, session: CaptchaSession):
        if len(session.members) > 1:
            with self.bot.database.atomic():
                for user_id, score in session.members.items():
                    RoundGameResult.create(
                        game_name=self.GAME_NAME,
                        game_id=session.game_id,
                        guild_id=session.channel.guild.id,
                        user_id=user_id,
                        mode=session.mode.name,
                        score=score,
                        rounds_played=len(session.rounds),
                        scoring_version=self.SCORING_VERSION,
                    )
            self.logger.info(
                f"Recorded captcha results for game {session.game_id} — {len(session.members)} players"
            )

    # ── on_message ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self._handle_guess_message(message)

    # ── Slash commands ────────────────────────────────────────────────────────

    @captcha_group.command(name="start", description="Start a new Captcha game")
    async def start(self, interaction: discord.Interaction):
        if self._is_stale_interaction(interaction):
            return
        if interaction.channel_id in self.active_sessions:
            await interaction.response.send_message(
                "A game is already in progress.", ephemeral=True
            )
            return
        if interaction.channel_id in self.sessions_starting:
            await interaction.response.send_message(
                "A game is already starting.", ephemeral=True
            )
            return

        self.sessions_starting.append(interaction.channel_id)

        try:
            mode_select = Select(
                placeholder="Choose a mode",
                options=[
                    discord.SelectOption(
                        label=m.name,
                        emoji=m.icon,
                        description=m.description,
                        value=m.name,
                    )
                    for m in self.MODES
                ],
            )

            async def mode_callback(i: discord.Interaction):
                mode_name = i.data["values"][0]
                mode = next(m for m in self.MODES if m.name == mode_name)

                rounds_select = Select(
                    placeholder="How many rounds?",
                    options=[
                        discord.SelectOption(label=f"{r} rounds", value=str(r))
                        for r in [5, 10, 15, 20]
                    ],
                )

                async def rounds_callback(ri: discord.Interaction):
                    chosen_rounds = int(ri.data["values"][0])
                    await ri.response.edit_message(
                        content=f"Starting **{mode.name}** captcha game ({chosen_rounds} rounds)...",
                        view=None,
                    )
                    await self.initialize_session(
                        mode,
                        ri.channel or await self.bot.fetch_channel(ri.channel_id),
                        ri.user,
                        chosen_rounds,
                    )

                rounds_select.callback = rounds_callback
                rounds_view = View(timeout=60)
                rounds_view.add_item(rounds_select)

                async def on_rounds_timeout():
                    if interaction.channel_id in self.sessions_starting:
                        self.sessions_starting.remove(interaction.channel_id)
                    try:
                        await interaction.edit_original_response(
                            content="Round selection timed out.", view=None
                        )
                    except discord.HTTPException:
                        pass

                rounds_view.on_timeout = on_rounds_timeout
                await i.response.edit_message(
                    content=f"{mode.icon} **{mode.name}** selected.",
                    view=rounds_view,
                )

            mode_select.callback = mode_callback
            view = View(timeout=60)
            view.add_item(mode_select)

            async def on_timeout():
                if interaction.channel_id in self.sessions_starting:
                    self.sessions_starting.remove(interaction.channel_id)
                try:
                    await interaction.edit_original_response(
                        content="Mode selection timed out.", view=None
                    )
                except discord.HTTPException:
                    pass

            view.on_timeout = on_timeout
            await interaction.response.send_message(view=view)
        except Exception:
            if interaction.channel_id in self.sessions_starting:
                self.sessions_starting.remove(interaction.channel_id)
            raise

    @captcha_group.command(name="stop", description="Stop the current Captcha game")
    async def stop(self, interaction: discord.Interaction):
        if self._is_stale_interaction(interaction):
            return
        session = self.get_session(interaction.channel_id)
        if not session:
            await interaction.response.send_message(
                "No game is in progress.", ephemeral=True
            )
            return

        session.cancel()
        self.active_sessions.pop(interaction.channel_id, None)
        if interaction.channel_id in self.sessions_starting:
            self.sessions_starting.remove(interaction.channel_id)

        try:
            await interaction.response.send_message("Game stopped.", ephemeral=True)
        except discord.HTTPException:
            pass

        asyncio.create_task(self._cleanup_stopped_session(session))

    @captcha_group.command(
        name="skip", description="Skip the current round (host only)"
    )
    async def skip(self, interaction: discord.Interaction):
        if self._is_stale_interaction(interaction):
            return
        session = self.get_session(interaction.channel_id)
        if not session:
            await interaction.response.send_message(
                "No game is in progress.", ephemeral=True
            )
            return
        if interaction.user != session.host:
            await interaction.response.send_message(
                "Only the host can skip.", ephemeral=True
            )
            return
        if session.round_deadline == 0.0:
            await interaction.response.send_message(
                "Guessing is not active right now.", ephemeral=True
            )
            return

        skipped_round = session.current_round + 1
        self.logger.info(f"Captcha round {skipped_round} skipped by {interaction.user}")

        if session.round_task and not session.round_task.done():
            session.round_task.cancel()
        if session.warning_task and not session.warning_task.done():
            session.warning_task.cancel()

        session.round_deadline = 0.0

        if session.round_warning_message:
            try:
                await session.round_warning_message.delete()
            except discord.HTTPException:
                pass
            session.round_warning_message = None

        if session.has_next_round():
            session.next()
            next_round_time = int(time.time()) + self.TIME_BETWEEN_ROUNDS
            embed = discord.Embed(
                title=f"Round {skipped_round} skipped", color=0x5865F2
            )
            embed.add_field(
                name="Next round", value=f"<t:{next_round_time}:R>", inline=False
            )
            try:
                await interaction.response.send_message(embed=embed)
                session.skip_message = await interaction.original_response()
            except discord.HTTPException:
                session.skip_message = await session.channel.send(embed=embed)
            asyncio.create_task(self.post_current_round(session, immediate=False))
        else:
            try:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title=f"Round {skipped_round} skipped", color=0x5865F2
                    )
                )
            except discord.HTTPException:
                await session.channel.send(
                    embed=discord.Embed(
                        title=f"Round {skipped_round} skipped", color=0x5865F2
                    )
                )
            asyncio.create_task(self.post_final_results(session, skipped=True))

        if session.current_round_message:
            try:
                old = session.current_round_message.embeds[0]
                frozen = discord.Embed(
                    title=old.title, description=old.description, color=old.color.value
                )
                frozen.add_field(
                    name="Round",
                    value=f"{session.current_round} / {len(session.rounds)}",
                    inline=True,
                )
                frozen.add_field(name="Guessing closed", value="Skipped", inline=True)
                await session.current_round_message.edit(embed=frozen, attachments=[])
            except discord.HTTPException as e:
                self.logger.warning(f"Failed to freeze round embed on skip: {e}")

    @captcha_group.command(
        name="leaderboard", description="Show the Captcha leaderboard"
    )
    @app_commands.describe(period="Time period to filter by")
    @app_commands.choices(
        period=[
            app_commands.Choice(name="All Time", value="all"),
            app_commands.Choice(name="Today", value="today"),
            app_commands.Choice(name="This Week", value="week"),
        ]
    )
    async def leaderboard(self, interaction: discord.Interaction, period: str = "all"):
        import datetime

        guild_id = interaction.guild.id
        query = RoundGameResult.select().where(
            RoundGameResult.game_name == self.GAME_NAME,
            RoundGameResult.guild_id == guild_id,
            RoundGameResult.scoring_version == self.SCORING_VERSION,
        )

        now = datetime.datetime.utcnow()
        if period == "today":
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.where(RoundGameResult.played_at >= cutoff)
            period_label = "Today"
        elif period == "week":
            cutoff = now - datetime.timedelta(days=7)
            query = query.where(RoundGameResult.played_at >= cutoff)
            period_label = "This Week"
        else:
            period_label = "All Time"

        totals: dict[int, float] = {}
        for row in query:
            totals[row.user_id] = totals.get(row.user_id, 0) + row.score

        if not totals:
            embed = discord.Embed(
                title=f"Captcha Leaderboard ({period_label})",
                description="No results yet. Games require at least 2 players to count.",
                color=0x5865F2,
            )
            await interaction.response.send_message(embed=embed)
            return

        sorted_players = sorted(totals.items(), key=lambda x: x[1], reverse=True)
        lines = []
        for user_id, score in sorted_players[:10]:
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"<{user_id}>"
            lines.append(f"{len(lines) + 1}. `{name}` ({score:.0f})")

        embed = discord.Embed(
            title=f"Captcha Leaderboard ({period_label})", color=0x5865F2
        )
        embed.add_field(name="Top Players", value="\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed)

    # ── Session init ──────────────────────────────────────────────────────────

    async def initialize_session(
        self,
        mode: CaptchaMode,
        channel: discord.TextChannel,
        host: discord.Member,
        num_rounds: int,
    ):
        self.logger.info(
            f"Starting captcha session in #{channel} — mode: {mode.name}, host: {host}, rounds: {num_rounds}"
        )
        try:
            session = CaptchaSession(mode, channel, host, self.GUESS_TIME)
            self.active_sessions[channel.id] = session

            # Generate all challenges up front (sync, but fast)
            challenges = await asyncio.to_thread(
                lambda: [generate_captcha(mode) for _ in range(num_rounds)]
            )
            rounds = [
                CaptchaRound(number=i, challenge=c) for i, c in enumerate(challenges)
            ]
            session.init(rounds)
        except Exception as e:
            self.logger.error(
                f"Failed to initialize captcha session in #{channel}: {e}",
                exc_info=True,
            )
            self.active_sessions.pop(channel.id, None)
            await channel.send("Failed to start the game, please try again.")
            return
        finally:
            if channel.id in self.sessions_starting:
                self.sessions_starting.remove(channel.id)

        asyncio.create_task(
            self.post_current_round(session, immediate=True, intro=True)
        )


async def setup(bot):
    await bot.add_cog(CaptchaCog(bot))
