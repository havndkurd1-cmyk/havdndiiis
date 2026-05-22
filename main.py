import discord
import os
import asyncio
import logging
from discord import app_commands
from openai import AsyncOpenAI
from collections import defaultdict, deque
import yt_dlp as youtube_dlp

# ================== LOGGING ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GROK_OMEGA")

# ================== ADMIN SETUP ==================
ADMIN_IDS = [
    1017196501635711048,   # ← CHANGE THIS TO YOUR DISCORD ID
]

def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.id in ADMIN_IDS or interaction.user.guild_permissions.administrator

# ================== YT-DLP CONFIG (Improved) ==================
ytdl_format_options = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'restrictfilenames': True,
    'noplaylist': False,           # Allow playlists if wanted
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extractor_args': {'youtube': {'player_client': ['ios', 'android', 'web']}},
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=0.4"'
}

ytdl = youtube_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title', 'Unknown Title')
        self.url = data.get('webpage_url') or data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# ================== BOT SETUP ==================
intents = discord.Intents.all()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Queue System
music_queues = defaultdict(lambda: deque())
now_playing = defaultdict(lambda: None)

async def play_next(guild_id: int):
    vc = discord.utils.get(bot.voice_clients, guild__id=guild_id)
    if not vc or not music_queues[guild_id]:
        now_playing[guild_id] = None
        # BOT STAYS CONNECTED EVEN IF QUEUE IS EMPTY
        return

    next_song = music_queues[guild_id].popleft()
    now_playing[guild_id] = next_song

    try:
        player = await YTDLSource.from_url(next_song['url'], loop=bot.loop)
        vc.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id), bot.loop))
        logger.info(f"Now playing in {guild_id}: {next_song['title']}")
    except Exception as e:
        logger.error(f"Play error: {e}")
        await asyncio.sleep(1)
        await play_next(guild_id)

# ================== AI SETUP (kept from before) ==================
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

MODEL = "meta-llama/llama-3.3-70b-instruct"

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ GROK-OMEGA-ULTRA | PROTOCOL ZERO ACTIVE | {bot.user}")

# ================== MUSIC COMMANDS ==================
@tree.command(name="join", description="Make the bot join your voice channel")
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ You are not in a voice channel.", ephemeral=True)
        return
    
    await interaction.user.voice.channel.connect()
    await interaction.response.send_message(f"✅ Joined **{interaction.user.voice.channel.name}** and will stay until `/leave` is used.")

@tree.command(name="leave", description="Make the bot leave the voice channel")
async def leave(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        await vc.disconnect()
        music_queues[interaction.guild.id].clear()
        now_playing[interaction.guild.id] = None
        await interaction.response.send_message("✅ Left the voice channel.")
    else:
        await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)

@tree.command(name="play", description="Play a song from YouTube or search term")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()

    if not interaction.user.voice:
        await interaction.followup.send("❌ Join a voice channel first!")
        return

    vc = interaction.guild.voice_client
    if not vc:
        vc = await interaction.user.voice.channel.connect()
        await interaction.followup.send(f"✅ Joined **{vc.channel.name}**")

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False, process=False))

        if 'entries' in data:
            data = data['entries'][0]

        song = {
            'title': data.get('title', query),
            'url': data.get('webpage_url') or query,
            'requester': interaction.user.name
        }

        music_queues[interaction.guild.id].append(song)

        if not vc.is_playing() and not vc.is_paused():
            await play_next(interaction.guild.id)
            await interaction.followup.send(f"▶️ **Now Playing:** {song['title']}")
        else:
            await interaction.followup.send(f"📝 **Queued:** {song['title']}")

    except Exception as e:
        logger.error(f"Play failed: {e}")
        await interaction.followup.send(f"❌ Failed to play: {str(e)[:200]}")

@tree.command(name="queue", description="Show the current queue")
async def show_queue(interaction: discord.Interaction):
    q = music_queues[interaction.guild.id]
    current = now_playing[interaction.guild.id]
    
    embed = discord.Embed(title="🎵 Music Queue", color=0x00ff00)
    
    if current:
        embed.add_field(name="Now Playing", value=f"**{current['title']}**", inline=False)
    
    if q:
        queue_text = "\n".join([f"`{i+1}.` {s['title'][:60]}" for i, s in enumerate(list(q)[:20])])
        embed.add_field(name=f"Up Next ({len(q)} songs)", value=queue_text or "Empty", inline=False)
    else:
        embed.add_field(name="Up Next", value="Empty", inline=False)
    
    await interaction.response.send_message(embed=embed)

@tree.command(name="skip", description="Skip current song")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏭️ Skipped current song.")
    else:
        await interaction.response.send_message("Nothing is playing.")

@tree.command(name="stop", description="Stop music and clear queue")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        vc.stop()
        music_queues[interaction.guild.id].clear()
        now_playing[interaction.guild.id] = None
        await interaction.response.send_message("⏹️ Stopped and queue cleared.")
    else:
        await interaction.response.send_message("Not playing anything.")

@tree.command(name="pause", description="Pause the music")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸️ Paused.")
    else:
        await interaction.response.send_message("Nothing playing.")

@tree.command(name="resume", description="Resume paused music")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message("▶️ Resumed.")
    else:
        await interaction.response.send_message("Nothing is paused.")

# ================== KEEP YOUR ORIGINAL AI / ADMIN COMMANDS HERE ==================
# Paste all your remaining code (imagine, lethus, on_message, etc.) below this line

# ================== RUN BOT ==================
async def main():
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    print("="*70)
    print("GROK-OMEGA-ULTRA - PROTOCOL ZERO")
    print("Music system upgraded - Bot stays in VC until /leave")
    print("="*70)
    asyncio.run(main())
