import discord
from discord.ext import commands
from discord import Intents
import os
import asyncio
import yt_dlp
import urllib.parse, urllib.request, re
from dotenv import load_dotenv


def run_bot():
    load_dotenv()
    TOKEN = os.getenv('discord_token')
    intents = discord.Intents.default()
    intents.message_content = True
    client = commands.Bot(command_prefix="!", intents=intents)

    queues = {}
    voice_clients = {}
    youtube_base_url = 'https://www.youtube.com/'
    youtube_results_url = youtube_base_url + 'results?'
    youtube_watch_url = youtube_base_url + 'watch?v='
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn -filter:a "volume=0.25"'}

    @client.event
    async def on_ready():
        print(f'{client.user} has graced you with his presence')

    async def play_next(ctx):
        id = int(ctx.guild.id)
        if queues[id]:
            next_song = queues[id].pop(0)
            await play(ctx, link=next_song)
    
    @client.command(name="play")
    async def play(ctx, *, link):
        id = int(ctx.guild.id)

        if id not in voice_clients:
            voice_clients[id] = None
        if id not in queues:
            queues[id] = []

        try:
            voice_client = voice_clients.get(id)
            if voice_client is None or not voice_client.is_connected():
                voice_client = await ctx.author.voice.channel.connect()
                voice_clients[id] = voice_client
        except Exception as e:
            print(e)

        try:
            if youtube_base_url not in link:
                query_string = urllib.parse.urlencode({
                    'search_query': link
                })

                content = urllib.request.urlopen(youtube_results_url + query_string)
                search_results = re.findall(r'/watch\\?v=(.{11})', content.read().decode())

                if search_results:
                    link = youtube_watch_url + search_results[0]
                else:
                    await ctx.send("No results found for the query.")
                    return

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download=False))

            song = {
                'url': data['url'],
                'title': data['title'],
                'artist': data.get('uploader', 'Unknown Artist')  # Fetch artist information
            }
            player = discord.FFmpegOpusAudio(song['url'], **ffmpeg_options)

            if voice_clients[id].is_playing():
                queues[id].append(song)
                await ctx.send(f"Song added to the queue: {song['title']} by {song['artist']}")
            else:
                voice_clients[id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))
                await ctx.send(f"Now playing: {song['title']} by {song['artist']}")
        except Exception as e:
            print(e)

            
    @client.command(name="clear_queue")
    async def clear_queue(ctx):
        if ctx.guild.id in queues:
            queues[ctx.guild.id].clear()
            await ctx.send("Queue cleared!")
        else:
            await ctx.send("There is no queue to clear")

    @client.command(name="pause")
    async def pause(ctx):
        try:
            voice_clients[ctx.guild.id].pause()
        except Exception as e:
            print(e)

    @client.command(name="resume")
    async def resume(ctx):
        try:
            voice_clients[ctx.guild.id].resume()
        except Exception as e:
            print(e)

    @client.command(name="stop")
    async def stop(ctx):
        try:
            voice_clients[ctx.guild.id].stop()
            await voice_clients[ctx.guild.id].disconnect()
            del voice_clients[ctx.guild.id]
        except Exception as e:
            print(e)

    @client.command(name="queue")
    async def queue(ctx):
        id = int(ctx.guild.id)
        if id in queues and queues[id]:
            queue_list = "\n".join([f"{index + 1}. {song['title']} by {song['artist']}" for index, song in enumerate(queues[id])])
            await ctx.send(f"Current queue:\n{queue_list}")
        else:
            await ctx.send("The queue is currently empty.")
    
    # @client.command(name="queue")
    # async def queue(ctx, *, url):
    #     if ctx.guild.id not in queues:
    #         queues[ctx.guild.id] = []
    #     queues[ctx.guild.id].append(url)
    #     await ctx.send("Added to queue!")
                       
    @client.command(name="skip")
    async def skip(ctx):
        id = int(ctx.guild.id)
        if id in voice_clients and voice_clients[id].is_playing():
            voice_clients[id].stop()
            await ctx.send("Skipped the current song.")
        else:
            await ctx.send("There's no song currently playing.")

    client.run(TOKEN)