"""
rolestats Cog

Description:
rolestats cog
"""

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands


class RoleStats(
    LancoCog,
    name="RoleStats",
    description="RoleStats cog",
):
    g = app_commands.Group(name="rolestats", description="RoleStats commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @g.command(
        name="stats",
        description="Get role stats",
    )
    async def stats(self, interaction: discord.Interaction, role: discord.Role):
        """Get role stats"""
        embed = discord.Embed(
            title="Role Stats",
            description=f"Stats for {role.name}",
            color=role.color,
        )
        embed.add_field(name="Role ID", value=role.id, inline=False)
        embed.add_field(name="Member Count", value=len(role.members), inline=False)
        embed.add_field(name="Color", value=role.color, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        users = []
        for member in role.members:
            users.append(f"{member.name}#{member.discriminator}")

        if len(users) > 0:
            embed = discord.Embed(
                title="Role Members",
                description="\n".join(users),
                color=role.color,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(RoleStats(bot))
