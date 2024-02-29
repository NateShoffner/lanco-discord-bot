import datetime
from discord import TextChannel, User, app_commands
import discord
from discord.ext import commands
from cogs.lancocog import LancoCog


class Story:
    def __init__(self, owner: User, origin: TextChannel, max_length: int):
        self.owner = owner
        self.origin = origin
        self.max_length = max_length
        self.started = datetime.datetime.now()
        self.words = []
        self.last_author = None
        self.last_updated = None

    def is_last_author(self, author: User):
        return self.last_author == author

    def add_word(self, author: User, word: str):
        self.words.append(word)
        self.last_author = author
        self.last_updated = datetime.datetime.now()

    def get_story(self):
        return " ".join(self.words)

    def get_word_count(self):
        return len(self.words)


class OneWordStory(LancoCog):
    story_group = app_commands.Group(name="story", description="One Word Story")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.stories = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        story = self.get_story(message.channel.id)
        if not story:
            return

        # ignore native commands
        if (
            message.content.startswith(self.bot.command_prefix)
            and len(message.content) > 1
        ):
            return

        # ignore commands from other bots
        known_command_prefixes = ["!", "T!"]  # Default  # Tatsu
        if message.content.lower().startswith(
            tuple(prefix.lower() for prefix in known_command_prefixes)
        ):
            return

        # ignore subsequent words from the same author
        if story.is_last_author(message.author):
            return

        words = message.content.split()

        # ignore messages with more than one word
        if len(words) != 1:
            return

        new_word = words[0]

        ends_with_punctuation = (
            new_word.endswith(".") or new_word.endswith("?") or new_word.endswith("!")
        )

        if ends_with_punctuation:
            new_word = new_word + "\n"

        story.add_word(message.author, new_word)
        await message.add_reaction("✅")

        if story.get_word_count() >= story.max_length:
            await message.channel.send(embed=self.create_story_embed(story, True))
            del self.stories[message.channel.id]
            return

        if ends_with_punctuation:
            await message.channel.send(embed=self.create_story_embed(story))

    @story_group.command(name="status", description="Get the current story status")
    async def story_status(self, interaction: discord.Interaction):
        story = self.get_story(interaction.channel_id)
        if not story:
            await interaction.response.send_message("No story in progress")
            return

        await interaction.response.send_message(embed=self.create_story_embed(story))

    @story_group.command(name="stop", description="Stop the current story")
    async def stop_story(self, interaction: discord.Interaction):
        story = self.get_story(interaction.channel_id)
        if not story:
            await interaction.response.send_message("No story in progress")
            return

        if story.owner != interaction.user:
            await interaction.response.send_message(
                "Only the story owner can stop the story", ephemeral=True
            )
            return

        await interaction.response.send_message("Story stopped")
        await interaction.channel.send(embed=self.create_story_embed(story, True))
        del self.stories[interaction.channel_id]

    @story_group.command(name="start", description="Start a new story")
    async def start_story(
        self, interaction: discord.Interaction, max_length: int = 100
    ):
        if self.get_story(interaction.channel_id):
            await interaction.response.send_message(
                "A story is already in progress in this channel"
            )
            return

        story = Story(interaction.user, interaction.channel, max_length)
        self.stories[interaction.channel_id] = story

        desc = [
            f"A new story has been started by {interaction.user.display_name}!",
            "",
            "**Rules:**",
            "* The story must be written one word at a time",
            "* You must wait for someone else to write a word before you can write another",
            "* You can end a sentence with a punctuation mark to start a new sentence",
            f"* The story will end after **{story.max_length}** words or when the owner stops it",
        ]

        embed = discord.Embed(
            title="One Word Story",
            description="\n".join(desc),
            color=discord.Color.blue(),
        )

        await interaction.response.send_message(embed=embed)

    def create_story_embed(self, story: Story, finished: bool = False):
        title = "The current story is" if not finished else "The final story was"
        desc = f"{title}:\n\n{story.get_story()}\n\nWord Count: {story.get_word_count()} / {story.max_length}"
        embed = discord.Embed(description=desc, color=discord.Color.blue())
        embed.set_author(
            name=story.owner.display_name, icon_url=story.owner.display_avatar
        )
        embed.set_footer(text=f"Last Updated by {story.last_author.display_name}")
        embed.timestamp = story.last_updated
        return embed

    def get_story(self, channel_id: int) -> Story:
        story = self.stories.get(channel_id)
        if not story:
            return None
        return story


async def setup(bot):
    await bot.add_cog(OneWordStory(bot))
