import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import FishbowlConfig


class Fishbowl(LancoCog, name="Fishbowl", description="Fishbowl cog"):

    g = app_commands.Group(name="fishbowl", description="Fishbowl commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([FishbowlConfig])

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        fishbowl_config = FishbowlConfig.get_or_none(channel_id=message.channel.id)
        if not fishbowl_config:
            return

        self.logger.info(
            f"Marking message in fishbowl channel {message.channel.id} for deletion in {fishbowl_config.ttl} seconds"
        )
        await message.delete(delay=fishbowl_config.ttl)

    @g.command(name="set", description="Designate a channel as a fishbowl")
    @is_bot_owner_or_admin()
    async def set_fishbowl(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        delete_delay: int = 30,
    ):
        config, created = FishbowlConfig.get_or_create(channel_id=channel.id)
        config.ttl = delete_delay
        config.save()
        await interaction.response.send_message(
            f"Channel {channel.mention} set as fishbowl with a TTL of {delete_delay} seconds",
            ephemeral=True,
        )

    @g.command(name="remove", description="Remove a channel as a fishbowl")
    @is_bot_owner_or_admin()
    async def remove_fishbowl(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        fishbowl_config = FishbowlConfig.get_or_none(channel_id=channel.id)
        if not fishbowl_config:
            await interaction.response.send_message(
                f"Channel {channel.mention} is not a fishbowl", ephemeral=True
            )
            return

        fishbowl_config.delete_instance()
        await interaction.response.send_message(
            f"Channel {channel.mention} removed as fishbowl", ephemeral=True
        )

    @g.command(name="list", description="List all fishbowl channels")
    @is_bot_owner_or_admin()
    async def list_fishbowls(self, interaction: discord.Interaction):
        fishbowl_configs = FishbowlConfig.select()
        if not fishbowl_configs:
            await interaction.response.send_message(
                "No fishbowl channels", ephemeral=True
            )
            return

        channels = [
            f"<#{fishbowl_config.channel_id}>" for fishbowl_config in fishbowl_configs
        ]
        await interaction.response.send_message("\n".join(channels), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Fishbowl(bot))
