import os
import asyncio
import yt_dlp
import requests

from telethon import TelegramClient, events, Button, types
from telethon.errors import (
    FloodWaitError,
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError
)

# ================= CONFIG =================

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

DOWNLOAD_PATH = "/tmp"
GROUP_USERNAME = "bhj_69"  # without @

# ================= CLIENTS =================

bot = TelegramClient("bot_session", api_id, api_hash)

account_client = TelegramClient(
    "user_account",
    api_id,
    api_hash,
    device_model="Samsung S23",
    system_version="Android 13",
    app_version="10.6.1",
    lang_code="en"
)

# ================= STORAGE =================

user_mode = {}
login_state = {}
user_links = {}

# ================= START =================

@bot.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    await event.reply(
        "Choose Mode:",
        buttons=[
            [Button.inline("🤖 Use Bot", b"bot_mode")],
            [Button.inline("👤 Use Account", b"account_mode")]
        ]
    )

# ================= BUTTON =================

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id

    if event.data == b"bot_mode":
        user_mode[user_id] = "bot"
        await event.edit("✅ Bot Mode Selected.\nSend /drm link")

    elif event.data == b"account_mode":
        user_mode[user_id] = "account"
        login_state[user_id] = {"step": "phone"}
        await event.edit("📱 Send your phone number with country code.\nExample: +91XXXXXXXXXX")

# ================= MESSAGE HANDLER =================

@bot.on(events.NewMessage)
async def main_handler(event):
    if not event.text:
        return

    user_id = event.sender_id
    text = event.text.strip()

    # ===== LOGIN FLOW =====

    if user_id in login_state:

        state = login_state[user_id]

        # PHONE STEP
        if state["step"] == "phone":
            try:
                await account_client.connect()
                sent = await account_client.send_code_request(text)
                state["phone"] = text
                state["phone_code_hash"] = sent.phone_code_hash
                state["step"] = "otp"
                await event.reply("📨 Enter OTP code received in Telegram")
            except Exception as e:
                await event.reply(f"❌ Failed to send code:\n{e}")
            return

        # OTP STEP
        if state["step"] == "otp":
            try:
                await account_client.sign_in(
                    phone=state["phone"],
                    code=text,
                    phone_code_hash=state["phone_code_hash"]
                )
                await event.reply("✅ Login Successful!")
                del login_state[user_id]

            except PhoneCodeInvalidError:
                await event.reply("❌ Invalid OTP. Try again.")
            except PhoneCodeExpiredError:
                await event.reply("❌ OTP Expired. Send /start again.")
                del login_state[user_id]
            except SessionPasswordNeededError:
                state["step"] = "2fa"
                await event.reply("🔐 Enter your 2FA password")
            except Exception as e:
                await event.reply(f"❌ Login Error:\n{e}")
            return

        # 2FA STEP
        if state["step"] == "2fa":
            try:
                await account_client.sign_in(password=text)
                await event.reply("✅ Login Successful with 2FA!")
                del login_state[user_id]
            except Exception as e:
                await event.reply(f"❌ Wrong Password:\n{e}")
            return

    # ===== DRM COMMAND =====

    if text.startswith("/drm"):
        try:
            url = text.split(" ", 1)[1]
            user_links[user_id] = url
            await event.reply("🎬 Send quality: 720 or 1080")
        except:
            await event.reply("Usage:\n/drm link")
        return

    # ===== QUALITY =====

    if user_id in user_links and text in ["720", "1080"]:

        url = user_links[user_id]
        status = await event.reply("⬇ Downloading...")

        try:
            ydl_opts = {
                "format": f"bestvideo[height<={text}]+bestaudio/best",
                "outtmpl": os.path.join(DOWNLOAD_PATH, "%(title)s.%(ext)s"),
                "merge_output_format": "mp4",
                "quiet": True,
            }

            loop = asyncio.get_event_loop()

            def run():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file_path = ydl.prepare_filename(info)
                    if not file_path.endswith(".mp4"):
                        file_path = file_path.rsplit(".", 1)[0] + ".mp4"
                    return file_path, info

            file_path, info = await loop.run_in_executor(None, run)

            await status.edit("📤 Uploading...")

            uploader = bot
            target = event.chat_id

            if user_mode.get(user_id) == "account":
                uploader = account_client
                target = GROUP_USERNAME

            await uploader.send_file(
                target,
                file_path,
                caption="✅ Upload Complete",
                supports_streaming=True,
            )

            await status.edit("✅ Upload Done")
            os.remove(file_path)
            del user_links[user_id]

        except FloodWaitError as e:
            await status.edit(f"⚠ FloodWait: {e.seconds}s")
        except Exception as e:
            await status.edit(f"❌ Error:\n{e}")

# ================= MAIN =================

async def main():
    print("🚀 Starting Bot...")
    await bot.start(bot_token=bot_token)
    print("✅ Bot started")
    await bot.run_until_disconnected()

asyncio.run(main())
