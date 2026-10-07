import datetime

import discord
from cogs.lancocog import LancoCog
from discord import Embed, Interaction, Reaction, User, app_commands
from discord.ext import commands

from .models import ReactEvent


class ReactTrack(
    LancoCog,
    name="ReactTrack",
    description="Track reactions",
):
    g = app_commands.Group(
        name="reacttrack", description="ReactTrack commands", guild_only=True
    )

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    async def cog_load(self):
        await super().cog_load()
        self.bot.database.create_tables([ReactEvent])

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: Reaction, user: User):
        # self.logger.info(f"Reaction removed: {reaction.emoji}")

        ReactEvent.create(
            message_id=reaction.message.id,
            channel_id=reaction.message.channel.id,
            guild_id=reaction.message.guild.id,
            user_id=user.id,
            emoji=str(reaction.emoji),
            timestamp=reaction.message.created_at,
            added=False,
        )

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: User):
        # self.logger.info(f"Reaction added: {reaction.emoji}")

        ReactEvent.create(
            message_id=reaction.message.id,
            channel_id=reaction.message.channel.id,
            guild_id=reaction.message.guild.id,
            user_id=user.id,
            emoji=str(reaction.emoji),
            timestamp=reaction.message.created_at,
            added=True,
        )

    @g.command(name="today", description="Check reactions today for a user")
    async def view(self, interaction, user: User):
        # Timestamps are stored timezone-aware in UTC (message.created_at), so
        # the cutoff has to be aware too: SQLite compares them as text, and a
        # naive local time would shift the window by the UTC offset.
        now = discord.utils.utcnow()
        last_24_hours = now - datetime.timedelta(days=1)

        events = (
            ReactEvent.select()
            .where(
                ReactEvent.user_id == user.id,
                ReactEvent.added == True,
                ReactEvent.timestamp > last_24_hours,
                ReactEvent.guild_id == interaction.guild.id,
            )
            .order_by(ReactEvent.timestamp)
        )

        embed = Embed(
            title=f"Reactions",
            color=0x00FF00,
        )

        if not events or len(events) == 0:
            await interaction.response.send_message(
                "No reactions found", ephemeral=True
            )
            return

        emoji_counts = {}
        for event in events:
            if event.emoji not in emoji_counts:
                emoji_counts[event.emoji] = 0
            emoji_counts[event.emoji] += 1

        oldest_timestamp = events[0].timestamp

        # calculate reactions per hour, using the oldest timestamp as the start
        time_diff = now - oldest_timestamp
        hours = time_diff.total_seconds() / 3600
        emojis_per_hour = len(events) / hours if hours > 0 else len(events)

        emoji_counts = dict(
            sorted(emoji_counts.items(), key=lambda item: item[1], reverse=True)
        )

        desc = f"Reactions from {user.mention} in the last 24 hours:\n\n"

        num = 1
        for emoji, count in emoji_counts.items():
            desc += f"{num}: {emoji} - Used {count} times\n\n"
            num += 1

        desc += f"Total reactions: {len(events)}\n"
        desc += f"Reactions per hour: {emojis_per_hour:.2f}"

        embed.description = desc

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ReactTrack(bot))
