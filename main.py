import os
import yt_dlp
import requests

from telethon import TelegramClient, events, types, Button
from telethon.errors import FloodWaitError

# ================= CONFIG =================
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

DOWNLOAD_PATH = "/tmp"
GROUP_USERNAME = "bhj_69"  # without @
THUMB_URL = "https://static.pw.live/5eb393ee95fab7468a79d189/ADMIN/6e008265-fef8-4357-a290-07e1da1ff964.png"

# ================= CLIENTS =================
bot = TelegramClient("bot_session", api_id, api_hash)
account_client = TelegramClient(
    "user_account",
    api_id,
    api_hash,
    device_model="Samsung Galaxy S23",
    system_version="13",
    app_version="10.0.1",
)

user_mode = {}
user_links = {}

# ================= HELPERS =================
def format_duration(seconds):
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}" if h > 0 else f"{m:02}:{s:02}"

def download_thumbnail():
    try:
        path = f"{DOWNLOAD_PATH}/thumb.jpg"
        r = requests.get(THUMB_URL, timeout=10)
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except:
        return None

def download_video(url, quality):
    format_string = (
        "bestvideo[height<=720]+bestaudio/best[height<=720]"
        if quality == "720"
        else "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    )

    ydl_opts = {
        "format": format_string,
        "outtmpl": f"{DOWNLOAD_PATH}/%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)

        if not file_path.endswith(".mp4"):
            file_path = file_path.rsplit(".", 1)[0] + ".mp4"

        return (
            file_path,
            info.get("duration", 0),
            info.get("width", 1280),
            info.get("height", 720),
        )

# ================= START =================
@bot.on(events.NewMessage(pattern=r"^/start"))
async def start_handler(event):
    print("START COMMAND RECEIVED")  # Debug log
    buttons = [
        [Button.inline("🤖 Use Bot", b"bot_mode")],
        [Button.inline("👤 Use Account", b"account_mode")]
    ]
    await event.respond("Choose Mode:", buttons=buttons)

# ================= BUTTON =================
@bot.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id

    if event.data == b"bot_mode":
        user_mode[user_id] = "bot"
        await event.edit("✅ Bot mode selected.\nSend /drm link")

    elif event.data == b"account_mode":
        if not await account_client.is_user_authorized():
            return await event.edit("❌ Account session not found.")
        user_mode[user_id] = "account"
        await event.edit("✅ Account mode selected.\nSend /drm link")

# ================= MAIN =================
@bot.on(events.NewMessage)
async def main_handler(event):
    text = event.text.strip()
    user_id = event.sender_id

    if text.startswith("/start"):
        return

    if text.startswith("/drm"):
        try:
            url = text.split(" ", 1)[1]
            user_links[user_id] = url
            return await event.reply("🎬 Send quality: 720 or 1080")
        except:
            return await event.reply("❌ Use:\n/drm link")

    if user_id in user_links and text in ["720", "1080"]:
        url = user_links[user_id]
        quality = text

        status = await event.reply("⬇ Downloading...")

        try:
            file_path, duration, width, height = download_video(url, quality)
            thumb = download_thumbnail()

            await status.edit("📤 Uploading...")

            uploader = bot
            target = event.chat_id

            if user_mode.get(user_id) == "account":
                uploader = account_client
                target = GROUP_USERNAME

            await uploader.send_file(
                target,
                file_path,
                caption="✅ Upload Complete!",
                thumb=thumb,
                supports_streaming=True,
                attributes=[
                    types.DocumentAttributeVideo(
                        duration=int(duration),
                        w=width,
                        h=height,
                        supports_streaming=True,
                    )
                ],
            )

            await status.edit("✅ Done")

        except FloodWaitError as e:
            await status.edit(f"FloodWait {e.seconds}s")
        except Exception as e:
            await status.edit(f"Error: {e}")

# ================= RUN =================
if __name__ == "__main__":
    bot.start(bot_token=bot_token)

    if os.path.exists("user_account.session"):
        account_client.start()
        print("Account session loaded")
    else:
        print("No account session found")

    print("🚀 Bot Running...")
    bot.run_until_disconnected()
