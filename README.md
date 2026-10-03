# 🎬 Telegram File & Movie Search Bot

Ek fast aur reliable Telegram Search Bot jo SQLite Database aur Pyrogram par based hai.

---

## 🚀 Features

- 🔍 **Fast Keyword Search:** Koi bhi movie/file ka naam type karte hi matched results dikhata hai.
- 🔘 **Inline Buttons with File Size:** Har button par file ka name aur exact size (MB/GB) show hota hai.
- 📄 **Pagination:** Next / Prev page buttons jab bohot saare search results hon.
- ⚡ **Auto-Index Channel Storage:** Private Channel me file post karte hi bot automatically usko database me save kar leta hai.
- 🛡️ **Zero Ban Risk:** Direct Bot API aur Telegram Caching ka use karta hai.

---

## 🛠️ Setup Instructions

### 1. Requirements Install Karein
```bash
pip install -r requirements.txt
```

### 2. Configuration (`.env`) Fill Karein
- `API_ID` & `API_HASH`: [my.telegram.org](https://my.telegram.org) se lein.
- `BOT_TOKEN`: [@BotFather](https://t.me/BotFather) se naya bot create karke lein.
- `STORAGE_CHANNEL_ID`: Ek Private Channel banayein, bot ko usme Admin banayein, aur channel ki ID dalein (e.g. `-100...`).
- `ADMINS`: Apna numeric User ID dalein ([@userinfobot](https://t.me/userinfobot) se nikal sakte hain).

### 3. Bot Run Karein
```bash
python bot.py
```

---

## 📂 Project Structure

- [`bot.py`](file:///c:/Users/Ayush%20Raj/Downloads/Movie/bot.py) - Main bot logic aur handlers.
- [`database.py`](file:///c:/Users/Ayush%20Raj/Downloads/Movie/database.py) - Async SQLite database operations.
- [`config.py`](file:///c:/Users/Ayush%20Raj/Downloads/Movie/config.py) - Environment & settings loader.
- [`utils.py`](file:///c:/Users/Ayush%20Raj/Downloads/Movie/utils.py) - Size formatting aur keyboard builder.
