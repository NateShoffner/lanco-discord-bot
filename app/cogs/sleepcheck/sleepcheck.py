import base64
import datetime
import json
import os
from dataclasses import dataclass

import discord
import openai
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.file_downloader import FileDownloader


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
        self.client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))
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
            sleep_time = await self.get_sleep_time(message)
            if sleep_time:
                users[message.author] = sleep_time

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

    async def get_sleep_time(self, message: discord.Message) -> datetime.timedelta:
        results = await self.file_downloader.download_attachments(
            message, self.cache_dir
        )
        filename = results[0].filename
        encoded = self.encode_image(filename)

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that responds in JSON.",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "If this appears to be a screenshot of a sleep tracker, please provide the total sleep time in minutes.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{encoded}"},
                        },
                    ],
                },
            ],
            temperature=0.0,
        )

        response = response.choices[0].message.content
        # remove markdown
        response = response.replace("```json\n", "").replace("```", "")

        for r in results:
            os.remove(r.filename)

        try:
            json_parsed = json.loads(response)
            mins = json_parsed["total_sleep_time_minutes"]
            self.logger.info(f"Sleep time: {mins}")
            return datetime.timedelta(minutes=mins)
        except Exception as e:
            self.logger.error(f"Error parsing JSON: {e}")
            return None

    def encode_image(self, image_path: str):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")


async def setup(bot):
    await bot.add_cog(SleepCheck(bot))
