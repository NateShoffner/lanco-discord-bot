import discord
from cogs.lancocog import LancoCog
from discord.ext import commands
from utils.tracked_message import track_message_ids


class EmoteTools(LancoCog, name="EmoteTools", description="Emote and sticker tools"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.register_context_menu(
            name="Emote Details", callback=self.ctx_menu, errback=self.ctx_menu_error
        )

    async def ctx_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await self.send_info(interaction, message)

    async def ctx_menu_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            f"An error occurred: {error}", ephemeral=True
        )

    @track_message_ids()
    async def send_info(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> discord.Message:
        if await self.is_emote(message):
            emote = await self.get_emote_from_message(message)
            embed = await self.build_emote_embed(interaction, emote[0])
            await interaction.response.send_message(embed=embed)

        elif await self.is_sticker(message):
            sticker = await self.get_stickers_from_message(message)
            embed = await self.build_sticker_embed(interaction, sticker[0])
            await interaction.response.send_message(embed=embed)

    async def get_stickers_from_message(
        self, message: discord.Message
    ) -> list[discord.Sticker]:
        return message.stickers

    async def get_emote_from_message(
        self, message: discord.Message
    ) -> list[discord.Emoji]:
        return message.guild.emojis

    async def is_emote(self, message: discord.Message) -> bool:
        return bool(message.guild and message.content.startswith("<")) or bool(
            message.guild and message.content.startswith(":")
        )

    async def is_sticker(self, message: discord.Message) -> bool:
        return bool(message.stickers)

    async def build_sticker_embed(
        self, ctx: commands.Context, sticker: discord.Sticker = None
    ) -> discord.Embed:
        if not sticker:
            return discord.Embed(title="Sticker not found")

        embed = discord.Embed(
            title=f"Sticker Info: {sticker.name}", color=discord.Color.blurple()
        )

        embed.add_field(name="ID", value=sticker.id)
        # embed.add_field(name="Description", value=sticker.description)
        embed.add_field(name="URL", value=sticker.url, inline=False)

        return embed

    async def build_emote_embed(
        self, ctx: commands.Context, emote: discord.Emoji = None
    ) -> discord.Embed:
        if not emote:
            return discord.Embed(title="Emote not found")

        embed = discord.Embed(
            title=f"Emote Info: {emote.name}", color=discord.Color.blurple()
        )

        embed.add_field(name="ID", value=emote.id)
        embed.add_field(name="Animated", value=f"{'Yes' if emote.animated else 'No'}")
        embed.add_field(name="URL", value=emote.url, inline=False)

        return embed


async def setup(bot):
    await bot.add_cog(EmoteTools(bot))
