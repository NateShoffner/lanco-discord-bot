import discord


def is_bot_owner_or_team_member(interaction: discord.Interaction):
    if interaction.client.application.team:
        return interaction.user in interaction.client.application.team.members
    return interaction.user.id == interaction.client.application.owner.id


def is_bot_owner():
    def predicate(interaction: discord.Interaction):
        return is_bot_owner_or_team_member(interaction)

    return discord.app_commands.check(predicate)


def is_bot_owner_or_admin():
    def predicate(interaction: discord.Interaction):
        if is_bot_owner_or_team_member(interaction):
            return True
        if interaction.guild.owner_id == interaction.user.id:
            return True
        if interaction.user.guild_permissions.administrator:
            return True
        return False

    return discord.app_commands.check(predicate)
