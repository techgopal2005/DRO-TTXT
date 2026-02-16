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
GROUP_USERNAME = "@bhj_69"   # 🔥 CHANGE THIS
THUMB_URL = "https://static.pw.live/5eb393ee95fab7468a79d189/ADMIN/6e008265-fef8-4357-a290-07e1da1ff964.png"

# BOT CLIENT
bot = TelegramClient("bot_session", api_id, api_hash).start(bot_token=bot_token)

# STORAGE
user_mode = {}
user_links = {}
login_state = {}
user_clients = {}

print("🚀 Bot Started")

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
        await event.edit("✅ Bot mode selected.\nSend /drm link")

    elif event.data == b"account_mode":
        user_mode[user_id] = "account"
        login_state[user_id] = "phone"
        await event.edit("📱 Send phone number with country code.")


# ================= MESSAGE HANDLER =================
@bot.on(events.NewMessage)
async def main_handler(event):
    user_id = event.sender_id
    text = event.text.strip()

    # ===== ACCOUNT LOGIN FLOW =====
    if user_mode.get(user_id) == "account":

        if login_state.get(user_id) == "phone":
            session_name = f"user_{user_id}"
            user_clients[user_id] = TelegramClient(session_name, api_id, api_hash)
            await user_clients[user_id].connect()
            await user_clients[user_id].send_code_request(text)

            login_state[user_id] = "otp"
            return await event.reply("📩 OTP sent. Send OTP.")

        elif login_state.get(user_id) == "otp":
            try:
                await user_clients[user_id].sign_in(code=text)
                login_state[user_id] = None
                return await event.reply("✅ Account Login Success.\nSend /drm link")
            except SessionPasswordNeededError:
                login_state[user_id] = "2fa"
                return await event.reply("🔐 Send 2FA password.")

        elif login_state.get(user_id) == "2fa":
            await user_clients[user_id].sign_in(password=text)
            login_state[user_id] = None
            return await event.reply("✅ Account Login Success.\nSend /drm link")

    # ===== DRM COMMAND =====
    if text.startswith("/drm"):
        try:
            url = text.split(" ", 1)[1]
            user_links[user_id] = url
            return await event.reply("🎬 Send quality: 720 or 1080")
        except:
            return await event.reply("❌ Use:\n/drm your_link")

    # ===== QUALITY =====
    if user_id in user_links and text in ["720", "1080"]:
        url = user_links[user_id]
        quality = text

        status = await event.reply("⬇ Downloading...")

        try:
            file_path, duration, width, height = await download_video(url, quality)
            thumb = download_thumbnail()
            formatted_duration = format_duration(duration)

            await status.edit("📤 Uploading...")

            if user_mode.get(user_id) == "account":
                uploader = user_clients[user_id]
                target = GROUP_USERNAME  # 🔥 ALWAYS UPLOAD TO GROUP
            else:
                uploader = bot
                target = event.chat_id  # bot uploads in same chat

            await uploader.send_file(
                target,
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

    # ===== UNKNOWN MESSAGE =====
    if not text.startswith("/"):
        return


# ================= RUN =================
bot.run_until_disconnected()
