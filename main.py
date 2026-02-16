import os
import asyncio
from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError

# ================= CONFIG =================

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

GROUP_USERNAME = os.getenv("GROUP_USERNAME")  # example: @mygroup

# ==========================================

# Bot client
bot = TelegramClient("bot_session", api_id, api_hash)

# Account client (uses uploaded session)
account = TelegramClient("user_account", api_id, api_hash)

# ================= START HANDLER =================

@bot.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    buttons = [
        [Button.inline("🤖 Use Bot", b"bot_mode")],
        [Button.inline("👤 Use Account", b"account_mode")]
    ]
    await event.reply("Choose Mode:", buttons=buttons)


# ================= BUTTON HANDLER =================

@bot.on(events.CallbackQuery)
async def callback_handler(event):

    if event.data == b"bot_mode":
        await event.edit("🤖 Bot mode selected.\nSend file or link.")

    elif event.data == b"account_mode":

        # Check if session exists
        if not os.path.exists("user_account.session"):
            await event.edit("❌ Account session not found on server.")
            return

        try:
            await account.connect()

            if not await account.is_user_authorized():
                await event.edit("❌ Session invalid or expired.")
                return

            await event.edit("👤 Account mode selected.\nSend file to upload.")

        except Exception as e:
            await event.edit(f"❌ Account connection error:\n{str(e)}")


# ================= FILE HANDLER =================

@bot.on(events.NewMessage)
async def handle_file(event):

    if not event.file:
        return

    await event.reply("⬆️ Upload started via account...")

    try:
        await account.connect()

        if not await account.is_user_authorized():
            await event.reply("❌ Account session expired.")
            return

        file_path = await event.download_media()

        await account.send_file(
            GROUP_USERNAME,
            file_path,
            caption="Uploaded via account"
        )

        await event.reply("✅ Uploaded successfully.")

    except FloodWaitError as e:
        await event.reply(f"⏳ Flood wait: {e.seconds} seconds.")
        await asyncio.sleep(e.seconds)

    except Exception as e:
        await event.reply(f"❌ Upload error:\n{str(e)}")


# ================= MAIN =================

async def main():
    await bot.start(bot_token=bot_token)
    print("✅ Bot started")
    await bot.run_until_disconnected()


asyncio.run(main())
