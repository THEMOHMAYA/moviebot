import os
import base64
import struct
import ipaddress
from dotenv import load_dotenv

load_dotenv()

# Telegram API credentials from https://my.telegram.org
API_ID = int(os.getenv("API_ID", "30668264"))
API_HASH = os.getenv("API_HASH", "fa3c65be2cf6d690807afc1026380fcc")

# Pyrogram or Telethon session string
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()

# Telegram Bot Token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "8584481491:AAEN-N7dGkJgV1CqJUepjSfRyQtczwfXMVQ").strip()

# ID of your Private Storage Channel (must start with -100)
STORAGE_CHANNEL_ID = int(os.getenv("STORAGE_CHANNEL_ID", "-1004380979857"))

# Admin Telegram User IDs (List of integers)
ADMINS = [int(x.strip()) for x in os.getenv("ADMINS", "1999645649").split(",") if x.strip()]

# Target Bot to forward search queries to
TARGET_BOT = os.getenv("TARGET_BOT", "iPapkornN2bot").replace("@", "").strip()

# Force Subscribe Channel (ID e.g. -100... or @channel_username, leave empty if disabled)
FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL", "").strip()
FORCE_SUB_LINK = os.getenv("FORCE_SUB_LINK", "").strip()

# Auto-Delete Timers (in seconds)
AUTO_DELETE_SECONDS = int(os.getenv("AUTO_DELETE_SECONDS", "120"))  # 2 minutes
NOTICE_DELETE_SECONDS = int(os.getenv("NOTICE_DELETE_SECONDS", "30"))  # 30 seconds


def get_telethon_session_string() -> str:
    """Converts Pyrogram session string or returns Telethon session string."""
    s_str = SESSION_STRING
    if not s_str:
        return ""
    
    # If it is already a Telethon string session (starts with '1' and decodes as telethon)
    if s_str.startswith("1") and len(s_str) > 300:
        return s_str

    try:
        data = base64.urlsafe_b64decode(s_str + "=" * (-len(s_str) % 4))
        if len(data) == 271:
            dc_id, api_id, test_mode, auth_key, user_id, is_bot = struct.unpack('>Bi?256sQ?', data)
            dc_ips = {
                1: "149.154.175.53",
                2: "149.154.167.51",
                3: "149.154.175.100",
                4: "149.154.167.91",
                5: "91.108.56.130"
            }
            ip_str = dc_ips.get(dc_id, "91.108.56.130")
            ip_bytes = ipaddress.IPv4Address(ip_str).packed
            packed = struct.pack('>B4sH256s', dc_id, ip_bytes, 443, auth_key)
            return '1' + base64.urlsafe_b64encode(packed).decode('ascii')
    except Exception:
        pass
    
    return s_str
