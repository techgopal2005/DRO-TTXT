import os
import asyncio
import yt_dlp
import time
import requests
from telethon import TelegramClient, events, types, Button
from telethon.errors import FloodWaitError, SessionPasswordNeededError, RPCError

# ================= CONFIG =================
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

DOWNLOAD_PATH = "/tmp"
GROUP_USERNAME = "bhj_69"  # Without @
THUMB_URL = "https://static.pw.live/5eb393ee95fab7468a79d189/ADMIN/6e008265-fef8-4357-a290-07e1da1ff964.png"

# ================= CLIENTS =================
bot = TelegramClient("bot_session", api_id, api_hash)
account_session_file = "user_account.session"

# Account client (will login later if needed)
account_client = None
if os.path.exists(account_session_file):
    account_client = TelegramClient(account_session_file, api_id, api_hash)

# STORAGE
user_mode = {}
user_links = {}

print("🚀 Bot Initialized")


# ================= HELPERS =================
def format_duration(seconds):
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"


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
    fmt = (
        "bestvideo[height<=720]+bestaudio/best[height<=720]"
        if quality == "720"
        else "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    )

    ydl_opts = {
        "format": fmt,
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


# ================= BOT HANDLERS =================
@bot.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    buttons = [[Button.inline("🤖 Use Bot", b"bot_mode")]]
    if account_client:
        buttons.append([Button.inline("👤 Use Account", b"account_mode")])
    await event.reply("Choose Mode:", buttons=buttons)


@bot.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id

    if event.data == b"bot_mode":
        user_mode[user_id] = "bot"
        await event.edit("✅ Bot mode selected.\nSend /drm <link>")

    elif event.data == b"account_mode":
        if not account_client:
            await event.edit(
                "❌ Account session not found.\nLogin locally first and upload `user_account.session`."
            )
            return
        user_mode[user_id] = "account"
        await event.edit("✅ Account mode selected.\nSend /drm <link>")


@bot.on(events.NewMessage)
async def main_handler(event):
    user_id = event.sender_id
    text = event.text.strip()

    # ===== DRM COMMAND =====
    if text.startswith("/drm"):
        try:
            url = text.split(" ", 1)[1]
            user_links[user_id] = url
            return await event.reply("🎬 Send quality: 720 or 1080")
        except Exception:
            return await event.reply("❌ Invalid command. Use:\n/drm <link>")

    # ===== QUALITY =====
    if user_id in user_links and text in ["720", "1080"]:
        url = user_links[user_id]
        quality = text

        try:
            status = await event.reply("⬇ Downloading video...")
            file_path, duration, width, height = await download_video(url, quality)
            thumb = download_thumbnail()
            formatted_duration = format_duration(duration)

            await status.edit("📤 Upload started...")

            # Select uploader
            if user_mode.get(user_id) == "account":
                uploader = account_client
                target = GROUP_USERNAME
            else:
                uploader = bot
                target = event.chat_id

            # Upload with progress
            async def progress(current, total):
                percent = int(current * 100 / total)
                now = time.time()
                new_text = f"📤 Uploading... {percent}%"
                if not hasattr(progress, "last_update"):
                    progress.last_update = 0
                    progress.last_text = ""
                if now - progress.last_update > 5 and new_text != progress.last_text:
                    try:
                        await status.edit(new_text)
                        progress.last_update = now
                        progress.last_text = new_text
                    except Exception:
                        pass

            await uploader.send_file(
                target,
                file_path,
                caption=f"✅ Upload Complete!\n⏱ Duration: {formatted_duration}",
                thumb=thumb,
                supports_streaming=True,
                progress_callback=progress,
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
        except RPCError as e:
            await event.reply(f"❌ Telegram RPC error: {e}")
        except Exception as e:
            await event.reply(f"❌ Error during download/upload: {e}")

    # ===== UNKNOWN MESSAGE =====
    if not text.startswith("/"):
        return await event.reply(
            "❌ Unknown command.\nUse /start to begin or /drm <link> to download"
        )


# ================= RUN BOT SAFELY =================
async def start_bot():
    while True:
        try:
            print("🚀 Starting bot...")
            await bot.start(bot_token=bot_token)
            print("✅ Bot started")
            await bot.run_until_disconnected()
        except FloodWaitError as e:
            print(f"⚠ FloodWait: sleeping {e.seconds}s...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"❌ Bot crashed: {e}, retrying in 10s...")
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(start_bot())
