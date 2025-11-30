"""
Database models and operations for Portfolio Management
Author: Dũng Trần
Date: 2025-11-26
"""
import os
import sys
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import pytz

# # =================================
# # OVERRIDE PRINT TO USE STDERR ONLY
# # =================================
# def _debug_print(msg):
#     print(msg, file=sys.stderr, flush=True)

# print = _debug_print

# ===============================
# FIX WINDOW CONSOLE ENCODING
# ===============================
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except:
    pass

# ===============================
# DATABASE CONFIGURATION
# ===============================
if 'PORTFOLIO_DB_PATH' in os.environ:
    DB_PATH = os.environ['PORTFOLIO_DB_PATH']
else:
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(CURRENT_DIR, 'portfolio.db')

print(f"[DB] Using database: {DB_PATH}", file=sys.stderr)

# ===============================
# CONSTANTS
# ===============================

# Timezone Việt Nam
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# ===============================
# DATABASE INITIALIZATION
# ===============================

def init_database() -> None:
    """
    Khởi tạo database và tạo các tables nếu chưa tồn tại.
    
    Hàm này sẽ được gọi MỖI LẦN server khởi động để đảm bảo
    database luôn sẵn sàng.
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Bảng 1: transactions - Lưu MỌI giao dịch mua/bán cổ phiếu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('BUY', 'SELL')),
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            price REAL NOT NULL CHECK(price > 0),
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            market DEFAULT 'VN' CHECK(market IN ('VN', 'US')),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # TABLE 2: positions - Vị thế hiện tại (tính từ transactions)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            ticker TEXT PRIMARY KEY,
            quantity INTEGER NOT NULL CHECK(quantity >= 0),
            avg_buy_price REAL NOT NULL CHECK(avg_buy_price > 0),
            market TEXT DEFAULT 'VN' CHECK(market IN ('VN', 'US')),
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # TABLE 3: price_cache - Cache giá realtime (5 phút)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_cache (
            ticker TEXT PRIMARY KEY,
            price REAL NOT NULL,
            last_updated TIMESTAMP NOT NULL
        )
    """)

    # TABLE 4: realized_pnl - Lịch sử lời/lỗ đã chốt
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS realized_pnl (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            buy_price REAL NOT NULL,
            sell_price REAL NOT NULL,
            pnl REAL NOT NULL,
            pnl_percent REAL NOT NULL,
            sell_date TEXT NOT NULL,
            sell_time TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tạo indexes để tăng tốc query
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_ticker 
        ON transactions(ticker)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_date 
        ON transactions(date DESC)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_realized_pnl_ticker 
        ON realized_pnl(ticker)
    """)
    
    conn.commit()
    conn.close()
    
    print(f"✅ Database initialized at: {DB_PATH}")

# ===============================
# HELPER FUNCTIONS
# ===============================

def get_vn_datetime() -> Tuple[str, str]:
    """
    Lấy ngày giờ hiện tại theo timezone Việt Nam.
    
    Returns:
        Tuple[str, str]: (date, time) theo format 'YYYY-MM-DD', 'HH:MM:SS'
    
    Example:
        >>> get_vn_datetime()
        ('2025-11-26', '14:30:45')
    """
    now = datetime.now(VN_TZ)
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')
    return date_str, time_str

def format_currency(amount: float) -> str:
    """
    Format số tiền theo chuẩn VN: 85,000 VNĐ
    
    Args:
        amount: Số tiền cần format
    
    Returns:
        str: Số tiền đã format với dấu phẩy và đơn vị
    
    Example:
        >>> format_currency(85000)
        '85,000 VNĐ'
        >>> format_currency(1250000.50)
        '1,250,000.5 VNĐ'
    """
    if amount is None: 
        return "N/A"
    return f"{amount:,.0f} VNĐ"

def format_percent(percent: float) -> str:
    """
    Format phần trăm với dấu +/- và 2 chữ số thập phân.
    
    Args:
        percent: Số phần trăm cần format
    
    Returns:
        str: Phần trăm đã format
    
    Example:
        >>> format_percent(5.88)
        '+5.88%'
        >>> format_percent(-3.25)
        '-3.25%'
    """
    sign = '+' if percent >= 0 else ''
    return f"{sign}{percent:.2f}%"
    
# ===============================
# CORE DATABASE OPERATIONS
# ===============================

def _handle_buy(
    cursor: sqlite3.Cursor,
    ticker: str,
    quantity: int,
    price: float,
    market: str
) -> Dict:
    """
    Xử lý giao dịch MUA: Cập nhật hoặc tạo mới position.
    
    Logic:
    - Nếu chưa có position: Tạo mới
    - Nếu đã có: Tính lại avg_buy_price theo công thức Average Cost
    
    Args:
        cursor: SQLite cursor
        ticker: Mã cổ phiếu
        quantity: Số lượng mua
        price: Giá mua
        market: VN hoặc US
    
    Returns:
        Dict: {'success': True, 'message': str}
    """
    # Kiểm tra đã có position chưa
    cursor.execute(
        "SELECT quantity, avg_buy_price FROM positions WHERE ticker = ?",
        (ticker,)
    )
    existing = cursor.fetchone()
    
    if existing is None:
        # Chưa có position → Tạo mới
        cursor.execute("""
            INSERT INTO positions (ticker, quantity, avg_buy_price, market)
            VALUES (?, ?, ?, ?)
        """, (ticker, quantity, price, market))
        
        msg = f"✅ Đã mua {quantity} cp {ticker} @ {format_currency(price)}"
    else:
        # Đã có position → Tính lại average cost
        old_qty, old_avg_price = existing
        
        # Công thức Average Cost:
        # new_avg = (old_qty × old_avg + new_qty × new_price) / (old_qty + new_qty)
        new_qty = old_qty + quantity
        new_avg_price = (old_qty * old_avg_price + quantity * price) / new_qty
        
        cursor.execute("""
            UPDATE positions 
            SET quantity = ?, 
                avg_buy_price = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE ticker = ?
        """, (new_qty, new_avg_price, ticker))
        
        msg = (f"✅ Đã mua thêm {quantity} cp {ticker} @ {format_currency(price)}\n"
               f"   Tổng: {new_qty} cp | Giá vốn TB: {format_currency(new_avg_price)}")
    
    return {'success': True, 'message': msg}

def _handle_sell(
    cursor: sqlite3.Cursor,
    ticker: str,
    quantity: int,
    sell_price: float,
    date_str: str,
    time_str: str
) -> Dict:
    """
    Xử lý giao dịch BÁN: Giảm position và tính realized P&L.
    
    Logic:
    1. Kiểm tra có đủ số lượng để bán không
    2. Tính realized P&L = (sell_price - avg_buy_price) × quantity
    3. Lưu vào table `realized_pnl`
    4. Giảm quantity trong `positions` (hoặc xóa nếu bán hết)
    
    Args:
        cursor: SQLite cursor
        ticker: Mã cổ phiếu
        quantity: Số lượng bán
        sell_price: Giá bán
        date_str: Ngày bán
        time_str: Giờ bán
    
    Returns:
        Dict: {'success': True, 'message': str, 'realized_pnl': float}
    
    Raises:
        ValueError: Nếu bán nhiều hơn số lượng đang có
    """
    # Lấy position hiện tại
    cursor.execute(
        "SELECT quantity, avg_buy_price FROM positions WHERE ticker = ?",
        (ticker,)
    )
    position = cursor.fetchone()
    
    if position is None:
        raise ValueError(f"Không tìm thấy cổ phiếu {ticker} trong danh mục")
    
    current_qty, avg_buy_price = position
    
    if quantity > current_qty:
        raise ValueError(
            f"Không đủ số lượng để bán! "
            f"Đang có: {current_qty} cp, muốn bán: {quantity} cp"
        )
    
    # Tính realized P&L
    pnl = (sell_price - avg_buy_price) * quantity
    pnl_percent = ((sell_price - avg_buy_price) / avg_buy_price) * 100
    
    # Lưu vào realized_pnl table
    cursor.execute("""
        INSERT INTO realized_pnl 
        (ticker, quantity, buy_price, sell_price, pnl, pnl_percent, sell_date, sell_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticker, quantity, avg_buy_price, sell_price, pnl, pnl_percent, date_str, time_str))
    
    # Cập nhật positions
    new_qty = current_qty - quantity
    
    if new_qty == 0:
        # Bán hết → Xóa position
        cursor.execute("DELETE FROM positions WHERE ticker = ?", (ticker,))
        position_msg = f"Đã bán hết {ticker}"
    else:
        # Còn lại → Giảm quantity (giá vốn TB không đổi)
        cursor.execute("""
            UPDATE positions 
            SET quantity = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE ticker = ?
        """, (new_qty, ticker))
        position_msg = f"Còn lại: {new_qty} cp {ticker}"
    
    # Format message
    pnl_emoji = "🎉" if pnl > 0 else "😢" if pnl < 0 else "➡️"
    msg = (f"✅ Đã bán {quantity} cp {ticker} @ {format_currency(sell_price)}\n"
           f"   {pnl_emoji} Realized P&L: {format_currency(pnl)} ({format_percent(pnl_percent)})\n"
           f"   {position_msg}")
    
    return {
        'success': True,
        'message': msg,
        'realized_pnl': pnl,
        'realized_pnl_percent': pnl_percent
    }

def add_transaction(
    ticker: str,
    trans_type: str,
    quantity: int,
    price: float,
    market: str = 'VN',
    notes: str = ''
) -> Dict:
    """
    Thêm giao dịch MUA hoặc BÁN vào database.
    
    Hàm này sẽ:
    1. Thêm record vào table `transactions`
    2. Cập nhật table `positions` (tăng/giảm quantity)
    3. Nếu SELL: Tính realized P&L và lưu vào `realized_pnl`
    
    Args:
        ticker: Mã cổ phiếu (VD: 'VNM', 'VCB')
        trans_type: 'BUY' hoặc 'SELL'
        quantity: Số lượng cổ phiếu
        price: Giá giao dịch (VNĐ)
        market: 'VN' hoặc 'US'
        notes: Ghi chú tùy chọn
    
    Returns:
        Dict: Kết quả giao dịch
        {
            'success': bool,
            'message': str,
            'transaction_id': int,
            'realized_pnl': float (nếu SELL)
        }
    
    Raises:
        ValueError: Nếu SELL nhiều hơn số lượng đang có
    
    Example:
        >>> add_transaction('VNM', 'BUY', 100, 85000)
        {'success': True, 'message': 'Đã mua 100 cp VNM @ 85,000 VNĐ', ...}
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    ticker = ticker.upper().strip()
    trans_type = trans_type.upper()
    date_str, time_str = get_vn_datetime()
    
    try:
        # 1. Thêm vào transactions table
        cursor.execute("""
            INSERT INTO transactions 
            (ticker, type, quantity, price, date, time, market, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, trans_type, quantity, price, date_str, time_str, market, notes))
        
        transaction_id = cursor.lastrowid
        
        # 2. Cập nhật positions table
        if trans_type == 'BUY':
            result = _handle_buy(cursor, ticker, quantity, price, market)
        elif trans_type == 'SELL':
            result = _handle_sell(cursor, ticker, quantity, price, date_str, time_str)
        else:
            raise ValueError(f"Invalid transaction type: {trans_type}")
        
        conn.commit()
        
        result['transaction_id'] = transaction_id
        return result
        
    except Exception as e:
        conn.rollback()
        return {
            'success': False,
            'message': f"❌ Lỗi: {str(e)}"
        }
    finally:
        conn.close()

# ===============================
# QUERY FUNCTIONS
# ===============================

def get_all_positions() -> List[Dict]:
    """
    Lấy tất cả vị thế hiện tại trong danh mục.
    
    Returns:
        List[Dict]: Danh sách positions
        [
            {
                'ticker': 'VNM',
                'quantity': 100,
                'avg_buy_price': 85000.0,
                'market': 'VN'
            },
            ...
        ]
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ticker, quantity, avg_buy_price, market, last_updated
        FROM positions 
        ORDER BY ticker
    """)
    
    positions = []
    for row in cursor.fetchall():
        positions.append({
            'ticker': row[0],
            'quantity': row[1],
            'avg_buy_price': row[2],
            'market': row[3],
            'last_updated': row[4],
        })
    
    conn.close()
    return positions

def get_transaction_history(
    ticker: Optional[str] = None,
    limit: int = 20
) -> List[Dict]:
    """
    Lấy lịch sử giao dịch.
    
    Args:
        ticker: Nếu có, chỉ lấy giao dịch của mã này. None = tất cả
        limit: Số lượng giao dịch tối đa (mặc định 20)
    
    Returns:
        List[Dict]: Danh sách giao dịch, sắp xếp mới nhất trước
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if ticker:
        query = """
            SELECT id, ticker, type, quantity, price, date, time, market, notes
            FROM transactions 
            WHERE ticker = ?
            ORDER BY date DESC, time DESC
            LIMIT ?
        """
        cursor.execute(query, (ticker.upper(), limit))
    else:
        query = """
            SELECT id, ticker, type, quantity, price, date, time, market, notes
            FROM transactions 
            ORDER BY date DESC, time DESC
            LIMIT ?
        """
        cursor.execute(query, (limit,))
    
    transactions = []
    for row in cursor.fetchall():
        transactions.append({
            'id': row[0],
            'ticker': row[1],
            'type': row[2],
            'quantity': row[3],
            'price': row[4],
            'date': row[5],
            'time': row[6],
            'market': row[7],
            'notes': row[8] or ''
        })
    
    conn.close()
    return transactions

def get_realized_pnl_summary(ticker: Optional[str] = None) -> Dict:
    """
    Tổng hợp realized P&L (lời/lỗ đã chốt).
    
    Args:
        ticker: Nếu có, chỉ tính cho mã này. None = tất cả
    
    Returns:
        Dict: {
            'total_pnl': float,
            'total_trades': int,
            'winning_trades': int,
            'losing_trades': int,
            'win_rate': float (%)
        }
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if ticker:
        cursor.execute("""
            SELECT 
                SUM(pnl) as total_pnl,
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades
            FROM realized_pnl
            WHERE ticker = ?
        """, (ticker.upper(),))
    else:
        cursor.execute("""
            SELECT 
                SUM(pnl) as total_pnl,
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades
            FROM realized_pnl
        """)
    
    row = cursor.fetchone()
    conn.close()
    
    if row[0] is None:  # Chưa có giao dịch nào
        return {
            'total_pnl': 0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0
        }
    
    total_pnl = row[0]
    total_trades = row[1]
    winning_trades = row[2]
    losing_trades = row[3]
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        'total_pnl': total_pnl,
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate
    }

# ===============================
# DATABASE MAINTENANCE
# ===============================

def clear_all_data() -> Dict:
    """
    XÓA TẤT CẢ dữ liệu trong database (cẩn thận!).
    
    Dùng để reset portfolio về trạng thái ban đầu.
    
    Returns:
        Dict: {'success': True, 'message': str}
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM transactions")
        cursor.execute("DELETE FROM positions")
        cursor.execute("DELETE FROM price_cache")
        cursor.execute("DELETE FROM realized_pnl")
        
        conn.commit()
        
        return {
            'success': True,
            'message': "✅ Đã xóa toàn bộ dữ liệu portfolio"
        }
    except Exception as e:
        conn.rollback()
        return {
            'success': False,
            'message': f"❌ Lỗi khi xóa dữ liệu: {str(e)}"
        }
    finally:
        conn.close()

# ===============================
# PRICE FETCHING (TCBS API)
# ===============================



def get_current_price(ticker: str, market: str = 'VN') -> Optional[float]:
    """
    Lấy giá hiện tại của cổ phiếu (có cache 5 phút).
    
    Args:
        ticker: Mã cổ phiếu (VD: 'VNM', 'VCB')
        market: 'VN' hoặc 'US'
    
    Returns:
        float: Giá hiện tại (VNĐ hoặc USD)
        None: Nếu không lấy được giá
    
    Example:
        >>> get_current_price('VNM')
        87500.0
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    ticker = ticker.upper().strip()
    
    try:
        # 1. Kiểm tra cache (5 phút)
        cursor.execute("""
            SELECT price, last_updated 
            FROM price_cache 
            WHERE ticker = ?
        """, (ticker,))
        
        cached = cursor.fetchone()
        
        if cached:
            cached_price, last_updated_str = cached
            # Parse datetime và chuyển thành naive (không timezone)
            last_updated = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
            if last_updated.tzinfo is not None:
                last_updated = last_updated.replace(tzinfo=None)

            # So sánh với thời gian hiện tại (naive)
            now = datetime.now(VN_TZ).replace(tzinfo=None)
            
            # Nếu cache còn mới (< 5 phút)
            if (now - last_updated) < timedelta(minutes=5):
                return cached_price
        
        # 2. Cache hết hạn → Fetch từ API
        if market == 'VN':
            price = _fetch_price_vnstock(ticker)
        else:  # US market
            price = _fetch_price_yfinance(ticker)
        
        if price is None:
            return None
        
        # 3. Cập nhật cache
        cursor.execute("""
            INSERT OR REPLACE INTO price_cache 
            (ticker, price, last_updated)
            VALUES (?, ?, ?)
        """, (ticker, price, datetime.now().isoformat()))
        
        conn.commit()
        return price
        
    except Exception as e:
        print(f"⚠️ Error fetching price for {ticker}: {e}")
        return None
    finally:
        conn.close()


def _fetch_price_vnstock(ticker: str) -> Optional[float]:
    """
    Lấy giá từ vnstock library (thị trường VN).
    
    Args:
        ticker: Mã cổ phiếu VN (VD: 'VNM', 'VCB')
    
    Returns:
        float: Giá đóng cửa gần nhất
        None: Nếu API lỗi hoặc không tìm thấy mã
    """
    try:
        from vnstock import Vnstock
        
        # Khởi tạo Vnstock
        stock = Vnstock().stock(symbol=ticker, source='VCI')
        
        # Lấy dữ liệu 7 ngày gần nhất (đảm bảo có data ngay cả khi chạy T2)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Lấy lịch sử giá 
        df = stock.quote.history(
            start=start_date,
            end=end_date,
            interval='1D'
        )
        
        # Kiểm tra có dữ liệu không
        if df is None or df.empty:
            print(f"⚠️ Không có dữ liệu cho mã {ticker}")
            return None
        
        # Lấy giá đóng cửa (close) mới nhất
        latest_price = float(df['close'].iloc[-1])

        # vnstock trả về đơn vị nghìn đồng → nhân 1000
        # VD: API trả 87.5 → Thực tế 87,500 VNĐ
        latest_price = latest_price * 1000
        
        return latest_price
        
    except ImportError:
        print("⚠️ Chưa cài vnstock. Chạy: pip install -U vnstock")
        return None
    except KeyError as e:
        print(f"⚠️ Không tìm thấy cột {e} trong dữ liệu {ticker}")
        return None
    except IndexError:
        print(f"⚠️ DataFrame rỗng cho mã {ticker}")
        return None
    except Exception as e:
        print(f"⚠️ Lỗi vnstock cho {ticker}: {e}")
        return None


def _fetch_price_yfinance(ticker: str) -> Optional[float]:
    """
    Lấy giá từ Yahoo Finance (thị trường US).
    
    Sử dụng thư viện yfinance (đã có sẵn từ technical_server.py).
    
    Args:
        ticker: Mã cổ phiếu US (VD: 'AAPL', 'TSLA')
    
    Returns:
        float: Giá hiện tại (USD)
        None: Nếu không lấy được
    """
    try:
        import yfinance as yf
        
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Ưu tiên currentPrice, fallback sang regularMarketPrice
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        
        if price is None:
            print(f"⚠️ Không lấy được giá cho {ticker} từ Yahoo Finance")
            return None
        
        return float(price)
        
    except Exception as e:
        print(f"⚠️ Lỗi Yahoo Finance cho {ticker}: {e}")
        return None


def validate_ticker(ticker: str, market: str = 'VN') -> bool:
    """
    Kiểm tra mã cổ phiếu có tồn tại không (bằng cách thử lấy giá).
    
    Args:
        ticker: Mã cổ phiếu
        market: 'VN' hoặc 'US'
    
    Returns:
        bool: True nếu tồn tại, False nếu không
    
    Example:
        >>> validate_ticker('VNM')
        True
        >>> validate_ticker('KHONGCOMA')
        False
    """
    price = get_current_price(ticker, market)
    return price is not None


# ===============================
# AUTO-INITIALIZATION
# ===============================

# Tự động khởi tạo database khi import module
try:
    init_database()
except Exception as e:
    print(f"⚠️ Warning: Could not initialize database: {e}")