import discord
from discord.ext import commands


def _is_bot_owner_or_team_member(bot, user) -> bool:
    if bot.application.team:
        return user in bot.application.team.members
    return user.id == bot.application.owner.id


def _is_bot_owner_or_admin(bot, user, guild) -> bool:
    # Guild admin is meaningless outside a guild, and in a DM `guild` is
    # None while `user` is a User with no guild_permissions, so both checks
    # below would raise. Returning False makes this an ordinary check
    # failure, which the error handlers already ignore. The owner is
    # refused too: every command using this check acts on a guild.
    if guild is None:
        return False
    if _is_bot_owner_or_team_member(bot, user):
        return True
    if guild.owner_id == user.id:
        return True
    if user.guild_permissions.administrator:
        return True
    return False


def is_bot_owner_or_team_member(interaction: discord.Interaction):
    return _is_bot_owner_or_team_member(interaction.client, interaction.user)


def is_bot_owner():
    """App command check: bot owner or team member. Prefix commands need is_bot_owner_ctx()."""

    def predicate(interaction: discord.Interaction):
        return is_bot_owner_or_team_member(interaction)

    return discord.app_commands.check(predicate)


def is_bot_owner_or_admin():
    """App command check: bot owner, guild owner, or guild admin. Prefix commands need is_bot_owner_or_admin_ctx()."""

    def predicate(interaction: discord.Interaction):
        return _is_bot_owner_or_admin(
            interaction.client, interaction.user, interaction.guild
        )

    return discord.app_commands.check(predicate)


def is_bot_owner_ctx():
    """Prefix command counterpart of is_bot_owner()."""

    def predicate(ctx: commands.Context):
        return _is_bot_owner_or_team_member(ctx.bot, ctx.author)

    return commands.check(predicate)


def is_bot_owner_or_admin_ctx():
    """Prefix command counterpart of is_bot_owner_or_admin()."""

    def predicate(ctx: commands.Context):
        return _is_bot_owner_or_admin(ctx.bot, ctx.author, ctx.guild)

    return commands.check(predicate)
