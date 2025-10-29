# telegram_gateway.py
import os
import sys
import logging
import httpx
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- NEW: Import your database manager ---
import db_manager 

# --- Configuration ---
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADK_API_URL = "http://127.0.0.1:8000/run_sse"  # Kept your working URL

if not TELEGRAM_BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN not found in .env file!")
    sys.exit(1)

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Kept your DEBUG level
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- HTTP Client ---
http_client = httpx.AsyncClient(timeout=60.0)

# --- Telegram Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message."""
    user = update.effective_user
    # --- UPDATED: Added info about /notify ---
    await update.message.reply_html(
        f"Xin chào {user.mention_html()}! Tôi là FinAgent - trợ lý tài chính. "
        f"Hỏi tôi về cổ phiếu VN (VNM, VCB, FPT) hoặc US (AAPL, GOOGL)!\n\n"
        f"Sử dụng /notify để đặt thông báo giá (ví dụ: <code>/notify VNM below 70000</code>).",
    )

# --- KEPT YOUR WORKING handle_message UNCHANGED ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles text messages via ADK HTTP API."""
    user_message = update.message.text
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    
    adk_user_id = "user"
    
    if 'session_id' not in context.user_data:
        try:
            create_session_url = f"http://127.0.0.1:8000/apps/multiagent/users/{adk_user_id}/sessions"
            session_response = await http_client.post(create_session_url, json={})
            session_response.raise_for_status()
            session_data = session_response.json()
            
            logger.info(f"Session creation response: {session_data}")
            
            if isinstance(session_data, dict):
                context.user_data['session_id'] = session_data.get('sessionId') or session_data.get('id') or session_data.get('session_id')
            else:
                context.user_data['session_id'] = str(session_data)
            
            if not context.user_data.get('session_id'):
                raise Exception(f"No session ID in response: {session_data}")
                
            logger.info(f"Created session: {context.user_data['session_id']}")
        except Exception as e:
            logger.error(f"Failed to create session: {e}", exc_info=True)
            await update.message.reply_text("Xin lỗi, không thể tạo phiên làm việc. Vui lòng thử lại.")
            return
    
    session_id = context.user_data['session_id']
    
    logger.info(f"Telegram user {user_id_str} (ADK session {session_id[:8]}...) sent: {user_message}")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    try:
        payload = {
            "appName": "multiagent",
            "userId": adk_user_id,
            "sessionId": session_id,
            "newMessage": {
                "role": "user",
                "parts": [{"text": user_message}]
            },
            "stateDelta": None,
            "streaming": False
        }

        agent_reply = ""
        
        async with http_client.stream('POST', ADK_API_URL, json=payload) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise Exception(f"API error {response.status_code}: {error_text.decode()[:200]}")
            
            last_content = ""
            line_count = 0
            
            async for line in response.aiter_lines():
                line_count += 1
                
                if not line or not line.strip():
                    continue
                
                logger.debug(f"Received line {line_count}: {line[:100]}")
                        
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    
                    if data_str == "[DONE]":
                        break
                        
                    try:
                        chunk = json.loads(data_str)
                        logger.debug(f"Parsed chunk: {str(chunk)[:200]}")
                        
                        if isinstance(chunk, dict):
                            if "content" in chunk:
                                content = chunk["content"]
                                if isinstance(content, dict) and "parts" in content:
                                    parts = content["parts"]
                                    if parts and isinstance(parts, list):
                                        for part in parts:
                                            if isinstance(part, dict) and "text" in part:
                                                last_content = part["text"]
                                                logger.info(f"Extracted text: {last_content[:100]}...")
                                                break
                            elif "parts" in chunk:
                                parts = chunk.get("parts", [])
                                if parts and isinstance(parts, list):
                                    for part in parts:
                                        if isinstance(part, dict) and "text" in part:
                                            last_content = part["text"]
                                            logger.info(f"Extracted text: {last_content[:100]}...")
                                            break
                                
                    except json.JSONDecodeError as e:
                        logger.debug(f"JSON decode error: {e}")
                        continue
            
            logger.info(f"Total lines received: {line_count}")

        if last_content:
            agent_reply = last_content
        else:
            agent_reply = "Xin lỗi, không nhận được phản hồi."
        
        reply_preview = str(agent_reply)[:100] if agent_reply else "empty"
        logger.info(f"Agent replied: {reply_preview}...")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        agent_reply = f"Xin lỗi, có lỗi xảy ra. Đảm bảo `adk web --port 8000` đang chạy."

    if isinstance(agent_reply, dict):
        if "parts" in agent_reply:
            parts = agent_reply.get("parts", [])
            if parts and isinstance(parts, list):
                agent_reply = parts[0].get("text", str(agent_reply))
        else:
            agent_reply = str(agent_reply)
    
    await update.message.reply_text(agent_reply)

# --- NEW: Alert commands using the database ---

async def notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets a price alert. Usage: /notify <SYMBOL> <above|below> <PRICE>"""
    chat_id_str = str(update.effective_chat.id)
    try:
        if len(context.args) != 3:
            await update.message.reply_text("Sử dụng: /notify <MÃ> <above|below> <GIÁ>\n"
                                            "Ví dụ: /notify VNM below 70000\n"
                                            "Ví dụ: /notify AAPL above 200")
            return
        
        symbol = context.args[0].upper()
        condition = context.args[1].lower()
        price_str = context.args[2]

        if condition not in ['above', 'below']:
            await update.message.reply_text("Điều kiện phải là 'above' (trên) hoặc 'below' (dưới).")
            return
        
        try:
            price = float(price_str)
        except ValueError:
            await update.message.reply_text("Giá phải là một con số.")
            return

        # --- Use db_manager ---
        success = db_manager.add_alert(chat_id_str, symbol, condition, price)
        
        if success:
            logger.info(f"Alert set by {chat_id_str}: {symbol} {condition} {price}")
            await update.message.reply_text(
                f"✅ Đã đặt thông báo: {symbol} {condition} {price:,.0f} VND (hoặc $)"
            )
        else:
            await update.message.reply_text("Lỗi: Không thể lưu thông báo vào cơ sở dữ liệu.")

    except Exception as e:
        logger.error(f"Failed to set alert: {e}")
        await update.message.reply_text(f"Lỗi khi đặt thông báo: {e}")


async def list_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists all active alerts for the user."""
    chat_id_str = str(update.effective_chat.id)
    
    # --- Use db_manager ---
    user_alerts = db_manager.get_alerts(chat_id_str)
    
    if not user_alerts:
        await update.message.reply_text("Bạn không có thông báo nào đang hoạt động.")
        return

    message = "🔔 Thông báo đang hoạt động:\n"
    for row in user_alerts:
        message += f"- {row['symbol']} {row['condition']} {row['price']:,.0f}\n"
        
    await update.message.reply_text(message)


async def clear_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clears all active alerts for the user."""
    chat_id_str = str(update.effective_chat.id)

    # --- Use db_manager ---
    alerts_cleared_count = db_manager.clear_alerts(chat_id_str)
    
    if alerts_cleared_count == 0:
        await update.message.reply_text("Bạn không có thông báo nào để xoá.")
        return

    logger.info(f"Cleared {alerts_cleared_count} alerts for {chat_id_str}")
    await update.message.reply_text(f"Đã xoá {alerts_cleared_count} thông báo.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error("Exception while handling an update:", exc_info=context.error)

# --- Main Function ---
def main() -> None:
    """Start the Telegram bot."""
    print("=" * 60)
    print("Starting Telegram Bot Gateway (Original + DB Alerts)") # Updated title
    print(f"ADK API: {ADK_API_URL}")
    print("=" * 60)
    
    # --- NEW: Initialize the database on start-up ---
    db_manager.init_database()
    print("✅ Database initialized.")

    print("⚠️  Make sure 'adk web --port 8000' is running!")
    print("=" * 60)

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # --- UPDATED: Add all handlers, including new ones ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("notify", notify_command))
    application.add_handler(CommandHandler("alerts", list_alerts_command))
    application.add_handler(CommandHandler("clearalerts", clear_alerts_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    print("✅ Telegram Bot is running!")
    print("💬 Message your bot to test!")
    application.run_polling()

if __name__ == '__main__':
    main()