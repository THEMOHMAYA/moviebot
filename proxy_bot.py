import asyncio
import logging
import os
import sys

# Python 3.12+ event loop compatibility
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from pyrogram import Client
from pyrogram.types import Message as PMessage

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

TARGET_BOT = os.getenv("TARGET_BOT", "iPapkornN2bot").replace("@", "").strip()

# Storage for dynamic button mappings:
# { btn_id: { "target_msg_id": int, "row": int, "col": int, "user_id": int, "url": str, "btn_text": str } }
BUTTON_MAPPINGS = {}

# Pyrogram Userbot Client
userbot = Client(
    name="relay_userbot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    session_string=config.SESSION_STRING,
    in_memory=True
)

# Aiogram Bot Instance
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

search_lock = asyncio.Lock()


@dp.message(CommandStart())
async def start_handler(message: Message):
    user_first = message.from_user.first_name if message.from_user else "User"
    await message.answer(
        f"👋 <b>Namaste {user_first}!</b>\n\n"
        f"🎬 <b>Movie & Series Search Bot</b>\n\n"
        f"🔍 Yaha kisi bhi movie ka naam likhein:\n"
        f"👉 <code>Pushpa 2</code>\n"
        f"👉 <code>Spider Man</code>"
    )


@dp.message(F.chat.type == "private", F.text, ~F.text.startswith("/"))
async def search_relay_handler(message: Message):
    query = (message.text or "").strip()
    user_id = message.from_user.id if message.from_user else message.chat.id
    
    if len(query) < 2:
        await message.answer("⚠️ Kripya sahi movie ka naam likhein.")
        return

    wait_msg = await message.answer(f"🔍 <i>Searching for '<b>{query}</b>' ...</i>")

    async with search_lock:
        try:
            logger.info(f"User {user_id} -> Query: '{query}' -> Target: @{TARGET_BOT}")
            
            # Send query message to Target Bot
            sent_msg = await userbot.send_message(TARGET_BOT, query)
            
            # Wait for response from target bot
            target_reply: PMessage = None
            for _ in range(25):
                await asyncio.sleep(0.6)
                async for last_msg in userbot.get_chat_history(TARGET_BOT, limit=4):
                    if last_msg.id > sent_msg.id and (last_msg.reply_markup or last_msg.text):
                        target_reply = last_msg
                        break
                if target_reply:
                    break

            if not target_reply:
                await wait_msg.edit_text("❌ Database bot ne koi response nahi diya. Thodi der baad dubara try karein.")
                return

            # Extract inline buttons
            keyboard = []
            if target_reply.reply_markup and target_reply.reply_markup.inline_keyboard:
                for r_idx, row in enumerate(target_reply.reply_markup.inline_keyboard):
                    btn_row = []
                    for c_idx, btn in enumerate(row):
                        btn_id = f"rly_{target_reply.id}_{r_idx}_{c_idx}"
                        BUTTON_MAPPINGS[btn_id] = {
                            "target_msg_id": target_reply.id,
                            "row": r_idx,
                            "col": c_idx,
                            "user_id": user_id,
                            "url": getattr(btn, "url", None),
                            "btn_text": btn.text
                        }
                        btn_row.append(InlineKeyboardButton(text=btn.text, callback_data=btn_id))
                    keyboard.append(btn_row)

            clean_text = (
                f"🎬 <b>Results for:</b> <code>{query}</code>\n\n"
                f"👇 <i>Neeche diye gaye button par click karke download karein:</i>"
            )

            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
            await wait_msg.edit_text(clean_text, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error during search relay: {e}", exc_info=True)
            await wait_msg.edit_text("⚠️ Search karne me error aaya. Kripya dobara try karein.")


@dp.callback_query(F.data.startswith("rly_"))
async def button_click_relay_handler(query: CallbackQuery):
    btn_id = query.data or ""
    btn_info = BUTTON_MAPPINGS.get(btn_id)

    if not btn_info:
        await query.answer("⚠️ Session expire ho gaya. Kripya movie dobara search karein.", show_alert=True)
        return

    await query.answer("⚡ Target bot se file mangwayi jaa rahi hai...")

    user_id = query.from_user.id
    target_msg_id = btn_info["target_msg_id"]
    row = btn_info["row"]
    col = btn_info["col"]
    btn_url = btn_info.get("url")

    status_msg = None
    if query.message and isinstance(query.message, Message):
        status_msg = await query.message.reply("⏳ <i>File download ho rahi hai, kripya 10-15 seconds wait karein...</i>")

    async with search_lock:
        try:
            logger.info(f"Action on msg {target_msg_id} [r:{row}, c:{col}] from @{TARGET_BOT}")

            last_seen_msg_id = target_msg_id

            # If button has URL with /start parameter, trigger /start in target bot
            if btn_url and "start=" in btn_url:
                start_param = btn_url.split("start=")[-1]
                logger.info(f"Triggering start param: /start {start_param}")
                sent_start = await userbot.send_message(TARGET_BOT, f"/start {start_param}")
                last_seen_msg_id = sent_start.id
            else:
                # Regular inline callback button click
                target_msg = await userbot.get_messages(TARGET_BOT, target_msg_id)
                try:
                    await target_msg.click(col, row)
                except Exception as click_err:
                    logger.warning(f"Click trigger note: {click_err}")

            # Wait for incoming media/file from target bot
            received_media_msg = None
            for _ in range(30):
                await asyncio.sleep(0.7)
                async for m in userbot.get_chat_history(TARGET_BOT, limit=4):
                    if m.id > last_seen_msg_id and (m.video or m.document or m.audio):
                        received_media_msg = m
                        break
                if received_media_msg:
                    break

            if not received_media_msg:
                if status_msg:
                    await status_msg.edit_text("❌ File aane me timeout ho gaya. Kripya dubara click karein.")
                return

            # Send/Copy media to user
            try:
                await userbot.copy_message(
                    chat_id=user_id,
                    from_chat_id=TARGET_BOT,
                    message_id=received_media_msg.id
                )
                if status_msg:
                    await status_msg.delete()
            except Exception as copy_err:
                logger.error(f"Direct copy error: {copy_err}, falling back to forward...")
                await userbot.forward_messages(
                    chat_id=user_id,
                    from_chat_id=TARGET_BOT,
                    message_ids=[received_media_msg.id]
                )
                if status_msg:
                    await status_msg.delete()

        except Exception as e:
            logger.error(f"Error relaying media: {e}", exc_info=True)
            if status_msg:
                await status_msg.edit_text(f"⚠️ Error: {e}")


async def main():
    logger.info("Connecting Relay Userbot via String Session...")
    await userbot.start()
    user_me = await userbot.get_me()
    logger.info(f"✅ Userbot Connected as: {user_me.first_name} (@{user_me.username or 'NoUsername'}) [ID: {user_me.id}]")

    logger.info(f"🔗 Target Bot Configured: @{TARGET_BOT}")

    bot_info = await bot.get_me()
    logger.info(f"🤖 Main Bot Live: @{bot_info.username} [ID: {bot_info.id}]")

    try:
        await dp.start_polling(bot)
    finally:
        await userbot.stop()


if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        pass

