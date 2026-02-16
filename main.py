import os
import asyncio
import yt_dlp
import time
import requests

from telethon import TelegramClient, events, types, Button
from telethon.errors import (
    FloodWaitError,
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
)

# ================= CONFIG =================
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

GROUP_USERNAME = "bhj_69"  # without @
DOWNLOAD_PATH = "/tmp"
THUMB_URL = "https://static.pw.live/5eb393ee95fab7468a79d189/ADMIN/6e008265-fef8-4357-a290-07e1da1ff964.png"

# ================= CLIENTS =================
bot = TelegramClient("bot_session", api_id, api_hash).start(bot_token=bot_token)

account_client = TelegramClient(
    "user_account",
    api_id,
    api_hash,
    device_model="Samsung Galaxy S23",
    system_version="13",
    app_version="10.0.1",
    lang_code="en"
)

# ================= STORAGE =================
user_mode = {}
user_links = {}
login_state = {}
login_data = {}

print("🚀 Bot Started")

# ================= HELPERS =================
def format_duration(seconds):
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}" if h > 0 else f"{m:02}:{s:02}"

def download_thumbnail():
    try:
        path = os.path.join(DOWNLOAD_PATH, "thumb.jpg")
        r = requests.get(THUMB_URL, timeout=10)
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except:
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
    buttons = [
        [Button.inline("🤖 Use Bot", b"bot_mode")],
        [Button.inline("👤 Use Account", b"account_mode")],
    ]
    await event.reply("Choose mode:", buttons=buttons)

# ================= BUTTON =================
@bot.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id

    if event.data == b"bot_mode":
        user_mode[user_id] = "bot"
        await event.edit("✅ Bot mode selected.\nSend /drm link")

    elif event.data == b"account_mode":
        user_mode[user_id] = "account"

        if not await account_client.is_user_authorized():
            login_state[user_id] = "await_phone"
            return await event.edit("📱 Send your phone number with country code\nExample: +919876543210")

        await event.edit("✅ Account already logged in.\nSend /drm link")

# ================= MESSAGE HANDLER =================
@bot.on(events.NewMessage)
async def main_handler(event):
    user_id = event.sender_id
    text = event.text.strip()

    # ===== LOGIN FLOW =====
    if login_state.get(user_id) == "await_phone":
        try:
            sent = await account_client.send_code_request(text)
            login_data[user_id] = {
                "phone": text,
                "phone_code_hash": sent.phone_code_hash
            }
            login_state[user_id] = "await_code"
            return await event.reply("📩 OTP sent. Send the OTP.")
        except Exception as e:
            return await event.reply(f"❌ Failed to send OTP:\n{e}")

    if login_state.get(user_id) == "await_code":
        try:
            data = login_data[user_id]
            await account_client.sign_in(
                phone=data["phone"],
                code=text,
                phone_code_hash=data["phone_code_hash"]
            )
            login_state.pop(user_id)
            return await event.reply("✅ Account login successful!")
        except SessionPasswordNeededError:
            login_state[user_id] = "await_2fa"
            return await event.reply("🔐 Send your 2-step password.")
        except (PhoneCodeExpiredError, PhoneCodeInvalidError):
            login_state.pop(user_id)
            return await event.reply("❌ OTP expired or invalid. Try again.")
        except Exception as e:
            login_state.pop(user_id)
            return await event.reply(f"❌ Login error:\n{e}")

    if login_state.get(user_id) == "await_2fa":
        try:
            await account_client.sign_in(password=text)
            login_state.pop(user_id)
            return await event.reply("✅ 2FA successful. Account logged in!")
        except Exception as e:
            login_state.pop(user_id)
            return await event.reply(f"❌ Wrong password:\n{e}")

    # ===== DRM =====
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

            await status.edit("📤 Upload started...")

            uploader = bot
            target = event.chat_id

            if user_mode.get(user_id) == "account":
                if not await account_client.is_user_authorized():
                    return await status.edit("❌ Account not logged in.")
                uploader = account_client
                target = GROUP_USERNAME

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
                        supports_streaming=True
                    )
                ]
            )

            await status.edit("✅ Upload Completed!")

            if os.path.exists(file_path):
                os.remove(file_path)
            if thumb and os.path.exists(thumb):
                os.remove(thumb)

            user_links.pop(user_id)

        except FloodWaitError as e:
            await status.edit(f"⚠ FloodWait: Wait {e.seconds} sec")
        except Exception as e:
            await status.edit(f"❌ Error:\n{e}")
