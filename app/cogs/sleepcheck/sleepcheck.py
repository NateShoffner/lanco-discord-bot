import datetime
import mimetypes
import os
from dataclasses import dataclass

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent
from utils.file_downloader import FileDownloader


class SleepScreenshot(BaseModel):
    total_sleep_time_minutes: int


@dataclass
class SleepRoyaleUser:
    user_id: int
    duration: datetime.timedelta


@dataclass
class SleepRoyale:
    channel_id: int
    active: bool
    started: datetime.datetime
    users: list[SleepRoyaleUser]


class SleepCheck(
    LancoCog,
    name="SleepCheck",
    description="SleepCheck commands",
):
    g = app_commands.Group(name="sleepcheck", description="SleepCheck commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.agent = Agent(
            model="openai:gpt-4o",
            system_prompt="Describe this image.",
            output_type=SleepScreenshot,
        )
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.file_downloader = FileDownloader()
        self.active_royales = {}

    @g.command(
        name="today",
        description="Check how much sleep everyone got today",
    )
    async def today(
        self,
        interaction: discord.Interaction,
        royale_channel: discord.TextChannel = None,
    ):
        """Check how much sleep everyone got today"""
        if not royale_channel:
            royale_channel = interaction.channel

        if royale_channel.id in self.active_royales:
            await interaction.response.send_message(
                "Sleep Royale is already active", ephemeral=True
            )
            return

        self.active_royales[royale_channel.id] = True

        def build_embed(description: str) -> discord.Embed:
            desc = f"{datetime.date.today().strftime('%B %d, %Y')}\n\n"
            desc += f"Channel: {royale_channel.mention}\n\n"
            desc += description

            embed = discord.Embed(
                title=f"Sleep Royale",
                description=desc,
                color=0x00FF00,
            )
            return embed

        start_embed = build_embed(
            "Sleep Royale has started!\nChecking for sleep screenshots..."
        )
        response_msg = await interaction.response.send_message(embed=start_embed)

        messages = await self.get_messages_from_day(
            royale_channel, datetime.date.today()
        )
        self.logger.info(f"Found {len(messages)} messages for today")

        finished_embed = build_embed("Calculating sleep times...")
        response_msg = await interaction.original_response()
        await response_msg.edit(embed=finished_embed)

        users = await self.get_sleep_times(messages)

        desc = "Leaderboard:\n"

        if users and len(users) > 0:
            # sort users by sleep time, with the highest sleep time first
            sorted_users = sorted(users.items(), key=lambda x: x[1], reverse=True)
            for i, (user, duration) in enumerate(sorted_users[:10]):
                hours, remainder = divmod(duration.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                desc += (
                    f"{i+1}. {user.display_name} - {hours} hours {minutes} minutes\n"
                )

        else:
            desc += "Not enough users provided sleep times"

        response_msg = await interaction.original_response()
        final_embed = build_embed(desc)
        await response_msg.edit(embed=final_embed)

        del self.active_royales[royale_channel.id]

    async def get_sleep_times(
        self, messages: list[discord.Message]
    ) -> dict[discord.User, datetime.timedelta]:
        users = {}
        for message in messages:
            if message.author.bot:
                continue

            if not message.attachments:
                continue

            self.logger.info(f"Processing message from {message.author.name}")
            ss = await self.process_screenshot(message)
            if ss:
                delta = datetime.timedelta(minutes=ss.total_sleep_time_minutes)
                users[message.author] = delta

        return users

    async def get_messages_from_day(
        self, channel: discord.TextChannel, day: datetime.date
    ) -> list[discord.Message]:
        """Get all messages from a specific day"""
        messages = []
        async for message in channel.history(
            after=datetime.datetime(day.year, day.month, day.day),
            limit=500,
            oldest_first=True,
        ):
            if message.created_at.date() == day:
                messages.append(message)

        return messages

    async def process_screenshot(self, message: discord.Message) -> SleepScreenshot:
        results = await self.file_downloader.download_attachments(
            message, self.cache_dir
        )
        filename = results[0].filename

        with open(filename, "rb") as f:
            image_bytes = f.read()

        # TODO might want to use python-magic so it's content-based
        mime_type, _ = mimetypes.guess_type(filename)

        # throw it out if it's not an image
        if not mime_type or not mime_type.startswith("image/"):
            self.logger.error(f"File {filename} is not an image.")
            return None

        result = await self.agent.run(
            [
                "Determine if this photo is a screenshot of a sleep tracker and if so, parse out the details.",
                BinaryContent(data=image_bytes, media_type=mime_type),
            ]
        )

        # cleanup
        for r in results:
            os.remove(r.filename)

        return result.output


async def setup(bot):
    await bot.add_cog(SleepCheck(bot))
