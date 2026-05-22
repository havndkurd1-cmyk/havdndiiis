import discord
import os
import asyncio
import logging
import random
import time
from discord import app_commands
from collections import defaultdict, deque
import yt_dlp as youtube_dlp
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GROK_OMEGA")

# ================== YT-DLP ==================
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

# ================== PROXY SCRAPER ==================
PROXIES = []

def scrape_proxies():
    global PROXIES
    sources = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http,socks4,socks5&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://www.proxy-list.download/api/v1/get?type=socks5",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"
    ]
    PROXIES = []
    for url in sources:
        try:
            r = requests.get(url, timeout=12)
            if r.status_code == 200:
                lines = [line.strip() for line in r.text.strip().splitlines() if line.strip() and ':' in line]
                PROXIES.extend(lines)
        except:
            pass
    PROXIES = list(set(PROXIES))
    print(f"✅ Scraped {len(PROXIES)} fresh proxies")
    return PROXIES

def get_random_proxy():
    if not PROXIES:
        scrape_proxies()
    return random.choice(PROXIES) if PROXIES else None

# ================== MUSIC COMMANDS ==================
@tree.command(name="play", description="Play song")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    if not interaction.user.voice:
        return await interaction.followup.send("Join VC first!")
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

# ================== FB MASS CREATOR ==================
@tree.command(name="fb_create_mass", description="Railway Max Stealth FB Mass Creator + Proxy Rotation")
@app_commands.describe(
    accounts="email1:pass1,email2:pass2,...",
    post_url="Post URL to comment on (optional)",
    comment_base="Base comment text"
)
async def fb_create_mass(interaction: discord.Interaction, accounts: str, post_url: str = "", comment_base: str = "This is fire"):
    await interaction.response.defer()
    await interaction.followup.send("🛡️ **Railway Max Stealth FB Creator v5 + Proxy Rotation** Starting...")

    account_list = [acc.strip().split(":", 1) for acc in accounts.split(",") if ":" in acc]
    results = []

    async def create_account(email: str, password: str, num: int):
        driver = None
        proxy = get_random_proxy()
        try:
            await asyncio.sleep(random.uniform(3, 7))

            options = uc.ChromeOptions()
            if proxy:
                options.add_argument(f'--proxy-server={proxy}')
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--window-size=1366,768")
            options.add_argument(f"--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.{random.randint(5200,6999)}.0 Safari/537.36")

            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            driver = uc.Chrome(options=options, version_main=134, headless=True)

            def human_delay(a=2.5, b=8.0):
                time.sleep(random.uniform(a, b))

            driver.get("https://www.facebook.com/r.php")
            human_delay(8, 14)

            driver.find_element(By.NAME, "firstname").send_keys(f"Kurd{random.randint(15,98)}")
            human_delay(1.5, 3.5)
            driver.find_element(By.NAME, "lastname").send_keys("Xan")
            human_delay(1.5, 3.5)
            driver.find_element(By.NAME, "reg_email__").send_keys(email)
            human_delay(1.5, 3.5)
            driver.find_element(By.NAME, "reg_email_confirmation__").send_keys(email)
            human_delay(1.5, 3.5)
            driver.find_element(By.NAME, "reg_passwd__").send_keys(password)
            human_delay(3, 6)

            driver.find_element(By.NAME, "birthday_month").send_keys(str(random.randint(1,12)))
            driver.find_element(By.NAME, "birthday_day").send_keys(str(random.randint(11,26)))
            driver.find_element(By.NAME, "birthday_year").send_keys("1998")
            human_delay(2, 5)

            driver.find_element(By.XPATH, "//input[@value='2']").click()
            human_delay(3, 7)

            driver.find_element(By.NAME, "websubmit").click()
            human_delay(18, 28)

            results.append(f"✅ Created → {email} | Proxy: {proxy}")

            if post_url:
                human_delay(10, 18)
                driver.get(post_url)
                human_delay(12, 20)

                comment_text = f"{comment_base} #{num} 🔥"
                comment_box = WebDriverWait(driver, 45).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[@role='textbox' or @contenteditable='true']"))
                )
                ActionChains(driver).move_to_element(comment_box).click().perform()
                human_delay(2, 4)

                for char in comment_text:
                    comment_box.send_keys(char)
                    await asyncio.sleep(random.uniform(0.07, 0.22))

                human_delay(3, 6)
                comment_box.send_keys(Keys.ENTER)
                results[-1] += " | Commented"

        except Exception as e:
            results.append(f"❌ Failed → {email} | Proxy {proxy} | {type(e).__name__}: {str(e)[:180]}")
        finally:
            if driver:
                try: driver.quit()
                except: pass

    # Staggered execution
    tasks = []
    max_acc = min(len(account_list), 8)
    for i, (email, pwd) in enumerate(account_list[:max_acc], 1):
        tasks.append(asyncio.create_task(create_account(email, pwd, i)))
        await asyncio.sleep(random.uniform(7, 12))

    await asyncio.gather(*tasks, return_exceptions=True)
    await interaction.followup.send("**Mass Creation Finished**\n\n" + "\n".join(results))

# ================== BOT EVENTS ==================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ {bot.user} | Protocol Zero Active | Max Stealth FB + Proxies Ready")

async def main():
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
