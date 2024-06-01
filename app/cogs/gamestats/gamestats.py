import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands


class GameStats(LancoCog, name="GameStats", description="Game stats for the server"):

    game_stats_group = app_commands.Group(
        name="gamestats", description="Game stat commands"
    )

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @game_stats_group.command(name="all", description="All games")
    async def all_games(self, interaction: discord.Interaction):
        playing_members = await self.get_playing_members(interaction)

        game_dict = {}
        for member in playing_members:
            game_name = member.activity.name
            if game_name not in game_dict:
                game_dict[game_name] = 1
            else:
                game_dict[game_name] += 1

        sorted_games = sorted(game_dict.items(), key=lambda x: x[1], reverse=True)

        desc = (
            "No Gamers Found :("
            if len(playing_members) == 0
            else "Number of people playing each game:\n"
        )

        for game_name, count in sorted_games:
            desc += f"\n**{game_name}**: {count}"

        embed = discord.Embed(
            title="Game Stats", description=desc, color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    async def get_playing_members(self, ctx: commands.Context) -> list[discord.Member]:
        members = ctx.guild.members
        playing_members = []
        for member in members:

            if member.bot:
                continue

            if (
                member.activity is not None
                and member.activity.type == discord.ActivityType.playing
            ):
                playing_members.append(member)
        return playing_members

    async def get_game_members(
        self, ctx: commands.Context, game_name: str
    ) -> list[discord.Member]:
        members = ctx.guild.members
        game_members = []
        for member in members:
            if member.activity is not None:
                if member.activity.name == game_name:
                    game_members.append(member)
        return game_members


async def setup(bot):
    await bot.add_cog(GameStats(bot))
