import discord
from cogs.lancocog import LancoCog
from discord import TextChannel, app_commands
from discord.ext import commands, tasks
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from utils.command_utils import is_bot_owner_or_admin
from utils.message_utils import get_user_messages


class ChannelDiscussion(BaseModel):
    topics: list[str] = Field(
        ..., description="List of topics being discussed in the channel"
    )
    suggested_name: str = Field(
        ...,
        description="Suggested channel name based on topics, hyphen-separated, alphanumeric only, and without stopwords or spaces",
    )


class ADHDChannel(
    LancoCog,
    name="ADHDChannel",
    description="Updates the channel name and topic based on the current discussion",
):
    adhd_channels = []  # TODO make this persistent

    g = app_commands.Group(name="adhd", description="ADHD Channel commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.agent = Agent(
            model="openai:gpt-4o",
            system_prompt="You are a helpful assistant that analyzes channel discussions and determines trending topics.",
            output_type=ChannelDiscussion,
        )

    @commands.Cog.listener()
    async def on_ready(self):
        await super().on_ready()
        self.update_channel_name.change_interval(seconds=30)
        self.update_channel_name.start()

    @g.command(
        name="toggle",
        description="Toggle the ADHD channel functionality for the current channel",
    )
    @is_bot_owner_or_admin()
    async def toggle(self, interaction: discord.Interaction):
        """Toggle the ADHD channel functionality for the current channel"""
        channel = interaction.channel
        if channel.id in self.adhd_channels:
            self.adhd_channels.remove(channel.id)
            await interaction.response.send_message(
                f"ADHD Channel functionality disabled for {channel.mention}"
            )
        else:
            self.adhd_channels.append(channel.id)
            await interaction.response.send_message(
                f"ADHD Channel functionality enabled for {channel.mention}"
            )

    @tasks.loop(seconds=10)
    async def update_channel_name(self):
        for channel_id in self.adhd_channels:
            channel = self.bot.get_channel(channel_id)
            self.logger.info(f"Updating channel {channel.name}")
            discussion = await self.get_channel_discussion(channel)
            if not discussion or not discussion.topics or len(discussion.topics) == 0:
                self.logger.info("No topics found")
                continue

            self.logger.info(f"New channel name: {discussion.suggested_name}")
            await channel.edit(name=discussion.suggested_name)

    async def get_channel_discussion(self, channel: TextChannel) -> ChannelDiscussion:
        messages = await get_user_messages(channel, limit=50, oldest_first=False)

        if not messages or len(messages) == 0:
            self.logger.info("No messages found")
            return None

        result = await self.agent.run(
            [
                "Analyze the following messages and extract the primary topics being discussed. "
                "Return a list of topics ordered by relevance.",
            ]
            + [m.content for m in messages]
        )

        return result.output


async def setup(bot):
    await bot.add_cog(ADHDChannel(bot))
