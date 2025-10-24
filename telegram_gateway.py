# telegram_gateway.py
import os
import sys
import logging
import httpx
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Configuration ---
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADK_API_URL = "http://127.0.0.1:8000/run_sse"  # Change to 8000 since you said it's available

if not TELEGRAM_BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN not found in .env file!")
    sys.exit(1)

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Changed to DEBUG to see more details
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- HTTP Client ---
http_client = httpx.AsyncClient(timeout=60.0)

# --- Telegram Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message."""
    user = update.effective_user
    await update.message.reply_html(
        f"Xin chào {user.mention_html()}! Tôi là FinAgent - trợ lý tài chính. "
        f"Hỏi tôi về cổ phiếu VN (VNM, VCB, FPT) hoặc US (AAPL, GOOGL)!",
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles text messages via ADK HTTP API."""
    user_message = update.message.text
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    
    # Always use "user" as userId to match web UI behavior
    adk_user_id = "user"
    
    # Get or create session ID
    if 'session_id' not in context.user_data:
        # Create session via POST request
        try:
            create_session_url = f"http://127.0.0.1:8000/apps/multiagent/users/{adk_user_id}/sessions"
            session_response = await http_client.post(create_session_url, json={})
            session_response.raise_for_status()
            session_data = session_response.json()
            
            logger.info(f"Session creation response: {session_data}")
            
            # The response might have different formats
            if isinstance(session_data, dict):
                context.user_data['session_id'] = session_data.get('sessionId') or session_data.get('id') or session_data.get('session_id')
            else:
                # If it returns a string directly
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
        # Use exact format from web UI
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
        
        # Stream response from ADK
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
                        
                        # Handle nested content structure: content.parts[].text
                        if isinstance(chunk, dict):
                            # Check for nested content.parts format
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
                            # Also check direct parts format (fallback)
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

        # Clean and decode the response
        if last_content:
            # The text is already properly decoded by json.loads()
            agent_reply = last_content
        else:
            agent_reply = "Xin lỗi, không nhận được phản hồi."
        
        # Safe logging - convert to string first
        reply_preview = str(agent_reply)[:100] if agent_reply else "empty"
        logger.info(f"Agent replied: {reply_preview}...")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        agent_reply = f"Xin lỗi, có lỗi xảy ra. Đảm bảo `adk web --port 8000` đang chạy."

    # Make absolutely sure we're sending text only
    if isinstance(agent_reply, dict):
        # If somehow still a dict, extract text
        if "parts" in agent_reply:
            parts = agent_reply.get("parts", [])
            if parts and isinstance(parts, list):
                agent_reply = parts[0].get("text", str(agent_reply))
        else:
            agent_reply = str(agent_reply)
    
    await update.message.reply_text(agent_reply)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error("Exception while handling an update:", exc_info=context.error)

# --- Main Function ---
def main() -> None:
    """Start the Telegram bot."""
    print("=" * 60)
    print("Starting Telegram Bot Gateway")
    print(f"ADK API: {ADK_API_URL}")
    print("=" * 60)
    print("⚠️  Make sure 'adk web --port 8000' is running!")
    print("=" * 60)

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    print("✅ Telegram Bot is running!")
    print("💬 Message your bot to test!")
    application.run_polling()

if __name__ == '__main__':
    main()