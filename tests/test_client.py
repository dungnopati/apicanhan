import asyncio
import pytest
from app.clients.base import BaseGeminiClient
from app.clients.official_client import OfficialGeminiClient
from app.clients.webapi_adapter import WebAPIAdapter
from app.clients.factory import get_gemini_client
from app.models.chat import ChatMessage
from app.config import settings


def test_client_inheritance():
    """Kiểm tra cả OfficialGeminiClient và WebAPIAdapter đều kế thừa từ BaseGeminiClient."""
    official = OfficialGeminiClient(api_key="test-key")
    webapi = WebAPIAdapter()

    assert isinstance(official, BaseGeminiClient)
    assert isinstance(webapi, BaseGeminiClient)
    assert official.backend_name == "official"
    assert webapi.backend_name == "webapi"


def test_official_model_resolution():
    """Kiểm tra việc chuẩn hóa tên mô hình."""
    client = OfficialGeminiClient(api_key="test-key")

    assert client._resolve_model("gemini-2.0-flash") == "gemini-2.0-flash"
    assert client._resolve_model("models/gemini-1.5-pro") == "gemini-1.5-pro"
    # OpenAI model names fallback to default Gemini model
    assert client._resolve_model("gpt-4o") == settings.DEFAULT_MODEL
    assert client._resolve_model("") == settings.DEFAULT_MODEL
    assert client._resolve_model(None) == settings.DEFAULT_MODEL


def test_convert_messages():
    """Kiểm tra chuyển đổi danh sách tin nhắn sang định dạng contents của Gemini."""
    client = OfficialGeminiClient(api_key="test-key")

    messages = [
        ChatMessage(role="system", content="Bạn là gia sư tiếng Anh."),
        ChatMessage(role="user", content="Xin chào"),
        ChatMessage(role="assistant", content="Chào bạn, mình có thể giúp gì?"),
        ChatMessage(role="user", content="Chỉ mình cách học từ vựng"),
    ]

    contents, system_inst = client._convert_messages(messages)

    assert system_inst == "Bạn là gia sư tiếng Anh."
    assert len(contents) == 3
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"][0]["text"] == "Xin chào"
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"][0]["text"] == "Chào bạn, mình có thể giúp gì?"
    assert contents[2]["role"] == "user"


def test_webapi_adapter_behavior():
    """Kiểm tra hoạt động của WebAPIAdapter."""
    # Khi chưa có cookie, phải báo lỗi rõ ràng
    adapter_empty = WebAPIAdapter(secure_1psid="", secure_1psidts="")
    with pytest.raises(ValueError, match="GEMINI_SECURE_1PSID"):
        asyncio.run(adapter_empty.generate_content("Xin chào"))

    # Kiểm tra danh sách model
    adapter = WebAPIAdapter(secure_1psid="mock-cookie")
    models = asyncio.run(adapter.list_models())
    assert len(models) >= 1
    assert any("gemini" in m.id for m in models)


def test_factory_switching():
    """Kiểm tra Factory chuyển đổi giữa các backend client."""
    client_official = get_gemini_client("official", force_refresh=True)
    assert isinstance(client_official, OfficialGeminiClient)

    client_webapi = get_gemini_client("webapi", force_refresh=True)
    assert isinstance(client_webapi, WebAPIAdapter)


def test_factory_caching_per_backend():
    """Kiểm tra Factory lưu trữ độc lập từng client backend không làm mất của nhau."""
    official1 = get_gemini_client("official", force_refresh=True)
    webapi1 = get_gemini_client("webapi", force_refresh=True)

    official2 = get_gemini_client("official")
    webapi2 = get_gemini_client("webapi")

    assert official1 is official2
    assert webapi1 is webapi2


def test_developer_role_conversion():
    """Kiểm tra vai trò developer được quy chuẩn thành system instructions."""
    client = OfficialGeminiClient(api_key="test-key")
    messages = [
        ChatMessage(role="developer", content="You are a strict grammar checker."),
        ChatMessage(role="user", content="Check this sentence."),
    ]
    contents, system_inst = client._convert_messages(messages)
    assert system_inst == "You are a strict grammar checker."
    assert len(contents) == 1
    assert contents[0]["role"] == "user"

