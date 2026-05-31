import datetime

import dateparser
from cogs.lancocog import LancoCog
from discord.ext import commands, tasks

from .models import Reminder


class RemindMe(
    LancoCog,
    name="RemindMe",
    description="Reminds a user of something after a specified duration",
):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([Reminder])
        self.reminders = []

    def cog_unload(self):
        self.load_daily_reminders.cancel()
        self.issue_reminders.cancel()

    async def cog_load(self):
        await self._load_reminders()
        self.load_daily_reminders.start()
        self.issue_reminders.start()

    async def _load_reminders(self):
        """Load all pending (unissued) reminders into memory."""
        reminders = list(Reminder.select().where(Reminder.issued == False))
        self.reminders = reminders
        self.logger.info(f"Loaded {len(reminders)} pending reminders")

    @tasks.loop(hours=24)
    async def load_daily_reminders(self):
        """Refresh the in-memory reminder list once a day."""
        await self._load_reminders()

    @tasks.loop(seconds=10)
    async def issue_reminders(self):
        now = datetime.datetime.now()
        due = [r for r in self.reminders if r.due_at <= now]

        for reminder in due:
            channel = self.bot.get_channel(reminder.channel_id)
            if channel:
                await channel.send(
                    f"<@{reminder.user_id}> Reminder: {reminder.message}"
                )
            else:
                self.logger.warning(
                    f"Could not find channel {reminder.channel_id} for reminder {reminder.id}"
                )

            reminder.issued = True
            reminder.save()
            self.logger.info(f"Reminder issued: {reminder.message}")

        if due:
            self.reminders = [r for r in self.reminders if not r.issued]

    @commands.command(
        name="remindme",
        description="Reminds you of something after a specified duration",
    )
    async def remindme(self, ctx: commands.Context, duration: str, *, reminder: str):
        """Reminds you of something after a specified duration. Example: !remindme 2h take out the trash"""

        remind_time = dateparser.parse(
            duration, settings={"PREFER_DATES_FROM": "future"}
        )

        if remind_time is None:
            await ctx.send(
                "Invalid duration. Try something like `2h`, `30m`, or `tomorrow`."
            )
            return

        now = datetime.datetime.now()
        delta = remind_time - now

        if delta.total_seconds() <= 0:
            await ctx.send(
                "That time is in the past. Try something like `2h`, `30m`, or `tomorrow`."
            )
            return

        r = Reminder.create(
            user_id=ctx.author.id,
            channel_id=ctx.channel.id,
            guild_id=ctx.guild.id,
            set_at=now,
            due_at=remind_time,
            message=reminder,
        )

        self.reminders.append(r)

        formatted_time = remind_time.strftime("%B %d, %Y at %I:%M %p")
        await ctx.send(f"Got it! I'll remind you on {formatted_time}: **{reminder}**")


async def setup(bot):
    await bot.add_cog(RemindMe(bot))
