# db_manager.py
import sqlite3
import logging
from typing import List, Tuple, Optional, Dict
from datetime import datetime, timedelta

DB_FILE = "finance_bot.db"
logger = logging.getLogger(__name__)

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """
    Initializes the database and creates tables if they don't exist.
    This should be run once when the bot starts.
    """
    logger.info(f"Initializing database at {DB_FILE}...")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Table for user sessions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    chat_id TEXT PRIMARY KEY,
                    adk_session_id TEXT NOT NULL,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Table for price alerts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    price REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # NEW: Table for message history (RAG)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT,
                    FOREIGN KEY (chat_id) REFERENCES sessions(chat_id)
                )
            """)
            
            # Create index for faster retrieval
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_message_chat_timestamp
                ON message_history(chat_id, timestamp DESC)
            """)
            
            conn.commit()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)

# --- Session Management ---

def save_session(chat_id: str, session_id: str):
    """Saves or updates a user's ADK session ID."""
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO sessions (chat_id, adk_session_id)
                VALUES (?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    adk_session_id = excluded.adk_session_id,
                    last_seen = CURRENT_TIMESTAMP
            """, (chat_id, session_id))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to save session for {chat_id}: {e}")

def get_session(chat_id: str) -> Optional[str]:
    """Retrieves the ADK session ID for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT adk_session_id FROM sessions WHERE chat_id = ?", (chat_id,))
            row = cursor.fetchone()
            return row['adk_session_id'] if row else None
    except Exception as e:
        logger.error(f"Failed to get session for {chat_id}: {e}")
        return None

# --- Alert Management ---

def add_alert(chat_id: str, symbol: str, condition: str, price: float) -> bool:
    """Adds a new price alert for a user."""
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO alerts (chat_id, symbol, condition, price)
                VALUES (?, ?, ?, ?)
            """, (chat_id, symbol, condition, price))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to add alert for {chat_id}: {e}")
        return False

def get_alerts(chat_id: str) -> List[sqlite3.Row]:
    """Gets all active alerts for a specific user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT symbol, condition, price FROM alerts WHERE chat_id = ?",
                (chat_id,)
            )
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Failed to get alerts for {chat_id}: {e}")
        return []

def clear_alerts(chat_id: str) -> int:
    """Clears all alerts for a specific user and returns the count."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM alerts WHERE chat_id = ?", (chat_id,))
            rows_affected = cursor.rowcount
            conn.commit()
            return rows_affected
    except Exception as e:
        logger.error(f"Failed to clear alerts for {chat_id}: {e}")
        return 0

def get_all_active_alerts() -> List[sqlite3.Row]:
    """Gets all alerts from all users for the notification job."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts")
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Failed to get all alerts: {e}")
        return []

def delete_alert_by_id(alert_id: int):
    """Deletes a single alert by its unique ID after it's triggered."""
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to delete alert {alert_id}: {e}")

# --- NEW: Message History Management for RAG ---

def save_message(chat_id: str, role: str, message: str, session_id: Optional[str] = None) -> bool:
    """
    Saves a message to the history for RAG context.
    
    Args:
        chat_id: User's chat ID
        role: 'user' or 'assistant'
        message: The message content
        session_id: Optional ADK session ID for tracking
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO message_history (chat_id, role, message, session_id)
                VALUES (?, ?, ?, ?)
            """, (chat_id, role, message, session_id))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save message for {chat_id}: {e}")
        return False

def get_conversation_history(chat_id: str, limit: int = 10, hours: int = 24) -> List[Dict]:
    """
    Retrieves recent conversation history for a user.
    
    Args:
        chat_id: User's chat ID
        limit: Maximum number of messages to retrieve
        hours: Only get messages from the last N hours (default 24)
    
    Returns:
        List of message dictionaries with role, message, and timestamp
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            cursor.execute("""
                SELECT role, message, timestamp
                FROM message_history
                WHERE chat_id = ? AND timestamp > ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (chat_id, cutoff_time, limit))
            
            rows = cursor.fetchall()
            
            # Convert to list of dicts and reverse to get chronological order
            messages = [
                {
                    'role': row['role'],
                    'message': row['message'],
                    'timestamp': row['timestamp']
                }
                for row in reversed(rows)
            ]
            
            return messages
    except Exception as e:
        logger.error(f"Failed to get conversation history for {chat_id}: {e}")
        return []

def search_user_context(chat_id: str, keywords: List[str], limit: int = 5) -> List[Dict]:
    """
    Search through user's message history for relevant context.
    Useful for RAG when user asks follow-up questions.
    
    Args:
        chat_id: User's chat ID
        keywords: List of keywords to search for
        limit: Maximum number of relevant messages to return
    
    Returns:
        List of relevant messages
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Build SQL query with LIKE for each keyword
            query = """
                SELECT role, message, timestamp
                FROM message_history
                WHERE chat_id = ? AND (
            """
            
            conditions = []
            params = [chat_id]
            
            for keyword in keywords:
                conditions.append("message LIKE ?")
                params.append(f"%{keyword}%")
            
            query += " OR ".join(conditions)
            query += f") ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            messages = [
                {
                    'role': row['role'],
                    'message': row['message'],
                    'timestamp': row['timestamp']
                }
                for row in rows
            ]
            
            return messages
    except Exception as e:
        logger.error(f"Failed to search context for {chat_id}: {e}")
        return []

def clear_old_messages(days: int = 30) -> int:
    """
    Cleanup old messages to prevent database from growing too large.
    
    Args:
        days: Delete messages older than this many days
    
    Returns:
        Number of messages deleted
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cutoff_date = datetime.now() - timedelta(days=days)
            
            cursor.execute("""
                DELETE FROM message_history
                WHERE timestamp < ?
            """, (cutoff_date,))
            
            rows_deleted = cursor.rowcount
            conn.commit()
            
            logger.info(f"Deleted {rows_deleted} old messages (older than {days} days)")
            return rows_deleted
    except Exception as e:
        logger.error(f"Failed to clear old messages: {e}")
        return 0

def get_user_stats(chat_id: str) -> Dict:
    """
    Get statistics about a user's interaction history.
    
    Returns:
        Dictionary with stats like total messages, first interaction, etc.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Total messages
            cursor.execute("""
                SELECT COUNT(*) as total,
                       MIN(timestamp) as first_interaction,
                       MAX(timestamp) as last_interaction
                FROM message_history
                WHERE chat_id = ?
            """, (chat_id,))
            
            row = cursor.fetchone()
            
            return {
                'total_messages': row['total'],
                'first_interaction': row['first_interaction'],
                'last_interaction': row['last_interaction']
            }
    except Exception as e:
        logger.error(f"Failed to get user stats for {chat_id}: {e}")
        return {}