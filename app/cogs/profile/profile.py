import urllib.parse
from os import name

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import ProfileLink, UserProfile, UserProfilesConfig


class ProfileModal(discord.ui.Modal, title="Profile Details"):
    name_input = discord.ui.TextInput(
        label="Name:",
        placeholder="Name",
        style=discord.TextStyle.short,
        required=True,
    )

    description_input = discord.ui.TextInput(
        label="Description:",
        placeholder="Description",
        style=discord.TextStyle.long,
        required=True,
    )

    nsfw_input = discord.ui.TextInput(
        label="Does this profile contain NSFW content?",
        placeholder="Y/N",
        style=discord.TextStyle.short,
        max_length=1,
        required=True,
        default="N",
    )

    def __init__(self, profile: UserProfile = None):
        super().__init__(timeout=None)
        self.profile = profile
        if profile:
            self.name_input.default = profile.name
            self.description_input.default = profile.description
            self.nsfw_input.default = "Y" if profile.is_nsfw else "N"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        edit = self.profile is not None

        if not edit:
            profile, created = UserProfile.get_or_create(
                user_id=interaction.user.id, name=self.name_input.value
            )
            if not created:
                await interaction.response.send_message(
                    f"You already have a profile with the name {name}", ephemeral=True
                )
                return
            self.profile = profile

        self.profile.name = self.name_input.value
        self.profile.description = self.description_input.value
        self.profile.is_nsfw = self.nsfw_input.value.lower() == "y"
        self.profile.save()

        await interaction.response.send_message(
            f"{'Updated' if edit else 'Created'} profile {self.profile.name}",
            ephemeral=True,
        )


class UserProfiles(LancoCog, name="UserProfiles", description="Custom user profiles"):
    profiles_group = app_commands.Group(name="profile", description="User profiles")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([UserProfile, ProfileLink, UserProfilesConfig])

    @profiles_group.command(
        name="toggle", description="Toggle user profiles for this server"
    )
    @is_bot_owner_or_admin()
    async def toggle(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        config, created = UserProfilesConfig.get_or_create(guild_id=guild_id)
        config.enabled = not config.enabled
        config.save()

        await interaction.response.send_message(
            f"User profiles are now {'enabled' if config.enabled else 'disabled'}"
        )

    @profiles_group.command(name="view", description="View a user's profile")
    async def view(self, interaction, user: discord.Member, name: str):
        if not await self.prompt_profiles_enabled(interaction):
            return

        profile = self.get_profile_by_name(user.id, name)
        if not profile:
            await interaction.response.send_message(
                f"{user.name} does not have a profile with the name {name}",
                ephemeral=True,
            )
            return

        await self.show_profile(interaction, profile)

    @profiles_group.command(name="create", description="Create your profile")
    async def create_profile(self, interaction: discord.Interaction):
        if not await self.prompt_profiles_enabled(interaction):
            return

        modal = ProfileModal()
        await interaction.response.send_modal(modal)

    @profiles_group.command(name="edit", description="Edit your profile")
    async def edit_profile(self, interaction: discord.Interaction, name: str):
        if not await self.prompt_profiles_enabled(interaction):
            return

        profile = UserProfile.get_or_none(user_id=interaction.user.id, name=name)
        if not profile:
            await interaction.response.send_message(
                "You do not have a profile to edit", ephemeral=True
            )
            return

        modal = ProfileModal(profile)
        await interaction.response.send_modal(modal)

    @profiles_group.command(name="list", description="List your profiles")
    async def list_profiles(self, interaction: discord.Interaction):
        if not await self.prompt_profiles_enabled(interaction):
            return

        profiles = UserProfile.select().where(
            UserProfile.user_id == interaction.user.id
        )
        if not profiles:
            await interaction.response.send_message("You do not have any profiles")
            return

        embed = discord.Embed(title="Your profiles")
        for count, profile in enumerate(profiles):
            name = profile.name
            if profile.is_default:
                name += " (default)"
            embed.add_field(name=count + 1, value=name, inline=False)

        await interaction.response.send_message(embed=embed)

    @profiles_group.command(name="default", description="Set your default profile")
    async def default_profile(self, interaction: discord.Interaction, name: str):
        if not await self.prompt_profiles_enabled(interaction):
            return

        profile = self.get_profile_by_name(interaction.user.id, name)
        if not profile:
            await interaction.response.send_message(
                f"You do not have a profile with the name {name}", ephemeral=True
            )
            return

        profile.is_default = True
        profile.save()

        await interaction.response.send_message(
            f"{profile.name} is now your default profile"
        )

    @profiles_group.command(name="me", description="View your default profile")
    async def myprofile(self, interaction: discord.Interaction):
        if not await self.prompt_profiles_enabled(interaction):
            return

        profile = UserProfile.get_or_none(user_id=interaction.user.id, is_default=True)
        if not profile:
            await interaction.response.send_message(
                "You do not have a default profile", ephemeral=True
            )
            return

        await self.show_profile(interaction, profile)

    @profiles_group.command(name="delete", description="Delete your profile")
    async def delete_profile(self, interaction: discord.Interaction, name: str):
        if not await self.prompt_profiles_enabled(interaction):
            return

        profile = self.get_profile_by_name(interaction.user.id, name)
        if not profile:
            await interaction.response.send_message(
                f"You do not have a profile with the name {name}", ephemeral=True
            )
            return

        profile.delete_instance()
        await interaction.response.send_message("Profile deleted", ephemeral=True)

    @profiles_group.command(
        name="link", description="Link your profile to another service"
    )
    async def link_profile(
        self, interaction: discord.Interaction, profile: str, name: str, url: str
    ):
        if not await self.prompt_profiles_enabled(interaction):
            return

        profile = self.get_profile_by_name(interaction.user.id, profile)
        if not profile:
            await interaction.response.send_message(
                f"You do not have a profile with the name {profile}", ephemeral=True
            )
            return

        try:
            url = urllib.parse.urlparse(url).geturl()
        except:
            await interaction.response.send_message("Invalid URL", ephemeral=True)
            return

        link, created = ProfileLink.get_or_create(
            user_id=interaction.user.id, service=name, url=url
        )
        if not created:
            link.url = url
            link.save()

        profile.links = link
        profile.save()

        await interaction.response.send_message(f"Linked {name}")

    @profiles_group.command(
        name="unlink", description="Unlink your profile from another service"
    )
    async def unlink_profile(
        self, interaction: discord.Interaction, profile: str, name: str
    ):
        if not await self.prompt_profiles_enabled(interaction):
            return
        await interaction.response.send_message(f"Unlinked {name}")

    async def show_profile(
        self, interaction: discord.Interaction, profile: UserProfile
    ):
        embed = discord.Embed(title=profile.name, description=profile.description)
        embed.set_author(
            name=interaction.user.name, icon_url=interaction.user.avatar.url
        )
        embed.timestamp = profile.last_updated
        await interaction.response.send_message(embed=embed)

    def get_profile_by_name(self, user_id: int, name: str) -> UserProfile:
        return UserProfile.get_or_none(user_id=user_id, name=name)

    async def prompt_profiles_enabled(self, interaction: discord.Interaction):
        if not self.profiles_enabled(interaction.guild.id):
            await interaction.response.send_message(
                "User profiles are not enabled for this server", ephemeral=True
            )
            return False
        return True

    def profiles_enabled(self, guild_id: int) -> bool:
        config = UserProfilesConfig.get_or_none(guild_id=guild_id)
        return config and config.enabled


async def setup(bot):
    await bot.add_cog(UserProfiles(bot))
