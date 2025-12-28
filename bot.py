import os
import discord
from discord.ext import commands
import yt_dlp  # Changed from youtube_dl to yt_dlp
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
        
        # Updated YT-DLP options
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
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
        if ctx.guild.id in self.song_queue and self.song_queue[ctx.guild.id]:
            voice_client = ctx.voice_client
            
            if voice_client:
                url = self.song_queue[ctx.guild.id].popleft()
                
                try:
                    with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        url2 = info['url']  # Changed from ['formats'][0]['url']
                        title = info.get('title', 'Unknown title')
                        
                        voice_client.play(
                            discord.FFmpegPCMAudio(
                                url2,
                                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
                            ),
                            after=lambda e: asyncio.run_coroutine_threadsafe(
                                self.play_next(ctx), self.loop
                            )
                        )
                        
                        await ctx.send(f"🎵 Now playing: {title}")
                except Exception as e:
                    await ctx.send(f"An error occurred while playing the song: {str(e)}")
                    await self.play_next(ctx)
        else:
            await ctx.send("Queue is empty. Use !play to add more songs!")

bot = MusicBot()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command()
async def play(ctx, *, query):  # Changed parameter name and added * to allow spaces
    if not ctx.message.author.voice:
        await ctx.send("You are not connected to a voice channel!")
        return
    
    channel = ctx.message.author.voice.channel
    voice_client = ctx.voice_client

    if ctx.guild.id not in bot.song_queue:
        bot.song_queue[ctx.guild.id] = deque()

    try:
        with yt_dlp.YoutubeDL(bot.ydl_opts) as ydl:
            try:
                # Handle both direct URLs and search queries
                info = ydl.extract_info(
                    f"ytsearch:{query}" if not query.startswith('http') else query,
                    download=False
                )
                if 'entries' in info:
                    # If it's a search query, take the first result
                    info = info['entries'][0]
                title = info.get('title', 'Unknown title')
                url = info['webpage_url']  # Store the actual video URL
            except Exception as e:
                await ctx.send(f"Error fetching video: {str(e)}")
                return

        if not voice_client:
            if ctx.voice_client:
                    try:
                        await ctx.voice_client.disconnect(force=True)
                    except:
                        pass

            await asyncio.sleep(1)  # Prevent rapid reconnect issues
            
            voice_client = await channel.connect(timeout=10, reconnect=False)

        elif voice_client.channel != channel:
                await voice_client.move_to(channel)



        bot.song_queue[ctx.guild.id].append(url)
        position = len(bot.song_queue[ctx.guild.id])

        if voice_client.is_playing() or voice_client.is_paused():
            await ctx.send(f"🎵 Added to queue (Position {position}): {title}")
        else:
            await ctx.send(f"🎵 Added to queue: {title}")
            await bot.play_next(ctx)

    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

@bot.command()
async def queue(ctx):
    """Display the current song queue"""
    if ctx.guild.id not in bot.song_queue or not bot.song_queue[ctx.guild.id]:
        await ctx.send("The queue is empty!")
        return

    queue_list = []
    with yt_dlp.YoutubeDL(bot.ydl_opts) as ydl:
        for i, url in enumerate(bot.song_queue[ctx.guild.id], 1):
            try:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Unknown title')
                queue_list.append(f"{i}. {title}")
            except:
                queue_list.append(f"{i}. Error getting title")

    queue_text = "\n".join(queue_list)
    await ctx.send(f"**Current Queue:**\n{queue_text}")

@bot.command()
async def skip(ctx):
    """Skip the current song"""
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("⏭️ Skipped the current song")
        await bot.play_next(ctx)
    else:
        await ctx.send("No song is currently playing!")

@bot.command()
async def clear(ctx):
    """Clear the song queue"""
    if ctx.guild.id in bot.song_queue:
        bot.song_queue[ctx.guild.id].clear()
    await ctx.send("🧹 Queue has been cleared!")

@bot.command()
async def leave(ctx):
    """Disconnect the bot from voice channel and clear the queue"""
    if ctx.voice_client:
        if ctx.guild.id in bot.song_queue:
            bot.song_queue[ctx.guild.id].clear()
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Bot has left the voice channel")

@bot.command()
async def pause(ctx):
    """Pause the current song"""
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await ctx.send("⏸️ Paused the current song")
    else:
        await ctx.send("No song is currently playing!")

@bot.command()
async def resume(ctx):
    """Resume the current song"""
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await ctx.send("▶️ Resumed the current song")
    else:
        await ctx.send("No song is paused!")

# Get token from environment variable
TOKEN = os.getenv('discord_token')
if not TOKEN:
    raise ValueError("No token found. Please set the discord_token environment variable.")

# Run the bot
bot.run(TOKEN)