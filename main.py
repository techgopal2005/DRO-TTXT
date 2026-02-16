import os
import asyncio
import yt_dlp
import time
import requests

from telethon import TelegramClient, events, types, Button
from telethon.errors import SessionPasswordNeededError, FloodWaitError

# ================= CONFIG =================
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

DOWNLOAD_PATH = "/tmp"
GROUP_USERNAME = "@bhj_69"   # 🔥 Replace with your group's username
THUMB_URL = "https://static.pw.live/5eb393ee95fab7468a79d189/ADMIN/6e008265-fef8-4357-a290-07e1da1ff964.png"

# BOT CLIENT
bot = TelegramClient("bot_session", api_id, api_hash).start(bot_token=bot_token)

# STORAGE
user_mode = {}
user_links = {}
login_state = {}
user_clients = {}

print("🚀 Bot Started")

# ================= HELPERS =================
def format_duration(seconds):
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}" if h > 0 else f"{m:02}:{s:02}"


def download_thumbnail():
    thumb_path = os.path.join(DOWNLOAD_PATH, "thumb.jpg")
    try:
        r = requests.get(THUMB_URL, timeout=15)
        r.raise_for_status()
        with open(thumb_path, "wb") as f:
            f.write(r.content)
        return thumb_path
    except Exception as e:
        print(f"⚠ Thumbnail download failed: {e}")
        return None


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
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 10,
    }

    try:
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
    except Exception as e:
        raise Exception(f"Download failed: {e}")


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


# ================= MAIN HANDLER =================
@bot.on(events.NewMessage)
async def main_handler(event):
    user_id = event.sender_id
    text = event.text.strip()

    # ===== ACCOUNT LOGIN FLOW =====
    if user_mode.get(user_id) == "account":
        try:
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
        except Exception as e:
            return await event.reply(f"❌ Login error: {e}")

    # ===== DRM COMMAND =====
    if text.startswith("/drm"):
        try:
            url = text.split(" ", 1)[1]
            user_links[user_id] = url
            return await event.reply("🎬 Send quality: 720 or 1080")
        except Exception as e:
            return await event.reply(f"❌ Invalid command. Use:\n/drm your_link\nError: {e}")

    # ===== QUALITY =====
    if user_id in user_links and text in ["720", "1080"]:
        url = user_links[user_id]
        quality = text

        try:
            status = await event.reply("⬇ Downloading...")

            file_path, duration, width, height = await download_video(url, quality)
            thumb = download_thumbnail()
            formatted_duration = format_duration(duration)

            # Notify user upload is starting
            await status.edit("📤 Upload started...")

            if user_mode.get(user_id) == "account":
                uploader = user_clients[user_id]
                target = GROUP_USERNAME  # Upload to group
            else:
                uploader = bot
                target = event.chat_id  # Bot uploads in same chat

            # Upload file
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

            await status.edit("✅ Upload Completed!")

            # Cleanup
            if os.path.exists(file_path):
                os.remove(file_path)
            if thumb and os.path.exists(thumb):
                os.remove(thumb)
            del user_links[user_id]

        except FloodWaitError as e:
            await event.reply(f"⚠ FloodWait: wait {e.seconds} seconds")
        except Exception as e:
            await event.reply(f"❌ Error during upload: {e}")

    # ===== UNKNOWN MESSAGE =====
    if not text.startswith("/"):
        return await event.reply(
            "❌ Unknown command.\nUse /start to begin or /drm link to download"
        )


# ================= RUN =================
bot.run_until_disconnected()
