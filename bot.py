import os
import discord
from discord.ext import commands
import yt_dlp
from collections import deque
import asyncio
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

logging.getLogger('discord.voice_client').setLevel(logging.DEBUG)


class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

        self.song_queue = {}

        # Clean YT-DLP options for streaming
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0'
        }

    async def play_next(self, ctx):
        """Play the next song in the queue."""
        guild_id = ctx.guild.id

        if guild_id in self.song_queue and self.song_queue[guild_id]:
            voice_client = ctx.voice_client

            if voice_client:
                url = self.song_queue[guild_id].popleft()

                try:
                    # Re-extract fresh streaming URL
                    with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)

                        # Safe URL extraction
                        url2 = info.get("url") or info["formats"][0]["url"]
                        title = info.get("title", "Unknown title")

                    # Play audio
                    voice_client.play(
                        discord.FFmpegPCMAudio(
                            url2,
                            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                            options="-vn"
                        ),
                        after=lambda e: asyncio.run_coroutine_threadsafe(
                            self.play_next(ctx), self.loop
                        )
                    )

                    await ctx.send(f"🎵 Now playing: {title}")

                except yt_dlp.utils.DownloadError:
                    await ctx.send("⚠️ Stream expired, refreshing…")
                    return await self.play_next(ctx)

                except Exception as e:
                    await ctx.send(f"An error occurred while playing the song: {str(e)}")
                    return await self.play_next(ctx)

        else:
            await ctx.send("Queue is empty. Use !play to add more songs!")


bot = MusicBot()


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')


@bot.command()
async def play(ctx, *, query):
    """Add a song to the queue and play if idle."""
    if not ctx.author.voice:
        return await ctx.send("You are not connected to a voice channel!")

    channel = ctx.author.voice.channel
    voice_client = ctx.voice_client

    guild_id = ctx.guild.id
    if guild_id not in bot.song_queue:
        bot.song_queue[guild_id] = deque()

    try:
        # Search or extract info
        with yt_dlp.YoutubeDL(bot.ydl_opts) as ydl:
            info = ydl.extract_info(
                f"ytsearch:{query}" if not query.startswith("http") else query,
                download=False
            )

            if "entries" in info:
                info = info["entries"][0]

            title = info.get("title", "Unknown title")
            url = info["webpage_url"]

    except Exception as e:
        return await ctx.send(f"Error fetching video: {str(e)}")

    # Connect to voice if needed
    if not voice_client:
        try:
            voice_client = await channel.connect(timeout=10, reconnect=False)
        except:
            await asyncio.sleep(1)
            voice_client = await channel.connect(timeout=10, reconnect=False)

    elif voice_client.channel != channel:
        await voice_client.move_to(channel)

    # Add to queue
    bot.song_queue[guild_id].append(url)
    position = len(bot.song_queue[guild_id])

    if voice_client.is_playing() or voice_client.is_paused():
        await ctx.send(f"🎵 Added to queue (Position {position}): {title}")
    else:
        await ctx.send(f"🎵 Added to queue: {title}")
        await bot.play_next(ctx)


@bot.command()
async def queue(ctx):
    """Display the current queue."""
    guild_id = ctx.guild.id

    if guild_id not in bot.song_queue or not bot.song_queue[guild_id]:
        return await ctx.send("The queue is empty!")

    queue_list = []
    with yt_dlp.YoutubeDL(bot.ydl_opts) as ydl:
        for i, url in enumerate(bot.song_queue[guild_id], 1):
            try:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Unknown title")
                queue_list.append(f"{i}. {title}")
            except:
                queue_list.append(f"{i}. Error getting title")

    await ctx.send("**Current Queue:**\n" + "\n".join(queue_list))


@bot.command()
async def skip(ctx):
    """Skip the current song."""
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await ctx.send("⏭️ Skipped the current song")
        await bot.play_next(ctx)
    else:
        await ctx.send("No song is currently playing!")


@bot.command()
async def clear(ctx):
    """Clear the queue."""
    guild_id = ctx.guild.id
    if guild_id in bot.song_queue:
        bot.song_queue[guild_id].clear()
    await ctx.send("🧹 Queue has been cleared!")


@bot.command()
async def leave(ctx):
    """Disconnect bot and clear queue."""
    if ctx.voice_client:
        guild_id = ctx.guild.id
        if guild_id in bot.song_queue:
            bot.song_queue[guild_id].clear()
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Bot has left the voice channel")


@bot.command()
async def pause(ctx):
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await ctx.send("⏸️ Paused the current song")
    else:
        await ctx.send("No song is currently playing!")


@bot.command()
async def resume(ctx):
    vc = ctx.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await ctx.send("▶️ Resumed the current song")
    else:
        await ctx.send("No song is paused!")


# Run bot
TOKEN = os.getenv("discord_token")
if not TOKEN:
    raise ValueError("No token found. Please set the discord_token environment variable.")

bot.run(TOKEN)