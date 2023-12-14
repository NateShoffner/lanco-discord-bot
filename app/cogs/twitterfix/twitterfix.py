import discord
from discord.ext import commands
from discord import app_commands
from .models import TwitterFixConfig

from cogs.lancocog import LancoCog


class TwitterFix(LancoCog):
    twitterfix_group = app_commands.Group(
        name="twitterfix", description="TwitterFix commands"
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.database.create_tables([TwitterFixConfig])

    @commands.Cog.listener()
    async def on_ready(self):
        print("TwitterFix cog loaded")
        await super().on_ready()

    @twitterfix_group.command(name="enable", description="Enable TwitterFix")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def enable(self, interaction: discord.Interaction):
        twitterfix_config, created = TwitterFixConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        twitterfix_config.enabled = True
        twitterfix_config.save()

        await interaction.response.send_message("TwitterFix enabled", ephemeral=True)

    @twitterfix_group.command(name="disable", description="Disable TwitterFix")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def disable(self, interaction: discord.Interaction):
        twitterfix_config, created = TwitterFixConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        twitterfix_config.enabled = False
        twitterfix_config.save()

        await interaction.response.send_message("TwitterFix disabled", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if "twitter.com" in message.content:
            twitterfix_config = TwitterFixConfig.get_or_none(guild_id=message.guild.id)
            if not twitterfix_config or not twitterfix_config.enabled:
                return

            link = message.content.split(" ")[0]
            link = link.replace("twitter.com", "fxtwitter.com")
            await message.channel.send(link)


async def setup(bot):
    await bot.add_cog(TwitterFix(bot))
