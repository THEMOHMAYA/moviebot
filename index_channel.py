import asyncio

# Python 3.12+ compatibility for Pyrogram
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import logging
from pyrogram import Client

from pyrogram.errors import FloodWait

import config
import database
from utils import format_size

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def index_existing_files():
    """Indexes all existing videos and documents in the storage channel using String Session."""
    if not config.SESSION_STRING:
        logger.error("SESSION_STRING nahi mila! Kripya .env me session string dalein.")
        return

    await database.init_db()
    logger.info("Connecting User Account using String Session...")

    user_client = Client(
        name="indexer_userbot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        session_string=config.SESSION_STRING
    )

    async with user_client:
        logger.info(f"Connected! Scanning channel {config.STORAGE_CHANNEL_ID} for files...")
        indexed_count = 0

        async for message in user_client.get_chat_history(config.STORAGE_CHANNEL_ID):
            media = message.document or message.video or message.audio
            if media:
                file_id = media.file_id
                file_unique_id = media.file_unique_id
                file_name = getattr(media, "file_name", None) or f"File_{message.id}"
                file_size = media.file_size or 0
                file_type = "video" if message.video else ("audio" if message.audio else "document")
                caption = message.caption or ""

                await database.save_file(
                    file_id=file_id,
                    file_unique_id=file_unique_id,
                    file_name=file_name,
                    file_size=file_size,
                    file_type=file_type,
                    caption=caption,
                    msg_id=message.id
                )
                indexed_count += 1
                if indexed_count % 20 == 0:
                    logger.info(f"Indexed {indexed_count} files so far...")

        logger.info(f"✅ Scanning complete! Total files indexed: {indexed_count}")

if __name__ == "__main__":
    asyncio.run(index_existing_files())
