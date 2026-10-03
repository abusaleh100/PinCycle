import os
import sqlite3
import asyncio
import re

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    CopyTextButton,
)
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 8762217575
OWNER_USERNAME = "wabillah"

DB_FILE = "pincycle.db"


# =========================
# DATABASE
# =========================

def db_connect():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            owner_id INTEGER NOT NULL,
            title TEXT
        )
    """)

    conn.commit()
    conn.close()


def has_access(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True

    conn = db_connect()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cur.fetchone()

    conn.close()

    return result is not None


def grant_access(user_id: int):
    conn = db_connect()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
        (user_id,)
    )

    conn.commit()
    conn.close()


def remove_access(user_id: int):
    conn = db_connect()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM users WHERE user_id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()


def save_group(chat_id: int, owner_id: int, title: str):
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO groups (chat_id, owner_id, title)
        VALUES (?, ?, ?)
    """, (chat_id, owner_id, title))

    conn.commit()
    conn.close()


def get_group_owner(chat_id: int):
    conn = db_connect()
    cur = conn.cursor()

    cur.execute(
        "SELECT owner_id FROM groups WHERE chat_id = ?",
        (chat_id,)
    )

    result = cur.fetchone()

    conn.close()

    if result:
        return result[0]

    return None


# =========================
# MAIN MENU
# =========================

def main_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Add Group",
                callback_data="add_group"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 Useful Commands",
                callback_data="useful_commands"
            )
        ],
        [
            InlineKeyboardButton(
                "👤 Contact Owner",
                url=f"https://t.me/{OWNER_USERNAME}"
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not has_access(user.id):

        keyboard = [
            [
                InlineKeyboardButton(
                    "👤 Contact Owner",
                    url=f"https://t.me/{OWNER_USERNAME}"
                )
            ]
        ]

        await update.message.reply_text(
            "❌ You don't have access to Pin Cycle.\n\n"
            "Please contact the owner to get access.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    await update.message.reply_text(
        "✅ Pin Cycle\n\n"
        "Select an option below:",
        reply_markup=main_menu()
    )


# =========================
# CALLBACK BUTTONS
# =========================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = query.from_user

    if not has_access(user.id):
        return

    # -------------------------
    # ADD GROUP
    # -------------------------

    if query.data == "add_group":

        select_button = KeyboardButton(
            "➕ Select Group",
            request_chat={
                "request_id": 1001,
                "chat_is_channel": False,
                "chat_is_forum": False,
                "bot_is_member": True,
                "bot_administrator_rights": {
                    "can_manage_chat": False,
                    "can_delete_messages": True,
                    "can_pin_messages": True,
                },
            }
        )

        back_button = KeyboardButton("⬅️ Back")

        keyboard = ReplyKeyboardMarkup(
            [
                [select_button],
                [back_button],
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )

        await query.edit_message_text(
            "Select the group where you want to use Pin Cycle."
        )

        await context.bot.send_message(
            chat_id=user.id,
            text="Choose an option:",
            reply_markup=keyboard
        )

        return

    # -------------------------
    # USEFUL COMMANDS
    # -------------------------

    if query.data == "useful_commands":

        keyboard = [
            [
                InlineKeyboardButton(
                    "4 Hours",
                    copy_text=CopyTextButton(
                        text="/pin 4h"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    "8 Hours",
                    copy_text=CopyTextButton(
                        text="/pin 8h"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    "12 Hours",
                    copy_text=CopyTextButton(
                        text="/pin 12h"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    "24 Hours",
                    copy_text=CopyTextButton(
                        text="/pin 24h"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Back",
                    callback_data="back_start"
                )
            ],
        ]

        await query.edit_message_text(
            "📋 Useful Commands\n\n"
            "Use these commands in your group.\n"
            "Tap any command to copy it and use it in your group.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # -------------------------
    # BACK TO START
    # -------------------------

    if query.data == "back_start":

        await query.edit_message_text(
            "✅ Pin Cycle\n\n"
            "Select an option below:",
            reply_markup=main_menu()
        )

        return


# =========================
# ADD GROUP BACK BUTTON
# =========================

async def add_group_back(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    if update.message.text != "⬅️ Back":
        return

    user = update.effective_user

    if not has_access(user.id):
        return

    # Delete the temporary Back message
    try:
        await update.message.delete()
    except Exception:
        pass

    # Remove reply keyboard first
    temp_message = await context.bot.send_message(
        chat_id=user.id,
        text="Returning...",
        reply_markup=ReplyKeyboardRemove()
    )

    # Turn that same message into the main menu
    await temp_message.edit_text(
        "✅ Pin Cycle\n\n"
        "Select an option below:",
        reply_markup=main_menu()
    )


# =========================
# GROUP SELECTED
# =========================

async def group_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    if not update.message.chat_shared:
        return

    user = update.effective_user

    if not has_access(user.id):
        return

    chat_id = update.message.chat_shared.chat_id

    try:
        chat = await context.bot.get_chat(chat_id)
    except Exception:
        await update.message.reply_text(
            "❌ I couldn't access this group.\n\n"
            "Please make sure Pin Cycle is added to the group."
        )
        return

    # Check user's status in group
    try:
        member = await context.bot.get_chat_member(
            chat_id,
            user.id
        )
    except Exception:
        await update.message.reply_text(
            "❌ I couldn't verify your permissions in this group."
        )
        return

    if member.status not in (
        ChatMemberStatus.OWNER,
        ChatMemberStatus.ADMINISTRATOR
    ):
        await update.message.reply_text(
            "❌ Only the group owner/admin can add Pin Cycle."
        )
        return

    # Check bot's permissions
    try:
        bot_member = await context.bot.get_chat_member(
            chat_id,
            context.bot.id
        )
    except Exception:
        await update.message.reply_text(
            "❌ I couldn't verify my permissions in this group."
        )
        return

    if bot_member.status not in (
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER
    ):
        await update.message.reply_text(
            "❌ Pin Cycle must be an administrator in the group."
        )
        return

    permissions = bot_member

    if not getattr(permissions, "can_delete_messages", False):
        await update.message.reply_text(
            "❌ Pin Cycle needs permission to delete messages."
        )
        return

    if not getattr(permissions, "can_pin_messages", False):
        await update.message.reply_text(
            "❌ Pin Cycle needs permission to pin messages."
        )
        return

    save_group(
        chat_id,
        user.id,
        chat.title or "Unnamed Group"
    )

    await update.message.reply_text(
        f"✅ Group added successfully.\n\n"
        f"Group: {chat.title or 'Unnamed Group'}\n\n"
        "Use one of these commands in the group:\n\n"
        "/pin 4h\n"
        "/pin 8h\n"
        "/pin 12h\n"
        "/pin 24h",
        reply_markup=ReplyKeyboardRemove()
    )


# =========================
# PIN COMMAND
# =========================

async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    user = update.effective_user
    chat = update.effective_chat

    # Only groups
    if chat.type not in ("group", "supergroup"):
        return

    # Check access
    if not has_access(user.id):
        return

    # Check registered group owner
    owner_id = get_group_owner(chat.id)

    if owner_id != user.id and user.id != OWNER_ID:
        return

    # Check argument
    if not context.args:
        try:
            await update.message.delete()
        except Exception:
            pass

        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                "❌ Please use:\n\n"
                "/pin 4h\n"
                "/pin 8h\n"
                "/pin 12h\n"
                "/pin 24h"
            )
        )

        return

    duration_text = context.args[0].lower().strip()

    duration_map = {
        "4h": 4 * 60 * 60,
        "8h": 8 * 60 * 60,
        "12h": 12 * 60 * 60,
        "24h": 24 * 60 * 60,
    }

    if duration_text not in duration_map:

        try:
            await update.message.delete()
        except Exception:
            pass

        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                "❌ Invalid duration.\n\n"
                "Use:\n"
                "/pin 4h\n"
                "/pin 8h\n"
                "/pin 12h\n"
                "/pin 24h"
            )
        )

        return

    duration = duration_map[duration_text]

    # Delete command immediately
    try:
        await update.message.delete()
    except Exception:
        pass

    # Store active pin cycle in bot_data
    if "pin_cycles" not in context.application.bot_data:
        context.application.bot_data["pin_cycles"] = {}

    context.application.bot_data["pin_cycles"][chat.id] = {
        "owner_id": user.id,
        "duration": duration,
        "duration_text": duration_text,
        "active": True,
    }

    await context.bot.send_message(
        chat_id=chat.id,
        text=(
            f"✅ Pin Cycle is ready. "
            f"The next post will be pinned for "
            f"{duration_text.replace('h', '')} hours, except admins."
        )
    )


# =========================
# MEMBER MESSAGE HANDLER
# =========================

async def member_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not chat:
        return

    if chat.type not in ("group", "supergroup"):
        return

    pin_cycles = context.application.bot_data.get(
        "pin_cycles",
        {}
    )

    cycle = pin_cycles.get(chat.id)

    if not cycle:
        return

    if not cycle.get("active"):
        return

    # Ignore admins / owner / creator
    try:
        member = await context.bot.get_chat_member(
            chat.id,
            user.id
        )

        if member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        ):
            return

    except Exception:
        return

    # Stop accepting another message immediately
    cycle["active"] = False

    try:
        await update.message.pin(
            disable_notification=True
        )
    except Exception as e:

        await context.bot.send_message(
            chat_id=chat.id,
            text="❌ I couldn't pin this message."
        )

        pin_cycles.pop(chat.id, None)
        return

    duration = cycle["duration"]

    # Wait selected duration
    await asyncio.sleep(duration)

    # Auto unpin
    try:
        await context.bot.unpin_chat_message(
            chat_id=chat.id,
            message_id=update.message.message_id
        )
    except Exception:
        pass

    # Remove cycle
    pin_cycles.pop(chat.id, None)


# =========================
# ACCESS COMMAND
# =========================

async def access_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if user.id != OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/access USER_ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid User ID."
        )
        return

    grant_access(target_id)

    await update.message.reply_text(
        f"✅ Access granted to {target_id}."
    )


# =========================
# REMOVE ACCESS
# =========================

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if user.id != OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/remove USER_ID"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid User ID."
        )
        return

    remove_access(target_id)

    await update.message.reply_text(
        f"✅ Access removed from {target_id}."
    )


# =========================
# ERROR HANDLER
# =========================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):

    print(
        "Exception while handling update:",
        context.error
    )


# =========================
# MAIN
# =========================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("pin", pin_command)
    )

    application.add_handler(
        CommandHandler("access", access_command)
    )

    application.add_handler(
        CommandHandler("remove", remove_command)
    )

    # Inline buttons
    application.add_handler(
        CallbackQueryHandler(button_handler)
    )

    # Back button from Add Group
    application.add_handler(
        MessageHandler(
            filters.Regex("^⬅️ Back$"),
            add_group_back
        )
    )

    # Group selection
    application.add_handler(
        MessageHandler(
            filters.StatusUpdate.CHAT_SHARED,
            group_selected
        )
    )

    # Group messages
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & ~filters.COMMAND,
            member_message
        )
    )

    # Errors
    application.add_error_handler(
        error_handler
    )

    print("Pin Cycle is running...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
