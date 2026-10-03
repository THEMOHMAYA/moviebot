import aiosqlite
import os

DB_PATH = "bot_database.db"

async def init_db():
    """Initializes the SQLite database table for file storage and users."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE,
                file_unique_id TEXT UNIQUE,
                file_name TEXT,
                file_size INTEGER,
                file_type TEXT,
                caption TEXT,
                channel_msg_id INTEGER
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_file_name ON files(file_name)")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def add_user(user_id: int, first_name: str = "", username: str = ""):
    """Adds or updates a user in the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, first_name, username)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                first_name = excluded.first_name,
                username = excluded.username
        """, (user_id, first_name, username))
        await db.commit()

async def get_all_users():
    """Fetches all registered user IDs."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_total_users_count():
    """Returns total user count."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        res = await cursor.fetchone()
        return res[0] if res else 0

async def save_file(file_id: str, file_unique_id: str, file_name: str, file_size: int, file_type: str, caption: str, msg_id: int):
    """Saves or updates a file record in the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO files (file_id, file_unique_id, file_name, file_size, file_type, caption, channel_msg_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (file_id, file_unique_id, file_name, file_size, file_type, caption, msg_id))
        await db.commit()

async def search_files(query: str, limit: int = 10, offset: int = 0):
    """Searches files by matching keywords in file_name or caption."""
    terms = query.strip().split()
    if not terms:
        return [], 0
    
    # Build SQL query matching all words (LIKE %word1% AND LIKE %word2%)
    conditions = []
    params = []
    for term in terms:
        conditions.append("(file_name LIKE ? OR caption LIKE ?)")
        search_pattern = f"%{term}%"
        params.extend([search_pattern, search_pattern])
        
    where_clause = " AND ".join(conditions)
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Get total count
        count_cursor = await db.execute(f"SELECT COUNT(*) as total FROM files WHERE {where_clause}", params)
        count_row = await count_cursor.fetchone()
        total_count = count_row["total"] if count_row else 0
        
        # Get paginated results
        sql = f"SELECT * FROM files WHERE {where_clause} ORDER BY id DESC LIMIT ? OFFSET ?"
        cursor = await db.execute(sql, params + [limit, offset])
        rows = await cursor.fetchall()
        
        return [dict(row) for row in rows], total_count

async def get_file_by_id(record_id: int):
    """Fetches single file data by primary key id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM files WHERE id = ?", (record_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_total_files_count():
    """Gets total indexed files count."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM files")
        res = await cursor.fetchone()
        return res[0] if res else 0
