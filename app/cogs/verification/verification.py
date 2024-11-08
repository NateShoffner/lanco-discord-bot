from enum import Enum

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from discord.utils import get

from .models import VerificationConfig, VerificationRequest


class VerificationStatus(Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    DENIED = "Denied"


class Verification(
    LancoCog,
    name="Verification",
    description="Verification cog",
):

    g = app_commands.Group(name="verification", description="Verification commands")

    APPROVAL_EMOJI = "✅"
    DENIAL_EMOJI = "❌"

    def __init__(self, bot):
        super().__init__(bot)
        self.bot.database.create_tables([VerificationConfig, VerificationRequest])

    @g.command(name="threshold", description="Set the vote threshold.")
    @commands.has_permissions(administrator=True)
    async def threshold(self, interaction: discord.Interaction, threshold: int):
        """
        Set the vote threshold.
        """
        config, created = VerificationConfig.get_or_create(
            guild_id=interaction.guild_id
        )
        config.vote_threshold = threshold
        config.save()

        await interaction.response.send_message(
            f"Vote threshold set to {threshold}", ephemeral=True
        )

    @g.command(name="role", description="Set the role to be given to verified users.")
    @commands.has_permissions(administrator=True)
    async def role(self, interaction: discord.Interaction, role: discord.Role):
        """
        Set the role to be given to verified users.
        """

        config, created = VerificationConfig.get_or_create(
            guild_id=interaction.guild_id
        )
        config.verified_role_id = role.id
        config.save()

        await interaction.response.send_message(
            f"Verified role set to {role.mention}", ephemeral=True
        )

    @g.command(name="modchannel", description="Set the mod channel.")
    @commands.has_permissions(administrator=True)
    async def modchannel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        """
        Set the mod channel.
        """

        config, created = VerificationConfig.get_or_create(
            guild_id=interaction.guild_id
        )
        config.mod_channel_id = channel.id
        config.save()

        await interaction.response.send_message(
            f"Mod channel set to {channel.mention}", ephemeral=True
        )

    async def save_votes(
        self, reaction: discord.Reaction
    ) -> tuple[VerificationConfig, VerificationRequest]:
        config = VerificationConfig.get_or_none(guild_id=reaction.message.guild.id)
        if config is None:
            return None

        request = VerificationRequest.get_or_none(message_id=reaction.message.id)
        if request is None:
            return None

        if request.pending is False:
            return None

        request.approvals = 0
        request.denials = 0

        for reaction in reaction.message.reactions:
            if reaction.emoji == self.APPROVAL_EMOJI:
                request.approvals = reaction.count - 1
            elif reaction.emoji == self.DENIAL_EMOJI:
                request.denials = reaction.count - 1
        request.save()

        return (config, request)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        if reaction.emoji not in [self.APPROVAL_EMOJI, self.DENIAL_EMOJI]:
            return

        await self.save_votes(reaction)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if reaction.emoji not in [self.APPROVAL_EMOJI, self.DENIAL_EMOJI]:
            return

        config, request = await self.save_votes(reaction)

        finalized = False
        status = VerificationStatus.PENDING
        if request.approvals >= config.vote_threshold:
            finalized = True
            verified_role = get(
                reaction.message.guild.roles, id=config.verified_role_id
            )
            member = get(reaction.message.guild.members, id=request.user_id)
            await member.add_roles(verified_role)
            status = VerificationStatus.APPROVED
        elif request.denials >= config.vote_threshold:
            finalized = True
            member = get(reaction.message.guild.members, id=request.user_id)
            status = VerificationStatus.DENIED

        request.pending = not finalized
        request.save()

        if finalized:
            user_notified = False
            try:
                if request.approvals >= config.vote_threshold:
                    await user.send(
                        f"You have been verified in {reaction.message.guild.name}."
                    )
                else:
                    await user.send(
                        f"Your verification request was denied in {reaction.message.guild.name}."
                    )
                user_notified = True
            except discord.Forbidden:
                pass

            msg = await reaction.message.channel.fetch_message(request.message_id)
            embed = self.build_embed(user, status, user_notified)
            await msg.edit(embed=embed)

    @app_commands.command(
        name="unverify",
        description="Remove verification",
    )
    async def unverify(self, interaction: discord.Interaction):
        """
        Command for users to remove verification.
        """
        config = VerificationConfig.get_or_none(guild_id=interaction.guild_id)
        user = interaction.user

        if not await self.is_user_verified(user, config.verified_role_id):
            await interaction.response.send_message(
                "You are not verified.", ephemeral=True
            )
            return

        verified_role = get(user.guild.roles, id=config.verified_role_id)
        await user.remove_roles(verified_role)
        await interaction.response.send_message("Verification removed.", ephemeral=True)

    @app_commands.command(
        name="verify",
        description="Request verification",
    )
    async def verify(self, interaction: discord.Interaction):
        """
        Command for users to request verification.
        """
        config = VerificationConfig.get_or_none(guild_id=interaction.guild_id)

        if config is None:
            await interaction.response.send_message(
                "Verification not set up.", ephemeral=True
            )
            return

        if config.mod_channel_id is None:
            await interaction.response.send_message(
                "Mod channel not set.", ephemeral=True
            )
            return

        mod_channel = self.bot.get_channel(config.mod_channel_id)

        if mod_channel is None:
            await interaction.response.send_message("Mod channel not found.")
            return

        user = interaction.user

        if await self.is_user_verified(user, config.verified_role_id):
            await interaction.response.send_message(
                "You are already verified.", ephemeral=True
            )
            return

        if await self.is_verification_pending(user):
            await interaction.response.send_message(
                "You already have a pending verification request.", ephemeral=True
            )
            return

        embed = self.build_embed(user, VerificationStatus.PENDING, False)

        message = await mod_channel.send(embed=embed)
        await message.add_reaction(self.APPROVAL_EMOJI)
        await message.add_reaction(self.DENIAL_EMOJI)

        request = VerificationRequest.create(
            user_id=user.id, message_id=message.id, guild_id=interaction.guild_id
        )

        await interaction.response.send_message(
            "Verification request sent.", ephemeral=True
        )

    def build_embed(
        self, user: discord.User, status: VerificationStatus, notified: bool
    ) -> discord.Embed:
        """Build the verification request embed"""

        embed = discord.Embed(
            title="Verification Request",
            description=f"{user.mention} has requested verification.",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=user.avatar.url)

        embed.add_field(name="ID", value=user.id, inline=False)
        embed.add_field(name="Username", value=user.name, inline=False)

        relative_age = discord.utils.utcnow() - user.created_at
        relative_server_age = discord.utils.utcnow() - user.joined_at

        embed.add_field(
            name="Account Created",
            value=f"{user.created_at.strftime('%B %d %Y %I:%M%p')} UTC\n({relative_age.days} days ago)",
            inline=False,
        )
        embed.add_field(
            name="Joined Server",
            value=f"{user.joined_at.strftime('%B %d %Y %I:%M%p')} UTC\n({relative_server_age.days} days ago)",
            inline=False,
        )

        embed.add_field(name="Status", value=status.value, inline=False)

        if status == VerificationStatus.PENDING:
            embed.add_field(
                name="Instructions",
                value=f"React with {self.APPROVAL_EMOJI} to approve, or {self.DENIAL_EMOJI} to deny.",
                inline=False,
            )
        else:
            embed.add_field(
                name="Notified", value="Yes" if notified else "No", inline=False
            )

        return embed

    async def is_user_verified(self, user: discord.User, role_id: int):
        """Check if a user is verified"""
        verified_role = get(user.guild.roles, id=role_id)
        if verified_role is None:
            return False
        return verified_role in user.roles

    async def is_verification_pending(self, user: discord.User):
        """Check if a user has a pending verification request"""
        request = VerificationRequest.get_or_none(user_id=user.id)
        if request is None:
            return False
        return request.pending


async def setup(bot):
    await bot.add_cog(Verification(bot))
