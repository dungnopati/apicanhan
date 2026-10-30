import os
from pathlib import Path
from dotenv import load_dotenv

# Tìm và nạp file .env từ thư mục gốc của dự án
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


class Settings:
    """Quản lý các biến môi trường và cấu hình hệ thống GeminiBridge & Payment."""

    def __init__(self):
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
        self.DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gemini-2.0-flash").strip()
        raw_port = os.getenv("PORT", "8200").strip()
        self.PORT: int = int(raw_port) if raw_port.isdigit() else 8200
        self.HOST: str = os.getenv("HOST", "127.0.0.1").strip()
        self.DEBUG: bool = os.getenv("DEBUG", "false").strip().lower() in ("true", "1")
        self.GEMINI_BACKEND_TYPE: str = os.getenv("GEMINI_BACKEND_TYPE", "official").strip().lower()
        self.GEMINI_SECURE_1PSID: str = os.getenv("GEMINI_SECURE_1PSID", "").strip()
        self.GEMINI_SECURE_1PSIDTS: str = os.getenv("GEMINI_SECURE_1PSIDTS", "").strip()
        self.BROWSER_CHANNEL: str = os.getenv("BROWSER_CHANNEL", "msedge").strip().lower()
        self.BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "false").strip().lower() in ("true", "1", "yes")
        self.BROWSER_PROFILE_DIR: str = os.getenv("BROWSER_PROFILE_DIR", "browser_profile").strip()

        # Cấu hình Cổng thanh toán nạp tiền tự động & VietQR Tingo
        self.VIETQR_MERCHANT_NAME: str = os.getenv("VIETQR_MERCHANT_NAME", "APICANHAN").strip()
        self.VIETQR_USERNAME: str = os.getenv("VIETQR_USERNAME", "admin").strip()
        self.VIETQR_PASSWORD: str = os.getenv("VIETQR_PASSWORD", "Apicanhan@2026").strip()
        self.VIETQR_BANK_ID: str = os.getenv("VIETQR_BANK_ID", "TCB").strip()
        self.VIETQR_ACCOUNT_NO: str = os.getenv("VIETQR_ACCOUNT_NO", "7179717878").strip()
        self.VIETQR_ACCOUNT_NAME: str = os.getenv("VIETQR_ACCOUNT_NAME", "HA TIEN DUNG").strip()
        self.PAYMENT_PREFIX: str = os.getenv("PAYMENT_PREFIX", "NAP").strip()

        # Cấu hình BOT đọc Email biến động số dư tự động 24/7 (Gmail IMAP)
        self.ENABLE_EMAIL_AUTO_BANK: bool = os.getenv("ENABLE_EMAIL_AUTO_BANK", "true").strip().lower() in ("true", "1", "yes")
        self.GMAIL_EMAIL: str = os.getenv("GMAIL_EMAIL", "").strip()
        self.GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "").strip()
        raw_interval = os.getenv("EMAIL_CHECK_INTERVAL", "10").strip()
        self.EMAIL_CHECK_INTERVAL: int = int(raw_interval) if raw_interval.isdigit() else 10

    @property
    def is_api_key_valid(self) -> bool:
        """Kiểm tra xem phương thức xác thực đã được cấu hình hợp lệ chưa."""
        if self.GEMINI_BACKEND_TYPE == "browser":
            return True
        if self.GEMINI_BACKEND_TYPE == "webapi":
            return bool(self.GEMINI_SECURE_1PSID)
        invalid_markers = ["YOUR_GEMINI_API_KEY_HERE", "YOUR_API_KEY", ""]
        return bool(self.GEMINI_API_KEY and self.GEMINI_API_KEY not in invalid_markers)

    @property
    def safe_api_key_preview(self) -> str:
        """Hiển thị trạng thái xác thực an toàn mà không làm lộ key hoặc cookie."""
        if self.GEMINI_BACKEND_TYPE == "browser":
            return f"Trình duyệt cá nhân ({self.BROWSER_CHANNEL.upper()})"

        if self.GEMINI_BACKEND_TYPE == "webapi":
            if self.GEMINI_SECURE_1PSID:
                return "Cookie WebAPI (Đã nạp)"
            return "Chưa cấu hình Cookie (Not set)"

        if not self.is_api_key_valid:
            return "Chưa cấu hình (Not set)"
        if len(self.GEMINI_API_KEY) <= 8:
            return "********"
        return f"{self.GEMINI_API_KEY[:4]}...{self.GEMINI_API_KEY[-4:]}"


settings = Settings()
