import os
import asyncio
import yt_dlp
import time
import requests

from telethon import TelegramClient, events, types, Button
from telethon.errors import SessionPasswordNeededError

# ================= CONFIG =================
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

DOWNLOAD_PATH = "/tmp"
THUMB_URL = "https://static.pw.live/5eb393ee95fab7468a79d189/ADMIN/6e008265-fef8-4357-a290-07e1da1ff964.png"

# BOT CLIENT
bot = TelegramClient("bot_session", api_id, api_hash).start(bot_token=bot_token)

# STORE USER MODES
user_mode = {}
user_links = {}
login_state = {}
user_clients = {}  # store logged-in account sessions


# ================= HELPER =================
def format_duration(seconds):
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}" if h > 0 else f"{m:02}:{s:02}"


def download_thumbnail():
    thumb_path = os.path.join(DOWNLOAD_PATH, "thumb.jpg")
    r = requests.get(THUMB_URL)
    with open(thumb_path, "wb") as f:
        f.write(r.content)
    return thumb_path


async def download_video(url, quality):
    format_string = (
        "bestvideo[height<=720]+bestaudio/best[height<=720]"
        if quality == "720"
        else "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    )

    ydl_opts = {
        "format": format_string,
        "outtmpl": os.path.join(DOWNLOAD_PATH, "%(title)s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
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
@bot.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    await event.reply(
        "Choose Mode:",
        buttons=[
            [Button.inline("🤖 Use Bot", b"bot_mode")],
            [Button.inline("👤 Use Account", b"account_mode")],
        ],
    )


# ================= BUTTON HANDLER =================
@bot.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id

    if event.data == b"bot_mode":
        user_mode[user_id] = "bot"
        await event.edit("✅ Bot mode selected.\nNow send /drm link")

    elif event.data == b"account_mode":
        user_mode[user_id] = "account"
        login_state[user_id] = "phone"
        await event.edit("📱 Send your phone number with country code.")


# ================= LOGIN FLOW =================
@bot.on(events.NewMessage)
async def message_handler(event):
    user_id = event.sender_id
    text = event.text

    # ACCOUNT LOGIN FLOW
    if user_mode.get(user_id) == "account":

        if login_state.get(user_id) == "phone":
            login_state[user_id] = "otp"
            session_name = f"user_{user_id}"
            user_clients[user_id] = TelegramClient(session_name, api_id, api_hash)
            await user_clients[user_id].connect()

            await user_clients[user_id].send_code_request(text)
            await event.reply("📩 OTP sent. Send OTP now.")

        elif login_state.get(user_id) == "otp":
            try:
                await user_clients[user_id].sign_in(code=text)
                login_state[user_id] = None
                await event.reply("✅ Account Login Successful!\nNow send /drm link")
            except SessionPasswordNeededError:
                login_state[user_id] = "2fa"
                await event.reply("🔐 Send your 2-step password.")

        elif login_state.get(user_id) == "2fa":
            await user_clients[user_id].sign_in(password=text)
            login_state[user_id] = None
            await event.reply("✅ Account Login Successful!\nNow send /drm link")


# ================= DRM COMMAND =================
@bot.on(events.NewMessage(pattern="/drm"))
async def drm_handler(event):
    user_id = event.sender_id

    if user_id not in user_mode:
        return await event.reply("❌ First use /start")

    try:
        url = event.text.split(" ", 1)[1]
        user_links[user_id] = url
        await event.reply("🎬 Send quality: 720 or 1080")
    except:
        await event.reply("❌ Use:\n/drm your_link_here")


# ================= QUALITY =================
@bot.on(events.NewMessage)
async def quality_handler(event):
    user_id = event.sender_id

    if user_id not in user_links:
        return

    if event.text not in ["720", "1080"]:
        return

    url = user_links[user_id]
    quality = event.text
    status = await event.reply("⬇ Downloading...")

    try:
        file_path, duration, width, height = await download_video(url, quality)
        thumb = download_thumbnail()
        formatted_duration = format_duration(duration)

        await status.edit("📤 Uploading...")

        uploader = (
            bot
            if user_mode[user_id] == "bot"
            else user_clients[user_id]
        )

        await uploader.send_file(
            event.chat_id,
            file_path,
            caption=f"✅ Upload Complete!\n⏱ Duration: {formatted_duration}",
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

        await status.edit("✅ Done!")

        os.remove(file_path)
        os.remove(thumb)
        del user_links[user_id]

    except Exception as e:
        await status.edit(f"❌ Error:\n{str(e)}")


print("🚀 Bot Running...")
bot.run_until_disconnected()
