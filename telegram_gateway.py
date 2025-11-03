# telegram_gateway.py

import os
import sys
import logging
import httpx
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Import database manager ---
import db_manager

# --- NOTIFICATION: Import required libraries ---
import yfinance as yf
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# --- Configuration ---
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADK_API_URL = "http://127.0.0.1:8000/run_sse"

if not TELEGRAM_BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN not found in .env file!")
    sys.exit(1)

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# --- HTTP Client ---
http_client = httpx.AsyncClient(timeout=60.0)

# --- NOTIFICATION: ThreadPoolExecutor for yfinance ---
executor = ThreadPoolExecutor(max_workers=3)

# --- NOTIFICATION: Helper function to check stock type ---
def is_vietnamese_stock(symbol: str) -> bool:
    """Check if symbol is Vietnamese (typically 3 letters without .VN suffix)"""
    clean_symbol = symbol.replace('.VN', '')
    return len(clean_symbol) <= 3 and clean_symbol.isalpha()

# --- NOTIFICATION: Helper function to get current price ---
async def fetch_current_price(symbol: str) -> float | None:
    """
    Fetches the latest closing price for a stock using yfinance.
    Returns the price as a float, or None if an error occurs.
    """
    symbol = symbol.upper()
    try:
        yf_symbol = f"{symbol}.VN" if is_vietnamese_stock(symbol) else symbol
       
        def get_yf_history():
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period="5d", interval="1d")
            return hist

        loop = asyncio.get_event_loop()
        hist = await loop.run_in_executor(executor, get_yf_history)
       
        if hist.empty:
            logger.warning(f"[Notification] No yfinance data for {symbol}")
            return None
       
        latest_price = hist['Close'].iloc[-1]
        logger.debug(f"[Notification] Fetched price for {symbol}: {latest_price}")
        return float(latest_price)
       
    except Exception as e:
        logger.error(f"[Notification] Failed to fetch price for {symbol}: {e}")
        return None

# --- NEW: Build context from conversation history ---
def build_context_prompt(chat_id: str) -> str:
    """
    Build a context prompt from recent conversation history for RAG.
    """
    history = db_manager.get_conversation_history(chat_id, limit=10, hours=24)
    
    if not history:
        return ""
    
    context_lines = ["Dựa vào lịch sử trò chuyện gần đây:"]
    for msg in history:
        role_vn = "Người dùng" if msg['role'] == 'user' else "FinAgent"
        context_lines.append(f"{role_vn}: {msg['message'][:200]}")  # Limit message length
    
    context_lines.append("\nHãy sử dụng thông tin này để trả lời câu hỏi mới nếu liên quan.")
    
    return "\n".join(context_lines)

# --- Telegram Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message."""
    user = update.effective_user
    chat_id_str = str(update.effective_chat.id)
    
    # Save the /start command
    db_manager.save_message(chat_id_str, 'user', '/start')
    
    welcome_msg = (
        f"Xin chào {user.mention_html()}! Tôi là FinAgent - trợ lý tài chính.\n\n"
        f"📊 Tôi có thể giúp bạn:\n"
        f"• Theo dõi cổ phiếu VN (VNM, VCB, FPT) và US (AAPL, GOOGL)\n"
        f"• Phân tích chỉ số tài chính\n"
        f"• Cập nhật tin tức thị trường\n"
        f"• Nhớ ngữ cảnh cuộc trò chuyện của bạn\n\n"
        f"🔔 Các lệnh hữu ích:\n"
        f"/notify - Đặt thông báo giá (VD: /notify VNM below 70000)\n"
        f"/alerts - Xem thông báo đang hoạt động\n"
        f"/clearalerts - Xóa tất cả thông báo\n"
        f"/history - Xem lịch sử trò chuyện\n"
        f"/clearhist - Xóa lịch sử trong phiên này"
    )
    
    await update.message.reply_html(welcome_msg)
    db_manager.save_message(chat_id_str, 'assistant', welcome_msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles text messages via ADK HTTP API with RAG context."""
    user_message = update.message.text
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    chat_id_str = str(update.effective_chat.id)
    
    # Save user message to history
    db_manager.save_message(chat_id_str, 'user', user_message)
    
    adk_user_id = "user"
   
    # Create session if needed
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
        # Build context from conversation history
        context_prompt = build_context_prompt(chat_id_str)
        
        # Combine context with new message if context exists
        enhanced_message = user_message
        if context_prompt:
            enhanced_message = f"{context_prompt}\n\n---\n\nCâu hỏi mới: {user_message}"
            logger.debug(f"Enhanced message with context: {enhanced_message[:200]}...")
        
        payload = {
            "appName": "multiagent",
            "userId": adk_user_id,
            "sessionId": session_id,
            "newMessage": {
                "role": "user",
                "parts": [{"text": enhanced_message}]
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
                                                logger.debug(f"Extracted text part: {last_content[:100]}...")
                                                break
                            elif "parts" in chunk:
                                parts = chunk.get("parts", [])
                                if parts and isinstance(parts, list):
                                    for part in parts:
                                        if isinstance(part, dict) and "text" in part:
                                            last_content = part["text"]
                                            logger.debug(f"Extracted text part: {last_content[:100]}...")
                                            break
                               
                    except json.JSONDecodeError as e:
                        logger.debug(f"JSON decode error: {e}")
                        continue
           
            logger.debug(f"Total lines received: {line_count}")

        if last_content:
            agent_reply = last_content
        else:
            if line_count > 0:
                agent_reply = "Bot đã thực hiện xong tác vụ."
            else:
                agent_reply = "Xin lỗi, không nhận được phản hồi."
       
        reply_preview = str(agent_reply)[:100] if agent_reply else "empty"
        logger.info(f"Agent replied: {reply_preview}...")

    except Exception as e:
        logger.error(f"Error during ADK call: {e}", exc_info=True)
        agent_reply = f"Xin lỗi, có lỗi xảy ra. Đảm bảo `adk web --port 8000` đang chạy."

    if isinstance(agent_reply, dict):
        agent_reply = str(agent_reply)
    
    # Save assistant's reply to history
    db_manager.save_message(chat_id_str, 'assistant', agent_reply, session_id)
   
    await update.message.reply_text(agent_reply)

# --- NEW: History management commands ---

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent conversation history."""
    chat_id_str = str(update.effective_chat.id)
    
    history = db_manager.get_conversation_history(chat_id_str, limit=5, hours=24)
    
    if not history:
        await update.message.reply_text("Bạn chưa có lịch sử trò chuyện nào trong 24 giờ qua.")
        return
    
    message = "📜 Lịch sử trò chuyện gần đây:\n\n"
    for msg in history:
        role_emoji = "👤" if msg['role'] == 'user' else "🤖"
        timestamp = msg['timestamp'][:16]  # YYYY-MM-DD HH:MM
        preview = msg['message'][:100] + "..." if len(msg['message']) > 100 else msg['message']
        message += f"{role_emoji} {timestamp}\n{preview}\n\n"
    
    await update.message.reply_text(message)

async def clear_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear conversation history for current session (last 24 hours)."""
    chat_id_str = str(update.effective_chat.id)
    
    # Get count before deleting
    history = db_manager.get_conversation_history(chat_id_str, limit=1000, hours=24)
    count = len(history)
    
    if count == 0:
        await update.message.reply_text("Không có lịch sử nào để xóa trong 24 giờ qua.")
        return
    
    # We need to add a method to clear recent history
    try:
        with db_manager.get_db_connection() as conn:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(hours=24)
            conn.execute("""
                DELETE FROM message_history 
                WHERE chat_id = ? AND timestamp > ?
            """, (chat_id_str, cutoff))
            conn.commit()
        
        await update.message.reply_text(f"✅ Đã xóa {count} tin nhắn trong lịch sử gần đây.")
    except Exception as e:
        logger.error(f"Failed to clear history: {e}")
        await update.message.reply_text("Lỗi khi xóa lịch sử.")

# --- Alert commands (unchanged) ---

async def notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    chat_id_str = str(update.effective_chat.id)
    user_alerts = db_manager.get_alerts(chat_id_str)
   
    if not user_alerts:
        await update.message.reply_text("Bạn không có thông báo nào đang hoạt động.")
        return

    message = "🔔 Thông báo đang hoạt động:\n"
    for row in user_alerts:
        message += f"- {row['symbol']} {row['condition']} {row['price']:,.0f}\n"
       
    await update.message.reply_text(message)

async def clear_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id_str = str(update.effective_chat.id)
    alerts_cleared_count = db_manager.clear_alerts(chat_id_str)
   
    if alerts_cleared_count == 0:
        await update.message.reply_text("Bạn không có thông báo nào để xoá.")
        return

    logger.info(f"Cleared {alerts_cleared_count} alerts for {chat_id_str}")
    await update.message.reply_text(f"Đã xoá {alerts_cleared_count} thông báo.")

# --- NOTIFICATION: Background Job Function ---
async def check_alerts(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job function to check all active alerts from the database."""
   
    alerts_to_check = db_manager.get_all_active_alerts()
   
    if not alerts_to_check:
        logger.debug("[Notification Job] No alerts in DB to check.")
        return
       
    logger.info(f"[Notification Job] Checking {len(alerts_to_check)} alerts...")
    alerts_triggered_ids = []

    for alert_row in alerts_to_check:
        alert_id = alert_row['id']
        chat_id = alert_row['chat_id']
        symbol = alert_row['symbol']
        condition = alert_row['condition']
        target_price = alert_row['price']
       
        current_price = await fetch_current_price(symbol)
       
        if current_price is None:
            logger.warning(f"[Notification Job] Skipping alert {alert_id} for {symbol} due to price fetch error.")
            continue
       
        triggered = False
        if condition == 'above' and current_price > target_price:
            triggered = True
        elif condition == 'below' and current_price < target_price:
            triggered = True
           
        if triggered:
            try:
                price_format = "{:,.0f}" if is_vietnamese_stock(symbol) else "{:,.2f}"
                currency = "VND" if is_vietnamese_stock(symbol) else "$"
               
                message = (
                    f"🚨 **THÔNG BÁO GIÁ** 🚨\n\n"
                    f"Mã **{symbol}** đã đạt điều kiện của bạn!\n"
                    f"Điều kiện: `{condition} {price_format.format(target_price)}`\n"
                    f"Giá hiện tại: **{price_format.format(current_price)} {currency}**"
                )
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
               
                alerts_triggered_ids.append(alert_id)
                logger.info(f"[Notification Job] Triggered alert {alert_id} for {chat_id}: {symbol}")

            except Exception as e:
                logger.error(f"[Notification Job] Failed to send notification for alert {alert_id} to {chat_id}: {e}")
                if "bot was blocked" in str(e).lower() or "chat not found" in str(e).lower():
                    alerts_triggered_ids.append(alert_id)
                    logger.warning(f"[Notification Job] Removing alert {alert_id} because user {chat_id} is unreachable.")

    if alerts_triggered_ids:
        logger.info(f"[Notification Job] Deleting {len(alerts_triggered_ids)} triggered alerts...")
        for alert_id in alerts_triggered_ids:
            db_manager.delete_alert_by_id(alert_id)
        logger.info("[Notification Job] Deletion complete.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error("Exception while handling an update:", exc_info=context.error)

# --- Main Function ---
def main() -> None:
    """Start the Telegram bot."""
    print("=" * 60)
    print("Starting Telegram Bot Gateway (With RAG & Notifications)")
    print(f"ADK API: {ADK_API_URL}")
    print("=" * 60)
   
    # Initialize the database on start-up
    db_manager.init_database()
    print("✅ Database initialized with message history support.")

    print("⚠️  Make sure 'adk web --port 8000' is running!")
    print("=" * 60)

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add all handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("notify", notify_command))
    application.add_handler(CommandHandler("alerts", list_alerts_command))
    application.add_handler(CommandHandler("clearalerts", clear_alerts_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("clearhist", clear_history_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
   
    application.add_error_handler(error_handler)

    # Start the background job
    job_queue = application.job_queue
    job_queue.run_repeating(check_alerts, interval=300, first=10)
    print("✅ Notification Watcher is active (checks every 5 mins)!")

    print("✅ Telegram Bot is running with RAG support!")
    print("💬 Message your bot to test!")
    application.run_polling()

if __name__ == '__main__':
    main()