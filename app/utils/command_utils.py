import discord


def is_bot_owner():
    def predicate(interaction: discord.Interaction):
        return interaction.user.id == interaction.client.application.owner.id

    return discord.app_commands.check(predicate)


def is_bot_owner_or_admin():
    def predicate(interaction: discord.Interaction):
        if interaction.user.id == interaction.client.application.owner.id:
            return True
        if interaction.guild.owner_id == interaction.user.id:
            return True
        if interaction.user.guild_permissions.administrator:
            return True
        return False

    return discord.app_commands.check(predicate)
