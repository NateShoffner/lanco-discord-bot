import asyncio
import os
import re

import discord
import spotipy
from cogs.lancocog import LancoCog, UrlHandler
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import SpotifyEmbedConfig


class SpotifyEmbed(
    LancoCog, name="Spotify Embed Fix", description="Fix Spotify embeds"
):
    embed_group = app_commands.Group(
        name="spotifyembed", description="SpotifyEmbed commands"
    )

    spotify_url_pattern = re.compile(
        r"https?://open.spotify.com/(track|album|playlist|artist)/([a-zA-Z0-9]+)"
    )

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        creds = spotipy.SpotifyClientCredentials(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_SECRET"),
        )
        self.sp = spotipy.Spotify(client_credentials_manager=creds)
        self.bot.database.create_tables([SpotifyEmbedConfig])

        bot.register_url_handler(
            UrlHandler(
                url_pattern=self.spotify_url_pattern,
                cog=self,
                example_url="https://open.spotify.com/playlist/7q7fMqxIWb8LBCHnyhvxBt",
            )
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        match = self.spotify_url_pattern.search(message.content)

        if match:
            self.logger.info(f"Spotify URL detected: {match.group(0)}")

            spotifyembed_config = SpotifyEmbedConfig.get_or_none(
                guild_id=message.guild.id
            )

            if not spotifyembed_config or not spotifyembed_config.enabled:
                return

            spotify_type = match.group(1)
            spotify_id = match.group(2)

            self.logger.info("Waiting for discord to embed the link...")

            # wait a bit to see if discord will embed the link
            await asyncio.sleep(2.5)

            # re-fetch the message to get the latest content
            message = await message.channel.fetch_message(message.id)
            if message.embeds:
                self.logger.info("Discord embedded the link, no need to fix it")
                return

            if spotify_type == "track":
                embed = self.generate_track_embed(spotify_id)
            elif spotify_type == "album":
                embed = self.generate_album_embed(spotify_id)
            elif spotify_type == "playlist":
                embed = self.generate_playlist_embed(spotify_id)
            elif spotify_type == "artist":
                embed = self.generate_artist_embed(spotify_id)

            await message.reply(embed=embed)

    def generate_track_embed(self, track_id: str) -> discord.Embed:
        track = self.sp.track(track_id)

        artist_urls = []
        for artist in track["artists"]:
            artist_urls.append(
                f"[{artist['name']}]({artist['external_urls']['spotify']})"
            )

        embed = discord.Embed(
            title=track["name"],
            description=f"▶️ [Open on Spotify]({track['external_urls']['spotify']})",
            url=track["external_urls"]["spotify"],
        )
        embed.add_field(
            name="Album",
            value=f"[{track['album']['name']}]({track['album']['external_urls']['spotify']})",
            inline=False,
        )
        embed.add_field(name="Artist(s)", value=", ".join(artist_urls), inline=False)
        embed.add_field(
            name="Length",
            value=self.milliseconds_to_minutes(track["duration_ms"]),
            inline=False,
        )
        embed.add_field(
            name="Year", value=track["album"]["release_date"][:4], inline=False
        )
        embed.set_thumbnail(url=track["album"]["images"][0]["url"])
        return embed

    def generate_album_embed(self, album_id: str) -> discord.Embed:
        album = self.sp.album(album_id)

        track_info = []
        for i, track in enumerate(album["tracks"]["items"]):
            track_info.append(
                f"{track['track_number']}. [{track['name']}]({track['external_urls']['spotify']})"
            )

        artist_urls = []
        for artist in album["artists"]:
            artist_urls.append(
                f"[{artist['name']}]({artist['external_urls']['spotify']})"
            )

        track_info = []
        for i, track in enumerate(album["tracks"]["items"]):
            track_info.append(
                f"[{track['track_number']}]: [{track['name']}]({track['external_urls']['spotify']}) - ({self.milliseconds_to_minutes(track['duration_ms'])}"
            )

        embed = discord.Embed(
            title=album["name"],
            description="\n".join(artist_urls),
            url=album["external_urls"]["spotify"],
        )
        embed.add_field(name="Tracks", value="\n".join(track_info), inline=False)
        embed.set_thumbnail(url=album["images"][0]["url"])

        return embed

    def generate_playlist_embed(self, playlist_id: str) -> discord.Embed:
        playlist = self.sp.playlist(playlist_id)

        max_tracks = 5
        track_info = []
        # TODO - decide on a better method of showing tracks that doesn't take up so much space
        for i, track in enumerate(playlist["tracks"]["items"][:max_tracks]):
            track_info.append(
                f"{i + 1}. [{track['track']['name']}]({track['track']['external_urls']['spotify']}) by [{track['track']['artists'][0]['name']}]({track['track']['artists'][0]['external_urls']['spotify']}) - {self.milliseconds_to_minutes(track['track']['duration_ms'])}"
            )

        track_info.append(f"... and {playlist['tracks']['total'] - max_tracks} more")

        desc = [
            f"Created by: [{playlist['owner']['display_name']}]({playlist['owner']['external_urls']['spotify']})".encode(
                "utf-8"
            ).decode(
                "utf-8"
            ),
            f"Followers: {playlist['followers']['total']}",
            f"Tracks: {playlist['tracks']['total']}",
        ]

        embed = discord.Embed(
            title=playlist["name"].encode("utf-8").decode("utf-8"),
            description="\n".join(desc),
            url=playlist["external_urls"]["spotify"],
        )
        embed.add_field(name="Tracks", value="\n".join(track_info), inline=False)
        embed.set_thumbnail(url=playlist["images"][0]["url"])

        return embed

    def generate_artist_embed(self, artist_id: str) -> discord.Embed:
        artist = self.sp.artist(artist_id)

        # TODO - add top tracks

        desc = [
            f"Genre(s): {', '.join(artist['genres'])}",
            f"Followers: {artist['followers']['total']}",
        ]

        embed = discord.Embed(
            title=artist["name"],
            description="\n".join(desc),
            url=artist["external_urls"]["spotify"],
        )
        embed.set_thumbnail(url=artist["images"][0]["url"])

        return embed

    def milliseconds_to_minutes(self, ms: int) -> str:
        length = ms / 1000
        minutes = int(length / 60)
        seconds = int(length % 60)
        return f"{minutes}:{seconds:02d}"

    @embed_group.command(
        name="toggle", description="Toggle Spotify embed fixing for this server"
    )
    @is_bot_owner_or_admin()
    async def toggle(self, interaction: discord.Interaction):
        config, created = SpotifyEmbedConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        if created:
            config.enabled = True
            config.save()
            await interaction.response.send_message("Spotify embed fixing enabled")
        else:
            config.delete_instance()
            await interaction.response.send_message("Spotify embed fixing disabled")


async def setup(bot):
    await bot.add_cog(SpotifyEmbed(bot))
