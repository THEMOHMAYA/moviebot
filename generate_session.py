import asyncio

# Compatibility for Python 3.12+
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client
import config

async def main():
    print("=" * 50)
    print("🔑 Telegram String Session Generator")
    print("=" * 50)
    print(f"Using API_ID: {config.API_ID}")
    print(f"Using API_HASH: {config.API_HASH}\n")
    
    app = Client(
        "session_creator",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        in_memory=True
    )
    
    async with app:
        session_str = await app.export_session_string()
        print("\n" + "=" * 50)
        print("✅ Aapka Naya String Session:")
        print("=" * 50)
        print(session_str)
        print("=" * 50)
        print("\n👉 Is String Session ko copy karke .env file me SESSION_STRING= me dalein!\n")

if __name__ == "__main__":
    asyncio.run(main())
