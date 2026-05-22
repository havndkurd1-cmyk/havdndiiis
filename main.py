import discord
import os
import asyncio
import logging
from discord import app_commands
from openai import AsyncOpenAI
from collections import defaultdict, deque
import yt_dlp as youtube_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GROK_OMEGA")

# ================== ADMIN IDS ==================
ADMIN_IDS = [1017196501635711048]   # ← CHANGE TO YOUR ID

def is_admin(interaction: discord.Interaction):
    return interaction.user.id in ADMIN_IDS or interaction.user.guild_permissions.administrator

# ================== BETTER YT-DLP CONFIG ==================
ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'extractor_args': {'youtube': {'player_client': ['ios', 'android', 'web', 'tv']}},
    'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -fflags +genpts',
    'options': '-vn -acodec pcm_s16le -ar 48000 -ac 2 -b:a 192k'   # Higher quality + forced PCM
}

ytdl = youtube_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.8):          # Increased default volume
        super().__init__(source, volume)
        self.title = data.get('title', 'Unknown')
        self.url = data.get('webpage_url') or data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            
            if 'entries' in data:
                data = data['entries'][0]

            filename = data['url'] if stream else ytdl.prepare_filename(data)
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, volume=0.8)
        except Exception as e:
            logger.error(f"YTDL Error: {e}")
            raise

# ================== BOT SETUP ==================
intents = discord.Intents.all()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

music_queues = defaultdict(lambda: deque())
now_playing = defaultdict(lambda: None)

async def play_next(guild_id: int):
    vc = discord.utils.get(bot.voice_clients, guild__id=guild_id)
    if not vc or not music_queues[guild_id]:
        now_playing[guild_id] = None
        return

    song = music_queues[guild_id].popleft()
    now_playing[guild_id] = song

    try:
        player = await YTDLSource.from_url(song['url'], loop=bot.loop)
        vc.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id), bot.loop))
        logger.info(f"Playing: {song['title']}")
    except Exception as e:
        logger.error(f"Play failed: {e}")
        await play_next(guild_id)

# ================== COMMANDS ==================
@tree.command(name="join", description="Join voice")
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message("Join a voice channel first!", ephemeral=True)
        return
    await interaction.user.voice.channel.connect()
    await interaction.response.send_message(f"✅ Joined **{interaction.user.voice.channel.name}** (stays until /leave)")

@tree.command(name="play", description="Play song (search or URL)")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()

    if not interaction.user.voice:
        await interaction.followup.send("❌ You must be in a voice channel!")
        return

    vc = interaction.guild.voice_client
    if not vc:
        vc = await interaction.user.voice.channel.connect()

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False, process=False))

        if 'entries' in data:
            data = data['entries'][0]

        song = {'title': data.get('title', query), 'url': data.get('webpage_url') or query}

        music_queues[interaction.guild.id].append(song)

        if not vc.is_playing():
            await play_next(interaction.guild.id)
            await interaction.followup.send(f"▶️ **Now Playing:** {song['title']}")
        else:
            await interaction.followup.send(f"📝 Queued: **{song['title']}**")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)[:300]}")

@tree.command(name="leave", description="Leave voice")
async def leave(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        await vc.disconnect()
        music_queues[interaction.guild.id].clear()
        await interaction.response.send_message("✅ Left voice channel.")
    else:
        await interaction.response.send_message("Not in voice.")

# Add skip, queue, pause, resume, stop commands (same as before) ...

# ================== RUN ==================
async def main():
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
