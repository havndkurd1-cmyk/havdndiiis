import discord
import os
import asyncio
import logging
from discord import app_commands
from collections import defaultdict, deque
import yt_dlp as youtube_dlp

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("GROK")

ADMIN_IDS = [1017196501635711048]  # YOUR ID

ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': False,
    'no_warnings': False,
    'default_search': 'ytsearch',
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -acodec pcm_s16le -ar 48000 -ac 2'
}

ytdl = youtube_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=1.0):
        super().__init__(source, volume)
        self.title = data.get('title', 'Unknown')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]

        logger.info(f"Streaming URL: {data.get('url')[:100]}...")
        return cls(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options), data=data)

# BOT
intents = discord.Intents.all()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

queues = defaultdict(lambda: deque())

async def play_next(guild_id):
    vc = discord.utils.get(bot.voice_clients, guild_id=guild_id)
    if not vc or not queues[guild_id]:
        return

    song = queues[guild_id].popleft()
    try:
        player = await YTDLSource.from_url(song['url'], loop=bot.loop)
        vc.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id), bot.loop))
        logger.info(f"NOW PLAYING: {song['title']}")
    except Exception as e:
        logger.error(f"PLAY ERROR: {e}")

@tree.command(name="play", description="Play song")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    if not interaction.user.voice:
        return await interaction.followup.send("Join VC first!")

    vc = interaction.guild.voice_client
    if not vc:
        vc = await interaction.user.voice.channel.connect()

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False, process=False))
        if 'entries' in data:
            data = data['entries'][0]

        song = {'title': data.get('title', query), 'url': data.get('webpage_url') or query}
        queues[interaction.guild.id].append(song)

        if not vc.is_playing():
            await play_next(interaction.guild_id)
            await interaction.followup.send(f"▶️ **Now Playing:** {song['title']}")
        else:
            await interaction.followup.send(f"📝 Queued: {song['title']}")
    except Exception as e:
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@tree.command(name="leave", description="Leave voice")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        queues[interaction.guild.id].clear()
        await interaction.response.send_message("Left voice.")

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ {bot.user} READY - Check logs for debug info")

async def main():
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
