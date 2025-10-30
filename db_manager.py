# db_manager.py
import sqlite3
import logging
from typing import List, Tuple, Optional

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
            # We need all columns, especially id and chat_id
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