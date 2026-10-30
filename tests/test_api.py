import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.models.chat import ModelInfo

client = TestClient(app)


def test_root_dashboard():
    """Kiểm tra trang chủ HTML dashboard."""
    response = client.get("/")
    assert response.status_code == 200
    assert "GeminiBridge" in response.text
    assert "Swagger UI" in response.text


def test_health_check_endpoint():
    """Kiểm tra endpoint /health."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["version"] == "1.0.0"
    assert "backend" in data
    assert "default_model" in data


def test_get_models():
    """Kiểm tra endpoint /api/models."""
    response = client.get("/api/models")
    assert response.status_code == 200
    models = response.json()
    assert isinstance(models, list)
    assert len(models) >= 1
    assert any("gemini" in m["id"] for m in models)


def test_openai_models_list():
    """Kiểm tra endpoint chuẩn OpenAI /v1/models."""
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 1
    assert "id" in data["data"][0]


def test_generate_endpoint_success():
    """Kiểm tra endpoint /api/generate với mock client."""
    mock_client = AsyncMock()
    mock_client.backend_name = "test"
    mock_client.generate_content.return_value = "Xin chào! Tôi là trợ lý AI."

    with patch("app.routes.chat.get_gemini_client", return_value=mock_client):
        response = client.post(
            "/api/generate",
            json={"prompt": "Chào bạn", "model": "gemini-2.0-flash"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Xin chào! Tôi là trợ lý AI."
        assert data["model"] == "gemini-2.0-flash"


def test_chat_endpoint_success():
    """Kiểm tra endpoint /api/chat với lịch sử hội thoại nhiều lượt."""
    mock_client = AsyncMock()
    mock_client.backend_name = "test"
    mock_client.chat.return_value = "Thủ đô của Việt Nam là Hà Nội."

    with patch("app.routes.chat.get_gemini_client", return_value=mock_client):
        response = client.post(
            "/api/chat",
            json={
                "messages": [
                    {"role": "user", "content": "Thủ đô của Việt Nam là gì?"}
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["reply"] == "Thủ đô của Việt Nam là Hà Nội."


def test_openai_chat_completions():
    """Kiểm tra endpoint /v1/chat/completions tương thích OpenAI."""
    mock_client = AsyncMock()
    mock_client.backend_name = "test"
    mock_client.chat.return_value = "Python là một ngôn ngữ lập trình phổ biến."

    with patch("app.routes.openai_compat.get_gemini_client", return_value=mock_client):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemini-2.0-flash",
                "messages": [
                    {"role": "user", "content": "Python là gì?"}
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "chat.completion"
        assert len(data["choices"]) == 1
        assert data["choices"][0]["message"]["content"] == "Python là một ngôn ngữ lập trình phổ biến."
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert "usage" in data


def test_missing_api_key_error_handling():
    """Kiểm tra phản hồi lỗi rõ ràng khi chưa có thông tin xác thực."""
    mock_client = AsyncMock()
    mock_client.generate_content.side_effect = ValueError(
        "Chưa cấu hình GEMINI_API_KEY! Vui lòng mở file .env..."
    )

    with patch("app.routes.chat.get_gemini_client", return_value=mock_client):
        response = client.post(
            "/api/generate",
            json={"prompt": "Test prompt không key"}
        )
        assert response.status_code == 400
        assert "GEMINI_API_KEY" in response.json()["detail"]


def test_openai_chat_completions_streaming():
    """Kiểm tra endpoint /v1/chat/completions khi bật stream: true."""
    async def mock_stream(*args, **kwargs):
        yield "Xin "
        yield "chào!"

    mock_client = AsyncMock()
    mock_client.backend_name = "test"
    mock_client.chat_stream = mock_stream

    with patch("app.routes.openai_compat.get_gemini_client", return_value=mock_client):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemini-flash-lite-latest",
                "messages": [{"role": "user", "content": "Chào bạn"}],
                "stream": True,
            }
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        content = response.text
        assert "chat.completion.chunk" in content
        assert "data: [DONE]" in content


def test_openai_chat_completions_null_content_and_developer_role():
    """Kiểm tra xử lý an toàn khi tin nhắn có role developer hoặc content là null."""
    mock_client = AsyncMock()
    mock_client.backend_name = "test"
    mock_client.chat.return_value = "Phản hồi thử nghiệm."

    with patch("app.routes.openai_compat.get_gemini_client", return_value=mock_client):
        response = client.post(
            "/v1/chat/completions",
            json={
                "messages": [
                    {"role": "developer", "content": "You are a helpful assistant."},
                    {"role": "user", "content": None},
                    {"role": "user", "content": "Test"}
                ]
            }
        )

        assert response.status_code == 200
        assert response.json()["choices"][0]["message"]["content"] == "Phản hồi thử nghiệm."


def test_openai_images_generations():
    """Kiểm tra endpoint /v1/images/generations."""
    mock_client = AsyncMock()
    mock_client.backend_name = "test"
    mock_client.generate_images.return_value = ["http://127.0.0.1:8200/outputs/test.png"]

    with patch("app.routes.openai_compat.get_gemini_client", return_value=mock_client):
        response = client.post(
            "/v1/images/generations",
            json={"prompt": "A cute cat"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1
        assert "test.png" in data["data"][0]["url"]


def test_openai_models_includes_video_models():
    """Kiểm tra endpoint /v1/models có chứa các model video mới (google-flow, google-vids)."""
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    model_ids = [m["id"] for m in data["data"]]
    assert "google-flow" in model_ids
    assert "google-vids" in model_ids


def test_openai_videos_generations_flow():
    """Kiểm tra endpoint OpenAI chuẩn /v1/videos/generations với Google Flow."""
    mock_url = "http://127.0.0.1:8200/outputs/videos/flow_test123.mp4"
    with patch("app.clients.video_generator.video_manager.generate_video", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_url
        response = client.post(
            "/v1/videos/generations",
            json={
                "prompt": "Cinematic ocean sunset",
                "model": "google-flow"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["url"] == mock_url
        mock_gen.assert_awaited_once_with(
            prompt="Cinematic ocean sunset",
            service="flow",
            aspect_ratio="16:9",
            duration=10
        )


def test_openai_videos_generations_vids():
    """Kiểm tra endpoint OpenAI chuẩn /v1/videos/generations với Google Vids."""
    mock_url = "http://127.0.0.1:8200/outputs/videos/vids_test456.mp4"
    with patch("app.clients.video_generator.video_manager.generate_video", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_url
        response = client.post(
            "/v1/videos/generations",
            json={
                "prompt": "Tokyo neon night",
                "model": "google-vids",
                "aspect_ratio": "9:16"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"][0]["url"] == mock_url
        mock_gen.assert_awaited_once_with(
            prompt="Tokyo neon night",
            service="vids",
            aspect_ratio="9:16",
            duration=10
        )


def test_openai_videos_generations_missing_prompt():
    """Kiểm tra báo lỗi khi thiếu prompt tạo video."""
    response = client.post(
        "/v1/videos/generations",
        json={"prompt": ""}
    )
    assert response.status_code == 400


def test_direct_video_generate_endpoint():
    """Kiểm tra endpoint REST trực tiếp /api/video/generate."""
    mock_url = "http://127.0.0.1:8200/outputs/videos/vids_abc.mp4"
    with patch("app.clients.video_generator.video_manager.generate_video", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_url
        response = client.post(
            "/api/video/generate",
            json={
                "prompt": "Floating glowing particles",
                "service": "vids"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["service"] == "Google Vids"
        assert data["video_url"] == mock_url
        assert data["file_name"] == "vids_abc.mp4"


def test_direct_video_list_endpoint():
    """Kiểm tra endpoint /api/video/list."""
    response = client.get("/api/video/list")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

