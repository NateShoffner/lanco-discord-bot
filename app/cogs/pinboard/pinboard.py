import discord
import peewee
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands

from .models import PinboardPost


class Pinboard(LancoCog, name="Pinboard", description="Pinboard cog"):
    g = app_commands.Group(name="pinboard", description="Pinboard commands")

    MAX_PINNED_MESSAGES = 30  # Maximum number of pinned messages per user, per guild

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.register_context_menu(
            name="Pin Message", callback=self.ctx_menu, errback=self.ctx_menu_error
        )
        self.bot.database.create_tables([PinboardPost])

    async def ctx_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        # check pinned count for user/guild
        pinned_count = (
            PinboardPost.select()
            .where(
                PinboardPost.pin_owner_id == interaction.user.id
                and PinboardPost.guild_id == interaction.guild.id
            )
            .count()
        )
        if pinned_count >= self.MAX_PINNED_MESSAGES:
            await interaction.response.send_message(
                "You have reached the maximum number of pinned messages", ephemeral=True
            )
            return

        try:
            config, create = PinboardPost.get_or_create(
                message_id=message.id,
                guild_id=interaction.guild.id,
                pin_owner_id=interaction.user.id,
                channel_id=message.channel.id,
                author_id=message.author.id,
                created_at=message.created_at,
                pinned_at=discord.utils.utcnow(),
            )
        except peewee.IntegrityError as exc:
            await interaction.response.send_message(
                "Message already pinned", ephemeral=True
            )
            return

        if create:
            await interaction.response.send_message(
                f"Pinned message: {message.jump_url}"
            )
        else:
            await interaction.response.send_message(
                "Message already pinned", ephemeral=True
            )

    async def ctx_menu_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(f"Error: {error}", ephemeral=True)

    @g.command(name="list", description="List pinned messages")
    async def list(self, interaction: discord.Interaction):
        pinned_message_ids = await self.get_pinned_message_ids(
            interaction.user, interaction.guild
        )
        if not pinned_message_ids:
            await interaction.response.send_message(
                "No pinned messages", ephemeral=True
            )
            return

        pinned_messages = await self.get_pinned_messages(
            interaction.user, interaction.guild
        )

        body = ""
        for i, pinned_message in enumerate(pinned_messages):
            excerpt = pinned_message.content[:50]
            body += f"{i+1}. {excerpt} [View]({pinned_message.jump_url})\n"

        embed = discord.Embed(
            title=f"Pinned Messages ({len(pinned_messages)})", description=body
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @g.command(name="unpin", description="Unpin a message")
    async def unpin(self, interaction: discord.Interaction, message_number: int):
        pinned_message_ids = await self.get_pinned_message_ids(
            interaction.user, interaction.guild
        )

        if not pinned_message_ids:
            await interaction.response.send_message(
                "No pinned messages", ephemeral=True
            )
            return

        if message_number < 1 or message_number > len(pinned_message_ids):
            await interaction.response.send_message(
                "Invalid message number", ephemeral=True
            )
            return

        pinned_message = pinned_message_ids[message_number - 1]
        PinboardPost.delete().where(PinboardPost.message_id == pinned_message).execute()

        await interaction.response.send_message("Message unpinned", ephemeral=True)

    async def get_pinned_message_ids(self, user: discord.User, guild: discord.Guild):
        pinned_messages = PinboardPost.select().where(
            PinboardPost.pin_owner_id == user.id and PinboardPost.guild_id == guild.id
        )
        if not pinned_messages:
            return None

        return [pinned_message.message_id for pinned_message in pinned_messages]

    async def get_pinned_messages(self, user: discord.User, guild: discord.Guild):
        pinned_messages = PinboardPost.select().where(
            PinboardPost.pin_owner_id == user.id and PinboardPost.guild_id == guild.id
        )
        if not pinned_messages:
            return None

        fetched_messages = []
        for pinned_message in pinned_messages:
            fetched_message = await self.bot.get_channel(
                pinned_message.channel_id
            ).fetch_message(pinned_message.message_id)
            fetched_messages.append(fetched_message)

        return fetched_messages


async def setup(bot):
    await bot.add_cog(Pinboard(bot))
