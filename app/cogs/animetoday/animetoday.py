import datetime
import os
import random

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands, tasks
from utils.command_utils import is_bot_owner_or_admin

from .models import AnimeTodayConfig


class AnimeToday(LancoCog, name="AnimeToday", description="Daily anime shot announcements"):
    embed_group = app_commands.Group(
        name="animetoday", description="AnimeToday commands"
    )

    est = datetime.timezone(datetime.timedelta(hours=-5))
    daily_announcement_time = (datetime.time(hour=7, tzinfo=est),)

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([AnimeTodayConfig])
        self.daily_anime_task.start()

    def cog_unload(self):
        self.daily_anime_task.cancel()

    @tasks.loop(time=daily_announcement_time)
    async def daily_anime_task(self):
        anime_today_configs = AnimeTodayConfig.select()
        for config in anime_today_configs:
            channel = self.bot.get_channel(config.channel_id)
            if channel:
                await self.send_daily_anime_shot(channel)

    @embed_group.command(
        name="toggle", description="Toggle the anime calendar for this channel"
    )
    @is_bot_owner_or_admin()
    async def toggle(self, interaction: discord.Interaction):
        """Toggle the anime calendar for this channel"""
        config, created = AnimeTodayConfig.get_or_create(guild_id=interaction.guild.id)
        if created:
            config.channel_id = interaction.channel.id
            config.save()
            await interaction.response.send_message("Anime calendar enabled")
        else:
            config.delete_instance()
            await interaction.response.send_message("Anime calendar disabled")

    @commands.command(name="animetest", description="Test the anime calendar")
    async def anime_test(self, ctx: commands.Context):
        """Test the anime calendar"""
        await self.send_daily_anime_shot(ctx.channel)

    async def send_daily_anime_shot(self, channel: discord.TextChannel):
        def suffix(d):
            return {1: "st", 2: "nd", 3: "rd"}.get(d % 20, "th")

        def custom_strftime(format, t):
            return t.strftime(format).replace("{S}", str(t.day) + suffix(t.day))

        img_file, anime_name = self.get_daily_anime_shot()

        if not img_file:
            return

        embed = discord.Embed()
        embed.set_image(url="attachment://anime_shot.png")
        embed.title = custom_strftime(
            "Today's Anime Shot: %B {S}", datetime.datetime.now()
        )
        if anime_name:
            embed.description = f"Source: {anime_name}"
        await channel.send(embed=embed, file=discord.File(img_file, "anime_shot.png"))

    def get_daily_anime_shot(self) -> tuple[str, str]:
        shots_dir = os.path.join(self.get_cog_data_directory(), "Shots")
        if not os.path.exists(shots_dir):
            os.makedirs(shots_dir)

        today = datetime.datetime.now()

        month_dir = os.path.join(shots_dir, today.strftime("%m_%B"))
        if not os.path.exists(month_dir):
            os.makedirs(month_dir)

        day_dir = os.path.join(month_dir, today.strftime("%d"))
        if not os.path.exists(day_dir):
            os.makedirs(day_dir)

        # get a random not .txt file from the day directory
        files = os.listdir(day_dir)
        files = [f for f in files if not f.endswith(".txt")]

        if not files or len(files) == 0:
            self.logger.error(f"No images found in {day_dir}")
            return None, None

        file = random.choice(files)

        img_file = os.path.join(day_dir, file)

        filename_without_extension = os.path.splitext(file)[0]

        # check if the file has a .txt file
        txt_file = os.path.join(day_dir, filename_without_extension + ".txt")
        anime_name = None
        if os.path.exists(txt_file):
            with open(txt_file, "r") as f:
                anime_name = f.read()
                # scrub first and last curly braces
                anime_name = anime_name[1:-1]

        return img_file, anime_name


async def setup(bot):
    await bot.add_cog(AnimeToday(bot))
