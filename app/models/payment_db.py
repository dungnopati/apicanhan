import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

DB_PATH = Path(__file__).resolve().parent.parent.parent / "outputs" / "payments.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Khởi tạo bảng lưu trữ đơn nạp tiền và lịch sử giao dịch."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                player_id TEXT NOT NULL,
                game_id TEXT NOT NULL DEFAULT 'DEFAULT_GAME',
                amount INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                description TEXT NOT NULL,
                qr_url TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL,
                paid_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT,
                order_id TEXT,
                amount INTEGER NOT NULL,
                content TEXT NOT NULL,
                bank_account TEXT,
                gateway TEXT,
                raw_data TEXT,
                received_at TEXT NOT NULL
            )
        """)
        conn.commit()


# Tự động khởi tạo DB khi module được load
init_db()


class PaymentDB:
    @staticmethod
    def create_order(
        order_id: str,
        player_id: str,
        amount: int,
        description: str,
        qr_url: str,
        game_id: str = "DEFAULT_GAME",
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Tạo mới 1 đơn nạp tiền."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metadata_str = json.dumps(extra_data or {}, ensure_ascii=False)
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO orders (order_id, player_id, game_id, amount, status, description, qr_url, metadata, created_at)
                VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?, ?)
                """,
                (order_id, player_id, game_id, amount, description, qr_url, metadata_str, now)
            )
            conn.commit()
        return PaymentDB.get_order(order_id)

    @staticmethod
    def get_order(order_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin đơn nạp theo mã đơn."""
        with get_db() as conn:
            cursor = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["metadata"] = json.loads(res["metadata"]) if res.get("metadata") else {}
            except Exception:
                pass
            return res

    @staticmethod
    def find_pending_order_by_content(content: str, amount: int) -> Optional[Dict[str, Any]]:
        """Tìm đơn hàng PENDING khớp với nội dung chuyển khoản và số tiền."""
        normalized_content = content.upper().replace(" ", "").strip()
        with get_db() as conn:
            cursor = conn.execute("SELECT * FROM orders WHERE status = 'PENDING'")
            rows = cursor.fetchall()
            for r in rows:
                order = dict(r)
                # Kiểm tra xem mã đơn hoặc description có xuất hiện trong nội dung chuyển khoản không
                expected_desc = order["description"].upper().replace(" ", "").strip()
                order_id_clean = order["order_id"].upper().replace(" ", "").strip()
                if (expected_desc in normalized_content or order_id_clean in normalized_content):
                    # Khớp nội dung và số tiền (cho phép số tiền nạp >= số tiền đơn)
                    if int(amount) >= int(order["amount"]):
                        return order
        return None

    @staticmethod
    def mark_order_paid(order_id: str) -> bool:
        """Cập nhật trạng thái đơn hàng thành công (đã thanh toán)."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_db() as conn:
            cursor = conn.execute(
                "UPDATE orders SET status = 'SUCCESS', paid_at = ? WHERE order_id = ?",
                (now, order_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def record_transaction(
        amount: int,
        content: str,
        transaction_id: str = "",
        order_id: str = "",
        bank_account: str = "",
        gateway: str = "",
        raw_data: Any = None
    ) -> int:
        """Ghi nhận lại lịch sử giao dịch webhook từ ngân hàng/VietQR."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        raw_str = json.dumps(raw_data or {}, ensure_ascii=False) if not isinstance(raw_data, str) else raw_data
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO transactions (transaction_id, order_id, amount, content, bank_account, gateway, raw_data, received_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (transaction_id, order_id, amount, content, bank_account, gateway, raw_str, now)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def list_orders(limit: int = 50) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def list_transactions(limit: int = 50) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.execute("SELECT * FROM transactions ORDER BY received_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

