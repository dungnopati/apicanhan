from typing import Optional, Dict
from app.clients.base import BaseGeminiClient
from app.clients.official_client import OfficialGeminiClient
from app.clients.webapi_adapter import WebAPIAdapter
from app.clients.browser_adapter import BrowserAdapter
from app.config import settings

_cached_clients: Dict[str, BaseGeminiClient] = {}


def get_gemini_client(backend_type: Optional[str] = None, force_refresh: bool = False) -> BaseGeminiClient:
    """Tạo hoặc lấy đối tượng GeminiClient dựa trên cấu hình hệ thống.

    Hỗ trợ 3 chế độ:
    - browser: Điều khiển trực tiếp trình duyệt Microsoft Edge / Chrome đã đăng nhập tài khoản cá nhân (Tạo ảnh Imagen 3 xịn nhất).
    - official: Sử dụng Google Gemini API chính thức qua API Key.
    - webapi: Sử dụng kết nối ngầm qua Cookie __Secure-1PSID.
    """
    global _cached_clients

    target_type = (backend_type or settings.GEMINI_BACKEND_TYPE).lower().strip()

    if not force_refresh and target_type in _cached_clients:
        return _cached_clients[target_type]

    if target_type == "browser":
        client = BrowserAdapter()
    elif target_type == "webapi":
        client = WebAPIAdapter(
            secure_1psid=settings.GEMINI_SECURE_1PSID,
            secure_1psidts=settings.GEMINI_SECURE_1PSIDTS,
        )
    else:
        # Mặc định sử dụng Official API
        client = OfficialGeminiClient(api_key=settings.GEMINI_API_KEY)

    _cached_clients[target_type] = client
    return client

