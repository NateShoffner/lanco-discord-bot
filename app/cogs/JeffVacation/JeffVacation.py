"""
Jeff Vacation Cog

Description:
Harasses Jeff about his vacation and shows a countdown to the end of it.
"""

import os
from datetime import datetime, timedelta

import discord
import pytz
from cogs.lancocog import LancoCog
from discord.ext import commands
from num2words import num2words
from PIL import Image, ImageDraw, ImageFont


class DawnScreen:
    def __init__(self, width=640, height=480):
        self.width = width
        self.height = height
        self.bg_color = "black"
        self.text_color = "white"

        font_path = os.path.join("assets", "font", "arial-narrow-bold.ttf")
        print(f"Using font from: {font_path}")
        self.font_top = ImageFont.truetype(font_path, 36)
        self.font_middle = ImageFont.truetype(font_path, 80)
        self.font_bottom = ImageFont.truetype(font_path, 40)

    def generate(self, day=1, hours=None):
        if hours is None:
            hours = 72 - (day - 1) * 24

        img = Image.new("RGB", (self.width, self.height), color=self.bg_color)
        draw = ImageDraw.Draw(img)

        if day == 1:
            line1 = "Dawn of"
            line2 = "The Final Day"
            line3 = f"-{hours} Hours Remain-"
        else:
            line1 = "Dawn of"
            line2 = f"The {self.ordinal_word(day)} Day"
            line3 = f"-{hours} Hours Remain-"

        _, y_title_top, _, y_title_bottom = self.font_middle.getbbox(line2)
        title_height = y_title_bottom - y_title_top
        title_y = (self.height - title_height) // 2

        self.draw_centered(draw, line1, title_y - 50, self.font_top)
        self.draw_centered(draw, line2, title_y - 20, self.font_middle)
        self.draw_centered(draw, line3, title_y + 90, self.font_bottom)

        return img

    def draw_centered(self, draw, text, y, font):
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) // 2
        draw.text((x, y), text, fill=self.text_color, font=font)

    def ordinal_word(self, n):
        return num2words(n, to="ordinal").capitalize()


class jeff(
    LancoCog,
    name="JeffVacation",
    description="Cog to manage Jeff's vacation countdown and related commands",
):
    def __init__(self, bot):
        super().__init__(bot)

    def get_remaining_time(self) -> timedelta:
        """Calculates the remaining time until the vacation starts or ends."""
        start_time = self.get_start_time()
        return_time = self.get_return_time()

        now = datetime.now(tz=pytz.timezone("US/Eastern"))

        if now < start_time:  # Vacation has not started yet
            return start_time - now
        elif now >= return_time:  # Vacation has already ended
            return timedelta(0)
        else:  # Vacation is ongoing
            return return_time - now

    def get_return_time(self) -> datetime:
        """Returns the time when the vacation ends."""
        return pytz.timezone("US/Eastern").localize(datetime(2025, 6, 2, 8, 0, 0))

    def get_start_time(self) -> datetime:
        """Returns the time when the vacation starts."""
        return pytz.timezone("US/Eastern").localize(datetime(2025, 5, 23, 17, 0, 0))

    @commands.command()
    async def vacation(self, ctx):
        """Shows how much time is left in the vacation."""
        user = await self.bot.fetch_user(297149191673741314)

        remaining = self.get_remaining_time()

        start_time = self.get_start_time()
        return_time = self.get_return_time()

        # first check if the vacation has not started yet
        if remaining.total_seconds() > (return_time - start_time).total_seconds():
            await ctx.send(
                f"{user.mention}, keep working! You're not on vacation yet. Time until vacation: **{remaining.days} days, {remaining.seconds // 3600} hours, {(remaining.seconds // 60) % 60} minutes, {remaining.seconds % 60} seconds**."
            )
            return

        # then check if the vacation has already ended
        if remaining.total_seconds() <= 0:
            await ctx.send(f"Vacation is already over! Welcome back {user.mention} 😎")
            return

        # build the time left string and exclude any zero values traversing the timedelta
        if remaining.days > 0:
            time_left = f"**{remaining.days} days**, "
        else:
            time_left = ""

        if remaining.seconds // 3600 > 0:
            time_left += f"**{remaining.seconds // 3600} hours**, "
        if (remaining.seconds // 60) % 60 > 0:
            time_left += f"**{(remaining.seconds // 60) % 60} minutes**, "
        if remaining.seconds % 60 > 0:
            time_left += f"**{remaining.seconds % 60} seconds**"

        if time_left.endswith(", "):
            time_left = time_left[:-2]

        dawn_screen = DawnScreen()

        total_hours = remaining.days * 24 + (remaining.seconds // 3600)

        img = dawn_screen.generate(day=remaining.days, hours=total_hours)

        cache_dir = os.path.join(self.get_cog_data_directory())
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        # randomly name the image to avoid conflicts
        filename = f"dawn_screen_{int(datetime.now().timestamp())}.png"

        img_path = os.path.join(cache_dir, filename)
        img.save(img_path)

        embed = discord.Embed(
            title=f"{user.display_name}'s Vacation",
            description=f"Time left in {user.mention}'s vacation:\n\n{time_left}\n\n**Returns: <t:{int(return_time.timestamp())}:F>**",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_image(url=f"attachment://{filename}")

        await ctx.send(embed=embed, file=discord.File(img_path))

        # Clean up the image file after sending
        if os.path.exists(img_path):
            os.remove(img_path)


async def setup(bot):
    await bot.add_cog(jeff(bot))
