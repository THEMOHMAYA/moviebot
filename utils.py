from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import RESULTS_PER_PAGE

def format_size(size_bytes: int) -> str:
    """Formats bytes into human readable format like 1.88 GB, 500 MB."""
    if not size_bytes:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    return f"{size:.2f} {units[unit_index]}"

def build_search_keyboard(results: list, query: str, page: int, total_count: int) -> InlineKeyboardMarkup:
    """Creates inline buttons for search results with pagination."""
    inline_keyboard = []
    
    # Add a button for each file
    for item in results:
        size_str = format_size(item.get("file_size", 0))
        name = item.get("file_name") or "Unnamed File"
        # Truncate button text if too long for Telegram UI
        display_text = f"📁 {size_str} • {name}"
        if len(display_text) > 55:
            display_text = display_text[:52] + "..."
            
        callback_data = f"get_{item['id']}"
        inline_keyboard.append([InlineKeyboardButton(text=display_text, callback_data=callback_data)])
        
    # Pagination Row
    total_pages = (total_count + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
    nav_buttons = []
    
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"page_{page - 1}_{query}"))
        
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{max(1, total_pages)}", callback_data="noop"))
    
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"page_{page + 1}_{query}"))
        
    if nav_buttons:
        inline_keyboard.append(nav_buttons)
        
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
