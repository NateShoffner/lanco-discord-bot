import calendar
import datetime

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands, tasks
from utils.command_utils import is_bot_owner_or_admin

from .models import BirthdayAnnouncementConfig, BirthdayUser


class BirthdayModal(discord.ui.Modal, title="Set your birthday"):
    date_input = discord.ui.TextInput(
        label="Enter your birthday:",
        placeholder="YYYY-MM-DD",
        style=discord.TextStyle.short,
        required=True,
    )

    def __init__(self, user: discord.User):
        super().__init__(timeout=None)
        self.user = user

    async def on_submit(self, interaction: discord.Interaction) -> None:
        date_str = self.date_input.value
        date = None
        try:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            await interaction.response.send_message(
                "Invalid date format", ephemeral=True
            )
            return

        user, created = BirthdayUser.get_or_create(
            guild_id=interaction.guild.id, user_id=interaction.user.id
        )
        user.date = date.date()
        user.save()

        date_str = date.strftime("%B %d")
        await interaction.response.send_message(
            f"Your birthday has been set to {date_str}", ephemeral=True
        )


class Birthday(LancoCog, name="Birthday", description="Wish a user a happy birthday"):
    bday_group = app_commands.Group(name="bday", description="Birthday commands")

    est = datetime.timezone(datetime.timedelta(hours=-5))
    daily_announcement_time = (datetime.time(hour=7, tzinfo=est),)

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([BirthdayUser, BirthdayAnnouncementConfig])
        self.daily_bday_task.start()

    def get_todays_birthday_users(self):
        return BirthdayUser.select().where(
            BirthdayUser.date.month == datetime.datetime.now().month,
            BirthdayUser.date.day == datetime.datetime.now().day,
        )

    @tasks.loop(time=daily_announcement_time)
    async def daily_bday_task(self):
        birthday_users = self.get_todays_birthday_users()

        if not birthday_users:
            return

        for user in birthday_users:
            config = BirthdayAnnouncementConfig.get_or_none(guild_id=user.guild_id)
            if not config:
                continue

            channel = self.bot.get_channel(config.channel_id)
            if not channel:
                continue

            await channel.send(f"Happy birthday <@{user.user_id}>!")

    @bday_group.command(name="set", description="Set your birthday")
    async def set_birthay(self, interaction: discord.Interaction):
        modal = BirthdayModal(interaction.user)
        await interaction.response.send_modal(modal)

    @bday_group.command(name="remove", description="Remove your birthday")
    async def remove_birthday(self, interaction: discord.Interaction):
        user = BirthdayUser.get_or_none(
            guild_id=interaction.guild.id, user_id=interaction.user.id
        )
        if not user:
            await interaction.response.send_message(
                "You don't have a birthday set", ephemeral=True
            )
            return

        user.delete_instance()
        await interaction.response.send_message(
            "Your birthday has been removed", ephemeral=True
        )

    @bday_group.command(
        name="channel", description="Set the channel for birthday announcements"
    )
    @is_bot_owner_or_admin()
    async def set_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        config, created = BirthdayAnnouncementConfig.get_or_create(
            guild_id=interaction.guild.id, channel_id=channel.id
        )

        await interaction.response.send_message(
            f"Birthday announcements will be made in {channel.mention}"
        )

    @bday_group.command(
        name="list", description="Show all birthdays for the specified or current month"
    )
    async def show_all_birthdays(
        self, interaction: discord.Interaction, month: str = None
    ):
        if month:
            try:
                month = list(calendar.month_name).index(month)
                month = int(month)
            except ValueError:
                await interaction.response.send_message("Please enter a valid month")
                return
        else:
            month = datetime.datetime.now().month

        birthday_users = BirthdayUser.select().where(BirthdayUser.date.month == month)

        if not birthday_users:
            await interaction.response.send_message(
                f"No birthdays for the month of {calendar.month_name[month]}"
            )
            return

        embed = discord.Embed(title=f"Birthdays for {calendar.month_name[month]}")
        bday_list = []
        birthday_users = sorted(birthday_users, key=lambda u: u.date.strftime("%d"))
        for u in birthday_users:
            user = self.bot.get_user(u.user_id)
            bday_list.append(f"{user.display_name} - {u.date.strftime('%B %d')}")
        embed.description = "\n".join(bday_list)

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Birthday(bot))
