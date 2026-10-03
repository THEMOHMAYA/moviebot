import asyncio
import logging
import sys
import re
from typing import Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from telethon import TelegramClient
from telethon.sessions import StringSession

import config
import database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
# Suppress noisy telethon internal reconnect logs
logging.getLogger("telethon.network.mtprotosender").setLevel(logging.ERROR)
logging.getLogger("telethon.network.connection.connection").setLevel(logging.ERROR)

logger = logging.getLogger("MovieBot")

# In-memory mapping for buttons and delivery queue:
BUTTON_CACHE: Dict[str, Dict[str, Any]] = {}
TRANSFER_QUEUE: Dict[int, asyncio.Future] = {}

bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Global userbot & lock references (initialized in main)
userbot: TelegramClient = None
relay_lock: asyncio.Lock = None


@dp.message(F.chat.type == "private", F.document | F.video | F.audio | F.photo)
async def incoming_userbot_media_handler(message: Message):
    """Listens for media forwarded from Userbot to deliver cleanly to user."""
    for uid, fut in list(TRANSFER_QUEUE.items()):
        if not fut.done():
            fut.set_result(message)
            return


def clean_target_text(text: str) -> str:
    """Removes promotional tags from target bot text."""
    if not text:
        return ""
    cleaned = re.sub(r'@\w+', '', text)
    cleaned = re.sub(r'Rotate your.*', '', cleaned)
    cleaned = re.sub(r'__+', '', cleaned)
    cleaned = re.sub(r'\*+', '', cleaned)
    return cleaned.strip()


async def check_force_sub(user_id: int) -> bool:
    """Checks if user has joined the required force subscribe channel."""
    if not config.FORCE_SUB_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(chat_id=config.FORCE_SUB_CHANNEL, user_id=user_id)
        if member.status in ["creator", "administrator", "member", "restricted"]:
            return True
        return False
    except Exception as e:
        logger.warning(f"Force sub check note ({e}) - allowing access")
        return True


def get_force_sub_keyboard():
    """Builds inline keyboard for Force Subscribe channel."""
    channel_link = config.FORCE_SUB_LINK
    if not channel_link:
        if str(config.FORCE_SUB_CHANNEL).startswith("@"):
            channel_link = f"https://t.me/{config.FORCE_SUB_CHANNEL.replace('@', '')}"
        elif str(config.FORCE_SUB_CHANNEL).startswith("-100"):
            channel_link = f"https://t.me/c/{str(config.FORCE_SUB_CHANNEL).replace('-100', '')}/1"
        else:
            channel_link = "https://t.me/frozentools"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Join Official Channel", url=channel_link)],
        [InlineKeyboardButton(text="🔄 Verify / Try Again", callback_data="fsub_check")]
    ])


async def schedule_message_auto_delete(chat_id: int, message_id: int, user_display: str):
    """Deletes a message after AUTO_DELETE_SECONDS and sends self-destructing notice."""
    try:
        await asyncio.sleep(config.AUTO_DELETE_SECONDS)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass

        # Send deletion notification
        notice_text = (
            f"Hey {user_display},\n\n"
            f"Your Request Has Been Deleted👍🏻\n"
            f"(Due To Avoid Copyrights Issue😌)\n\n"
            f"Iꜰ Yᴏᴜ Wᴀɴᴛ Tʜᴀᴛ Fɪʟᴇ, Rᴇqᴜᴇꜱᴛ Aɢᴀɪɴ ❤️"
        )
        try:
            notice_msg = await bot.send_message(chat_id=chat_id, text=notice_text)
            # Delete notice after NOTICE_DELETE_SECONDS (30s)
            await asyncio.sleep(config.NOTICE_DELETE_SECONDS)
            try:
                await bot.delete_message(chat_id=chat_id, message_id=notice_msg.message_id)
            except Exception:
                pass
        except Exception:
            pass
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"Auto-delete task note: {e}")


@dp.message(CommandStart())
async def start_handler(message: Message):
    """Handles /start command."""
    if message.from_user:
        await database.add_user(
            user_id=message.from_user.id,
            first_name=message.from_user.first_name or "",
            username=message.from_user.username or ""
        )

    user_id = message.from_user.id if message.from_user else message.chat.id
    if not await check_force_sub(user_id):
        await message.answer(
            "🔒 <b>Access Denied — Channel Subscription Required</b>\n\n"
            f"To access our movie database and download files, please join our official update channel:\n\n"
            f"👉 <b>Channel:</b> <code>{config.FORCE_SUB_CHANNEL or '@frozentools'}</code>\n\n"
            "<i>After joining, tap the <b>'🔄 Verify / Try Again'</b> button below!</i>",
            reply_markup=get_force_sub_keyboard()
        )
        return

    user_name = message.from_user.first_name if message.from_user else "Friend"
    welcome_msg = (
        f"👋 <b>Hello {user_name}!</b>\n\n"
        f"🎬 <b>Welcome to Movie & Series Hub!</b>\n\n"
        f"🔍 Simply send the name of any Movie or Web Series you'd like to watch.\n"
        f"⚡ <i>Our high-speed servers will instantly fetch the best quality files for you!</i>\n\n"
        f"📌 <b>Examples:</b>\n"
        f"👉 <code>Pushpa 2</code>\n"
        f"👉 <code>Inception</code>\n"
        f"👉 <code>Money Heist</code>\n"
        f"👉 <code>Interstellar</code>"
    )
    await message.answer(welcome_msg)


@dp.callback_query(F.data == "fsub_check")
async def fsub_check_handler(query: CallbackQuery):
    """Handles force-sub verify button click."""
    user_id = query.from_user.id
    if await check_force_sub(user_id):
        await query.answer("✅ Verification successful! You can now search and download any movie.", show_alert=True)
        if query.message and isinstance(query.message, Message):
            await query.message.edit_text(
                "🎬 <b>Access Granted!</b>\n\n"
                "🔍 Send the name of any Movie or Series to search:\n"
                "👉 <code>Pushpa 2</code>\n"
                "👉 <code>Inception</code>"
            )
    else:
        await query.answer(f"❌ You have not joined {config.FORCE_SUB_CHANNEL or '@frozentools'} yet. Please join the channel first!", show_alert=True)


@dp.message(Command("broadcast"))
async def broadcast_handler(message: Message):
    """Admin command to broadcast text or media to all users."""
    if not message.from_user or message.from_user.id not in config.ADMINS:
        return

    reply_to = message.reply_to_message
    broadcast_text = message.text.replace("/broadcast", "").strip() if message.text else ""

    if not reply_to and not broadcast_text:
        await message.answer(
            "⚠️ <b>Broadcast Usage:</b>\n\n"
            "1. Reply to any post/video/photo/text with <code>/broadcast</code>\n"
            "2. Or type <code>/broadcast Your Message Here</code>"
        )
        return

    users = await database.get_all_users()
    total_users = len(users)
    if total_users == 0:
        await message.answer("❌ No registered users found in the database.")
        return

    status_msg = await message.answer(f"📢 <b>Broadcast Started...</b>\n\n👥 Target Users: <code>{total_users}</code>")

    success = 0
    failed = 0
    start_time = asyncio.get_event_loop().time()

    for idx, uid in enumerate(users, 1):
        try:
            if reply_to:
                await bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=reply_to.message_id)
            else:
                await bot.send_message(chat_id=uid, text=broadcast_text)
            success += 1
        except Exception:
            failed += 1

        if idx % 25 == 0:
            await asyncio.sleep(0.3)

    duration = round(asyncio.get_event_loop().time() - start_time, 1)
    report_text = (
        f"✅ <b>Broadcast Completed!</b>\n\n"
        f"👥 <b>Total Users:</b> <code>{total_users}</code>\n"
        f"🟢 <b>Delivered:</b> <code>{success}</code>\n"
        f"🔴 <b>Failed / Blocked:</b> <code>{failed}</code>\n"
        f"⏱️ <b>Time Taken:</b> <code>{duration}s</code>"
    )
    await status_msg.edit_text(report_text)


@dp.message(Command("stats"))
async def stats_handler(message: Message):
    """Shows bot statistics."""
    if not message.from_user or message.from_user.id not in config.ADMINS:
        return
    total_users = await database.get_total_users_count()
    await message.answer(
        f"📊 <b>System Statistics:</b>\n\n"
        f"👥 <b>Total Registered Users:</b> <code>{total_users}</code>\n"
        f"📢 <b>Force Subscribe Channel:</b> <code>{config.FORCE_SUB_CHANNEL or 'Disabled'}</code>\n"
        f"⏳ <b>Auto-Delete Duration:</b> <code>{config.AUTO_DELETE_SECONDS}s</code>\n"
        f"⚡ <b>Engine Status:</b> <code>Active & Healthy</code>"
    )


@dp.message(F.chat.type == "private", F.text, ~F.text.startswith("/"))
async def search_handler(message: Message):
    """Searches movie database and presents results."""
    if message.from_user:
        await database.add_user(
            user_id=message.from_user.id,
            first_name=message.from_user.first_name or "",
            username=message.from_user.username or ""
        )

    user_id = message.from_user.id if message.from_user else message.chat.id
    if not await check_force_sub(user_id):
        await message.answer(
            "🔒 <b>Access Denied — Channel Subscription Required</b>\n\n"
            f"To access our movie database and download files, please join our official update channel:\n\n"
            f"👉 <b>Channel:</b> <code>{config.FORCE_SUB_CHANNEL or '@frozentools'}</code>\n\n"
            "<i>After joining, tap the <b>'🔄 Verify / Try Again'</b> button below!</i>",
            reply_markup=get_force_sub_keyboard()
        )
        return

    query = (message.text or "").strip()
    if len(query) < 2:
        await message.answer("⚠️ Please enter at least 2 characters to search.")
        return

    wait_msg = await message.answer(f"🔍 <i>Searching for '<b>{query}</b>' in database... Please wait...</i>")

    async with relay_lock:
        try:
            logger.info(f"User {user_id} -> Query: '{query}'")

            # Send search query to target bot
            sent_msg = await userbot.send_message(config.TARGET_BOT, query)

            # Wait for response with buttons from target bot (fast 250ms polling)
            target_reply = None
            for _ in range(35):
                await asyncio.sleep(0.25)
                async for msg in userbot.iter_messages(config.TARGET_BOT, limit=4):
                    if msg.id > sent_msg.id and (msg.buttons or msg.media or msg.text):
                        target_reply = msg
                        break
                if target_reply:
                    break

            if not target_reply:
                await wait_msg.edit_text("❌ Database search timed out. Please try again in a moment.")
                return

            # If no buttons found or empty search result
            if not target_reply.buttons:
                reply_text = clean_target_text(target_reply.text) or f"❌ No results found for '{query}'."
                await wait_msg.edit_text(
                    f"🎬 <b>Results for:</b> <code>{query}</code>\n\n"
                    f"{reply_text}\n\n"
                    f"💡 <i>Please check your spelling or try another keyword.</i>"
                )
                return

            # Build inline keyboard from target bot's buttons
            inline_keyboard = []
            for r_idx, row in enumerate(target_reply.buttons):
                btn_row = []
                for c_idx, btn in enumerate(row):
                    btn_key = f"t_{target_reply.id}_{r_idx}_{c_idx}"
                    is_navigation = any(k in btn.text.lower() for k in ["page", "next", "prev", "⏩", "⏪", "◀️", "▶️", "▫️"])
                    
                    BUTTON_CACHE[btn_key] = {
                        "target_msg_id": target_reply.id,
                        "row": r_idx,
                        "col": c_idx,
                        "user_id": user_id,
                        "url": getattr(btn, "url", None),
                        "text": btn.text,
                        "is_nav": is_navigation,
                        "query": query
                    }

                    if btn.url and not ("start=" in btn.url or "t.me" in btn.url):
                        btn_row.append(InlineKeyboardButton(text=btn.text, url=btn.url))
                    else:
                        btn_row.append(InlineKeyboardButton(text=btn.text, callback_data=btn_key))
                
                if btn_row:
                    inline_keyboard.append(btn_row)

            result_text = (
                f"🎬 <b>Search Results for:</b> <code>{query}</code>\n\n"
                f"👇 <i>Select your preferred quality/file below to download:</i>"
            )

            markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard) if inline_keyboard else None
            await wait_msg.edit_text(result_text, reply_markup=markup)

            # Schedule auto-delete of search results message
            user_display = f"@{message.from_user.username}" if (message.from_user and message.from_user.username) else (message.from_user.first_name if message.from_user else "User")
            asyncio.create_task(schedule_message_auto_delete(user_id, wait_msg.message_id, user_display))

        except Exception as e:
            logger.error(f"Search query error: {e}", exc_info=True)
            await wait_msg.edit_text("⚠️ An error occurred while searching. Please try again.")


@dp.callback_query(F.data.startswith("t_"))
async def callback_relay_handler(query: CallbackQuery):
    """Handles button clicks for pagination and file delivery."""
    btn_key = query.data or ""
    btn_data = BUTTON_CACHE.get(btn_key)

    if not btn_data:
        await query.answer("⚠️ Search session expired. Please search for the movie again.", show_alert=True)
        return

    user_id = query.from_user.id
    target_msg_id = btn_data["target_msg_id"]
    row = btn_data["row"]
    col = btn_data["col"]
    is_nav = btn_data.get("is_nav", False)
    search_q = btn_data.get("query", "Movie")

    # If it's a pagination or navigation button
    if is_nav:
        await query.answer("⚡ Loading...")
        async with relay_lock:
            try:
                target_msg = await userbot.get_messages(config.TARGET_BOT, ids=target_msg_id)
                if target_msg and target_msg.buttons and row < len(target_msg.buttons) and col < len(target_msg.buttons[row]):
                    target_btn = target_msg.buttons[row][col]
                    try:
                        await target_btn.click()
                    except Exception as click_err:
                        logger.debug(f"Target button click note: {click_err}")

                    # Fast poll for edited buttons (every 150ms)
                    updated_msg = None
                    for _ in range(10):
                        await asyncio.sleep(0.15)
                        msg_check = await userbot.get_messages(config.TARGET_BOT, ids=target_msg_id)
                        if msg_check and msg_check.buttons:
                            if msg_check.buttons != target_msg.buttons:
                                updated_msg = msg_check
                                break
                            updated_msg = msg_check

                    if not updated_msg or not updated_msg.buttons:
                        async for m in userbot.iter_messages(config.TARGET_BOT, limit=3):
                            if m.buttons:
                                updated_msg = m
                                break

                    if updated_msg and updated_msg.buttons and query.message and isinstance(query.message, Message):
                        new_keyboard = []
                        for r_i, r_val in enumerate(updated_msg.buttons):
                            b_row = []
                            for c_i, b_val in enumerate(r_val):
                                n_key = f"t_{updated_msg.id}_{r_i}_{c_i}"
                                is_n = any(k in b_val.text.lower() for k in ["page", "next", "prev", "⏩", "⏪", "◀️", "▶️", "▫️"])
                                BUTTON_CACHE[n_key] = {
                                    "target_msg_id": updated_msg.id,
                                    "row": r_i,
                                    "col": c_i,
                                    "user_id": user_id,
                                    "url": getattr(b_val, "url", None),
                                    "text": b_val.text,
                                    "is_nav": is_n,
                                    "query": search_q
                                }
                                if b_val.url and not ("start=" in b_val.url or "t.me" in b_val.url):
                                    b_row.append(InlineKeyboardButton(text=b_val.text, url=b_val.url))
                                else:
                                    b_row.append(InlineKeyboardButton(text=b_val.text, callback_data=n_key))
                            if b_row:
                                new_keyboard.append(b_row)

                        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=new_keyboard))
                return
            except Exception as e:
                logger.error(f"Navigation error: {e}", exc_info=True)
                return

    # Regular file download button click
    await query.answer("⚡ Fetching your requested file from cloud storage...")
    
    status_msg = None
    if query.message and isinstance(query.message, Message):
        status_msg = await query.message.reply("⏳ <i>Fetching file from cloud server... Please wait a few seconds.</i>")

    async with relay_lock:
        try:
            target_msg = await userbot.get_messages(config.TARGET_BOT, ids=target_msg_id)
            if not target_msg or not target_msg.buttons:
                if status_msg:
                    await status_msg.edit_text("❌ Request session expired. Please search again.")
                return

            target_btn = target_msg.buttons[row][col]
            logger.info(f"Clicking button: '{target_btn.text}' on msg {target_msg_id}")

            last_msg_id = target_msg_id
            start_param = None
            try:
                click_res = await target_btn.click()
                if hasattr(click_res, 'url') and click_res.url and "start=" in click_res.url:
                    start_param = click_res.url.split("start=")[-1]
            except Exception as click_err:
                logger.debug(f"Click callback error: {click_err}")

            if not start_param and btn_data.get("url") and "start=" in btn_data["url"]:
                start_param = btn_data["url"].split("start=")[-1]

            if start_param:
                logger.info(f"Triggering start param: /start {start_param}")
                sent_start = await userbot.send_message(config.TARGET_BOT, f"/start {start_param}")
                last_msg_id = sent_start.id

            # Fast wait for target bot to deliver the media file
            media_msg = None
            for _ in range(40):
                await asyncio.sleep(0.3)
                async for m in userbot.iter_messages(config.TARGET_BOT, limit=3):
                    if m.id > last_msg_id and m.media:
                        media_msg = m
                        break
                if media_msg:
                    break

            if not media_msg:
                if status_msg:
                    await status_msg.edit_text("❌ Download timed out. Please try again.")
                return

            if status_msg:
                await status_msg.edit_text("📤 <i>Sending file to your chat...</i>")

            # Deliver media cleanly to user via Bot API (no target ads, clean caption)
            delivered = False
            loop = asyncio.get_running_loop()
            transfer_future = loop.create_future()
            TRANSFER_QUEUE[user_id] = transfer_future

            bot_info = await bot.get_me()
            try:
                # Userbot forwards media to our bot
                logger.info(f"Userbot forwarding media {media_msg.id} to @{bot_info.username}...")
                await userbot.forward_messages(
                    entity=bot_info.username,
                    messages=[media_msg.id],
                    from_peer=config.TARGET_BOT
                )

                # Wait for bot to receive the media
                incoming_bot_msg: Message = await asyncio.wait_for(transfer_future, timeout=15.0)
                media = incoming_bot_msg.video or incoming_bot_msg.document or incoming_bot_msg.audio or (incoming_bot_msg.photo[-1] if incoming_bot_msg.photo else None)

                if media:
                    clean_caption = (
                        f"🎬 <b>{btn_data['text']}</b>\n\n"
                        f"👉This file automatically❗delete after  2 minute❗so please forward in another chat👈\n\n"
                        f"⚡ <i>Delivered by @{bot_info.username}</i>"
                    )
                    
                    sent_file_msg: Message = None
                    if incoming_bot_msg.video:
                        sent_file_msg = await bot.send_video(chat_id=user_id, video=media.file_id, caption=clean_caption)
                    elif incoming_bot_msg.document:
                        sent_file_msg = await bot.send_document(chat_id=user_id, document=media.file_id, caption=clean_caption)
                    elif incoming_bot_msg.audio:
                        sent_file_msg = await bot.send_audio(chat_id=user_id, audio=media.file_id, caption=clean_caption)
                    elif incoming_bot_msg.photo:
                        sent_file_msg = await bot.send_photo(chat_id=user_id, photo=media.file_id, caption=clean_caption)

                    if sent_file_msg:
                        delivered = True
                        logger.info(f"✅ Clean file successfully delivered to user {user_id} via Bot API!")
                        
                        # Schedule Auto-Delete after 2 minutes
                        user_display = f"@{query.from_user.username}" if query.from_user.username else query.from_user.first_name
                        asyncio.create_task(schedule_message_auto_delete(user_id, sent_file_msg.message_id, user_display))

                        # Also auto-backup to Storage Channel (if configured)
                        if config.STORAGE_CHANNEL_ID:
                            try:
                                await bot.copy_message(
                                    chat_id=config.STORAGE_CHANNEL_ID,
                                    from_chat_id=incoming_bot_msg.chat.id,
                                    message_id=incoming_bot_msg.message_id
                                )
                            except Exception as backup_err:
                                logger.warning(f"Storage channel backup note: {backup_err}")

            except Exception as bridge_err:
                logger.error(f"Bot bridge transfer failed: {bridge_err}", exc_info=True)
            finally:
                TRANSFER_QUEUE.pop(user_id, None)

            if status_msg:
                await status_msg.delete()

            if not delivered:
                await bot.send_message(chat_id=user_id, text="⚠️ An error occurred while sending the file. Please try again.")

        except Exception as e:
            logger.error(f"Error handling file delivery: {e}", exc_info=True)
            if status_msg:
                await status_msg.edit_text(f"⚠️ Error: {e}")


async def main():
    """Main startup orchestrator."""
    global userbot, relay_lock

    print("=" * 50)
    print("🚀 Starting Cinema & Series Engine")
    print("=" * 50)

    # Initialize Database
    await database.init_db()
    logger.info("Database initialized successfully.")

    relay_lock = asyncio.Lock()

    # 1. Connect Telethon Userbot
    logger.info("Connecting Userbot engine...")
    telethon_session = config.get_telethon_session_string()
    userbot = TelegramClient(
        StringSession(telethon_session),
        config.API_ID,
        config.API_HASH
    )
    await userbot.connect()
    if not await userbot.is_user_authorized():
        logger.error("Userbot is not authorized! Check your SESSION_STRING in .env")
        return
    user_me = await userbot.get_me()
    logger.info(f"✅ Userbot Connected: {user_me.first_name} (@{user_me.username or 'NoUsername'}) [ID: {user_me.id}]")

    # 2. Connect Aiogram Bot
    bot_info = await bot.get_me()
    logger.info(f"🤖 Cinema Bot Live: @{bot_info.username} [ID: {bot_info.id}]")
    
    # Initialize chat from Userbot to Bot
    try:
        await userbot.send_message(bot_info.username, "/start")
    except Exception as e:
        logger.warning(f"Could not send /start from userbot to bot: {e}")

    print("=" * 50)
    print(f"🌟 Bot is ACTIVE! Search movies at @{bot_info.username}")
    print("=" * 50)

    try:
        # 3. Start polling
        await dp.start_polling(bot)
    finally:
        await userbot.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
