import discord
import os
import asyncio
import logging
import random
import time
from discord import app_commands
from collections import defaultdict, deque
import yt_dlp as youtube_dlp

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium_stealth import stealth
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GROK_OMEGA")

# ================== YT-DLP (unchanged) ==================
ytdl_format_options = {
    'format': 'bestaudio/best[acodec=opus]/bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'cookiefile': 'cookies.txt',
    'extractor_args': {'youtube': {'player_client': ['ios', 'android', 'web', 'tv']}},
}

ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn -acodec pcm_s16le -ar 48000 -ac 2'}
ytdl = youtube_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=1.0):
        super().__init__(source, volume)
        self.title = data.get('title', 'Unknown')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data: data = data['entries'][0]
        return cls(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options), data=data, volume=1.0)

# ================== BOT SETUP ==================
intents = discord.Intents.all()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)
queues = defaultdict(lambda: deque())

# Music commands (kept short)
@tree.command(name="play", description="Play song")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    if not interaction.user.voice: return await interaction.followup.send("Join VC first!")
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(query, download=False, process=False))
        if 'entries' in data: data = data['entries'][0]
        song = {'title': data.get('title', query), 'url': data.get('webpage_url') or query}
        queues[interaction.guild.id].append(song)
        if not vc.is_playing():
            await play_next(interaction.guild.id)
            await interaction.followup.send(f"▶️ **Now Playing:** {song['title']}")
        else:
            await interaction.followup.send(f"📝 **Queued:** {song['title']}")
    except Exception as e:
        await interaction.followup.send(f"Error: {str(e)[:200]}")

async def play_next(guild_id: int):
    vc = discord.utils.get(bot.voice_clients, guild__id=guild_id)
    if not vc or not queues[guild_id]: return
    song = queues[guild_id].popleft()
    try:
        player = await YTDLSource.from_url(song['url'], loop=bot.loop)
        vc.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id), bot.loop))
    except: pass

@tree.command(name="leave", description="Leave VC")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        queues[interaction.guild.id].clear()
        await interaction.response.send_message("Left voice.")

# ================== BEST STEALTH FB MASS CREATOR ==================
@tree.command(name="fb_create_mass", description="Create FB accounts (MAX STEALTH)")
@app_commands.describe(
    accounts="email1:pass1,email2:pass2,...",
    post_url="Post URL to comment on",
    comment_base="Comment text"
)
async def fb_create_mass(interaction: discord.Interaction, accounts: str, post_url: str, comment_base: str = "This is fire"):
    await interaction.response.defer()
    await interaction.followup.send("🛡️ Starting **Maximum Stealth** Mass Account Creation...")

    account_list = [acc.strip().split(":", 1) for acc in accounts.split(",") if ":" in acc]
    results = []

    async def create_account(email: str, password: str, num: int):
        driver = None
        try:
            await asyncio.sleep(random.uniform(0.5, 3.5))

            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--window-size=1366,768")
            options.add_argument(f"--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.{random.randint(6000,6999)}.0 Safari/537.36")

            driver = webdriver.Chrome(options=options)
            
            stealth(driver,
                    languages=["en-US", "en"],
                    vendor="Google Inc.",
                    platform="Win32",
                    webgl_vendor="Intel Inc.",
                    renderer="Intel Iris OpenGL Engine",
                    fix_hairline=True)

            def human_delay(a=2.0, b=6.0):
                time.sleep(random.uniform(a, b))

            def human_mouse_move():
                try:
                    ActionChains(driver).move_by_offset(random.randint(-30,30), random.randint(-30,30)).perform()
                except: pass

            # Create Account
            driver.get("https://www.facebook.com/r.php")
            human_delay(5, 8)
            human_mouse_move()

            driver.find_element(By.NAME, "firstname").send_keys(f"Kurd{random.randint(11,89)}")
            human_delay(0.8, 2)
            driver.find_element(By.NAME, "lastname").send_keys("X")
            human_delay(0.8, 2)
            driver.find_element(By.NAME, "reg_email__").send_keys(email)
            human_delay(0.8, 2)
            driver.find_element(By.NAME, "reg_email_confirmation__").send_keys(email)
            human_delay(0.8, 2)
            driver.find_element(By.NAME, "reg_passwd__").send_keys(password)
            human_delay(1.5, 3.5)

            driver.find_element(By.NAME, "birthday_month").send_keys(str(random.randint(1,12)))
            driver.find_element(By.NAME, "birthday_day").send_keys(str(random.randint(10,25)))
            driver.find_element(By.NAME, "birthday_year").send_keys("1997")
            human_delay()
            driver.find_element(By.XPATH, "//input[@value='2']").click()
            human_delay(1, 2)

            driver.find_element(By.NAME, "websubmit").click()
            human_delay(12, 18)

            results.append(f"✅ Created → {email}")

            # Auto Comment
            if post_url:
                human_delay(6, 10)
                driver.get(post_url)
                human_delay(7, 12)
                human_mouse_move()

                comment_text = f"{comment_base} #{num} 🔥"

                comment_box = WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[@role='textbox']"))
                )
                ActionChains(driver).move_to_element(comment_box).click().perform()
                human_delay(1.2, 2.5)

                for char in comment_text:
                    comment_box.send_keys(char)
                    time.sleep(random.uniform(0.06, 0.22))

                human_delay(1.8, 3.5)
                comment_box.send_keys(Keys.ENTER)
                results[-1] += " | Commented"

        except Exception as e:
            results.append(f"❌ Failed → {email} | {str(e)[:90]}")
        finally:
            if driver:
                try: driver.quit()
                except: pass

    # Launch with delay
    tasks = []
    for i, (email, pwd) in enumerate(account_list[:12], 1):
        tasks.append(asyncio.create_task(create_account(email, pwd, i)))
        await asyncio.sleep(2.8)   # Good stagger

    await asyncio.gather(*tasks)

    await interaction.followup.send("**Mass Creation Finished**\n\n" + "\n".join(results))

# ================== RUN BOT ==================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ {bot.user} | Protocol Zero Active | Max Stealth FB Ready")

async def main():
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
